"""Cliente REAL de IA para clasificar incidencias (responsable: Samid).

Proveedor: Anthropic Claude (Messages API) mediante "tool use" forzado, que
obliga al modelo a responder con un JSON estructurado. La respuesta SIEMPRE
pasa por validar_respuesta_ia() antes de usarse.

Configuración (.env):
    ANTHROPIC_API_KEY=...            obligatorio para usar IA
    ANTHROPIC_MODEL=claude-sonnet-5-5 (opcional)
    IA_TIMEOUT_SEGUNDOS=30           (opcional)

Si falta la clave, la librería no está instalada, la red falla o la respuesta
no es válida, se lanza IAError. Este módulo NUNCA inventa una clasificación.
"""
from core import config

CATEGORIAS = ("infraestructura", "equipo_tecnologico", "red_conectividad", "software",
              "seguridad", "aseo_mantenimiento", "otro")
PRIORIDADES = ("baja", "media", "alta", "critica")
AREAS = ("mantenimiento", "soporte_ti", "redes", "seguridad", "servicios_generales",
         "coordinacion_academica")

NOMBRE_HERRAMIENTA = "clasificar_incidencia"

HERRAMIENTA = {
    "name": NOMBRE_HERRAMIENTA,
    "description": "Registra la clasificación de una incidencia del campus.",
    "input_schema": {
        "type": "object",
        "properties": {
            "categoria": {"type": "string", "enum": list(CATEGORIAS)},
            "prioridad": {"type": "string", "enum": list(PRIORIDADES)},
            "area_responsable": {"type": "string", "enum": list(AREAS)},
            "justificacion": {"type": "string", "description": "Máximo 2 frases en español."},
            "confianza": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["categoria", "prioridad", "area_responsable", "justificacion", "confianza"],
    },
}

SISTEMA = """Eres el asistente de mesa de ayuda de una sede educativa (Campuslands).
Clasificas incidencias sobre aulas, cubículos y equipos tecnológicos.
Criterios de prioridad:
- critica: riesgo para la seguridad de personas (eléctrico, incendio, gas, inundación) o caída total de un servicio esencial.
- alta: impide usar un espacio o equipo que se necesita hoy, o afecta a muchas personas.
- media: degrada el uso pero hay alternativa.
- baja: estético, menor o sin urgencia.
Áreas: mantenimiento (infraestructura física, eléctrico, mobiliario), soporte_ti (equipos y software),
redes (internet/wifi), seguridad (riesgo, hurto, accesos), servicios_generales (aseo, insumos),
coordinacion_academica (programación de clases/uso de espacios).
Responde SOLO llamando a la herramienta clasificar_incidencia."""


class IAError(Exception):
    """La IA no está disponible o devolvió una respuesta no válida."""


def ia_configurada() -> bool:
    return bool(config.anthropic_api_key())


def validar_respuesta_ia(datos) -> dict:
    """Valida y normaliza la respuesta del modelo. Lanza IAError si algo no cumple."""
    if not isinstance(datos, dict):
        raise IAError("La IA no devolvió un objeto estructurado.")
    faltan = [c for c in ("categoria", "prioridad", "area_responsable", "justificacion", "confianza")
              if c not in datos]
    if faltan:
        raise IAError(f"Respuesta de IA incompleta; faltan: {', '.join(faltan)}.")
    limpio = {}
    for campo, permitidos in (("categoria", CATEGORIAS), ("prioridad", PRIORIDADES),
                              ("area_responsable", AREAS)):
        valor = str(datos[campo]).strip().lower()
        if valor not in permitidos:
            raise IAError(f"La IA propuso un valor no permitido para {campo}: '{valor}'.")
        limpio[campo] = valor
    just = str(datos["justificacion"]).strip()
    if not 3 <= len(just) <= 600:
        raise IAError("La justificación de la IA está vacía o es demasiado larga.")
    limpio["justificacion"] = just
    try:
        conf = float(datos["confianza"])
    except (TypeError, ValueError):
        raise IAError("La confianza de la IA no es numérica.") from None
    if not 0 <= conf <= 1:
        raise IAError(f"La confianza de la IA está fuera de rango: {conf}.")
    limpio["confianza"] = round(conf, 2)
    return limpio


def _crear_cliente():
    try:
        import anthropic
    except ImportError:
        raise IAError("La librería 'anthropic' no está instalada (pip install -r requirements.txt).") from None
    clave = config.anthropic_api_key()
    if not clave:
        raise IAError("No hay ANTHROPIC_API_KEY configurada en el archivo .env.")
    return anthropic, anthropic.Anthropic(api_key=clave, timeout=config.ia_timeout(), max_retries=1)


def clasificar(titulo: str, descripcion: str, contexto: str = "", cliente=None) -> dict:
    """Llama al modelo real. Devuelve dict validado + 'modelo'. Lanza IAError.

    `cliente` permite inyectar otro cliente compatible (opcional).
    """
    if cliente is None:
        anthropic, cliente = _crear_cliente()
        errores_api = (anthropic.APIError,)
    else:
        errores_api = ()
    modelo = config.anthropic_model()
    mensaje = f"Título: {titulo}\nDescripción: {descripcion}"
    if contexto:
        mensaje += f"\nContexto del sistema: {contexto}"
    try:
        respuesta = cliente.messages.create(
            model=modelo,
            max_tokens=500,
            system=SISTEMA,
            tools=[HERRAMIENTA],
            tool_choice={"type": "tool", "name": NOMBRE_HERRAMIENTA},
            messages=[{"role": "user", "content": mensaje}],
        )
    except errores_api as e:
        estado = getattr(e, "status_code", None)
        raise IAError(f"Fallo del servicio de IA ({type(e).__name__}{f' {estado}' if estado else ''}): {e}") from None
    except Exception as e:  # red, timeout u otro error del cliente
        raise IAError(f"No se pudo contactar el servicio de IA: {type(e).__name__}: {e}") from None

    bloque = next((b for b in getattr(respuesta, "content", []) or []
                   if getattr(b, "type", None) == "tool_use" and getattr(b, "name", None) == NOMBRE_HERRAMIENTA),
                  None)
    if bloque is None:
        raise IAError("La IA no devolvió la clasificación en el formato esperado.")
    resultado = validar_respuesta_ia(bloque.input)
    resultado["modelo"] = getattr(respuesta, "model", None) or modelo
    return resultado
