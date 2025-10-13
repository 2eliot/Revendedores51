#!/usr/bin/env python3
"""
Script de inicio rápido para la API de Conexión de Revendedores51
Facilita el inicio y gestión de la API con opciones adicionales
"""

import os
import sys
import subprocess
import time
import requests
import threading
from datetime import datetime

def print_banner():
    """Muestra el banner de inicio"""
    print("=" * 70)
    print("🔗 API DE CONEXIÓN - REVENDEDORES51")
    print("=" * 70)
    print("📅 Fecha:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("🌐 Puerto: 5002")
    print("📍 URL: http://localhost:5002")
    print("🔗 Web: https://revendedores51.onrender.com/")
    print("=" * 70)

def check_dependencies():
    """Verifica que las dependencias estén instaladas"""
    print("🔍 Verificando dependencias...")
    
    required_packages = ['flask', 'requests', 'werkzeug']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"   ✅ {package}")
        except ImportError:
            missing_packages.append(package)
            print(f"   ❌ {package} - FALTANTE")
    
    if missing_packages:
        print(f"\n⚠️  Faltan dependencias: {', '.join(missing_packages)}")
        print("💡 Ejecuta: pip install " + " ".join(missing_packages))
        return False
    
    print("✅ Todas las dependencias están instaladas\n")
    return True

def check_files():
    """Verifica que los archivos necesarios existan"""
    print("📁 Verificando archivos...")
    
    required_files = [
        'connection_api.py', 
        'test_connection_api.py', 
        'pin_manager.py',
        'CONNECTION_API_GUIDE.md'
    ]
    missing_files = []
    
    for file in required_files:
        if os.path.exists(file):
            print(f"   ✅ {file}")
        else:
            missing_files.append(file)
            print(f"   ❌ {file} - FALTANTE")
    
    if missing_files:
        print(f"\n⚠️  Faltan archivos: {', '.join(missing_files)}")
        return False
    
    print("✅ Todos los archivos están presentes\n")
    return True

def check_database():
    """Verifica que la base de datos exista"""
    print("🗄️  Verificando base de datos...")
    
    db_path = os.environ.get('DATABASE_PATH', 'usuarios.db')
    
    if os.path.exists(db_path):
        print(f"   ✅ Base de datos encontrada: {db_path}")
        
        # Verificar tamaño de la base de datos
        size = os.path.getsize(db_path)
        if size > 0:
            print(f"   📊 Tamaño: {size:,} bytes")
        else:
            print("   ⚠️  Base de datos vacía")
        
        return True
    else:
        print(f"   ❌ Base de datos no encontrada: {db_path}")
        print("   💡 La base de datos se creará automáticamente al iniciar la API")
        return True  # No es crítico, se crea automáticamente

def wait_for_api(url="http://localhost:5002/api/connection/health", timeout=30):
    """Espera a que la API esté disponible"""
    print("⏳ Esperando a que la API esté lista...")
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                print("✅ API lista y funcionando!")
                return True
        except:
            pass
        
        print("   ⏳ Esperando...", end="\r")
        time.sleep(1)
    
    print("❌ Timeout: La API no respondió en el tiempo esperado")
    return False

def test_api_quick():
    """Ejecuta una prueba rápida de la API"""
    print("\n🧪 Ejecutando prueba rápida...")
    
    try:
        # Health check
        response = requests.get("http://localhost:5002/api/connection/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Health Check: {data['message']}")
            print(f"   📊 Versión: {data['version']}")
            print(f"   🕒 Timestamp: {data['timestamp']}")
            
            # Probar obtener paquetes
            response = requests.get("http://localhost:5002/api/connection/packages", timeout=5)
            if response.status_code == 200:
                paquetes = response.json()['data']
                print(f"   ✅ Paquetes disponibles: {len(paquetes)}")
            
            # Probar obtener stock
            response = requests.get("http://localhost:5002/api/connection/stock", timeout=5)
            if response.status_code == 200:
                stock = response.json()['data']
                total_pines = sum(stock.values())
                print(f"   ✅ Stock total de pines: {total_pines}")
            
            print("✅ Prueba rápida completada exitosamente!")
            return True
        else:
            print(f"❌ Error en health check: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error en prueba rápida: {e}")
        return False

