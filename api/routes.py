import os
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Literal, Optional # Added Optional for a potential User class later
from bson import ObjectId
from io import BytesIO
from pymongo import ReturnDocument

from services.story_service import (
    generate_ai_story,
    generate_story_title,
    text_to_speech,
    fetch_image_url
)
from db.mongo import story_collection

router = APIRouter()
audio_cache = {}  # In-memory cache for audio BytesIO objects

# Define a placeholder for user authentication/dependency injection
# In a real app, this would be a function that authenticates a user
# and returns their ID or a User object.
# async def get_current_user_id(request: Request) -> str:
#     # For now, we'll just use a default 'guest' or look for a header
#     # Replace this with actual JWT decoding or session management
#     user_id = request.headers.get("x-user-id", "guest")
#     if user_id == "guest":
#         # Optional: Raise HTTPException if authentication is required for a route
#         # raise HTTPException(status_code=401, detail="Authentication required")
#         pass # Allow guest for now
#     return user_id

# Let's keep the user_id in the body for now as per previous discussion,
# but note that for production, fetching user_id from token is better.

class Story(BaseModel):
    id: str
    user_id: str = "guest"
    username: str = "Guest"
    genre: str
    theme: str
    length: str
    language: str
    title: str
    content: str
    audio_url: str
    image_url: str
    source: Literal["ai", "manual"]
    status: Literal["draft", "published"]
    bookmarked_by: List[str] = []
    created_at: str = None

class StoryRequest(BaseModel):
    genre: str
    theme: str
    length: str
    language: str = "english"
    status: Literal["draft", "published"] = "published"
    user_id: str = "guest"
    username: str = "Guest"

class ManualStoryRequest(BaseModel):
    genre: str
    theme: str
    length: str
    title: str
    content: str
    status: Literal["draft", "published"]
    language: str = "english"
    source: Literal["manual"] = "manual"
    user_id: str = "guest"
    username: str = "Guest"

class StoryUpdate(BaseModel):
    title: str
    content: str
    status: Literal["draft", "published"]

# --- AI-generated story ---
@router.post("/generate_story", response_model=Story)
async def generate_story(request_data: StoryRequest, request: Request):
    if request_data.status == "published" and request_data.user_id == "guest":
        raise HTTPException(status_code=403, detail="Guests cannot publish stories")

    try:
        content = await generate_ai_story(
            request_data.genre,
            request_data.theme,
            request_data.length,
            request_data.language
        )
        title = await generate_story_title(content, request_data.language)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Story generation failed: {e}")

    story_id = str(ObjectId())

    try:
        audio_bytes = await text_to_speech(content, request_data.language)
        audio_cache[story_id] = audio_bytes
        audio_url = str(request.url_for("stream_audio", story_id=story_id))
    except Exception as e:
        print(f"[WARN] Audio generation failed: {e}")
        audio_url = str(request.url_for("default_audio"))

    try:
        image_url = await fetch_image_url(
            title=title,
            theme=request_data.theme,
            genre=request_data.genre
        )
    except Exception:
        image_url = "https://source.unsplash.com/800x600/?story"

    story_doc = {
        "_id": ObjectId(story_id),
        "user_id": request_data.user_id,
        "username": request_data.username,
        "genre": request_data.genre,
        "theme": request_data.theme,
        "length": request_data.length,
        "language": request_data.language,
        "title": title,
        "content": content,
        "audio_url": audio_url,
        "image_url": image_url,
        "source": "ai",
        "status": request_data.status,
        "bookmarked_by": [], # New stories start with an empty bookmarked_by list
        "created_at": str(request.scope.get("time", ""))
    }

    await story_collection.insert_one(story_doc)
    story_doc["id"] = story_id
    del story_doc["_id"]
    return Story(**story_doc)

