import requests
import json
import time

# Configuración de la API
API_BASE_URL = "http://localhost:5001"

def print_separator(title):
    """Imprime un separador visual"""
    print("\n" + "="*60)
    print(f"🧪 {title}")
    print("="*60)

def test_health():
    """Prueba el endpoint de salud"""
    print_separator("PRUEBA DE SALUD DE LA API")
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/health")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_crear_usuario():
    """Prueba crear un nuevo usuario"""
    print_separator("CREAR NUEVO USUARIO")
    
    usuario_data = {
        "nombre": "Juan",
        "apellido": "Pérez",
        "telefono": "+58412-1234567",
        "correo": "juan.perez@test.com",
        "contraseña": "password123"
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/usuarios",
            json=usuario_data,
            headers={'Content-Type': 'application/json'}
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        
        if response.status_code == 201:
            return response.json()['data']['id']
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_login(correo, contraseña):
    """Prueba el login de usuario"""
    print_separator("LOGIN DE USUARIO")
    
    login_data = {
        "correo": correo,
        "contraseña": contraseña
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/login",
            json=login_data,
            headers={'Content-Type': 'application/json'}
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_obtener_usuarios():
    """Prueba obtener todos los usuarios"""
    print_separator("OBTENER TODOS LOS USUARIOS")
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/usuarios")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_obtener_usuario(user_id):
    """Prueba obtener un usuario específico"""
    print_separator(f"OBTENER USUARIO ID: {user_id}")
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/usuarios/{user_id}")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_actualizar_saldo(user_id, nuevo_saldo):
    """Prueba actualizar el saldo de un usuario"""
    print_separator(f"ACTUALIZAR SALDO USUARIO ID: {user_id}")
    
    saldo_data = {
        "saldo": nuevo_saldo
    }
    
    try:
        response = requests.put(
            f"{API_BASE_URL}/api/usuarios/{user_id}/saldo",
            json=saldo_data,
            headers={'Content-Type': 'application/json'}
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_obtener_paquetes():
    """Prueba obtener todos los paquetes"""
    print_separator("OBTENER PAQUETES DISPONIBLES")
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/paquetes")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_actualizar_precio_paquete(paquete_id, nuevo_precio):
    """Prueba actualizar el precio de un paquete"""
    print_separator(f"ACTUALIZAR PRECIO PAQUETE ID: {paquete_id}")
    
    precio_data = {
        "precio": nuevo_precio
    }
    
    try:
        response = requests.put(
            f"{API_BASE_URL}/api/paquetes/{paquete_id}/precio",
            json=precio_data,
            headers={'Content-Type': 'application/json'}
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_obtener_stock():
    """Prueba obtener el stock de pines"""
    print_separator("OBTENER STOCK DE PINES")
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/stock")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_agregar_pin():
    """Prueba agregar un pin al stock"""
    print_separator("AGREGAR PIN AL STOCK")
    
    pin_data = {
        "monto_id": 1,
        "pin_codigo": "TEST-PIN-12345"
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/pines",
            json=pin_data,
            headers={'Content-Type': 'application/json'}
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        return response.status_code == 201
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_obtener_transacciones():
    """Prueba obtener todas las transacciones"""
    print_separator("OBTENER TODAS LAS TRANSACCIONES")
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/transacciones")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_obtener_transacciones_usuario(user_id):
    """Prueba obtener transacciones de un usuario específico"""
    print_separator(f"OBTENER TRANSACCIONES USUARIO ID: {user_id}")
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/usuarios/{user_id}/transacciones")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def run_all_tests():
    """Ejecuta todas las pruebas de la API"""
    print("🚀 INICIANDO PRUEBAS COMPLETAS DE LA API")
    print("⚠️  Asegúrate de que la API esté corriendo en http://localhost:5001")
    
    # Esperar un momento para que el usuario pueda leer
    time.sleep(2)
    
    results = []
    
    # 1. Prueba de salud
    results.append(("Health Check", test_health()))
    
    # 2. Crear usuario
    user_id = test_crear_usuario()
    results.append(("Crear Usuario", user_id is not None))
    
    if user_id:
        # 3. Login
        results.append(("Login Usuario", test_login("juan.perez@test.com", "password123")))
        
        # 4. Obtener usuario específico
        results.append(("Obtener Usuario", test_obtener_usuario(user_id)))
        
        # 5. Actualizar saldo
        results.append(("Actualizar Saldo", test_actualizar_saldo(user_id, 50.00)))
        
        # 6. Obtener transacciones del usuario
        results.append(("Transacciones Usuario", test_obtener_transacciones_usuario(user_id)))
    
    # 7. Obtener todos los usuarios
    results.append(("Obtener Usuarios", test_obtener_usuarios()))
    
    # 8. Obtener paquetes
    results.append(("Obtener Paquetes", test_obtener_paquetes()))
    
    # 9. Actualizar precio de paquete
    results.append(("Actualizar Precio", test_actualizar_precio_paquete(1, 0.75)))
    
    # 10. Obtener stock
    results.append(("Obtener Stock", test_obtener_stock()))
    
    # 11. Agregar pin
    results.append(("Agregar Pin", test_agregar_pin()))
    
    # 12. Obtener transacciones
    results.append(("Obtener Transacciones", test_obtener_transacciones()))
    
    # Mostrar resumen
    print_separator("RESUMEN DE PRUEBAS")
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✅ PASÓ" if result else "❌ FALLÓ"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n📊 RESULTADOS FINALES:")
    print(f"   ✅ Pruebas exitosas: {passed}")
    print(f"   ❌ Pruebas fallidas: {failed}")
    print(f"   📈 Porcentaje de éxito: {(passed/(passed+failed)*100):.1f}%")

def test_individual():
    """Permite ejecutar pruebas individuales"""
    print("🧪 PRUEBAS INDIVIDUALES DE LA API")
    print("Selecciona qué prueba quieres ejecutar:")
    print("1. Health Check")
    print("2. Crear Usuario")
    print("3. Login")
    print("4. Obtener Usuarios")
    print("5. Obtener Paquetes")
    print("6. Obtener Stock")
    print("7. Agregar Pin")
    print("8. Obtener Transacciones")
    print("9. Ejecutar todas las pruebas")
    print("0. Salir")
    
    while True:
        try:
            opcion = input("\n👉 Ingresa el número de la opción: ").strip()
            
            if opcion == "0":
                print("👋 ¡Hasta luego!")
                break
            elif opcion == "1":
                test_health()
            elif opcion == "2":
                test_crear_usuario()
            elif opcion == "3":
                correo = input("Correo: ").strip()
                contraseña = input("Contraseña: ").strip()
                test_login(correo, contraseña)
            elif opcion == "4":
                test_obtener_usuarios()
            elif opcion == "5":
                test_obtener_paquetes()
            elif opcion == "6":
                test_obtener_stock()
            elif opcion == "7":
                test_agregar_pin()
            elif opcion == "8":
                test_obtener_transacciones()
            elif opcion == "9":
                run_all_tests()
                break
            else:
                print("❌ Opción inválida. Intenta de nuevo.")
                
        except KeyboardInterrupt:
            print("\n👋 ¡Hasta luego!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        run_all_tests()
    else:
        test_individual()
