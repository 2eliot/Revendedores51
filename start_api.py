#!/usr/bin/env python3
"""
Script de inicio rápido para la API independiente
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
    print("🚀 API INDEPENDIENTE - SISTEMA DE REVENDEDORES")
    print("=" * 70)
    print("📅 Fecha:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("🌐 Puerto: 5001")
    print("📍 URL: http://localhost:5001")
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
    
    required_files = ['api_standalone.py', 'test_api.py']
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

def wait_for_api(url="http://localhost:5001/api/health", timeout=30):
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
        response = requests.get("http://localhost:5001/api/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Health Check: {data['message']}")
            print(f"   📊 Versión: {data['version']}")
            
            # Probar obtener paquetes
            response = requests.get("http://localhost:5001/api/paquetes", timeout=5)
            if response.status_code == 200:
                paquetes = response.json()['data']
                print(f"   ✅ Paquetes disponibles: {len(paquetes)}")
            
            # Probar obtener stock
            response = requests.get("http://localhost:5001/api/stock", timeout=5)
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
    print("🚀 Iniciando API...")
    
    try:
        # Iniciar la API en un proceso separado
        process = subprocess.Popen(
            [sys.executable, 'api_standalone.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Esperar un poco para que inicie
        time.sleep(2)
        
        # Verificar si el proceso sigue corriendo
        if process.poll() is None:
            print("✅ API iniciada correctamente")
            return process
        else:
            stdout, stderr = process.communicate()
            print("❌ Error al iniciar la API:")
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
            return None
            
    except Exception as e:
        print(f"❌ Error al iniciar la API: {e}")
        return None

def show_menu():
    """Muestra el menú de opciones"""
    print("\n📋 OPCIONES DISPONIBLES:")
    print("1. 🚀 Iniciar API")
    print("2. 🧪 Ejecutar pruebas completas")
    print("3. 🔍 Ejecutar pruebas individuales")
    print("4. 📊 Monitorear API (si está corriendo)")
    print("5. 📖 Mostrar endpoints disponibles")
    print("6. 🌐 Abrir en navegador")
    print("0. ❌ Salir")

def show_endpoints():
    """Muestra los endpoints disponibles"""
    print("\n📡 ENDPOINTS DISPONIBLES:")
    endpoints = [
        ("GET", "/api/health", "Verificar estado de la API"),
        ("GET", "/api/usuarios", "Obtener todos los usuarios"),
        ("POST", "/api/usuarios", "Crear nuevo usuario"),
        ("GET", "/api/usuarios/{id}", "Obtener usuario específico"),
        ("PUT", "/api/usuarios/{id}/saldo", "Actualizar saldo de usuario"),
        ("GET", "/api/usuarios/{id}/transacciones", "Obtener transacciones de usuario"),
        ("POST", "/api/login", "Autenticación de usuario"),
        ("GET", "/api/paquetes", "Obtener paquetes disponibles"),
        ("PUT", "/api/paquetes/{id}/precio", "Actualizar precio de paquete"),
        ("GET", "/api/stock", "Obtener stock de pines"),
        ("POST", "/api/pines", "Agregar pin al stock"),
        ("GET", "/api/transacciones", "Obtener todas las transacciones"),
    ]
    
    for method, endpoint, description in endpoints:
        print(f"   {method:4} {endpoint:30} - {description}")

def monitor_api():
    """Monitorea el estado de la API"""
    print("\n📊 MONITOREANDO API (Presiona Ctrl+C para detener)")
    print("=" * 50)
    
    try:
        while True:
            try:
                start_time = time.time()
                response = requests.get("http://localhost:5001/api/health", timeout=5)
                end_time = time.time()
                
                response_time = (end_time - start_time) * 1000
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                if response.status_code == 200:
                    print(f"[{timestamp}] ✅ API OK - {response_time:.2f}ms")
                else:
                    print(f"[{timestamp}] ⚠️  Status: {response.status_code}")
                    
            except Exception as e:
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}] ❌ Error: {e}")
            
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n📊 Monitoreo detenido")

def open_browser():
    """Abre la API en el navegador"""
    import webbrowser
    
    print("🌐 Abriendo API en el navegador...")
    try:
        webbrowser.open("http://localhost:5001/api/health")
        print("✅ Navegador abierto")
    except Exception as e:
        print(f"❌ Error al abrir navegador: {e}")
        print("💡 Abre manualmente: http://localhost:5001/api/health")

def main():
    """Función principal"""
    print_banner()
    
    # Verificaciones iniciales
    if not check_dependencies():
        return
    
    if not check_files():
        return
    
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
                    print("⚠️  La API ya está corriendo")
                else:
                    api_process = start_api()
                    if api_process and wait_for_api():
                        test_api_quick()
                        
            elif opcion == "2":
                print("🧪 Ejecutando pruebas completas...")
                subprocess.run([sys.executable, 'test_api.py', '--all'])
                
            elif opcion == "3":
                print("🧪 Ejecutando pruebas individuales...")
                subprocess.run([sys.executable, 'test_api.py'])
                
            elif opcion == "4":
                monitor_api()
                
            elif opcion == "5":
                show_endpoints()
                
            elif opcion == "6":
                open_browser()
                
            else:
                print("❌ Opción inválida")
            
            if opcion != "0":
                input("\n⏸️  Presiona Enter para continuar...")
    
    finally:
        # Limpiar procesos
        if api_process and api_process.poll() is None:
            print("\n🛑 Deteniendo API...")
            api_process.terminate()
            try:
                api_process.wait(timeout=5)
                print("✅ API detenida correctamente")
            except subprocess.TimeoutExpired:
                api_process.kill()
                print("⚠️  API forzada a detenerse")

if __name__ == "__main__":
    main()
