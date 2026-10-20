import asyncio

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
