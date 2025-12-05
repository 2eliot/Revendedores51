#!/usr/bin/env python3
"""
Script de prueba para la integración con la API externa de Inefable Shop
"""

import os
import sys
from datetime import datetime
from inefable_api_client import get_inefable_client
from pin_manager import create_pin_manager

def print_header(title):
    """Imprime un encabezado formateado"""
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)

def print_result(test_name, success, message, details=None):
    """Imprime el resultado de una prueba"""
    status = "✅ ÉXITO" if success else "❌ ERROR"
    print(f"\n{status} - {test_name}")
    print(f"   Mensaje: {message}")
    if details:
        print(f"   Detalles: {details}")

def test_inefable_api_connection():
    """Prueba la conexión con la API externa de Inefable Shop"""
    print_header("PRUEBA DE CONEXIÓN CON API EXTERNA")
    
    try:
        client = get_inefable_client()
        success, message = client.test_connection()
        
        print_result("Conexión con API Externa", success, message)
        
        if success:
            print(f"   URL: {client.base_url}")
            print(f"   Usuario: {client.usuario}")
            print(f"   Timeout: {client.timeout}s")
        
        return success
        
    except Exception as e:
        print_result("Conexión con API Externa", False, f"Error inesperado: {str(e)}")
        return False

def test_pin_request():
    """Prueba solicitar un pin de la API externa"""
    print_header("PRUEBA DE SOLICITUD DE PIN")
    
    try:
        client = get_inefable_client()
        
        # Probar con monto_id 1 (110 💎)
        monto_id = 1
        print(f"Solicitando pin para monto_id {monto_id} (110 💎)...")
        
        result = client.request_pin(monto_id)
        
        if result.get('status') == 'success':
            pin_code = result.get('pin_code')
            source = result.get('source')
            timestamp = result.get('timestamp')
            
            print_result("Solicitud de Pin", True, "Pin obtenido exitosamente")
            print(f"   Pin: {pin_code[:4]}****{pin_code[-4:] if len(pin_code) >= 8 else pin_code}")
            print(f"   Fuente: {source}")
            print(f"   Timestamp: {timestamp}")
            
            return True, pin_code
        else:
            error_msg = result.get('message', 'Error desconocido')
            error_type = result.get('error_type', 'unknown')
            print_result("Solicitud de Pin", False, error_msg, f"Tipo: {error_type}")
            return False, None
            
    except Exception as e:
        print_result("Solicitud de Pin", False, f"Error inesperado: {str(e)}")
        return False, None

def test_pin_manager_integration():
    """Prueba la integración del gestor de pines con API externa"""
    print_header("PRUEBA DE INTEGRACIÓN CON GESTOR DE PINES")
    
    try:
        # Usar base de datos de prueba
        test_db = "test_integration.db"
        pin_manager = create_pin_manager(test_db)
        
        # Obtener estado del stock
        print("Obteniendo estado del stock...")
        status = pin_manager.get_stock_status()
        
        if status.get('status') == 'success':
            local_stock = status.get('local_stock', {})
            api_available = status.get('external_api', {}).get('available', False)
            
            print_result("Estado del Stock", True, "Estado obtenido correctamente")
            print(f"   Stock local total: {status.get('total_local_pins', 0)} pines")
            print(f"   API externa disponible: {'Sí' if api_available else 'No'}")
            
            # Mostrar stock por monto
            for monto_id in range(1, 10):
                stock_count = local_stock.get(monto_id, 0)
                print(f"   Monto {monto_id}: {stock_count} pines")
        else:
            print_result("Estado del Stock", False, status.get('message', 'Error desconocido'))
            return False
        
        # Probar solicitud de pin con respaldo
        print("\nProbando solicitud de pin con respaldo de API externa...")
        monto_id = 1
        
        result = pin_manager.request_pin_with_fallback(monto_id, use_external_api=True)
        
        if result.get('status') == 'success':
            pin_code = result.get('pin_code')
            source = result.get('source')
            
            print_result("Pin con Respaldo", True, "Pin obtenido exitosamente")
            print(f"   Pin: {pin_code[:4]}****{pin_code[-4:] if len(pin_code) >= 8 else pin_code}")
            print(f"   Fuente: {source}")
            
            # Limpiar base de datos de prueba
            if os.path.exists(test_db):
                os.remove(test_db)
                print(f"   Base de datos de prueba eliminada: {test_db}")
            
            return True
        else:
            error_msg = result.get('message', 'Error desconocido')
            print_result("Pin con Respaldo", False, error_msg)
            return False
            
    except Exception as e:
        print_result("Integración con Gestor", False, f"Error inesperado: {str(e)}")
        return False

