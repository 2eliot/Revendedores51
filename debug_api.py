#!/usr/bin/env python3
"""
Script de depuración para la API
"""

import sqlite3
import hashlib
from werkzeug.security import check_password_hash

def get_db_connection():
    """Obtiene una conexión a la base de datos"""
    conn = sqlite3.connect('usuarios.db')
    conn.row_factory = sqlite3.Row
    return conn

def verify_password(password, hashed):
    """Verifica la contraseña hasheada (compatible con métodos antiguos y nuevos)"""
    print(f"🔍 Verificando contraseña:")
    print(f"   Password: {password}")
    print(f"   Hash: {hashed[:50]}...")
    
    # Intentar con Werkzeug (maneja pbkdf2, scrypt, etc.)
    if hashed.startswith(('pbkdf2:', 'scrypt:')):
        result = check_password_hash(hashed, password)
        print(f"   Método Werkzeug (pbkdf2/scrypt): {result}")
        return result
    
    # Si no es un hash de Werkzeug, verificar con SHA256 (método anterior)
    sha256_hash = hashlib.sha256(password.encode()).hexdigest()
    result = hashed == sha256_hash
    print(f"   Método SHA256: {result}")
    print(f"   SHA256 calculado: {sha256_hash[:50]}...")
    return result

def get_user_by_email(email):
    """Obtiene un usuario por su email"""
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM usuarios WHERE correo = ?', (email,)).fetchone()
    conn.close()
    return user

def debug_authentication():
    """Depura el proceso de autenticación"""
    email = "test@ejemplo.com"
    password = "test123"
    
    print("🔧 DEPURACIÓN DE AUTENTICACIÓN")
    print("=" * 50)
    
    # Obtener usuario
    user = get_user_by_email(email)
    
    if not user:
        print(f"❌ Usuario {email} no encontrado")
        return False
    
    print(f"✅ Usuario encontrado: {user['correo']}")
    print(f"   Nombre: {user['nombre']} {user['apellido']}")
    print(f"   Saldo: ${user['saldo']}")
    
    # Verificar contraseña
    password_valid = verify_password(password, user['contraseña'])
    
    if password_valid:
        print("✅ Contraseña válida")
        return True
    else:
        print("❌ Contraseña inválida")
        return False

if __name__ == "__main__":
    debug_authentication()
