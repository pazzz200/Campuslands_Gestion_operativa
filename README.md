# Gestión de Campus: espacios, recursos tecnológicos e incidencias con IA

Aplicación web para la gestión operativa de una sede de **Campuslands**. Desde un mismo lugar permite reservar aulas y cubículos, prestar equipos tecnológicos y reportar incidencias, que una **IA (Google Gemini)** clasifica automáticamente.



---

## Índice
1. [Problema](#1-problema)
2. [Integrantes](#2-integrantes)
3. [Stack tecnológico](#3-stack-tecnológico)
4. [Funcionalidades (MVP)](#4-funcionalidades-mvp)
5. [Uso de IA](#5-uso-de-ia)
6. [Reglas de negocio implementadas](#6-reglas-de-negocio-implementadas)
7. [Datos: carga, lectura, validación y persistencia](#7-datos-carga-lectura-validación-y-persistencia)
8. [Instalación y ejecución](#8-instalación-y-ejecución)
9. [Arquitectura y estructura del proyecto](#9-arquitectura-y-estructura-del-proyecto)

---

## 1. Problema

En la sede, la operación diaria se maneja de forma dispersa, con hojas de cálculo, mensajes y registros en papel. Esto genera problemas concretos:

- **Espacios:** dos grupos reservan la misma aula a la misma hora, se reservan espacios cerrados por mantenimiento o se asignan cubículos con menos puestos de los necesarios.
- **Recursos tecnológicos:** no se sabe qué portátil o proyector está disponible, quién lo tiene ni cuándo debe devolverlo. Se prestan equipos dañados y no queda historial.
- **Incidencias:** los reportes llegan sin orden ni prioridad, así que una falla eléctrica peligrosa puede esperar detrás de un problema estético. Además, nadie sabe qué área debe atenderla.

**Solución:** una sola aplicación que centraliza los tres procesos y aplica las reglas de negocio de forma automática. Por ejemplo, impide reservas solapadas y préstamos dobles. La IA clasifica cada incidencia por categoría, prioridad y área responsable, y el personal mantiene siempre la última palabra.

---

## 2. Integrantes

| Integrante | Rol y responsabilidad |
|---|---|
| **David Ricardo López Molina** | Integración y núcleo: `app.py`, base de datos, configuración, carga de datos oficiales, utilidades de interfaz y diseño visual (`core/`, `scripts/`, `static/`). |
| **Juan David Paz Santos** | Módulo de **espacios y reservas** (`modules/espacios/`). |
| **Juan Diego Velandia** | Módulo de **recursos tecnológicos**: préstamos, devoluciones y trazabilidad (`modules/recursos/`). |
| **Samid Andres Plata Melo** | Módulo de **incidencias** e integración con la **IA** (`modules/incidencias/`). |

---

## 3. Stack tecnológico

| Capa | Tecnología | Uso |
|---|---|---|
| Lenguaje | **Python 3.10+** (probado con 3.14) | Toda la aplicación. |
| Interfaz web | **Streamlit ≥ 1.50** | Pantallas, formularios, tablas y navegación. |
| Diseño | **HTML + CSS + JavaScript** (`static/`) | Tema visual con los colores de Campuslands, tarjetas, pestañas, fondo animado de estrellas, reloj y contadores animados. |
| Base de datos | **SQLite** (módulo `sqlite3` de Python) | Persistencia en `data/campus.db`, con claves foráneas, restricciones `CHECK` e índices únicos. |
| Datos | **pandas** + **openpyxl** | Lectura de archivos oficiales CSV, XLSX y JSON. |
| IA | **Google Gemini** (API REST, `urllib` de la librería estándar) | Clasificación de incidencias con salida JSON forzada por esquema. |
| Configuración | **python-dotenv** | Lectura de la clave de IA y otros parámetros desde `.env`. |

Dependencias en [`requirements.txt`](requirements.txt).

---

## 4. Funcionalidades (MVP)

Menú lateral de la aplicación:

| Página | Qué permite hacer |
|---|---|
| **Inicio** | Panel con indicadores en vivo: espacios (e inhabilitados), reservas de hoy y futuras, equipos disponibles, préstamos activos y vencidos, incidencias abiertas y críticas, y cuántas se clasificaron con IA o de forma manual. También muestra el estado de la IA. |
| **Espacios y reservas** | Consultar espacios con filtros por tipo, estado y capacidad. Buscar disponibilidad por fecha, franja horaria y asistentes. Crear, modificar y cancelar reservas. Registrar y editar espacios, e inhabilitarlos (con la opción de cancelar sus reservas futuras) o habilitarlos. |
| **Recursos tecnológicos** | Consultar equipos y su disponibilidad. Registrar préstamos y devoluciones (indicando en qué estado vuelve el equipo). Cambiar el estado operativo. Ver la trazabilidad completa de cada equipo. Registrar equipos nuevos. |
| **Incidencias (IA)** | Reportar una incidencia (opcionalmente asociada a un espacio o equipo), pedir la clasificación a la IA, aceptarla o ajustarla, y guardarla. Consultar incidencias ordenadas por prioridad, cambiar su estado, prioridad o área, y ver su historial de cambios. |
| **Datos** | Cargar los archivos oficiales de espacios y equipos (subiéndolos o desde la carpeta `data/oficial/`) y ver el resultado: insertados, omitidos y errores por fila. |

---

## 5. Uso de IA

### Para qué se usa
La IA clasifica cada **incidencia** reportada. A partir del título, la descripción y el contexto (el espacio o equipo afectado y su estado), propone:

| Campo | Valores posibles |
|---|---|
| `categoria` | infraestructura, equipo_tecnologico, red_conectividad, software, seguridad, aseo_mantenimiento, otro |
| `prioridad` | baja, media, alta, critica |
| `area_responsable` | mantenimiento, soporte_ti, redes, seguridad, servicios_generales, coordinacion_academica |
| `justificacion` | máximo 2 frases en español explicando la decisión |
| `confianza` | número entre 0 y 1 |

### Cómo funciona ([`modules/incidencias/ia_client.py`](modules/incidencias/ia_client.py))
1. **Proveedor:** Google Gemini, mediante su API REST `generateContent`. El plan gratuito de Google AI Studio basta.
2. **Instrucciones del sistema:** el modelo recibe criterios explícitos de prioridad. Por ejemplo, `critica` se usa ante riesgo para personas (eléctrico, incendio, gas, inundación) o la caída total de un servicio esencial. También recibe la descripción de qué atiende cada área.
3. **Salida estructurada:** se usa `responseMimeType: application/json` junto con un `responseSchema` que **limita los valores a los catálogos**, así que el modelo no puede inventar categorías.
4. **Validación propia:** toda respuesta pasa por `validar_respuesta_ia()`, que revisa campos obligatorios, valores dentro del catálogo, la longitud de la justificación y que la confianza esté entre 0 y 1. Si algo no cumple, la respuesta se descarta.
5. **Contexto real:** si la incidencia se asocia a un espacio o equipo, se envían sus datos (tipo, capacidad, estado operativo, etc.) para que la clasificación sea más precisa.
6. **Tolerancia a fallos:** si el modelo principal está saturado (HTTP 503/429/500) o no está disponible (404), se prueban de forma automática los modelos de respaldo (`gemini-3.7-flash`, `gemini-flash-latest`, `gemini-flash-lite-latest`).

### La persona decide, la IA sugiere
- La sugerencia se muestra en el formulario y el usuario puede **aceptarla tal cual o ajustarla** antes de guardar.
- Cada incidencia registra su **origen de clasificación**:
  - `IA`: se aceptó exactamente lo que propuso la IA.
  - `IA_AJUSTADA`: hubo sugerencia de IA, pero el usuario cambió algún valor.
  - `MANUAL`: sin IA, porque no está configurada, falló o no se usó.
- Se guardan también el **modelo** usado, la **justificación**, la **confianza** y, si aplica, el **motivo del fallo** de la IA. Así se puede auditar cada caso.
- **La IA nunca bloquea la operación.** Si no hay clave, no hay internet o la respuesta no es válida, la app avisa y permite clasificar de forma manual. El módulo **nunca inventa** una clasificación.

---

## 6. Reglas de negocio implementadas

Todas las reglas viven en los `service.py` de cada módulo, **no en la interfaz**. Lanzan `BusinessError` con un mensaje claro en español, que la interfaz muestra sin romperse. Las más críticas también se protegen en la base de datos.

### Espacios y reservas ([`modules/espacios/service.py`](modules/espacios/service.py))
| # | Regla |
|---|---|
| R1 | No se reserva un espacio **inhabilitado**. |
| R2 | Los **asistentes** no pueden superar la **capacidad** del espacio. |
| R3 | No puede haber **dos reservas activas solapadas** en el mismo espacio. |
| R4 | La hora de fin debe ser **posterior** a la de inicio y estar dentro del **horario de la sede (06:00–22:00)**. |
| R5 | No se reserva en **fechas u horas pasadas**. |
| R6 | No se **reduce la capacidad** de un espacio por debajo de los asistentes de sus reservas futuras. |
| R7 | No se modifica una reserva **cancelada**. |
| — | Al inhabilitar un espacio, la app muestra las reservas futuras afectadas y permite cancelarlas en el mismo paso. Los códigos de espacio no se repiten. |

### Recursos tecnológicos ([`modules/recursos/service.py`](modules/recursos/service.py))
| # | Regla |
|---|---|
| R1 | Solo se prestan equipos en estado **operativo**. |
| R2 | Un equipo no puede tener **dos préstamos activos**. Se valida en el código y además con un **índice único parcial** en la base de datos. |
| R3 | Solo se devuelve un préstamo **activo**; no se devuelve dos veces. |
| R4 | La fecha de devolución prevista **no puede ser anterior a hoy**. |
| R5 | No se cambia el **estado operativo** de un equipo mientras está **prestado**. |
| R6 | **Trazabilidad:** toda operación (registro, préstamo, devolución o cambio de estado) queda en `movimientos_equipo` con fecha y usuario. |
| — | Si un equipo vuelve dañado o necesita mantenimiento, es **obligatorio describir el problema**. La **disponibilidad se calcula** (operativo y sin préstamo activo) y no se guarda, para que nunca quede inconsistente. Los préstamos vencidos se marcan automáticamente. |

### Incidencias ([`modules/incidencias/service.py`](modules/incidencias/service.py))
| # | Regla |
|---|---|
| R1 | Categoría, prioridad y área deben pertenecer a los **catálogos**, tanto si vienen de la IA como de forma manual. |
| R2 | El **espacio o equipo** referenciado debe **existir**, lo que mantiene la integridad entre módulos. |
| R3 | Solo se permiten **transiciones de estado válidas**: `abierta → en_proceso / cerrada`, `en_proceso → resuelta / abierta`, `resuelta → cerrada / en_proceso`. Una incidencia **cerrada** no se modifica. |
| R4 | La sugerencia de la IA se **revalida** antes de guardarse; nunca se guarda una sugerencia inválida como si fuera de IA. |
| — | Cada cambio de estado, prioridad o área queda en `historial_incidencias` (valor anterior, valor nuevo, usuario y fecha). Las incidencias se listan **ordenadas por prioridad**. |

### Validaciones generales ([`core/validaciones.py`](core/validaciones.py))
Campos obligatorios, longitudes máximas, enteros positivos, fechas `AAAA-MM-DD`, horas `HH:MM` y valores de catálogo. Todas las escrituras se hacen dentro de una **transacción exclusiva** (`BEGIN IMMEDIATE`): se valida y se escribe de forma atómica, sin carreras entre usuarios, y si algo falla se hace *rollback* completo.

---

## 7. Datos: carga, lectura, validación y persistencia

### Carga
Hay dos formas de cargar los archivos oficiales:
- **Desde la app:** página **Datos** → elegir tipo (`espacios` o `equipos`) → subir el archivo → **Cargar archivo oficial**. También se puede pulsar **Cargar carpeta data/oficial**.
- **Por consola:** copiar los archivos en `data/oficial/` con nombres `espacios.*` y `equipos.*` y ejecutar:
  ```bash
  python -m scripts.cargar_datos
  ```

### Lectura ([`core/data_loader.py`](core/data_loader.py))
- Formatos admitidos: **CSV** (detecta el separador `,` o `;` y el BOM UTF-8), **XLSX/XLS** y **JSON** (lista de objetos o `{"espacios": [...]}`).
- Los nombres de columna se **normalizan**: minúsculas, sin tildes y con espacios convertidos en `_`. Además se reconocen **sinónimos**, por ejemplo `codigo`, `serial` o `placa` → `id`; `aforo` o `cupo` → `capacidad`; `bloque` o `piso` → `ubicacion`.
- Los valores también se normalizan. Por ejemplo, `salón` o `laboratorio` → `aula`; `disponible` o `bueno` → `operativo`; `averiado` → `danado`.

| Entidad | Columnas obligatorias | Opcionales |
|---|---|---|
| Espacios | código, nombre, tipo (aula/cubículo), capacidad | ubicación, estado, motivo |
| Equipos | código, nombre, tipo | descripción, estado |

### Validación
- Si faltan columnas obligatorias, se rechaza el archivo indicando cuáles faltan y cuáles se encontraron.
- **Cada fila se inserta usando los mismos `service.py` que la interfaz**, así que los datos cargados cumplen exactamente las mismas reglas de negocio. Por ejemplo, una capacidad de 0 o un tipo desconocido se rechazan.
- Las filas con error **no detienen la carga**: se informan una a una (`Fila 7: El campo 'capacidad' debe ser mayor que cero.`) y el resto se inserta.
- La carga es **idempotente**: los códigos que ya existen se **omiten** y no pisan cambios hechos desde la app. Se puede cargar el mismo archivo varias veces sin duplicar.
- Cada registro guarda su **origen** (`oficial` o `manual`) para distinguir datos cargados de datos creados en la app.

### Persistencia ([`core/db.py`](core/db.py))
- Base de datos **SQLite** en `data/campus.db`, creada automáticamente al iniciar. Los datos **se conservan al reiniciar** la aplicación.
- Esquema único y centralizado con 7 tablas: `espacios`, `reservas`, `equipos`, `prestamos`, `movimientos_equipo`, `incidencias` e `historial_incidencias`.
- La base de datos también hace cumplir reglas:
  - **claves foráneas** activas, con `ON DELETE RESTRICT`;
  - restricciones **`CHECK`** sobre tipos, estados, prioridades, capacidad > 0 y asistentes > 0;
  - **índice único parcial** que impide dos préstamos activos del mismo equipo.
- La ruta se puede cambiar con `DB_PATH` en `.env`. La base no se sube al repositorio: cada equipo genera la suya y carga los datos oficiales.

---

## 8. Instalación y ejecución

### Requisitos
- **Python 3.10 o superior** y **Git**.
- Una clave gratuita de **Google Gemini**, que se crea sin tarjeta en <https://aistudio.google.com> → *Get API key*. Es opcional: sin ella, la app funciona con clasificación manual.

### Pasos

**1. Clonar el repositorio**
```bash
git clone https://github.com/pazzz200/Campuslands_Gestion_operativa.git
cd Campuslands_Gestion_operativa
```

**2. Crear el entorno virtual e instalar dependencias**
```bash
python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
```


**3. Configurar la IA**
```bash
# Windows:
copy .env.example .env
# macOS / Linux:
cp .env.example .env
```
Abrir `.env` y pegar la clave en `GEMINI_API_KEY=`.

**4. Ejecutar**
```bash
streamlit run app.py
```
Se abre en <http://localhost:8501>. Para detenerla, pulsar `Ctrl + C` en la terminal.

**5. Cargar los datos oficiales**
Copiar `espacios.*` y `equipos.*` en `data/oficial/` y pulsar **Datos → Cargar carpeta data/oficial**, o ejecutar `python -m scripts.cargar_datos`.

### Variables de configuración (`.env`)
| Variable | Obligatoria | Por defecto | Descripción |
|---|---|---|---|
| `GEMINI_API_KEY` | Para usar IA | — | Clave de Google AI Studio. |
| `GEMINI_MODEL` | No | `gemini-3.8-flash` | Modelo principal. |
| `GEMINI_MODELOS_RESPALDO` | No | `gemini-3.7-flash,gemini-flash-latest,gemini-flash-lite-latest` | Modelos que se prueban si el principal está saturado. |
| `IA_TIMEOUT_SEGUNDOS` | No | `30` | Tiempo máximo de espera de la IA. |
| `DB_PATH` | No | `data/campus.db` | Ruta de la base de datos. |



---

## 9. Arquitectura y estructura del proyecto

Arquitectura en capas: **interfaz (`ui.py`) → reglas de negocio (`service.py`) → base de datos (`core/db.py`)**. Las interfaces y el cargador de datos solo llaman a las funciones de los `service.py`, que son el contrato entre módulos (documentado en [`docs/CONTRATOS.md`](docs/CONTRATOS.md)). Por eso una regla se cumple igual tanto si la acción viene de la pantalla como de un archivo cargado.

```
app.py                      Aplicación principal: menú, página de Inicio y página de Datos
core/
  config.py                 Lectura de variables de .env
  db.py                     Esquema SQLite, conexión y transacciones atómicas
  data_loader.py            Lectura y carga de CSV / XLSX / JSON oficiales
  validaciones.py           Validadores de formato reutilizables
  errors.py                 BusinessError / NotFoundError
  ui_utils.py               Manejo de errores en pantalla y tablas
  estilos.py                Inyección del tema visual (CSS/JS), cabecera y logo
modules/
  espacios/   service.py    Reglas de espacios y reservas      ui.py  Pantallas
  recursos/   service.py    Reglas de préstamos y equipos      ui.py  Pantallas
  incidencias/service.py    Reglas de incidencias              ui.py  Pantallas
              ia_client.py  Cliente de Google Gemini + validación de la respuesta
scripts/cargar_datos.py     Carga de data/oficial/ por consola
static/                     estilos.css, interacciones.js (estrellas, reloj, animaciones), logo.png
.streamlit/config.toml      Colores base del tema
data/oficial/               Archivos oficiales de la hackatón (ver LEEME.md)
docs/CONTRATOS.md           Funciones públicas de cada módulo
```

**Dependencias entre módulos:** `incidencias` usa `espacios.obtener_espacio` y `recursos.obtener_equipo` para validar las referencias. No hay ningún otro cruce, así que cada integrante trabaja en su módulo sin pisar a los demás.

**Manejo de errores:** ninguna acción muestra una traza técnica al usuario. Los errores de negocio se muestran como mensajes claros y los inesperados se registran en el log mientras la app sigue funcionando.
