from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Literal
from bson import ObjectId
from services.story_service import generate_ai_story, text_to_speech
from db.mongo import story_collection

router = APIRouter()

class Story(BaseModel):
    id: str
    genre: str
    theme: str
    length: str
    title: str
    content: str
    audio_url: str
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
async def generate_story(request: StoryRequest):
    try:
        content = generate_ai_story(request.genre, request.theme, request.length)
        audio_path = text_to_speech(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Story generation failed: {e}")

    audio_url = f"https://ai-story-backend-1h6m.onrender.com/{audio_path}"
    first_line = content.strip().split("\n")[0]
    title = first_line if len(first_line) < 100 else first_line[:97] + "..."

    story = {
        "genre": request.genre,
        "theme": request.theme,
        "length": request.length,
        "title": title,
        "content": content,
        "audio_url": audio_url,
        "source": "ai",
        "status": "published"
    }

    result = await story_collection.insert_one(story)
    story["id"] = str(result.inserted_id)
    return Story(**story)

# --- Manual story ---
@router.post("/create_manual_story", response_model=Story)
async def create_manual_story(request: ManualStoryRequest):
    try:
        audio_path = text_to_speech(request.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio generation failed: {e}")

    audio_url = f"https://ai-story-backend-1h6m.onrender.com/{audio_path}"

    story = {
        "genre": request.genre,
        "theme": request.theme,
        "length": request.length,
        "title": request.title,
        "content": request.content,
        "audio_url": audio_url,
        "source": request.source,
        "status": request.status
    }

    result = await story_collection.insert_one(story)
    story["id"] = str(result.inserted_id)
    return Story(**story)

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

# --- Update story by ID ---
@router.put("/story/{story_id}", response_model=Story)
async def update_story(story_id: str, update: StoryUpdate):
    result = await story_collection.find_one_and_update(
        {"_id": ObjectId(story_id)},
        {"$set": {"title": update.title, "content": update.content, "status": update.status}},
        return_document=True
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
