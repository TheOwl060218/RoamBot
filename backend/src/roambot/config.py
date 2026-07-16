from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ROAMBOT_", extra="ignore")

    data_dir: Path = Path("data")
    database_name: str = "roambot.db"
    secure_cookies: bool = False
    session_hours: int = 24

    @property
    def database_path(self) -> Path:
        return self.data_dir / self.database_name
