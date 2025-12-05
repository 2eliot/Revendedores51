#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnóstico de Eliminación de Transacciones
Analiza las posibles causas de por qué se borra el historial de usuarios
"""

import sqlite3
import os
from datetime import datetime, timedelta

def get_db_connection():
    """Obtiene conexión a la base de datos"""
    DATABASE = 'usuarios.db'
    if os.environ.get('DATABASE_PATH'):
        DATABASE = os.environ.get('DATABASE_PATH')
    
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def analizar_problemas_eliminacion():
    """Analiza los problemas potenciales de eliminación de transacciones"""
    print("🔍 DIAGNÓSTICO: Análisis de Eliminación de Transacciones")
    print("=" * 60)
    
    conn = get_db_connection()
    
    # 1. Verificar si existe la función de limpieza automática
    print("\n1️⃣ LIMPIEZA AUTOMÁTICA DE TRANSACCIONES ANTIGUAS:")
    print("-" * 50)
    
    # Calcular fecha límite (1 semana atrás)
    fecha_limite = datetime.now() - timedelta(weeks=1)
    fecha_limite_str = fecha_limite.strftime('%Y-%m-%d %H:%M:%S')
    
    # Contar transacciones que serían eliminadas por la limpieza automática
    transacciones_antiguas = conn.execute('''
        SELECT COUNT(*) FROM transacciones 
        WHERE fecha < ?
    ''', (fecha_limite_str,)).fetchone()[0]
    
    print(f"📅 Fecha límite: {fecha_limite_str}")
    print(f"🗑️ Transacciones que serían eliminadas: {transacciones_antiguas}")
    
    if transacciones_antiguas > 0:
        print("⚠️ PROBLEMA IDENTIFICADO: La limpieza automática está eliminando transacciones")
        print("   Esta función se ejecuta cada vez que un usuario carga la página principal")
    
    # 2. Verificar límite de 30 transacciones por usuario
    print("\n2️⃣ LÍMITE DE 30 TRANSACCIONES POR USUARIO:")
    print("-" * 50)
    
    usuarios_con_exceso = conn.execute('''
        SELECT usuario_id, COUNT(*) as total_transacciones
        FROM transacciones 
        GROUP BY usuario_id 
        HAVING COUNT(*) > 30
        ORDER BY total_transacciones DESC
    ''').fetchall()
    
    if usuarios_con_exceso:
        print("⚠️ PROBLEMA IDENTIFICADO: Usuarios con más de 30 transacciones")
        for usuario in usuarios_con_exceso:
            print(f"   Usuario ID {usuario['usuario_id']}: {usuario['total_transacciones']} transacciones")
            
            # Calcular cuántas serían eliminadas
            transacciones_a_eliminar = usuario['total_transacciones'] - 30
            print(f"   → Se eliminarían {transacciones_a_eliminar} transacciones más antiguas")
    else:
        print("✅ No hay usuarios con más de 30 transacciones")
    
    # 3. Verificar distribución de transacciones por fecha
    print("\n3️⃣ DISTRIBUCIÓN DE TRANSACCIONES POR FECHA:")
    print("-" * 50)
    
    # Últimos 7 días
    for i in range(7):
        fecha = datetime.now() - timedelta(days=i)
        fecha_str = fecha.strftime('%Y-%m-%d')
        
        count = conn.execute('''
            SELECT COUNT(*) FROM transacciones 
            WHERE DATE(fecha) = ?
        ''', (fecha_str,)).fetchone()[0]
        
        dia_nombre = fecha.strftime('%A')
        print(f"   {fecha_str} ({dia_nombre}): {count} transacciones")
    
    # 4. Verificar transacciones más antiguas
    print("\n4️⃣ TRANSACCIONES MÁS ANTIGUAS:")
    print("-" * 50)
    
    transaccion_mas_antigua = conn.execute('''
        SELECT MIN(fecha) as fecha_mas_antigua FROM transacciones
    ''').fetchone()
    
    if transaccion_mas_antigua and transaccion_mas_antigua['fecha_mas_antigua']:
        print(f"📅 Transacción más antigua: {transaccion_mas_antigua['fecha_mas_antigua']}")
        
        # Calcular antigüedad
        try:
            fecha_antigua = datetime.strptime(transaccion_mas_antigua['fecha_mas_antigua'], '%Y-%m-%d %H:%M:%S')
            antiguedad = datetime.now() - fecha_antigua
            print(f"⏰ Antigüedad: {antiguedad.days} días")
            
            if antiguedad.days > 7:
                print("⚠️ PROBLEMA: Hay transacciones de más de 7 días que deberían haber sido eliminadas")
        except:
            print("❌ Error al calcular antigüedad")
    else:
        print("❌ No hay transacciones en la base de datos")
    
    # 5. Verificar usuarios específicos con pocas transacciones
    print("\n5️⃣ USUARIOS CON POCAS TRANSACCIONES:")
    print("-" * 50)
    
    usuarios_pocas_transacciones = conn.execute('''
        SELECT u.id, u.nombre, u.apellido, u.correo, COUNT(t.id) as total_transacciones
        FROM usuarios u
        LEFT JOIN transacciones t ON u.id = t.usuario_id
        GROUP BY u.id, u.nombre, u.apellido, u.correo
        HAVING COUNT(t.id) < 5
        ORDER BY total_transacciones ASC
    ''').fetchall()
    
    if usuarios_pocas_transacciones:
        print("👥 Usuarios con menos de 5 transacciones:")
        for usuario in usuarios_pocas_transacciones:
            print(f"   {usuario['nombre']} {usuario['apellido']} ({usuario['correo']}): {usuario['total_transacciones']} transacciones")
    else:
        print("✅ Todos los usuarios tienen 5 o más transacciones")
    
    # 6. Verificar total de transacciones en el sistema
    print("\n6️⃣ ESTADÍSTICAS GENERALES:")
    print("-" * 50)
    
    total_transacciones = conn.execute('SELECT COUNT(*) FROM transacciones').fetchone()[0]
    total_usuarios = conn.execute('SELECT COUNT(*) FROM usuarios').fetchone()[0]
    
    print(f"📊 Total de transacciones: {total_transacciones}")
    print(f"👥 Total de usuarios: {total_usuarios}")
    
    if total_usuarios > 0:
        promedio_transacciones = total_transacciones / total_usuarios
        print(f"📈 Promedio de transacciones por usuario: {promedio_transacciones:.2f}")
    
    conn.close()

def simular_limpieza_automatica():
    """Simula la limpieza automática para ver qué se eliminaría"""
    print("\n🧪 SIMULACIÓN DE LIMPIEZA AUTOMÁTICA:")
    print("=" * 60)
    
    conn = get_db_connection()
    
    # Calcular fecha límite (1 semana atrás)
    fecha_limite = datetime.now() - timedelta(weeks=1)
    fecha_limite_str = fecha_limite.strftime('%Y-%m-%d %H:%M:%S')
    
    print(f"📅 Fecha límite: {fecha_limite_str}")
    
    # Obtener transacciones que serían eliminadas
    transacciones_a_eliminar = conn.execute('''
        SELECT t.*, u.nombre, u.apellido, u.correo
        FROM transacciones t
        JOIN usuarios u ON t.usuario_id = u.id
        WHERE t.fecha < ?
        ORDER BY t.fecha DESC
    ''', (fecha_limite_str,)).fetchall()
    
    if transacciones_a_eliminar:
        print(f"🗑️ Se eliminarían {len(transacciones_a_eliminar)} transacciones:")
        print("\nDetalle de transacciones que se eliminarían:")
        for trans in transacciones_a_eliminar[:10]:  # Mostrar solo las primeras 10
            print(f"   - Usuario: {trans['nombre']} {trans['apellido']}")
            print(f"     Fecha: {trans['fecha']}")
            print(f"     Monto: ${abs(trans['monto']):.2f}")
            print(f"     Control: {trans['numero_control']}")
            print()
        
        if len(transacciones_a_eliminar) > 10:
            print(f"   ... y {len(transacciones_a_eliminar) - 10} más")
    else:
        print("✅ No hay transacciones que serían eliminadas por la limpieza automática")
    
    conn.close()

def verificar_configuracion_actual():
    """Verifica la configuración actual que podría estar causando problemas"""
    print("\n⚙️ CONFIGURACIÓN ACTUAL:")
    print("=" * 60)
    
    print("🔧 Configuraciones problemáticas identificadas:")
    print("   1. Limpieza automática se ejecuta en CADA carga de página principal")
    print("   2. Límite de 30 transacciones por usuario se aplica en CADA compra")
    print("   3. Limpieza de transacciones de más de 1 semana es muy agresiva")
    
    print("\n💡 RECOMENDACIONES:")
    print("   1. Cambiar limpieza automática para que se ejecute solo 1 vez al día")
    print("   2. Aumentar límite de transacciones por usuario (de 30 a 100)")
    print("   3. Cambiar período de limpieza de 1 semana a 1 mes")
    print("   4. Agregar logs para rastrear cuándo se eliminan transacciones")

if __name__ == "__main__":
    try:
        analizar_problemas_eliminacion()
        simular_limpieza_automatica()
        verificar_configuracion_actual()
        
        print("\n" + "=" * 60)
        print("✅ DIAGNÓSTICO COMPLETADO")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error durante el diagnóstico: {e}")
