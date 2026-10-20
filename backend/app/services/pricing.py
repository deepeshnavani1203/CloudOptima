from datetime import datetime, timedelta, timezone

from app.schemas import PriceRecord

FRESHNESS_LIMIT = timedelta(hours=24)


def normalize_price(record: dict) -> PriceRecord:
    normalized = dict(record)
    normalized.setdefault("currency", "USD")
    return PriceRecord.model_validate(normalized)


def is_fresh(observed_at: datetime, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    now = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now
    timestamp = observed_at.replace(tzinfo=timezone.utc) if observed_at.tzinfo is None else observed_at
    return now - timestamp <= FRESHNESS_LIMIT and timestamp <= now
