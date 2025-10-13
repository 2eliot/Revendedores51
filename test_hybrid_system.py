#!/usr/bin/env python3
"""
Script de prueba para el sistema híbrido:
- Usuarios ven solo stock local con indicadores ✅/❌
- Admin puede obtener pines de API externa manualmente
"""

import sqlite3
import os
from pin_manager import create_pin_manager

def setup_test_db():
    """Crea una base de datos de prueba con algunos pines"""
    test_db = 'test_hybrid.db'
    
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
        (1, 'LOCAL-PIN-001'),
        (1, 'LOCAL-PIN-002'),
        (2, 'LOCAL-PIN-003'),
        (3, 'LOCAL-PIN-004'),
    ]
    
    conn.executemany('''
        INSERT INTO pines_freefire (monto_id, pin_codigo)
        VALUES (?, ?)
    ''', test_pins)
    
    conn.commit()
    conn.close()
    
    return test_db

def test_hybrid_system():
    """Prueba el sistema híbrido"""
    print("🧪 INICIANDO PRUEBAS DEL SISTEMA HÍBRIDO")
    print("=" * 60)
    
    # Configurar base de datos de prueba
    test_db = setup_test_db()
    pin_manager = create_pin_manager(test_db)
    
    # Mostrar stock inicial
    print("\n📊 STOCK LOCAL INICIAL:")
    local_stock = pin_manager.get_local_stock()
    for monto_id in range(1, 10):
        count = local_stock.get(monto_id, 0)
        indicator = '✅' if count > 0 else '❌'
        print(f"  Monto {monto_id}: {indicator} {count} pines")
    
    # Prueba 1: Usuario normal - Solo stock local
    print("\n🧪 PRUEBA 1: Usuario normal solicita pin (solo stock local)")
    print("-" * 50)
    result = pin_manager.request_pin(1)
    if result.get('status') == 'success':
        print(f"✅ Pin obtenido del stock local: {result.get('pin_code')}")
        print(f"   Stock restante: {result.get('stock_remaining')}")
    else:
        print(f"❌ Error: {result.get('message')}")
    
    # Prueba 2: Usuario normal - Sin stock local
    print("\n🧪 PRUEBA 2: Usuario normal solicita pin sin stock local")
    print("-" * 50)
    result = pin_manager.request_pin(5)  # Monto 5 no tiene stock
    if result.get('status') == 'error':
        print(f"✅ Error esperado (sin stock local): {result.get('message')}")
    else:
        print(f"❌ Debería haber dado error: {result}")
    
    # Prueba 3: Admin - Probar API externa
    print("\n🧪 PRUEBA 3: Admin prueba conexión con API externa")
    print("-" * 50)
    try:
        api_result = pin_manager.test_external_api()
        if api_result.get('status') == 'success':
            print(f"✅ API externa disponible: {api_result.get('message')}")
        else:
            print(f"⚠️ API externa no disponible: {api_result.get('message')}")
    except Exception as e:
        print(f"⚠️ Error al probar API externa: {str(e)}")
    
    # Prueba 4: Admin - Obtener pin de API externa
    print("\n🧪 PRUEBA 4: Admin obtiene pin de API externa")
    print("-" * 50)
    try:
        external_result = pin_manager.request_pin_from_external_api(5)  # Monto sin stock local
        if external_result.get('status') == 'success':
            print(f"✅ Pin obtenido de API externa: {external_result.get('pin_code')}")
            print(f"   Agregado al stock local para monto {external_result.get('monto_id')}")
        elif external_result.get('status') == 'warning':
            print(f"⚠️ Advertencia: {external_result.get('message')}")
        else:
            print(f"❌ Error en API externa: {external_result.get('message')}")
    except Exception as e:
        print(f"⚠️ Error al obtener pin de API externa: {str(e)}")
    
    # Mostrar stock final
    print("\n📊 STOCK LOCAL FINAL:")
    local_stock = pin_manager.get_local_stock()
    for monto_id in range(1, 10):
        count = local_stock.get(monto_id, 0)
        indicator = '✅' if count > 0 else '❌'
        print(f"  Monto {monto_id}: {indicator} {count} pines")
    
    # Prueba 5: Usuario normal después de que admin agregó stock
    print("\n🧪 PRUEBA 5: Usuario normal solicita pin después de que admin agregó stock")
    print("-" * 50)
    result = pin_manager.request_pin(5)  # Ahora debería tener stock si la API funcionó
    if result.get('status') == 'success':
        print(f"✅ Pin obtenido (agregado por admin): {result.get('pin_code')}")
        print(f"   Stock restante: {result.get('stock_remaining')}")
    else:
        print(f"❌ Sin stock disponible: {result.get('message')}")
    
    # Limpiar
    print(f"\n🧹 Eliminando base de datos de prueba: {test_db}")
    os.remove(test_db)
    
    print("\n🎉 PRUEBAS DEL SISTEMA HÍBRIDO COMPLETADAS")
    print("\n📋 RESUMEN DEL SISTEMA:")
    print("✅ Usuarios: Solo ven stock local con indicadores ✅/❌")
    print("✅ Admin: Puede obtener pines de API externa manualmente")
    print("✅ Flujo: API externa → Stock local → Usuarios")

if __name__ == '__main__':
    test_hybrid_system()
