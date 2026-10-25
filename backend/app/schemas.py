from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Provider = Literal["AWS", "GCP", "Azure"]


class PriceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Provider
    region: str = Field(min_length=1)
    instance_type: str = Field(min_length=1)
    vcpu: int | None = Field(default=None, gt=0)
    memory_gb: float | None = Field(default=None, gt=0)
    hourly_price: float | None = Field(default=None, ge=0)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    pricing_type: str = Field(min_length=1)
    source: str = Field(min_length=1)
    observed_at: datetime
    freshness: Literal["fresh", "stale"]
    availability_evidence: str
    interruption_risk: Literal["low", "medium", "high", "unknown"]
    sku_id: str | None = None
    arm_sku_name: str | None = None
    meter_id: str | None = None
    service_id: str | None = None
    product_id: str | None = None
    meter_name: str | None = None
    pricing_model_status: Literal["verified", "unclassified", "unsupported"] = "verified"
    pricing_evidence: str = ""
    native_price: float | None = Field(default=None, ge=0)
    native_unit: str | None = None
    native_unit_description: str | None = None
    effective_at: datetime | None = None
    fetched_at: datetime | None = None
    source_url: str | None = None
    snapshot_id: str | None = None
    specifications_complete: bool | None = None

    @model_validator(mode="after")
    def validate_specifications(self):
        self.specifications_complete = (
            self.vcpu is not None and self.memory_gb is not None
            if self.specifications_complete is None
            else self.specifications_complete and self.vcpu is not None and self.memory_gb is not None
        )
        return self


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
    pricing_snapshot_id: str | None = Field(default=None, min_length=1, max_length=128)


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
    pricing_type: Literal["OnDemand", "Spot", "Any"] = "Any"
    workload_tolerates_interruptions: bool | None = None


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
