import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from api import public_server
from services.auth import create_token
from services.public_mongodb_store import PublicMongoStore


class FakeUsers:
    async def find_one(self, query, projection=None):
        return {"_id": query["_id"], "email": "person@example.com"}


class FakeRepository:
    def __init__(self):
        self.database = SimpleNamespace(users=FakeUsers())
        self.messages = []

    async def add_message(self, conversation_id, user_id, role, content, input_type="text"):
        self.messages.append({"role": role, "content": content, "input_type": input_type})

    async def get_conversation(self, conversation_id, user_id):
        return {"id": conversation_id, "messages": list(self.messages)}


class CloudChatTests(unittest.TestCase):
    def test_general_question_uses_groq_and_mongodb_repository(self):
        repository = FakeRepository()
        groq_response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Machine learning lets computers learn patterns from data."))])
        groq_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: groq_response)))
        user_id = "user-test-id"
        public_server.app.dependency_overrides[public_server.require_store] = lambda: repository
        try:
            with patch.object(public_server, "client", groq_client):
                response = TestClient(public_server.app).post(
                    "/api/chat",
                    headers={"Authorization": f"Bearer {create_token(user_id)}"},
                    json={"conversation_id": "507f1f77bcf86cd799439011", "message": "What is machine learning?", "input_type": "voice"},
                )
        finally:
            public_server.app.dependency_overrides.clear()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("Machine learning", response.json()["response"])
        self.assertEqual(repository.messages[0]["input_type"], "voice")
        self.assertEqual(repository.messages[1]["role"], "assistant")

    def test_action_confirmation_can_be_saved_without_cloud_reexecuting_it(self):
        repository = FakeRepository()
        user_id = "user-test-id"
        public_server.app.dependency_overrides[public_server.require_store] = lambda: repository
        try:
            with patch.object(public_server, "client", None):
                response = TestClient(public_server.app).post(
                    "/api/chat",
                    headers={"Authorization": f"Bearer {create_token(user_id)}"},
                    json={"conversation_id": "507f1f77bcf86cd799439011", "message": "Open YouTube", "action_result": "Opening YouTube now."},
                )
        finally:
            public_server.app.dependency_overrides.clear()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["response"], "Opening YouTube now.")


class MongoOwnershipTests(unittest.TestCase):
    def test_conversation_query_is_scoped_to_user(self):
        class Conversations:
            query = None

            async def find_one(self, query):
                self.query = query
                return None

        conversations = Conversations()
        repository = PublicMongoStore(SimpleNamespace(conversations=conversations))
        import asyncio
        asyncio.run(repository.get_conversation("507f1f77bcf86cd799439011", "user-123"))
        self.assertEqual(conversations.query["user_id"], "user-123")


if __name__ == "__main__":
    unittest.main()
