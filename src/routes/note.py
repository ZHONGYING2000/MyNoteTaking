from io import BytesIO
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request, send_file

from src.models.attachment import Attachment
from src.models.note import Note, db
from src.storage import StorageConfigurationError, get_s3_client
from translator import TranslationError, translate_note

note_bp = Blueprint('note', __name__)
MAX_ATTACHMENT_SIZE = 4 * 1024 * 1024

@note_bp.route('/translate', methods=['POST'])
def translate_text():
    """Translate plain text without creating or changing a note."""
    data = request.get_json(silent=True) or {}
    text = data.get('text')
    target_language = data.get('target_language')
    source_language = data.get('source_language', 'auto')

    if not isinstance(text, str) or not text.strip():
        return jsonify({
            'error': {
                'code': 'invalid_request',
                'message': 'text is required',
            }
        }), 400
    if not isinstance(target_language, str) or not target_language.strip():
        return jsonify({
            'error': {
                'code': 'invalid_request',
                'message': 'target_language is required',
            }
        }), 400
    if not isinstance(source_language, str) or not source_language.strip():
        return jsonify({
            'error': {
                'code': 'invalid_request',
                'message': 'source_language must be a non-empty string',
            }
        }), 400

    try:
        translation = translate_note(
            title='',
            content=text,
            source_language=source_language.strip(),
            target_language=target_language.strip(),
        )
    except TranslationError as error:
        return jsonify({
            'error': {
                'code': 'translation_failed',
                'message': str(error),
            }
        }), 502
    except Exception:
        return jsonify({
            'error': {
                'code': 'translation_unavailable',
                'message': 'The translation service is unavailable',
            }
        }), 502

    return jsonify({
        'source_language': source_language.strip(),
        'target_language': target_language.strip(),
        'translation': translation['content'],
    })


@note_bp.route('/notes', methods=['GET'])
def get_notes():
    """Get all notes, ordered by most recently updated"""
    notes = Note.query.order_by(Note.updated_at.desc()).all()
    return jsonify([note.to_dict() for note in notes])

