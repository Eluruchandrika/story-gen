import os
import uuid
import requests
from dotenv import load_dotenv
from gtts import gTTS

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Use Gemini or any available model from OpenRouter
OPENROUTER_MODEL = "openai/gpt-3.5-turbo"  # You can use others like anthropic/claude-3-opus

def generate_ai_story(genre: str, theme: str, length: str):
    prompt = f"Write a {length} {genre} story about {theme}. Make it engaging and creative."

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "http://localhost",  # You can set your site here
        "Content-Type": "application/json"
    }

    data = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": "You are a creative storyteller."},
            {"role": "user", "content": prompt}
        ]
    }

    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
    
    if response.status_code != 200:
        raise Exception(f"OpenRouter API error: {response.status_code} - {response.text}")
    
    story = response.json()["choices"][0]["message"]["content"]
    return story


def text_to_speech(story_text):
    tts = gTTS(text=story_text, lang="en")
    filename = f"story_{uuid.uuid4().hex}.mp3"
    file_path = f"static/{filename}"
    tts.save(file_path)
    return file_path