# --- Manual story ---
@router.post("/create_manual_story", response_model=Story)
async def create_manual_story(request_data: ManualStoryRequest, request: Request):
    if request_data.status == "published" and request_data.user_id == "guest":
        raise HTTPException(status_code=403, detail="Guests cannot publish stories")

    story_id = str(ObjectId())

    try:
        audio_bytes = await text_to_speech(request_data.content, request_data.language)
        audio_cache[story_id] = audio_bytes
        audio_url = str(request.url_for("stream_audio", story_id=story_id))
    except Exception as e:
        print(f"[WARN] Audio generation failed: {e}")
        audio_url = str(request.url_for("default_audio"))

    try:
        image_url = await fetch_image_url(
            title=request_data.title,
            theme=request_data.theme,
            genre=request_data.genre
        )
    except Exception:
        image_url = "https://source.unsplash.com/800x600/?story"

    story_doc = {
        "_id": ObjectId(story_id),
        "user_id": request_data.user_id,
        "username": request_data.username,
        "genre": request_data.genre,
        "theme": request_data.theme,
        "length": request_data.length,
        "language": request_data.language,
        "title": request_data.title,
        "content": request_data.content,
        "audio_url": audio_url,
        "image_url": image_url,
        "source": request_data.source,
        "status": request_data.status,
        "bookmarked_by": [], # New manual stories also start with an empty bookmarked_by list
        "created_at": str(request.scope.get("time", ""))
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
            audio = await text_to_speech(story["content"], story.get("language", "english"))
            audio_cache[story_id] = audio
        except Exception:
            return await default_audio()
    audio.seek(0)
    return StreamingResponse(audio, media_type="audio/mpeg")

# --- Serve default audio ---
@router.get("/default_audio")
async def default_audio():
    fallback_message = "Sorry, the audio is currently unavailable for this story."
    try:
        audio = await text_to_speech(fallback_message, "english")
    except Exception:
        return StreamingResponse(BytesIO(), media_type="audio/mpeg")
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

# --- Paginated stories ---
@router.get("/stories_paginated", response_model=List[Story])
async def get_stories_paginated(skip: int = 0, limit: int = 10):
    cursor = story_collection.find().sort("_id", -1).skip(skip).limit(limit)
    stories = []
    async for story in cursor:
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
        {
            "$set": {
                "title": update.title,
                "content": update.content,
                "status": update.status
            }
        },
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

# --- Bookmark story ---
# Changed this to expect the story_id in the path, and user_id in the body (or from auth)
class BookmarkRequest(BaseModel):
    storyId: str # This field is essential to receive from the frontend
    userId: str

@router.post("/api/library/add") # Matches the frontend's POST URL
async def add_story_to_library(bookmark_request: BookmarkRequest):
    story_id = bookmark_request.storyId # Assuming storyId is passed in the request body
    user_id = bookmark_request.userId # Assuming userId is passed in the request body

    if not ObjectId.is_valid(story_id):
        raise HTTPException(status_code=400, detail="Invalid Story ID format")

    try:
        result = await story_collection.update_one(
            {"_id": ObjectId(story_id)},
            {"$addToSet": {"bookmarked_by": user_id}}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Story not found")
        if result.modified_count == 0:
            # This means the user_id was already in bookmarked_by, no change made
            return {"message": "Story already in user's library"}
        return {"message": "Story added to library"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add story to library: {str(e)}")

# --- Unbookmark story (Remove from library) ---
@router.post("/api/library/remove") # A new endpoint for removing from library
async def remove_story_from_library(bookmark_request: BookmarkRequest):
    story_id = bookmark_request.storyId
    user_id = bookmark_request.userId

    if not ObjectId.is_valid(story_id):
        raise HTTPException(status_code=400, detail="Invalid Story ID format")

    try:
        result = await story_collection.update_one(
            {"_id": ObjectId(story_id)},
            {"$pull": {"bookmarked_by": user_id}}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Story not found")
        if result.modified_count == 0:
            return {"message": "Story was not in user's library"} # Not an error, just wasn't there
        return {"message": "Story removed from library"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove story from library: {str(e)}")


# --- Get bookmarked stories for a specific user ---
@router.get("/api/users/{user_id}/library", response_model=List[Story])
async def get_bookmarked_stories_by_user(user_id: str):
    # Find all stories where the user_id is in the 'bookmarked_by' array
    cursor = story_collection.find({"bookmarked_by": user_id}).sort("_id", -1)
    bookmarked_stories = []
    async for story in cursor:
        story["id"] = str(story["_id"])
        del story["_id"] # Remove mongo's _id to fit pydantic model
        bookmarked_stories.append(Story(**story))
    return bookmarked_stories

# --- Get user-specific stories (all stories created by user) ---
@router.get("/stories/user/{user_id}", response_model=List[Story])
async def get_user_stories(user_id: str):
    cursor = story_collection.find({"user_id": user_id}).sort("_id", -1)
    stories = []
    async for story in cursor:
        story["id"] = str(story["_id"])
        del story["_id"]
        stories.append(Story(**story))
    return stories

# --- Get user's draft stories ---
@router.get("/drafts/{user_id}", response_model=List[Story])
async def get_drafts(user_id: str):
    cursor = story_collection.find({"user_id": user_id, "status": "draft"}).sort("_id", -1)
    stories = []
    async for story in cursor:
        story["id"] = str(story["_id"])
        del story["_id"]
        stories.append(Story(**story))
    return stories

# --- Search stories ---
@router.get("/search_stories", response_model=List[Story])
async def search_stories(q: str):
    query = {
        "$or": [
            {"title": {"$regex": q, "$options": "i"}},
            {"theme": {"$regex": q, "$options": "i"}}
        ]
    }
    cursor = story_collection.find(query).sort("_id", -1)
    stories = []
    async for story in cursor:
        story["id"] = str(story["_id"])
        del story["_id"]
        stories.append(Story(**story))
    return stories



# --- Get count of stories generated by a specific user ---
@router.get("/api/users/{user_id}/stories/count")
async def get_user_stories_count(user_id: str):
    count = await story_collection.count_documents({"user_id": user_id})
    return {"count": count}