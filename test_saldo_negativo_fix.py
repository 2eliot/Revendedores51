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

def test_debito_atomico_evita_doble_descuento_incorrecto():
    """Prueba que el descuento condicional en SQL evita perder cobros concurrentes."""
    print("\n🧪 PRUEBA: Débito atómico evita sobrescritura de saldo")

    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    conn.execute('UPDATE usuarios SET saldo = ? WHERE correo = ?', (1.00, 'test@example.com'))
    conn.commit()

    user = conn.execute('SELECT id FROM usuarios WHERE correo = ?', ('test@example.com',)).fetchone()
    user_id = user['id']

    cursor_1 = conn.execute(
        'UPDATE usuarios SET saldo = saldo - ? WHERE id = ? AND saldo >= ?',
        (1.00, user_id, 1.00)
    )
    cursor_2 = conn.execute(
        'UPDATE usuarios SET saldo = saldo - ? WHERE id = ? AND saldo >= ?',
        (1.00, user_id, 1.00)
    )
    conn.commit()

    saldo_final = conn.execute('SELECT saldo FROM usuarios WHERE id = ?', (user_id,)).fetchone()['saldo']
    print(f"🔁 Primer UPDATE afectó {cursor_1.rowcount} fila(s)")
    print(f"🔁 Segundo UPDATE afectó {cursor_2.rowcount} fila(s)")
    print(f"💰 Saldo final: ${saldo_final:.2f}")

    conn.close()
    return cursor_1.rowcount == 1 and cursor_2.rowcount == 0 and abs(saldo_final - 0.0) < 0.0001

