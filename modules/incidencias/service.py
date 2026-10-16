"""Módulo de incidencias — lógica de negocio (responsable: Samid).

Contrato público: ver docs/CONTRATOS.md.

Flujo:
  1. sugerir_clasificacion()  -> llama a la IA real; si falla devuelve ok=False y el motivo.
  2. registrar_incidencia()   -> guarda con origen_clasificacion:
         'IA'          el usuario aceptó exactamente lo que propuso la IA
         'IA_AJUSTADA' hubo sugerencia de IA pero el usuario cambió algún valor
         'MANUAL'      sin IA (no configurada, falló o el usuario no la usó)
  3. actualizar_incidencia()  -> cambia estado/prioridad/área con transiciones válidas e historial.

Reglas:
  R1 Categoría, prioridad y área deben pertenecer a los catálogos (sea IA o manual).
  R2 El espacio/equipo referenciado debe existir (integridad con los otros módulos).
  R3 Solo transiciones de estado válidas; una incidencia cerrada no se modifica.
  R4 La sugerencia de IA se revalida antes de guardarse; nunca se guarda una
     sugerencia inválida como si fuera de IA.
"""
from core.db import ahora, consultar, consultar_uno, transaccion
from core.errors import BusinessError, NotFoundError
from core.validaciones import opcion, texto_requerido
from modules.espacios import service as espacios
from modules.incidencias import ia_client
from modules.incidencias.ia_client import AREAS, CATEGORIAS, PRIORIDADES, IAError
from modules.recursos import service as recursos

ESTADOS = ("abierta", "en_proceso", "resuelta", "cerrada")
TRANSICIONES = {
    "abierta": ("en_proceso", "cerrada"),
    "en_proceso": ("resuelta", "abierta"),
    "resuelta": ("cerrada", "en_proceso"),
    "cerrada": (),
}


def _contexto(espacio_id, equipo_id) -> str:
    partes = []
    if espacio_id:
        e = espacios.obtener_espacio(espacio_id)
        partes.append(f"Espacio {e['id']} ({e['tipo']}, {e['nombre']}, capacidad {e['capacidad']}, {e['estado']})")
    if equipo_id:
        q = recursos.obtener_equipo(equipo_id)
        partes.append(f"Equipo {q['id']} ({q['tipo']}, {q['nombre']}, estado {q['estado_operativo']})")
    return "; ".join(partes)


def sugerir_clasificacion(titulo: str, descripcion: str, espacio_id: str | None = None,
                          equipo_id: str | None = None) -> dict:
    """Devuelve SIEMPRE un dict:
    {'ok': True, 'origen': 'IA', 'categoria', 'prioridad', 'area_responsable',
     'justificacion', 'confianza', 'modelo', 'error': None}
    o {'ok': False, 'origen': None, 'error': '<motivo>'} si la IA no está disponible.
    """
    titulo = texto_requerido(titulo, "título", 150)
    descripcion = texto_requerido(descripcion, "descripción", 2000)
    contexto = _contexto(espacio_id or None, equipo_id or None)  # R2 también aquí
    try:
        r = ia_client.clasificar(titulo, descripcion, contexto)
    except IAError as e:
        return {"ok": False, "origen": None, "error": str(e)}
    return {"ok": True, "origen": "IA", "error": None, **r}


def registrar_incidencia(titulo: str, descripcion: str, reportado_por: str, categoria: str,
                         prioridad: str, area_responsable: str, espacio_id: str | None = None,
                         equipo_id: str | None = None, sugerencia_ia: dict | None = None) -> dict:
    titulo = texto_requerido(titulo, "título", 150)
    descripcion = texto_requerido(descripcion, "descripción", 2000)
    reportado_por = texto_requerido(reportado_por, "reportado por", 120)
    categoria = opcion(categoria, CATEGORIAS, "categoría")  # R1
    prioridad = opcion(prioridad, PRIORIDADES, "prioridad")
    area_responsable = opcion(area_responsable, AREAS, "área responsable")
    espacio_id, equipo_id = espacio_id or None, equipo_id or None
    if espacio_id:
        espacios.obtener_espacio(espacio_id)  # R2: lanza NotFoundError
    if equipo_id:
        recursos.obtener_equipo(equipo_id)

    origen, ia_modelo, ia_just, ia_conf, ia_error = "MANUAL", None, None, None, None
    if sugerencia_ia and sugerencia_ia.get("ok"):
        try:
            valida = ia_client.validar_respuesta_ia(sugerencia_ia)  # R4
        except IAError as e:
            ia_error = f"Sugerencia descartada: {e}"
        else:
            igual = (valida["categoria"], valida["prioridad"], valida["area_responsable"]) == \
                    (categoria, prioridad, area_responsable)
            origen = "IA" if igual else "IA_AJUSTADA"
            ia_modelo = sugerencia_ia.get("modelo")
            ia_just, ia_conf = valida["justificacion"], valida["confianza"]
    elif sugerencia_ia:
        ia_error = sugerencia_ia.get("error") or "IA no disponible"

    with transaccion() as con:
        cur = con.execute(
            "INSERT INTO incidencias (titulo, descripcion, espacio_id, equipo_id, reportado_por, categoria,"
            " prioridad, area_responsable, estado, origen_clasificacion, ia_modelo, ia_justificacion,"
            " ia_confianza, ia_error, creado_en, actualizado_en)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'abierta', ?, ?, ?, ?, ?, ?, ?)",
            (titulo, descripcion, espacio_id, equipo_id, reportado_por, categoria, prioridad,
             area_responsable, origen, ia_modelo, ia_just, ia_conf, ia_error, ahora(), ahora()))
        nuevo_id = cur.lastrowid
        con.execute("INSERT INTO historial_incidencias (incidencia_id, campo, valor_anterior, valor_nuevo,"
                    " usuario, fecha) VALUES (?, 'creacion', NULL, ?, ?, ?)",
                    (nuevo_id, f"origen {origen}", reportado_por, ahora()))
    return obtener_incidencia(nuevo_id)


