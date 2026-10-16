"""Módulo de espacios y reservas — lógica de negocio (responsable: Juan Paz).

Contrato público (ver docs/CONTRATOS.md). Todas las funciones:
  * reciben tipos simples (str, int, date/time o str ISO),
  * devuelven dict / list[dict] con los mismos nombres de columna que la BD,
  * lanzan BusinessError / NotFoundError con mensaje para el usuario.

Reglas de negocio implementadas aquí (no en la interfaz):
  R1 No se reserva un espacio inhabilitado.
  R2 Los asistentes no pueden superar la capacidad del espacio.
  R3 No puede haber dos reservas activas solapadas en el mismo espacio.
  R4 La hora de fin debe ser posterior a la de inicio y dentro del horario de la sede.
  R5 No se reserva en fechas/horas pasadas.
  R6 No se reduce la capacidad por debajo de reservas futuras ya aprobadas.
  R7 No se modifica una reserva cancelada.
"""
from datetime import datetime

from core.db import ahora, consultar, consultar_uno, transaccion
from core.errors import BusinessError, NotFoundError
from core.validaciones import (entero_positivo, fecha_iso, hora_hhmm, opcion,
                               texto_opcional, texto_requerido)

TIPOS_ESPACIO = ("aula", "cubiculo")
ESTADOS_ESPACIO = ("habilitado", "inhabilitado")
ESTADOS_RESERVA = ("activa", "cancelada")
HORA_APERTURA = "06:00"
HORA_CIERRE = "22:00"


# ----------------------------------------------------------------- espacios
def listar_espacios(tipo: str | None = None, estado: str | None = None,
                    capacidad_minima: int | None = None) -> list[dict]:
    sql, params = "SELECT * FROM espacios WHERE 1=1", []
    if tipo:
        sql += " AND tipo = ?"
        params.append(opcion(tipo, TIPOS_ESPACIO, "tipo"))
    if estado:
        sql += " AND estado = ?"
        params.append(opcion(estado, ESTADOS_ESPACIO, "estado"))
    if capacidad_minima:
        sql += " AND capacidad >= ?"
        params.append(int(capacidad_minima))
    return consultar(sql + " ORDER BY tipo, id", tuple(params))


def obtener_espacio(espacio_id: str, con=None) -> dict:
    sql = "SELECT * FROM espacios WHERE id = ?"
    fila = (con.execute(sql, (espacio_id,)).fetchone() if con
            else consultar_uno(sql, (espacio_id,)))
    if not fila:
        raise NotFoundError(f"No existe el espacio '{espacio_id}'.")
    return dict(fila)


def crear_espacio(espacio_id: str, nombre: str, tipo: str, capacidad: int,
                  ubicacion: str = "", origen_dato: str = "manual") -> dict:
    espacio_id = texto_requerido(espacio_id, "código", 50).upper()
    nombre = texto_requerido(nombre, "nombre", 120)
    tipo = opcion(tipo, TIPOS_ESPACIO, "tipo")
    capacidad = entero_positivo(capacidad, "capacidad")
    ubicacion = texto_opcional(ubicacion, 200)
    with transaccion() as con:
        if con.execute("SELECT 1 FROM espacios WHERE id = ?", (espacio_id,)).fetchone():
            raise BusinessError(f"Ya existe un espacio con el código '{espacio_id}'.")
        con.execute(
            "INSERT INTO espacios (id, nombre, tipo, capacidad, ubicacion, origen_dato, creado_en)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (espacio_id, nombre, tipo, capacidad, ubicacion, origen_dato, ahora()),
        )
    return obtener_espacio(espacio_id)


