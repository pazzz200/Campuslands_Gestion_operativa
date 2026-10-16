"""Módulo de recursos tecnológicos — interfaz Streamlit (responsable: Juan Diego Velandia).

Contrato con app.py: exponer render() sin parámetros.
"""
from datetime import date, timedelta

import streamlit as st

from core.ui_utils import ejecutar, tabla
from modules.recursos import service as svc

COLS_EQUIPO = ["id", "nombre", "tipo", "estado_operativo", "disponible", "prestado_a",
               "fecha_devolucion_prevista", "descripcion", "origen_dato"]
COLS_PRESTAMO = ["id", "equipo_id", "equipo_nombre", "solicitante", "fecha_prestamo",
                 "fecha_devolucion_prevista", "vencido", "estado", "fecha_devolucion",
                 "estado_equipo_devolucion", "observaciones"]


def render():
    st.header("💻 Recursos tecnológicos")
    t1, t2, t3, t4 = st.tabs(["Consultar equipos", "Préstamos y devoluciones", "Trazabilidad", "Administrar equipos"])

    with t1:
        c1, c2, c3 = st.columns(3)
        tipo = c1.selectbox("Tipo", ["(todos)", *svc.tipos_equipo()], key="eq_tipo")
        estado = c2.selectbox("Estado operativo", ["(todos)", *svc.ESTADOS_OPERATIVOS], key="eq_estado")
        solo = c3.checkbox("Solo disponibles", key="eq_solo")
        filas = ejecutar(svc.listar_equipos, None if tipo == "(todos)" else tipo,
                         None if estado == "(todos)" else estado, solo) or []
        tabla(filas, COLS_EQUIPO, "No hay equipos. Cárguelos en 'Datos' o regístrelos.")

    with t2:
        st.subheader("Registrar préstamo")
        disponibles = svc.listar_equipos(solo_disponibles=True)
        opciones = {f"{e['id']} · {e['nombre']} ({e['tipo']})": e["id"] for e in disponibles}
        with st.form("form_prestamo"):
            eq = st.selectbox("Equipo disponible", list(opciones) or ["(no hay equipos disponibles)"])
            c1, c2 = st.columns(2)
            solicitante = c1.text_input("Solicitante")
            fecha_prev = c2.date_input("Devolución prevista", date.today() + timedelta(days=1))
            obs = st.text_input("Observaciones")
            usuario = st.text_input("Registrado por", key="prest_usuario")
            if st.form_submit_button("Prestar", type="primary"):
                ejecutar(svc.registrar_prestamo, opciones.get(eq, ""), solicitante, fecha_prev, obs, usuario,
                         exito="Préstamo registrado.")

        st.subheader("Registrar devolución")
        activos = svc.listar_prestamos(estado="activo")
        if not activos:
            st.info("No hay préstamos activos.")
        else:
            op = {f"#{p['id']} · {p['equipo_id']} · {p['solicitante']} (vence {p['fecha_devolucion_prevista']})"
                  f"{' ⚠️ VENCIDO' if p['vencido'] else ''}": p["id"] for p in activos}
            with st.form("form_devolucion"):
                sel = st.selectbox("Préstamo activo", list(op))
                estado_eq = st.selectbox("Estado en que se recibe", ["operativo", "mantenimiento", "danado"])
                obs = st.text_input("Observaciones (obligatorias si no está operativo)")
                usuario = st.text_input("Recibido por")
                if st.form_submit_button("Registrar devolución", type="primary"):
                    ejecutar(svc.registrar_devolucion, op[sel], estado_eq, obs, usuario,
                             exito="Devolución registrada.")

        st.subheader("Historial de préstamos")
        est = st.selectbox("Estado", ["(todos)", *svc.ESTADOS_PRESTAMO], key="hist_prest_estado")
        tabla(svc.listar_prestamos(None if est == "(todos)" else est), COLS_PRESTAMO, "Sin préstamos.")

    with t3:
        equipos = [e["id"] for e in svc.listar_equipos()]
        eid = st.selectbox("Equipo", ["(todos)", *equipos], key="traz_eq")
        tabla(svc.historial_equipo(None if eid == "(todos)" else eid),
              ["fecha", "equipo_id", "accion", "detalle", "usuario"], "Sin movimientos.")

    with t4:
        st.subheader("Registrar equipo")
        with st.form("form_equipo", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            codigo = c1.text_input("Código / serial")
            nombre = c2.text_input("Nombre")
            tipo = c3.text_input("Tipo (portátil, proyector...)")
            desc = st.text_input("Descripción")
            usuario = st.text_input("Registrado por")
            if st.form_submit_button("Crear equipo"):
                ejecutar(svc.crear_equipo, codigo, nombre, tipo, desc, "operativo", "manual", usuario,
                         exito="Equipo registrado.")

        equipos = svc.listar_equipos()
        if equipos:
            st.subheader("Cambiar estado operativo")
            with st.form("form_estado_eq"):
                eid = st.selectbox("Equipo", [f"{e['id']} ({e['estado_operativo']})" for e in equipos])
                nuevo = st.selectbox("Nuevo estado", svc.ESTADOS_OPERATIVOS)
                motivo = st.text_input("Motivo")
                usuario = st.text_input("Usuario")
                if st.form_submit_button("Aplicar"):
                    ejecutar(svc.cambiar_estado_operativo, eid.split(" (")[0], nuevo, motivo, usuario,
                             exito="Estado actualizado.")
