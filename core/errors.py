"""Errores de negocio compartidos (responsable: David López).

Todas las reglas de negocio lanzan BusinessError con un mensaje en español
comprensible para el usuario final. La interfaz solo los muestra; nunca
contiene la lógica de validación.
"""


class BusinessError(Exception):
    """Operación rechazada por una regla de negocio. El mensaje es para el usuario."""


class NotFoundError(BusinessError):
    """El registro solicitado no existe."""
