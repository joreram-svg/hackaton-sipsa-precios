from pathlib import Path

from pydantic import SecretStr

from sipsa.config import Settings
from sipsa.db.backend import PostgresSession
from sipsa.db.repo import Repository


class RecordingCursor:
    description = [("producto_id",)]

    def __init__(self):
        self.executed = None

    def execute(self, sql, params):
        self.executed = (sql, params)
        return self

    def fetchall(self):
        return [("papa_pastusa",)]


class RecordingConnection:
    def __init__(self):
        self.cursor_instance = RecordingCursor()
        self.read_only = None
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def set_session(self, readonly):
        self.read_only = readonly

    def close(self):
        self.closed = True


def test_postgres_traduce_parametros_de_la_sql_compartida():
    """Detecta consultas del repositorio enviadas a psycopg2 con marcadores DuckDB."""
    connection = RecordingConnection()
    session = PostgresSession(connection)

    cursor = session.execute(
        "SELECT producto_id FROM dim_producto WHERE categoria=? AND nombre<>?",
        ["tuberculos", ""],
    )

    assert connection.cursor_instance.executed == (
        "SELECT producto_id FROM dim_producto WHERE categoria=%s AND nombre<>%s",
        ["tuberculos", ""],
    )
    assert cursor.fetchall() == [("papa_pastusa",)]


def test_backend_por_defecto_sigue_siendo_duckdb_y_url_es_secreta():
    """Detecta una migración que cambie el motor predeterminado o exponga la credencial."""
    settings = Settings(
        _env_file=None,
        db_path=Path("data/test.duckdb"),
        supabase_db_url="postgresql://usuario:secreto@host/base",
    )

    assert settings.db_backend == "duckdb"
    assert isinstance(settings.supabase_db_url, SecretStr)
    assert "secreto" not in repr(settings)


def test_repository_selecciona_postgres_y_devuelve_filas(monkeypatch):
    """Detecta que DB_BACKEND=postgres sea ignorado por la capa de consultas."""
    connection = RecordingConnection()
    monkeypatch.setattr("psycopg2.connect", lambda *args, **kwargs: connection)
    settings = Settings(
        _env_file=None,
        db_backend="postgres",
        supabase_db_url="postgresql://usuario:secreto@host/base",
    )

    rows = Repository(settings).list_products("tuberculos")

    assert rows == [{"producto_id": "papa_pastusa"}]
    assert connection.read_only is True
    assert connection.closed is True
