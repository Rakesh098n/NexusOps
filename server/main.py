"""Authenticated same-origin API for the NexusOps web app."""

import asyncio
import json
import os
import queue
import secrets
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from starlette.middleware.sessions import SessionMiddleware

from utils.analysis_service import run_business_analysis
from utils.auth import (
    ROLE_PERMISSIONS,
    ROLES,
    authenticate_user,
    create_user,
    demo_mode_enabled,
    get_active_user,
    initialize_user_store,
    list_users,
    update_user,
)
from utils.llm import is_provider_key_configured
from utils.local_analytics import (
    build_inventory_scenario,
    get_dashboard_data,
    get_data_table,
    get_inventory_snapshot,
)
from utils.tools import is_power_automate_configured


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
SESSION_SECRET = os.getenv("SESSION_SECRET") or secrets.token_urlsafe(32)
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").casefold() in {
    "1",
    "true",
    "yes",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_user_store()
    yield


app = FastAPI(title="NexusOps API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET or "local-development-only-change-this-secret",
    same_site="lax",
    https_only=COOKIE_SECURE,
    session_cookie="nexusops_session",
)


class AnalysisRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1500)
    trigger_flow: bool = False

    @field_validator("question")
    @classmethod
    def question_must_have_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Enter a business question.")
        return cleaned


class InventoryScenarioRequest(BaseModel):
    lead_time_days: int = Field(default=14, ge=1, le=365)
    safety_stock_days: int = Field(default=7, ge=0, le=365)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=1024)


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=12, max_length=1024)
    role: str

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, value: str) -> str:
        if value not in ROLES:
            raise ValueError("Choose a valid workspace role.")
        return value


class UserUpdateRequest(BaseModel):
    role: str | None = None
    active: bool | None = None
    password: str | None = Field(default=None, min_length=12, max_length=1024)

    @field_validator("role")
    @classmethod
    def optional_role_must_be_valid(cls, value: str | None) -> str | None:
        if value is not None and value not in ROLES:
            raise ValueError("Choose a valid workspace role.")
        return value


def require_user(request: Request) -> dict[str, Any]:
    session_user = request.session.get("user")
    if not session_user or not session_user.get("username"):
        raise HTTPException(status_code=401, detail="Sign in to access this workspace.")
    user = get_active_user(session_user["username"])
    if not user:
        request.session.clear()
        raise HTTPException(status_code=401, detail="This account is inactive. Contact an administrator.")
    request.session["user"] = user
    return user


