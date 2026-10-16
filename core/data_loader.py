"""Cargador de datos oficiales (responsable: David López).

Lee CSV, XLSX o JSON y los inserta usando los MISMOS services de cada módulo,
así los datos cargados pasan por las mismas reglas de negocio que la interfaz.

Es tolerante a nombres de columna distintos (ver SINONIMOS). Cuando lleguen los
archivos oficiales: copiarlos en data/oficial/ como espacios.<ext> y
equipos.<ext>, revisar que sus columnas aparezcan en SINONIMOS (agregar si no)
y ejecutar:  python -m scripts.cargar_datos

La carga es idempotente: los códigos que ya existen se omiten (no se pisan
cambios hechos desde la aplicación).
"""
import io
import json
import unicodedata
from pathlib import Path

import pandas as pd

from core.errors import BusinessError

SINONIMOS = {
    "espacios": {
        "id": ["id", "codigo", "cod", "codigo_espacio", "id_espacio", "espacio", "sala"],
        "nombre": ["nombre", "nombre_espacio", "descripcion", "denominacion"],
        "tipo": ["tipo", "tipo_espacio", "clase", "categoria"],
        "capacidad": ["capacidad", "aforo", "cupo", "capacidad_maxima", "puestos"],
        "ubicacion": ["ubicacion", "bloque", "piso", "sede", "lugar"],
        "estado": ["estado", "habilitado", "disponibilidad", "estado_espacio"],
        "motivo": ["motivo", "motivo_inhabilitacion", "observaciones", "observacion"],
    },
    "equipos": {
        "id": ["id", "codigo", "cod", "serial", "placa", "inventario", "codigo_equipo", "id_equipo"],
        "nombre": ["nombre", "nombre_equipo", "equipo", "modelo"],
        "tipo": ["tipo", "tipo_equipo", "categoria", "clase"],
        "descripcion": ["descripcion", "marca", "caracteristicas", "detalle", "observaciones"],
        "estado": ["estado", "estado_operativo", "condicion", "estado_equipo"],
    },
}

_TIPO_ESPACIO = {"aula": "aula", "salon": "aula", "sala": "aula", "laboratorio": "aula",
                 "cubiculo": "cubiculo", "cubiculos": "cubiculo", "sala_estudio": "cubiculo"}
_ESTADO_ESPACIO_INHAB = {"inhabilitado", "no", "false", "0", "no_disponible", "fuera_de_servicio",
                         "cerrado", "mantenimiento", "inactivo"}
_ESTADO_EQUIPO = {"operativo": "operativo", "disponible": "operativo", "bueno": "operativo", "activo": "operativo",
                  "ok": "operativo", "prestado": "operativo", "mantenimiento": "mantenimiento",
                  "en_mantenimiento": "mantenimiento", "reparacion": "mantenimiento", "danado": "danado",
                  "malo": "danado", "averiado": "danado", "fuera_de_servicio": "danado", "baja": "baja",
                  "dado_de_baja": "baja"}


def _norm(texto) -> str:
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return "_".join(texto.strip().lower().replace("-", " ").split())


def leer_tabla(origen, nombre_archivo: str | None = None) -> pd.DataFrame:
    """origen: ruta (str/Path) o bytes/archivo subido. Devuelve DataFrame con columnas normalizadas."""
    nombre = (nombre_archivo or str(origen)).lower()
    if isinstance(origen, bytes):
        origen = io.BytesIO(origen)
    try:
        if nombre.endswith((".xlsx", ".xls")):
            df = pd.read_excel(origen)
        elif nombre.endswith(".json"):
            datos = json.load(origen) if hasattr(origen, "read") else json.loads(Path(origen).read_text("utf-8"))
            if isinstance(datos, dict):  # {"espacios": [...]} o {"data": [...]}
                datos = next((v for v in datos.values() if isinstance(v, list)), [])
            df = pd.DataFrame(datos)
        else:
            df = pd.read_csv(origen, sep=None, engine="python", encoding="utf-8-sig")
    except Exception as e:
        raise BusinessError(f"No se pudo leer el archivo '{nombre}': {e}") from None
    df.columns = [_norm(c) for c in df.columns]
    return df.dropna(how="all")


