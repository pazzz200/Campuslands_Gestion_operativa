"""Configuración por variables de entorno (responsable: David López).

Lee el archivo .env (si existe) una sola vez. Nunca se escriben credenciales
en el código: usar .env.example como plantilla.
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv es opcional; las variables del sistema siguen funcionando
    load_dotenv = None

BASE_DIR = Path(__file__).resolve().parent.parent

if load_dotenv:
    load_dotenv(BASE_DIR / ".env")


def get(nombre: str, defecto: str | None = None) -> str | None:
    valor = os.getenv(nombre)
    return valor if valor not in (None, "") else defecto


def db_path() -> str:
    return get("DB_PATH", str(BASE_DIR / "data" / "campus.db"))


def anthropic_api_key() -> str | None:
    return get("ANTHROPIC_API_KEY")


def anthropic_model() -> str:
    return get("ANTHROPIC_MODEL", "claude-sonnet-5-5")


def ia_timeout() -> float:
    try:
        return float(get("IA_TIMEOUT_SEGUNDOS", "30"))
    except ValueError:
        return 30.0
