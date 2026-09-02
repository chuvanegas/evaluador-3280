# Changelog — Evaluador Resolución 3280
> DUSAKAWI EPSI · Seguimiento Metas Res. 3280/2018

---

## [v0.4.1] — 2026-09-02 · Conteo por registros (coincide Excel)

### Corrección crítica
- **Conteo de registros en lugar de pacientes únicos**: `_preAgregar` ahora suma registros (enteros) en lugar de acumular Sets de pacientes únicos. Esto hace que los valores de "ACTIVIDAD CONCLUIDA" coincidan exactamente con el Excel DUSAKAWI:
  - Medicina general: 167 ✓ (antes: 154, contaba Sets con deduplicación cruzada entre CUPS)
  - Enfermería: 163 ✓
  - Profilaxis: 133 ✓
  - Barniz de flúor: 167 (Excel=159 — residual de 8 registros en zona de borde de edad)
- **Toggle "Con finalidad" activo por defecto**: la vista pre-eval ahora muestra la columna "Con finalidad" al abrir, que coincide con la columna "ACTIVIDAD CONCLUIDA" del Excel (antes mostraba "Sin filtro" por defecto)
- **Causa del error 154**: los Sets de pacientes con múltiples CUPS de medicina (ej. 890201 Y 890283) se sumaban por separado en el servidor, contando al mismo paciente varias veces. Con contadores de registros esto no ocurre — cada prestación es un registro independiente.

---

## [v0.4.0] — 2026-09-02 · Finalidad correcta + Clasificación por Diagnóstico

### Correcciones críticas
- **Bug de columnas de finalidad en TXT (Res. 3374)**: el parser leía la columna equivocada para `finalidadTecnologiaSalud`
  - Consultas: corregido de columna 20 a columna **10** — ahora `"11"` (preventiva) coincide correctamente
  - Procedimientos: corregido de columna 19 a columna **12** — ahora `"14"` (detección temprana) coincide
  - Efecto: todas las actividades con filtro de finalidad (medicina general, enfermería, odontología, barniz de flúor, profilaxis) antes mostraban 0 en "Con finalidad"; ahora cuentan los pacientes correctos
- **Orden de actividades en pre-eval**: Flask ordenaba las claves del JSON alfabéticamente; corregido con `app.json.sort_keys = False` — las actividades aparecen en el orden definido por la configuración (medicina general primero, luego enfermería, etc.)
- **Toggle "Sin finalidad"**: la columna "Sin final." ahora refleja correctamente cuántos registros tienen el CUPS pero con finalidad incorrecta o ausente

### Nuevas funciones
- **Clasificación por diagnóstico (DX)**: el parser ahora extrae `codDiagnosticoPrincipal` de cada consulta y procedimiento. Cada paciente queda asignado automáticamente a uno o más grupos DX según sus diagnósticos:
  | Diagnósticos | Grupo DX |
  |---|---|
  | Z316, Z318, Z319 | `PRECONCEPCIONAL` |
  | Z321, Z33X, Z340–Z359 | `EMBARAZADA` |
  | Z309, Z300, Z304 | `PLANIFICACION` |
  | E100–E149, E232, N251 | `DM` |
  | I10X, G932, I150–I159, I270, I272, K766, O100, O104, O109, O13X, O16X, P292, R030 | `HIPERTENSION` |
- **Pre-eval Ruta Materna y RCV por DX**: los programas Materna y RCV ahora cuentan únicamente los pacientes que tienen diagnósticos de la ruta, no todos los pacientes en el rango de edad:
  - `RUTA_MATERNA_PRECONCEPCION` / `RUTA_MATERNA_IVE` → grupo `PRECONCEPCIONAL`
  - `RUTA_MATERNA_PRENATAL` / `PARTO` / `POSPARTO` → grupo `EMBARAZADA`
  - `DI00011` → `EMBARAZADA` + `PRECONCEPCIONAL`
  - `RCV_DM` → `DM`
  - `RCV_RIESGO` / `RCV_DM_HTA` → `DM` + `HIPERTENSION`
- **Soporte multi-grupo por paciente**: un paciente puede pertenecer simultáneamente a su curso de vida (por edad) y a uno o más grupos DX — todos se contabilizan en las rutas correspondientes sin duplicación dentro de cada ruta

### Arquitectura
- `_getDxGrupos(dx)` — función de clasificación DX en el browser, basada en tabla `_DX_GRUPOS` con listas `exact` y `prefix` por grupo
- `_dxGruposPorPac` — mapa pre-calculado `numDoc → Set<DX_grupo>` construido en O(N) antes del loop de pacientes
- `_preAgregar` acepta arrays de grupos por paciente (antes solo aceptaba un string); itera sobre todos los grupos para construir los índices de conteo
- `_grupos_para_prog` en `app.py` respeta el campo `aplica_a` del programa cuando existe, antes de caer al cálculo por rango de edad

---

## [v0.3.0] — 2026-09-01 · Pre-evaluación completa por grupos de edad