def obtener_incidencia(incidencia_id: int) -> dict:
    fila = consultar_uno("SELECT * FROM incidencias WHERE id = ?", (incidencia_id,))
    if not fila:
        raise NotFoundError(f"No existe la incidencia #{incidencia_id}.")
    return fila


def listar_incidencias(estado: str | None = None, prioridad: str | None = None,
                       area_responsable: str | None = None, origen: str | None = None) -> list[dict]:
    sql, params = "SELECT * FROM incidencias WHERE 1=1", []
    for col, val, permitidos in (("estado", estado, ESTADOS), ("prioridad", prioridad, PRIORIDADES),
                                 ("area_responsable", area_responsable, AREAS)):
        if val:
            sql += f" AND {col} = ?"
            params.append(opcion(val, permitidos, col))
    if origen:
        sql += " AND origen_clasificacion = ?"
        params.append(origen.upper())
    orden = "CASE prioridad WHEN 'critica' THEN 0 WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END"
    return consultar(f"{sql} ORDER BY {orden}, id DESC", tuple(params))


def actualizar_incidencia(incidencia_id: int, estado: str | None = None, prioridad: str | None = None,
                          area_responsable: str | None = None, usuario: str = "") -> dict:
    cambios = {}
    with transaccion() as con:
        inc = con.execute("SELECT * FROM incidencias WHERE id = ?", (incidencia_id,)).fetchone()
        if not inc:
            raise NotFoundError(f"No existe la incidencia #{incidencia_id}.")
        if inc["estado"] == "cerrada":  # R3
            raise BusinessError(f"La incidencia #{incidencia_id} está cerrada y no admite cambios.")
        if estado and estado != inc["estado"]:
            estado = opcion(estado, ESTADOS, "estado")
            if estado not in TRANSICIONES[inc["estado"]]:
                raise BusinessError(f"Transición no permitida: {inc['estado']} → {estado}. "
                                    f"Desde '{inc['estado']}' solo: {', '.join(TRANSICIONES[inc['estado']])}.")
            cambios["estado"] = estado
        if prioridad and prioridad != inc["prioridad"]:
            cambios["prioridad"] = opcion(prioridad, PRIORIDADES, "prioridad")
        if area_responsable and area_responsable != inc["area_responsable"]:
            cambios["area_responsable"] = opcion(area_responsable, AREAS, "área responsable")
        if not cambios:
            raise BusinessError("No hay cambios para guardar.")
        sets = ", ".join(f"{c} = ?" for c in cambios)
        con.execute(f"UPDATE incidencias SET {sets}, actualizado_en = ? WHERE id = ?",
                    (*cambios.values(), ahora(), incidencia_id))
        for campo, nuevo in cambios.items():
            con.execute("INSERT INTO historial_incidencias (incidencia_id, campo, valor_anterior, valor_nuevo,"
                        " usuario, fecha) VALUES (?, ?, ?, ?, ?, ?)",
                        (incidencia_id, campo, inc[campo], nuevo, usuario, ahora()))
    return obtener_incidencia(incidencia_id)


def historial_incidencia(incidencia_id: int) -> list[dict]:
    return consultar("SELECT * FROM historial_incidencias WHERE incidencia_id = ? ORDER BY id",
                     (incidencia_id,))


def resumen() -> dict:
    return {
        "incidencias_abiertas": consultar_uno(
            "SELECT COUNT(*) n FROM incidencias WHERE estado IN ('abierta','en_proceso')")["n"],
        "incidencias_criticas": consultar_uno(
            "SELECT COUNT(*) n FROM incidencias WHERE prioridad IN ('critica','alta')"
            " AND estado IN ('abierta','en_proceso')")["n"],
        "clasificadas_ia": consultar_uno(
            "SELECT COUNT(*) n FROM incidencias WHERE origen_clasificacion IN ('IA','IA_AJUSTADA')")["n"],
        "clasificadas_manual": consultar_uno(
            "SELECT COUNT(*) n FROM incidencias WHERE origen_clasificacion = 'MANUAL'")["n"],
    }
