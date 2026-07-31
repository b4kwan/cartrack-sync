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

def find_vehicle_id(uid, reg_no):
    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "service": "object",
            "method": "execute_kw",
            "args": [
                ODOO_DB, uid, Odoo_API_KEY,
                "fleet.vehicle", "search",
                [[["name", "ilike", reg_no]]]
            ]
        },
        "id": 2
    }
    try:
        res = requests.post(f"{ODOO_URL}/jsonrpc", json=payload, timeout=15).json()
        result = res.get("result", [])
        return result[0] if result else None
    except Exception:
        return None

def create_odometer(uid, vehicle_id, value, date_str):
    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "service": "object",
            "method": "execute_kw",
            "args": [
                ODOO_DB, uid, Odoo_API_KEY,
                "fleet.vehicle.odometer", "create",
                [{
                    "vehicle_id": vehicle_id,
                    "value": float(value),
                    "date": date_str
                }]
            ]
        },
        "id": 3
    }
    try:
        res = requests.post(f"{ODOO_URL}/jsonrpc", json=payload, timeout=15).json()
        return not bool(res.get("error"))
    except Exception:
        return False

def main():
    print("Memulai sinkronisasi Cartrack ke Odoo via GitHub Actions...")
    
    # Menggunakan Header Token langsung
    headers = {
        "Authorization": f"Token {CARTRACK_TOKEN}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
    }

    # 1. Ambil daftar kendaraan dari Cartrack
    res = requests.get(CARTRACK_BASE_URL, headers=headers, timeout=20)
    if res.status_code != 200:
        print(f"Gagal mengambil data dari Cartrack. Status: {res.status_code}, Respon: {res.text}")
        return

    vehicles = res.json()
    if isinstance(vehicles, dict):
        vehicles = vehicles.get("data", vehicles.get("vehicles", []))

    print(f"Ditemukan {len(vehicles)} kendaraan di Cartrack. Menghubungkan ke Odoo...")
    uid = get_odoo_uid()
    if not uid:
        print("Gagal terautentikasi ke Odoo.")
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    success_count = 0

    # 2. Iterasi per kendaraan untuk menarik odometer & lempar ke Odoo
    for v in vehicles:
        reg = v.get("registration")
        if not reg:
            continue

        odo_url = f"{CARTRACK_BASE_URL}/{reg}/odometer"
        odo_res = requests.get(odo_url, headers=headers, timeout=15)
        
        if odo_res.status_code == 200:
            odo_data = odo_res.json()
            val = odo_data.get("odometer", odo_data.get("value", odo_data.get("distance", 0)))
            
            vehicle_id = find_vehicle_id(uid, reg)
            if vehicle_id:
                sukses = create_odometer(uid, vehicle_id, val, today_str)
                if sukses:
                    print(f"✅ Sukses: [{reg}] -> Odometer: {val}")
                    success_count += 1
                else:
                    print(f"❌ Gagal simpan ke Odoo untuk kendaraan: {reg}")
            else:
                print(f"⚠️ Mobil [{reg}] tidak ditemukan di sistem Odoo.")
        else:
            print(f"❌ Gagal tarik odometer {reg}")

    print(f"Sinkronisasi selesai! Total {success_count} data berhasil dimasukkan ke Odoo.")

if __name__ == "__main__":
    main()
