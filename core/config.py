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


def gemini_api_key() -> str | None:
    return get("GEMINI_API_KEY")


def gemini_model() -> str:
    return get("GEMINI_MODEL", "gemini-3.8-flash")


def gemini_modelos_respaldo() -> list[str]:
    """Modelos que se prueban, en orden, si el principal está saturado o no disponible."""
    valor = get("GEMINI_MODELOS_RESPALDO", "gemini-3.7-flash,gemini-flash-latest,gemini-flash-lite-latest")
    return [m.strip() for m in valor.split(",") if m.strip()]


def ia_timeout() -> float:
    try:
        return float(get("IA_TIMEOUT_SEGUNDOS", "30"))
    except ValueError:
        return 30.0
