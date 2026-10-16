"""Módulo de incidencias e IA — interfaz Streamlit (responsable: Samid).

Contrato con app.py: exponer render() sin parámetros.
La interfaz distingue SIEMPRE visualmente lo generado por IA de lo manual.
"""
import streamlit as st

from core.ui_utils import ejecutar, tabla
from modules.espacios import service as espacios
from modules.incidencias import ia_client
from modules.incidencias import service as svc
from modules.recursos import service as recursos

COLS = ["id", "titulo", "estado", "prioridad", "categoria", "area_responsable", "origen_clasificacion",
        "ia_confianza", "espacio_id", "equipo_id", "reportado_por", "creado_en"]
ETIQUETA_ORIGEN = {"IA": "🤖 IA", "IA_AJUSTADA": "🤖✏️ IA ajustada por usuario", "MANUAL": "✋ Manual (sin IA)"}


def _idx(lista, valor):
    return lista.index(valor) if valor in lista else 0


def _registrar():
    st.subheader("Reportar incidencia")
    if ia_client.ia_configurada():
        st.caption("Clasificación con IA real: Anthropic Claude (modelo configurado en .env).")
    else:
        st.warning("IA no configurada (falta ANTHROPIC_API_KEY). Se usará clasificación **MANUAL**.")

    esp_ids = ["(ninguno)", *[e["id"] for e in espacios.listar_espacios()]]
    eq_ids = ["(ninguno)", *[e["id"] for e in recursos.listar_equipos()]]
    titulo = st.text_input("Título", key="inc_titulo")
    descripcion = st.text_area("Descripción", key="inc_desc")
    c1, c2, c3 = st.columns(3)
    esp = c1.selectbox("Espacio relacionado", esp_ids, key="inc_esp")
    eq = c2.selectbox("Equipo relacionado", eq_ids, key="inc_eq")
    reportado = c3.text_input("Reportado por", key="inc_rep")
    esp = None if esp == "(ninguno)" else esp
    eq = None if eq == "(ninguno)" else eq

    if st.button("🤖 Clasificar con IA", disabled=not ia_client.ia_configurada()):
        with st.spinner("Consultando el modelo de IA..."):
            sug = ejecutar(svc.sugerir_clasificacion, titulo, descripcion, esp, eq)
        if sug is not None:
            st.session_state["inc_sugerencia"] = sug

    sug = st.session_state.get("inc_sugerencia")
    if sug:
        if sug["ok"]:
            st.info(f"🤖 **Sugerencia generada por IA** ({sug['modelo']}, confianza {sug['confianza']:.0%}): "
                    f"categoría **{sug['categoria']}**, prioridad **{sug['prioridad']}**, "
                    f"área **{sug['area_responsable']}**.\n\n_{sug['justificacion']}_")
        else:
            st.error(f"La IA no pudo clasificar: {sug['error']}\n\n✋ Complete la clasificación MANUALMENTE. "
                     "El registro quedará marcado como 'MANUAL (sin IA)'.")

    base = sug if sug and sug["ok"] else {}
    with st.form("form_incidencia"):
        st.markdown("**Clasificación final** (puede ajustar la sugerencia)")
        c1, c2, c3 = st.columns(3)
        cat = c1.selectbox("Categoría", ia_client.CATEGORIAS, index=_idx(ia_client.CATEGORIAS, base.get("categoria")))
        pri = c2.selectbox("Prioridad", ia_client.PRIORIDADES,
                           index=_idx(ia_client.PRIORIDADES, base.get("prioridad", "media")))
        area = c3.selectbox("Área responsable", ia_client.AREAS,
                            index=_idx(ia_client.AREAS, base.get("area_responsable")))
        if st.form_submit_button("Registrar incidencia", type="primary"):
            inc = ejecutar(svc.registrar_incidencia, titulo, descripcion, reportado, cat, pri, area, esp, eq, sug,
                           exito="Incidencia registrada.")
            if inc:
                st.write(f"Incidencia #{inc['id']} · origen: {ETIQUETA_ORIGEN[inc['origen_clasificacion']]}")
                st.session_state.pop("inc_sugerencia", None)


def _gestionar():
    c1, c2, c3, c4 = st.columns(4)
    est = c1.selectbox("Estado", ["(todos)", *svc.ESTADOS], key="fi_est")
    pri = c2.selectbox("Prioridad", ["(todas)", *ia_client.PRIORIDADES], key="fi_pri")
    area = c3.selectbox("Área", ["(todas)", *ia_client.AREAS], key="fi_area")
    origen = c4.selectbox("Origen", ["(todos)", "IA", "IA_AJUSTADA", "MANUAL"], key="fi_origen")
    filas = ejecutar(svc.listar_incidencias, None if est == "(todos)" else est, None if pri == "(todas)" else pri,
                     None if area == "(todas)" else area, None if origen == "(todos)" else origen) or []
    tabla(filas, COLS, "No hay incidencias.")
    if not filas:
        return
    sel = st.selectbox("Ver / actualizar incidencia", [f"#{f['id']} · {f['titulo']}" for f in filas])
    inc = svc.obtener_incidencia(int(sel.split(" ·")[0][1:]))
    st.markdown(f"**{inc['titulo']}** — {ETIQUETA_ORIGEN[inc['origen_clasificacion']]}")
    st.write(inc["descripcion"])
    if inc["ia_justificacion"]:
        st.caption(f"🤖 IA ({inc['ia_modelo']}, confianza {inc['ia_confianza']}): {inc['ia_justificacion']}")
    if inc["ia_error"]:
        st.caption(f"✋ IA no usada: {inc['ia_error']}")
    if inc["estado"] != "cerrada":
        with st.form("form_upd_inc"):
            c1, c2, c3, c4 = st.columns(4)
            opciones = [inc["estado"], *svc.TRANSICIONES[inc["estado"]]]
            nuevo_est = c1.selectbox("Estado", opciones)
            nueva_pri = c2.selectbox("Prioridad", ia_client.PRIORIDADES, index=_idx(ia_client.PRIORIDADES, inc["prioridad"]))
            nueva_area = c3.selectbox("Área", ia_client.AREAS, index=_idx(ia_client.AREAS, inc["area_responsable"]))
            usuario = c4.text_input("Usuario")
            if st.form_submit_button("Actualizar"):
                ejecutar(svc.actualizar_incidencia, inc["id"], nuevo_est, nueva_pri, nueva_area, usuario,
                         exito="Incidencia actualizada.")
    st.markdown("**Historial**")
    tabla(svc.historial_incidencia(inc["id"]), ["fecha", "campo", "valor_anterior", "valor_nuevo", "usuario"])


def render():
    st.header("🛠️ Incidencias (clasificación con IA)")
    t1, t2 = st.tabs(["Reportar", "Consultar y actualizar"])
    with t1:
        _registrar()
    with t2:
        _gestionar()
