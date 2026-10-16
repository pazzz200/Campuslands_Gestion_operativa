"""Cliente REAL de IA para clasificar incidencias (responsable: Samid).

Proveedor: Google Gemini (plan gratuito, clave sin tarjeta en https://aistudio.google.com)
mediante su API REST con salida JSON forzada por esquema (responseSchema).

Configuración (.env):
    GEMINI_API_KEY=...               obligatorio para usar IA
    GEMINI_MODEL=gemini-3.8-flash    (opcional)
    GEMINI_MODELOS_RESPALDO=gemini-3.7-flash,gemini-flash-latest,gemini-flash-lite-latest (opcional)
    IA_TIMEOUT_SEGUNDOS=30           (opcional)

La respuesta SIEMPRE pasa por validar_respuesta_ia(). Si falta la clave, la red
falla o la respuesta no es válida, se lanza IAError. Este módulo NUNCA inventa
una clasificación.
"""
import json
import urllib.error
import urllib.request

from core import config

CATEGORIAS = ("infraestructura", "equipo_tecnologico", "red_conectividad", "software",
              "seguridad", "aseo_mantenimiento", "otro")
PRIORIDADES = ("baja", "media", "alta", "critica")
AREAS = ("mantenimiento", "soporte_ti", "redes", "seguridad", "servicios_generales",
         "coordinacion_academica")
CAMPOS = ("categoria", "prioridad", "area_responsable", "justificacion", "confianza")

ESQUEMA_GEMINI = {
    "type": "OBJECT",
    "properties": {
        "categoria": {"type": "STRING", "enum": list(CATEGORIAS)},
        "prioridad": {"type": "STRING", "enum": list(PRIORIDADES)},
        "area_responsable": {"type": "STRING", "enum": list(AREAS)},
        "justificacion": {"type": "STRING"},
        "confianza": {"type": "NUMBER"},
    },
    "required": list(CAMPOS),
}

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"

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
La justificación debe tener máximo 2 frases en español y la confianza un número entre 0 y 1."""


class IAError(Exception):
    """La IA no está disponible o devolvió una respuesta no válida."""

    def __init__(self, mensaje: str, http_estado: int | None = None):
        super().__init__(mensaje)
        self.http_estado = http_estado


# Respuestas HTTP con las que vale la pena probar otro modelo:
# saturación / límite (429, 500, 503) o modelo no disponible para la cuenta (404).
ESTADOS_REINTENTABLES = {404, 429, 500, 503}


def ia_configurada() -> bool:
    return bool(config.gemini_api_key())


def nombre_proveedor() -> str:
    return f"Google Gemini ({config.gemini_model()})"


def validar_respuesta_ia(datos) -> dict:
    """Valida y normaliza la respuesta del modelo. Lanza IAError si algo no cumple."""
    if not isinstance(datos, dict):
        raise IAError("La IA no devolvió un objeto estructurado.")
    faltan = [c for c in CAMPOS if c not in datos]
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


def _mensaje(titulo, descripcion, contexto) -> str:
    mensaje = f"Título: {titulo}\nDescripción: {descripcion}"
    return mensaje + (f"\nContexto del sistema: {contexto}" if contexto else "")


# ------------------------------------------------------------------ Gemini
def _post_json(url: str, cuerpo: dict, cabeceras: dict) -> dict:
    """POST HTTP con la librería estándar. """
    req = urllib.request.Request(url, data=json.dumps(cuerpo).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", **cabeceras})
    try:
        with urllib.request.urlopen(req, timeout=config.ia_timeout()) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detalle = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
        except Exception:
            detalle = ""
        raise IAError(f"Fallo del servicio de IA (HTTP {e.code}): {detalle or e.reason}", e.code) from None
    except Exception as e:  # red, DNS, timeout, JSON corrupto
        raise IAError(f"No se pudo contactar el servicio de IA: {type(e).__name__}: {e}") from None


def _clasificar_gemini(titulo, descripcion, contexto, clave, modelo) -> dict:
    cuerpo = {
        "systemInstruction": {"parts": [{"text": SISTEMA}]},
        "contents": [{"role": "user", "parts": [{"text": _mensaje(titulo, descripcion, contexto)}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": ESQUEMA_GEMINI,
                             "temperature": 0.2},
    }
    datos = _post_json(GEMINI_URL.format(modelo=modelo), cuerpo, {"x-goog-api-key": clave})
    try:
        texto = datos["candidates"][0]["content"]["parts"][0]["text"]
        respuesta = json.loads(texto)
    except (KeyError, IndexError, TypeError, ValueError):
        motivo = (datos.get("promptFeedback") or {}).get("blockReason") if isinstance(datos, dict) else None
        raise IAError(f"La IA no devolvió la clasificación en el formato esperado"
                      f"{f' (bloqueado: {motivo})' if motivo else ''}.") from None
    resultado = validar_respuesta_ia(respuesta)
    resultado["modelo"] = datos.get("modelVersion") or modelo
    return resultado


# ------------------------------------------------------------------ público
def clasificar(titulo: str, descripcion: str, contexto: str = "") -> dict:
    """Llama a Gemini. Devuelve dict validado + 'modelo'. Lanza IAError.

    Si el modelo principal está saturado o no disponible, prueba los de respaldo.
    """
    clave = config.gemini_api_key()
    if not clave:
        raise IAError("No hay GEMINI_API_KEY configurada en el archivo .env.")
    modelos = [config.gemini_model()]
    modelos += [m for m in config.gemini_modelos_respaldo() if m not in modelos]
    error = None
    for modelo in modelos:
        try:
            return _clasificar_gemini(titulo, descripcion, contexto, clave, modelo)
        except IAError as e:
            if e.http_estado not in ESTADOS_REINTENTABLES:
                raise
            error = e
    raise error