def actualizar_espacio(espacio_id: str, nombre: str | None = None, capacidad: int | None = None,
                       ubicacion: str | None = None) -> dict:
    with transaccion() as con:
        espacio = obtener_espacio(espacio_id, con)
        nombre = texto_requerido(nombre, "nombre", 120) if nombre is not None else espacio["nombre"]
        ubicacion = texto_opcional(ubicacion, 200) if ubicacion is not None else espacio["ubicacion"]
        nueva_cap = entero_positivo(capacidad, "capacidad") if capacidad is not None else espacio["capacidad"]
        if nueva_cap < espacio["capacidad"]:  # R6
            max_asist = con.execute(
                "SELECT MAX(asistentes) FROM reservas WHERE espacio_id = ? AND estado = 'activa'"
                " AND fecha >= ?", (espacio_id, datetime.now().date().isoformat()),
            ).fetchone()[0]
            if max_asist and max_asist > nueva_cap:
                raise BusinessError(
                    f"No se puede reducir la capacidad a {nueva_cap}: hay reservas futuras "
                    f"con {max_asist} asistentes. Modifíquelas o cancélelas primero.")
        con.execute("UPDATE espacios SET nombre = ?, capacidad = ?, ubicacion = ? WHERE id = ?",
                    (nombre, nueva_cap, ubicacion, espacio_id))
    return obtener_espacio(espacio_id)


def inhabilitar_espacio(espacio_id: str, motivo: str,
                        cancelar_reservas_futuras: bool = False) -> dict:
    """Devuelve {'espacio': dict, 'reservas_afectadas': list[dict], 'canceladas': bool}."""
    motivo = texto_requerido(motivo, "motivo de inhabilitación", 300)
    with transaccion() as con:
        espacio = obtener_espacio(espacio_id, con)
        if espacio["estado"] == "inhabilitado":
            raise BusinessError(f"El espacio '{espacio_id}' ya está inhabilitado.")
        afectadas = [dict(f) for f in con.execute(
            "SELECT * FROM reservas WHERE espacio_id = ? AND estado = 'activa' AND fecha >= ?"
            " ORDER BY fecha, hora_inicio", (espacio_id, datetime.now().date().isoformat()))]
        con.execute("UPDATE espacios SET estado = 'inhabilitado', motivo_inhabilitacion = ? WHERE id = ?",
                    (motivo, espacio_id))
        if cancelar_reservas_futuras and afectadas:
            con.execute(
                "UPDATE reservas SET estado = 'cancelada', actualizado_en = ?,"
                " motivo = motivo || ' [Cancelada: espacio inhabilitado]'"
                " WHERE espacio_id = ? AND estado = 'activa' AND fecha >= ?",
                (ahora(), espacio_id, datetime.now().date().isoformat()))
    return {"espacio": obtener_espacio(espacio_id), "reservas_afectadas": afectadas,
            "canceladas": bool(cancelar_reservas_futuras and afectadas)}


def habilitar_espacio(espacio_id: str) -> dict:
    with transaccion() as con:
        espacio = obtener_espacio(espacio_id, con)
        if espacio["estado"] == "habilitado":
            raise BusinessError(f"El espacio '{espacio_id}' ya está habilitado.")
        con.execute("UPDATE espacios SET estado = 'habilitado', motivo_inhabilitacion = '' WHERE id = ?",
                    (espacio_id,))
    return obtener_espacio(espacio_id)


# ----------------------------------------------------------------- reservas
def _validar_franja(fecha, hora_inicio, hora_fin) -> tuple[str, str, str]:
    fecha = fecha_iso(fecha, "fecha")
    hora_inicio = hora_hhmm(hora_inicio, "hora de inicio")
    hora_fin = hora_hhmm(hora_fin, "hora de fin")
    if hora_fin <= hora_inicio:  # R4
        raise BusinessError("La hora de fin debe ser posterior a la hora de inicio.")
    if hora_inicio < HORA_APERTURA or hora_fin > HORA_CIERRE:
        raise BusinessError(f"Las reservas deben estar entre {HORA_APERTURA} y {HORA_CIERRE}.")
    if datetime.fromisoformat(f"{fecha}T{hora_inicio}") < datetime.now():  # R5
        raise BusinessError("No se pueden hacer reservas en fechas u horas pasadas.")
    return fecha, hora_inicio, hora_fin


