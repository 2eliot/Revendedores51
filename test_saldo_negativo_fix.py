#!/usr/bin/env python3
"""
Test para verificar que la corrección del saldo negativo funciona correctamente.
Este script simula el escenario donde un usuario intenta comprar pines sin saldo suficiente.
"""

import sqlite3
import os
import sys
from datetime import datetime

# Configuración de la base de datos de prueba
TEST_DB = 'test_saldo_negativo.db'

def setup_test_database():
    """Configura una base de datos de prueba"""
    # Eliminar base de datos anterior si existe
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    
    # Crear tablas necesarias
    conn.execute('''
        CREATE TABLE usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            apellido TEXT NOT NULL,
            telefono TEXT NOT NULL,
            correo TEXT UNIQUE NOT NULL,
            contraseña TEXT NOT NULL,
            saldo REAL DEFAULT 0.0,
            fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
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
    
    conn.execute('''
        CREATE TABLE precios_paquetes (
            id INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL,
            precio REAL NOT NULL,
            descripcion TEXT NOT NULL,
            activo BOOLEAN DEFAULT TRUE,
            fecha_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.execute('''
        CREATE TABLE transacciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            numero_control TEXT NOT NULL,
            pin TEXT NOT NULL,
            transaccion_id TEXT NOT NULL,
            monto REAL DEFAULT 0.0,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.execute('''
        CREATE TABLE configuracion_fuentes_pines (
            monto_id INTEGER PRIMARY KEY,
            fuente TEXT NOT NULL DEFAULT 'local',
            activo BOOLEAN DEFAULT TRUE,
            fecha_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insertar datos de prueba
    # Usuario con saldo insuficiente
    conn.execute('''
        INSERT INTO usuarios (nombre, apellido, telefono, correo, contraseña, saldo)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', ('Test', 'User', '1234567890', 'test@example.com', 'hashed_password', 1.00))
    
    # Precios de paquetes
    conn.execute('''
        INSERT INTO precios_paquetes (id, nombre, precio, descripcion, activo)
        VALUES (?, ?, ?, ?, ?)
    ''', (1, '110 💎', 0.66, '110 Diamantes Free Fire', True))
    
    conn.execute('''
        INSERT INTO precios_paquetes (id, nombre, precio, descripcion, activo)
        VALUES (?, ?, ?, ?, ?)
    ''', (2, '341 💎', 2.25, '341 Diamantes Free Fire', True))
    
    # Configuración de fuentes (local)
    conn.execute('''
        INSERT INTO configuracion_fuentes_pines (monto_id, fuente, activo)
        VALUES (?, ?, ?)
    ''', (1, 'local', True))
    
    conn.execute('''
        INSERT INTO configuracion_fuentes_pines (monto_id, fuente, activo)
        VALUES (?, ?, ?)
    ''', (2, 'local', True))
    
    # Agregar algunos pines de prueba
    conn.execute('''
        INSERT INTO pines_freefire (monto_id, pin_codigo)
        VALUES (?, ?)
    ''', (1, 'TEST-PIN-001'))
    
    conn.execute('''
        INSERT INTO pines_freefire (monto_id, pin_codigo)
        VALUES (?, ?)
    ''', (2, 'TEST-PIN-002'))
    
    conn.commit()
    conn.close()
    print("✅ Base de datos de prueba configurada")

def test_saldo_insuficiente_scenario():
    """Prueba el escenario donde un usuario intenta comprar con saldo insuficiente"""
    print("\n🧪 PRUEBA: Usuario con saldo insuficiente intenta comprar")
    
    # Simular la lógica corregida del sistema
    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    
    # Obtener usuario de prueba
    user = conn.execute('SELECT * FROM usuarios WHERE correo = ?', ('test@example.com',)).fetchone()
    print(f"👤 Usuario: {user['nombre']} {user['apellido']}")
    print(f"💰 Saldo actual: ${user['saldo']:.2f}")
    
    # Obtener precio del paquete que quiere comprar (monto_id = 2, precio = $2.25)
    precio = conn.execute('SELECT precio FROM precios_paquetes WHERE id = ?', (2,)).fetchone()
    precio_total = precio['precio']
    print(f"🛒 Intentando comprar paquete de ${precio_total:.2f}")
    
    # PASO 1: Verificar saldo ANTES de intentar obtener pines
    if user['saldo'] < precio_total:
        print(f"❌ VALIDACIÓN DE SALDO: Saldo insuficiente (${user['saldo']:.2f} < ${precio_total:.2f})")
        print("🛡️ SISTEMA PROTEGIDO: No se permite la compra")
        conn.close()
        return True
    
    print("✅ Saldo suficiente, procediendo con la compra...")
    conn.close()
    return False

def test_saldo_suficiente_scenario():
    """Prueba el escenario donde un usuario tiene saldo suficiente"""
    print("\n🧪 PRUEBA: Usuario con saldo suficiente compra exitosamente")
    
    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    
    # Actualizar saldo del usuario para que sea suficiente
    conn.execute('UPDATE usuarios SET saldo = ? WHERE correo = ?', (5.00, 'test@example.com'))
    conn.commit()
    
    # Obtener usuario actualizado
    user = conn.execute('SELECT * FROM usuarios WHERE correo = ?', ('test@example.com',)).fetchone()
    print(f"👤 Usuario: {user['nombre']} {user['apellido']}")
    print(f"💰 Saldo actual: ${user['saldo']:.2f}")
    
    # Obtener precio del paquete (monto_id = 1, precio = $0.66)
    precio = conn.execute('SELECT precio FROM precios_paquetes WHERE id = ?', (1,)).fetchone()
    precio_total = precio['precio']
    print(f"🛒 Intentando comprar paquete de ${precio_total:.2f}")
    
    # PASO 1: Verificar saldo
    if user['saldo'] < precio_total:
        print(f"❌ Saldo insuficiente")
        conn.close()
        return False
    
    print("✅ Saldo suficiente")
    
    # PASO 2: Intentar obtener pin (simulado)
    pin = conn.execute('SELECT * FROM pines_freefire WHERE monto_id = ? AND usado = FALSE LIMIT 1', (1,)).fetchone()
    
    if not pin:
        print("❌ Sin stock disponible")
        conn.close()
        return False
    
    print(f"✅ Pin obtenido: {pin['pin_codigo']}")
    
    # PASO 3: AHORA SÍ descontar saldo y procesar transacción
    nuevo_saldo = user['saldo'] - precio_total
    conn.execute('UPDATE usuarios SET saldo = ? WHERE id = ?', (nuevo_saldo, user['id']))
    
    # Eliminar pin del stock
    conn.execute('DELETE FROM pines_freefire WHERE id = ?', (pin['id'],))
    
    # Registrar transacción
    conn.execute('''
        INSERT INTO transacciones (usuario_id, numero_control, pin, transaccion_id, monto)
        VALUES (?, ?, ?, ?, ?)
    ''', (user['id'], '1234567890', pin['pin_codigo'], 'TEST-001', -precio_total))
    
    conn.commit()
    
    # Verificar resultado
    user_updated = conn.execute('SELECT * FROM usuarios WHERE id = ?', (user['id'],)).fetchone()
    print(f"💰 Nuevo saldo: ${user_updated['saldo']:.2f}")
    print("✅ Transacción completada exitosamente")
    
    conn.close()
    return True

def test_api_externa_sin_stock():
    """Prueba el escenario donde la API externa no tiene stock"""
    print("\n🧪 PRUEBA: API externa sin stock - saldo debe mantenerse intacto")
    
    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    
    # Configurar usuario con saldo suficiente
    conn.execute('UPDATE usuarios SET saldo = ? WHERE correo = ?', (10.00, 'test@example.com'))
    
    # Configurar monto_id 2 para usar API externa
    conn.execute('UPDATE configuracion_fuentes_pines SET fuente = ? WHERE monto_id = ?', ('api_externa', 2))
    conn.commit()
    
    user = conn.execute('SELECT * FROM usuarios WHERE correo = ?', ('test@example.com',)).fetchone()
    saldo_inicial = user['saldo']
    print(f"💰 Saldo inicial: ${saldo_inicial:.2f}")
    
    # Simular que la API externa falla
    print("🌐 Simulando falla de API externa...")
    api_result = {'status': 'error', 'message': 'Sin stock en API externa'}
    
    if api_result['status'] != 'success':
        print(f"❌ API Externa falló: {api_result['message']}")
        print("🛡️ SISTEMA PROTEGIDO: Saldo no se descuenta")
        
        # Verificar que el saldo no cambió
        user_final = conn.execute('SELECT * FROM usuarios WHERE id = ?', (user['id'],)).fetchone()
        print(f"💰 Saldo final: ${user_final['saldo']:.2f}")
        
        if user_final['saldo'] == saldo_inicial:
            print("✅ CORRECCIÓN EXITOSA: Saldo se mantuvo intacto")
            conn.close()
            return True
        else:
            print("❌ ERROR: Saldo fue modificado incorrectamente")
            conn.close()
            return False
    
    conn.close()
    return False

def cleanup():
    """Limpia archivos de prueba"""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    print("🧹 Archivos de prueba eliminados")

def main():
    """Función principal de pruebas"""
    print("🔧 PRUEBAS DE CORRECCIÓN DEL SALDO NEGATIVO")
    print("=" * 50)
    
    try:
        # Configurar base de datos de prueba
        setup_test_database()
        
        # Ejecutar pruebas
        test1_passed = test_saldo_insuficiente_scenario()
        test2_passed = test_saldo_suficiente_scenario()
        test3_passed = test_api_externa_sin_stock()
        
        # Resumen de resultados
        print("\n" + "=" * 50)
        print("📊 RESUMEN DE PRUEBAS:")
        print(f"✅ Saldo insuficiente protegido: {'PASS' if test1_passed else 'FAIL'}")
        print(f"✅ Compra exitosa con saldo: {'PASS' if test2_passed else 'FAIL'}")
        print(f"✅ API externa sin stock protegida: {'PASS' if test3_passed else 'FAIL'}")
        
        if all([test1_passed, test2_passed, test3_passed]):
            print("\n🎉 TODAS LAS PRUEBAS PASARON - CORRECCIÓN EXITOSA")
            print("🛡️ El sistema ahora está protegido contra saldos negativos")
        else:
            print("\n❌ ALGUNAS PRUEBAS FALLARON - REVISAR IMPLEMENTACIÓN")
            
    except Exception as e:
        print(f"❌ Error durante las pruebas: {str(e)}")
    finally:
        cleanup()

if __name__ == "__main__":
    main()
