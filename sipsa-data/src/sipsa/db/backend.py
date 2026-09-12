from contextlib import contextmanager
from typing import Any, Iterator

from sipsa.config import Settings


class DuckDBSession:
    """Adaptador mínimo que conserva la API nativa usada por el proyecto."""

    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None):
        return self.connection.execute(sql, params or [])

    def register(self, name: str, value: Any) -> None:
        self.connection.register(name, value)


class PostgresSession:
    """Adapta la SQL compartida con marcadores DuckDB a psycopg2."""

    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None):
        cursor = self.connection.cursor()
        cursor.execute(sql.replace("?", "%s"), params or [])
        return cursor


@contextmanager
def open_database(
    settings: Settings,
    *,
    read_only: bool = False,
) -> Iterator[DuckDBSession | PostgresSession]:
    """Abre el backend configurado y cierra siempre la conexión subyacente."""
    if settings.db_backend == "duckdb":
        import duckdb

        with duckdb.connect(str(settings.db_path), read_only=read_only) as connection:
            yield DuckDBSession(connection)
        return

    if settings.supabase_db_url is None:
        raise ValueError("SUPABASE_DB_URL es obligatoria cuando DB_BACKEND=postgres")

    import psycopg2

    connection = psycopg2.connect(
        settings.supabase_db_url.get_secret_value(),
        connect_timeout=15,
        application_name="sipsa_data",
    )
    try:
        if read_only:
            connection.set_session(readonly=True)
        yield PostgresSession(connection)
        if not read_only:
            connection.commit()
    except Exception:
        if not read_only:
            connection.rollback()
        raise
    finally:
        connection.close()
