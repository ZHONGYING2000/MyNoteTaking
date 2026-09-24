import unittest
from unittest.mock import patch

from src.main import app
import src.routes.note as note_routes


class TextTranslationTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

    @patch.object(note_routes, 'translate_note', return_value={
        'title': '',
        'content': '你好，世界',
    })
    def test_translate_text_returns_translated_content(self, translate_note):
        response = self.client.post('/api/translate', json={
            'text': 'Hello, world',
            'target_language': 'Chinese',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['translation'], '你好，世界')
        translate_note.assert_called_once_with(
            title='',
            content='Hello, world',
            source_language='auto',
            target_language='Chinese',
        )

    def test_translate_text_requires_text(self):
        response = self.client.post('/api/translate', json={
            'target_language': 'Chinese',
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['error']['code'], 'invalid_request')


if __name__ == '__main__':
    unittest.main()