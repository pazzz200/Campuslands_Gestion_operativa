Coloque aquí los archivos OFICIALES de la hackatón:

- `espacios.csv` / `espacios.xlsx` / `espacios.json`: columnas mínimas: código, nombre, tipo (aula/cubículo), capacidad. Opcionales: ubicación, estado, motivo.
- `equipos.csv` / `equipos.xlsx` / `equipos.json`: columnas mínimas: código, nombre, tipo. Opcionales: descripción, estado.

Después: `python -m scripts.cargar_datos` o la página **Datos** de la app.
Si una columna tiene otro nombre, agréguelo en `SINONIMOS` de `core/data_loader.py`.