def start_api():
    """Inicia la API en un proceso separado"""
    print("🚀 Iniciando API de Conexión...")
    
    try:
        # Iniciar la API en un proceso separado
        process = subprocess.Popen(
            [sys.executable, 'connection_api.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Esperar un poco para que inicie
        time.sleep(3)
        
        # Verificar si el proceso sigue corriendo
        if process.poll() is None:
            print("✅ API de Conexión iniciada correctamente")
            return process
        else:
            stdout, stderr = process.communicate()
            print("❌ Error al iniciar la API de Conexión:")
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
            return None
            
    except Exception as e:
        print(f"❌ Error al iniciar la API: {e}")
        return None

def show_menu():
    """Muestra el menú de opciones"""
    print("\n📋 OPCIONES DISPONIBLES:")
    print("1. 🚀 Iniciar API de Conexión")
    print("2. 🧪 Ejecutar pruebas completas")
    print("3. 🔍 Ejecutar pruebas individuales")
    print("4. 📊 Monitorear API (si está corriendo)")
    print("5. 📖 Mostrar endpoints disponibles")
    print("6. 🌐 Abrir documentación")
    print("7. 👤 Crear usuario de prueba")
    print("8. 📋 Mostrar ejemplos de uso")
    print("0. ❌ Salir")

def show_endpoints():
    """Muestra los endpoints disponibles"""
    print("\n📡 ENDPOINTS DE LA API DE CONEXIÓN:")
    endpoints = [
        ("GET", "/api/connection/health", "Verificar estado de la API"),
        ("POST", "/api/connection/login", "Autenticación de usuario"),
        ("GET", "/api/connection/balance/{user_id}", "Obtener saldo de usuario"),
        ("GET", "/api/connection/packages", "Obtener paquetes disponibles"),
        ("POST", "/api/connection/purchase", "Comprar PIN con descuento automático"),
        ("GET", "/api/connection/stock", "Obtener estado del stock"),
        ("GET", "/api/connection/user/{user_id}/transactions", "Obtener transacciones de usuario"),
    ]
    
    for method, endpoint, description in endpoints:
        print(f"   {method:4} {endpoint:45} - {description}")

def show_usage_examples():
    """Muestra ejemplos de uso"""
    print("\n💡 EJEMPLOS DE USO:")
    
    print("\n🔐 1. Autenticación (cURL):")
    print("curl -X POST http://localhost:5002/api/connection/login \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d '{\"email\":\"test@ejemplo.com\",\"password\":\"test123\"}'")
    
    print("\n💰 2. Verificar saldo (cURL):")
    print("curl http://localhost:5002/api/connection/balance/123")
    
    print("\n🛒 3. Comprar PIN (cURL):")
    print("curl -X POST http://localhost:5002/api/connection/purchase \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d '{\"user_id\":123,\"package_id\":1,\"quantity\":1}'")
    
    print("\n🐍 4. Ejemplo en Python:")
    print("import requests")
    print("response = requests.post('http://localhost:5002/api/connection/login',")
    print("                       json={'email': 'test@ejemplo.com', 'password': 'test123'})")
    print("user_data = response.json()['data']")
    print("print(f'Saldo: ${user_data[\"balance\"]:.2f}')")

def create_test_user():
    """Guía para crear usuario de prueba"""
    print("\n👤 CREAR USUARIO DE PRUEBA:")
    print("=" * 50)
    print("Para que las pruebas funcionen correctamente, necesitas:")
    print()
    print("1. 🌐 Ir a: https://revendedores51.onrender.com/")
    print("2. 📝 Registrar un usuario con:")
    print("   • Email: test@ejemplo.com")
    print("   • Contraseña: test123")
    print("   • Nombre: Test")
    print("   • Apellido: Usuario")
    print("   • Teléfono: 1234567890")
    print()
    print("3. 💰 Agregar saldo desde el panel de administración:")
    print("   • Iniciar sesión como admin")
    print("   • Ir a la sección de administración")
    print("   • Agregar $10.00 al usuario de prueba")
    print()
    print("4. 🎯 Agregar algunos PINs al stock:")
    print("   • Agregar PINs para el paquete ID 1 (110 💎)")
    print("   • Esto permitirá probar las compras")
    print()
    print("✅ Una vez hecho esto, las pruebas funcionarán correctamente")

def monitor_api():
    """Monitorea el estado de la API"""
    print("\n📊 MONITOREANDO API DE CONEXIÓN (Presiona Ctrl+C para detener)")
    print("=" * 60)
    
    try:
        while True:
            try:
                start_time = time.time()
                response = requests.get("http://localhost:5002/api/connection/health", timeout=5)
                end_time = time.time()
                
                response_time = (end_time - start_time) * 1000
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                if response.status_code == 200:
                    data = response.json()
                    service = data.get('service', 'API')
                    print(f"[{timestamp}] ✅ {service} OK - {response_time:.2f}ms")
                else:
                    print(f"[{timestamp}] ⚠️  Status: {response.status_code}")
                    
            except Exception as e:
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}] ❌ Error: {e}")
            
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n📊 Monitoreo detenido")

