from urllib.parse import urlparse

from fastapi import HTTPException


class MockDnsAdapter:
    async def switch(self, endpoint: str, healthy: bool) -> dict:
        parsed = urlparse(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HTTPException(status_code=422, detail="Target endpoint must be an absolute HTTP(S) URL.")
        if not healthy:
            raise HTTPException(status_code=409, detail="Target health check failed; DNS was not changed.")
        return {
            "status": "simulated",
            "endpoint": endpoint,
            "message": "Mock DNS update only. DNS propagation is not instantaneous and requires verification.",
        }
