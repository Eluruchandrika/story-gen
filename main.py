from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router
import os

app = FastAPI(
    title="AI-Powered Story Generator API",
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/openapi.json"
)

# Ensure static directory exists
os.makedirs("static", exist_ok=True)

# Mount static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

origins = [
    "http://localhost:3000",  
    "http://127.0.0.1:3000", 
    "https://story-media-five.vercel.app",
    "https://ai-story-backend-1h6m.onrender.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  
    allow_credentials=True, 
    allow_methods=["*"],   
    allow_headers=["*"],  
)

# API routes
app.include_router(router, tags=["Story"])

# Root route
@app.get("/")
def read_root():
    return {"message": "Welcome to the AI Powered Story Generator API"}

# Health check route
@app.get("/health")
def health_check():
    return {"status": "ok"}

# Optional run
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)