def test_multiple_pins():
    """Prueba solicitar múltiples pines"""
    print_header("PRUEBA DE MÚLTIPLES PINES")
    
    try:
        test_db = "test_multiple.db"
        pin_manager = create_pin_manager(test_db)
        
        monto_id = 1
        cantidad = 3
        
        print(f"Solicitando {cantidad} pines para monto_id {monto_id}...")
        
        result = pin_manager.request_multiple_pins(monto_id, cantidad, use_external_api=True)
        
        if result.get('status') in ['success', 'partial_success']:
            pins = result.get('pins', [])
            sources_used = result.get('sources_used', [])
            cantidad_obtenida = result.get('cantidad_obtenida', 0)
            
            success_msg = f"{cantidad_obtenida} pines obtenidos"
            if result.get('status') == 'partial_success':
                success_msg += f" (parcial: {cantidad_obtenida}/{cantidad})"
            
            print_result("Múltiples Pines", True, success_msg)
            print(f"   Fuentes utilizadas: {', '.join(sources_used)}")
            
            for i, pin_data in enumerate(pins, 1):
                pin_code = pin_data.get('pin_code', '')
                source = pin_data.get('source', 'unknown')
                print(f"   Pin {i}: {pin_code[:4]}****{pin_code[-4:] if len(pin_code) >= 8 else pin_code} ({source})")
            
            # Limpiar base de datos de prueba
            if os.path.exists(test_db):
                os.remove(test_db)
            
            return True
        else:
            error_msg = result.get('message', 'Error desconocido')
            print_result("Múltiples Pines", False, error_msg)
            return False
            
    except Exception as e:
        print_result("Múltiples Pines", False, f"Error inesperado: {str(e)}")
        return False

def test_configuration():
    """Verifica la configuración de la API externa"""
    print_header("VERIFICACIÓN DE CONFIGURACIÓN")
    
    try:
        client = get_inefable_client()
        
        # Verificar configuración
        config_ok = True
        issues = []
        
        if not client.usuario or client.usuario == 'aquiUsuario':
            config_ok = False
            issues.append("Usuario no configurado correctamente")
        
        if not client.clave or client.clave == 'aquiclave':
            config_ok = False
            issues.append("Clave no configurada correctamente")
        
        if not client.base_url:
            config_ok = False
            issues.append("URL base no configurada")
        
        # Verificar variables de entorno
        env_usuario = os.environ.get('INEFABLE_USUARIO')
        env_clave = os.environ.get('INEFABLE_CLAVE')
        
        print_result("Configuración", config_ok, 
                    "Configuración correcta" if config_ok else "Problemas encontrados",
                    "; ".join(issues) if issues else None)
        
        print(f"   Usuario configurado: {client.usuario}")
        print(f"   Variable INEFABLE_USUARIO: {'✓' if env_usuario else '✗'}")
        print(f"   Variable INEFABLE_CLAVE: {'✓' if env_clave else '✗'}")
        print(f"   URL: {client.base_url}")
        print(f"   Timeout: {client.timeout}s")
        
        # Mostrar mapeo de montos
        print("\n   Mapeo de montos:")
        for local_id, external_id in client.monto_mapping.items():
            print(f"     Monto local {local_id} → Monto externo {external_id}")
        
        return config_ok
        
    except Exception as e:
        print_result("Configuración", False, f"Error al verificar configuración: {str(e)}")
        return False

def main():
    """Función principal del script de prueba"""
    print_header("SCRIPT DE PRUEBA - INTEGRACIÓN INEFABLE SHOP")
    print(f"Fecha y hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Lista de pruebas
    tests = [
        ("Configuración", test_configuration),
        ("Conexión API", test_inefable_api_connection),
        ("Solicitud de Pin", test_pin_request),
        ("Integración Gestor", test_pin_manager_integration),
        ("Múltiples Pines", test_multiple_pins)
    ]
    
    results = []
    
    # Ejecutar pruebas
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print_result(test_name, False, f"Error crítico: {str(e)}")
            results.append((test_name, False))
    
    # Resumen final
    print_header("RESUMEN DE PRUEBAS")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"Pruebas ejecutadas: {total}")
    print(f"Pruebas exitosas: {passed}")
    print(f"Pruebas fallidas: {total - passed}")
    print(f"Porcentaje de éxito: {(passed/total)*100:.1f}%")
    
    print("\nDetalle:")
    for test_name, result in results:
        status = "✅" if result else "❌"
        print(f"  {status} {test_name}")
    
    if passed == total:
        print("\n🎉 ¡Todas las pruebas pasaron exitosamente!")
        print("La integración con la API externa de Inefable Shop está funcionando correctamente.")
    else:
        print(f"\n⚠️  {total - passed} prueba(s) fallaron.")
        print("Revisa la configuración y la conectividad con la API externa.")
    
    print_header("FIN DE PRUEBAS")
    
    return passed == total

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Pruebas interrumpidas por el usuario.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error crítico en el script de prueba: {str(e)}")
        sys.exit(1)
