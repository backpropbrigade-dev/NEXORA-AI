from datetime import datetime, timezone
import re

from bson import ObjectId


class PublicMongoStore:
    def __init__(self, database):
        self.database = database

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)

    @staticmethod
    def _conversation(document):
        if document is None:
            return None
        return {
            "id": str(document["_id"]),
            "title": document["title"],
            "created_at": document["created_at"],
            "updated_at": document["updated_at"],
        }

    @staticmethod
    def _message(document):
        return {
            "id": str(document["_id"]),
            "role": document["role"],
            "content": document["content"],
            "input_type": document["input_type"],
            "created_at": document["created_at"],
        }

    async def list_conversations(self, user_id, query=""):
        filter_query = {"user_id": user_id}
        clean_query = query.strip()
        if clean_query:
            safe_query = re.escape(clean_query)
            filter_query["$or"] = [
                {"title": {"$regex": safe_query, "$options": "i"}},
                {"search_text": {"$regex": safe_query, "$options": "i"}},
            ]
        cursor = self.database.conversations.find(
            filter_query,
            {"title": 1, "created_at": 1, "updated_at": 1},
        ).sort("updated_at", -1)
        return [self._conversation(document) async for document in cursor]

    async def create_conversation(self, conversation_id, user_id, title="New conversation"):
        now = self._now()
        document = {
            "_id": ObjectId(conversation_id),
            "user_id": user_id,
            "title": title.strip() or "New conversation",
            "created_at": now,
            "updated_at": now,
            "search_text": title.strip(),
        }
        await self.database.conversations.insert_one(document)
        return await self.get_conversation(conversation_id, user_id)

    async def get_conversation(self, conversation_id, user_id):
        try:
            object_id = ObjectId(conversation_id)
        except Exception:
            return None
        conversation = await self.database.conversations.find_one({"_id": object_id, "user_id": user_id})
        if conversation is None:
            return None
        messages = self.database.messages.find(
            {"conversation_id": object_id, "user_id": user_id}
        ).sort([("created_at", 1), ("_id", 1)])
        result = self._conversation(conversation)
        result["messages"] = [self._message(message) async for message in messages]
        return result

    async def add_message(self, conversation_id, user_id, role, content, input_type="text"):
        clean_content = content.strip()
        if role not in {"user", "assistant"} or not clean_content:
            raise ValueError("Message role and content are required")
        try:
            object_id = ObjectId(conversation_id)
        except Exception:
            return None
        conversation = await self.database.conversations.find_one(
            {"_id": object_id, "user_id": user_id}
        )
        if conversation is None:
            return None
        title = conversation["title"]
        if role == "user" and title == "New conversation":
            title = " ".join(clean_content.split())[:60] or "New conversation"
        now = self._now()
        message = {
            "_id": ObjectId(),
            "conversation_id": object_id,
            "user_id": user_id,
            "role": role,
            "content": clean_content,
            "input_type": input_type,
            "created_at": now,
        }
        await self.database.messages.insert_one(message)
        await self.database.conversations.update_one(
            {"_id": object_id, "user_id": user_id},
            {"$set": {"title": title, "updated_at": now}, "$setOnInsert": {"search_text": clean_content}},
        )
        await self.database.conversations.update_one(
            {"_id": object_id, "user_id": user_id},
            {"$set": {"search_text": f"{title} {clean_content}"}},
        )
        result = await self.get_conversation(conversation_id, user_id)
        result["last_message"] = self._message(message)
        return result

    async def rename(self, conversation_id, user_id, title):
        clean_title = " ".join(title.split()).strip()
        if not clean_title:
            raise ValueError("Conversation title cannot be empty")
        try:
            object_id = ObjectId(conversation_id)
        except Exception:
            return None
        result = await self.database.conversations.update_one(
            {"_id": object_id, "user_id": user_id},
            {"$set": {"title": clean_title[:120], "updated_at": self._now()}},
        )
        if result.modified_count == 0 and result.matched_count == 0:
            return None
        return await self.get_conversation(conversation_id, user_id)

    async def delete(self, conversation_id, user_id):
        try:
            object_id = ObjectId(conversation_id)
        except Exception:
            return False
        result = await self.database.conversations.delete_one({"_id": object_id, "user_id": user_id})
        if result.deleted_count:
            await self.database.messages.delete_many({"conversation_id": object_id, "user_id": user_id})
        return result.deleted_count > 0

    async def clear(self, user_id):
        conversations = self.database.conversations.find({"user_id": user_id}, {"_id": 1})
        ids = [document["_id"] async for document in conversations]
        if ids:
            await self.database.messages.delete_many({"conversation_id": {"$in": ids}, "user_id": user_id})
            await self.database.conversations.delete_many({"_id": {"$in": ids}, "user_id": user_id})
