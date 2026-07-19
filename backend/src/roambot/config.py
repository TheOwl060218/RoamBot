from enum import StrEnum
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderMode(StrEnum):
    MOCK = "mock"
    LIVE = "live"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ROAMBOT_", extra="forbid")

    data_dir: Path = Path("data")
    database_name: str = "roambot.db"
    master_password_file: Path = Field(
        default=Path("/run/secrets/roambot_master_password"),
        repr=False,
    )
    secure_cookies: bool = False
    session_hours: int = 24
    provider_mode: ProviderMode = ProviderMode.MOCK
    demo_mode: bool = True
    amap_base_url: AnyHttpUrl = AnyHttpUrl("https://restapi.amap.com")
    qweather_api_host: AnyHttpUrl | None = None
    llm_base_url: AnyHttpUrl | None = None
    llm_model: str | None = None
    provider_timeout_seconds: float = Field(default=5.0, gt=0)
    max_geocode_calls: int = Field(default=3, gt=0)
    max_poi_search_calls: int = Field(default=6, gt=0)
    max_weather_calls: int = Field(default=5, gt=0)
    max_distance_calls: int = Field(default=5, gt=0)
    max_llm_calls: int = Field(default=1, gt=0)

    @field_validator("amap_base_url", "qweather_api_host", "llm_base_url", mode="before")
    @classmethod
    def reject_explicit_port(cls, value: object) -> object:
        if isinstance(value, str):
            try:
                if urlsplit(value).port is not None:
                    raise ValueError("provider URL must not include a port")
            except ValueError as exc:
                raise ValueError("provider URL is invalid") from exc
        return value

    @field_validator("amap_base_url", "qweather_api_host", "llm_base_url")
    @classmethod
    def validate_provider_root(cls, value: AnyHttpUrl | None) -> AnyHttpUrl | None:
        if value is None:
            return None
        if (
            value.scheme != "https"
            or value.username is not None
            or value.password is not None
            or value.path not in (None, "", "/")
            or value.query is not None
            or value.fragment is not None
        ):
            raise ValueError("provider URL must be an HTTPS origin")
        return value

    @field_validator("qweather_api_host")
    @classmethod
    def validate_qweather_host(cls, value: AnyHttpUrl | None) -> AnyHttpUrl | None:
        if value is not None and (
            value.host is None or not value.host.endswith(".qweatherapi.com")
        ):
            raise ValueError("QWeather API host must be account-specific")
        return value

    @model_validator(mode="after")
    def validate_live_mode(self) -> "Settings":
        if self.provider_mode is ProviderMode.MOCK:
            return self
        if self.demo_mode:
            raise ValueError("live provider mode cannot use demo data")
        if self.qweather_api_host is None:
            raise ValueError("live provider mode requires a QWeather API host")
        if self.llm_base_url is None:
            raise ValueError("live provider mode requires an LLM base URL")
        if self.llm_model is None or not self.llm_model.strip():
            raise ValueError("live provider mode requires an LLM model")
        self.llm_model = self.llm_model.strip()
        return self

    @property
    def database_path(self) -> Path:
        return self.data_dir / self.database_name