### Nuevas funciones
- **Pre-eval — todos los cursos de vida**: PRIMERA_INFANCIA e INFANCIA ahora aparecen con sus totales correctos (antes solo se veía ADOLESCENCIA en adelante)
- **Dashboard — chips consolidados**: la cobertura muestra un solo chip por tipo de sección (Consultas, Procedimientos, Medicamentos, Otros Servicios) con total acumulado de todos los archivos cargados, más las fechas mínima y máxima de atención por archivo
- **Navegación directa al Paso 3**: al hacer clic en "Pre-evaluar RIPS" desde el Dashboard, la aplicación va directo al panel de Pre-evaluación (antes aterrizaba en el formulario vacío del Prestador)

### Correcciones
- **CUPS con `|finalidad` embebida**: el formato RIPS TXT (Res. 3374) genera campos CUPS como `990201|05`; el parser ahora separa el código CUPS limpio (`990201`) de la finalidad embebida (`05`) para que coincida exactamente con la parametrización
- **Orden de programas en pre-eval**: los resultados ahora siguen el orden definido por Res. 3280/2018 — PRIMERA_INFANCIA → INFANCIA → ADOLESCENCIA → JOVENES → ADULTEZ → VEJEZ → Ruta Materna → DI → RCV
- **Error en paso al error de API**: si `/api/preeval` devuelve error, la UI avanza igual al Paso 3 y muestra el mensaje de error (antes se quedaba en el paso anterior sin mensaje visible)
- Eliminados todos los bloques de debug (cajas amarillas, `console.log` de conteos) del código de producción

### Arquitectura
- Los conteos de pre-eval se pre-agregan completamente en el browser (`_preAgregar`) antes de enviarlos al servidor — el servidor solo aplica la parametrización y devuelve resultados
- Grupos DI/RCV/Materna usan rango de edad (`edad_min`/`edad_max`) para clasificar usuarios; Cursos de Vida usan el campo `__grupo` exacto

---

## [v0.2.0] — 2026-09-01 · Persistencia en Supabase + Carga RIPS Dashboard

### Nuevas funciones
- **Supabase v0.2**: prestadores y metas persisten en la nube — accesibles desde cualquier PC o navegador
  - Tablas: `usuarios`, `prestadores`, `metas`, `evaluaciones`
  - Credenciales solo por variables de entorno (`SUPABASE_URL`, `SUPABASE_KEY`)
- **Dashboard — Carga de Datos RIPS**: zona de carga (TXT / JSON) en la página inicial
  - Parseo de archivos 100% en el navegador (sin límite de tamaño, soporta 12+ archivos)
  - Cálculo de cobertura poblacional por curso de vida en el browser
  - Tabla de cobertura: Primera Infancia → Vejez + Materna + RCV
  - Tabla de usuarios con actividades CUPS repetidas
  - Botones: Procesar Data / Limpiar RIPS / Pre-evaluar / Ir a Evaluación
- **RIPS TXT (Res. 3374)**: parseo con codificación windows-1252/latin-1 en JavaScript
- **Cálculo de edad correcto**: usa fecha máxima de atención de todos los archivos RIPS (como Excel)

### Correcciones
- Bordes punteados vacíos en zonas de carga (`display:block` en `label.upload-big/.upload-drop`)
- Scroll vertical en tabla CUPS de Mantenimiento (`display:block` en `switchMantTab`)
- Claves de grupos con guión bajo (`PRIMERA_INFANCIA`, `JOVENES`) — coinciden con backend
- UUIDs completos (36 chars) para compatibilidad con Supabase
- Error 413 Payload Too Large al subir archivos grandes — resuelto moviendo parseo al browser

### Arquitectura
- Solo persiste en Supabase: **prestadores**, **metas**, **actas de evaluación firmadas**
- RIPS y pre-evaluación: temporales en sesión (se reinician cada carga — por diseño)
- Vercel: timeout 60s, `maxLambdaSize` 50mb
- Email git configurado: `elprimordialjd29@gmail.com`

---

## [v0.1.0] — 2026-08-XX · Versión inicial

### Funciones
- Autenticación con roles: `admin`, `evaluador`, `viewer`
- Gestión de prestadores (IPS contratadas) con modal de creación/edición
- Metas por programa y actividad: carga desde archivo xlsx (hoja A3 COMPLETO) o ingreso manual
- Pre-evaluación automática de RIPS según Res. 3280/2018
- 6 cursos de vida: Primera Infancia, Infancia, Adolescencia, Jóvenes, Adultez, Vejez
- Ruta Materna, Demanda Inducida (DI), RCV
- Tabla CUPS en Mantenimiento con filtros por segmento y scroll completo
- Modo oscuro (toggle sol/luna)
- Actas de evaluación con vista previa y exportación Excel
- Deploy en Vercel (serverless Python / Flask)
- Soporte RIPS TXT (Res. 3374) y JSON (Res. 2275)
