from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise Exception("MONGO_URI is not set in environment variables")

client = AsyncIOMotorClient(MONGO_URI)
db = client["story-gen"]

# Main collection: all stories, including bookmarked info inside each story document
story_collection = db["stories"]

# You can remove saved_stories_collection if unused
