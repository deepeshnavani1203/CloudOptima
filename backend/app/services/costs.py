from app.schemas import CostRequest


def calculate_costs(request: CostRequest) -> dict:
    current_cost = request.current_hourly_cost * request.duration_hours
    target_compute_cost = request.target_hourly_cost * request.duration_hours
    target_total_cost = (
        target_compute_cost
        + request.transfer_cost
        + request.migration_overhead
        + request.other_costs
    )
    net_savings = current_cost - target_total_cost
    savings_percent = net_savings / current_cost * 100 if current_cost > 0 else 0.0
    hourly_delta = request.current_hourly_cost - request.target_hourly_cost
    one_time_costs = request.transfer_cost + request.migration_overhead + request.other_costs
    break_even_hours = one_time_costs / hourly_delta if hourly_delta > 0 else None
    return {
        "current_provider": request.current_provider,
        "target_provider": request.target_provider,
        "current_cost": round(current_cost, 6),
        "target_compute_cost": round(target_compute_cost, 6),
        "transfer_cost": request.transfer_cost,
        "migration_overhead": request.migration_overhead,
        "other_costs": request.other_costs,
        "target_total_cost": round(target_total_cost, 6),
        "net_savings": round(net_savings, 6),
        "savings_percent": round(savings_percent, 4),
        "break_even_hours": round(break_even_hours, 4) if break_even_hours is not None else None,
        "minimum_savings_percent": request.minimum_savings_percent,
        "meets_savings_threshold": savings_percent >= request.minimum_savings_percent,
        "assumptions": [
            "This is an estimate based on the prices and assumptions supplied; it is not a bill or guaranteed saving.",
            "Hourly costs are multiplied by workload duration.",
            "Transfer, migration, and other costs are one-time estimates added once.",
            "Taxes, negotiated discounts, storage, licensing, support, and non-compute services are excluded unless user estimates are included in other costs.",
        ],
        "missing_cost_categories": [
            "Taxes and negotiated discounts",
            "Storage, licensing, support, and other non-compute services",
        ],
    }
