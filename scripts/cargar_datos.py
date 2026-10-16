"""Carga por consola de los datos oficiales (responsable: David López).

Uso (desde la raíz del proyecto):
    python -m scripts.cargar_datos               # carga data/oficial/
"""
import sys

from core import db
from core.config import BASE_DIR
from core.data_loader import cargar_carpeta


def main():
    db.init_db()
    carpeta = BASE_DIR / "data" / "oficial"
    resultados = cargar_carpeta(carpeta, "oficial")
    if not resultados:
        print(f"No hay archivos espacios.* / equipos.* en {carpeta}")
        return 1
    for nombre, r in resultados.items():
        print(f"{nombre}: {r['insertados']} insertados, {r['omitidos']} omitidos, {len(r['errores'])} errores")
        for e in r["errores"]:
            print("   -", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
