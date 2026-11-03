import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, Request
from pwdlib import PasswordHash


password_hash = PasswordHash.recommended()
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
TOKEN_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))


def validate_auth_config():
    if not JWT_SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY is required")


def normalize_email(email):
    return email.strip().lower()


def validate_password(password):
    if len(password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")


def create_token(user_id):
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": user_id, "iat": now, "exp": now + timedelta(minutes=TOKEN_MINUTES)},
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def get_token(request: Request):
    cookie_token = request.cookies.get("nexora_access_token")
    if cookie_token:
        return cookie_token
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def verify_token(request: Request):
    token = get_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication is required")
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
    except jwt.PyJWTError as error:
        raise HTTPException(status_code=401, detail="Authentication is invalid or expired") from error
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication is invalid")
    return user_id


def rate_limit_key(request, email):
    return hashlib.sha256(f"{request.client.host}:{email}".encode()).hexdigest()


def new_rate_limit_document(key):
    return {
        "_id": key,
        "attempts": 1,
        "window_started": datetime.now(timezone.utc),
        "nonce": secrets.token_hex(8),
    }
