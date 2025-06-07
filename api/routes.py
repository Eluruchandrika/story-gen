import os
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Literal
from bson import ObjectId
from io import BytesIO
from pymongo import ReturnDocument
import httpx

from services.story_service import generate_ai_story, generate_story_title, text_to_speech, fetch_image_url
from db.mongo import story_collection

router = APIRouter()
audio_cache = {}  # In-memory cache for audio BytesIO objects

# UNSPLASH_ACCESS_KEY is already loaded in story_service, but keeping this for explicit clarity if needed elsewhere in routes
# UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY") 

class Story(BaseModel):
    id: str
    genre: str
    theme: str
    length: str
    language: str # Added language field
    title: str
    content: str
    audio_url: str
    image_url: str
    source: Literal["ai", "manual"]
    status: Literal["draft", "published"]

class StoryRequest(BaseModel):
    genre: str
    theme: str
    length: str
    language: str = "english" # Added language with a default value

class ManualStoryRequest(BaseModel):
    genre: str
    theme: str
    length: str
    title: str
    content: str
    status: Literal["draft", "published"]
    language: str = "english" # Added language with a default value
    source: Literal["manual"] = "manual"

class StoryUpdate(BaseModel):
    title: str
    content: str
    status: Literal["draft", "published"]

# --- AI-generated story ---
@router.post("/generate_story", response_model=Story)
async def generate_story(request_data: StoryRequest, request: Request):
    try:
        content = await generate_ai_story(
            request_data.genre,
            request_data.theme,
            request_data.length,
            request_data.language # Pass language to AI story generation
        )
        # Generate title using the new generate_story_title function
        title = await generate_story_title(content, request_data.language)
        audio_bytes = await text_to_speech(content, request_data.language) # Pass language to text-to-speech
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Story generation failed: {e}")

    story_id = str(ObjectId())
    audio_cache[story_id] = audio_bytes

    audio_url = str(request.url_for("stream_audio", story_id=story_id))

    try:
        image_url = await fetch_image_url(title=title, theme=request_data.theme, genre=request_data.genre)
    except Exception:
        image_url = "https://source.unsplash.com/800x600/?story"

    story_doc = {
        "_id": ObjectId(story_id),
        "genre": request_data.genre,
        "theme": request_data.theme,
        "length": request_data.length,
        "language": request_data.language, # Store language
        "title": title,
        "content": content,
        "audio_url": audio_url,
        "image_url": image_url,
        "source": "ai",
        "status": "published"
    }

    await story_collection.insert_one(story_doc)
    story_doc["id"] = story_id
    del story_doc["_id"]
    return Story(**story_doc)

# --- Manual story ---
@router.post("/create_manual_story", response_model=Story)
async def create_manual_story(request_data: ManualStoryRequest, request: Request):
    try:
        audio_bytes = await text_to_speech(request_data.content, request_data.language) # Pass language to text-to-speech
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio generation failed: {e}")

    story_id = str(ObjectId())
    audio_cache[story_id] = audio_bytes

    audio_url = str(request.url_for("stream_audio", story_id=story_id))

    try:
        image_url = await fetch_image_url(title=request_data.title, theme=request_data.theme, genre=request_data.genre)
    except Exception:
        image_url = "https://source.unsplash.com/800x600/?story"

    story_doc = {
        "_id": ObjectId(story_id),
        "genre": request_data.genre,
        "theme": request_data.theme,
        "length": request_data.length,
        "language": request_data.language, # Store language
        "title": request_data.title,
        "content": request_data.content,
        "audio_url": audio_url,
        "image_url": image_url,
        "source": request_data.source,
        "status": request_data.status
    }

    await story_collection.insert_one(story_doc)
    story_doc["id"] = story_id
    del story_doc["_id"]
    return Story(**story_doc)

# --- Serve audio stream ---
@router.get("/story_audio/{story_id}")
async def stream_audio(story_id: str):
    audio: BytesIO = audio_cache.get(story_id)
    if not audio:
        story = await story_collection.find_one({"_id": ObjectId(story_id)})
        if not story:
            raise HTTPException(status_code=404, detail="Story not found")
        try:
            # When retrieving from DB, also ensure language is passed if available, default to "english"
            audio = await text_to_speech(story["content"], story.get("language", "english"))
            audio_cache[story_id] = audio
        except Exception:
            raise HTTPException(status_code=500, detail="Audio generation failed")
    audio.seek(0)
    return StreamingResponse(audio, media_type="audio/mpeg")

# --- Get all stories ---
@router.get("/stories", response_model=List[Story])
async def get_stories():
    stories_cursor = story_collection.find().sort("_id", -1)
    stories = []
    async for story in stories_cursor:
        story["id"] = str(story["_id"])
        del story["_id"]
        stories.append(Story(**story))
    return stories

# --- Get story by ID ---
@router.get("/story/{story_id}", response_model=Story)
async def get_story(story_id: str):
    story = await story_collection.find_one({"_id": ObjectId(story_id)})
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    story["id"] = str(story["_id"])
    del story["_id"]
    return Story(**story)

# --- Update story ---
@router.put("/story/{story_id}", response_model=Story)
async def update_story(story_id: str, update: StoryUpdate):
    result = await story_collection.find_one_and_update(
        {"_id": ObjectId(story_id)},
        {"$set": {"title": update.title, "content": update.content, "status": update.status}},
        return_document=ReturnDocument.AFTER
    )
    if not result:
        raise HTTPException(status_code=404, detail="Story not found")
    result["id"] = str(result["_id"])
    del result["_id"]
    return Story(**result)

# --- Delete story ---
@router.delete("/story/{story_id}")
async def delete_story(story_id: str):
    result = await story_collection.delete_one({"_id": ObjectId(story_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Story not found")
    return {"message": "Story deleted successfully"}