from datetime import datetime

from src.models.user import db


class Attachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    note_id = db.Column(
        db.Integer, db.ForeignKey('note.id', ondelete='CASCADE'), nullable=False, index=True
    )
    filename = db.Column(db.String(255), nullable=False)
    object_key = db.Column(db.String(512), nullable=False, unique=True)
    content_type = db.Column(db.String(255), nullable=False)
    size = db.Column(db.BigInteger, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    note = db.relationship('Note', back_populates='attachments')

    def to_dict(self):
        return {
            'id': self.id,
            'note_id': self.note_id,
            'filename': self.filename,
            'content_type': self.content_type,
            'size': self.size,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }