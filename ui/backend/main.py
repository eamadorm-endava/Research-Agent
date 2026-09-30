from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import oauth, chat, upload

app = FastAPI(
    title="Research-Agent Custom UI API",
    description="Backend for handling Agent Engine streaming and unified OAuth",
    version="1.0.0",
)

# Configure CORS (restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(oauth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(upload.router, prefix="/api/upload", tags=["Upload"])


@app.get("/health")
async def health_check():
    return {"status": "ok"}
