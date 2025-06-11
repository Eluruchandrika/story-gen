import os
import asyncio
from io import BytesIO
from typing import Optional
from datetime import datetime

from dotenv import load_dotenv
import httpx
from gtts import gTTS
from bson import ObjectId

from db.mongo import story_collection  # Only story_collection now

# Load environment variables
load_dotenv()

# API Keys
OPENROUTER_API_KEY: Optional[str] = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = "openai/gpt-3.5-turbo"
UNSPLASH_ACCESS_KEY: Optional[str] = os.getenv("UNSPLASH_ACCESS_KEY")

if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY not set in environment variables")

if not UNSPLASH_ACCESS_KEY:
    print("Warning: UNSPLASH_ACCESS_KEY not set in environment variables. Using fallback image URLs.")

# Language Code Mapping
LANGUAGE_CODES = {
    "english": "en", "hindi": "hi", "spanish": "es", "french": "fr", "german": "de",
    "bengali": "bn", "tamil": "ta", "gujarati": "gu", "japanese": "ja", "chinese": "zh",
    "portuguese": "pt", "italian": "it", "russian": "ru", "arabic": "ar", "swahili": "sw",
    "dutch": "nl", "kannada": "kn", "malayalam": "ml", "telugu": "te", "sinhala": "si"
}

# === STORY GENERATION ===
async def generate_ai_story(genre: str, theme: str, length: str, language: str = "english") -> str:
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
            response = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
            response.raise_for_status()
            story = response.json()["choices"][0]["message"]["content"].strip()
            return story
        except Exception as e:
            raise Exception(f"OpenRouter API failed: {e}")

# === TITLE GENERATION ===
async def generate_story_title(story_text: str, language: str = "english") -> str:
    prompt = f"Summarize the following story into a short title (max 5 words) in {language}:\n\n{story_text}"
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
        response = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        response.raise_for_status()
        title = response.json()["choices"][0]["message"]["content"].strip()
        return " ".join(title.split()[:5])  # limit to 5 words

# === TEXT TO SPEECH ===
async def text_to_speech(story_text: str, language: str = "english") -> BytesIO:
    loop = asyncio.get_running_loop()
    lang_code = LANGUAGE_CODES.get(language.lower(), "en")

    def generate_audio(text: str, lang: str) -> BytesIO:
        tts = gTTS(text=text, lang=lang)
        audio_bytes = BytesIO()
        tts.write_to_fp(audio_bytes)
        audio_bytes.seek(0)
        return audio_bytes

    try:
        return await loop.run_in_executor(None, generate_audio, story_text, lang_code)
    except Exception:
        fallback = await loop.run_in_executor(None, generate_audio, "Audio unavailable. Please try again later.", "en")
        return fallback

# === IMAGE FETCH ===
async def fetch_image_url(title: str, theme: str, genre: str) -> str:
    query = ", ".join(filter(None, [title.strip(), theme.strip(), genre.strip()]))
    query = query if query else "story"

    if not UNSPLASH_ACCESS_KEY:
        return f"https://source.unsplash.com/800x600/?{query.replace(' ', '+')}"

    url = "https://api.unsplash.com/search/photos"
    headers = {"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"}
    params = {"query": query, "per_page": 1, "orientation": "landscape"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            results = response.json().get("results", [])
            if results:
                return results[0]["urls"]["regular"]
    except Exception:
        pass

    return f"https://source.unsplash.com/800x600/?{query.replace(' ', '+')}"

# === SAVE GENERATED STORY ===
async def save_story_to_db(user_id: str, username: str, story_data: dict) -> dict:
    story_doc = {
        **story_data,
        "user_id": ObjectId(user_id),
        "username": username,
        "status": "published",
        "source": "ai",
        "bookmarked_by": [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    result = await story_collection.insert_one(story_doc)
    story_doc["id"] = str(result.inserted_id)
    story_doc["user_id"] = str(story_doc["user_id"])
    story_doc["created_at"] = story_doc["created_at"].isoformat() + "Z"

    return story_doc

# === SAVE A STORY TO USER'S LIBRARY (Bookmark) ===
async def save_to_user_library(user_id: str, story_id: str) -> bool:
    # Check if user already bookmarked
    story = await story_collection.find_one({
        "_id": ObjectId(story_id),
        "bookmarked_by": str(user_id)
    })

    if story:
        # Already bookmarked
        return False

    update_result = await story_collection.update_one(
        {"_id": ObjectId(story_id)},
        {"$addToSet": {"bookmarked_by": str(user_id)}}
    )

    return update_result.modified_count == 1
