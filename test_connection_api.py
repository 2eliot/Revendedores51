#!/usr/bin/env python3
"""
Script de pruebas para la API de Conexión de Revendedores51
Prueba todos los endpoints y funcionalidades principales
"""

import requests
import json
import time
from datetime import datetime

# Configuración
API_BASE_URL = "http://localhost:5002"
TEST_USER_EMAIL = "test@ejemplo.com"
TEST_USER_PASSWORD = "test123"

class ConnectionAPITester:
    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()
        self.user_data = None
        
    def print_header(self, title):
        """Imprime un encabezado para las pruebas"""
        print("\n" + "=" * 60)
        print(f"🧪 {title}")
        print("=" * 60)
    
    def print_test(self, test_name, success, message="", data=None):
        """Imprime el resultado de una prueba"""
        status = "✅" if success else "❌"
        print(f"{status} {test_name}")
        if message:
            print(f"   📝 {message}")
        if data and isinstance(data, dict):
            print(f"   📊 Datos: {json.dumps(data, indent=6, ensure_ascii=False)}")
        print()
    
    def test_health_check(self):
        """Prueba el endpoint de health check"""
        self.print_header("HEALTH CHECK")
        
        try:
            response = self.session.get(f"{self.base_url}/api/connection/health")
            
            if response.status_code == 200:
                data = response.json()
                self.print_test(
                    "Health Check",
                    True,
                    f"API funcionando - Versión: {data.get('version', 'N/A')}",
                    data
                )
                return True
            else:
                self.print_test(
                    "Health Check",
                    False,
                    f"Status Code: {response.status_code}"
                )
                return False
                
        except Exception as e:
            self.print_test("Health Check", False, f"Error: {str(e)}")
            return False
    
    def test_login(self):
        """Prueba el endpoint de login"""
        self.print_header("AUTENTICACIÓN")
        
        # Datos de prueba
        login_data = {
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/api/connection/login",
                json=login_data,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    self.user_data = data.get('data', {})
                    self.print_test(
                        "Login Exitoso",
                        True,
                        f"Usuario: {self.user_data.get('name')} - Saldo: ${self.user_data.get('balance', 0):.2f}",
                        self.user_data
                    )
                    return True
                else:
                    self.print_test(
                        "Login",
                        False,
                        data.get('message', 'Error desconocido')
                    )
                    return False
            elif response.status_code == 401:
                self.print_test(
                    "Login",
                    False,
                    "Credenciales incorrectas - Verifica que el usuario de prueba exista"
                )
                return False
            else:
                self.print_test(
                    "Login",
                    False,
                    f"Status Code: {response.status_code}"
                )
                return False
                
        except Exception as e:
            self.print_test("Login", False, f"Error: {str(e)}")
            return False
    
    def test_get_balance(self):
        """Prueba el endpoint de obtener saldo"""
        if not self.user_data:
            self.print_test("Get Balance", False, "No hay datos de usuario (login requerido)")
            return False
        
        user_id = self.user_data.get('user_id')
        
        try:
            response = self.session.get(f"{self.base_url}/api/connection/balance/{user_id}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    balance_data = data.get('data', {})
                    self.print_test(
                        "Obtener Saldo",
                        True,
                        f"Saldo actual: ${balance_data.get('balance', 0):.2f}",
                        balance_data
                    )
                    return True
                else:
                    self.print_test("Obtener Saldo", False, data.get('message'))
                    return False
            else:
                self.print_test("Obtener Saldo", False, f"Status Code: {response.status_code}")
                return False
                
        except Exception as e:
            self.print_test("Obtener Saldo", False, f"Error: {str(e)}")
            return False
    
    def test_get_packages(self):
        """Prueba el endpoint de obtener paquetes"""
        self.print_header("PAQUETES DISPONIBLES")
        
        try:
            response = self.session.get(f"{self.base_url}/api/connection/packages")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    packages = data.get('data', [])
                    self.print_test(
                        "Obtener Paquetes",
                        True,
                        f"Total de paquetes: {len(packages)}",
                        {'total_packages': len(packages), 'packages': packages[:3]}  # Solo mostrar primeros 3
                    )
                    
                    # Mostrar algunos paquetes
                    print("   📦 Paquetes disponibles:")
                    for package in packages[:5]:  # Mostrar primeros 5
                        print(f"      • ID {package['id']}: {package['name']} - ${package['price']:.2f}")
                    
                    return True
                else:
                    self.print_test("Obtener Paquetes", False, data.get('message'))
                    return False
            else:
                self.print_test("Obtener Paquetes", False, f"Status Code: {response.status_code}")
                return False
                
        except Exception as e:
            self.print_test("Obtener Paquetes", False, f"Error: {str(e)}")
            return False
    
    def test_get_stock(self):
        """Prueba el endpoint de obtener stock"""
        self.print_header("STOCK DE PINES")
        
        try:
            response = self.session.get(f"{self.base_url}/api/connection/stock")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    stock_data = data.get('data', {})
                    total_pins = data.get('total_pins', 0)
                    
                    self.print_test(
                        "Obtener Stock",
                        True,
                        f"Total de PINs disponibles: {total_pins}",
                        {'total_pins': total_pins, 'stock_by_package': stock_data}
                    )
                    
                    # Mostrar stock por paquete
                    print("   📊 Stock por paquete:")
                    for package_id, count in stock_data.items():
                        print(f"      • Paquete {package_id}: {count} PINs")
                    
                    return True
                else:
                    self.print_test("Obtener Stock", False, data.get('message'))
                    return False
            else:
                self.print_test("Obtener Stock", False, f"Status Code: {response.status_code}")
                return False
                
        except Exception as e:
            self.print_test("Obtener Stock", False, f"Error: {str(e)}")
            return False
    
    def test_purchase_pin(self, package_id=1, quantity=1):
        """Prueba el endpoint de compra de PIN"""
        self.print_header("COMPRA DE PIN")
        
        if not self.user_data:
            self.print_test("Compra PIN", False, "No hay datos de usuario (login requerido)")
            return False
        
        user_id = self.user_data.get('user_id')
        
        purchase_data = {
            "user_id": user_id,
            "package_id": package_id,
            "quantity": quantity
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/api/connection/purchase",
                json=purchase_data,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    purchase_info = data.get('data', {})
                    
                    # Actualizar saldo del usuario
                    self.user_data['balance'] = purchase_info.get('new_balance', self.user_data.get('balance', 0))
                    
                    message = f"Paquete: {purchase_info.get('package_name')} - Precio: ${purchase_info.get('total_price', 0):.2f} - Nuevo saldo: ${purchase_info.get('new_balance', 0):.2f}"
                    
                    self.print_test(
                        "Compra PIN",
                        True,
                        message,
                        purchase_info
                    )
                    
                    # Mostrar PIN(s) obtenido(s)
                    if quantity == 1:
                        print(f"   🎯 PIN obtenido: {purchase_info.get('pin', 'N/A')}")
                    else:
                        pins = purchase_info.get('pins', [])
                        print(f"   🎯 PINs obtenidos ({len(pins)}):")
                        for i, pin in enumerate(pins, 1):
                            print(f"      {i}. {pin}")
                    
                    return True
                else:
                    self.print_test("Compra PIN", False, data.get('message'))
                    return False
            elif response.status_code == 400:
                data = response.json()
                self.print_test("Compra PIN", False, f"Error de validación: {data.get('message')}")
                return False
            else:
                self.print_test("Compra PIN", False, f"Status Code: {response.status_code}")
                return False
                
        except Exception as e:
            self.print_test("Compra PIN", False, f"Error: {str(e)}")
            return False
    
    def test_get_transactions(self):
        """Prueba el endpoint de obtener transacciones"""
        self.print_header("HISTORIAL DE TRANSACCIONES")
        
        if not self.user_data:
            self.print_test("Obtener Transacciones", False, "No hay datos de usuario (login requerido)")
            return False
        
        user_id = self.user_data.get('user_id')
        
        try:
            response = self.session.get(f"{self.base_url}/api/connection/user/{user_id}/transactions?limit=5")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    transactions = data.get('data', [])
                    
                    self.print_test(
                        "Obtener Transacciones",
                        True,
                        f"Total de transacciones: {len(transactions)}",
                        {'total_transactions': len(transactions)}
                    )
                    
                    # Mostrar algunas transacciones
                    if transactions:
                        print("   📋 Transacciones recientes:")
                        for i, transaction in enumerate(transactions[:3], 1):
                            print(f"      {i}. ID: {transaction.get('transaction_id')} - Monto: ${abs(transaction.get('amount', 0)):.2f} - Fecha: {transaction.get('date')}")
                    else:
                        print("   📋 No hay transacciones registradas")
                    
                    return True
                else:
                    self.print_test("Obtener Transacciones", False, data.get('message'))
                    return False
            else:
                self.print_test("Obtener Transacciones", False, f"Status Code: {response.status_code}")
                return False
                
        except Exception as e:
            self.print_test("Obtener Transacciones", False, f"Error: {str(e)}")
            return False
    
    def test_error_handling(self):
        """Prueba el manejo de errores"""
        self.print_header("MANEJO DE ERRORES")
        
        # Probar endpoint inexistente
        try:
            response = self.session.get(f"{self.base_url}/api/connection/nonexistent")
            if response.status_code == 404:
                self.print_test("Endpoint inexistente", True, "Error 404 manejado correctamente")
            else:
                self.print_test("Endpoint inexistente", False, f"Status Code inesperado: {response.status_code}")
        except Exception as e:
            self.print_test("Endpoint inexistente", False, f"Error: {str(e)}")
        
        # Probar login con credenciales inválidas
        try:
            invalid_login = {
                "email": "invalid@test.com",
                "password": "wrongpassword"
            }
            response = self.session.post(
                f"{self.base_url}/api/connection/login",
                json=invalid_login,
                headers={'Content-Type': 'application/json'}
            )
            if response.status_code == 401:
                self.print_test("Login inválido", True, "Error 401 manejado correctamente")
            else:
                self.print_test("Login inválido", False, f"Status Code inesperado: {response.status_code}")
        except Exception as e:
            self.print_test("Login inválido", False, f"Error: {str(e)}")
        
        # Probar compra sin saldo suficiente (si el usuario tiene poco saldo)
        if self.user_data and self.user_data.get('balance', 0) < 100:
            try:
                expensive_purchase = {
                    "user_id": self.user_data.get('user_id'),
                    "package_id": 6,  # Paquete más caro
                    "quantity": 10    # Cantidad alta
                }
                response = self.session.post(
                    f"{self.base_url}/api/connection/purchase",
                    json=expensive_purchase,
                    headers={'Content-Type': 'application/json'}
                )
                if response.status_code == 400:
                    data = response.json()
                    if "saldo insuficiente" in data.get('message', '').lower():
                        self.print_test("Saldo insuficiente", True, "Error de saldo manejado correctamente")
                    else:
                        self.print_test("Saldo insuficiente", False, f"Mensaje inesperado: {data.get('message')}")
                else:
                    self.print_test("Saldo insuficiente", False, f"Status Code inesperado: {response.status_code}")
            except Exception as e:
                self.print_test("Saldo insuficiente", False, f"Error: {str(e)}")
    
    def run_all_tests(self):
        """Ejecuta todas las pruebas"""
        print("🚀 INICIANDO PRUEBAS DE LA API DE CONEXIÓN")
        print(f"🌐 URL Base: {self.base_url}")
        print(f"👤 Usuario de prueba: {TEST_USER_EMAIL}")
        print(f"🕒 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Contador de pruebas
        tests_passed = 0
        total_tests = 0
        
        # Lista de pruebas a ejecutar
        test_methods = [
            ('Health Check', self.test_health_check),
            ('Login', self.test_login),
            ('Get Balance', self.test_get_balance),
            ('Get Packages', self.test_get_packages),
            ('Get Stock', self.test_get_stock),
            ('Purchase PIN', lambda: self.test_purchase_pin(1, 1)),
            ('Get Transactions', self.test_get_transactions),
            ('Error Handling', self.test_error_handling)
        ]
        
        # Ejecutar pruebas
        for test_name, test_method in test_methods:
            try:
                result = test_method()
                total_tests += 1
                if result:
                    tests_passed += 1
            except Exception as e:
                print(f"❌ Error en prueba {test_name}: {str(e)}")
                total_tests += 1
        
        # Resumen final
        self.print_header("RESUMEN DE PRUEBAS")
        success_rate = (tests_passed / total_tests * 100) if total_tests > 0 else 0
        
        print(f"✅ Pruebas exitosas: {tests_passed}")
        print(f"❌ Pruebas fallidas: {total_tests - tests_passed}")
        print(f"📊 Total de pruebas: {total_tests}")
        print(f"🎯 Tasa de éxito: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("\n🎉 ¡API funcionando correctamente!")
        elif success_rate >= 60:
            print("\n⚠️  API funcionando con algunos problemas")
        else:
            print("\n🚨 API con problemas significativos")
        
        return success_rate >= 80

def main():
    """Función principal"""
    print("🧪 TESTER DE API DE CONEXIÓN - REVENDEDORES51")
    print("=" * 60)
    
    # Verificar si la API está corriendo
    try:
        response = requests.get(f"{API_BASE_URL}/api/connection/health", timeout=5)
        if response.status_code != 200:
            print("❌ La API no está respondiendo correctamente")
            print("💡 Asegúrate de que la API esté corriendo en http://localhost:5002")
            return
    except requests.exceptions.RequestException:
        print("❌ No se puede conectar a la API")
        print("💡 Asegúrate de que la API esté corriendo en http://localhost:5002")
        print("💡 Ejecuta: python connection_api.py")
        return
    
    # Crear tester y ejecutar pruebas
    tester = ConnectionAPITester(API_BASE_URL)
    success = tester.run_all_tests()
    
    if success:
        print("\n🎯 TODAS LAS PRUEBAS COMPLETADAS EXITOSAMENTE")
        print("✅ La API de conexión está lista para usar")
    else:
        print("\n⚠️  ALGUNAS PRUEBAS FALLARON")
        print("🔧 Revisa los errores y la configuración de la API")

if __name__ == "__main__":
    main()
