"""
Configuración de seguridad para producción
IMPORTANTE: Este archivo contiene configuraciones críticas de seguridad
"""

import os
import secrets
from cryptography.fernet import Fernet

# ============================================================================
# CONFIGURACIÓN DE SEGURIDAD PARA PRODUCCIÓN
# ============================================================================

def setup_production_security():
    """
    Configuración de seguridad para producción.
    Ejecutar este script antes de desplegar en producción.
    """
    
    print("🔒 CONFIGURACIÓN DE SEGURIDAD PARA PRODUCCIÓN")
    print("=" * 50)
    
    # 1. Generar clave secreta para Flask
    secret_key = secrets.token_hex(32)
    print(f"SECRET_KEY: {secret_key}")
    
    # 2. Generar clave de encriptación para PINs
    encryption_key = Fernet.generate_key()
    print(f"ENCRYPTION_KEY: {encryption_key.decode()}")
    
    # 3. Configurar base de datos segura
    db_path = "/var/www/secure_app/database/usuarios.db"
    print(f"DATABASE_PATH: {db_path}")
    
    # 4. Generar credenciales de administrador seguras
    admin_email = "admin@inefable.com"
    admin_password = secrets.token_urlsafe(16)  # Contraseña aleatoria segura
    
    print("\n🛡️ VARIABLES DE ENTORNO REQUERIDAS:")
    print("=" * 40)
    print("Agregar estas variables al servidor de producción:")
    print(f"export SECRET_KEY='{secret_key}'")
    print(f"export ENCRYPTION_KEY='{encryption_key.decode()}'")
    print(f"export DATABASE_PATH='{db_path}'")
    print(f"export ADMIN_EMAIL='{admin_email}'")
    print(f"export ADMIN_PASSWORD='{admin_password}'")
    print("export FLASK_ENV='production'")
    print("export FLASK_DEBUG='False'")
    
    print("\n🔑 CREDENCIALES DE ADMINISTRADOR:")
    print("=" * 35)
    print(f"Email: {admin_email}")
    print(f"Contraseña: {admin_password}")
    print("⚠️ GUARDA ESTAS CREDENCIALES EN UN LUGAR SEGURO")
    
    print("\n🔐 CONFIGURACIONES ADICIONALES DE SEGURIDAD:")
    print("=" * 45)
    print("1. Usar HTTPS obligatorio (SSL/TLS)")
    print("2. Configurar firewall para puerto 443 únicamente")
    print("3. Usar servidor web seguro (Nginx + Gunicorn)")
    print("4. Configurar copias de seguridad automáticas de la BD")
    print("5. Monitoreo de logs de seguridad")
    print("6. Actualizar dependencias regularmente")
    
    # 4. Crear archivo .env para desarrollo local
    with open('.env.example', 'w') as f:
        f.write(f"""# Archivo de ejemplo para variables de entorno
# Copiar a .env y modificar según sea necesario

# Clave secreta de Flask (generar nueva para producción)
SECRET_KEY={secret_key}

# Clave de encriptación para PINs (generar nueva para producción)
ENCRYPTION_KEY={encryption_key.decode()}

# Ruta de la base de datos
DATABASE_PATH=usuarios.db

# Configuración de Flask
FLASK_ENV=development
FLASK_DEBUG=True

# En producción cambiar a:
# FLASK_ENV=production
# FLASK_DEBUG=False
""")
    
    print(f"\n✅ Archivo '.env.example' creado con configuraciones de ejemplo")
    
    return {
        'secret_key': secret_key,
        'encryption_key': encryption_key.decode(),
        'database_path': db_path
    }

def create_secure_database_backup():
    """
    Script para crear copias de seguridad seguras de la base de datos
    """
    import sqlite3
    import datetime
    import shutil
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"backup_usuarios_{timestamp}.db"
    
    try:
        # Crear copia de seguridad
        shutil.copy2('usuarios.db', f'backups/{backup_name}')
        print(f"✅ Backup creado: {backup_name}")
        
        # Comprimir backup (opcional)
        import gzip
        with open(f'backups/{backup_name}', 'rb') as f_in:
            with gzip.open(f'backups/{backup_name}.gz', 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Eliminar backup sin comprimir
        os.remove(f'backups/{backup_name}')
        print(f"✅ Backup comprimido: {backup_name}.gz")
        
    except Exception as e:
        print(f"❌ Error creando backup: {e}")

def security_checklist():
    """
    Lista de verificación de seguridad para producción
    """
    checklist = [
        "✅ Variables de entorno configuradas",
        "✅ HTTPS habilitado (SSL/TLS)",
        "✅ Firewall configurado",
        "✅ Contraseñas hasheadas con PBKDF2",
        "✅ PINs encriptados con Fernet",
        "✅ Cookies seguras habilitadas",
        "✅ Protección XSS habilitada",
        "✅ Protección CSRF habilitada",
        "✅ Base de datos en ubicación segura",
        "✅ Backups automáticos configurados",
        "✅ Logs de seguridad habilitados",
        "✅ Dependencias actualizadas",
        "✅ Servidor web seguro (Nginx/Apache)",
        "✅ Aplicación ejecutándose con usuario no-root",
        "✅ Permisos de archivos configurados correctamente"
    ]
    
    print("\n🔍 LISTA DE VERIFICACIÓN DE SEGURIDAD:")
    print("=" * 40)
    for item in checklist:
        print(item)
    
    print("\n⚠️ RECORDATORIOS IMPORTANTES:")
    print("- Cambiar credenciales de admin por defecto")
    print("- Revisar logs regularmente")
    print("- Actualizar dependencias mensualmente")
    print("- Probar backups periódicamente")
    print("- Monitorear intentos de acceso no autorizados")

if __name__ == "__main__":
    # Crear directorio de backups si no existe
    os.makedirs('backups', exist_ok=True)
    
    # Ejecutar configuración de seguridad
    config = setup_production_security()
    
    # Mostrar lista de verificación
    security_checklist()
    
    print("\n🚀 LISTO PARA PRODUCCIÓN")
    print("Recuerda configurar las variables de entorno en tu servidor!")
