#!/usr/bin/env python3
"""
Script de prueba para las notificaciones de cartera
Simula la adición de créditos para probar la funcionalidad
"""

import sqlite3
import os
from datetime import datetime

DATABASE = 'usuarios.db'

def get_db_connection():
    """Obtiene una conexión a la base de datos"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def add_test_credit(user_id, amount):
    """Añade un crédito de prueba a un usuario"""
    conn = get_db_connection()
    
    # Crear tabla de créditos de billetera si no existe
    conn.execute('''
        CREATE TABLE IF NOT EXISTS creditos_billetera (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            monto REAL DEFAULT 0.0,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
            visto BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')
    
    # Agregar columna 'visto' si no existe
    try:
        conn.execute('ALTER TABLE creditos_billetera ADD COLUMN visto BOOLEAN DEFAULT FALSE')
        conn.commit()
    except:
        pass  # La columna ya existe
    
    # Actualizar saldo del usuario
    conn.execute('UPDATE usuarios SET saldo = saldo + ? WHERE id = ?', (amount, user_id))
    
    # Registrar en créditos de billetera
    conn.execute('''
        INSERT INTO creditos_billetera (usuario_id, monto, visto)
        VALUES (?, ?, FALSE)
    ''', (user_id, amount))
    
    conn.commit()
    conn.close()
    print(f"✅ Crédito de ${amount:.2f} agregado al usuario ID {user_id}")

def get_users():
    """Obtiene la lista de usuarios"""
    conn = get_db_connection()
    users = conn.execute('SELECT id, nombre, apellido, correo FROM usuarios WHERE id > 0').fetchall()
    conn.close()
    return users

def get_unread_credits_count(user_id):
    """Obtiene el número de créditos no vistos"""
    conn = get_db_connection()
    count = conn.execute('''
        SELECT COUNT(*) FROM creditos_billetera 
        WHERE usuario_id = ? AND (visto = FALSE OR visto IS NULL)
    ''', (user_id,)).fetchone()[0]
    conn.close()
    return count

def main():
    print("🧪 Script de Prueba - Notificaciones de Cartera")
    print("=" * 50)
    
    # Verificar si existe la base de datos
    if not os.path.exists(DATABASE):
        print("❌ Base de datos no encontrada. Ejecute la aplicación primero.")
        return
    
    # Obtener usuarios
    users = get_users()
    if not users:
        print("❌ No hay usuarios registrados. Registre un usuario primero.")
        return
    
    print("\n👥 Usuarios disponibles:")
    for user in users:
        unread_count = get_unread_credits_count(user['id'])
        print(f"  ID: {user['id']} - {user['nombre']} {user['apellido']} ({user['correo']}) - Notificaciones: {unread_count}")
    
    print("\n🎯 Opciones de prueba:")
    print("1. Agregar crédito de $5.00 a un usuario")
    print("2. Agregar crédito de $10.00 a un usuario")
    print("3. Agregar crédito personalizado")
    print("4. Salir")
    
    while True:
        try:
            opcion = input("\nSeleccione una opción (1-4): ").strip()
            
            if opcion == "4":
                print("👋 ¡Hasta luego!")
                break
            
            if opcion not in ["1", "2", "3"]:
                print("❌ Opción inválida. Intente nuevamente.")
                continue
            
            # Solicitar ID de usuario
            user_id = input("Ingrese el ID del usuario: ").strip()
            try:
                user_id = int(user_id)
            except ValueError:
                print("❌ ID de usuario inválido.")
                continue
            
            # Verificar que el usuario existe
            user_exists = any(user['id'] == user_id for user in users)
            if not user_exists:
                print("❌ Usuario no encontrado.")
                continue
            
            # Determinar monto según opción
            if opcion == "1":
                amount = 5.00
            elif opcion == "2":
                amount = 10.00
            elif opcion == "3":
                amount_str = input("Ingrese el monto a agregar: $").strip()
                try:
                    amount = float(amount_str)
                    if amount <= 0:
                        print("❌ El monto debe ser mayor a 0.")
                        continue
                except ValueError:
                    print("❌ Monto inválido.")
                    continue
            
            # Agregar crédito
            add_test_credit(user_id, amount)
            
            # Mostrar estado actualizado
            new_unread_count = get_unread_credits_count(user_id)
            print(f"🔔 El usuario ahora tiene {new_unread_count} notificaciones sin leer")
            print("\n💡 Para probar:")
            print("1. Inicie la aplicación: python app.py")
            print("2. Inicie sesión con el usuario")
            print("3. Observe la notificación verde en el botón de cartera")
            print("4. Haga clic en el botón de cartera para ver los créditos")
            print("5. La notificación desaparecerá después de ver la cartera")
            
        except KeyboardInterrupt:
            print("\n👋 ¡Hasta luego!")
            break
        except Exception as e:
            print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    main()
