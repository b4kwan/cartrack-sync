import os
import requests
from datetime import datetime

# ==========================================
# KONFIGURASI CARTRACK & ODOO
# ==========================================
CARTRACK_USER = "PROY00001"
CARTRACK_TOKEN = "83e18c5e077615626fbc9c5f9566e5b6ae45c00a7b6fcfc6bd2562cdb86bd6d"
CARTRACK_BASE_URL = "https://fleetapi-id.cartrack.com/rest/vehicles"

ODOO_URL     = "https://proyekin.odoo.com"  
ODOO_DB      = "proyekin"                   
ODOO_USER    = "lucky@proyekin.co.id"  
Odoo_API_KEY = "0c43226f9769cde2ce5d92ac5993897e2876d19e"

def get_odoo_uid():
    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "service": "common",
            "method": "authenticate",
            "args": [ODOO_DB, ODOO_USER, Odoo_API_KEY, {}]
        },
        "id": 1
    }
    try:
        res = requests.post(f"{ODOO_URL}/jsonrpc", json=payload, timeout=15)
        return res.json().get("result")
    except Exception as e:
        print(f"Error Odoo Auth: {e}")
        return None

def main():
    print("Memulai sinkronisasi Cartrack ke Odoo via GitHub Actions (Debug Mode)...")
    
    headers = {
        "api-key": CARTRACK_TOKEN,
        "username": CARTRACK_USER,
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
    }

    # Ambil daftar kendaraan dari Cartrack
    res = requests.get(CARTRACK_BASE_URL, headers=headers, timeout=20)
    
    # Cetak Headers untuk keperluan debugging error 401
    print(f"HTTP Status Code: {res.status_code}")
    print(f"Response Headers: {dict(res.headers)}")
    
    if res.status_code != 200:
        print(f"Gagal mengambil data dari Cartrack. Respon: {res.text}")
        return

    vehicles = res.json()
    if isinstance(vehicles, dict):
        vehicles = vehicles.get("data", vehicles.get("vehicles", []))

    print(f"Berhasil terhubung! Ditemukan {len(vehicles)} kendaraan.")

if __name__ == "__main__":
    main()