def _mapear_columnas(df: pd.DataFrame, entidad: str) -> dict:
    mapa = {}
    for campo, opciones in SINONIMOS[entidad].items():
        col = next((c for c in opciones if c in df.columns), None)
        if col:
            mapa[campo] = col
    faltan = [c for c in ("id", "nombre", "tipo") + (("capacidad",) if entidad == "espacios" else ())
              if c not in mapa]
    if faltan:
        raise BusinessError(f"Faltan columnas obligatorias para {entidad}: {', '.join(faltan)}. "
                            f"Columnas encontradas: {', '.join(df.columns)}.")
    return mapa


def _valor(fila, mapa, campo, defecto=""):
    col = mapa.get(campo)
    if not col:
        return defecto
    v = fila[col]
    return defecto if pd.isna(v) else (str(int(v)) if isinstance(v, float) and v.is_integer() else str(v).strip())


def cargar_espacios(df: pd.DataFrame, origen_dato: str = "oficial") -> dict:
    from modules.espacios import service as esp
    mapa = _mapear_columnas(df, "espacios")
    res = {"insertados": 0, "omitidos": 0, "errores": []}
    existentes = {e["id"] for e in esp.listar_espacios()}
    for i, fila in df.iterrows():
        codigo = _valor(fila, mapa, "id").upper()
        try:
            if codigo in existentes:
                res["omitidos"] += 1
                continue
            tipo = _TIPO_ESPACIO.get(_norm(_valor(fila, mapa, "tipo")), _norm(_valor(fila, mapa, "tipo")))
            esp.crear_espacio(codigo, _valor(fila, mapa, "nombre"), tipo, _valor(fila, mapa, "capacidad"),
                              _valor(fila, mapa, "ubicacion"), origen_dato)
            estado = _norm(_valor(fila, mapa, "estado", "habilitado"))
            if estado in _ESTADO_ESPACIO_INHAB:
                esp.inhabilitar_espacio(codigo, _valor(fila, mapa, "motivo") or "Inhabilitado según datos oficiales")
            existentes.add(codigo)
            res["insertados"] += 1
        except BusinessError as e:
            res["errores"].append(f"Fila {i + 2}: {e}")
    return res


def cargar_equipos(df: pd.DataFrame, origen_dato: str = "oficial") -> dict:
    from modules.recursos import service as rec
    mapa = _mapear_columnas(df, "equipos")
    res = {"insertados": 0, "omitidos": 0, "errores": []}
    existentes = {e["id"] for e in rec.listar_equipos()}
    for i, fila in df.iterrows():
        codigo = _valor(fila, mapa, "id").upper()
        try:
            if codigo in existentes:
                res["omitidos"] += 1
                continue
            estado_txt = _norm(_valor(fila, mapa, "estado", "operativo"))
            estado = _ESTADO_EQUIPO.get(estado_txt)
            if estado is None:
                raise BusinessError(f"Estado de equipo desconocido: '{estado_txt}'.")
            rec.crear_equipo(codigo, _valor(fila, mapa, "nombre"), _valor(fila, mapa, "tipo"),
                             _valor(fila, mapa, "descripcion"), estado, origen_dato, "carga_datos")
            existentes.add(codigo)
            res["insertados"] += 1
        except BusinessError as e:
            res["errores"].append(f"Fila {i + 2}: {e}")
    return res


CARGADORES = {"espacios": cargar_espacios, "equipos": cargar_equipos}


def cargar_archivo(origen, entidad: str, origen_dato: str = "oficial", nombre_archivo: str | None = None) -> dict:
    if entidad not in CARGADORES:
        raise BusinessError(f"Entidad desconocida: {entidad}. Use: {', '.join(CARGADORES)}.")
    return CARGADORES[entidad](leer_tabla(origen, nombre_archivo), origen_dato)


def cargar_carpeta(carpeta: str | Path, origen_dato: str = "oficial") -> dict:
    """Busca <carpeta>/espacios*.{csv,xlsx,json} y equipos*.* y los carga (espacios primero)."""
    carpeta = Path(carpeta)
    resultados = {}
    for entidad in ("espacios", "equipos"):
        for ruta in sorted(carpeta.glob(f"{entidad}*")):
            if ruta.suffix.lower() in (".csv", ".xlsx", ".xls", ".json"):
                resultados[ruta.name] = cargar_archivo(ruta, entidad, origen_dato)
    return resultados
