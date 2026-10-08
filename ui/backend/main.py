"""FastAPI entrypoint with identity checks, explicit CORS and honest readiness."""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from .agent_client import get_remote_agent
from .auth import get_current_user
from .config import UI_CONFIG
from .routers import chat, oauth, upload

app = FastAPI(title="OSIRIS API", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=UI_CONFIG.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization", "X-Goog-IAP-JWT-Assertion"],
)


@app.middleware("http")
async def secure_headers(request, call_next):
    """Prevent caching of private responses and constrain browser content."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; frame-ancestors 'none'"
    )
    response.headers["Cache-Control"] = "no-store"
    return response


app.include_router(oauth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(upload.router, prefix="/api/upload", tags=["Upload"])


@app.get("/health")
def health_check():
    """A probe for process liveness, without external service calls."""
    return {"status": "alive"}


@app.get("/api/ready")
async def ready(user_id: str = Depends(get_current_user)):
    """Report unavailable Agent Engines instead of a misleading healthy status."""
    get_remote_agent.cache_clear()
    remote_agent = await run_in_threadpool(get_remote_agent)
    return {"status": "ready", "agent": remote_agent.api_resource.name}


@app.get("/api/auth/status")
def auth_status(user_id: str = Depends(get_current_user)):
    """Show provider connectivity without disclosing any access or refresh tokens."""
    return {
        provider: chat.token_store.get_token_data(user_id, provider) is not None
        for provider in oauth.PROVIDER_CONFIGS
    }
