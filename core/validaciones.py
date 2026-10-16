"""Validadores genéricos de formato (responsable: David López).

Solo validan FORMATO. Las reglas de negocio viven en el service.py de cada módulo.
Todos lanzan BusinessError con mensajes en español.
"""
from datetime import date, datetime, time

from core.errors import BusinessError


def texto_requerido(valor, campo: str, max_len: int = 500) -> str:
    if valor is None or not str(valor).strip():
        raise BusinessError(f"El campo '{campo}' es obligatorio.")
    valor = str(valor).strip()
    if len(valor) > max_len:
        raise BusinessError(f"El campo '{campo}' supera los {max_len} caracteres.")
    return valor


def texto_opcional(valor, max_len: int = 1000) -> str:
    valor = "" if valor is None else str(valor).strip()
    if len(valor) > max_len:
        raise BusinessError(f"El texto supera los {max_len} caracteres.")
    return valor


def entero_positivo(valor, campo: str) -> int:
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        raise BusinessError(f"El campo '{campo}' debe ser un número entero.") from None
    if isinstance(valor, float) and not float(valor).is_integer():
        raise BusinessError(f"El campo '{campo}' debe ser un número entero.")
    if numero <= 0:
        raise BusinessError(f"El campo '{campo}' debe ser mayor que cero.")
    return numero


def fecha_iso(valor, campo: str = "fecha") -> str:
    """Acepta date o 'YYYY-MM-DD'. Devuelve 'YYYY-MM-DD'."""
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    try:
        return date.fromisoformat(str(valor).strip()).isoformat()
    except (TypeError, ValueError):
        raise BusinessError(f"El campo '{campo}' debe tener formato AAAA-MM-DD.") from None


def hora_hhmm(valor, campo: str = "hora") -> str:
    """Acepta time o 'HH:MM'. Devuelve 'HH:MM'."""
    if isinstance(valor, time):
        return valor.strftime("%H:%M")
    try:
        return datetime.strptime(str(valor).strip()[:5], "%H:%M").strftime("%H:%M")
    except (TypeError, ValueError):
        raise BusinessError(f"El campo '{campo}' debe tener formato HH:MM.") from None


def opcion(valor, permitidas: tuple | list, campo: str) -> str:
    valor = "" if valor is None else str(valor).strip().lower()
    if valor not in permitidas:
        raise BusinessError(
            f"Valor inválido para '{campo}': '{valor}'. Permitidos: {', '.join(permitidas)}."
        )
    return valor
