# Changelog — Evaluador Resolución 3280
> DUSAKAWI EPSI · Seguimiento Metas Res. 3280/2018

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
