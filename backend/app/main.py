"""
Local web API and page for the face-recognition capture tool.

Run from the project folder:
    python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

Then open http://127.0.0.1:8000 in your browser.

This version has NO login. Keep it on 127.0.0.1 until authentication is added.
"""

from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from backend.app.capture_service import (
    CaptureServiceError,
    check_database,
    fetch_captures,
    run_capture,
)

ROLL_NUMBER_PATTERN = r"^[A-Za-z0-9_-]{1,32}$"
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Face Recognition Attendance - capture API", version="0.1.0")


def error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


@app.exception_handler(CaptureServiceError)
async def handle_service_error(request, exc: CaptureServiceError):
    return JSONResponse(status_code=exc.status_code, content=error_body(exc.code, exc.message))


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=error_body(
            "invalid_request",
            "The request is not valid. A roll number may only contain letters, digits, "
            "'-' and '_' (up to 32 characters).",
        ),
    )


class CaptureRequest(BaseModel):
    roll_number: str = Field(pattern=ROLL_NUMBER_PATTERN)


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/health/ready")
def health_ready():
    check_database()
    return {"database": "ok"}


@app.post("/api/capture")
def capture(body: CaptureRequest):
    return run_capture(body.roll_number)


@app.get("/api/captures")
def captures(
    roll_number: str | None = Query(default=None, pattern=ROLL_NUMBER_PATTERN),
    limit: int = Query(default=20, ge=1, le=200),
):
    return {"captures": fetch_captures(roll_number, limit)}