def require_roles(*roles: str):
    def role_dependency(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Your workspace role does not allow this action.")
        return user

    return role_dependency


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config")
async def get_config() -> dict[str, Any]:
    provider_ready = is_provider_key_configured()
    webhook_configured = is_power_automate_configured()
    return {
        "provider": "Groq",
        "provider_ready": provider_ready,
        "automation_ready": provider_ready and webhook_configured,
        "auth_required": True,
        "roles": list(ROLES),
        "demo_mode": demo_mode_enabled(),
    }


@app.get("/api/session")
async def get_session(request: Request) -> dict[str, Any]:
    session_user = request.session.get("user")
    user = (
        get_active_user(session_user["username"])
        if session_user and session_user.get("username")
        else None
    )
    if not user:
        request.session.clear()
    return {
        "auth_required": True,
        "user": (
            {
                **user,
                "permissions": list(ROLE_PERMISSIONS[user["role"]]),
            }
            if user
            else None
        ),
    }


@app.post("/auth/login")
async def login(payload: LoginRequest, request: Request) -> dict[str, Any]:
    user = authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    request.session.clear()
    request.session["user"] = user
    return {"user": {**user, "permissions": list(ROLE_PERMISSIONS[user["role"]])}}


@app.post("/auth/logout")
async def logout(request: Request) -> dict[str, bool]:
    request.session.clear()
    return {"logged_out": True}


@app.get("/api/dashboard")
async def dashboard(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    data = get_dashboard_data()
    return {
        "totals": data["totals"],
        "monthly": data["monthly"].to_dict(orient="records"),
        "inventory": (
            data["inventory"].to_dict(orient="records")
            if user["role"] in {"admin", "manager"}
            else []
        ),
    }


@app.get("/api/data/{dataset}")
async def data_table(
    dataset: str,
    _: dict[str, Any] = Depends(require_roles("admin")),
) -> dict[str, Any]:
    dataset_name = dataset.replace("-", " ").title()
    try:
        data = get_data_table(dataset_name)
    except ValueError as error:
        raise HTTPException(status_code=404, detail="Unknown dataset.") from error
    return {"dataset": dataset_name, "rows": data.to_dict(orient="records")}


@app.post("/api/inventory/scenario")
async def inventory_scenario(
    payload: InventoryScenarioRequest,
    _: dict[str, Any] = Depends(require_roles("admin", "manager")),
) -> dict[str, Any]:
    return build_inventory_scenario(
        get_inventory_snapshot(include_demand=True),
        payload.lead_time_days,
        payload.safety_stock_days,
    )


@app.post("/api/analyze")
async def analyze(
    payload: AnalysisRequest,
    user: dict[str, Any] = Depends(require_roles("admin", "manager")),
) -> StreamingResponse:
    events: queue.Queue[dict[str, Any] | None] = queue.Queue()
    started = time.perf_counter()

    def on_progress(stage: str, update: dict[str, Any]) -> None:
        events.put(
            {
                "type": "progress",
                "stage": stage,
                "error": update.get("error"),
            }
        )

    def run_analysis() -> None:
        try:
            result = run_business_analysis(
                question=payload.question,
                use_provider=is_provider_key_configured(),
                trigger_flow=(
                    payload.trigger_flow
                    and is_provider_key_configured()
                    and is_power_automate_configured()
                    and user["role"] in {"admin", "manager"}
                ),
                progress_callback=on_progress,
            )
            result["question"] = payload.question
            result["elapsed_seconds"] = round(time.perf_counter() - started, 2)
            events.put({"type": "result", "data": result})
        except Exception as error:
            events.put({"type": "error", "message": str(error)})
        finally:
            events.put(None)

    threading.Thread(target=run_analysis, daemon=True).start()

    async def event_stream():
        while True:
            try:
                event = await asyncio.to_thread(events.get, True, 20)
            except queue.Empty:
                yield ": keep-alive\n\n"
                continue
            if event is None:
                break
            yield f"data: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/users")
async def users(
    _: dict[str, Any] = Depends(require_roles("admin")),
) -> dict[str, Any]:
    return {"users": list_users(), "roles": list(ROLES)}


@app.post("/api/users", status_code=201)
async def add_user(
    payload: UserCreateRequest,
    _: dict[str, Any] = Depends(require_roles("admin")),
) -> dict[str, Any]:
    try:
        user = create_user(payload.username, payload.password, payload.role)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"user": user}


@app.patch("/api/users/{username}")
async def change_user(
    username: str,
    payload: UserUpdateRequest,
    actor: dict[str, Any] = Depends(require_roles("admin")),
) -> dict[str, Any]:
    try:
        user = update_user(
            username,
            role=payload.role,
            active=payload.active,
            password=payload.password,
            actor_username=actor["username"],
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"user": user}


if FRONTEND_DIST.is_dir():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/{path:path}", include_in_schema=False)
async def frontend(path: str):
    if FRONTEND_DIST.is_dir():
        requested = (FRONTEND_DIST / path).resolve()
        try:
            requested.relative_to(FRONTEND_DIST.resolve())
        except ValueError:
            raise HTTPException(status_code=404, detail="Not found.") from None
        if path and requested.is_file():
            return FileResponse(requested)
        index = FRONTEND_DIST / "index.html"
        if index.is_file():
            return FileResponse(index)
    return HTMLResponse(
        "<h1>NexusOps web client is not built.</h1>"
        "<p>Run <code>npm run dev</code> in the frontend directory, or build the frontend.</p>",
        status_code=503,
    )
