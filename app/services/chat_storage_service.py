import sqlite3
import json
import logging

from schemas.requests import ChatMessage
from schemas.responses import ChatCompletedReponse
from pydantic import ValidationError
from config import get_settings
from app_logging import log
from contextlib import contextmanager

settings = get_settings()

def create_db() -> None:
    with transaction() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL UNIQUE
            );
  
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chats (
            conv_id INTEGER NOT NULL,
            chat_id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL UNIQUE,
            content TEXT,
            CONSTRAINT conversation_id
                FOREIGN KEY (conv_id)
                REFERENCES conversation(id)
            );
        """)

def get_unique_conv_id() -> int:
    with transaction() as conn:
        cursor = conn.execute("""
            SELECT MAX(id) FROM conversation;
        """)
        max_id = cursor.fetchone()[0]
        if max_id is None:
            return 1
        else:
            return max_id + 1

def create_conv(conv_id : int) -> None:
    with transaction() as conn:
        conn.execute("""
        INSERT INTO conversation (id) VALUES (?)
        """,(conv_id,))
        log(f"Successfully created a conversation with id {conv_id}", level=logging.INFO)

def create_chat(conv_id : int, input : ChatMessage) -> None:
    # Store the message, including image content, as JSON.
    with transaction() as conn:
        conn.execute("""
            INSERT INTO chats (conv_id, content) VALUES (?, ?)
            """, (conv_id, input.model_dump_json())
            )
        log(f"Successfully created a chat for conv_id {conv_id} with system prompt.", level=logging.INFO)

def list_conversations() -> list[dict]:
    with transaction() as conn:
        rows = conn.execute("""
            SELECT conversation.id, (
                SELECT content FROM chats
                WHERE conv_id = conversation.id
                    AND json_extract(content, '$.role') = 'user'
                ORDER BY chat_id LIMIT 1
            )
            FROM conversation
            ORDER BY (SELECT MAX(chat_id) FROM chats WHERE conv_id = conversation.id) DESC,
                conversation.id DESC
        """).fetchall()

    conversations = []
    
    for conv_id, first_message in rows:
        content = json.loads(first_message).get("content") if first_message else None
        if isinstance(content, list):
            content = " ".join(part.get("text", "") for part in content if part.get("type") == "text")
        title = " ".join((content or ("Image chat" if first_message else "New chat")).split())[:80]
        conversations.append({"conv_id": conv_id, "title": title or "Image chat"})
    return conversations


def get_conv(conv_id : int) -> list[ChatCompletedReponse | ChatMessage]:
    with transaction() as conn:
        if conn.execute("SELECT 1 FROM conversation WHERE id = ?", (conv_id,)).fetchone() is None:
            raise LookupError(f"Conversation {conv_id} not found")
        cursor = conn.execute("""
        SELECT content
        FROM chats
        WHERE conv_id = (?)
        ORDER BY chat_id
        
        """,(conv_id,))
        data = cursor.fetchall()
    out : list[ChatCompletedReponse | ChatMessage] = []
    # Read both older completion objects and current plain message records.
    for jsn in data:
        try:
            record = json.loads(jsn[0])
            schema = ChatCompletedReponse if "choices" in record else ChatMessage
            out.append(schema.model_validate(record))
        except (ValidationError, json.JSONDecodeError):
            log(f"Invalid stored message in conversation {conv_id}", level=logging.ERROR)
            raise

    log(f"Successfully retrieved chats for conv_id {conv_id} with {len(data)} messages.", level=logging.INFO)
    return out
        
def open_db():
    conn = sqlite3.connect(
        settings.DATABASE_PATH,
        timeout=10)

    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA journal_mode = WAL")

    return conn

@contextmanager
def transaction():
    conn = open_db()
    try:
        with conn:
            yield conn
    finally:
        conn.close()




