import os
from contextlib import asynccontextmanager

from pymongo import AsyncMongoClient


class MongoDatabase:
    def __init__(self):
        self.uri = os.getenv("MONGODB_URI")
        self.database_name = os.getenv("MONGODB_DATABASE", "nexora")
        self.client = None
        self.database = None

    async def connect(self):
        if not self.uri:
            raise RuntimeError("MONGODB_URI is required")
        self.client = AsyncMongoClient(
            self.uri,
            tz_aware=True,
            connectTimeoutMS=5000,
            serverSelectionTimeoutMS=5000,
            socketTimeoutMS=30000,
            maxPoolSize=10,
            minPoolSize=0,
        )
        try:
            await self.client.admin.command("ping")
        except Exception as error:
            await self.close()
            raise RuntimeError("MongoDB is unavailable") from error
        self.database = self.client[self.database_name]
        await self.database.users.create_index("email_normalized", unique=True)
        await self.database.conversations.create_index([("user_id", 1), ("updated_at", -1)])
        await self.database.messages.create_index([("conversation_id", 1), ("created_at", 1)])

    async def close(self):
        if self.client is not None:
            await self.client.close()
        self.client = None
        self.database = None


mongo = MongoDatabase()


@asynccontextmanager
async def lifespan(app):
    from services.auth import validate_auth_config

    validate_auth_config()
    await mongo.connect()
    try:
        yield
    finally:
        await mongo.close()
