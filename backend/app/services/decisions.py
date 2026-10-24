from datetime import datetime, timezone

from app.schemas import DecisionRequest, PriceRecord
from app.services.costs import calculate_costs
from app.schemas import CostRequest

_REGION_GROUPS = {
    "us-east-1": "us-east",
    "us-east1": "us-east",
    "eastus": "us-east",
    "eastus2": "us-east",
    "us-east4": "us-east",
}


def recommend(request: DecisionRequest, prices: list[PriceRecord]) -> dict:
    current_total = request.current_hourly_cost * request.duration_hours
    candidates = []
    rejected = []
    desired_group = _REGION_GROUPS.get(request.region.lower())
    available_models = {
        price.pricing_type for price in prices
        if price.provider != request.current_provider and price.pricing_type in {"OnDemand", "Spot"}
    }

    for price in prices:
        if price.provider == request.current_provider:
            continue
        reasons = []
        region_group = _REGION_GROUPS.get(price.region.lower())
        same_region = price.region.lower() == request.region.lower()
        same_region_group = desired_group is not None and region_group == desired_group
        if not same_region and not same_region_group:
            reasons.append(f"Region {price.region} is not normalized to requested region {request.region}.")
        if not price.specifications_complete or price.vcpu is None or price.memory_gb is None:
            reasons.append("Verified vCPU and memory specifications are unavailable.")
        elif price.vcpu < request.required_vcpu or price.memory_gb < request.required_memory_gb:
            reasons.append("Instance does not meet the requested vCPU and memory requirements.")
        if price.freshness != "fresh":
            reasons.append("Required pricing data is stale.")
        if price.currency != "USD":
            reasons.append("Price currency is not normalized to USD.")
        if price.hourly_price is None or price.hourly_price < 0:
            reasons.append("A supported hourly price is unavailable.")
        if price.pricing_model_status != "verified":
            reasons.append("Pricing model is not verified by the provider catalog.")
        if request.pricing_type != "Any" and price.pricing_type != request.pricing_type:
            reasons.append(f"Pricing model {price.pricing_type} does not match requested {request.pricing_type}.")
        if request.pricing_type == "Any" and len(available_models) > 1:
            reasons.append("Specify one pricing model; on-demand and Spot prices cannot be compared together.")
        if price.pricing_type == "Unclassified":
            reasons.append("The provider did not identify an eligible pricing model.")
        if price.pricing_type == "Spot" and request.workload_tolerates_interruptions is False:
            reasons.append("Workload is not marked as tolerant of Spot interruptions.")
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
            "currency": price.currency,
            "pricing_type": price.pricing_type,
            "sku_id": price.sku_id,
            "pricing_snapshot_id": price.snapshot_id,
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
        "estimated_net_savings": selected["net_savings"] if selected else None,
        "savings_percent": selected["savings_percent"] if selected else None,
        "current_total_cost": round(current_total, 6),
        "candidates": candidates,
        "rejected_candidates": rejected,
        "evaluated_at": datetime.now(timezone.utc),
        "mode": "demo",
        "limitations": [
            "Catalog retail prices are estimates and do not represent negotiated rates or actual bills.",
            "Capacity, regional availability, and interruption risk cannot be verified without provider data.",
        ],
    }
