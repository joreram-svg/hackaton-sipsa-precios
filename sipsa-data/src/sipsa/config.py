from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    db_path: Path = PROJECT_ROOT / "data" / "sipsa.duckdb"
    admin_token: str = "change-me"
    source_priority: str = "excel_dane,soap_dane,socrata,seed"
    socrata_dataset_id: str = ""
    ciudades: str = "Bogotá,Medellín,Cali"
    hist_weeks: int = 104
    api_port: int = 8000
    mcp_port: int = 8001
    tz: str = "America/Bogota"
    telegram_bot_token: str = ""
    telegram_state_path: Path = PROJECT_ROOT / "data" / "ui_state.sqlite"
    telegram_data_mode: Literal["demo", "api"] = "demo"
    telegram_api_base_url: str = "http://127.0.0.1:8000"

    @property
    def source_names(self) -> list[str]:
        return [value.strip() for value in self.source_priority.split(",") if value.strip()]

    @property
    def city_names(self) -> list[str]:
        return [value.strip() for value in self.ciudades.split(",") if value.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

