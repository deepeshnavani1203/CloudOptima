import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
load_dotenv(Path(__file__).resolve().parents[1] / ".env.profile")


def _boolean(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value.")


def _optional(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "demo")
    demo_mode: bool = _boolean("DEMO_MODE", True)
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    mongodb_uri: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    database_name: str = os.getenv("DATABASE_NAME", "cloudoptima")
    profile_username: str | None = field(default=_optional("APP_PROFILE_USERNAME"), repr=False)
    profile_display_name: str | None = field(default=_optional("APP_PROFILE_DISPLAY_NAME"), repr=False)
    profile_email: str | None = field(default=_optional("APP_PROFILE_EMAIL"), repr=False)
    profile_role: str | None = field(default=_optional("APP_PROFILE_ROLE"), repr=False)
    groq_api_key: str | None = field(default=_optional("GROQ_API_KEY"), repr=False)
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    gcp_project_id: str | None = field(default=_optional("GCP_PROJECT_ID"), repr=False)
    gcp_billing_api_key: str | None = field(default=_optional("GCP_BILLING_API_KEY"), repr=False)
    google_application_credentials: str | None = field(default=_optional("GOOGLE_APPLICATION_CREDENTIALS"), repr=False)
    azure_subscription_id: str | None = field(default=_optional("AZURE_SUBSCRIPTION_ID"), repr=False)
    azure_pricing_enabled: bool = _boolean("AZURE_PRICING_ENABLED", False)
    dns_adapter: str = os.getenv("DNS_ADAPTER", "mock")
    dns_api_token: str | None = field(default=_optional("DNS_API_TOKEN"), repr=False)

    def __post_init__(self):
        origin = urlsplit(self.frontend_origin)
        if origin.scheme not in {"http", "https"} or not origin.netloc or origin.path not in {"", "/"}:
            raise ValueError("FRONTEND_ORIGIN must be an HTTP(S) origin without a path.")
        if not self.mongodb_uri.startswith(("mongodb://", "mongodb+srv://")):
            raise ValueError("MONGODB_URI must use mongodb:// or mongodb+srv://.")
        if not self.database_name.strip():
            raise ValueError("DATABASE_NAME cannot be empty.")
        profile_values = (
            self.profile_username,
            self.profile_display_name,
            self.profile_email,
            self.profile_role,
        )
        if any(profile_values) and not all(profile_values):
            raise ValueError("All APP_PROFILE_* fields must be set together.")
        if self.dns_adapter != "mock":
            raise ValueError("Only DNS_ADAPTER=mock is supported; live DNS changes are disabled.")
        if not self.app_env.strip():
            raise ValueError("APP_ENV cannot be empty.")


settings = Settings()
