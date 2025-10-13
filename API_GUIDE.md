# 🚀 Guía de la API Independiente

## 📋 Descripción

Esta API independiente te permite probar todas las funcionalidades de tu sistema de revendedores sin afectar la aplicación web principal. Es perfecta para:

- ✅ Probar nuevas funcionalidades antes de integrarlas
- ✅ Desarrollo y debugging independiente
- ✅ Testing automatizado
- ✅ Integración con otras aplicaciones
- ✅ Monitoreo y análisis de datos

## 🛠️ Instalación y Configuración

### 1. Requisitos Previos

```bash
# Instalar dependencias (si no están instaladas)
pip install flask requests werkzeug
```

### 2. Iniciar la API

```bash
# Opción 1: Ejecutar directamente
python api_standalone.py

# Opción 2: Con variables de entorno personalizadas
API_SECRET_KEY=mi_clave_secreta API_DATABASE_PATH=mi_api.db python api_standalone.py
```

La API se ejecutará en: **http://localhost:5001**

### 3. Verificar que funciona

```bash
# Prueba rápida con curl
curl http://localhost:5001/api/health

# O abre en tu navegador
http://localhost:5001/api/health
```

## 📡 Endpoints Disponibles

### 🏥 Health Check
```http
GET /api/health
```
**Respuesta:**
```json
{
  "status": "success",
  "message": "API funcionando correctamente",
  "timestamp": "2025-01-08T16:57:00",
  "version": "1.0.0"
}
```

### 👥 Gestión de Usuarios

#### Obtener todos los usuarios
```http
GET /api/usuarios
```

#### Crear nuevo usuario
```http
POST /api/usuarios
Content-Type: application/json

{
  "nombre": "Juan",
  "apellido": "Pérez",
  "telefono": "+58412-1234567",
  "correo": "juan@example.com",
  "contraseña": "password123"
}
```

#### Obtener usuario específico
```http
GET /api/usuarios/{id}
```

#### Actualizar saldo de usuario
```http
PUT /api/usuarios/{id}/saldo
Content-Type: application/json

{
  "saldo": 50.00
}
```

#### Obtener transacciones de usuario
```http
GET /api/usuarios/{id}/transacciones
```

### 🔐 Autenticación

#### Login de usuario
```http
POST /api/login
Content-Type: application/json

{
  "correo": "juan@example.com",
  "contraseña": "password123"
}
```

### 📦 Gestión de Paquetes

#### Obtener paquetes disponibles
```http
GET /api/paquetes
```

#### Actualizar precio de paquete
```http
PUT /api/paquetes/{id}/precio
Content-Type: application/json

{
  "precio": 0.75
}
```

### 📊 Stock y Pines

#### Obtener stock de pines
```http
GET /api/stock
```

#### Agregar pin al stock
```http
POST /api/pines
Content-Type: application/json

{
  "monto_id": 1,
  "pin_codigo": "ABC123DEF456"
}
```

### 💳 Transacciones

#### Obtener todas las transacciones
```http
GET /api/transacciones
```

## 🧪 Ejecutar Pruebas

### Pruebas Automáticas Completas
```bash
# Ejecutar todas las pruebas
python test_api.py --all
```

### Pruebas Individuales
```bash
# Ejecutar menú interactivo
python test_api.py
```

### Ejemplo de Uso con Python

```python
import requests
import json

# Configuración
API_URL = "http://localhost:5001"

# 1. Verificar que la API funciona
response = requests.get(f"{API_URL}/api/health")
print(f"API Status: {response.json()['status']}")

# 2. Crear un usuario
usuario_data = {
    "nombre": "María",
    "apellido": "González",
    "telefono": "+58414-9876543",
    "correo": "maria@test.com",
    "contraseña": "segura123"
}

response = requests.post(
    f"{API_URL}/api/usuarios",
    json=usuario_data,
    headers={'Content-Type': 'application/json'}
)

if response.status_code == 201:
    user_id = response.json()['data']['id']
    print(f"Usuario creado con ID: {user_id}")
    
    # 3. Actualizar saldo
    requests.put(
        f"{API_URL}/api/usuarios/{user_id}/saldo",
        json={"saldo": 25.50},
        headers={'Content-Type': 'application/json'}
    )
    print("Saldo actualizado")
    
    # 4. Obtener información del usuario
    response = requests.get(f"{API_URL}/api/usuarios/{user_id}")
    usuario = response.json()['data']
    print(f"Usuario: {usuario['nombre']} - Saldo: ${usuario['saldo']}")
```

### Ejemplo con cURL

