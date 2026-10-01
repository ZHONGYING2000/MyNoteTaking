import json
import os
import unittest
from unittest.mock import patch

from translator import TranslationError, _parse_translation, translate_note


class FakeCompletion:
    def __init__(self, content):
        self.choices = [type('Choice', (), {
            'message': type('Message', (), {'content': content})()
        })()]


class FakeCompletions:
    def __init__(self, content):
        self.content = content
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return FakeCompletion(self.content)


class FakeClient:
    def __init__(self, content):
        self.completions = FakeCompletions(content)
        self.chat = type('Chat', (), {
            'completions': self.completions
        })()


class TranslatorTests(unittest.TestCase):
    def test_parse_translation_requires_title_and_content_strings(self):
        with self.assertRaises(TranslationError):
            _parse_translation(json.dumps({'title': 'Only title'}))

        with self.assertRaises(TranslationError):
            _parse_translation('```json\n{"title":"x","content":"y"}\n```')

    @patch('translator._create_client')
    @patch.dict(os.environ, {}, clear=True)
    def test_translate_note_uses_deepseek_default_model(self, create_client):
        client = FakeClient('{"title":"你好","content":"世界"}')
        create_client.return_value = client

        result = translate_note('Hello', 'World', target_language='Chinese')

        self.assertEqual(result, {'title': '你好', 'content': '世界'})
        self.assertEqual(
            client.completions.kwargs['model'],
            'deepseek/deepseek-v4-flash-0731',
        )
        create_client.assert_called_once()


if __name__ == '__main__':
    unittest.main()