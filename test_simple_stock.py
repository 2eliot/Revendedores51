#!/usr/bin/env python3
"""
Script de prueba simple para verificar que el sistema funciona solo con stock local
"""

import sqlite3
import os
from pin_manager import create_pin_manager

def setup_test_db():
    """Crea una base de datos de prueba con algunos pines"""
    test_db = 'test_simple.db'
    
    # Eliminar base de datos anterior si existe
    if os.path.exists(test_db):
        os.remove(test_db)
    
    # Crear base de datos y tabla
    conn = sqlite3.connect(test_db)
    conn.execute('''
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
        (1, 'TEST-PIN-001'),
        (1, 'TEST-PIN-002'),
        (2, 'TEST-PIN-003'),
        (3, 'TEST-PIN-004'),
        (3, 'TEST-PIN-005'),
        (3, 'TEST-PIN-006'),
    ]
    
    conn.executemany('''
        INSERT INTO pines_freefire (monto_id, pin_codigo)
        VALUES (?, ?)
    ''', test_pins)
    
    conn.commit()
    conn.close()
    
    return test_db

def test_simple_stock():
    """Prueba el sistema simple de stock local"""
    print("🧪 INICIANDO PRUEBAS DE STOCK LOCAL SIMPLE")
    print("=" * 50)
    
    # Configurar base de datos de prueba
    test_db = setup_test_db()
    pin_manager = create_pin_manager(test_db)
    
    # Mostrar stock inicial
    print("\n📊 STOCK INICIAL:")
    local_stock = pin_manager.get_local_stock()
    for monto_id in range(1, 10):
        count = local_stock.get(monto_id, 0)
        indicator = '✅' if count > 0 else '❌'
        print(f"  Monto {monto_id}: {indicator} {count} pines")
    
    # Prueba 1: Solicitar pin con stock disponible
    print("\n🧪 PRUEBA 1: Solicitar pin con stock disponible")
    print("-" * 40)
    result = pin_manager.request_pin(1)
    if result.get('status') == 'success':
        print(f"✅ Pin obtenido: {result.get('pin_code')}")
        print(f"   Stock restante: {result.get('stock_remaining')}")
    else:
        print(f"❌ Error: {result.get('message')}")
    
    # Prueba 2: Solicitar pin sin stock
    print("\n🧪 PRUEBA 2: Solicitar pin sin stock")
    print("-" * 40)
    result = pin_manager.request_pin(4)  # Monto 4 no tiene stock
    if result.get('status') == 'error':
        print(f"✅ Error esperado: {result.get('message')}")
    else:
        print(f"❌ Debería haber dado error pero obtuvo: {result}")
    
    # Prueba 3: Solicitar múltiples pines
    print("\n🧪 PRUEBA 3: Solicitar múltiples pines")
    print("-" * 40)
    result = pin_manager.request_multiple_pins(3, 2)  # 2 pines del monto 3
    if result.get('status') == 'success':
        pins = result.get('pins', [])
        print(f"✅ {len(pins)} pines obtenidos:")
        for i, pin in enumerate(pins, 1):
            print(f"   Pin {i}: {pin.get('pin_code')}")
    else:
        print(f"❌ Error: {result.get('message')}")
    
    # Mostrar stock final
    print("\n📊 STOCK FINAL:")
    local_stock = pin_manager.get_local_stock()
    for monto_id in range(1, 10):
        count = local_stock.get(monto_id, 0)
        indicator = '✅' if count > 0 else '❌'
        print(f"  Monto {monto_id}: {indicator} {count} pines")
    
    # Limpiar
    print(f"\n🧹 Eliminando base de datos de prueba: {test_db}")
    os.remove(test_db)
    
    print("\n🎉 PRUEBAS COMPLETADAS")
    print("✅ Sistema funcionando solo con stock local")

if __name__ == '__main__':
    test_simple_stock()
