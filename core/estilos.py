"""Tema visual compartido (responsable: David López).

aplicar_estilos() inyecta static/estilos.css y static/interacciones.js.
hero() dibuja la cabecera de una página. Los módulos pueden usar hero() en su
render() para que todas las pantallas tengan el mismo aspecto.
"""
import base64
from html import escape

import streamlit as st

from core.config import BASE_DIR

_STATIC = BASE_DIR / "static"


@st.cache_data
def _leer(nombre: str) -> str:
    return (_STATIC / nombre).read_text(encoding="utf-8")


def aplicar_estilos():
    st.markdown(f"<style>{_leer('estilos.css')}</style>", unsafe_allow_html=True)
    # Iframe invisible (mismo origen): el JS actúa sobre la página principal.
    with st.container(height=1, border=False, key="cg_js"):
        st.iframe(f"<script>{_leer('interacciones.js')}</script>", height=1)


@st.cache_data
def _logo_b64() -> str:
    return base64.b64encode((_STATIC / "logo.png").read_bytes()).decode()


def marca_sidebar():
    st.sidebar.markdown(
        f'<div class="cg-sidebar-marca"><img src="data:image/png;base64,{_logo_b64()}" alt="Campuslands">'
        '<span>Gestión de Campus</span></div>',
        unsafe_allow_html=True,
    )


def reloj_sidebar():
    st.sidebar.markdown('<div class="cg-reloj" id="cg-reloj"></div>', unsafe_allow_html=True)


def hero(titulo: str, subtitulo: str = "", chips: list[tuple[str, str]] | None = None):
    """chips: lista de (texto, tipo) donde tipo es "ok", "warn" o ""."""
    chips_html = "".join(
        f'<span class="cg-chip {escape(tipo)}">{escape(texto)}</span>' for texto, tipo in (chips or [])
    )
    st.markdown(
        f'<div class="cg-hero"><h1>{escape(titulo)}</h1><p>{escape(subtitulo)}</p>'
        f'<div class="cg-chips">{chips_html}</div></div>',
        unsafe_allow_html=True,
    )


def seccion(texto: str):
    st.markdown(f'<div class="cg-seccion">{escape(texto)}</div>', unsafe_allow_html=True)
