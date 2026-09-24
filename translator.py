import argparse
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-4o-mini"
PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "translate_prompt.md"

load_dotenv()


class TranslationError(RuntimeError):
    """Raised when translation cannot produce a valid result."""


def load_translation_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except OSError as error:
        raise TranslationError(f"Unable to read translation prompt: {error}") from error


def _create_client() -> OpenAI:
    api_key = os.getenv("OPEN_ROUTER_KEY")
    if not api_key:
        raise TranslationError("OPEN_ROUTER_KEY is not set in .env or the environment")

    return OpenAI(
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
    )


def _parse_translation(content: str | None) -> dict[str, str]:
    if not content or not content.strip():
        raise TranslationError("The model returned an empty translation")

    try:
        result: Any = json.loads(content)
    except json.JSONDecodeError as error:
        raise TranslationError("The model returned invalid JSON") from error

    if not isinstance(result, dict):
        raise TranslationError("The model response must be a JSON object")

    if set(result) != {"title", "content"} or not all(
        isinstance(result[field], str) for field in ("title", "content")
    ):
        raise TranslationError(
            'The model response must contain only string fields "title" and "content"'
        )

    return {"title": result["title"], "content": result["content"]}


def translate_note(
    title: str,
    content: str,
    target_language: str,
    source_language: str = "auto",
) -> dict[str, str]:
    """Translate a note and return its validated JSON representation."""
    if not target_language.strip():
        raise TranslationError("target_language must not be empty")

    prompt = load_translation_prompt().format(
        source_language=source_language,
        target_language=target_language,
        title=title,
        content=content,
    )
    client = _create_client()

    response = client.chat.completions.create(
        model=os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL),
        messages=[
            {
                "role": "system",
                "content": "Follow the translation task and JSON output format exactly.",
            },
            {"role": "user", "content": prompt},
        ],
        extra_body={"provider": {"allow_fallbacks": True}},
    )
    return _parse_translation(response.choices[0].message.content)


def llm_generate(prompt: str) -> str:
    """Translate command-line text into Chinese for backwards compatibility."""
    result = translate_note("", prompt, target_language="Chinese")
    return result["content"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Translate a command-line prompt through OpenRouter."
    )
    parser.add_argument("prompt", nargs="+", help="Text to translate")
    parser.add_argument("--source-language", default="auto")
    parser.add_argument("--target-language", default="Chinese")
    args = parser.parse_args()

    try:
        result = translate_note(
            title="",
            content=" ".join(args.prompt),
            source_language=args.source_language,
            target_language=args.target_language,
        )
        print(json.dumps(result, ensure_ascii=False))
    except Exception as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()