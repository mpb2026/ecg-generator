# server.py
import os
import json
import logging
from logging.handlers import RotatingFileHandler
import sys
from typing import Optional, Any, Dict

import requests
from fastapi import FastAPI, HTTPException, File, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# -----------------------------
# Cargar .env
# -----------------------------
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET")

# -----------------------------
# Logging con rotación
# -----------------------------
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "server.log")

logger = logging.getLogger("ecg_backend")
logger.setLevel(logging.DEBUG)  # DEBUG en desarrollo; cambiar a INFO en staging/producción

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
console_handler.setFormatter(console_fmt)
logger.addHandler(console_handler)

file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(console_fmt)
logger.addHandler(file_handler)

# -----------------------------
# App FastAPI
# -----------------------------
app = FastAPI(title="ECG Cases API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # en producción restringir orígenes
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Pydantic models
# -----------------------------
class ECGAdvanced(BaseModel):
    iam: Optional[str] = "none"
    bundle: Optional[str] = "none"
    electrolytes: Optional[str] = "normal"
    specialRhythm: Optional[str] = "none"

class ECGConfig(BaseModel):
    gain: Optional[int] = 10
    rhythm: Optional[str] = "NSR"
    samples: Optional[int] = 2500
    advanced: Optional[ECGAdvanced] = ECGAdvanced()
    heartRate: Optional[int] = 70

class CaseIn(BaseModel):
    id: Any = Field(..., description="ID del caso (string o entero)")
    title: str
    description: Optional[str] = None
    diagnosis: Optional[str] = None
    explanation: Optional[str] = None
    ecgConfig: Optional[ECGConfig] = None
    ecg_image_url: Optional[str] = None

# -----------------------------
# Helpers Supabase REST
# -----------------------------
def redact_payload(payload: dict) -> dict:
    p = dict(payload)
    for k in ("password", "token", "service_role", "service_role_key"):
        if k in p:
            p[k] = "***REDACTED***"
    return p

def supabase_get(table: str, params: str = ""):
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("Supabase URL/KEY no configurados")
        raise HTTPException(status_code=500, detail="Supabase not configured")
    url = f"{SUPABASE_URL}/rest/v1/{table}{params}"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    resp = requests.get(url, headers=headers)
    logger.debug("Supabase GET url=%s status=%s", url, resp.status_code)
    logger.debug("Supabase GET body=%s", resp.text)
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        logger.error("Supabase GET failed url=%s status=%s body=%s", url, resp.status_code, resp.text)
        raise
    return resp.json()

def supabase_post(table: str, payload: dict):
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("Supabase URL/KEY no configurados")
        raise HTTPException(status_code=500, detail="Supabase not configured")
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    logger.debug("Supabase POST url=%s payload=%s", url, redact_payload(payload))
    resp = requests.post(url, headers=headers, data=json.dumps(payload))
    logger.debug("Supabase POST body=%s", resp.text)
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        logger.error("Supabase POST failed url=%s status=%s body=%s", url, resp.status_code, resp.text)
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()

# -----------------------------
# Exception handlers globales
# -----------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s: %s", request.method, request.url.path, str(exc))
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning("HTTPException %s %s status=%s detail=%s", request.method, request.url.path, exc.status_code, exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("Validation error on %s %s: %s", request.method, request.url.path, exc.errors())
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

# -----------------------------
# Endpoints
# -----------------------------
@app.get("/")
def root():
    return {"message": "Backend funcionando correctamente"}

@app.get("/cases")
def get_cases():
    try:
        return supabase_get("cases")
    except requests.HTTPError as e:
        logger.error("Error al obtener cases: %s", str(e))
        raise HTTPException(status_code=502, detail="Error fetching cases from Supabase")

@app.get("/cases/{case_id}")
def get_case(case_id: str):
    """
    Intento: primero como string (ej: 'B1'), luego como entero (ej: 1).
    Devuelve 404 si no existe.
    """
    # Intentar como string
    params_str = f"?id=eq.'{case_id}'"
    try:
        data = supabase_get("cases", params_str)
        if data:
            return data[0]
    except requests.HTTPError:
        logger.debug("Intento string falló para %s", case_id)

    # Intentar como número
    try:
        int_id = int(case_id)
        params_num = f"?id=eq.{int_id}"
        try:
            data2 = supabase_get("cases", params_num)
            if data2:
                return data2[0]
        except requests.HTTPError:
            logger.debug("Intento numérico falló para %s", case_id)
    except ValueError:
        logger.debug("case_id no convertible a int: %s", case_id)

    raise HTTPException(status_code=404, detail="Case not found")

@app.post("/cases")
def create_case(payload: CaseIn):
    try:
        result = supabase_post("cases", payload.dict())
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error creando case: %s", str(e))
        raise HTTPException(status_code=500, detail="Error creating case")

@app.post("/upload")
def upload_file(file: UploadFile = File(...)):
    """
    Subida de archivos a Supabase Storage usando la Service Role Key (solo servidor).
    """
    if not SERVICE_ROLE_KEY:
        logger.error("Service role key no configurada")
        raise HTTPException(status_code=500, detail="Service role key not configured")
    if not SUPABASE_BUCKET:
        logger.error("Supabase bucket no configurado")
        raise HTTPException(status_code=500, detail="Supabase bucket not configured")

    filename = file.filename
    url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{filename}"
    headers = {"Authorization": f"Bearer {SERVICE_ROLE_KEY}", "apikey": SERVICE_ROLE_KEY}
    files = {"file": (filename, file.file, file.content_type)}
    resp = requests.post(url, headers=headers, files=files)
    logger.debug("UPLOAD %s STATUS %s", url, resp.status_code)
    logger.debug("UPLOAD BODY %s", resp.text)
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        logger.error("Upload error: %s", resp.text)
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return {"status": "ok", "result": resp.json()}
