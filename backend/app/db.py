import logging
from collections import defaultdict
from datetime import datetime, timezone

from pymongo import AsyncMongoClient, ASCENDING, DESCENDING

from app.config import settings

logger = logging.getLogger(__name__)


class DocumentStore:
    def __init__(self):
        self.client = None
        self.database = None
        self.mode = "memory"
        self.status = "unavailable"
        self.connection_error = "not_connected"
        self._memory = defaultdict(dict)

    async def connect(self):
        try:
            self.client = AsyncMongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=10000)
            await self.client.admin.command("ping")
            self.database = self.client[settings.database_name]
            await self._create_indexes()
            await self._seed_profile()
            self.mode = "mongodb"
            self.status = "connected"
            self.connection_error = None
        except Exception as error:
            if self.client:
                await self.client.close()
            self.client = None
            self.database = None
            self.mode = "memory"
            self.status = "unavailable"
            self.connection_error = self._safe_connection_error(error)
            logger.warning(
                "MongoDB unavailable; using explicit in-memory demo storage (%s)",
                self.connection_error,
            )

    @staticmethod
    def _safe_connection_error(error: Exception) -> str:
        message = str(error).lower()
        if "tls" in message or "ssl" in message:
            return "tls_handshake_failed"
        if "authentication failed" in message or "auth failed" in message:
            return "authentication_failed"
        if "name resolution" in message or "getaddrinfo" in message:
            return "dns_resolution_failed"
        if "timed out" in message or "timeout" in message:
            return "connection_timeout"
        return "connection_failed"

    async def _create_indexes(self):
        indexes = {
            "pricing_snapshots": [("observed_at", DESCENDING), ("provider", ASCENDING)],
            "workload_configs": [("workload_name", ASCENDING)],
            "cost_analyses": [("created_at", DESCENDING)],
            "decision_analyses": [("created_at", DESCENDING)],
            "migrations": [("migration_id", ASCENDING), ("created_at", DESCENDING)],
            "audit_logs": [("created_at", DESCENDING), ("resource_id", ASCENDING)],
            "users": [("username", ASCENDING)],
        }
        for collection, fields in indexes.items():
            for field, direction in fields:
                await self.database[collection].create_index([(field, direction)])
        await self.database["migrations"].create_index("migration_id", unique=True)
        await self.database["users"].create_index("username", unique=True)

    async def _seed_profile(self):
        if not settings.profile_username:
            return
        now = datetime.now(timezone.utc)
        await self.database["users"].update_one(
            {"username": settings.profile_username},
            {
                "$set": {
                    "display_name": settings.profile_display_name,
                    "email": settings.profile_email,
                    "role": settings.profile_role,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "username": settings.profile_username,
                    "created_at": now,
                },
            },
            upsert=True,
        )

    async def insert(self, collection: str, key: str, document: dict):
        if self.mode == "mongodb":
            payload = dict(document)
            if collection == "pricing_snapshots":
                payload["_id"] = key
                await self.database[collection].replace_one({"_id": key}, payload, upsert=True)
            else:
                await self.database[collection].insert_one(payload)
        else:
            self._memory[collection][key] = document

    async def replace(self, collection: str, key: str, document: dict):
        if self.mode == "mongodb":
            await self.database[collection].replace_one({"migration_id": key}, dict(document), upsert=True)
        else:
            self._memory[collection][key] = document

    async def get(self, collection: str, key: str):
        if self.mode == "mongodb":
            return await self.database[collection].find_one({"migration_id": key}, {"_id": 0})
        return self._memory[collection].get(key)

    async def get_by_id(self, collection: str, key: str):
        if self.mode == "mongodb":
            return await self.database[collection].find_one({"_id": key}, {"_id": 0})
        return self._memory[collection].get(key)

    async def list(self, collection: str, limit: int = 100):
        if self.mode == "mongodb":
            cursor = self.database[collection].find({}, {"_id": 0}).sort("created_at", DESCENDING).limit(limit)
            return await cursor.to_list(length=limit)
        return list(self._memory[collection].values())[-limit:][::-1]

    async def close(self):
        if self.client:
            await self.client.close()


store = DocumentStore()