def open_documentation():
    """Abre la documentación"""
    import webbrowser
    
    print("📖 Abriendo documentación...")
    
    # Verificar si existe el archivo de documentación
    if os.path.exists('CONNECTION_API_GUIDE.md'):
        try:
            # En Windows, usar notepad
            if os.name == 'nt':
                subprocess.run(['notepad', 'CONNECTION_API_GUIDE.md'])
            # En macOS, usar open
            elif sys.platform == 'darwin':
                subprocess.run(['open', 'CONNECTION_API_GUIDE.md'])
            # En Linux, usar el editor por defecto
            else:
                subprocess.run(['xdg-open', 'CONNECTION_API_GUIDE.md'])
            
            print("✅ Documentación abierta")
        except Exception as e:
            print(f"❌ Error al abrir documentación: {e}")
            print("💡 Abre manualmente el archivo: CONNECTION_API_GUIDE.md")
    else:
        print("❌ Archivo de documentación no encontrado: CONNECTION_API_GUIDE.md")

def main():
    """Función principal"""
    print_banner()
    
    # Verificaciones iniciales
    if not check_dependencies():
        return
    
    if not check_files():
        return
    
    check_database()
    
    api_process = None
    
    try:
        while True:
            show_menu()
            
            try:
                opcion = input("\n👉 Selecciona una opción: ").strip()
            except KeyboardInterrupt:
                print("\n👋 ¡Hasta luego!")
                break
            
            if opcion == "0":
                print("👋 ¡Hasta luego!")
                break
                
            elif opcion == "1":
                if api_process and api_process.poll() is None:
                    print("⚠️  La API de Conexión ya está corriendo")
                else:
                    api_process = start_api()
                    if api_process and wait_for_api():
                        test_api_quick()
                        
            elif opcion == "2":
                print("🧪 Ejecutando pruebas completas...")
                subprocess.run([sys.executable, 'test_connection_api.py'])
                
            elif opcion == "3":
                print("🧪 Ejecutando pruebas individuales...")
                print("💡 Usa Ctrl+C para detener las pruebas en cualquier momento")
                subprocess.run([sys.executable, 'test_connection_api.py'])
                
            elif opcion == "4":
                monitor_api()
                
            elif opcion == "5":
                show_endpoints()
                
            elif opcion == "6":
                open_documentation()
                
            elif opcion == "7":
                create_test_user()
                
            elif opcion == "8":
                show_usage_examples()
                
            else:
                print("❌ Opción inválida")
            
            if opcion != "0":
                input("\n⏸️  Presiona Enter para continuar...")
    
    finally:
        # Limpiar procesos
        if api_process and api_process.poll() is None:
            print("\n🛑 Deteniendo API de Conexión...")
            api_process.terminate()
            try:
                api_process.wait(timeout=5)
                print("✅ API de Conexión detenida correctamente")
            except subprocess.TimeoutExpired:
                api_process.kill()
                print("⚠️  API de Conexión forzada a detenerse")

if __name__ == "__main__":
    main()
