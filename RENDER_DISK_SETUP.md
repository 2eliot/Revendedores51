# 🗄️ Configuración de Render Disk para SQLite

Esta guía te ayudará a configurar almacenamiento persistente en Render para mantener tu base de datos SQLite entre redespliegues.

## 📋 Pasos para configurar Render Disk

### 1. Configurar el Disk en Render

1. **Ve a tu servicio en Render**
   - Accede a tu dashboard de Render
   - Selecciona tu servicio web

2. **Agregar Disk**
   - Ve a la pestaña **"Settings"**
   - Busca la sección **"Disks"**
   - Haz clic en **"Add Disk"**

3. **Configurar el Disk**
   ```
   Name: database-storage
   Mount Path: /opt/render/project/src/data
   Size: 1 GB (gratuito)
   ```

4. **Guardar configuración**
   - Haz clic en **"Save"**
   - Render reiniciará tu servicio automáticamente

### 2. Configurar Variables de Entorno

En la sección **"Environment Variables"** de tu servicio, agrega:

```bash
# Variables obligatorias
SECRET_KEY=tu_clave_secreta_de_64_caracteres
FLASK_ENV=production
ADMIN_EMAIL=admin@inefable.com
ADMIN_PASSWORD=tu_contraseña_segura

# Variable para la base de datos persistente
DATABASE_PATH=/opt/render/project/src/data/usuarios.db
```

### 3. Generar SECRET_KEY

Para generar una SECRET_KEY segura, ejecuta en Python:

```python
import secrets
print(secrets.token_hex(32))
```

Ejemplo de resultado: `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2`

## ✅ Verificación

Después de configurar todo:

1. **Primer despliegue**: Se creará la base de datos en `/opt/render/project/src/data/usuarios.db`
2. **Redespliegues**: La base de datos se mantendrá intacta
3. **Datos persistentes**: Usuarios, transacciones y pines se conservarán

## 🔧 Cambios realizados en el código

El archivo `app.py` ya incluye el código necesario:

```python
# Configuración de la base de datos
DATABASE = os.environ.get('DATABASE_PATH', 'usuarios.db')

# Crear directorio para la base de datos si no existe
db_dir = os.path.dirname(DATABASE)
if db_dir and not os.path.exists(db_dir):
    os.makedirs(db_dir, exist_ok=True)
```

## 📊 Ventajas de esta configuración

- ✅ **Datos persisten** entre redespliegues
- ✅ **Gratuito** hasta 1GB de almacenamiento
- ✅ **Sin cambios complejos** en el código
- ✅ **Compatible** con tu SQLite actual
- ✅ **Backups automáticos** por parte de Render

## 🚨 Importante

- El directorio `/opt/render/project/src/data` es específico de Render
- No cambies el **Mount Path** sin actualizar la variable `DATABASE_PATH`
- La primera vez que se despliegue, la base de datos estará vacía
- Los datos se mantendrán en redespliegues posteriores

## 🔄 Proceso de despliegue

1. **Push a GitHub**: El código se actualiza
2. **Render detecta cambios**: Inicia redespliegue automático
3. **Disk persistente**: Los datos de la base de datos se mantienen
4. **Aplicación lista**: Con todos los datos intactos

¡Listo! Tu aplicación ahora mantendrá todos los datos entre redespliegues.
