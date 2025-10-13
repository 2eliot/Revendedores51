#!/usr/bin/env python3
"""
Script para crear un usuario de prueba para la API
"""

import sqlite3
from werkzeug.security import generate_password_hash

def create_test_user():
    """Crea un usuario de prueba"""
    
    # Datos del usuario de prueba
    email = "test@ejemplo.com"
    password = "test123"
    nombre = "Usuario"
    apellido = "Prueba"
    telefono = "1234567890"
    saldo = 100.0  # Saldo inicial para pruebas
    
    # Hashear la contraseña
    password_hash = generate_password_hash(password)
    
    # Conectar a la base de datos
    conn = sqlite3.connect('usuarios.db')
    
    try:
        # Verificar si el usuario ya existe
        existing_user = conn.execute('SELECT id FROM usuarios WHERE correo = ?', (email,)).fetchone()
        
        if existing_user:
            print(f"✅ Usuario {email} ya existe")
            # Actualizar saldo si es necesario
            conn.execute('UPDATE usuarios SET saldo = ? WHERE correo = ?', (saldo, email))
            conn.commit()
            print(f"💰 Saldo actualizado a ${saldo}")
        else:
            # Crear el usuario
            conn.execute('''
                INSERT INTO usuarios (correo, contraseña, nombre, apellido, telefono, saldo)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (email, password_hash, nombre, apellido, telefono, saldo))
            conn.commit()
            print(f"✅ Usuario de prueba creado: {email}")
            print(f"🔑 Contraseña: {password}")
            print(f"💰 Saldo inicial: ${saldo}")
        
        # Verificar que se creó correctamente
        user = conn.execute('SELECT correo, nombre, apellido, saldo FROM usuarios WHERE correo = ?', (email,)).fetchone()
        if user:
            print(f"📋 Datos del usuario:")
            print(f"   Email: {user[0]}")
            print(f"   Nombre: {user[1]} {user[2]}")
            print(f"   Saldo: ${user[3]}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error al crear usuario: {str(e)}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("🔧 CREANDO USUARIO DE PRUEBA")
    print("=" * 40)
    
    success = create_test_user()
    
    if success:
        print("\n🎉 Usuario de prueba listo para usar")
        print("💡 Ahora puedes ejecutar: python test_simple_api.py")
    else:
        print("\n❌ Error al crear usuario de prueba")
