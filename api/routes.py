from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Literal
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
    source: Literal["manual"] = "manual"  # Default value

# AI-generated story route
@router.post("/generate_story", response_model=Story)
async def generate_story(request: StoryRequest):
    content = generate_ai_story(request.genre, request.theme, request.length)
    audio_path = text_to_speech(content)
    audio_url = f"http://127.0.0.1:8000/{audio_path}"
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

# Manual story route
@router.post("/create_manual_story", response_model=Story)
async def create_manual_story(request: ManualStoryRequest):
    audio_path = text_to_speech(request.content)
    audio_url = f"http://127.0.0.1:8000/{audio_path}"

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

# Fetch all stories
@router.get("/stories", response_model=List[Story])
async def get_stories():
    stories_cursor = story_collection.find()
    stories = []
    async for story in stories_cursor:
        story["id"] = str(story["_id"])
        del story["_id"]
        stories.append(Story(**story))
    return stories
