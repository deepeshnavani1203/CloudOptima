from fastapi import APIRouter

from app.adapters.dns import MockDnsAdapter

router = APIRouter(prefix="/api/dns", tags=["DNS simulation"])
dns_adapter = MockDnsAdapter()


@router.post("/simulate")
async def simulate_dns(endpoint: str, healthy: bool = True):
    return await dns_adapter.switch(endpoint, healthy)
