"""Base de datos compartida SQLite (responsable: David López).

ÚNICO archivo que define el esquema. Si un módulo necesita una columna nueva,
se la pide a David para mantener un solo contrato de datos.

Uso desde los módulos:
    from core.db import transaccion, consultar, consultar_uno

    with transaccion() as con:          # escritura atómica (BEGIN IMMEDIATE)
        con.execute("INSERT ...", (...))

    filas = consultar("SELECT ... WHERE x = ?", (valor,))   # -> list[dict]
    fila = consultar_uno("SELECT ...", (...))               # -> dict | None
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from core import config

_db_path_override: str | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS espacios (
    id TEXT PRIMARY KEY,                       -- código del espacio (ej. A-101, CUB-03)
    nombre TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('aula', 'cubiculo')),
    capacidad INTEGER NOT NULL CHECK (capacidad > 0),
    ubicacion TEXT DEFAULT '',
    estado TEXT NOT NULL DEFAULT 'habilitado' CHECK (estado IN ('habilitado', 'inhabilitado')),
    motivo_inhabilitacion TEXT DEFAULT '',
    origen_dato TEXT NOT NULL DEFAULT 'manual', -- 'oficial' | 'manual'
    creado_en TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reservas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    espacio_id TEXT NOT NULL REFERENCES espacios(id) ON DELETE RESTRICT,
    solicitante TEXT NOT NULL,
    fecha TEXT NOT NULL,                       -- YYYY-MM-DD
    hora_inicio TEXT NOT NULL,                 -- HH:MM
    hora_fin TEXT NOT NULL,                    -- HH:MM
    asistentes INTEGER NOT NULL CHECK (asistentes > 0),
    motivo TEXT DEFAULT '',
    estado TEXT NOT NULL DEFAULT 'activa' CHECK (estado IN ('activa', 'cancelada')),
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_reservas_espacio_fecha ON reservas(espacio_id, fecha, estado);

CREATE TABLE IF NOT EXISTS equipos (
    id TEXT PRIMARY KEY,                       -- código / serial / inventario
    nombre TEXT NOT NULL,
    tipo TEXT NOT NULL,                        -- portátil, proyector, tablet...
    descripcion TEXT DEFAULT '',
    estado_operativo TEXT NOT NULL DEFAULT 'operativo'
        CHECK (estado_operativo IN ('operativo', 'mantenimiento', 'danado', 'baja')),
    origen_dato TEXT NOT NULL DEFAULT 'manual',
    creado_en TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prestamos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipo_id TEXT NOT NULL REFERENCES equipos(id) ON DELETE RESTRICT,
    solicitante TEXT NOT NULL,
    fecha_prestamo TEXT NOT NULL,              -- ISO datetime
    fecha_devolucion_prevista TEXT NOT NULL,   -- YYYY-MM-DD
    fecha_devolucion TEXT,                     -- ISO datetime, NULL mientras esté activo
    estado TEXT NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'devuelto')),
    observaciones TEXT DEFAULT '',
    estado_equipo_devolucion TEXT
);
-- Defensa en profundidad: la BD impide dos préstamos activos del mismo equipo.
CREATE UNIQUE INDEX IF NOT EXISTS ux_prestamo_activo_por_equipo
    ON prestamos(equipo_id) WHERE estado = 'activo';

CREATE TABLE IF NOT EXISTS movimientos_equipo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipo_id TEXT NOT NULL REFERENCES equipos(id) ON DELETE RESTRICT,
    accion TEXT NOT NULL,                      -- REGISTRO, PRESTAMO, DEVOLUCION, CAMBIO_ESTADO...
    detalle TEXT DEFAULT '',
    usuario TEXT DEFAULT '',
    fecha TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS incidencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT NOT NULL,
    descripcion TEXT NOT NULL,
    espacio_id TEXT REFERENCES espacios(id) ON DELETE RESTRICT,
    equipo_id TEXT REFERENCES equipos(id) ON DELETE RESTRICT,
    reportado_por TEXT NOT NULL,
    categoria TEXT NOT NULL,
    prioridad TEXT NOT NULL CHECK (prioridad IN ('baja', 'media', 'alta', 'critica')),
    area_responsable TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'abierta'
        CHECK (estado IN ('abierta', 'en_proceso', 'resuelta', 'cerrada')),
    origen_clasificacion TEXT NOT NULL CHECK (origen_clasificacion IN ('IA', 'IA_AJUSTADA', 'MANUAL')),
    ia_modelo TEXT,
    ia_justificacion TEXT,
    ia_confianza REAL,
    ia_error TEXT,                             -- motivo por el que no se usó la IA (si aplica)
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS historial_incidencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incidencia_id INTEGER NOT NULL REFERENCES incidencias(id) ON DELETE CASCADE,
    campo TEXT NOT NULL,
    valor_anterior TEXT,
    valor_nuevo TEXT,
    usuario TEXT DEFAULT '',
    fecha TEXT NOT NULL
);
"""


def ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def set_db_path(ruta: str | None) -> None:
    """Permite usar otra ruta de base de datos."""
    global _db_path_override
    _db_path_override = ruta


def get_db_path() -> str:
    return _db_path_override or config.db_path()


def get_connection() -> sqlite3.Connection:
    ruta = get_db_path()
    if ruta != ":memory:":
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(ruta, timeout=10, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db() -> None:
    con = get_connection()
    try:
        con.executescript(SCHEMA)
    finally:
        con.close()


@contextmanager
def transaccion():
    """Transacción de escritura exclusiva: valida y escribe sin carreras."""
    con = get_connection()
    try:
        con.execute("BEGIN IMMEDIATE")
        yield con
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()


def consultar(sql: str, params: tuple = ()) -> list[dict]:
    con = get_connection()
    try:
        return [dict(f) for f in con.execute(sql, params).fetchall()]
    finally:
        con.close()


def consultar_uno(sql: str, params: tuple = ()) -> dict | None:
    filas = consultar(sql, params)
    return filas[0] if filas else None
