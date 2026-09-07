"""FastAPI application entrypoint.

Wires together: CORS (the review UI is a separate origin), security
headers, consistent error-response shaping, and the route modules. No
processing pipeline is invoked here -- see api/routes/resumes.py for what
this stage of the API actually does.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from resume_engine.api.dependencies import provide_settings
from resume_engine.api.routes import resumes, system
from resume_engine.api.schemas import ErrorResponse

app = FastAPI(title="Resume Parsing & Skill Extraction Engine API", version="0.0.1")

_settings = provide_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(_settings.cors_allowed_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    # HTTPS readiness: only advertise HSTS when the deployment is actually
    # terminating TLS -- sending it over plain HTTP is meaningless/unsafe.
    if _settings.force_https:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Sensible response shaping: don't leak raw Pydantic internals to the client.
    error = ErrorResponse(code="validation_error", message="Request payload failed validation.")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=error.model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Never leak stack traces / internal paths in the response body.
    error = ErrorResponse(code="internal_error", message="An unexpected error occurred.")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error.model_dump(),
    )


app.include_router(system.router)
app.include_router(resumes.router)
