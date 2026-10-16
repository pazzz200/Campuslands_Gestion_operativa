# Gestión de Campus: espacios, recursos tecnológicos e incidencias con IA

## Instalar y ejecutar

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # Windows: copy .env.example .env  → pegar ANTHROPIC_API_KEY
streamlit run app.py
```

Abrir http://localhost:8501.

## Uso
- **Datos**: subir los archivos oficiales (CSV, XLSX o JSON) de espacios y equipos, o dejarlos en `data/oficial/` y pulsar "Cargar carpeta". También se puede por consola: `python -m scripts.cargar_datos`.
- **Espacios y reservas**: consultar disponibilidad, reservar, modificar o cancelar, y administrar aulas y cubículos (habilitar o inhabilitar).
- **Recursos tecnológicos**: préstamos, devoluciones, estado operativo y trazabilidad de cada equipo.
- **Incidencias (IA)**: reportar, clasificar con IA (Anthropic Claude), ajustar la clasificación, y actualizar el estado con su historial. Si la IA falla, se clasifica manualmente y queda marcado como "Manual (sin IA)".

Los datos se guardan en `data/campus.db` y se conservan al reiniciar.

## Configuración (.env)
- `ANTHROPIC_API_KEY`: clave de la IA (console.anthropic.com).
- `ANTHROPIC_MODEL`: opcional, por defecto `claude-sonnet-5-5`.
- `IA_TIMEOUT_SEGUNDOS`: opcional, por defecto 30.

## Estructura
```
app.py                 aplicación principal (David López)
core/                  base de datos, configuración y carga de datos (David López)
modules/espacios/      espacios y reservas (Juan Paz)
modules/recursos/      recursos tecnológicos (Juan Diego Velandia)
modules/incidencias/   incidencias e IA (Samid)
data/oficial/          archivos oficiales
docs/CONTRATOS.md      funciones que expone cada módulo
```
