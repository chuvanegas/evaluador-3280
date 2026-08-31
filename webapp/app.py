#!/usr/bin/env python3
"""
Evaluador Res. 3280 – DUSAKAWI EPSI  v0.1
Servidor Flask con autenticación, roles y gestión de prestadores
"""
import json, os, datetime, uuid, hashlib
from pathlib import Path
from functools import wraps
from flask import (Flask, request, jsonify, render_template,
                   send_from_directory, session, redirect, url_for)
from werkzeug.utils import secure_filename

from evaluator import RIPSEvaluator

# ── Config ─────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config" / "res3280_cups.json"

# Vercel tiene sistema de archivos read-only; usar /tmp para escritura
_IS_VERCEL = os.environ.get("VERCEL") == "1"
_TMP       = Path("/tmp") if _IS_VERCEL else BASE_DIR
UPLOAD_DIR = _TMP / "uploads"
DATA_PATH  = _TMP / "data"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DATA_PATH.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dusakawi_3280_secret_2026")
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 MB

# ── Almacén en memoria ─────────────────────────────────────────────────────
_sessions = {}

# ── Persistencia simple (JSON) – en v0.2 migrar a Supabase ────────────────
USERS_FILE = DATA_PATH / "users.json"
IPS_FILE   = DATA_PATH / "ips.json"

def _hash(pwd): return hashlib.sha256(pwd.encode()).hexdigest()

def _load_users():
    if USERS_FILE.exists():
        with open(USERS_FILE, encoding="utf-8") as f:
            return json.load(f)
    # Usuarios por defecto
    default = [
        {"id": "1", "nombre": "Administrador", "username": "admin",
         "password": _hash("admin123"), "rol": "admin", "activo": True},
        {"id": "2", "nombre": "Jesus Vanegas", "username": "jvanegas",
         "password": _hash("dusakawi2026"), "rol": "evaluador", "activo": True},
    ]
    _save_users(default)
    return default

