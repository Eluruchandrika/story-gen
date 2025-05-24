from fastapi import APIRouter
from pydantic import BaseModel
from services.story_service import generate_ai_story, text_to_speech

router = APIRouter()

class StoryRequest(BaseModel):
    genre:str
    theme:str
    length:str


@router.post("/generate_story")
def generate_story(request:StoryRequest):
    story= generate_ai_story(request.genre, request.theme, request.length )
    
    audio_path = text_to_speech(story)

    return {"story": story , "audio_url": f"http://127.0.0.1:8000/{audio_path}"}
