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
UNSPLASH_ACCESS_KEY: Optional[str] = os.getenv("UNSPLASH_ACCESS_KEY")

if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY not set in environment variables")

if not UNSPLASH_ACCESS_KEY:
    print("Warning: UNSPLASH_ACCESS_KEY not set in environment variables. Using fallback image URLs.")

# Language codes supported by gTTS and for prompt language naming
LANGUAGE_CODES = {
    "english": "en",
    "hindi": "hi",
    "spanish": "es",
    "french": "fr",
    "german": "de",
    "bengali": "bn",
    "tamil": "ta",
    "gujarati": "gu",
    "japanese": "ja",
    "chinese": "zh",
    "portuguese": "pt",
    "italian": "it",
    "russian": "ru",
    "arabic": "ar",
    "swahili": "sw",
    "dutch": "nl",
    "kannada": "kn",
    "malayalam": "ml",
    "telugu": "te",
    "sinhala": "si",
    # Add more if needed
}

async def generate_ai_story(
    genre: str,
    theme: str,
    length: str,
    language: str = "english"
) -> str:
    """
    Async function to generate AI story using OpenRouter API via httpx,
    in the specified language.
    """
    prompt = f"Write a {length} {genre} story about {theme} in {language}. Make it engaging and creative."

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
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data
            )
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

async def generate_story_title(story_text: str, language: str = "english") -> str:
    """
    Generate a short summarized title (max 5 words) for the story text
    in the specified language.
    """
    prompt = (
        f"Summarize the following story into a short title (max 5 words) in {language}:\n\n{story_text}"
    )

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
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data
        )
        response.raise_for_status()
        json_response = response.json()
        choices = json_response.get("choices", [])
        if not choices:
            raise Exception("No choices found in OpenRouter response")
        message = choices[0].get("message", {})
        title = message.get("content", "").strip()
        # Optionally truncate to 5 words if API returns longer
        title_words = title.split()
        if len(title_words) > 5:
            title = " ".join(title_words[:5])
        return title

async def text_to_speech(story_text: str, language: str = "english") -> BytesIO:
    """
    Async wrapper around gTTS, supporting multiple languages.
    """
    loop = asyncio.get_running_loop()
    lang_code = LANGUAGE_CODES.get(language.lower(), "en")

    def generate_audio():
        tts = gTTS(text=story_text, lang=lang_code)
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
    Returns an image URL from Unsplash API using combined keywords,
    or falls back to source.unsplash.com if API call fails or key not set.
    """
    # Combine keywords, remove empties
    keywords_list = []
    if title and title.strip():
        keywords_list.append(title.strip())
    if theme and theme.strip():
        keywords_list.append(theme.strip())
    if genre and genre.strip():
        keywords_list.append(genre.strip())
    query = ", ".join(keywords_list) if keywords_list else "story"

    if not UNSPLASH_ACCESS_KEY:
        # Fallback URL (random image with keywords)
        return f"https://source.unsplash.com/800x600/?{query.replace(' ', '+')}"

    url = "https://api.unsplash.com/search/photos"
    headers = {"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"}
    params = {
        "query": query,
        "per_page": 1,
        "orientation": "landscape",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            if results:
                return results[0]["urls"]["regular"]
    except Exception:
        pass

    # Fallback if API call failed
    return f"https://source.unsplash.com/800x600/?{query.replace(' ', '+')}"
