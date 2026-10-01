import io
import unittest
from unittest.mock import Mock, patch

from src.main import app
from src.models.attachment import Attachment
from src.models.note import Note, db
import src.routes.note as note_routes


class NoteAttachmentTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
        response = self.client.post('/api/notes', json={
            'title': 'Attachment test',
            'content': 'Test note',
        })
        self.assertEqual(response.status_code, 201)
        self.note_id = response.get_json()['id']

    def tearDown(self):
        with app.app_context():
            note = db.session.get(Note, self.note_id)
            if note:
                db.session.delete(note)
                db.session.commit()

    def upload_file(self, filename='image.png', content=b'image bytes'):
        return self.client.post(
            f'/api/notes/{self.note_id}/attachments',
            data={'file': (io.BytesIO(content), filename, 'image/png')},
            content_type='multipart/form-data',
        )

    @patch.object(note_routes, 'get_s3_client')
    def test_upload_and_list_attachment(self, get_s3_client):
        storage = Mock()
        get_s3_client.return_value = storage

        response = self.upload_file(filename='旅行 照片.png')

        self.assertEqual(response.status_code, 201)
        attachment = response.get_json()
        self.assertEqual(attachment['filename'], '旅行 照片.png')
        self.assertEqual(attachment['size'], len(b'image bytes'))
        storage.put_object.assert_called_once()
        self.assertEqual(storage.put_object.call_args.kwargs['Bucket'], 'note-attachments')

        listing = self.client.get(f'/api/notes/{self.note_id}/attachments')
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.get_json()[0]['id'], attachment['id'])

    @patch.object(note_routes, 'get_s3_client')
    def test_download_redirects_to_signed_url(self, get_s3_client):
        storage = Mock()
        storage.generate_presigned_url.return_value = 'https://storage.example/signed'
        get_s3_client.return_value = storage
        upload = self.upload_file()
        attachment_id = upload.get_json()['id']

        response = self.client.get(
            f'/api/notes/{self.note_id}/attachments/{attachment_id}/download'
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], 'https://storage.example/signed')
        self.assertEqual(storage.generate_presigned_url.call_args.kwargs['ExpiresIn'], 300)

    def test_upload_rejects_files_over_limit(self):
        response = self.upload_file(content=b'x' * (4 * 1024 * 1024 + 1))

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.get_json()['error']['code'], 'file_too_large')

    @patch.object(note_routes, 'get_s3_client')
    def test_deleting_note_deletes_its_objects(self, get_s3_client):
        storage = Mock()
        storage.delete_objects.return_value = {'Deleted': []}
        get_s3_client.return_value = storage
        self.upload_file()

        response = self.client.delete(f'/api/notes/{self.note_id}')

        self.assertEqual(response.status_code, 204)
        storage.delete_objects.assert_called_once()
        self.assertEqual(storage.delete_objects.call_args.kwargs['Bucket'], 'note-attachments')


if __name__ == '__main__':
    unittest.main()