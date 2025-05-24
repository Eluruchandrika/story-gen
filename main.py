from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from api.routes import router

app = FastAPI(title="AI-Powered Story Generator API")

app.include_router(router)

app.mount("/static",StaticFiles(directory="static"),name="static")

@app.get("/")
def read_root():
    return {"message":"welcome to the AI Powered Story Generator API"}

if __name__ =="__main__":
    import uvicorn
    uvicorn.run(app, host='0.0.0.0',port=8000)
