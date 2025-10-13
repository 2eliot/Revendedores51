import sqlite3
import os
from datetime import datetime, timedelta

def verificar_gestor_lotes():
    """Verifica el estado del gestor de lotes y pines"""
    
    if not os.path.exists('usuarios.db'):
        print("❌ ERROR: La base de datos no existe")
        return
    
    conn = sqlite3.connect('usuarios.db')
    cursor = conn.cursor()
    
    print("=" * 50)
    print("🔍 VERIFICACIÓN DEL GESTOR DE LOTES")
    print("=" * 50)
    print()
    
    # 1. Estado general de pines
    print("📌 ESTADO DE PINES:")
    cursor.execute('SELECT COUNT(*) FROM pines_freefire')
    total_pines = cursor.fetchone()[0]
    print(f"   Total de pines en la base de datos: {total_pines}")
    
    cursor.execute('SELECT COUNT(*) FROM pines_freefire WHERE usado = TRUE')
    pines_usados = cursor.fetchone()[0]
    print(f"   Pines ya utilizados: {pines_usados}")
    
    pines_disponibles = total_pines - pines_usados
    print(f"   Pines disponibles: {pines_disponibles}")
    print()
    
    # 2. Stock por tipo de paquete
    print("📦 STOCK POR TIPO DE PAQUETE:")
    cursor.execute('''
        SELECT monto_id, COUNT(*) 
        FROM pines_freefire 
        WHERE usado = FALSE 
        GROUP BY monto_id 
        ORDER BY monto_id
    ''')
    stock_por_tipo = cursor.fetchall()
    
    if stock_por_tipo:
        for monto_id, cantidad in stock_por_tipo:
            print(f"   Paquete ID {monto_id}: {cantidad} pines")
    else:
        print("   ⚠️  No hay pines disponibles en stock")
    print()
    
    # 3. Transacciones recientes
    print("💳 TRANSACCIONES RECIENTES (últimos 7 días):")
    cursor.execute('''
        SELECT COUNT(*) 
        FROM transacciones 
        WHERE fecha >= datetime('now', '-7 days')
    ''')
    transacciones_semana = cursor.fetchone()[0]
    print(f"   Transacciones en los últimos 7 días: {transacciones_semana}")
    
    # 4. Últimas transacciones con detalles
    cursor.execute('''
        SELECT t.fecha, u.nombre, u.apellido, t.monto, t.pin, t.numero_control
        FROM transacciones t
        JOIN usuarios u ON t.usuario_id = u.id
        ORDER BY t.fecha DESC
        LIMIT 5
    ''')
    ultimas_transacciones = cursor.fetchall()
    
    if ultimas_transacciones:
        print("   Últimas 5 transacciones:")
        for trans in ultimas_transacciones:
            fecha, nombre, apellido, monto, pin, control = trans
            pin_preview = pin[:20] + "..." if len(pin) > 20 else pin
            print(f"     • {fecha} - {nombre} {apellido} - ${abs(monto):.2f} - Control: {control}")
            print(f"       Pin: {pin_preview}")
    else:
        print("   ⚠️  No hay transacciones registradas")
    print()
    
    # 5. Usuarios activos
    print("👥 USUARIOS DEL SISTEMA:")
    cursor.execute('SELECT COUNT(*) FROM usuarios')
    total_usuarios = cursor.fetchone()[0]
    print(f"   Total de usuarios registrados: {total_usuarios}")
    
    cursor.execute('''
        SELECT u.nombre, u.apellido, u.saldo, COUNT(t.id) as transacciones
        FROM usuarios u 
        LEFT JOIN transacciones t ON u.id = t.usuario_id 
        GROUP BY u.id 
        ORDER BY transacciones DESC 
        LIMIT 5
    ''')
    usuarios_activos = cursor.fetchall()
    
    if usuarios_activos:
        print("   Top 5 usuarios con más transacciones:")
        for usuario in usuarios_activos:
            nombre, apellido, saldo, transacciones = usuario
            print(f"     • {nombre} {apellido}: {transacciones} transacciones - Saldo: ${saldo:.2f}")
    print()
    
    # 6. Verificar problemas potenciales
    print("🔧 DIAGNÓSTICO DE PROBLEMAS:")
    
    # Verificar pines duplicados
    cursor.execute('''
        SELECT pin_codigo, COUNT(*) as duplicados
        FROM pines_freefire 
        WHERE usado = FALSE
        GROUP BY pin_codigo, monto_id
        HAVING COUNT(*) > 1
    ''')
    pines_duplicados = cursor.fetchall()
    
    if pines_duplicados:
        print(f"   ⚠️  Se encontraron {len(pines_duplicados)} códigos de pines duplicados")
        for pin, count in pines_duplicados[:3]:  # Mostrar solo los primeros 3
            print(f"     • Pin {pin}: {count} duplicados")
    else:
        print("   ✅ No se encontraron pines duplicados")
    
    # Verificar transacciones sin pines
    cursor.execute('''
        SELECT COUNT(*) 
        FROM transacciones 
        WHERE pin IS NULL OR pin = ''
    ''')
    transacciones_sin_pin = cursor.fetchone()[0]
    
    if transacciones_sin_pin > 0:
        print(f"   ⚠️  {transacciones_sin_pin} transacciones sin código de pin")
    else:
        print("   ✅ Todas las transacciones tienen códigos de pin")
    
    # Verificar Blood Striker
    print()
    print("🎯 TRANSACCIONES BLOOD STRIKER:")
    cursor.execute('SELECT COUNT(*) FROM transacciones_bloodstriker WHERE estado = "pendiente"')
    bs_pendientes = cursor.fetchone()[0]
    print(f"   Transacciones pendientes: {bs_pendientes}")
    
    cursor.execute('SELECT COUNT(*) FROM transacciones_bloodstriker WHERE estado = "aprobado"')
    bs_aprobadas = cursor.fetchone()[0]
    print(f"   Transacciones aprobadas: {bs_aprobadas}")
    
    cursor.execute('SELECT COUNT(*) FROM transacciones_bloodstriker WHERE estado = "rechazado"')
    bs_rechazadas = cursor.fetchone()[0]
    print(f"   Transacciones rechazadas: {bs_rechazadas}")
    
    print()
    print("=" * 50)
    print("📋 RESUMEN:")
    
    if pines_disponibles == 0:
        print("❌ PROBLEMA CRÍTICO: No hay pines disponibles en stock")
        print("   Solución: Agregar pines usando el panel de administrador")
    elif pines_disponibles < 10:
        print("⚠️  ADVERTENCIA: Stock bajo de pines")
        print(f"   Solo quedan {pines_disponibles} pines disponibles")
    else:
        print("✅ Stock de pines: OK")
    
    if transacciones_semana == 0:
        print("⚠️  No hay actividad reciente en el sistema")
    else:
        print(f"✅ Sistema activo: {transacciones_semana} transacciones esta semana")
    
    if bs_pendientes > 0:
        print(f"⚠️  Hay {bs_pendientes} transacciones de Blood Striker pendientes de aprobación")
    
    print("=" * 50)
    
    conn.close()

if __name__ == "__main__":
    verificar_gestor_lotes()
