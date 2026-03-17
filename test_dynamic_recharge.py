#!/usr/bin/env python3
"""
Test de endpoints /api/catalog/active y /api/recharge/dynamic
Ejecutar desde el VPS en /home/apps/web-a-inefablestore o web-b-revendedores
Lee WEBB_API_KEY del entorno o del .env
"""
import os
import sys
import json
import requests

# --- Config ---
# Revendedores51 corre en puerto 5001 en el mismo VPS
REVENDEDORES_URL = os.environ.get("REVENDEDORES_BASE_URL", "http://127.0.0.1:5001")
API_KEY = os.environ.get("REVENDEDORES_API_KEY") or os.environ.get("WEBB_API_KEY") or ""

PLAYER_ID = "825999694838"

def sep(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def test_catalog():
    """Test GET /api/catalog/active"""
    sep("1. TEST /api/catalog/active")
    url = f"{REVENDEDORES_URL}/api/catalog/active"
    print(f"GET {url}")
    print(f"API_KEY: {API_KEY[:4]}...{API_KEY[-4:]}" if len(API_KEY) > 8 else f"API_KEY: '{API_KEY}' (VACIA O CORTA!)")

    try:
        r = requests.get(url, params={"api_key": API_KEY}, headers={"X-API-Key": API_KEY}, timeout=15)
        print(f"Status: {r.status_code}")
        data = r.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))

        if data.get("ok"):
            items = data.get("items", [])
            print(f"\nTotal paquetes activos: {len(items)}")
            for it in items:
                print(f"  - pkg_id={it['package_id']}  product_id={it.get('product_id')}  "
                      f"{it.get('product_name','')} / {it.get('name','')}")
            return items
        else:
            print(f"ERROR: {data.get('error')}")
            return []
    except Exception as e:
        print(f"EXCEPCION: {e}")
        return []

def test_recharge_dynamic(package_id, product_id=None):
    """Test POST /api/recharge/dynamic"""
    sep(f"2. TEST /api/recharge/dynamic (pkg={package_id}, player={PLAYER_ID})")
    url = f"{REVENDEDORES_URL}/api/recharge/dynamic"

    payload = {
        "api_key": API_KEY,
        "player_id": PLAYER_ID,
        "package_id": str(package_id),
    }
    if product_id:
        payload["product_id"] = str(product_id)

    print(f"POST {url}")
    print(f"Payload: {json.dumps(payload, ensure_ascii=False)}")
    print("Esperando respuesta (puede tardar hasta 30s)...")

    try:
        r = requests.post(url, data=payload, timeout=60)
        print(f"Status: {r.status_code}")
        data = r.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return data
    except Exception as e:
        print(f"EXCEPCION: {e}")
        return {}

def test_recharge_freefire():
    """Test POST /api/recharge/freefire_id (endpoint legacy)"""
    sep("3. TEST /api/recharge/freefire_id (legacy, verificacion de API key)")
    url = f"{REVENDEDORES_URL}/api/recharge/freefire_id"

    payload = {
        "api_key": API_KEY,
        "player_id": PLAYER_ID,
        "package_id": "1",
    }
    print(f"POST {url}")
    print(f"Payload: {json.dumps(payload, ensure_ascii=False)}")

    try:
        r = requests.post(url, data=payload, timeout=15)
        print(f"Status: {r.status_code}")
        data = r.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
        if r.status_code == 401:
            print("\n*** API KEY INVALIDA - Verifica que WEBB_API_KEY este configurada ***")
            print(f"    Key enviada: '{API_KEY}'")
        return data
    except Exception as e:
        print(f"EXCEPCION: {e}")
        return {}


if __name__ == "__main__":
    print("=" * 60)
    print("  TEST DE RECARGAS DINAMICAS - Revendedores51")
    print("=" * 60)
    print(f"URL: {REVENDEDORES_URL}")
    print(f"API_KEY configurada: {'SI' if API_KEY else 'NO (!!)'}")
    print(f"Player ID: {PLAYER_ID}")

    if not API_KEY:
        print("\n*** ERROR: No se encontro WEBB_API_KEY ni REVENDEDORES_API_KEY ***")
        print("Ejecuta: export WEBB_API_KEY='tu_clave_aqui'")
        print("O corre desde el directorio de la app con el .env correcto")
        sys.exit(1)

    # 1. Probar catalogo
    items = test_catalog()

    # 2. Probar recarga legacy (solo para verificar API key)
    ff_result = test_recharge_freefire()
    if ff_result.get("error") == "API key invalida" or (not ff_result.get("ok") and "key" in str(ff_result.get("error", "")).lower()):
        print("\n*** LA API KEY NO COINCIDE. Corrige WEBB_API_KEY antes de continuar. ***")
        sys.exit(1)

    # 3. Probar recarga dinamica si hay paquetes
    dyn_items = [it for it in items if it.get("product_id")]
    if dyn_items:
        pkg = dyn_items[0]
        print(f"\nUsando primer paquete dinamico: {pkg.get('name')} (pkg_id={pkg['package_id']})")

        confirm = input("\nEjecutar recarga de prueba? (s/n): ").strip().lower()
        if confirm == "s":
            test_recharge_dynamic(pkg["package_id"], pkg.get("product_id"))
        else:
            print("Recarga cancelada.")
    else:
        print("\nNo hay paquetes dinamicos en el catalogo.")
        if items:
            print("Solo hay paquetes Free Fire ID disponibles.")

    sep("FIN DE PRUEBAS")