def _buscar_conflictos(con, espacio_id, fecha, hora_inicio, hora_fin, excluir_id=None) -> list[dict]:
    sql = ("SELECT * FROM reservas WHERE espacio_id = ? AND fecha = ? AND estado = 'activa'"
           " AND hora_inicio < ? AND hora_fin > ?")
    params = [espacio_id, fecha, hora_fin, hora_inicio]
    if excluir_id is not None:
        sql += " AND id != ?"
        params.append(excluir_id)
    return [dict(f) for f in con.execute(sql, params)]


def _validar_reserva(con, espacio_id, fecha, hora_inicio, hora_fin, asistentes, excluir_id=None):
    espacio = obtener_espacio(espacio_id, con)
    if espacio["estado"] != "habilitado":  # R1
        raise BusinessError(f"El espacio '{espacio_id}' está inhabilitado"
                            f" ({espacio['motivo_inhabilitacion'] or 'sin motivo'}); no admite reservas.")
    if asistentes > espacio["capacidad"]:  # R2
        raise BusinessError(f"Se solicitaron {asistentes} asistentes y el espacio '{espacio_id}'"
                            f" tiene capacidad para {espacio['capacidad']}.")
    conflictos = _buscar_conflictos(con, espacio_id, fecha, hora_inicio, hora_fin, excluir_id)
    if conflictos:  # R3
        c = conflictos[0]
        raise BusinessError(f"Conflicto de horario: el espacio '{espacio_id}' ya está reservado el {fecha}"
                            f" de {c['hora_inicio']} a {c['hora_fin']} (reserva #{c['id']}, {c['solicitante']}).")


def obtener_reserva(reserva_id: int) -> dict:
    fila = consultar_uno("SELECT * FROM reservas WHERE id = ?", (reserva_id,))
    if not fila:
        raise NotFoundError(f"No existe la reserva #{reserva_id}.")
    return fila


def listar_reservas(espacio_id: str | None = None, fecha=None, estado: str | None = None,
                    solicitante: str | None = None) -> list[dict]:
    sql = ("SELECT r.*, e.nombre AS espacio_nombre, e.tipo AS espacio_tipo FROM reservas r"
           " JOIN espacios e ON e.id = r.espacio_id WHERE 1=1")
    params = []
    if espacio_id:
        sql += " AND r.espacio_id = ?"
        params.append(espacio_id)
    if fecha:
        sql += " AND r.fecha = ?"
        params.append(fecha_iso(fecha))
    if estado:
        sql += " AND r.estado = ?"
        params.append(opcion(estado, ESTADOS_RESERVA, "estado"))
    if solicitante:
        sql += " AND r.solicitante LIKE ?"
        params.append(f"%{solicitante.strip()}%")
    return consultar(sql + " ORDER BY r.fecha, r.hora_inicio", tuple(params))


def crear_reserva(espacio_id: str, solicitante: str, fecha, hora_inicio, hora_fin,
                  asistentes: int, motivo: str = "") -> dict:
    solicitante = texto_requerido(solicitante, "solicitante", 120)
    asistentes = entero_positivo(asistentes, "asistentes")
    motivo = texto_opcional(motivo, 300)
    fecha, hora_inicio, hora_fin = _validar_franja(fecha, hora_inicio, hora_fin)
    with transaccion() as con:  # validar y escribir en la misma transacción evita dobles reservas
        _validar_reserva(con, espacio_id, fecha, hora_inicio, hora_fin, asistentes)
        cur = con.execute(
            "INSERT INTO reservas (espacio_id, solicitante, fecha, hora_inicio, hora_fin, asistentes,"
            " motivo, estado, creado_en, actualizado_en) VALUES (?, ?, ?, ?, ?, ?, ?, 'activa', ?, ?)",
            (espacio_id, solicitante, fecha, hora_inicio, hora_fin, asistentes, motivo, ahora(), ahora()))
        nuevo_id = cur.lastrowid
    return obtener_reserva(nuevo_id)


