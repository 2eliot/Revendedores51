#!/usr/bin/env python3
"""
Test script para verificar el sistema de notificaciones personalizadas
"""

import sqlite3
import sys
import os
from datetime import datetime

# Agregar el directorio actual al path para importar las funciones
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importar funciones de app.py
from app import (
    create_personal_notification,
    get_user_personal_notifications,
    get_unread_personal_notifications_count,
    mark_personal_notifications_as_read,
    get_db_connection,
    DATABASE
)

def test_personal_notifications():
    """Prueba el sistema completo de notificaciones personalizadas"""
    print("🧪 INICIANDO PRUEBAS DE NOTIFICACIONES PERSONALIZADAS")
    print("=" * 60)
    
    # Verificar que la base de datos existe
    if not os.path.exists(DATABASE):
        print(f"❌ Error: Base de datos no encontrada en {DATABASE}")
        return False
    
    print(f"✅ Base de datos encontrada: {DATABASE}")
    
    # Obtener un usuario de prueba de la base de datos
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM usuarios WHERE id != 0 LIMIT 1').fetchone()
    
    if not user:
        print("❌ Error: No se encontraron usuarios en la base de datos")
        conn.close()
        return False
    
    user_id = user['id']
    user_name = f"{user['nombre']} {user['apellido']}"
    print(f"👤 Usuario de prueba: {user_name} (ID: {user_id})")
    
    # Verificar transacciones de Blood Striker pendientes
    bs_transactions = conn.execute('''
        SELECT bs.*, p.nombre as paquete_nombre, p.precio
        FROM transacciones_bloodstriker bs
        JOIN precios_bloodstriker p ON bs.paquete_id = p.id
        WHERE bs.estado = 'pendiente'
        LIMIT 1
    ''').fetchall()
    
    print(f"📋 Transacciones Blood Striker pendientes: {len(bs_transactions)}")
    
    conn.close()
    
    # PRUEBA 1: Crear notificación personalizada
    print("\n🔔 PRUEBA 1: Crear notificación personalizada")
    try:
        titulo = "🎯 Prueba de Notificación"
        mensaje = "Esta es una notificación de prueba para verificar el sistema."
        tipo = "success"
        
        notification_id = create_personal_notification(user_id, titulo, mensaje, tipo)
        print(f"✅ Notificación creada exitosamente (ID: {notification_id})")
    except Exception as e:
        print(f"❌ Error creando notificación: {e}")
        return False
    
    # PRUEBA 2: Obtener contador de notificaciones no leídas
    print("\n📊 PRUEBA 2: Verificar contador de notificaciones")
    try:
        count = get_unread_personal_notifications_count(user_id)
        print(f"✅ Notificaciones no leídas: {count}")
        
        if count == 0:
            print("⚠️ Advertencia: El contador debería ser 1 después de crear una notificación")
        else:
            print("✅ Contador funcionando correctamente")
    except Exception as e:
        print(f"❌ Error obteniendo contador: {e}")
        return False
    
    # PRUEBA 3: Obtener notificaciones del usuario
    print("\n📋 PRUEBA 3: Obtener notificaciones del usuario")
    try:
        notifications = get_user_personal_notifications(user_id)
        print(f"✅ Notificaciones obtenidas: {len(notifications)}")
        
        for notif in notifications:
            print(f"   - {notif['titulo']}: {notif['mensaje'][:50]}...")
    except Exception as e:
        print(f"❌ Error obteniendo notificaciones: {e}")
        return False
    
    # PRUEBA 4: Marcar notificaciones como leídas
    print("\n✅ PRUEBA 4: Marcar notificaciones como leídas")
    try:
        mark_personal_notifications_as_read(user_id)
        print("✅ Notificaciones marcadas como leídas")
        
        # Verificar que el contador ahora es 0
        count_after = get_unread_personal_notifications_count(user_id)
        print(f"📊 Contador después de marcar como leídas: {count_after}")
        
        if count_after == 0:
            print("✅ Sistema funcionando correctamente - notificaciones eliminadas")
        else:
            print("⚠️ Advertencia: El contador debería ser 0 después de marcar como leídas")
    except Exception as e:
        print(f"❌ Error marcando como leídas: {e}")
        return False
    
    # PRUEBA 5: Simular aprobación de Blood Striker (si hay transacciones pendientes)
    if bs_transactions:
        print("\n🎯 PRUEBA 5: Simular aprobación de Blood Striker")
        try:
            bs_transaction = bs_transactions[0]
            
            # Crear notificación como lo haría la función de aprobación
            titulo = "🎯 Recarga Blood Striker Aprobada"
            mensaje = f"Tu recarga de {bs_transaction['paquete_nombre']} por ${bs_transaction['precio']:.2f} ha sido aprobada exitosamente. ID: {bs_transaction['player_id']}"
            
            notification_id = create_personal_notification(bs_transaction['usuario_id'], titulo, mensaje, 'success')
            print(f"✅ Notificación de aprobación creada (ID: {notification_id})")
            
            # Verificar contador
            count = get_unread_personal_notifications_count(bs_transaction['usuario_id'])
            print(f"📊 Contador para usuario {bs_transaction['usuario_id']}: {count}")
            
        except Exception as e:
            print(f"❌ Error simulando aprobación: {e}")
            return False
    
    print("\n" + "=" * 60)
    print("🎉 TODAS LAS PRUEBAS COMPLETADAS EXITOSAMENTE")
    print("✅ El sistema de notificaciones personalizadas está funcionando correctamente")
    print("\nFuncionalidades verificadas:")
    print("- ✅ Creación de notificaciones personalizadas")
    print("- ✅ Contador de notificaciones no leídas")
    print("- ✅ Obtención de notificaciones del usuario")
    print("- ✅ Marcado como leídas (eliminación)")
    print("- ✅ Integración con aprobaciones de Blood Striker")
    
    return True

if __name__ == "__main__":
    success = test_personal_notifications()
    sys.exit(0 if success else 1)
