#!/usr/bin/env python3
"""
Script de pruebas para la API Simple de Revendedores51
Prueba el formato: /api.php?action=recarga&usuario=X&clave=X&tipo=recargaPinFreefire&monto=1&numero=0
"""

import requests
import urllib.parse
from datetime import datetime

# Configuración
API_BASE_URL = "http://localhost:5003"
TEST_USER_EMAIL = "test@ejemplo.com"
TEST_USER_PASSWORD = "test123"

def print_header(title):
    """Imprime un encabezado para las pruebas"""
    print("\n" + "=" * 60)
    print(f"🧪 {title}")
    print("=" * 60)

def print_test(test_name, success, message="", data=None):
    """Imprime el resultado de una prueba"""
    status = "✅" if success else "❌"
    print(f"{status} {test_name}")
    if message:
        print(f"   📝 {message}")
    if data:
        print(f"   📊 Respuesta: {data}")
    print()

def test_health_check():
    """Prueba el health check"""
    print_header("HEALTH CHECK")
    
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        
        if response.status_code == 200:
            data = response.json()
            print_test(
                "Health Check",
                True,
                f"API funcionando - Versión: {data.get('version', 'N/A')}",
                data
            )
            return True
        else:
            print_test("Health Check", False, f"Status Code: {response.status_code}")
            return False
            
    except Exception as e:
        print_test("Health Check", False, f"Error: {str(e)}")
        return False

def test_root_endpoint():
    """Prueba el endpoint raíz"""
    print_header("ENDPOINT RAÍZ")
    
    try:
        response = requests.get(f"{API_BASE_URL}/")
        
        if response.status_code == 200:
            data = response.json()
            print_test(
                "Endpoint Raíz",
                True,
                f"Información de la API obtenida",
                data
            )
            return True
        else:
            print_test("Endpoint Raíz", False, f"Status Code: {response.status_code}")
            return False
            
    except Exception as e:
        print_test("Endpoint Raíz", False, f"Error: {str(e)}")
        return False

def test_api_recarga(usuario=TEST_USER_EMAIL, clave=TEST_USER_PASSWORD, monto=1, numero=1):
    """Prueba el endpoint de recarga"""
    print_header(f"RECARGA PIN - Paquete {monto}, Cantidad {numero}")
    
    # Construir URL con parámetros
    params = {
        'action': 'recarga',
        'usuario': usuario,
        'clave': clave,
        'tipo': 'recargaPinFreefire',
        'monto': str(monto),
        'numero': str(numero)
    }
    
    url = f"{API_BASE_URL}/api.php?" + urllib.parse.urlencode(params)
    print(f"   🌐 URL: {url}")
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if response.status_code == 200 and data.get('status') == 'success':
            response_data = data.get('data', {})
            
            message = f"Usuario: {response_data.get('usuario')} - "
            message += f"Paquete: {response_data.get('paquete')} - "
            message += f"Precio: ${response_data.get('precio_total', 0):.2f} - "
            message += f"Nuevo saldo: ${response_data.get('saldo_nuevo', 0):.2f}"
            
            print_test("Recarga PIN", True, message, data)
            
            # Mostrar PIN(s) obtenido(s)
            if numero == 1:
                pin = response_data.get('pin', 'N/A')
                print(f"   🎯 PIN obtenido: {pin}")
            else:
                pines = response_data.get('pines', [])
                print(f"   🎯 PINs obtenidos ({len(pines)}):")
                for i, pin in enumerate(pines, 1):
                    print(f"      {i}. {pin}")
            
            return True
        else:
            error_msg = data.get('message', 'Error desconocido')
            print_test("Recarga PIN", False, f"Error: {error_msg}", data)
            return False
            
    except Exception as e:
        print_test("Recarga PIN", False, f"Error: {str(e)}")
        return False

def test_invalid_credentials():
    """Prueba con credenciales inválidas"""
    print_header("CREDENCIALES INVÁLIDAS")
    
    params = {
        'action': 'recarga',
        'usuario': 'invalid@test.com',
        'clave': 'wrongpassword',
        'tipo': 'recargaPinFreefire',
        'monto': '1',
        'numero': '1'
    }
    
    url = f"{API_BASE_URL}/api.php?" + urllib.parse.urlencode(params)
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if response.status_code == 401 and data.get('code') == '401':
            print_test("Credenciales Inválidas", True, "Error 401 manejado correctamente", data)
            return True
        else:
            print_test("Credenciales Inválidas", False, f"Respuesta inesperada: {data}")
            return False
            
    except Exception as e:
        print_test("Credenciales Inválidas", False, f"Error: {str(e)}")
        return False

def test_missing_parameters():
    """Prueba con parámetros faltantes"""
    print_header("PARÁMETROS FALTANTES")
    
    # Probar sin parámetro 'action'
    params = {
        'usuario': TEST_USER_EMAIL,
        'clave': TEST_USER_PASSWORD,
        'tipo': 'recargaPinFreefire',
        'monto': '1'
    }
    
    url = f"{API_BASE_URL}/api.php?" + urllib.parse.urlencode(params)
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if response.status_code == 400 and data.get('code') == '400':
            print_test("Parámetros Faltantes", True, "Error 400 manejado correctamente", data)
            return True
        else:
            print_test("Parámetros Faltantes", False, f"Respuesta inesperada: {data}")
            return False
            
    except Exception as e:
        print_test("Parámetros Faltantes", False, f"Error: {str(e)}")
        return False

