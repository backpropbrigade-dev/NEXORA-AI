"""Authenticated, text-only API for the NEXORA AI public demo."""

import hashlib
import logging
import os
from pathlib import Path
from datetime import timezone

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from pydantic import BaseModel, EmailStr, Field
from pymongo.errors import DuplicateKeyError, PyMongoError

from services.auth import (
    create_token,
    normalize_email,
    password_hash,
    rate_limit_key,
    validate_password,
    verify_token,
)
from services.mongodb import lifespan, mongo
from services.public_mongodb_store import PublicMongoStore


logger = logging.getLogger("nexora.auth")
ACCOUNT_EXISTS_MESSAGE = "An account with this email already exists. Please sign in."
PRODUCTION_FRONTEND_ORIGIN = "https://nexora-ai-two-smoky.vercel.app"


def auth_subject(email):
    return hashlib.sha256(email.encode("utf-8")).hexdigest()[:12]


def cookie_options(request):
    if request.headers.get("origin", "").rstrip("/") == PRODUCTION_FRONTEND_ORIGIN:
        return {"secure": True, "samesite": "none"}
    return {"secure": cookie_secure, "samesite": cookie_samesite}


configured_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv("PUBLIC_FRONTEND_ORIGINS", "").split(",")
    if origin.strip()
]
for required_origin in (
    "https://nexora-ai-two-smoky.vercel.app",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
):
    if required_origin not in configured_origins:
        configured_origins.append(required_origin)
client = (
    Groq(api_key=os.environ["GROQ_API_KEY"], timeout=20, max_retries=0)
    if os.getenv("GROQ_API_KEY")
    else None
)
cookie_secure = os.getenv("COOKIE_SECURE", "false").lower() == "true"
cookie_samesite = os.getenv("COOKIE_SAMESITE", "lax").lower()
app = FastAPI(title="NEXORA AI Public Demo API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


class AuthRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str = Field(min_length=1, max_length=4000)
    input_type: str = Field(default="text", pattern="^(text|voice)$")
    action_result: str | None = Field(default=None, max_length=1000)
    follow_up_question: str | None = Field(default=None, max_length=4000)


class ConversationRequest(BaseModel):
    title: str = Field(default="New conversation", max_length=120)


class RenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)


def require_store():
    if mongo.database is None:
        raise HTTPException(status_code=503, detail="Database is not ready")
    return PublicMongoStore(mongo.database)


def rate_window_elapsed(now, started_at):
    # Treat legacy BSON datetimes decoded without tz_aware as UTC.
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    return (now - started_at).total_seconds()


def database_unavailable():
    return HTTPException(status_code=503, detail="Authentication service is temporarily unavailable")


async def record_auth_attempt(repository, rate_key, now, limit):
    collection = repository.database.auth_rate_limits
    window = await collection.find_one({"_id": rate_key})
    if window and rate_window_elapsed(now, window["window_started"]) < 900 and window["attempts"] >= limit:
        raise HTTPException(status_code=429, detail="Too many authentication attempts; try again later")
    if not window or rate_window_elapsed(now, window["window_started"]) >= 900:
        await collection.replace_one(
            {"_id": rate_key},
            {"_id": rate_key, "attempts": 1, "window_started": now},
            upsert=True,
        )
    else:
        await collection.update_one({"_id": rate_key}, {"$inc": {"attempts": 1}})


async def current_user(request: Request, repository=Depends(require_store)):
    user_id = verify_token(request)
    user = await repository.database.users.find_one({"_id": user_id}, {"email": 1})
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication is invalid")
    return {"id": user_id, "email": user["email"]}


async def get_conversation_or_404(repository, conversation_id, user_id):
    conversation = await repository.get_conversation(conversation_id, user_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "service": "nexora-public-demo",
        "database": "ready" if mongo.database is not None else "not_ready",
    }


@app.get("/api/ready")
async def ready():
    if mongo.database is None:
        raise HTTPException(status_code=503, detail="Database is not ready")
    try:
        await mongo.client.admin.command("ping")
    except PyMongoError as error:
        raise HTTPException(status_code=503, detail="Database is not ready") from error
    return {"ok": True, "database": "ready"}


@app.post("/api/auth/register")
async def register(request: Request, payload: AuthRequest, response: Response, repository=Depends(require_store)):
    email = normalize_email(payload.email)
    validate_password(payload.password)
    rate_key = rate_limit_key(request, email)
    now = repository._now()
    try:
        await record_auth_attempt(repository, rate_key, now, 5)
        existing = await repository.database.users.find_one({"email_normalized": email}, {"_id": 1})
        if existing:
            raise HTTPException(status_code=409, detail=ACCOUNT_EXISTS_MESSAGE)
        user_id = str(__import__("uuid").uuid4())
        await repository.database.users.insert_one({
            "_id": user_id,
            "email": email,
            "email_normalized": email,
            "password_hash": password_hash.hash(payload.password),
            "created_at": now,
        })
    except DuplicateKeyError as error:
        raise HTTPException(status_code=409, detail=ACCOUNT_EXISTS_MESSAGE) from error
    except PyMongoError as error:
        raise database_unavailable() from error
    response.set_cookie(
        "nexora_access_token",
        create_token(user_id),
        httponly=True,
        **cookie_options(request),
        max_age=1800,
    )
    return {"user": {"id": user_id, "email": email}}


