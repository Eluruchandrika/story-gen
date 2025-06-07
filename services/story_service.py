import os
import asyncio
from io import BytesIO
from typing import Optional

from dotenv import load_dotenv
import httpx
from gtts import gTTS

load_dotenv()

OPENROUTER_API_KEY: Optional[str] = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL: str = "openai/gpt-3.5-turbo"

if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY not set in environment variables")

async def generate_ai_story(genre: str, theme: str, length: str) -> str:
    """
    Async function to generate AI story using OpenRouter API via httpx.
    """
    prompt = f"Write a {length} {genre} story about {theme}. Make it engaging and creative."

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "http://localhost",
        "Content-Type": "application/json"
    }

    data = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": "You are a creative storyteller."},
            {"role": "user", "content": prompt}
        ]
    }

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            response = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
            response.raise_for_status()
            json_response = response.json()

            choices = json_response.get("choices")
            if not choices or not isinstance(choices, list):
                raise Exception("No choices found in OpenRouter response")

            message = choices[0].get("message")
            if not message or "content" not in message:
                raise Exception("No content found in OpenRouter response message")

            story = message["content"].strip()
            return story

        except httpx.RequestError as e:
            raise Exception(f"OpenRouter API request failed: {e}")
        except Exception as e:
            raise Exception(f"OpenRouter API error: {e}")

async def text_to_speech(story_text: str) -> BytesIO:
    """
    Async wrapper around gTTS TTS generation (blocking).
    """
    loop = asyncio.get_running_loop()

    def generate_audio():
        tts = gTTS(text=story_text, lang="en")
        audio_bytes = BytesIO()
        tts.write_to_fp(audio_bytes)
        audio_bytes.seek(0)
        return audio_bytes

    try:
        audio_bytes = await loop.run_in_executor(None, generate_audio)
        return audio_bytes
    except Exception as e:
        raise Exception(f"TTS generation failed: {e}")

async def fetch_image_url(title: str, theme: str, genre: str) -> str:
    """
    Returns a URL string from Unsplash with combined keywords.
    """
    # Filter empty or None values, replace spaces with + for URL encoding
    keywords = "+".join(
        filter(None, [title.strip().replace(" ", "+") if title else None,
                      theme.strip().replace(" ", "+") if theme else None,
                      genre.strip().replace(" ", "+") if genre else None])
    )
    if not keywords:
        keywords = "story"
    url = f"https://source.unsplash.com/800x600/?{keywords}"
    return url
