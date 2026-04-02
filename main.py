import os
from dotenv import load_dotenv
load_dotenv()

import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

# We removed the old ai_engine imports!
from routes.api import router

# Load the API keys from your .env file
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Whisper will load itself when called, and Groq is in the cloud.
    logger.info("🟢 ALL SYSTEMS READY. HYBRID API IS LIVE!")
    yield
    logger.info("🛑 Shutting down.")

app = FastAPI(title="Clinical SOAP AI API", version="3.0", lifespan=lifespan)

# Mount the static CSS and JS files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tell the app to use all the endpoints we wrote in api.py
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)