@app.post("/api/auth/login")
async def login(request: Request, payload: AuthRequest, response: Response, repository=Depends(require_store)):
    email = normalize_email(payload.email)
    rate_key = rate_limit_key(request, email)
    now = repository._now()
    try:
        await record_auth_attempt(repository, rate_key, now, 10)
        user = await repository.database.users.find_one({"email_normalized": email})
    except PyMongoError as error:
        logger.exception("Authentication database lookup failed")
        raise database_unavailable() from error
    if user is None:
        logger.info("Authentication failed: user_not_found subject=%s", auth_subject(email))
        raise HTTPException(status_code=401, detail="Invalid email or password")
    try:
        password_valid = password_hash.verify(payload.password, user["password_hash"])
    except (KeyError, TypeError, ValueError):
        logger.error(
            "Authentication failed: malformed_password_record subject=%s",
            auth_subject(email),
        )
        raise database_unavailable()
    if not password_valid:
        logger.info("Authentication failed: password_mismatch subject=%s", auth_subject(email))
        raise HTTPException(status_code=401, detail="Invalid email or password")
    response.set_cookie(
        "nexora_access_token",
        create_token(user["_id"]),
        httponly=True,
        **cookie_options(request),
        max_age=1800,
    )
    return {"user": {"id": user["_id"], "email": user["email"]}}


@app.get("/api/auth/me")
async def me(request: Request, repository=Depends(require_store)):
    """Return the current session without treating a logged-out visitor as an error."""
    try:
        user_id = verify_token(request)
    except HTTPException as error:
        if error.status_code == 401:
            return {"user": None}
        raise
    user = await repository.database.users.find_one({"_id": user_id}, {"email": 1})
    if user is None:
        return {"user": None}
    return {"user": {"id": user_id, "email": user["email"]}}


@app.get("/api/auth/session")
async def session(request: Request):
    """Check for a login cookie without returning 401 for logged-out visitors."""
    try:
        user_id = verify_token(request)
    except HTTPException as error:
        if error.status_code == 401:
            return {"user": None}
        raise
    repository = require_store()
    try:
        user = await repository.database.users.find_one({"_id": user_id}, {"email": 1})
    except PyMongoError as error:
        raise database_unavailable() from error
    if user is None:
        return {"user": None}
    return {"user": {"id": user_id, "email": user["email"]}}


@app.post("/api/auth/logout")
async def logout(request: Request, response: Response):
    response.delete_cookie("nexora_access_token", **cookie_options(request))
    return {"ok": True}


@app.get("/api/status")
async def status():
    return {
        "status": "idle",
        "message": "Public text chat ready.",
        "microphone": "unavailable",
        "groq": "ready" if client is not None else "unavailable",
        "speech_engine": "browser",
        "local_service": "unavailable",
    }


@app.get("/api/conversations")
async def list_conversations(search: str = "", user=Depends(current_user), repository=Depends(require_store)):
    return await repository.list_conversations(user["id"], search)


@app.post("/api/conversations")
async def create_conversation(payload: ConversationRequest, user=Depends(current_user), repository=Depends(require_store)):
    return await repository.create_conversation(str(__import__("bson").ObjectId()), user["id"], payload.title)


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, user=Depends(current_user), repository=Depends(require_store)):
    return await get_conversation_or_404(repository, conversation_id, user["id"])


@app.patch("/api/conversations/{conversation_id}")
async def rename_conversation(conversation_id: str, payload: RenameRequest, user=Depends(current_user), repository=Depends(require_store)):
    result = await repository.rename(conversation_id, user["id"], payload.title)
    if result is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return result


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, user=Depends(current_user), repository=Depends(require_store)):
    if not await repository.delete(conversation_id, user["id"]):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"ok": True}


@app.delete("/api/conversations")
async def clear_conversations(user=Depends(current_user), repository=Depends(require_store)):
    await repository.clear(user["id"])
    return {"ok": True}


@app.post("/api/chat")
async def chat(payload: ChatRequest, user=Depends(current_user), repository=Depends(require_store)):
    action_only = bool(payload.action_result and not payload.follow_up_question)
    if client is None and not action_only:
        raise HTTPException(status_code=503, detail="Public AI service is not configured")
    conversation_id = payload.conversation_id or str(__import__("bson").ObjectId())
    if payload.conversation_id is None:
        await repository.create_conversation(conversation_id, user["id"])
    else:
        await get_conversation_or_404(repository, conversation_id, user["id"])
    await repository.add_message(conversation_id, user["id"], "user", payload.message, payload.input_type)
    if payload.action_result and not payload.follow_up_question:
        await repository.add_message(conversation_id, user["id"], "assistant", payload.action_result)
        return {
            "conversation_id": conversation_id,
            "response": payload.action_result,
            "conversation": await repository.get_conversation(conversation_id, user["id"]),
        }
    conversation = await repository.get_conversation(conversation_id, user["id"])
    messages = [{"role": message["role"], "content": message["content"]} for message in conversation["messages"][-12:]]
    if payload.action_result and payload.follow_up_question:
        messages = messages[:-1] + [
            {"role": "assistant", "content": f"The local computer action completed: {payload.action_result}"},
            {"role": "user", "content": payload.follow_up_question},
        ]
    try:
        completion = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
            messages=messages,
            temperature=0.4,
            max_tokens=500,
        )
        answer = (completion.choices[0].message.content or "").strip()
    except Exception as error:
        raise HTTPException(status_code=502, detail="The public AI service is temporarily unavailable") from error
    if not answer:
        raise HTTPException(status_code=502, detail="The public AI service returned an empty response")
    await repository.add_message(conversation_id, user["id"], "assistant", answer)
    return {
        "conversation_id": conversation_id,
        "response": answer,
        "conversation": await repository.get_conversation(conversation_id, user["id"]),
    }
