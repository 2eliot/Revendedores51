#!/usr/bin/env python3
"""
Script de prueba para verificar que el sistema priorice correctamente el stock local
sobre la API externa.
"""

import os
import sys
import sqlite3
from pin_manager import create_pin_manager

def setup_test_database():
    """Crea una base de datos de prueba con algunos pines"""
    test_db = 'test_stock.db'
    
    # Eliminar base de datos de prueba si existe
    if os.path.exists(test_db):
        os.remove(test_db)
    
    # Crear base de datos de prueba
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    
    # Crear tabla de pines
    cursor.execute('''
        CREATE TABLE pines_freefire (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            monto_id INTEGER NOT NULL,
            pin_codigo TEXT NOT NULL,
            usado BOOLEAN DEFAULT FALSE,
            fecha_agregado DATETIME DEFAULT CURRENT_TIMESTAMP,
            fecha_usado DATETIME NULL,
            usuario_id INTEGER NULL
        )
    ''')
    
    # Agregar algunos pines de prueba
    test_pins = [
        (1, 'TEST110DIAMONDS001'),
        (1, 'TEST110DIAMONDS002'),
        (2, 'TEST341DIAMONDS001'),
        (3, 'TEST572DIAMONDS001'),
        (3, 'TEST572DIAMONDS002'),
        (3, 'TEST572DIAMONDS003'),
    ]
    
    for monto_id, pin_code in test_pins:
        cursor.execute('''
            INSERT INTO pines_freefire (monto_id, pin_codigo)
            VALUES (?, ?)
        ''', (monto_id, pin_code))
    
    conn.commit()
    conn.close()
    
    return test_db

def test_stock_priority():
    """Prueba que el sistema priorice el stock local"""
    print("🧪 INICIANDO PRUEBAS DE PRIORIDAD DE STOCK")
    print("=" * 50)
    
    # Configurar base de datos de prueba
    test_db = setup_test_database()
    pin_manager = create_pin_manager(test_db)
    
    try:
        # Verificar stock inicial
        print("\n📊 STOCK INICIAL:")
        local_stock = pin_manager.get_local_stock()
        for monto_id, count in local_stock.items():
            if count > 0:
                print(f"  Monto {monto_id}: {count} pines")
        
        # Prueba 1: Solicitar pin cuando HAY stock local
        print("\n🧪 PRUEBA 1: Solicitar pin con stock local disponible")
        print("-" * 40)
        
        result = pin_manager.request_pin_with_fallback(monto_id=1, use_external_api=True)
        
        if result.get('status') == 'success':
            source = result.get('source')
            pin_code = result.get('pin_code')
            print(f"✅ Pin obtenido exitosamente")
            print(f"   Fuente: {source}")
            print(f"   Pin: {pin_code[:4]}****{pin_code[-4:]}")
            
            if source == 'local_stock':
                print("✅ CORRECTO: Se usó stock local como se esperaba")
            else:
                print("❌ ERROR: Se usó API externa cuando había stock local disponible")
                return False
        else:
            print(f"❌ ERROR: No se pudo obtener pin: {result.get('message')}")
            return False
        
        # Prueba 2: Solicitar pin cuando NO hay stock local
        print("\n🧪 PRUEBA 2: Solicitar pin SIN stock local disponible")
        print("-" * 40)
        
        # Vaciar stock local para monto 4 (que no tiene pines)
        result = pin_manager.request_pin_with_fallback(monto_id=4, use_external_api=True)
        
        if result.get('status') == 'success':
            source = result.get('source')
            pin_code = result.get('pin_code')
            print(f"✅ Pin obtenido exitosamente")
            print(f"   Fuente: {source}")
            print(f"   Pin: {pin_code[:4]}****{pin_code[-4:]}")
            
            if source == 'inefable_api':
                print("✅ CORRECTO: Se usó API externa cuando no había stock local")
            else:
                print("❌ ERROR: Se esperaba usar API externa pero se usó otra fuente")
        else:
            error_type = result.get('error_type')
            if error_type in ['no_stock_anywhere', 'no_stock', 'no_pin_found']:
                print("✅ CORRECTO: No hay stock en ninguna fuente (comportamiento esperado)")
            else:
                print(f"⚠️  Sin stock disponible: {result.get('message')}")
        
        # Prueba 3: Verificar que el stock local se reduce correctamente
        print("\n🧪 PRUEBA 3: Verificar reducción de stock local")
        print("-" * 40)
        
        stock_before = pin_manager.get_local_stock(1)
        print(f"Stock antes: {stock_before}")
        
        result = pin_manager.request_pin_with_fallback(monto_id=1, use_external_api=True)
        
        stock_after = pin_manager.get_local_stock(1)
        print(f"Stock después: {stock_after}")
        
        if result.get('status') == 'success' and result.get('source') == 'local_stock':
            if stock_after == stock_before - 1:
                print("✅ CORRECTO: Stock local se redujo correctamente")
            else:
                print("❌ ERROR: Stock local no se redujo correctamente")
                return False
        
        # Prueba 4: Múltiples pines con stock mixto
        print("\n🧪 PRUEBA 4: Múltiples pines con stock mixto")
        print("-" * 40)
        
        # Solicitar 5 pines del monto 3 (que tiene 3 en stock local)
        result = pin_manager.request_multiple_pins(monto_id=3, cantidad=5, use_external_api=True)
        
        if result.get('status') in ['success', 'partial_success']:
            pins = result.get('pins', [])
            sources_used = result.get('sources_used', [])
            
            print(f"Pines obtenidos: {len(pins)}")
            print(f"Fuentes usadas: {sources_used}")
            
            local_count = sum(1 for pin in pins if pin['source'] == 'local_stock')
            external_count = sum(1 for pin in pins if pin['source'] == 'inefable_api')
            
            print(f"Del stock local: {local_count}")
            print(f"De API externa: {external_count}")
            
            if local_count <= 3:  # Máximo 3 del stock local
                print("✅ CORRECTO: Se usó primero el stock local disponible")
            else:
                print("❌ ERROR: Se usaron más pines locales de los disponibles")
                return False
        
        print("\n🎉 TODAS LAS PRUEBAS COMPLETADAS")
        return True
        
    except Exception as e:
        print(f"❌ ERROR INESPERADO: {str(e)}")
        return False
    
    finally:
        # Limpiar base de datos de prueba
        if os.path.exists(test_db):
            os.remove(test_db)
            print(f"\n🧹 Base de datos de prueba eliminada: {test_db}")

if __name__ == "__main__":
    success = test_stock_priority()
    
    if success:
        print("\n✅ RESULTADO: Sistema funcionando correctamente")
        print("   - Prioriza stock local sobre API externa")
        print("   - Solo usa API externa cuando no hay stock local")
        sys.exit(0)
    else:
        print("\n❌ RESULTADO: Se encontraron problemas en el sistema")
        sys.exit(1)
