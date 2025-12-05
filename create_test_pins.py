#!/usr/bin/env python3
"""
Script para crear PINs de prueba para la API
"""

import sqlite3
import random
import string
from datetime import datetime

def generate_pin():
    """Genera un PIN de prueba"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

def create_test_pins():
    """Crea PINs de prueba para diferentes paquetes"""
    
    conn = sqlite3.connect('usuarios.db')
    
    try:
        # Crear PINs para los primeros 5 paquetes (monto_id 1-5)
        pins_per_package = 10  # 10 PINs por paquete
        
        for monto_id in range(1, 6):
            print(f"📦 Creando PINs para paquete {monto_id}...")
            
            for i in range(pins_per_package):
                pin_codigo = generate_pin()
                
                conn.execute('''
                    INSERT INTO pines_freefire (monto_id, pin_codigo, usado, fecha_agregado)
                    VALUES (?, ?, ?, ?)
                ''', (monto_id, pin_codigo, False, datetime.now()))
            
            print(f"   ✅ {pins_per_package} PINs creados para paquete {monto_id}")
        
        conn.commit()
        
        # Verificar que se crearon correctamente
        print("\n📊 RESUMEN DE PINs CREADOS:")
        for monto_id in range(1, 6):
            count = conn.execute(
                'SELECT COUNT(*) FROM pines_freefire WHERE monto_id = ? AND usado = 0', 
                (monto_id,)
            ).fetchone()[0]
            
            # Obtener nombre del paquete
            package = conn.execute(
                'SELECT nombre FROM precios_paquetes WHERE id = ?', 
                (monto_id,)
            ).fetchone()
            
            package_name = package[0] if package else f"Paquete {monto_id}"
            print(f"   Paquete {monto_id} ({package_name}): {count} PINs disponibles")
        
        print(f"\n🎉 Total de PINs de prueba creados: {pins_per_package * 5}")
        return True
        
    except Exception as e:
        print(f"❌ Error al crear PINs: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("🔧 CREANDO PINs DE PRUEBA")
    print("=" * 40)
    
    success = create_test_pins()
    
    if success:
        print("\n✅ PINs de prueba creados exitosamente")
        print("💡 Ahora puedes probar la API con: python test_simple_api.py")
    else:
        print("\n❌ Error al crear PINs de prueba")