def modificar_reserva(reserva_id: int, espacio_id: str | None = None, fecha=None, hora_inicio=None,
                      hora_fin=None, asistentes: int | None = None, motivo: str | None = None) -> dict:
    actual = obtener_reserva(reserva_id)
    if actual["estado"] != "activa":  # R7
        raise BusinessError(f"La reserva #{reserva_id} está {actual['estado']} y no se puede modificar.")
    espacio_id = espacio_id or actual["espacio_id"]
    asistentes = entero_positivo(asistentes, "asistentes") if asistentes is not None else actual["asistentes"]
    motivo = texto_opcional(motivo, 300) if motivo is not None else actual["motivo"]
    fecha, hora_inicio, hora_fin = _validar_franja(
        fecha or actual["fecha"], hora_inicio or actual["hora_inicio"], hora_fin or actual["hora_fin"])
    with transaccion() as con:
        _validar_reserva(con, espacio_id, fecha, hora_inicio, hora_fin, asistentes, excluir_id=reserva_id)
        con.execute(
            "UPDATE reservas SET espacio_id = ?, fecha = ?, hora_inicio = ?, hora_fin = ?, asistentes = ?,"
            " motivo = ?, actualizado_en = ? WHERE id = ?",
            (espacio_id, fecha, hora_inicio, hora_fin, asistentes, motivo, ahora(), reserva_id))
    return obtener_reserva(reserva_id)


def cancelar_reserva(reserva_id: int) -> dict:
    with transaccion() as con:
        fila = con.execute("SELECT estado FROM reservas WHERE id = ?", (reserva_id,)).fetchone()
        if not fila:
            raise NotFoundError(f"No existe la reserva #{reserva_id}.")
        if fila["estado"] == "cancelada":
            raise BusinessError(f"La reserva #{reserva_id} ya estaba cancelada.")
        con.execute("UPDATE reservas SET estado = 'cancelada', actualizado_en = ? WHERE id = ?",
                    (ahora(), reserva_id))
    return obtener_reserva(reserva_id)


def consultar_disponibilidad(fecha, hora_inicio, hora_fin, asistentes: int = 1,
                             tipo: str | None = None) -> list[dict]:
    """Espacios habilitados, con capacidad suficiente y sin conflictos en la franja."""
    fecha, hora_inicio, hora_fin = _validar_franja(fecha, hora_inicio, hora_fin)
    asistentes = entero_positivo(asistentes, "asistentes")
    candidatos = listar_espacios(tipo=tipo, estado="habilitado", capacidad_minima=asistentes)
    ocupados = {r["espacio_id"] for r in consultar(
        "SELECT espacio_id FROM reservas WHERE fecha = ? AND estado = 'activa'"
        " AND hora_inicio < ? AND hora_fin > ?", (fecha, hora_fin, hora_inicio))}
    return [e for e in candidatos if e["id"] not in ocupados]


def resumen() -> dict:
    """Indicadores para el tablero de inicio."""
    hoy = datetime.now().date().isoformat()
    return {
        "espacios_total": consultar_uno("SELECT COUNT(*) n FROM espacios")["n"],
        "espacios_inhabilitados": consultar_uno(
            "SELECT COUNT(*) n FROM espacios WHERE estado = 'inhabilitado'")["n"],
        "reservas_hoy": consultar_uno(
            "SELECT COUNT(*) n FROM reservas WHERE fecha = ? AND estado = 'activa'", (hoy,))["n"],
        "reservas_futuras": consultar_uno(
            "SELECT COUNT(*) n FROM reservas WHERE fecha >= ? AND estado = 'activa'", (hoy,))["n"],
    }
