"""Aplicación principal Streamlit (responsable: David López).

Ejecutar:  streamlit run app.py

Integra los tres módulos a través de su contrato render(). Los integrantes NO
editan este archivo: si agregan una pantalla, la agregan dentro de su ui.py.
"""
import logging

import streamlit as st

from core import db
from core.data_loader import cargar_archivo, cargar_carpeta
from core.config import BASE_DIR
from core.ui_utils import ejecutar
from modules.espacios import service as espacios_svc
from modules.espacios import ui as espacios_ui
from modules.incidencias import ia_client
from modules.incidencias import service as incidencias_svc
from modules.incidencias import ui as incidencias_ui
from modules.recursos import service as recursos_svc
from modules.recursos import ui as recursos_ui

logging.basicConfig(level=logging.INFO)
st.set_page_config(page_title="Gestión de Campus", page_icon="🏫", layout="wide")


@st.cache_resource
def _inicializar():
    db.init_db()
    return True


def pagina_inicio():
    st.title("🏫 Gestión de espacios, recursos e incidencias")
    e, r, i = espacios_svc.resumen(), recursos_svc.resumen(), incidencias_svc.resumen()
    c = st.columns(4)
    c[0].metric("Espacios", e["espacios_total"], f"{e['espacios_inhabilitados']} inhabilitados", delta_color="off")
    c[1].metric("Reservas hoy", e["reservas_hoy"], f"{e['reservas_futuras']} futuras", delta_color="off")
    c[2].metric("Equipos disponibles", f"{r['equipos_disponibles']}/{r['equipos_total']}")
    c[3].metric("Préstamos activos", r["prestamos_activos"], f"{r['prestamos_vencidos']} vencidos",
                delta_color="inverse")
    c = st.columns(4)
    c[0].metric("Incidencias abiertas", i["incidencias_abiertas"])
    c[1].metric("Alta / crítica", i["incidencias_criticas"])
    c[2].metric("Clasificadas por IA", i["clasificadas_ia"])
    c[3].metric("Clasificadas manual", i["clasificadas_manual"])
    st.caption(f"Base de datos: `{db.get_db_path()}` · IA: "
               f"{'configurada (Anthropic Claude)' if ia_client.ia_configurada() else 'NO configurada → modo manual'}")
    if e["espacios_total"] == 0 and r["equipos_total"] == 0:
        st.warning("La base está vacía. Cargue los archivos oficiales en **Datos** o registre espacios y equipos desde cada módulo.")


def pagina_datos():
    st.header("📂 Datos")
    st.markdown("Cargue los archivos **oficiales** (CSV, XLSX o JSON). Los códigos existentes se omiten.")
    c1, c2 = st.columns(2)
    entidad = c1.selectbox("Tipo de datos", ["espacios", "equipos"])
    archivo = c2.file_uploader("Archivo", type=["csv", "xlsx", "xls", "json"])
    if archivo and st.button("Cargar archivo oficial", type="primary"):
        res = ejecutar(cargar_archivo, archivo.getvalue(), entidad, "oficial", archivo.name)
        if res:
            _mostrar_resultado({archivo.name: res})

    st.divider()
    carpeta = BASE_DIR / "data" / "oficial"
    st.markdown(f"O cargue todo lo que haya en `data/oficial/` (archivos `espacios.*`, `equipos.*`).")
    if st.button("Cargar carpeta data/oficial"):
        res = ejecutar(cargar_carpeta, carpeta, "oficial")
        if res is not None:
            _mostrar_resultado(res) if res else st.info("No se encontraron archivos en data/oficial/.")


def _mostrar_resultado(resultados: dict):
    for nombre, r in resultados.items():
        st.success(f"{nombre}: {r['insertados']} insertados, {r['omitidos']} omitidos (ya existían), "
                   f"{len(r['errores'])} con error.")
        for err in r["errores"]:
            st.error(err)


PAGINAS = {
    "Inicio": pagina_inicio,
    "Espacios y reservas": espacios_ui.render,
    "Recursos tecnológicos": recursos_ui.render,
    "Incidencias (IA)": incidencias_ui.render,
    "Datos": pagina_datos,
}


def main():
    _inicializar()
    pagina = st.sidebar.radio("Menú", list(PAGINAS))
    st.sidebar.caption("Hackatón Campuslands · MVP")
    try:
        PAGINAS[pagina]()
    except Exception as e:  # última red de seguridad: nunca mostrar una traza al usuario
        logging.exception("Error en la página %s", pagina)
        st.error(f"Ocurrió un error inesperado en '{pagina}': {e}")


main()
