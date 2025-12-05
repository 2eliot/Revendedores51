#!/usr/bin/env python3
"""
Script para probar la extracción de pin del cliente actualizado
"""

from inefable_api_client import get_inefable_client

def test_pin_extraction():
    """Prueba la extracción de pin con el cliente actualizado"""
    
    print("🧪 Probando extracción de pin con cliente actualizado...")
    print("-" * 50)
    
    # Obtener cliente
    client = get_inefable_client()
    
    # Probar solicitud de pin
    print("Solicitando pin para monto_id 1 (110 💎)...")
    result = client.request_pin(1)
    
    print(f"Status: {result.get('status')}")
    print(f"Message: {result.get('message', 'N/A')}")
    
    if result.get('status') == 'success':
        pin_code = result.get('pin_code')
        print(f"✅ PIN EXTRAÍDO EXITOSAMENTE: {pin_code}")
        print(f"Monto ID: {result.get('monto_id')}")
        print(f"Fuente: {result.get('source')}")
        print(f"Timestamp: {result.get('timestamp')}")
    else:
        print(f"❌ ERROR: {result.get('message')}")
        print(f"Error Type: {result.get('error_type')}")
        
        # Mostrar respuesta raw si está disponible
        if result.get('raw_response'):
            print("Raw Response:")
            print(result.get('raw_response')[:500] + "...")
    
    print("-" * 50)
    return result

if __name__ == "__main__":
    test_pin_extraction()
