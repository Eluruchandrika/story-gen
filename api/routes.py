from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from services.story_service import generate_ai_story, text_to_speech
from db.mongo import story_collection
from bson import ObjectId
import uuid

router = APIRouter()

class Story(BaseModel):
    id: str
    genre: str
    theme: str
    length: str
    title: str
    content: str
    audio_url: str

class StoryRequest(BaseModel):
    genre: str
    theme: str
    length: str

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
        "audio_url": audio_url
    }

    result = await story_collection.insert_one(story)
    story["id"] = str(result.inserted_id)

    return story

@router.get("/stories", response_model=List[Story])
async def get_stories():
    stories_cursor = story_collection.find()
    stories = []
    async for story in stories_cursor:
        story["id"] = str(story["_id"])
        stories.append(Story(**story))
    return stories
