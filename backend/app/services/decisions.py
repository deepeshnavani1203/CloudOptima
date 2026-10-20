from datetime import datetime, timezone

from app.schemas import DecisionRequest, PriceRecord
from app.services.costs import calculate_costs
from app.schemas import CostRequest

_REGION_GROUPS = {
    "us-east-1": "us-east",
    "us-east1": "us-east",
    "eastus": "us-east",
}


def recommend(request: DecisionRequest, prices: list[PriceRecord]) -> dict:
    current_total = request.current_hourly_cost * request.duration_hours
    candidates = []
    rejected = []
    desired_group = _REGION_GROUPS.get(request.region.lower())

    for price in prices:
        if price.provider == request.current_provider:
            continue
        reasons = []
        region_group = _REGION_GROUPS.get(price.region.lower())
        if not desired_group or region_group != desired_group:
            reasons.append(f"Region {price.region} is not normalized to requested region {request.region}.")
        if price.vcpu < request.required_vcpu or price.memory_gb < request.required_memory_gb:
            reasons.append("Instance does not meet the requested vCPU and memory requirements.")
        if price.freshness != "fresh":
            reasons.append("Required pricing data is stale.")
        if price.currency != "USD":
            reasons.append("Price currency is not normalized to USD.")
        if price.hourly_price < 0:
            reasons.append("Hourly price is invalid.")
        if reasons:
            rejected.append({"provider": price.provider, "eligible": False, "reason": " ".join(reasons)})
            continue

        cost = calculate_costs(CostRequest(
            current_hourly_cost=request.current_hourly_cost,
            target_hourly_cost=price.hourly_price,
            duration_hours=request.duration_hours,
            transfer_cost=request.transfer_cost,
            migration_overhead=request.migration_overhead,
            current_provider=request.current_provider,
            target_provider=price.provider,
            minimum_savings_percent=request.minimum_savings_percent,
        ))
        item = {
            "provider": price.provider,
            "region": price.region,
            "instance_type": price.instance_type,
            "hourly_price": price.hourly_price,
            "total_cost": cost["target_total_cost"],
            "net_savings": cost["net_savings"],
            "savings_percent": cost["savings_percent"],
            "eligible": cost["net_savings"] > 0 and cost["meets_savings_threshold"],
            "reason": (
                "Capacity, regional availability, and interruption risk require provider-side validation."
                if cost["net_savings"] > 0 and cost["meets_savings_threshold"]
                else "Estimated total savings do not meet the configured minimum threshold."
            ),
            "pricing_source": price.source,
            "availability_evidence": price.availability_evidence,
            "interruption_risk": price.interruption_risk,
        }
        candidates.append(item)

    candidates.sort(key=lambda candidate: candidate["total_cost"])
    eligible = [candidate for candidate in candidates if candidate["eligible"]]
    selected = eligible[0] if eligible else None
    return {
        "recommended_provider": selected["provider"] if selected else request.current_provider,
        "reason": (
            f"{selected['provider']} has the lowest eligible estimated total cost and meets the savings threshold."
            if selected
            else (
                "No pricing records are available; no alternative can be verified. Stay on the current provider until pricing is configured."
                if not prices
                else "No alternative meets the eligibility and minimum savings requirements; stay on the current provider."
            )
        ),
        "estimated_net_savings": selected["net_savings"] if selected else (0 if prices else None),
        "savings_percent": selected["savings_percent"] if selected else (0 if prices else None),
        "current_total_cost": round(current_total, 6),
        "candidates": candidates,
        "rejected_candidates": rejected,
        "evaluated_at": datetime.now(timezone.utc),
        "mode": "demo",
        "limitations": [
            "Live provider pricing adapters are not configured.",
            "Capacity, regional availability, and interruption risk cannot be verified without provider data.",
        ],
    }