def _save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def _load_ips():
    if IPS_FILE.exists():
        with open(IPS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []

def _save_ips(ips):
    with open(IPS_FILE, "w", encoding="utf-8") as f:
        json.dump(ips, f, ensure_ascii=False, indent=2)

# ── Auth helpers ───────────────────────────────────────────────────────────
class SimpleUser:
    def __init__(self, data):
        self.id       = data["id"]
        self.nombre   = data["nombre"]
        self.username = data["username"]
        self.rol      = data["rol"]
        self.activo   = data.get("activo", True)

def _get_current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    users = _load_users()
    u = next((u for u in users if u["id"] == uid), None)
    return SimpleUser(u) if u else None

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = _get_current_user()
            if not user or user.rol not in roles:
                return jsonify({"error": "Sin permisos"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator

# ── Sesión evaluador ───────────────────────────────────────────────────────
def _get_session_dir() -> Path:
    sid = session.get("sid")
    if not sid:
        sid = str(uuid.uuid4())
        session["sid"] = sid
    d = UPLOAD_DIR / sid
    d.mkdir(exist_ok=True)
    return d

def _session_data() -> dict:
    sid = session.get("sid", "")
    if sid not in _sessions:
        _sessions[sid] = {"archivos": {}, "metas": {}, "info_acta": {}, "resultados": None}
    return _sessions[sid]

# ══════════════════════════════════════════════════════════════════════════
# RUTAS AUTH
# ══════════════════════════════════════════════════════════════════════════
@app.route("/login", methods=["GET", "POST"])
def login_page():
    if session.get("user_id"):
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        users = _load_users()
        user = next((u for u in users if u["username"] == username and u.get("activo", True)), None)
        if user and user["password"] == _hash(password):
            session["user_id"] = user["id"]
            session.permanent = True
            return redirect(url_for("index"))
        return render_template("login.html", error="Usuario o contraseña incorrectos")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

# ══════════════════════════════════════════════════════════════════════════
# RUTAS PRINCIPALES
# ══════════════════════════════════════════════════════════════════════════
@app.route("/")
@login_required
def index():
    user = _get_current_user()
    return render_template("index.html", current_user=user)

@app.route("/api/config")
@login_required
def api_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    return jsonify({"programas": cfg["programas"], "actividades_base": cfg["actividades_base"],
                    "cursos_de_vida": cfg["cursos_de_vida"], "finalidades": cfg.get("finalidades", {})})

# ══════════════════════════════════════════════════════════════════════════
# RUTAS PRESTADORES (IPS)
# ══════════════════════════════════════════════════════════════════════════
@app.route("/api/ips", methods=["GET"])
@login_required
def get_ips():
    return jsonify({"ips": _load_ips()})

@app.route("/api/ips", methods=["POST"])
@login_required
def create_ips():
    user = _get_current_user()
    if user.rol not in ["admin", "evaluador"]:
        return jsonify({"error": "Sin permisos"}), 403
    body = request.get_json() or {}
    if not body.get("nombre"):
        return jsonify({"error": "El nombre es requerido"}), 400
    ips_list = _load_ips()
    new_ips = {
        "id": str(uuid.uuid4())[:8],
        "nombre": body.get("nombre","").upper(),
        "nit": body.get("nit",""),
        "departamento": body.get("departamento",""),
        "municipio": body.get("municipio",""),
        "num_contrato": body.get("num_contrato",""),
        "vigencia_inicio": body.get("vigencia_inicio",""),
        "vigencia_fin": body.get("vigencia_fin",""),
        "rep_legal": body.get("rep_legal",""),
        "regimen": body.get("regimen","SUBSIDIADO"),
        "tipo_contrato": body.get("tipo_contrato","ASISTENCIAL"),
        "metas": body.get("metas", {}),
        "num_actas": 0,
        "creado_por": user.username,
        "creado_en": datetime.datetime.now().isoformat()
    }
    ips_list.append(new_ips)
    _save_ips(ips_list)
    return jsonify({"ok": True, "ips": new_ips})

@app.route("/api/ips/<ips_id>", methods=["PUT"])
@login_required
def update_ips(ips_id):
    user = _get_current_user()
    if user.rol not in ["admin", "evaluador"]:
        return jsonify({"error": "Sin permisos"}), 403
    body = request.get_json() or {}
    ips_list = _load_ips()
    for ips in ips_list:
        if ips["id"] == ips_id:
            for k in ["nombre","nit","departamento","municipio","num_contrato","vigencia_inicio","vigencia_fin","rep_legal","regimen","tipo_contrato","metas"]:
                if k in body: ips[k] = body[k]
            _save_ips(ips_list)
            return jsonify({"ok": True})
    return jsonify({"error": "No encontrado"}), 404

@app.route("/api/ips/<ips_id>/metas", methods=["POST"])
@login_required
def set_metas_ips(ips_id):
    """Guarda metas asociadas a una IPS (manual o desde archivo nota técnica)."""
    user = _get_current_user()
    if user.rol not in ["admin", "evaluador"]:
        return jsonify({"error": "Sin permisos"}), 403
    ips_list = _load_ips()
    target = next((ip for ip in ips_list if ip["id"] == ips_id), None)
    if not target:
        return jsonify({"error": "IPS no encontrada"}), 404

    # Carga desde archivo (nota técnica)
    if request.files.get("archivo"):
        f = request.files["archivo"]
        fname = f.filename.lower()
        tmp = UPLOAD_DIR / f"nt_{ips_id}_{f.filename}"
        f.save(str(tmp))
        if fname.endswith(".xlsx") or fname.endswith(".xls"):
            metas = RIPSEvaluator.parsear_nota_tecnica(str(tmp))
        else:
            return jsonify({"error": "Formato no soportado para nota técnica"}), 400
        target["metas"] = metas
        _save_ips(ips_list)
        resumen = {prog: sum(acts.values()) for prog, acts in metas.items()}
        return jsonify({"ok": True, "metas": resumen})

    # Carga manual (JSON)
    body = request.get_json() or {}
    target["metas"] = body.get("metas", {})
    _save_ips(ips_list)
    return jsonify({"ok": True})

# ══════════════════════════════════════════════════════════════════════════
# RUTAS USUARIOS
# ══════════════════════════════════════════════════════════════════════════
@app.route("/api/usuarios", methods=["GET"])
@login_required
def get_usuarios():
    user = _get_current_user()
    if user.rol != "admin":
        return jsonify({"error": "Sin permisos"}), 403
    users = _load_users()
    # No devolver password
    safe = [{"id":u["id"],"nombre":u["nombre"],"username":u["username"],
              "rol":u["rol"],"activo":u.get("activo",True)} for u in users]
    return jsonify({"usuarios": safe})

@app.route("/api/usuarios", methods=["POST"])
@login_required
def create_usuario():
    user = _get_current_user()
    if user.rol != "admin":
        return jsonify({"error": "Sin permisos"}), 403
    body = request.get_json() or {}
    if not body.get("username") or not body.get("password"):
        return jsonify({"error": "Usuario y contraseña son requeridos"}), 400
    users = _load_users()
    if any(u["username"] == body["username"] for u in users):
        return jsonify({"error": "El usuario ya existe"}), 400
    new_user = {
        "id": str(uuid.uuid4())[:8],
        "nombre": body.get("nombre", body["username"]),
        "username": body["username"],
        "password": _hash(body["password"]),
        "rol": body.get("rol", "evaluador"),
        "activo": True
    }
    users.append(new_user)
    _save_users(users)
    return jsonify({"ok": True})

# ══════════════════════════════════════════════════════════════════════════
# RUTAS EVALUACIÓN (mismas que antes + auth)
# ══════════════════════════════════════════════════════════════════════════
def _parsear_rips_txt(content_bytes):
    """
    Parsea el formato TXT de RIPS (Res. 3374/2000): pipe-delimited, latin-1.
    Retorna dict {seccion: [lista_de_dicts]}.
    """
    text = content_bytes.decode("latin-1")
    lines = [l.rstrip("|").strip() for l in text.replace("\r","").split("\n")]

    secciones_raw = {}
    seccion_actual = None
    for line in lines:
        if line.startswith("°---- ARCHIVO-") and line.endswith("----°"):
            nombre_sec = line.replace("°---- ARCHIVO-","").replace(" ----°","").strip()
            if nombre_sec not in secciones_raw:
                secciones_raw[nombre_sec] = []
                seccion_actual = nombre_sec
            else:
                seccion_actual = None  # marcador de cierre — dejar de leer esta sección
        elif seccion_actual and line and not line.startswith("°"):
            secciones_raw[seccion_actual].append(line)

    result = {}

    def cols(line):
        return [c.strip() for c in line.split(",")]

    if "USUARIOS" in secciones_raw:
        rows = []
        for line in secciones_raw["USUARIOS"]:
            c = cols(line)
            if len(c) < 5: continue
            rows.append({
                "tipoDocumentoIdentificacion": c[0],
                "numDocumentoIdentificacion":  c[1],
                "codPrestador":                c[2] if len(c) > 2 else "",
                "fechaNacimiento":             c[3] if len(c) > 3 else "",
                "codSexo":                     c[4] if len(c) > 4 else "",
                "codZona":                     c[5] if len(c) > 5 else "",
                "codMunicipio":                c[6] if len(c) > 6 else "",
            })
        result["usuarios"] = rows

    if "CONSULTAS" in secciones_raw:
        rows = []
        for line in secciones_raw["CONSULTAS"]:
            c = cols(line)
            if len(c) < 7: continue
            rows.append({
                "tipoDocumentoIdentificacion":  c[1],
                "numDocumentoIdentificacion":   c[2],
                "fechaInicioAtencion":          c[4][:10] if len(c) > 4 else "",
                "codConsulta":                  c[6] if len(c) > 6 else "",
                "finalidadTecnologiaSalud":     c[20] if len(c) > 20 else "",
            })
        result["consultas"] = rows

    if "PROCEDIMIENTOS" in secciones_raw:
        rows = []
        for line in secciones_raw["PROCEDIMIENTOS"]:
            c = cols(line)
            if len(c) < 8: continue
            rows.append({
                "tipoDocumentoIdentificacion":  c[1],
                "numDocumentoIdentificacion":   c[2],
                "fechaInicioAtencion":          c[4][:10] if len(c) > 4 else "",
                "codProcedimiento":             c[7] if len(c) > 7 else "",
                "finalidadTecnologiaSalud":     c[19] if len(c) > 19 else "",
            })
        result["procedimientos"] = rows

    if "MEDICAMENTOS" in secciones_raw:
        rows = []
        for line in secciones_raw["MEDICAMENTOS"]:
            c = cols(line)
            if len(c) < 10: continue
            rows.append({
                "tipoDocumentoIdentificacion":   c[1],
                "numDocumentoIdentificacion":    c[2],
                "fechaDispensacionMedicamento":  c[6][:10] if len(c) > 6 else "",
                "codTecnologiaSalud":            c[10] if len(c) > 10 else "",
                "nomTecnologiaSalud":            c[11] if len(c) > 11 else "",
            })
        result["medicamentos"] = rows

    if "OTROS SERVICIOS" in secciones_raw:
        rows = []
        for line in secciones_raw["OTROS SERVICIOS"]:
            c = cols(line)
            if len(c) < 8: continue
            rows.append({
                "tipoDocumentoIdentificacion":  c[1],
                "numDocumentoIdentificacion":   c[2],
                "fechaInicioAtencion":          c[6][:10] if len(c) > 6 else "",
                "codServicio":                  c[8] if len(c) > 8 else "",
                "nomServicio":                  c[9] if len(c) > 9 else "",
            })
        result["otrosServicios"] = rows

    return result


@app.route("/api/upload-rips", methods=["POST"])
@login_required
def upload_rips():
    if "files" not in request.files:
        return jsonify({"error": "No se recibieron archivos"}), 400
    sd = _session_data()
    info = []
    for file in request.files.getlist("files"):
        if not file.filename: continue
        fname_lower = file.filename.lower()

        # ── Formato TXT (RIPS Res. 3374 antiguo) ──────────────────────────────
        if fname_lower.endswith(".txt"):
            try:
                content = file.read()
                secciones = _parsear_rips_txt(content)
                if not secciones:
                    info.append({"archivo": file.filename, "error": "No se encontraron secciones RIPS en el archivo", "ok": False})
                    continue
                for seccion, datos in secciones.items():
                    sd["archivos"][seccion] = datos
                    info.append({"archivo": seccion, "registros": len(datos), "ok": True})
            except Exception as e:
                info.append({"archivo": file.filename, "error": str(e), "ok": False})
            continue

        # ── Formato JSON (RIPS nuevo) ─────────────────────────────────────────
        nombre = fname_lower.replace(".json","")
        canon = _canonicalizar_nombre(nombre)
        try:
            data = json.load(file)
            if not isinstance(data, list): data = [data]
            sd["archivos"][canon] = data
            info.append({"archivo": canon, "registros": len(data), "ok": True})
        except Exception as e:
            info.append({"archivo": nombre, "error": str(e), "ok": False})

    cobertura = {}
    if "usuarios" in sd["archivos"]:
        from evaluator import _calcular_edad, _grupo_edad, _load_config
        cfg = _load_config()
        hoy = datetime.date.today()
        for u in sd["archivos"]["usuarios"]:
            fn = u.get("fechaNacimiento") or u.get("fecha_nacimiento")
            edad = _calcular_edad(fn, hoy)
            grupo = _grupo_edad(edad, cfg["cursos_de_vida"])
            if grupo: cobertura[grupo] = cobertura.get(grupo, 0) + 1
    return jsonify({"archivos_cargados": list(sd["archivos"].keys()), "detalle": info, "cobertura_poblacion": cobertura})

def _canonicalizar_nombre(nombre):
    nombre = nombre.lower()
    for alias, canon in [
        ("consultaambulatorio","consultas"),("consultaambulatorias","consultas"),
        ("consulta","consultas"),("procedimiento","procedimientos"),
        ("otroservicio","otrosServicios"),("otrosservicio","otrosServicios"),
        ("otro_servicio","otrosServicios"),("medicamento","medicamentos"),
        ("usuario","usuarios"),
    ]:
        if alias in nombre: return canon
    return nombre

@app.route("/api/upload-nota-tecnica", methods=["POST"])
@login_required
def upload_nota_tecnica():
    if "file" not in request.files:
        return jsonify({"error": "No se recibió archivo"}), 400
    file = request.files["file"]
    if not file.filename.endswith((".xlsx",".xls")):
        return jsonify({"error": "Solo se aceptan archivos Excel (.xlsx)"}), 400
    tmp = _get_session_dir() / secure_filename(file.filename)
    file.save(str(tmp))
    try:
        metas = RIPSEvaluator.parsear_nota_tecnica(str(tmp))
        sd = _session_data()
        sd["metas"] = metas
        resumen = {prog: {act: v["meta"] for act, v in acts.items() if act != "__upc"}
                   for prog, acts in metas.items()}
        return jsonify({"ok": True, "metas": resumen, "programas": list(metas.keys())})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/set-metas", methods=["POST"])
@login_required
def set_metas():
    body = request.get_json()
    if not body: return jsonify({"error": "No se recibieron datos"}), 400
    sd = _session_data()
    sd["metas"] = body.get("metas", {})
    sd["info_acta"] = body.get("info_acta", {})
    return jsonify({"ok": True})

@app.route("/api/evaluar", methods=["POST"])
@login_required
def evaluar():
    sd   = _session_data()
    body = request.get_json() or {}
    if "info_acta" in body: sd["info_acta"] = body["info_acta"]
    if "metas" in body: sd["metas"] = body["metas"]
    periodo_str = sd.get("info_acta",{}).get("periodo_fin","")
    periodo_ref = None
    if periodo_str:
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try: periodo_ref = datetime.datetime.strptime(periodo_str, fmt).date(); break
            except: pass
    ev = RIPSEvaluator(periodo_ref=periodo_ref)
    for nombre, data in sd["archivos"].items():
        ev.cargar_archivo(nombre, data)
    metas = sd.get("metas", {})
    resultados = ev.evaluar(metas)
    resumen    = ev.resumen_acta(resultados)
    sd["resultados"] = resultados
    sd["resumen"]    = resumen
    total_e = sum(r["total_exigido"]    for r in resultados.values())
    total_r = sum(r["total_reconocido"] for r in resultados.values())
    total_d = sum(r["total_descuento"]  for r in resultados.values())
    return jsonify({"ok": True, "resultados": resultados, "resumen": resumen,
                    "totales": {"exigido": total_e, "reconocido": total_r, "descuento": total_d,
                                "pct": total_r/total_e if total_e else 1.0}})

@app.route("/api/generar-acta", methods=["POST"])
@login_required
def generar_acta():
    sd   = _session_data()
    body = request.get_json() or {}
    if not sd.get("resultados"):
        return jsonify({"error": "Primero ejecute la evaluación"}), 400
    info = sd.get("info_acta", {})
    info.update(body.get("info_acta", {}))
    programas_acta = []
    for prog_id, r in sd["resultados"].items():
        programas_acta.append({"id": prog_id, "nombre": r["nombre_acta"],
                                "exigido": r["total_exigido"], "reconocido": r["total_reconocido"],
                                "descuento": r["total_descuento"], "pct": r["pct_cumplimiento"]})
    total_e = sum(p["exigido"]    for p in programas_acta)
    total_r = sum(p["reconocido"] for p in programas_acta)
    total_d = sum(p["descuento"]  for p in programas_acta)
    datos_acta = {"programas": programas_acta, "total_exigido": total_e,
                  "total_reconocido": total_r, "total_descuento": total_d}
    try:
        import sys as _sys
        _sys.path.insert(0, str(BASE_DIR.parent))
        from evaluador_3280 import generar_acta_excel
    except ImportError:
        # Fallback: generador básico sin openpyxl extra (solo en Vercel sin el módulo padre)
        try:
            from acta_simple import generar_acta_excel
        except ImportError:
            return jsonify({"error": "Módulo generador no disponible en este entorno"}), 500
    out_path = _get_session_dir() / "ACTA_EVALUACION.xlsx"
    generar_acta_excel(datos_acta, info, str(out_path))
    # Incrementar contador de actas del IPS
    empresa = info.get("empresa","")
    if empresa:
        ips_list = _load_ips()
        for ips in ips_list:
            if ips["nombre"] == empresa:
                ips["num_actas"] = ips.get("num_actas",0) + 1
                break
        _save_ips(ips_list)
    return send_from_directory(str(out_path.parent), out_path.name, as_attachment=True,
                               download_name=f"ACTA_{info.get('empresa','IPS')}_{info.get('periodo','')}.xlsx")

@app.route("/api/estado")
@login_required
def estado():
    sd = _session_data()
    return jsonify({"archivos_cargados": list(sd["archivos"].keys()),
                    "tiene_metas": bool(sd.get("metas")),
                    "tiene_resultados": bool(sd.get("resultados")),
                    "registros": {k: len(v) for k,v in sd["archivos"].items()}})

def _load_config_mutable():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)

def _save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

@app.route("/api/config/actividad", methods=["POST"])
@login_required
def update_actividad():
    user = _get_current_user()
    if user.rol not in ["admin", "evaluador"]:
        return jsonify({"error": "Sin permisos"}), 403
    body = request.get_json() or {}
    act_id = body.get("act_id")
    if not act_id:
        return jsonify({"error": "act_id requerido"}), 400
    prog_id = body.get("prog_id")  # required only for new activities
    cfg = _load_config_mutable()
    is_new = act_id not in cfg.get("actividades_base", {})
    if is_new:
        if not prog_id:
            return jsonify({"error": "prog_id requerido para nueva actividad"}), 400
        if prog_id not in [p["id"] for p in cfg.get("programas", [])]:
            return jsonify({"error": f"Programa '{prog_id}' no existe"}), 400
        cfg.setdefault("actividades_base", {})[act_id] = {
            "cups": [], "finalidad": [], "aplica_a": [], "archivo": "consultas", "descripcion": act_id
        }
        # Add act_id to the program's activity list
        for p in cfg.get("programas", []):
            if p["id"] == prog_id:
                p.setdefault("actividades", [])
                if act_id not in p["actividades"]:
                    p["actividades"].append(act_id)
    act = cfg["actividades_base"][act_id]
    if "cups" in body:        act["cups"]        = body["cups"]
    if "finalidad" in body:   act["finalidad"]   = body["finalidad"]
    if "aplica_a" in body:    act["aplica_a"]    = body["aplica_a"]
    if "archivo" in body:     act["archivo"]     = body["archivo"]
    if "descripcion" in body: act["descripcion"] = body["descripcion"]
    _save_config(cfg)
    return jsonify({"ok": True, "created": is_new})

@app.route("/api/config/cursos-vida", methods=["POST"])
@login_required
def update_cursos_vida():
    user = _get_current_user()
    if user.rol != "admin":
        return jsonify({"error": "Sin permisos"}), 403
    body = request.get_json() or {}
    cfg = _load_config_mutable()
    cfg["cursos_de_vida"] = body.get("cursos_de_vida", cfg["cursos_de_vida"])
    _save_config(cfg)
    return jsonify({"ok": True})

@app.route("/api/config/finalidades", methods=["POST"])
@login_required
def update_finalidades():
    user = _get_current_user()
    if user.rol != "admin":
        return jsonify({"error": "Sin permisos"}), 403
    body = request.get_json() or {}
    cfg = _load_config_mutable()
    cfg["finalidades"] = body.get("finalidades", cfg.get("finalidades", {}))
    _save_config(cfg)
    return jsonify({"ok": True})

@app.route("/api/limpiar", methods=["POST"])
@login_required
def limpiar():
    sd = _session_data()
    sd.clear()
    sd.update({"archivos":{}, "metas":{}, "info_acta":{}, "resultados": None})
    return jsonify({"ok": True})

if __name__ == "__main__":
    print("\n🚀 Evaluador Res. 3280 v0.1 – DUSAKAWI EPSI")
    print("   Login: admin / admin123")
    print("   Abre tu navegador en: http://localhost:5050\n")
    app.run(debug=True, port=5050, host="0.0.0.0")
