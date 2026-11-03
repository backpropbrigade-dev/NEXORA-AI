import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


class ConversationStore:
    """Small SQLite repository for local, per-conversation chat history."""

    def __init__(self, database_path: Path):
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self):
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL REFERENCES conversations(id)
                        ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    input_type TEXT NOT NULL DEFAULT 'text',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_conversations_updated
                    ON conversations(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_messages_conversation
                    ON messages(conversation_id, created_at);
                """
            )

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    def list_conversations(self, query=""):
        pattern = f"%{query.strip()}%"
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT c.id, c.title, c.created_at, c.updated_at
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                WHERE (? = '' OR c.title LIKE ? OR m.content LIKE ?)
                ORDER BY c.updated_at DESC
                """,
                (query.strip(), pattern, pattern),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_conversation(self, conversation_id, title="New conversation"):
        now = self._now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO conversations (id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (conversation_id, title.strip() or "New conversation", now, now),
            )
        return self.get_conversation(conversation_id)

    def get_conversation(self, conversation_id):
        with self._connect() as connection:
            conversation = connection.execute(
                "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            if conversation is None:
                return None
            messages = connection.execute(
                """
                SELECT id, role, content, input_type, created_at
                FROM messages WHERE conversation_id = ? ORDER BY created_at, id
                """,
                (conversation_id,),
            ).fetchall()
        result = dict(conversation)
        result["messages"] = [dict(message) for message in messages]
        return result

    def add_message(self, conversation_id, role, content, input_type="text"):
        if role not in {"user", "assistant"} or not content.strip():
            raise ValueError("Message role and content are required")
        now = self._now()
        with self._connect() as connection:
            conversation = connection.execute(
                "SELECT title FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            if conversation is None:
                raise ValueError("Conversation does not exist")
            title = conversation["title"]
            if role == "user" and title == "New conversation":
                title = " ".join(content.split())[:60] or "New conversation"
            connection.execute(
                """
                INSERT INTO messages
                    (conversation_id, role, content, input_type, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (conversation_id, role, content.strip(), input_type, now),
            )
            connection.execute(
                """
                UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?
                """,
                (title, now, conversation_id),
            )
        conversation = self.get_conversation(conversation_id)
        conversation["last_message"] = conversation["messages"][-1]
        return conversation

    def rename(self, conversation_id, title):
        clean_title = " ".join(title.split()).strip()
        if not clean_title:
            raise ValueError("Conversation title cannot be empty")
        with self._connect() as connection:
            result = connection.execute(
                """
                UPDATE conversations SET title = ?, updated_at = ?
                WHERE id = ?
                """,
                (clean_title[:120], self._now(), conversation_id),
            )
            if result.rowcount == 0:
                return None
        return self.get_conversation(conversation_id)

    def delete(self, conversation_id):
        with self._connect() as connection:
            result = connection.execute(
                "DELETE FROM conversations WHERE id = ?", (conversation_id,)
            )
        return result.rowcount > 0

    def clear(self):
        with self._connect() as connection:
            connection.execute("DELETE FROM conversations")
