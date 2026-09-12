"""Persistencia local de las preferencias mínimas de la interfaz."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class UserProfile(StrEnum):
    """Perfiles que el usuario puede declarar libremente."""

    CONSUMER = "consumer"
    SMALL_BUSINESS = "small_business"


@dataclass(frozen=True, slots=True)
class UserPreferences:
    chat_id: int
    profile: UserProfile | None = None
    city: str = "Bogotá"
    last_menu: str = "onboarding"


class PreferenceStore:
    """Almacén SQLite pequeño, sin sesiones ni control de acceso."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS telegram_preferences (
                    chat_id INTEGER PRIMARY KEY,
                    profile TEXT,
                    city TEXT NOT NULL DEFAULT 'Bogotá',
                    last_menu TEXT NOT NULL DEFAULT 'onboarding'
                )
                """
            )

    def get(self, chat_id: int) -> UserPreferences:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO telegram_preferences (chat_id) VALUES (?)",
                (chat_id,),
            )
            row = connection.execute(
                "SELECT chat_id, profile, city, last_menu "
                "FROM telegram_preferences WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()

        if row is None:
            raise RuntimeError("No fue posible recuperar las preferencias")
        profile = UserProfile(row["profile"]) if row["profile"] else None
        return UserPreferences(
            chat_id=row["chat_id"],
            profile=profile,
            city=row["city"],
            last_menu=row["last_menu"],
        )

    def set_profile(self, chat_id: int, profile: UserProfile) -> None:
        self.get(chat_id)
        with self._connect() as connection:
            connection.execute(
                "UPDATE telegram_preferences SET profile = ? WHERE chat_id = ?",
                (profile.value, chat_id),
            )

    def set_city(self, chat_id: int, city: str) -> None:
        self.get(chat_id)
        with self._connect() as connection:
            connection.execute(
                "UPDATE telegram_preferences SET city = ? WHERE chat_id = ?",
                (city, chat_id),
            )

    def set_last_menu(self, chat_id: int, last_menu: str) -> None:
        self.get(chat_id)
        with self._connect() as connection:
            connection.execute(
                "UPDATE telegram_preferences SET last_menu = ? WHERE chat_id = ?",
                (last_menu, chat_id),
            )
