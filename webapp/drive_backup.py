"""
Backup automático a Google Drive via Service Account.

Variables de entorno requeridas:
  GOOGLE_DRIVE_CREDENTIALS  — JSON completo de la service account (como string)
  GOOGLE_DRIVE_FOLDER_ID    — ID de la carpeta de Drive compartida con la service account
"""
import json, os, io, datetime

_service = None

def _get_service():
    global _service
    if _service:
        return _service
    creds_json = os.environ.get("GOOGLE_DRIVE_CREDENTIALS")
    if not creds_json:
        return None
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        info = json.loads(creds_json)
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/drive.file"]
        )
        _service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return _service
    except Exception as e:
        print(f"[drive_backup] Error init: {e}")
        return None


def _folder_id():
    return os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")


def _find_file(service, folder_id, name):
    """Devuelve el ID del archivo si ya existe en la carpeta."""
    q = f"name='{name}' and '{folder_id}' in parents and trashed=false"
    res = service.files().list(q=q, fields="files(id,name)").execute()
    files = res.get("files", [])
    return files[0]["id"] if files else None


def subir_json(nombre_archivo: str, datos, subfolder: str | None = None) -> bool:
    """
    Sube o actualiza un JSON en Drive.
    nombre_archivo: ej. 'actas_2026-09-02.json'
    datos: dict o list serializable
    subfolder: nombre de subcarpeta dentro de la carpeta principal (se crea si no existe)
    Devuelve True si se subió correctamente.
    """
    service = _get_service()
    folder_id = _folder_id()
    if not service or not folder_id:
        return False
    try:
        # Resolver subcarpeta
        target_folder = folder_id
        if subfolder:
            target_folder = _get_or_create_subfolder(service, folder_id, subfolder)

        content = json.dumps(datos, ensure_ascii=False, indent=2).encode("utf-8")
        media = _make_media(content)
        existing_id = _find_file(service, target_folder, nombre_archivo)

        if existing_id:
            service.files().update(fileId=existing_id, media_body=media).execute()
        else:
            meta = {"name": nombre_archivo, "parents": [target_folder],
                    "mimeType": "application/json"}
            service.files().create(body=meta, media_body=media, fields="id").execute()
        return True
    except Exception as e:
        print(f"[drive_backup] Error subir {nombre_archivo}: {e}")
        return False


def _get_or_create_subfolder(service, parent_id: str, name: str) -> str:
    q = f"name='{name}' and '{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    res = service.files().list(q=q, fields="files(id)").execute()
    files = res.get("files", [])
    if files:
        return files[0]["id"]
    meta = {"name": name, "parents": [parent_id],
            "mimeType": "application/vnd.google-apps.folder"}
    f = service.files().create(body=meta, fields="id").execute()
    return f["id"]


def _make_media(content: bytes):
    from googleapiclient.http import MediaIoBaseUpload
    buf = io.BytesIO(content)
    return MediaIoBaseUpload(buf, mimetype="application/json", resumable=False)


def leer_json(nombre_archivo: str, subfolder: str | None = None):
    """
    Lee un JSON desde Drive. Devuelve el objeto deserializado o None si no existe/falla.
    """
    service = _get_service()
    folder_id = _folder_id()
    if not service or not folder_id:
        return None
    try:
        target_folder = folder_id
        if subfolder:
            target_folder = _get_or_create_subfolder(service, folder_id, subfolder)
        file_id = _find_file(service, target_folder, nombre_archivo)
        if not file_id:
            return None
        from googleapiclient.http import MediaIoBaseDownload
        buf = io.BytesIO()
        req = service.files().get_media(fileId=file_id)
        downloader = MediaIoBaseDownload(buf, req)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        buf.seek(0)
        return json.loads(buf.read().decode("utf-8"))
    except Exception as e:
        print(f"[drive_backup] Error leer {nombre_archivo}: {e}")
        return None


def disponible() -> bool:
    return bool(os.environ.get("GOOGLE_DRIVE_CREDENTIALS")) and bool(_folder_id())
