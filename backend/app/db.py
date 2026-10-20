import logging
from collections import defaultdict

from pymongo import AsyncMongoClient, ASCENDING, DESCENDING

from app.config import settings

logger = logging.getLogger(__name__)


class DocumentStore:
    def __init__(self):
        self.client = None
        self.database = None
        self.mode = "memory"
        self.status = "unavailable"
        self._memory = defaultdict(dict)

    async def connect(self):
        try:
            self.client = AsyncMongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=1200)
            await self.client.admin.command("ping")
            self.database = self.client[settings.database_name]
            await self._create_indexes()
            self.mode = "mongodb"
            self.status = "connected"
        except Exception as error:
            if self.client:
                await self.client.close()
            self.client = None
            self.database = None
            self.mode = "memory"
            self.status = "unavailable"
            logger.warning("MongoDB unavailable; using explicit in-memory demo storage (%s)", type(error).__name__)

    async def _create_indexes(self):
        indexes = {
            "pricing_snapshots": [("observed_at", DESCENDING), ("provider", ASCENDING)],
            "workload_configs": [("workload_name", ASCENDING)],
            "cost_analyses": [("created_at", DESCENDING)],
            "migrations": [("migration_id", ASCENDING), ("created_at", DESCENDING)],
            "audit_logs": [("created_at", DESCENDING), ("resource_id", ASCENDING)],
        }
        for collection, fields in indexes.items():
            for field, direction in fields:
                await self.database[collection].create_index([(field, direction)])
        await self.database["migrations"].create_index("migration_id", unique=True)

    async def insert(self, collection: str, key: str, document: dict):
        if self.mode == "mongodb":
            await self.database[collection].insert_one(dict(document))
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

    async def list(self, collection: str, limit: int = 100):
        if self.mode == "mongodb":
            cursor = self.database[collection].find({}, {"_id": 0}).sort("created_at", DESCENDING).limit(limit)
            return await cursor.to_list(length=limit)
        return list(self._memory[collection].values())[-limit:][::-1]

    async def close(self):
        if self.client:
            await self.client.close()


store = DocumentStore()
