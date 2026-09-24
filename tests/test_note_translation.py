import unittest
from unittest.mock import patch

from src.main import app
import src.routes.note as note_routes


class NoteTranslationTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
        response = self.client.post('/api/notes', json={
            'title': 'Hello',
            'content': 'World',
        })
        self.note_id = response.get_json()['id']

    def tearDown(self):
        self.client.delete(f'/api/notes/{self.note_id}')

    @patch.object(note_routes, 'translate_note', return_value={
        'title': '你好',
        'content': '世界',
    })
    def test_translate_note_returns_json_preview(self, translate_note):
        response = self.client.post(
            f'/api/notes/{self.note_id}/translate',
            json={'target_language': 'Chinese'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['translation']['content'], '世界')
        translate_note.assert_called_once()

    def test_translate_note_requires_target_language(self):
        response = self.client.post(
            f'/api/notes/{self.note_id}/translate',
            json={},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['error']['code'], 'invalid_request')


if __name__ == '__main__':
    unittest.main()