@note_bp.route('/notes', methods=['POST'])
def create_note():
    """Create a new note"""
    try:
        data = request.json
        if not data or 'title' not in data or 'content' not in data:
            return jsonify({'error': 'Title and content are required'}), 400
        
        note = Note(title=data['title'], content=data['content'])
        db.session.add(note)
        db.session.commit()
        return jsonify(note.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@note_bp.route('/notes/<int:note_id>', methods=['GET'])
def get_note(note_id):
    """Get a specific note by ID"""
    note = Note.query.get_or_404(note_id)
    return jsonify(note.to_dict())


@note_bp.route('/notes/<int:note_id>/attachments', methods=['GET'])
def get_note_attachments(note_id):
    note = Note.query.get_or_404(note_id)
    response = jsonify([attachment.to_dict() for attachment in note.attachments])
    response.headers['Cache-Control'] = 'no-store'
    return response


@note_bp.route('/notes/<int:note_id>/attachments', methods=['POST'])
def upload_note_attachment(note_id):
    note = Note.query.get_or_404(note_id)
    uploaded_file = request.files.get('file')
    if uploaded_file is None or not uploaded_file.filename:
        return jsonify({'error': 'A file is required'}), 400

    filename = uploaded_file.filename.replace('\\', '/').rsplit('/', 1)[-1].strip()
    filename = filename[:255] or 'attachment'
    uploaded_file.stream.seek(0, 2)
    file_size = uploaded_file.stream.tell()
    uploaded_file.stream.seek(0)
    if file_size == 0:
        return jsonify({'error': 'The uploaded file is empty'}), 400
    if file_size > MAX_ATTACHMENT_SIZE:
        return jsonify({
            'error': {
                'code': 'file_too_large',
                'message': 'Each uploaded file must be 4 MB or smaller',
            }
        }), 413

    object_key = f'notes/{note.id}/{uuid4().hex}'
    bucket = current_app.config['ATTACHMENTS_BUCKET']
    try:
        storage = get_s3_client()
        storage.put_object(
            Bucket=bucket,
            Key=object_key,
            Body=uploaded_file.stream,
            ContentType=uploaded_file.mimetype or 'application/octet-stream',
        )
    except StorageConfigurationError:
        return jsonify({'error': 'Attachment storage is not configured'}), 503
    except Exception:
        current_app.logger.exception('Failed to upload note attachment')
        return jsonify({'error': 'Unable to upload attachment'}), 502

    attachment = Attachment(
        note_id=note.id,
        filename=filename,
        object_key=object_key,
        content_type=uploaded_file.mimetype or 'application/octet-stream',
        size=file_size,
    )
    try:
        db.session.add(attachment)
        db.session.commit()
    except Exception:
        db.session.rollback()
        try:
            storage.delete_object(Bucket=bucket, Key=object_key)
        except Exception:
            current_app.logger.exception('Failed to clean up an unlinked attachment')
        current_app.logger.exception('Failed to save attachment metadata')
        return jsonify({'error': 'Unable to save attachment metadata'}), 500

    return jsonify(attachment.to_dict()), 201


@note_bp.route(
    '/notes/<int:note_id>/attachments/<int:attachment_id>/download', methods=['GET']
)
def download_note_attachment(note_id, attachment_id):
    Note.query.get_or_404(note_id)
    attachment = Attachment.query.filter_by(
        id=attachment_id, note_id=note_id
    ).first_or_404()

    try:
        storage = get_s3_client()
        stored_object = storage.get_object(
            Bucket=current_app.config['ATTACHMENTS_BUCKET'],
            Key=attachment.object_key,
        )
        file_content = stored_object['Body'].read()
    except StorageConfigurationError:
        return jsonify({'error': 'Attachment storage is not configured'}), 503
    except Exception:
        current_app.logger.exception('Failed to download note attachment')
        return jsonify({'error': 'Unable to download attachment'}), 502

    response = send_file(
        BytesIO(file_content),
        mimetype='application/octet-stream',
        as_attachment=True,
        download_name=attachment.filename,
        max_age=0,
    )
    response.headers['Cache-Control'] = 'no-store'
    return response


@note_bp.route('/notes/<int:note_id>/translate', methods=['POST'])
def translate_note_route(note_id):
    """Translate a note without changing the stored note."""
    note = Note.query.get_or_404(note_id)
    data = request.get_json(silent=True) or {}
    target_language = data.get('target_language')
    source_language = data.get('source_language', 'auto')

    if not isinstance(target_language, str) or not target_language.strip():
        return jsonify({
            'error': {
                'code': 'invalid_request',
                'message': 'target_language is required',
            }
        }), 400
    if not isinstance(source_language, str) or not source_language.strip():
        return jsonify({
            'error': {
                'code': 'invalid_request',
                'message': 'source_language must be a non-empty string',
            }
        }), 400

    try:
        translation = translate_note(
            title=note.title,
            content=note.content,
            source_language=source_language.strip(),
            target_language=target_language.strip(),
        )
    except TranslationError as error:
        return jsonify({
            'error': {
                'code': 'translation_failed',
                'message': str(error),
            }
        }), 502
    except Exception:
        return jsonify({
            'error': {
                'code': 'translation_unavailable',
                'message': 'The translation service is unavailable',
            }
        }), 502

    return jsonify({
        'note_id': note.id,
        'source_language': source_language.strip(),
        'target_language': target_language.strip(),
        'translation': translation,
    })

@note_bp.route('/notes/<int:note_id>', methods=['PUT'])
def update_note(note_id):
    """Update a specific note"""
    try:
        note = Note.query.get_or_404(note_id)
        data = request.json
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        note.title = data.get('title', note.title)
        note.content = data.get('content', note.content)
        db.session.commit()
        return jsonify(note.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@note_bp.route('/notes/<int:note_id>', methods=['DELETE'])
def delete_note(note_id):
    """Delete a specific note"""
    try:
        note = Note.query.get_or_404(note_id)
        if note.attachments:
            storage = get_s3_client()
            result = storage.delete_objects(
                Bucket=current_app.config['ATTACHMENTS_BUCKET'],
                Delete={
                    'Objects': [{'Key': attachment.object_key} for attachment in note.attachments],
                    'Quiet': True,
                },
            )
            if result.get('Errors'):
                return jsonify({'error': 'Unable to delete note attachments'}), 502
        db.session.delete(note)
        db.session.commit()
        return '', 204
    except StorageConfigurationError:
        return jsonify({'error': 'Attachment storage is not configured'}), 503
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@note_bp.route('/notes/search', methods=['GET'])
def search_notes():
    """Search notes by title or content"""
    query = request.args.get('q', '')
    if not query:
        return jsonify([])
    
    notes = Note.query.filter(
        (Note.title.contains(query)) | (Note.content.contains(query))
    ).order_by(Note.updated_at.desc()).all()
    
    return jsonify([note.to_dict() for note in notes])

