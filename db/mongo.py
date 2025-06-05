from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise Exception("MONGO_URI is not set in environment variables")

print(f"Connecting to MongoDB with URI: {MONGO_URI}")

client = AsyncIOMotorClient(MONGO_URI)
db = client["story-gen"]
story_collection = db["stories"]
