import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from pymongo.errors import PyMongoError

from api import public_server


class FakeUsers:
    def __init__(self):
        self.documents = {}

    async def find_one(self, query, projection=None):
        if "email_normalized" in query:
            return self.documents.get(query["email_normalized"])
        if "_id" in query:
            return next((user for user in self.documents.values() if user["_id"] == query["_id"]), None)
        return None

    async def insert_one(self, document):
        if document["email_normalized"] in self.documents:
            from pymongo.errors import DuplicateKeyError
            raise DuplicateKeyError("duplicate email")
        self.documents[document["email_normalized"]] = document


class FakeRateLimits:
    def __init__(self):
        self.documents = {}

    async def find_one(self, query):
        document = self.documents.get(query["_id"])
        if document is None:
            return None
        # Match MongoDB's legacy default BSON datetime decoding behavior.
        result = dict(document)
        started = result["window_started"]
        if started.tzinfo is not None:
            result["window_started"] = started.replace(tzinfo=None)
        return result

    async def replace_one(self, query, document, upsert=False):
        self.documents[query["_id"]] = dict(document)

    async def update_one(self, query, update):
        self.documents[query["_id"]]["attempts"] += update["$inc"]["attempts"]


class AuthApiTests(unittest.TestCase):
    def setUp(self):
        self.database = SimpleNamespace(users=FakeUsers(), auth_rate_limits=FakeRateLimits())
        self.previous_database = public_server.mongo.database
        public_server.mongo.database = self.database
        self.client = TestClient(public_server.app)
        self.secret_patch = patch("services.auth.JWT_SECRET_KEY", "unit-test-signing-key-with-enough-entropy")
        self.secret_patch.start()

    def tearDown(self):
        self.secret_patch.stop()
        public_server.mongo.database = self.previous_database

    def test_register_duplicate_login_session_and_refresh(self):
        payload = {"email": "Person@Example.com", "password": "correct-horse-battery"}
        registered = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(registered.status_code, 200, registered.text)
        user = self.database.users.documents["person@example.com"]
        self.assertNotEqual(user["password_hash"], payload["password"])

        duplicate = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(duplicate.status_code, 409, duplicate.text)
        self.assertEqual(
            duplicate.json()["detail"],
            "An account with this email already exists. Please sign in.",
        )

        production_login = self.client.post(
            "/api/auth/login",
            json=payload,
            headers={"Origin": "https://nexora-ai-two-smoky.vercel.app"},
        )
        self.assertEqual(production_login.status_code, 200, production_login.text)
        self.assertIn(
            "SameSite=none",
            production_login.headers["set-cookie"],
        )
        self.assertIn("Secure", production_login.headers["set-cookie"])

        # Exercise a prior Mongo rate-limit date decoded as naive UTC.
        valid_login = self.client.post("/api/auth/login", json=payload)
        self.assertEqual(valid_login.status_code, 200, valid_login.text)
        self.assertEqual(self.client.get("/api/auth/session").json()["user"]["email"], "person@example.com")

        refreshed_client = TestClient(public_server.app)
        refreshed_client.cookies.update(self.client.cookies)
        self.assertEqual(refreshed_client.get("/api/auth/session").json(), {"user": valid_login.json()["user"]})

    def test_invalid_login_and_missing_or_invalid_session_are_unauthenticated(self):
        anonymous = TestClient(public_server.app)
        self.assertEqual(anonymous.get("/api/auth/session").json(), {"user": None})
        anonymous.cookies.set("nexora_access_token", "not-a-valid-token")
        self.assertEqual(anonymous.get("/api/auth/session").json(), {"user": None})

        self.client.post("/api/auth/register", json={"email": "person@example.com", "password": "correct-horse-battery"})
        invalid = self.client.post("/api/auth/login", json={"email": "person@example.com", "password": "wrong-password"})
        self.assertEqual(invalid.status_code, 401)

    def test_malformed_password_record_is_not_reported_as_invalid_credentials(self):
        self.database.users.documents["person@example.com"] = {
            "_id": "user-id",
            "email": "person@example.com",
            "email_normalized": "person@example.com",
            "password_hash": None,
        }
        with patch.object(public_server, "logger") as logger:
            response = self.client.post(
                "/api/auth/login",
                json={"email": "person@example.com", "password": "correct-horse-battery"},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Authentication service is temporarily unavailable")
        logger.error.assert_called_once()

    def test_logout_clears_cookie_and_allows_signing_in_again(self):
        payload = {"email": "person@example.com", "password": "correct-horse-battery"}
        self.assertEqual(self.client.post("/api/auth/register", json=payload).status_code, 200)
        self.assertEqual(self.client.get("/api/auth/session").json()["user"]["email"], payload["email"])

        logged_out = self.client.post("/api/auth/logout")
        self.assertEqual(logged_out.status_code, 200)
        self.assertEqual(self.client.get("/api/auth/session").json(), {"user": None})

        logged_in = self.client.post("/api/auth/login", json=payload)
        self.assertEqual(logged_in.status_code, 200, logged_in.text)
        self.assertEqual(self.client.get("/api/auth/session").json()["user"]["email"], payload["email"])

    def test_registration_validation_and_database_failure_are_not_generic_500s(self):
        invalid = self.client.post("/api/auth/register", json={"email": "not-an-email", "password": "short"})
        self.assertEqual(invalid.status_code, 422)

        class BrokenUsers(FakeUsers):
            async def find_one(self, query, projection=None):
                raise PyMongoError("simulated database outage")

        self.database.users = BrokenUsers()
        unavailable = self.client.post("/api/auth/register", json={"email": "person@example.com", "password": "correct-horse-battery"})
        self.assertEqual(unavailable.status_code, 503)
        self.assertNotIn("simulated database outage", unavailable.text)

    def test_production_origin_passes_credentialed_preflight(self):
        cors_middleware = next(
            middleware
            for middleware in public_server.app.user_middleware
            if middleware.cls.__name__ == "CORSMiddleware"
        )
        original_origins = cors_middleware.kwargs["allow_origins"]
        original_stack = public_server.app.middleware_stack
        cors_middleware.kwargs["allow_origins"] = [
            "https://nexora-ai-two-smoky.vercel.app"
        ]
        public_server.app.middleware_stack = None
        try:
            response = self.client.options(
                "/api/auth/login",
                headers={
                    "Origin": "https://nexora-ai-two-smoky.vercel.app",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type",
                },
            )
        finally:
            cors_middleware.kwargs["allow_origins"] = original_origins
            public_server.app.middleware_stack = original_stack

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "https://nexora-ai-two-smoky.vercel.app",
        )
        self.assertEqual(
            response.headers["access-control-allow-credentials"], "true"
        )
        self.assertIn("POST", response.headers["access-control-allow-methods"])
        self.assertIn("PUT", response.headers["access-control-allow-methods"])
        self.assertIn(
            "Content-Type", response.headers["access-control-allow-headers"]
        )

    def test_production_origin_is_preserved_when_environment_has_other_origins(self):
        cors_middleware = next(
            middleware
            for middleware in public_server.app.user_middleware
            if middleware.cls.__name__ == "CORSMiddleware"
        )
        self.assertIn(
            "https://nexora-ai-two-smoky.vercel.app",
            cors_middleware.kwargs["allow_origins"],
        )

if __name__ == "__main__":
    unittest.main()
