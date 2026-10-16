"""Módulo de recursos tecnológicos — lógica de negocio (responsable: Juan Diego Velandia).

Contrato público: ver docs/CONTRATOS.md.

Disponibilidad = estado_operativo == 'operativo' Y sin préstamo activo.
(La disponibilidad se DERIVA de los préstamos; no se guarda en otra columna
 para que nunca quede inconsistente.)

Reglas de negocio:
  R1 Solo se prestan equipos en estado operativo.
  R2 Un equipo no puede tener dos préstamos activos (validado aquí + índice único en BD).
  R3 Solo se devuelve un préstamo activo; no se devuelve dos veces.
  R4 La fecha de devolución prevista no puede ser anterior a hoy.
  R5 No se cambia el estado operativo de un equipo mientras está prestado.
  R6 Toda operación queda registrada en movimientos_equipo (trazabilidad).
"""
import sqlite3
from datetime import date

from core.db import ahora, consultar, consultar_uno, transaccion
from core.errors import BusinessError, NotFoundError
from core.validaciones import fecha_iso, opcion, texto_opcional, texto_requerido

ESTADOS_OPERATIVOS = ("operativo", "mantenimiento", "danado", "baja")
ESTADOS_PRESTAMO = ("activo", "devuelto")

_SQL_EQUIPOS = """
SELECT e.*,
       p.id AS prestamo_activo_id, p.solicitante AS prestado_a,
       p.fecha_devolucion_prevista,
       CASE WHEN e.estado_operativo = 'operativo' AND p.id IS NULL THEN 1 ELSE 0 END AS disponible
FROM equipos e
LEFT JOIN prestamos p ON p.equipo_id = e.id AND p.estado = 'activo'
"""


def _registrar_movimiento(con, equipo_id, accion, detalle="", usuario=""):
    con.execute("INSERT INTO movimientos_equipo (equipo_id, accion, detalle, usuario, fecha)"
                " VALUES (?, ?, ?, ?, ?)", (equipo_id, accion, detalle, usuario, ahora()))


# ------------------------------------------------------------------ equipos
def listar_equipos(tipo: str | None = None, estado_operativo: str | None = None,
                   solo_disponibles: bool = False) -> list[dict]:
    sql, params = _SQL_EQUIPOS + " WHERE 1=1", []
    if tipo:
        sql += " AND LOWER(e.tipo) = LOWER(?)"
        params.append(tipo.strip())
    if estado_operativo:
        sql += " AND e.estado_operativo = ?"
        params.append(opcion(estado_operativo, ESTADOS_OPERATIVOS, "estado operativo"))
    if solo_disponibles:
        sql += " AND e.estado_operativo = 'operativo' AND p.id IS NULL"
    return consultar(sql + " ORDER BY e.tipo, e.id", tuple(params))


def tipos_equipo() -> list[str]:
    return [f["tipo"] for f in consultar("SELECT DISTINCT tipo FROM equipos ORDER BY tipo")]


def obtener_equipo(equipo_id: str) -> dict:
    fila = consultar_uno(_SQL_EQUIPOS + " WHERE e.id = ?", (equipo_id,))
    if not fila:
        raise NotFoundError(f"No existe el equipo '{equipo_id}'.")
    return fila


