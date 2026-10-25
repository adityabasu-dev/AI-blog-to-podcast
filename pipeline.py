from firecrawl import Firecrawl
import os
from dotenv import load_dotenv
import re
from google import genai
from elevenlabs import ElevenLabs
from urllib.parse import urlparse

load_dotenv()

MAX_SCRIPT_CHARS = 2000
MIN_ARTICLE_CHARS = 300
MAX_ARTICLE_CHARS = 100_000

DEFAULT_VOICE_ID = "onwK4e9ZLuTAKqWW03F9"
DEFAULT_TTS_MODEL = "eleven_flash_v2_5"


class ScriptValidationError(ValueError):
    def __init__(self, message, script):
        super().__init__(message)
        self.script = script


def get_api_key(name):
    key = os.getenv(name)

    if not key:
        raise ValueError(
            f"{name} is missing from your .env file."
        )

    return key


def scrape_blog(url):
    try:
        client = Firecrawl(
            api_key=get_api_key("FIRECRAWL_API_KEY")
        )

        data = client.scrape(
            url,
            formats=["markdown"],
            only_main_content=True
        )

        markdown = getattr(data, "markdown", None)

        if not isinstance(markdown, str) or not markdown.strip():
            raise ValueError(
                "Couldn't extract an article from that page."
            )

        return markdown

    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(
            f"Article scraping failed: {e}"
        ) from e


def clean_markdown(md_text):
    # 1. Remove footer sections
    md_text = re.split(
        r'(?im)^(?:Posted in|#{0,6}\s*Related articles)\s*$',
        md_text,
        maxsplit=1
    )[0]

    # 2. Remove Markdown images
    clean_text = re.sub(
        r'!\[[^\]]*\]\([^)]*\)', '', md_text
    )

    # 3. Remove links but preserve their text
    clean_text = re.sub(
        r'\[([^\]]+)\]\([^)]+\)', r'\1', clean_text
    )

    # 4. Remove remaining URLs
    clean_text = re.sub(
        r'https?://[^\s)>]+', '', clean_text
    )

    # 5. Remove Markdown table lines
    clean_text = re.sub(
        r'(?m)^\s*\|.*$',
        '', clean_text
    )

    # 6. Remove Learn more lines
    clean_text = re.sub(
        r'(?im)^\s*Learn more:.*$',
        '', clean_text
    )

    # 7. Remove Get started call to action
    clean_text = re.sub(
        r'(?i)\bGet started\b\s*[\*\s.]*',
        '',
        clean_text
    )

    # 8. Remove Markdown headings and bold markers
    clean_text = re.sub(r'(?m)^\s*#{1,6}\s*', '', clean_text)
    clean_text = clean_text.replace('**', '')

    # 9. Remove escaped Markdown characters
    clean_text = re.sub(r'\\([\[\]*_])', r'\1', clean_text)

    # 10. Remove excessive blank lines
    clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)
    return clean_text.strip()


def generate_script(clean_text):
    try:
        client = genai.Client(
            api_key=get_api_key("GEMINI_API_KEY")
        )

        response = client.interactions.create(
            model="gemini-3.5-flash-lite",
            system_instruction=f"""
            You are a professional podcast scriptwriter.

            Convert this technology article into
            a concise, engaging podcast narration.

            Rules:
            - Maximum {MAX_SCRIPT_CHARS} characters.
            - Natural, conversational tone.
            - Explain technical concepts simply.
            - Preserve important facts.
            - No Markdown formatting.
            - No URLs or promotional calls to action.
            - Output only the narration.
            """,
            input=clean_text,
            generation_config={
                "max_output_tokens": 2000,
                "temperature": 0.7,
            }
        )

        return response.output_text, getattr(
            response, "status", None
        )

    except Exception as e:
        raise RuntimeError(
            f"Script generation failed: {e}"
        ) from e



def validate_script(script, max_chars=MAX_SCRIPT_CHARS, status=None):
    # 1. Check for empty or invalid text
    if not isinstance(script, str) or not script.strip():
        return False, "Script is empty or invalid", ""

    script = script.strip()

    # 2. Check interaction status
    if str(status).lower() != "completed":
        return False, f"Model output was incomplete (status: {status})", script

    # 3. Check character limit
    if len(script) > max_chars:
        return False, f"Script exceeds {max_chars} characters", script

    # 4. Check ending punctuation
    valid_endings = (".", "!", "?", '"', "'", "”", "’")

    if not script.endswith(valid_endings):
        return False, "Script may have an incomplete ending", script

    return True, "Script is ready for TTS", script


def generate_audio(
    script,
    voice_id=DEFAULT_VOICE_ID,
    model_id=DEFAULT_TTS_MODEL
):
    is_valid, reason, script = validate_script(
        script,
        status="completed"
    )

    if not is_valid:
        raise ValueError(reason)

    try:
        client = ElevenLabs(
            api_key=get_api_key("ELEVENLABS_API_KEY")
        )

        audio = client.text_to_speech.convert(
            model_id=model_id,
            voice_id=voice_id,
            text=script
        )

        audio_bytes = b"".join(
            chunk for chunk in audio if chunk
        )

        if not audio_bytes:
            raise RuntimeError("ElevenLabs returned empty audio.")

        return audio_bytes

    except Exception as e:
        raise RuntimeError(
            f"Audio generation failed: {e}"
        ) from e


def blog_to_script(url):
    parsed = urlparse(url.strip())

    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Please enter a valid blog URL.")
    markdown = scrape_blog(url)
    clean_text = clean_markdown(markdown)

    if len(clean_text) < MIN_ARTICLE_CHARS:
        raise ValueError(
            "Couldn't extract enough article content from that page."
        )

    if len(clean_text) > MAX_ARTICLE_CHARS:
        raise ValueError(
            "This article is too long to process."
        )

    script, status = generate_script(clean_text)

    is_valid, reason, script = validate_script(
        script,
        max_chars=MAX_SCRIPT_CHARS,
        status=status
    )

    if not is_valid:
        raise ScriptValidationError(reason, script)

    return script
