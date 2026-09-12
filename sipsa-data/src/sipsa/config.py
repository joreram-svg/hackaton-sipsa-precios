from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    db_path: Path = PROJECT_ROOT / "data" / "sipsa.duckdb"
    db_backend: Literal["duckdb", "postgres"] = "duckdb"
    supabase_db_url: SecretStr | None = None
    admin_token: str = "change-me"
    source_priority: str = "excel_dane,soap_dane,socrata,seed"
    socrata_dataset_id: str = ""
    ciudades: str = "Armenia,Barranquilla,Bogotá,Bucaramanga,Cali,Cartagena de Indias,Cúcuta,Ibagué,Manizales,Medellín,Montería,Neiva,Pasto,Pereira,Popayán,Santa Marta,Sincelejo,Tunja,Valledupar,Villavicencio"
    hist_weeks: int = 104
    api_port: int = 8000
    mcp_port: int = 8001
    tz: str = "America/Bogota"
    telegram_bot_token: str = ""
    telegram_chat_ids: str = ""

    @property
    def source_names(self) -> list[str]:
        return [value.strip() for value in self.source_priority.split(",") if value.strip()]

    @property
    def city_names(self) -> list[str]:
        return [value.strip() for value in self.ciudades.split(",") if value.strip()]

    @property
    def telegram_chat_id_values(self) -> list[int]:
        return [int(value.strip()) for value in self.telegram_chat_ids.split(",") if value.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
