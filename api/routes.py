from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Literal
from bson import ObjectId
from io import BytesIO
from pymongo import ReturnDocument

from services.story_service import generate_ai_story, text_to_speech, fetch_image_url
from db.mongo import story_collection

router = APIRouter()
audio_cache = {}  # In-memory cache for audio BytesIO objects


class Story(BaseModel):
    id: str
    genre: str
    theme: str
    length: str
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


class ManualStoryRequest(BaseModel):
    genre: str
    theme: str
    length: str
    title: str
    content: str
    status: Literal["draft", "published"]
    source: Literal["manual"] = "manual"


class StoryUpdate(BaseModel):
    title: str
    content: str
    status: Literal["draft", "published"]


# --- AI-generated story ---
@router.post("/generate_story", response_model=Story)
async def generate_story(request_data: StoryRequest, request: Request):
    try:
        content = await generate_ai_story(request_data.genre, request_data.theme, request_data.length)
        audio_bytes = await text_to_speech(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Story generation failed: {e}")

    # Extract a concise title from the first line (max 5 words)
    first_line = content.strip().split("\n")[0]
    title_words = first_line.split()
    title = " ".join(title_words[:5]) if len(title_words) > 5 else first_line

    story_id = str(ObjectId())
    audio_cache[story_id] = audio_bytes

    # Build full absolute URL for audio streaming endpoint
    audio_url = str(request.url_for("stream_audio", story_id=story_id))

    # Fetch image URL with theme and genre keywords
    try:
        image_url = await fetch_image_url(title=title, theme=request_data.theme, genre=request_data.genre)
    except Exception:
        image_url = "https://source.unsplash.com/800x600/?story"

    story_doc = {
        "_id": ObjectId(story_id),
        "genre": request_data.genre,
        "theme": request_data.theme,
        "length": request_data.length,
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
        audio_bytes = await text_to_speech(request_data.content)
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
            audio = await text_to_speech(story["content"])
            audio_cache[story_id] = audio
        except Exception:
            raise HTTPException(status_code=500, detail="Audio generation failed")
    audio.seek(0)  # reset pointer before streaming
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
