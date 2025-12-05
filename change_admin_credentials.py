#!/usr/bin/env python3
"""
Script para cambiar las credenciales de administrador de INEFABLE STORE
Ejecutar este script para cambiar el email y contraseña del administrador
"""

import os
import getpass
import secrets

def change_admin_credentials():
    """
    Cambia las credenciales de administrador
    """
    print("🔑 CAMBIAR CREDENCIALES DE ADMINISTRADOR")
    print("=" * 40)
    
    # Solicitar nuevo email
    while True:
        new_email = input("Nuevo email de administrador: ").strip()
        if new_email and "@" in new_email:
            break
        print("❌ Por favor ingresa un email válido")
    
    # Opciones para la contraseña
    print("\nOpciones para la contraseña:")
    print("1. Generar contraseña aleatoria segura (recomendado)")
    print("2. Ingresar contraseña personalizada")
    
    while True:
        opcion = input("Selecciona una opción (1 o 2): ").strip()
        if opcion in ['1', '2']:
            break
        print("❌ Por favor selecciona 1 o 2")
    
    if opcion == '1':
        # Generar contraseña aleatoria
        new_password = secrets.token_urlsafe(16)
        print(f"\n🔐 Contraseña generada: {new_password}")
        print("⚠️ GUARDA ESTA CONTRASEÑA EN UN LUGAR SEGURO")
    else:
        # Contraseña personalizada
        while True:
            new_password = getpass.getpass("Nueva contraseña: ")
            confirm_password = getpass.getpass("Confirmar contraseña: ")
            
            if new_password == confirm_password:
                if len(new_password) >= 8:
                    break
                else:
                    print("❌ La contraseña debe tener al menos 8 caracteres")
            else:
                print("❌ Las contraseñas no coinciden")
    
    # Mostrar comandos para configurar variables de entorno
    print("\n🛡️ CONFIGURAR VARIABLES DE ENTORNO:")
    print("=" * 35)
    print("Ejecuta estos comandos en tu servidor:")
    print(f"export ADMIN_EMAIL='{new_email}'")
    print(f"export ADMIN_PASSWORD='{new_password}'")
    
    # Para Windows
    print("\nEn Windows (CMD):")
    print(f"set ADMIN_EMAIL={new_email}")
    print(f"set ADMIN_PASSWORD={new_password}")
    
    # Para Windows (PowerShell)
    print("\nEn Windows (PowerShell):")
    print(f"$env:ADMIN_EMAIL='{new_email}'")
    print(f"$env:ADMIN_PASSWORD='{new_password}'")
    
    # Crear archivo .env local (opcional)
    create_env = input("\n¿Crear archivo .env local para desarrollo? (s/n): ").strip().lower()
    
    if create_env in ['s', 'si', 'y', 'yes']:
        env_content = f"""# Variables de entorno para desarrollo local
# NO SUBIR ESTE ARCHIVO A REPOSITORIOS PÚBLICOS

ADMIN_EMAIL={new_email}
ADMIN_PASSWORD={new_password}

# Otras variables (generar con production_config.py)
# SECRET_KEY=tu_clave_secreta
# ENCRYPTION_KEY=tu_clave_encriptacion
# DATABASE_PATH=usuarios.db
# FLASK_ENV=development
# FLASK_DEBUG=True
"""
        
        with open('.env', 'w') as f:
            f.write(env_content)
        
        print("✅ Archivo .env creado")
        print("⚠️ IMPORTANTE: Agrega .env a tu .gitignore")
        
        # Crear .gitignore si no existe
        gitignore_content = """
# Variables de entorno
.env
.env.local
.env.production

# Base de datos
*.db
usuarios.db

# Backups
backups/
*.gz

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.venv/

# Logs
logs/
*.log
"""
        
        if not os.path.exists('.gitignore'):
            with open('.gitignore', 'w') as f:
                f.write(gitignore_content)
            print("✅ Archivo .gitignore creado")
    
    print("\n✅ CREDENCIALES ACTUALIZADAS")
    print("=" * 25)
    print(f"Email: {new_email}")
    print(f"Contraseña: {'*' * len(new_password)}")
    
    print("\n📝 PRÓXIMOS PASOS:")
    print("1. Configurar las variables de entorno en tu servidor")
    print("2. Reiniciar la aplicación")
    print("3. Probar el login con las nuevas credenciales")
    print("4. Eliminar las credenciales por defecto del código (si las hay)")
    
    return new_email, new_password

def test_credentials():
    """
    Prueba las credenciales configuradas
    """
    admin_email = os.environ.get('ADMIN_EMAIL')
    admin_password = os.environ.get('ADMIN_PASSWORD')
    
    if admin_email and admin_password:
        print("✅ Variables de entorno configuradas:")
        print(f"ADMIN_EMAIL: {admin_email}")
        print(f"ADMIN_PASSWORD: {'*' * len(admin_password)}")
    else:
        print("❌ Variables de entorno no configuradas")
        print("Ejecuta el script para configurar las credenciales")

if __name__ == "__main__":
    print("INEFABLE STORE - Gestión de Credenciales de Administrador")
    print("=" * 55)
    
    print("\nOpciones:")
    print("1. Cambiar credenciales de administrador")
    print("2. Verificar credenciales actuales")
    print("3. Salir")
    
    while True:
        opcion = input("\nSelecciona una opción (1, 2 o 3): ").strip()
        
        if opcion == '1':
            change_admin_credentials()
            break
        elif opcion == '2':
            test_credentials()
            break
        elif opcion == '3':
            print("👋 ¡Hasta luego!")
            break
        else:
            print("❌ Por favor selecciona 1, 2 o 3")