```bash
# 1. Health check
curl -X GET http://localhost:5001/api/health

# 2. Crear usuario
curl -X POST http://localhost:5001/api/usuarios \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Carlos",
    "apellido": "Rodríguez",
    "telefono": "+58416-5555555",
    "correo": "carlos@test.com",
    "contraseña": "password456"
  }'

# 3. Obtener usuarios
curl -X GET http://localhost:5001/api/usuarios

# 4. Obtener stock
curl -X GET http://localhost:5001/api/stock

# 5. Agregar pin
curl -X POST http://localhost:5001/api/pines \
  -H "Content-Type: application/json" \
  -d '{
    "monto_id": 1,
    "pin_codigo": "TEST-PIN-789"
  }'
```

## 🔧 Configuración Avanzada

### Variables de Entorno

```bash
# Clave secreta personalizada
export API_SECRET_KEY="tu_clave_super_secreta"

# Base de datos personalizada
export API_DATABASE_PATH="/ruta/a/tu/base_datos.db"

# Ejecutar con configuración personalizada
python api_standalone.py
```

### Base de Datos

La API usa una base de datos SQLite separada (`api_test.db` por defecto) que incluye:

- ✅ Tabla de usuarios
- ✅ Tabla de transacciones
- ✅ Tabla de pines de Free Fire
- ✅ Tabla de precios de paquetes
- ✅ Datos de prueba precargados

## 🚀 Integración con la Web Principal

Una vez que hayas probado y validado las funcionalidades en la API independiente, puedes integrarlas en tu aplicación web principal (`app.py`) siguiendo estos pasos:

### 1. Copiar Funciones Validadas
```python
# Ejemplo: Si agregaste una nueva función en api_standalone.py
def nueva_funcionalidad():
    # Código validado en la API
    pass

# Cópiala a app.py y adáptala según sea necesario
```

### 2. Agregar Rutas Web
```python
# En app.py, agregar las rutas web correspondientes
@app.route('/nueva-funcionalidad')
def nueva_funcionalidad_web():
    # Usar la función validada
    return render_template('nueva_template.html')
```

### 3. Migrar Base de Datos
```python
# Si agregaste nuevas tablas o campos, actualizar init_db() en app.py
def init_db():
    # ... código existente ...
    
    # Agregar nuevas tablas validadas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS nueva_tabla (
            id INTEGER PRIMARY KEY,
            campo TEXT NOT NULL
        )
    ''')
```

## 📊 Monitoreo y Logs

### Logs de la API
```bash
# La API muestra logs en tiempo real
🚀 Iniciando API independiente...
📍 Endpoints disponibles:
   GET  /api/health - Verificar estado de la API
   ...
🌐 API corriendo en: http://localhost:5001
```

### Monitoreo de Rendimiento
```python
# Ejemplo de monitoreo básico
import time
import requests

def monitor_api():
    start_time = time.time()
    response = requests.get("http://localhost:5001/api/health")
    end_time = time.time()
    
    print(f"Tiempo de respuesta: {(end_time - start_time)*1000:.2f}ms")
    print(f"Status: {response.status_code}")
```

## 🛡️ Seguridad

### Consideraciones de Seguridad

- 🔒 La API usa contraseñas hasheadas con PBKDF2
- 🔒 Validación de entrada en todos los endpoints
- 🔒 Manejo de errores sin exposición de información sensible
- 🔒 Base de datos separada para testing

### Para Producción

Si decides usar esta API en producción:

```python
# Configurar variables de entorno seguras
export API_SECRET_KEY="clave_super_segura_de_32_caracteres"
export FLASK_ENV="production"

# Usar HTTPS
# Configurar rate limiting
# Implementar autenticación JWT
# Configurar CORS apropiadamente
```

## 🆘 Solución de Problemas

### Error: "Connection refused"
```bash
# Verificar que la API esté corriendo
python api_standalone.py

# Verificar el puerto
netstat -an | grep 5001
```

### Error: "Module not found"
```bash
# Instalar dependencias faltantes
pip install flask requests werkzeug
```

### Error: "Database locked"
```bash
# Cerrar la API y reiniciar
# O usar una base de datos diferente
export API_DATABASE_PATH="nueva_api.db"
python api_standalone.py
```

### Problemas con las Pruebas
```bash
# Verificar que la API esté corriendo antes de ejecutar pruebas
curl http://localhost:5001/api/health

# Si falla, reiniciar la API
python api_standalone.py
```

## 📈 Próximos Pasos

1. **Probar todas las funcionalidades** con `test_api.py`
2. **Desarrollar nuevas características** en la API independiente
3. **Validar el comportamiento** antes de integrar
4. **Migrar funcionalidades validadas** a la aplicación web principal
5. **Repetir el ciclo** para desarrollo continuo

## 🤝 Contribuir

Para agregar nuevas funcionalidades:

1. Agregar endpoint en `api_standalone.py`
2. Crear prueba correspondiente en `test_api.py`
3. Validar funcionamiento
4. Documentar en esta guía
5. Integrar en aplicación principal

---

**¡Listo!** Ahora tienes una API completamente funcional e independiente para probar y desarrollar nuevas funcionalidades sin riesgo. 🎉
