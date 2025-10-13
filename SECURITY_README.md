# 🔒 INEFABLE STORE - Guía de Seguridad

## 🛡️ Medidas de Seguridad Implementadas

### 1. **Protección de Contraseñas**
- ✅ **PBKDF2 + SHA256**: Las contraseñas se hashean usando Werkzeug con salt de 16 bytes
- ✅ **No más SHA256 simple**: Eliminado el hash básico vulnerable
- ✅ **Verificación segura**: Función `verify_password()` para validar credenciales

### 2. **Encriptación de PINs**
- ✅ **Fernet (AES 128)**: Todos los PINs se encriptan antes de almacenarse
- ✅ **Clave única**: Clave de encriptación generada automáticamente
- ✅ **Funciones seguras**: `encrypt_pin()` y `decrypt_pin()` con manejo de errores

### 3. **Configuración de Sesiones**
- ✅ **Cookies seguras**: `SESSION_COOKIE_SECURE = True` (solo HTTPS)
- ✅ **Protección XSS**: `SESSION_COOKIE_HTTPONLY = True`
- ✅ **Protección CSRF**: `SESSION_COOKIE_SAMESITE = 'Lax'`
- ✅ **Clave secreta**: Generada automáticamente con `secrets.token_hex(32)`

### 4. **Variables de Entorno**
- ✅ **SECRET_KEY**: Clave secreta de Flask desde variable de entorno
- ✅ **ENCRYPTION_KEY**: Clave de encriptación desde variable de entorno
- ✅ **DATABASE_PATH**: Ruta de BD configurable para producción

## 🚀 Instalación y Configuración

### Paso 1: Instalar Dependencias
```bash
pip install -r requirements.txt
```

### Paso 2: Configurar Seguridad para Producción
```bash
python production_config.py
```

### Paso 3: Configurar Variables de Entorno
```bash
# En el servidor de producción
export SECRET_KEY='tu_clave_secreta_generada'
export ENCRYPTION_KEY='tu_clave_encriptacion_generada'
export DATABASE_PATH='/ruta/segura/usuarios.db'
export FLASK_ENV='production'
export FLASK_DEBUG='False'
```

### Paso 4: Ejecutar en Producción
```bash
# Con Gunicorn (recomendado)
gunicorn -w 4 -b 0.0.0.0:8000 app:app

# O con Flask (solo desarrollo)
python app.py
```

## 🔐 Configuración de Servidor Web (Nginx)

```nginx
server {
    listen 443 ssl;
    server_name tu-dominio.com;
    
    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Redirigir HTTP a HTTPS
server {
    listen 80;
    server_name tu-dominio.com;
    return 301 https://$server_name$request_uri;
}
```

## 📊 Base de Datos Segura

### Ubicación Recomendada
```bash
# Crear directorio seguro
sudo mkdir -p /var/www/secure_app/database
sudo chown www-data:www-data /var/www/secure_app/database
sudo chmod 750 /var/www/secure_app/database
```

### Backups Automáticos
```bash
# Agregar a crontab para backup diario
0 2 * * * python /path/to/production_config.py backup
```

## ⚠️ Lista de Verificación de Seguridad

### Antes de Producción:
- [ ] Variables de entorno configuradas
- [ ] HTTPS habilitado con certificado SSL válido
- [ ] Firewall configurado (solo puertos 80, 443)
- [ ] Base de datos en ubicación segura
- [ ] Permisos de archivos configurados (750 para directorios, 640 para archivos)
- [ ] Usuario no-root para ejecutar la aplicación
- [ ] Logs de seguridad habilitados
- [ ] Backups automáticos configurados

### Mantenimiento Regular:
- [ ] Actualizar dependencias mensualmente
- [ ] Revisar logs de seguridad semanalmente
- [ ] Probar backups mensualmente
- [ ] Cambiar claves de encriptación anualmente
- [ ] Monitorear intentos de acceso no autorizados

## 🚨 Credenciales por Defecto

**⚠️ IMPORTANTE: Cambiar inmediatamente en producción**

```
Admin por defecto:
Email: admin@mail.com
Password: admin123
```

## 📝 Logs de Seguridad

### Eventos Monitoreados:
- Intentos de login fallidos
- Accesos de administrador
- Transacciones realizadas
- Errores de encriptación/desencriptación
- Cambios en la base de datos

### Ubicación de Logs:
```bash
/var/log/inefable_store/
├── access.log
├── error.log
└── security.log
```

## 🔧 Solución de Problemas

### Error de Encriptación:
```python
# Si hay problemas con la encriptación, regenerar clave:
python production_config.py
```

### Error de Base de Datos:
```python
# Verificar permisos:
ls -la usuarios.db
# Debe mostrar: -rw-r----- www-data www-data
```

### Error de Sesiones:
```python
# Verificar que HTTPS esté habilitado si SESSION_COOKIE_SECURE = True
# En desarrollo local, cambiar a False temporalmente
```

## 📞 Contacto de Seguridad

Para reportar vulnerabilidades de seguridad:
- Email: security@inefable-store.com
- Respuesta garantizada en 24 horas
- Divulgación responsable apreciada

---

**🔒 Recuerda: La seguridad es un proceso continuo, no un destino.**
