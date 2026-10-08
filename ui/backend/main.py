"""UI API with explicit browser boundaries and process/agent health reporting."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.responses import Response

from .config import OAUTH_CALLBACK_CSP_SOURCE, UI_CONFIG
from .limits import limiter
from .routers import chat, oauth, upload

app = FastAPI(
    title="Research-Agent Custom UI API",
    description="Backend for handling Agent Engine streaming and unified OAuth",
    version="1.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=UI_CONFIG.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Goog-IAP-JWT-Assertion"],
)


@app.middleware("http")
async def secure_headers(request: Request, call_next) -> Response:
    """Keep private responses uncached and constrain browser content execution."""
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        f"default-src 'none'; script-src {OAUTH_CALLBACK_CSP_SOURCE}; "
        "base-uri 'none'; frame-ancestors 'none'"
    )
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


app.include_router(oauth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(upload.router, prefix="/api/upload", tags=["Upload"])


@app.get("/health")
@limiter.exempt
async def health_check() -> JSONResponse:
    """Return unavailable when the configured agent lookup failed."""
    if chat.remote_app is None:
        return JSONResponse({"status": "agent_unavailable"}, status_code=503)
    return JSONResponse({"status": "ok"})
