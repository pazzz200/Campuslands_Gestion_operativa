"""Utilidades de interfaz compartidas (responsable: David López).

ejecutar() envuelve cualquier llamada a un service: muestra el error de negocio
de forma comprensible y nunca deja que la app se caiga con una traza.
"""
import logging

import pandas as pd
import streamlit as st

from core.errors import BusinessError

log = logging.getLogger("campus")


def ejecutar(funcion, *args, exito: str | None = None, **kwargs):
    """Llama funcion(*args, **kwargs). Devuelve el resultado o None si falló."""
    try:
        resultado = funcion(*args, **kwargs)
    except BusinessError as e:
        st.error(f"❌ {e}")
        return None
    except Exception as e:  # error inesperado: se registra y se informa sin romper la app
        log.exception("Error inesperado")
        st.error(f"⚠️ Error inesperado: {e}. La operación no se realizó.")
        return None
    if exito:
        st.success(f"✅ {exito}")
    return resultado


def tabla(filas: list[dict], columnas: list[str] | None = None, vacio: str = "Sin registros."):
    if not filas:
        st.info(vacio)
        return
    df = pd.DataFrame(filas)
    if columnas:
        df = df[[c for c in columnas if c in df.columns]]
    st.dataframe(df, width="stretch", hide_index=True)
