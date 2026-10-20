from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Provider = Literal["AWS", "GCP", "Azure"]


class PriceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Provider
    region: str = Field(min_length=1)
    instance_type: str = Field(min_length=1)
    vcpu: int = Field(gt=0)
    memory_gb: float = Field(gt=0)
    hourly_price: float = Field(ge=0)
    currency: Literal["USD"] = "USD"
    pricing_type: str = Field(min_length=1)
    source: str = Field(min_length=1)
    observed_at: datetime
    freshness: Literal["fresh", "stale"]
    availability_evidence: str
    interruption_risk: Literal["low", "medium", "high", "unknown"]


class CostRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_hourly_cost: float = Field(ge=0)
    target_hourly_cost: float = Field(ge=0)
    duration_hours: float = Field(gt=0)
    transfer_cost: float = Field(default=0, ge=0)
    migration_overhead: float = Field(default=0, ge=0)
    other_costs: float = Field(default=0, ge=0)
    minimum_savings_percent: float = Field(default=0, ge=0, le=100)
    current_provider: Provider
    target_provider: Provider


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_provider: Provider
    duration_hours: float = Field(gt=0)
    current_hourly_cost: float = Field(ge=0)
    required_vcpu: int = Field(gt=0)
    required_memory_gb: float = Field(gt=0)
    transfer_cost: float = Field(default=0, ge=0)
    migration_overhead: float = Field(default=0, ge=0)
    minimum_savings_percent: float = Field(default=0, ge=0, le=100)
    region: str = Field(default="us-east-1", min_length=1)


class MigrationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_provider: Provider
    target_provider: Provider
    simulation: bool = True
    workload_name: str = Field(default="unspecified", min_length=1, max_length=120)


class MigrationAdvance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    health_check_passed: bool = True
    confirm_live: bool = False