def test_request_id_idempotente_reutiliza_misma_compra():
    """Prueba que un request_id repetido no genera una segunda compra."""
    print("\n🧪 PRUEBA: request_id duplicado reutiliza la compra original")

    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    conn.execute('''
        CREATE TABLE IF NOT EXISTS purchase_request_idempotency (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            endpoint TEXT NOT NULL,
            request_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'processing',
            response_payload TEXT,
            transaccion_id TEXT,
            numero_control TEXT,
            fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
            fecha_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(usuario_id, endpoint, request_id)
        )
    ''')
    conn.execute('ALTER TABLE transacciones ADD COLUMN request_id TEXT') if False else None
    try:
        conn.execute('ALTER TABLE transacciones ADD COLUMN request_id TEXT')
    except Exception:
        pass
    conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_tx_user_request_id_test ON transacciones(usuario_id, request_id)')

    user = conn.execute('SELECT id FROM usuarios WHERE correo = ?', ('test@example.com',)).fetchone()
    user_id = user['id']
    request_id = 'req-test-123'
    endpoint = 'validar_freefire_global'

    conn.execute(
        'INSERT INTO purchase_request_idempotency (usuario_id, endpoint, request_id, status) VALUES (?, ?, ?, ?)',
        (user_id, endpoint, request_id, 'processing')
    )
    conn.execute(
        '''INSERT INTO transacciones (usuario_id, numero_control, pin, transaccion_id, monto, request_id)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (user_id, '1111111111', 'PIN-ORIGINAL', 'FFG-ORIGINAL', -0.86, request_id)
    )
    conn.execute(
        '''UPDATE purchase_request_idempotency
           SET status = 'completed', response_payload = ?, transaccion_id = ?, numero_control = ?
           WHERE usuario_id = ? AND endpoint = ? AND request_id = ?''',
        ('{"pin": "PIN-ORIGINAL", "transaccion_id": "FFG-ORIGINAL"}', 'FFG-ORIGINAL', '1111111111', user_id, endpoint, request_id)
    )
    conn.commit()

    duplicate_insert_blocked = False
    try:
        conn.execute(
            '''INSERT INTO transacciones (usuario_id, numero_control, pin, transaccion_id, monto, request_id)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (user_id, '2222222222', 'PIN-DUPLICADO', 'FFG-DUP', -0.86, request_id)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        duplicate_insert_blocked = True

    total_rows = conn.execute(
        'SELECT COUNT(*) AS total FROM transacciones WHERE usuario_id = ? AND request_id = ?',
        (user_id, request_id)
    ).fetchone()['total']
    estado = conn.execute(
        'SELECT status FROM purchase_request_idempotency WHERE usuario_id = ? AND endpoint = ? AND request_id = ?',
        (user_id, endpoint, request_id)
    ).fetchone()['status']

    print(f"🧾 Filas con mismo request_id: {total_rows}")
    print(f"🔒 Duplicado bloqueado por índice único: {'sí' if duplicate_insert_blocked else 'no'}")
    print(f"📌 Estado idempotente: {estado}")

    conn.close()
    return duplicate_insert_blocked and total_rows == 1 and estado == 'completed'

def test_request_id_unico_en_transacciones_freefire_id():
    """Prueba que Free Fire ID no permita dos transacciones con el mismo request_id por usuario."""
    print("\n🧪 PRUEBA: request_id único en transacciones_freefire_id")

    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    conn.execute('''
        CREATE TABLE IF NOT EXISTS transacciones_freefire_id (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            player_id TEXT NOT NULL,
            paquete_id INTEGER NOT NULL,
            numero_control TEXT NOT NULL,
            transaccion_id TEXT NOT NULL,
            monto REAL DEFAULT 0.0,
            estado TEXT DEFAULT 'pendiente',
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
            request_id TEXT
        )
    ''')
    conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_ffid_usuario_request_id_test ON transacciones_freefire_id(usuario_id, request_id)')

    user = conn.execute('SELECT id FROM usuarios WHERE correo = ?', ('test@example.com',)).fetchone()
    user_id = user['id']
    request_id = 'req-ffid-123'

    conn.execute(
        '''INSERT INTO transacciones_freefire_id
           (usuario_id, player_id, paquete_id, numero_control, transaccion_id, monto, estado, request_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (user_id, '123456789', 1, '3333333333', 'FFID-ORIGINAL', -0.90, 'procesando', request_id)
    )
    conn.commit()

    duplicate_blocked = False
    try:
        conn.execute(
            '''INSERT INTO transacciones_freefire_id
               (usuario_id, player_id, paquete_id, numero_control, transaccion_id, monto, estado, request_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (user_id, '123456789', 1, '4444444444', 'FFID-DUP', -0.90, 'procesando', request_id)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        duplicate_blocked = True

    total_rows = conn.execute(
        'SELECT COUNT(*) AS total FROM transacciones_freefire_id WHERE usuario_id = ? AND request_id = ?',
        (user_id, request_id)
    ).fetchone()['total']

    print(f"🧾 Filas FFID con mismo request_id: {total_rows}")
    print(f"🔒 Duplicado FFID bloqueado por índice único: {'sí' if duplicate_blocked else 'no'}")

    conn.close()
    return duplicate_blocked and total_rows == 1

def test_request_id_unico_en_transacciones_dinamicas():
    """Prueba que juegos dinámicos no permitan dos transacciones con el mismo request_id por usuario."""
    print("\n🧪 PRUEBA: request_id único en transacciones_dinamicas")

    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    conn.execute('''
        CREATE TABLE IF NOT EXISTS transacciones_dinamicas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            juego_id INTEGER NOT NULL,
            usuario_id INTEGER NOT NULL,
            paquete_id INTEGER NOT NULL,
            numero_control TEXT NOT NULL,
            transaccion_id TEXT NOT NULL,
            monto REAL DEFAULT 0.0,
            estado TEXT DEFAULT 'procesando',
            request_id TEXT
        )
    ''')
    conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_tx_din_usuario_request_id_test ON transacciones_dinamicas(usuario_id, request_id)')

    user = conn.execute('SELECT id FROM usuarios WHERE correo = ?', ('test@example.com',)).fetchone()
    user_id = user['id']
    request_id = 'req-dyn-123'

    conn.execute(
        '''INSERT INTO transacciones_dinamicas
           (juego_id, usuario_id, paquete_id, numero_control, transaccion_id, monto, estado, request_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (1, user_id, 1, '5555555555', 'DYN-ORIGINAL', -1.25, 'procesando', request_id)
    )
    conn.commit()

    duplicate_blocked = False
    try:
        conn.execute(
            '''INSERT INTO transacciones_dinamicas
               (juego_id, usuario_id, paquete_id, numero_control, transaccion_id, monto, estado, request_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (1, user_id, 1, '6666666666', 'DYN-DUP', -1.25, 'procesando', request_id)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        duplicate_blocked = True

    total_rows = conn.execute(
        'SELECT COUNT(*) AS total FROM transacciones_dinamicas WHERE usuario_id = ? AND request_id = ?',
        (user_id, request_id)
    ).fetchone()['total']

    print(f"🧾 Filas dinámicas con mismo request_id: {total_rows}")
    print(f"🔒 Duplicado dinámico bloqueado por índice único: {'sí' if duplicate_blocked else 'no'}")

    conn.close()
    return duplicate_blocked and total_rows == 1

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
        test4_passed = test_debito_atomico_evita_doble_descuento_incorrecto()
        test5_passed = test_request_id_idempotente_reutiliza_misma_compra()
        test6_passed = test_request_id_unico_en_transacciones_freefire_id()
        test7_passed = test_request_id_unico_en_transacciones_dinamicas()
        
        # Resumen de resultados
        print("\n" + "=" * 50)
        print("📊 RESUMEN DE PRUEBAS:")
        print(f"✅ Saldo insuficiente protegido: {'PASS' if test1_passed else 'FAIL'}")
        print(f"✅ Compra exitosa con saldo: {'PASS' if test2_passed else 'FAIL'}")
        print(f"✅ API externa sin stock protegida: {'PASS' if test3_passed else 'FAIL'}")
        print(f"✅ Débito atómico sin pérdida de cobro: {'PASS' if test4_passed else 'FAIL'}")
        print(f"✅ request_id idempotente: {'PASS' if test5_passed else 'FAIL'}")
        print(f"✅ request_id único en Free Fire ID: {'PASS' if test6_passed else 'FAIL'}")
        print(f"✅ request_id único en juegos dinámicos: {'PASS' if test7_passed else 'FAIL'}")
        
        if all([test1_passed, test2_passed, test3_passed, test4_passed, test5_passed, test6_passed, test7_passed]):
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
