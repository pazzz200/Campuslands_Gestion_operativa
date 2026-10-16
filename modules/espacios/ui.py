"""Módulo de espacios y reservas — interfaz Streamlit (responsable: Juan Paz).

Contrato con app.py: exponer render() sin parámetros.
La interfaz NO valida reglas de negocio: solo llama a service y muestra resultados.
"""
from datetime import date, time, timedelta

import streamlit as st

from core.ui_utils import ejecutar, tabla
from modules.espacios import service as svc

COLS_ESPACIO = ["id", "nombre", "tipo", "capacidad", "ubicacion", "estado", "motivo_inhabilitacion", "origen_dato"]
COLS_RESERVA = ["id", "espacio_id", "espacio_nombre", "fecha", "hora_inicio", "hora_fin",
                "asistentes", "solicitante", "motivo", "estado"]


def _opciones_espacios(solo_habilitados=False):
    espacios = svc.listar_espacios(estado="habilitado" if solo_habilitados else None)
    return {f"{e['id']} · {e['nombre']} ({e['tipo']}, cap. {e['capacidad']})": e["id"] for e in espacios}


def render():
    st.header("🏫 Espacios y reservas")
    t1, t2, t3, t4 = st.tabs(["Consultar espacios", "Disponibilidad y reservar",
                              "Gestionar reservas", "Administrar espacios"])

    with t1:
        c1, c2, c3 = st.columns(3)
        tipo = c1.selectbox("Tipo", ["(todos)", *svc.TIPOS_ESPACIO], key="esp_f_tipo")
        estado = c2.selectbox("Estado", ["(todos)", *svc.ESTADOS_ESPACIO], key="esp_f_estado")
        cap = c3.number_input("Capacidad mínima", min_value=0, value=0, key="esp_f_cap")
        filas = ejecutar(svc.listar_espacios, None if tipo == "(todos)" else tipo,
                         None if estado == "(todos)" else estado, cap or None)
        tabla(filas or [], COLS_ESPACIO, "No hay espacios registrados. Cárguelos en 'Datos'.")

    with t2:
        st.subheader("Buscar espacios disponibles")
        c1, c2, c3, c4, c5 = st.columns(5)
        f = c1.date_input("Fecha", date.today() + timedelta(days=1), key="disp_fecha")
        hi = c2.time_input("Inicio", time(8, 0), key="disp_hi", step=900)
        hf = c3.time_input("Fin", time(10, 0), key="disp_hf", step=900)
        asis = c4.number_input("Asistentes", min_value=1, value=1, key="disp_asis")
        tipo_d = c5.selectbox("Tipo", ["(todos)", *svc.TIPOS_ESPACIO], key="disp_tipo")
        if st.button("Buscar disponibilidad"):
            libres = ejecutar(svc.consultar_disponibilidad, f, hi, hf, asis,
                              None if tipo_d == "(todos)" else tipo_d)
            if libres is not None:
                tabla(libres, COLS_ESPACIO, "No hay espacios disponibles para esa franja.")

        st.subheader("Registrar reserva")
        opciones = _opciones_espacios(solo_habilitados=True)
        with st.form("form_reserva", clear_on_submit=False):
            esp = st.selectbox("Espacio", list(opciones) or ["(sin espacios habilitados)"])
            c1, c2, c3 = st.columns(3)
            fecha = c1.date_input("Fecha", date.today() + timedelta(days=1))
            hora_i = c2.time_input("Hora inicio", time(8, 0), step=900)
            hora_f = c3.time_input("Hora fin", time(10, 0), step=900)
            c4, c5 = st.columns(2)
            solicitante = c4.text_input("Solicitante")
            asistentes = c5.number_input("Asistentes", min_value=1, value=1)
            motivo = st.text_input("Motivo")
            if st.form_submit_button("Reservar", type="primary"):
                r = ejecutar(svc.crear_reserva, opciones.get(esp, ""), solicitante, fecha, hora_i,
                             hora_f, asistentes, motivo, exito="Reserva registrada.")
                if r:
                    st.json(r)

    with t3:
        c1, c2, c3 = st.columns(3)
        filtro_esp = c1.selectbox("Espacio", ["(todos)", *[e["id"] for e in svc.listar_espacios()]], key="gr_esp")
        filtro_estado = c2.selectbox("Estado", ["(todos)", *svc.ESTADOS_RESERVA], key="gr_estado")
        filtro_sol = c3.text_input("Solicitante contiene", key="gr_sol")
        reservas = ejecutar(svc.listar_reservas, None if filtro_esp == "(todos)" else filtro_esp, None,
                            None if filtro_estado == "(todos)" else filtro_estado, filtro_sol or None) or []
        tabla(reservas, COLS_RESERVA, "No hay reservas.")

        activas = [r for r in reservas if r["estado"] == "activa"]
        if activas:
            st.subheader("Modificar o cancelar")
            sel = st.selectbox("Reserva", [f"#{r['id']} · {r['espacio_id']} · {r['fecha']} {r['hora_inicio']}-"
                                           f"{r['hora_fin']} · {r['solicitante']}" for r in activas])
            r = activas[[f"#{x['id']}" for x in activas].index(sel.split(" ·")[0])]
            todas = _opciones_espacios()
            with st.form("form_mod_reserva"):
                claves = list(todas)
                idx = next((i for i, k in enumerate(claves) if todas[k] == r["espacio_id"]), 0)
                esp = st.selectbox("Espacio", claves, index=idx)
                c1, c2, c3, c4 = st.columns(4)
                fecha = c1.date_input("Fecha", date.fromisoformat(r["fecha"]))
                hi = c2.time_input("Inicio", time.fromisoformat(r["hora_inicio"]), step=900)
                hf = c3.time_input("Fin", time.fromisoformat(r["hora_fin"]), step=900)
                asis = c4.number_input("Asistentes", min_value=1, value=int(r["asistentes"]))
                motivo = st.text_input("Motivo", r["motivo"] or "")
                b1, b2 = st.columns(2)
                if b1.form_submit_button("Guardar cambios", type="primary"):
                    ejecutar(svc.modificar_reserva, r["id"], todas[esp], fecha, hi, hf, asis, motivo,
                             exito=f"Reserva #{r['id']} modificada.")
                if b2.form_submit_button("Cancelar reserva"):
                    ejecutar(svc.cancelar_reserva, r["id"], exito=f"Reserva #{r['id']} cancelada.")

    with t4:
        st.subheader("Registrar espacio")
        with st.form("form_espacio", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns(4)
            codigo = c1.text_input("Código")
            nombre = c2.text_input("Nombre")
            tipo = c3.selectbox("Tipo", svc.TIPOS_ESPACIO)
            capacidad = c4.number_input("Capacidad", min_value=1, value=10)
            ubicacion = st.text_input("Ubicación")
            if st.form_submit_button("Crear espacio"):
                ejecutar(svc.crear_espacio, codigo, nombre, tipo, capacidad, ubicacion,
                         exito="Espacio registrado.")

        espacios = svc.listar_espacios()
        if espacios:
            st.subheader("Editar / habilitar / inhabilitar")
            ids = [e["id"] for e in espacios]
            eid = st.selectbox("Espacio", ids, key="adm_esp")
            e = svc.obtener_espacio(eid)
            st.caption(f"Estado actual: **{e['estado']}** {e['motivo_inhabilitacion'] or ''}")
            with st.form("form_edit_esp"):
                c1, c2, c3 = st.columns(3)
                nombre = c1.text_input("Nombre", e["nombre"])
                cap = c2.number_input("Capacidad", min_value=1, value=int(e["capacidad"]))
                ubic = c3.text_input("Ubicación", e["ubicacion"] or "")
                if st.form_submit_button("Guardar"):
                    ejecutar(svc.actualizar_espacio, eid, nombre, cap, ubic, exito="Espacio actualizado.")
            if e["estado"] == "habilitado":
                motivo = st.text_input("Motivo de inhabilitación", key="motivo_inh")
                cancelar = st.checkbox("Cancelar automáticamente las reservas futuras", key="cancel_fut")
                if st.button("Inhabilitar espacio"):
                    res = ejecutar(svc.inhabilitar_espacio, eid, motivo, cancelar, exito="Espacio inhabilitado.")
                    if res and res["reservas_afectadas"]:
                        accion = "canceladas" if res["canceladas"] else "AÚN ACTIVAS (revíselas)"
                        st.warning(f"{len(res['reservas_afectadas'])} reserva(s) futura(s) {accion}:")
                        tabla(res["reservas_afectadas"], COLS_RESERVA)
            elif st.button("Habilitar espacio"):
                ejecutar(svc.habilitar_espacio, eid, exito="Espacio habilitado.")
