# Contratos de integración

Regla de oro: **las funciones de `service.py` son el contrato**. Las interfaces (`ui.py`), y el cargador de datos solo llaman a estas funciones. Si cambias una firma, avisa al equipo y actualiza este archivo.

Convenciones comunes:
- Fechas `'AAAA-MM-DD'` (también aceptan `datetime.date`). Horas `'HH:MM'` (también aceptan `datetime.time`).
- Todas las funciones devuelven `dict` o `list[dict]` con **los mismos nombres de columna que la BD** (`core/db.py`).
- Los errores de negocio lanzan `core.errors.BusinessError` (o `NotFoundError`) con un mensaje en español para el usuario. La interfaz los muestra con `core.ui_utils.ejecutar()`.
- Toda escritura se hace dentro de `core.db.transaccion()`, que valida y escribe de forma atómica.
- Cada `ui.py` expone `render()` sin parámetros, y `app.py` lo registra en el menú.

## core (David López)
| Función | Devuelve |
|---|---|
| `db.init_db()` | crea las tablas si no existen |
| `db.transaccion()` | context manager → `sqlite3.Connection` (BEGIN IMMEDIATE / COMMIT / ROLLBACK) |
| `db.consultar(sql, params)` / `db.consultar_uno(...)` | `list[dict]` / `dict \| None` |
| `db.ahora()` | `'AAAA-MM-DDTHH:MM:SS'` |
| `data_loader.cargar_archivo(origen, entidad, origen_dato='oficial', nombre_archivo=None)` | `{'insertados', 'omitidos', 'errores': [str]}` |
| `data_loader.cargar_carpeta(carpeta, origen_dato)` | `{nombre_archivo: resultado}` |

## modules.espacios.service (Juan Paz)
Constantes: `TIPOS_ESPACIO=('aula','cubiculo')`, `ESTADOS_ESPACIO`, `ESTADOS_RESERVA=('activa','cancelada')`, `HORA_APERTURA`, `HORA_CIERRE`.

| Función | Devuelve |
|---|---|
| `listar_espacios(tipo=None, estado=None, capacidad_minima=None)` | `list[espacio]` |
| `obtener_espacio(espacio_id)` | `espacio` (NotFoundError) |
| `crear_espacio(espacio_id, nombre, tipo, capacidad, ubicacion='', origen_dato='manual')` | `espacio` |
| `actualizar_espacio(espacio_id, nombre=None, capacidad=None, ubicacion=None)` | `espacio` |
| `inhabilitar_espacio(espacio_id, motivo, cancelar_reservas_futuras=False)` | `{'espacio', 'reservas_afectadas', 'canceladas'}` |
| `habilitar_espacio(espacio_id)` | `espacio` |
| `consultar_disponibilidad(fecha, hora_inicio, hora_fin, asistentes=1, tipo=None)` | `list[espacio]` libres |
| `listar_reservas(espacio_id=None, fecha=None, estado=None, solicitante=None)` | `list[reserva + espacio_nombre, espacio_tipo]` |
| `obtener_reserva(reserva_id)` | `reserva` |
| `crear_reserva(espacio_id, solicitante, fecha, hora_inicio, hora_fin, asistentes, motivo='')` | `reserva` |
| `modificar_reserva(reserva_id, espacio_id=None, fecha=None, hora_inicio=None, hora_fin=None, asistentes=None, motivo=None)` | `reserva` |
| `cancelar_reserva(reserva_id)` | `reserva` |
| `resumen()` | `{'espacios_total', 'espacios_inhabilitados', 'reservas_hoy', 'reservas_futuras'}` |

`espacio` = `{id, nombre, tipo, capacidad, ubicacion, estado, motivo_inhabilitacion, origen_dato, creado_en}`
`reserva` = `{id, espacio_id, solicitante, fecha, hora_inicio, hora_fin, asistentes, motivo, estado, creado_en, actualizado_en}`

## modules.recursos.service (Juan Diego Velandia)
Constantes: `ESTADOS_OPERATIVOS=('operativo','mantenimiento','danado','baja')`, `ESTADOS_PRESTAMO=('activo','devuelto')`.

| Función | Devuelve |
|---|---|
| `listar_equipos(tipo=None, estado_operativo=None, solo_disponibles=False)` | `list[equipo]` |
| `tipos_equipo()` | `list[str]` |
| `obtener_equipo(equipo_id)` | `equipo` (NotFoundError) |
| `crear_equipo(equipo_id, nombre, tipo, descripcion='', estado_operativo='operativo', origen_dato='manual', usuario='')` | `equipo` |
| `cambiar_estado_operativo(equipo_id, nuevo_estado, motivo, usuario='')` | `equipo` |
| `registrar_prestamo(equipo_id, solicitante, fecha_devolucion_prevista, observaciones='', usuario='')` | `prestamo` |
| `registrar_devolucion(prestamo_id, estado_equipo='operativo', observaciones='', usuario='')` | `prestamo` |
| `listar_prestamos(estado=None, equipo_id=None, solicitante=None)` | `list[prestamo + equipo_nombre, equipo_tipo, vencido]` |
| `obtener_prestamo(prestamo_id)` | `prestamo` |
| `historial_equipo(equipo_id=None, limite=200)` | `list[movimiento]` |
| `resumen()` | `{'equipos_total', 'equipos_disponibles', 'prestamos_activos', 'prestamos_vencidos'}` |

`equipo` = `{id, nombre, tipo, descripcion, estado_operativo, origen_dato, creado_en, prestamo_activo_id, prestado_a, fecha_devolucion_prevista, disponible (0/1)}`.
`disponible` **se calcula** (operativo y sin préstamo activo) y no se guarda.

## modules.incidencias (Samid)
`ia_client`: `CATEGORIAS`, `PRIORIDADES=('baja','media','alta','critica')`, `AREAS`, `IAError`, `ia_configurada()`, `nombre_proveedor()`, `validar_respuesta_ia(dict) -> dict`, `clasificar(titulo, descripcion, contexto='') -> {categoria, prioridad, area_responsable, justificacion, confianza, modelo}`.

`service`:
| Función | Devuelve |
|---|---|
| `sugerir_clasificacion(titulo, descripcion, espacio_id=None, equipo_id=None)` | `{'ok': True, 'origen': 'IA', ...campos, 'modelo', 'error': None}` o `{'ok': False, 'origen': None, 'error': str}`. **Nunca lanza por fallos de IA.** |
| `registrar_incidencia(titulo, descripcion, reportado_por, categoria, prioridad, area_responsable, espacio_id=None, equipo_id=None, sugerencia_ia=None)` | `incidencia` con `origen_clasificacion` ∈ `IA`, `IA_AJUSTADA`, `MANUAL` |
| `listar_incidencias(estado=None, prioridad=None, area_responsable=None, origen=None)` | `list[incidencia]` ordenadas por prioridad |
| `obtener_incidencia(id)` / `historial_incidencia(id)` | `incidencia` / `list[cambio]` |
| `actualizar_incidencia(id, estado=None, prioridad=None, area_responsable=None, usuario='')` | `incidencia` |
| `resumen()` | `{'incidencias_abiertas', 'incidencias_criticas', 'clasificadas_ia', 'clasificadas_manual'}` |

Transiciones: `abierta → en_proceso | cerrada`, `en_proceso → resuelta | abierta`, `resuelta → cerrada | en_proceso`, `cerrada → (ninguna)`.

Dependencias entre módulos: `incidencias` usa `espacios.obtener_espacio` y `recursos.obtener_equipo` para validar las referencias. Ningún otro cruce.
