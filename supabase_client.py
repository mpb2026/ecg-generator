import os
import requests
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env SIEMPRE desde la carpeta donde está este archivo
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# Debug para confirmar que las variables se cargan
print("SUPABASE_URL:", SUPABASE_URL)
print("SUPABASE_ANON_KEY:", SUPABASE_ANON_KEY[:10], "...")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise RuntimeError("ERROR: No se cargaron SUPABASE_URL o SUPABASE_ANON_KEY desde .env")

HEADERS = {
    "apikey": SUPABASE_ANON_KEY,
    "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    "Content-Type": "application/json"
}

def supabase_select(table: str):
    url = f"{SUPABASE_URL}/rest/v1/{table}?select=*"
    print("GET:", url)  # Debug
    response = requests.get(url, headers=HEADERS)
    print("STATUS:", response.status_code)  # Debug
    response.raise_for_status()
    return response.json()

def supabase_select_single(table: str, column: str, value: str):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{column}=eq.{value}&select=*"
    print("GET:", url)  # Debug
    response = requests.get(url, headers=HEADERS)
    print("STATUS:", response.status_code)  # Debug
    response.raise_for_status()
    data = response.json()
    return data[0] if data else None