def test_invalid_package():
    """Prueba con paquete inválido"""
    print_header("PAQUETE INVÁLIDO")
    
    params = {
        'action': 'recarga',
        'usuario': TEST_USER_EMAIL,
        'clave': TEST_USER_PASSWORD,
        'tipo': 'recargaPinFreefire',
        'monto': '99',  # Paquete que no existe
        'numero': '1'
    }
    
    url = f"{API_BASE_URL}/api.php?" + urllib.parse.urlencode(params)
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if response.status_code == 400 and data.get('code') == '400':
            print_test("Paquete Inválido", True, "Error 400 manejado correctamente", data)
            return True
        else:
            print_test("Paquete Inválido", False, f"Respuesta inesperada: {data}")
            return False
            
    except Exception as e:
        print_test("Paquete Inválido", False, f"Error: {str(e)}")
        return False

def test_post_method():
    """Prueba método POST (debe fallar)"""
    print_header("MÉTODO POST")
    
    try:
        response = requests.post(f"{API_BASE_URL}/api.php", json={
            'action': 'recarga',
            'usuario': TEST_USER_EMAIL,
            'clave': TEST_USER_PASSWORD,
            'tipo': 'recargaPinFreefire',
            'monto': '1'
        })
        
        data = response.json()
        
        if response.status_code == 405 and data.get('code') == '405':
            print_test("Método POST", True, "Error 405 manejado correctamente", data)
            return True
        else:
            print_test("Método POST", False, f"Respuesta inesperada: {data}")
            return False
            
    except Exception as e:
        print_test("Método POST", False, f"Error: {str(e)}")
        return False

def run_all_tests():
    """Ejecuta todas las pruebas"""
    print("🚀 INICIANDO PRUEBAS DE LA API SIMPLE")
    print(f"🌐 URL Base: {API_BASE_URL}")
    print(f"👤 Usuario de prueba: {TEST_USER_EMAIL}")
    print(f"🕒 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Contador de pruebas
    tests_passed = 0
    total_tests = 0
    
    # Lista de pruebas a ejecutar
    test_functions = [
        ("Health Check", test_health_check),
        ("Root Endpoint", test_root_endpoint),
        ("Recarga PIN (1 PIN)", lambda: test_api_recarga(monto=1, numero=1)),
        ("Recarga PIN (3 PINs)", lambda: test_api_recarga(monto=1, numero=3)),
        ("Credenciales Inválidas", test_invalid_credentials),
        ("Parámetros Faltantes", test_missing_parameters),
        ("Paquete Inválido", test_invalid_package),
        ("Método POST", test_post_method)
    ]
    
    # Ejecutar pruebas
    for test_name, test_function in test_functions:
        try:
            result = test_function()
            total_tests += 1
            if result:
                tests_passed += 1
        except Exception as e:
            print(f"❌ Error en prueba {test_name}: {str(e)}")
            total_tests += 1
    
    # Resumen final
    print_header("RESUMEN DE PRUEBAS")
    success_rate = (tests_passed / total_tests * 100) if total_tests > 0 else 0
    
    print(f"✅ Pruebas exitosas: {tests_passed}")
    print(f"❌ Pruebas fallidas: {total_tests - tests_passed}")
    print(f"📊 Total de pruebas: {total_tests}")
    print(f"🎯 Tasa de éxito: {success_rate:.1f}%")
    
    if success_rate >= 80:
        print("\n🎉 ¡API funcionando correctamente!")
        print("✅ La API simple está lista para usar")
    elif success_rate >= 60:
        print("\n⚠️  API funcionando con algunos problemas")
    else:
        print("\n🚨 API con problemas significativos")
    
    print("\n💡 EJEMPLOS DE USO:")
    print("🔗 URL de ejemplo:")
    example_url = f"{API_BASE_URL}/api.php?action=recarga&usuario={TEST_USER_EMAIL}&clave={TEST_USER_PASSWORD}&tipo=recargaPinFreefire&monto=1&numero=1"
    print(f"   {example_url}")
    
    print("\n🌐 Para producción, reemplaza localhost:5003 con:")
    print("   https://revendedores51.onrender.com/")
    
    return success_rate >= 80

def main():
    """Función principal"""
    print("🧪 TESTER DE API SIMPLE - REVENDEDORES51")
    print("=" * 60)
    
    # Verificar si la API está corriendo
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print("❌ La API no está respondiendo correctamente")
            print("💡 Asegúrate de que la API esté corriendo en http://localhost:5003")
            print("💡 Ejecuta: python simple_connection_api.py")
            return
    except requests.exceptions.RequestException:
        print("❌ No se puede conectar a la API")
        print("💡 Asegúrate de que la API esté corriendo en http://localhost:5003")
        print("💡 Ejecuta: python simple_connection_api.py")
        return
    
    # Ejecutar pruebas
    success = run_all_tests()
    
    if success:
        print("\n🎯 TODAS LAS PRUEBAS COMPLETADAS EXITOSAMENTE")
    else:
        print("\n⚠️  ALGUNAS PRUEBAS FALLARON")
        print("🔧 Revisa los errores y la configuración de la API")

if __name__ == "__main__":
    main()
