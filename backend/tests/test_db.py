import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from app.db import DocumentStore


def test_mongodb_connection_failure_is_reported_and_uses_explicit_memory_mode(monkeypatch):
    class UnavailableMongo:
        admin = None

        def __init__(self):
            self.admin = self

        async def command(self, _name):
            raise OSError("database unavailable")

        async def close(self):
            return None

    client = UnavailableMongo()
    monkeypatch.setattr("app.db.AsyncMongoClient", lambda *_args, **_kwargs: client)
    store = DocumentStore()

    asyncio.run(store.connect())

    assert store.status == "unavailable"
    assert store.mode == "memory"
    assert store.client is None
    assert store.connection_error == "connection_failed"


def test_mongodb_tls_failure_has_safe_status_code(monkeypatch):
    class UnavailableMongo:
        def __init__(self, *_args, **_kwargs):
            self.admin = self

        async def command(self, _name):
            raise OSError("TLS handshake failed for mongodb://secret-host")

        async def close(self):
            return None

    monkeypatch.setattr("app.db.AsyncMongoClient", UnavailableMongo)
    store = DocumentStore()

    asyncio.run(store.connect())

    assert store.connection_error == "tls_handshake_failed"


def test_connected_store_seeds_profile_in_users_collection(monkeypatch):
    class FakeCollection:
        def __init__(self):
            self.indexes = []
            self.updates = []

        async def create_index(self, index, unique=False):
            self.indexes.append((index, unique))

        async def update_one(self, query, update, upsert=False):
            self.updates.append((query, update, upsert))

    class FakeDatabase:
        def __init__(self):
            self.collections = {}

        def __getitem__(self, name):
            return self.collections.setdefault(name, FakeCollection())

    class FakeMongo:
        def __init__(self, *_args, **_kwargs):
            self.admin = self
            self.database = FakeDatabase()

        async def command(self, _name):
            return {"ok": 1}

        def __getitem__(self, _name):
            return self.database

        async def close(self):
            return None

    client = FakeMongo()
    monkeypatch.setattr("app.db.AsyncMongoClient", lambda *_args, **_kwargs: client)
    monkeypatch.setattr("app.db.settings", SimpleNamespace(
        mongodb_uri="mongodb://localhost",
        database_name="cloudoptima",
        profile_username="demo-owner",
        profile_display_name="Demo Owner",
        profile_email="owner@example.invalid",
        profile_role="Developer",
    ))
    store = DocumentStore()

    asyncio.run(store.connect())

    assert store.mode == "mongodb"
    assert store.status == "connected"
    assert store.connection_error is None
    users = client.database["users"]
    assert ([("username", 1)], False) in users.indexes
    assert ("username", True) in users.indexes
    query, update, upsert = users.updates[0]
    assert query == {"username": "demo-owner"}
    assert update["$set"] == {
        "display_name": "Demo Owner",
        "email": "owner@example.invalid",
        "role": "Developer",
        "updated_at": update["$set"]["updated_at"],
    }
    assert isinstance(update["$set"]["updated_at"], datetime)
    assert update["$set"]["updated_at"].tzinfo == timezone.utc
    assert update["$setOnInsert"]["username"] == "demo-owner"
    assert isinstance(update["$setOnInsert"]["created_at"], datetime)
    assert upsert is True