def crear_equipo(equipo_id: str, nombre: str, tipo: str, descripcion: str = "",
                 estado_operativo: str = "operativo", origen_dato: str = "manual",
                 usuario: str = "") -> dict:
    equipo_id = texto_requerido(equipo_id, "código", 50).upper()
    nombre = texto_requerido(nombre, "nombre", 120)
    tipo = texto_requerido(tipo, "tipo", 60).lower()
    descripcion = texto_opcional(descripcion, 500)
    estado_operativo = opcion(estado_operativo, ESTADOS_OPERATIVOS, "estado operativo")
    with transaccion() as con:
        if con.execute("SELECT 1 FROM equipos WHERE id = ?", (equipo_id,)).fetchone():
            raise BusinessError(f"Ya existe un equipo con el código '{equipo_id}'.")
        con.execute("INSERT INTO equipos (id, nombre, tipo, descripcion, estado_operativo, origen_dato, creado_en)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (equipo_id, nombre, tipo, descripcion, estado_operativo, origen_dato, ahora()))
        _registrar_movimiento(con, equipo_id, "REGISTRO", f"Alta ({origen_dato}), estado {estado_operativo}", usuario)
    return obtener_equipo(equipo_id)


def cambiar_estado_operativo(equipo_id: str, nuevo_estado: str, motivo: str, usuario: str = "") -> dict:
    nuevo_estado = opcion(nuevo_estado, ESTADOS_OPERATIVOS, "estado operativo")
    motivo = texto_requerido(motivo, "motivo del cambio", 300)
    with transaccion() as con:
        eq = con.execute("SELECT * FROM equipos WHERE id = ?", (equipo_id,)).fetchone()
        if not eq:
            raise NotFoundError(f"No existe el equipo '{equipo_id}'.")
        if eq["estado_operativo"] == nuevo_estado:
            raise BusinessError(f"El equipo '{equipo_id}' ya está en estado '{nuevo_estado}'.")
        if con.execute("SELECT 1 FROM prestamos WHERE equipo_id = ? AND estado = 'activo'",
                       (equipo_id,)).fetchone():  # R5
            raise BusinessError(f"El equipo '{equipo_id}' está prestado. Registre la devolución antes de "
                                "cambiar su estado operativo.")
        con.execute("UPDATE equipos SET estado_operativo = ? WHERE id = ?", (nuevo_estado, equipo_id))
        _registrar_movimiento(con, equipo_id, "CAMBIO_ESTADO",
                              f"{eq['estado_operativo']} → {nuevo_estado}: {motivo}", usuario)
    return obtener_equipo(equipo_id)


# ---------------------------------------------------------------- préstamos
def obtener_prestamo(prestamo_id: int) -> dict:
    fila = consultar_uno("SELECT p.*, e.nombre AS equipo_nombre FROM prestamos p"
                         " JOIN equipos e ON e.id = p.equipo_id WHERE p.id = ?", (prestamo_id,))
    if not fila:
        raise NotFoundError(f"No existe el préstamo #{prestamo_id}.")
    return fila


def listar_prestamos(estado: str | None = None, equipo_id: str | None = None,
                     solicitante: str | None = None) -> list[dict]:
    sql = ("SELECT p.*, e.nombre AS equipo_nombre, e.tipo AS equipo_tipo,"
           " CASE WHEN p.estado = 'activo' AND p.fecha_devolucion_prevista < DATE('now','localtime')"
           " THEN 1 ELSE 0 END AS vencido"
           " FROM prestamos p JOIN equipos e ON e.id = p.equipo_id WHERE 1=1")
    params = []
    if estado:
        sql += " AND p.estado = ?"
        params.append(opcion(estado, ESTADOS_PRESTAMO, "estado"))
    if equipo_id:
        sql += " AND p.equipo_id = ?"
        params.append(equipo_id)
    if solicitante:
        sql += " AND p.solicitante LIKE ?"
        params.append(f"%{solicitante.strip()}%")
    return consultar(sql + " ORDER BY p.id DESC", tuple(params))


def registrar_prestamo(equipo_id: str, solicitante: str, fecha_devolucion_prevista,
                       observaciones: str = "", usuario: str = "") -> dict:
    solicitante = texto_requerido(solicitante, "solicitante", 120)
    observaciones = texto_opcional(observaciones, 500)
    fecha_prev = fecha_iso(fecha_devolucion_prevista, "fecha de devolución prevista")
    if fecha_prev < date.today().isoformat():  # R4
        raise BusinessError("La fecha de devolución prevista no puede ser anterior a hoy.")
    try:
        with transaccion() as con:
            eq = con.execute("SELECT * FROM equipos WHERE id = ?", (equipo_id,)).fetchone()
            if not eq:
                raise NotFoundError(f"No existe el equipo '{equipo_id}'.")
            if eq["estado_operativo"] != "operativo":  # R1
                raise BusinessError(f"El equipo '{equipo_id}' no está disponible: estado "
                                    f"'{eq['estado_operativo']}'.")
            activo = con.execute("SELECT id, solicitante FROM prestamos WHERE equipo_id = ? AND estado = 'activo'",
                                 (equipo_id,)).fetchone()
            if activo:  # R2
                raise BusinessError(f"El equipo '{equipo_id}' ya está prestado a {activo['solicitante']}"
                                    f" (préstamo #{activo['id']}). No se permiten préstamos duplicados.")
            cur = con.execute(
                "INSERT INTO prestamos (equipo_id, solicitante, fecha_prestamo, fecha_devolucion_prevista,"
                " estado, observaciones) VALUES (?, ?, ?, ?, 'activo', ?)",
                (equipo_id, solicitante, ahora(), fecha_prev, observaciones))
            nuevo_id = cur.lastrowid
            _registrar_movimiento(con, equipo_id, "PRESTAMO",
                                  f"Préstamo #{nuevo_id} a {solicitante}, devolver {fecha_prev}", usuario)
    except sqlite3.IntegrityError:  # índice único: segunda línea de defensa
        raise BusinessError(f"El equipo '{equipo_id}' ya tiene un préstamo activo.") from None
    return obtener_prestamo(nuevo_id)


def registrar_devolucion(prestamo_id: int, estado_equipo: str = "operativo",
                         observaciones: str = "", usuario: str = "") -> dict:
    """estado_equipo: estado operativo en que se recibe el equipo (operativo/danado/mantenimiento)."""
    estado_equipo = opcion(estado_equipo, ("operativo", "mantenimiento", "danado"), "estado del equipo")
    observaciones = texto_opcional(observaciones, 500)
    if estado_equipo != "operativo" and not observaciones:
        raise BusinessError("Describa en observaciones el problema del equipo devuelto.")
    with transaccion() as con:
        p = con.execute("SELECT * FROM prestamos WHERE id = ?", (prestamo_id,)).fetchone()
        if not p:
            raise NotFoundError(f"No existe el préstamo #{prestamo_id}.")
        if p["estado"] != "activo":  # R3
            raise BusinessError(f"El préstamo #{prestamo_id} ya fue devuelto el {p['fecha_devolucion']}.")
        con.execute("UPDATE prestamos SET estado = 'devuelto', fecha_devolucion = ?, estado_equipo_devolucion = ?,"
                    " observaciones = TRIM(observaciones || ' ' || ?) WHERE id = ?",
                    (ahora(), estado_equipo, observaciones, prestamo_id))
        con.execute("UPDATE equipos SET estado_operativo = ? WHERE id = ?", (estado_equipo, p["equipo_id"]))
        _registrar_movimiento(con, p["equipo_id"], "DEVOLUCION",
                              f"Préstamo #{prestamo_id} devuelto; estado: {estado_equipo}. {observaciones}".strip(),
                              usuario)
    return obtener_prestamo(prestamo_id)


def historial_equipo(equipo_id: str | None = None, limite: int = 200) -> list[dict]:
    sql, params = "SELECT * FROM movimientos_equipo", []
    if equipo_id:
        sql += " WHERE equipo_id = ?"
        params.append(equipo_id)
    return consultar(sql + " ORDER BY id DESC LIMIT ?", (*params, limite))


def resumen() -> dict:
    return {
        "equipos_total": consultar_uno("SELECT COUNT(*) n FROM equipos")["n"],
        "equipos_disponibles": len(listar_equipos(solo_disponibles=True)),
        "prestamos_activos": consultar_uno("SELECT COUNT(*) n FROM prestamos WHERE estado = 'activo'")["n"],
        "prestamos_vencidos": consultar_uno(
            "SELECT COUNT(*) n FROM prestamos WHERE estado = 'activo'"
            " AND fecha_devolucion_prevista < DATE('now','localtime')")["n"],
    }
