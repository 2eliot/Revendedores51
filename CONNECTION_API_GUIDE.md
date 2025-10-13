# 🔗 API de Conexión - Revendedores51

## 📋 Descripción

La API de Conexión de Revendedores51 permite a tu web externa conectarse directamente con el sistema para:

- ✅ **Autenticar usuarios** con email y contraseña
- 💰 **Verificar saldos** en tiempo real
- 🎯 **Obtener PINs** con descuento automático del saldo
- 📊 **Consultar stock** disponible
- 📋 **Ver historial** de transacciones

## 🚀 Inicio Rápido

### 1. Iniciar la API

```bash
# Ejecutar la API de conexión
python connection_api.py
```

La API estará disponible en: `http://localhost:5002`

### 2. Probar la API

```bash
# Ejecutar pruebas automáticas
python test_connection_api.py
```

## 📡 Endpoints Disponibles

### 🔍 Health Check

**GET** `/api/connection/health`

Verifica que la API esté funcionando correctamente.

**Respuesta:**
```json
{
  "status": "success",
  "message": "API de Conexión funcionando correctamente",
  "service": "Revendedores51 Connection API",
  "timestamp": "2024-01-15T10:30:00",
  "version": "1.0.0"
}
```

---

### 🔐 Autenticación

**POST** `/api/connection/login`

Autentica un usuario con email y contraseña.

**Body (JSON):**
```json
{
  "email": "usuario@ejemplo.com",
  "password": "contraseña123"
}
```

**Respuesta exitosa (200):**
```json
{
  "status": "success",
  "message": "Login exitoso",
  "data": {
    "user_id": 123,
    "name": "Juan Pérez",
    "email": "usuario@ejemplo.com",
    "balance": 15.50,
    "token": "auth_token_here",
    "phone": "1234567890"
  }
}
```

**Respuesta de error (401):**
```json
{
  "status": "error",
  "message": "Credenciales incorrectas"
}
```

---

### 💰 Consultar Saldo

**GET** `/api/connection/balance/{user_id}`

Obtiene el saldo actual de un usuario.

**Parámetros:**
- `user_id`: ID del usuario (obtenido del login)

**Respuesta:**
```json
{
  "status": "success",
  "data": {
    "user_id": 123,
    "name": "Juan Pérez",
    "balance": 15.50,
    "last_updated": "2024-01-15T10:30:00"
  }
}
```

---

### 📦 Obtener Paquetes

**GET** `/api/connection/packages`

Obtiene todos los paquetes disponibles con sus precios.

**Respuesta:**
```json
{
  "status": "success",
  "data": [
    {
      "id": 1,
      "name": "110 💎",
      "price": 0.66,
      "description": "110 Diamantes Free Fire"
    },
    {
      "id": 2,
      "name": "341 💎",
      "price": 2.25,
      "description": "341 Diamantes Free Fire"
    }
  ],
  "total": 9
}
```

---

### 🛒 Comprar PIN

**POST** `/api/connection/purchase`

Compra un PIN verificando saldo y descontándolo automáticamente.

**Body (JSON):**
```json
{
  "user_id": 123,
  "package_id": 1,
  "quantity": 1
}
```

**Parámetros:**
- `user_id`: ID del usuario
- `package_id`: ID del paquete (1-9)
- `quantity`: Cantidad de PINs (1-10)

**Respuesta exitosa (200) - Un PIN:**
```json
{
  "status": "success",
  "message": "PIN obtenido exitosamente",
  "data": {
    "pin": "ABCD-EFGH-1234",
    "package_name": "110 💎",
    "package_description": "110 Diamantes Free Fire",
    "price_per_unit": 0.66,
    "quantity": 1,
    "total_price": 0.66,
    "transaction_id": "API-ABC123",
    "control_number": "1234567890",
    "new_balance": 14.84,
    "timestamp": "2024-01-15T10:30:00"
  }
}
```

**Respuesta exitosa (200) - Múltiples PINs:**
```json
{
  "status": "success",
  "message": "3 PINs obtenidos exitosamente",
  "data": {
    "pins": [
      "ABCD-EFGH-1234",
      "EFGH-IJKL-5678",
      "IJKL-MNOP-9012"
    ],
    "package_name": "110 💎",
    "quantity": 3,
    "total_price": 1.98,
    "transaction_id": "API-DEF456",
    "control_number": "0987654321",
    "new_balance": 13.52,
    "timestamp": "2024-01-15T10:35:00"
  }
}
```

**Respuesta de error (400):**
```json
{
  "status": "error",
  "message": "Saldo insuficiente. Necesitas $0.66 pero tienes $0.50"
}
```

---

### 📊 Consultar Stock

**GET** `/api/connection/stock`

Obtiene el estado del stock de PINs disponibles.

**Respuesta:**
```json
{
  "status": "success",
  "data": {
    "1": 50,
    "2": 30,
    "3": 25,
    "4": 15,
    "5": 10,
    "6": 5,
    "7": 40,
    "8": 20,
    "9": 8
  },
  "total_pins": 203
}
```

---

### 📋 Historial de Transacciones

**GET** `/api/connection/user/{user_id}/transactions`

Obtiene las transacciones recientes de un usuario.

**Parámetros de consulta:**
- `limit`: Número máximo de transacciones (por defecto: 10, máximo: 50)

**Ejemplo:** `/api/connection/user/123/transactions?limit=5`

**Respuesta:**
```json
{
  "status": "success",
  "data": [
    {
      "id": 456,
      "transaction_id": "API-ABC123",
      "control_number": "1234567890",
      "amount": -0.66,
      "date": "2024-01-15 10:30:00",
      "pin": "ABCD-EFGH-1234"
    }
  ],
  "total": 1
}
```

## 🔧 Ejemplos de Uso

### JavaScript/Fetch

```javascript
// 1. Autenticación
async function login(email, password) {
    const response = await fetch('http://localhost:5002/api/connection/login', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            email: email,
            password: password
        })
    });
    
    const data = await response.json();
    
    if (data.status === 'success') {
        console.log('Login exitoso:', data.data);
        return data.data;
    } else {
        console.error('Error de login:', data.message);
        return null;
    }
}

// 2. Verificar saldo
async function checkBalance(userId) {
    const response = await fetch(`http://localhost:5002/api/connection/balance/${userId}`);
    const data = await response.json();
    
    if (data.status === 'success') {
        console.log('Saldo actual:', data.data.balance);
        return data.data.balance;
    }
    return 0;
}

// 3. Comprar PIN
async function buyPin(userId, packageId, quantity = 1) {
    const response = await fetch('http://localhost:5002/api/connection/purchase', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            user_id: userId,
            package_id: packageId,
            quantity: quantity
        })
    });
    
    const data = await response.json();
    
    if (data.status === 'success') {
        console.log('PIN obtenido:', data.data);
        return data.data;
    } else {
        console.error('Error al comprar PIN:', data.message);
        return null;
    }
}

// Ejemplo de uso completo
async function example() {
    // Login
    const user = await login('usuario@ejemplo.com', 'contraseña123');
    if (!user) return;
    
    // Verificar saldo
    const balance = await checkBalance(user.user_id);
    console.log(`Saldo disponible: $${balance}`);
    
    // Comprar PIN si hay saldo suficiente
    if (balance >= 0.66) {
        const purchase = await buyPin(user.user_id, 1, 1);
        if (purchase) {
            console.log(`PIN obtenido: ${purchase.pin}`);
            console.log(`Nuevo saldo: $${purchase.new_balance}`);
        }
    }
}
```

### Python/Requests

```python
import requests
import json

API_BASE = "http://localhost:5002"

def login(email, password):
    """Autenticar usuario"""
    response = requests.post(f"{API_BASE}/api/connection/login", 
                           json={"email": email, "password": password})
    
    if response.status_code == 200:
        data = response.json()
        if data['status'] == 'success':
            return data['data']
    return None

def check_balance(user_id):
    """Verificar saldo"""
    response = requests.get(f"{API_BASE}/api/connection/balance/{user_id}")
    
    if response.status_code == 200:
        data = response.json()
        if data['status'] == 'success':
            return data['data']['balance']
    return 0

def buy_pin(user_id, package_id, quantity=1):
    """Comprar PIN"""
    response = requests.post(f"{API_BASE}/api/connection/purchase", 
                           json={
                               "user_id": user_id,
                               "package_id": package_id,
                               "quantity": quantity
                           })
    
    if response.status_code == 200:
        data = response.json()
        if data['status'] == 'success':
            return data['data']
    return None

# Ejemplo de uso
def main():
    # Login
    user = login('usuario@ejemplo.com', 'contraseña123')
    if not user:
        print("Error de login")
        return
    
    print(f"Usuario: {user['name']}")
    print(f"Saldo: ${user['balance']:.2f}")
    
    # Comprar PIN
    if user['balance'] >= 0.66:
        purchase = buy_pin(user['user_id'], 1, 1)
        if purchase:
            print(f"PIN obtenido: {purchase['pin']}")
            print(f"Nuevo saldo: ${purchase['new_balance']:.2f}")

if __name__ == "__main__":
    main()
```

### PHP/cURL

```php
<?php

class Revendedores51API {
    private $baseUrl = 'http://localhost:5002';
    
    public function login($email, $password) {
        $data = json_encode([
            'email' => $email,
            'password' => $password
        ]);
        
        $response = $this->makeRequest('/api/connection/login', 'POST', $data);
        
        if ($response && $response['status'] === 'success') {
            return $response['data'];
        }
        
        return null;
    }
    
    public function checkBalance($userId) {
        $response = $this->makeRequest("/api/connection/balance/{$userId}");
        
        if ($response && $response['status'] === 'success') {
            return $response['data']['balance'];
        }
        
        return 0;
    }
    
    public function buyPin($userId, $packageId, $quantity = 1) {
        $data = json_encode([
            'user_id' => $userId,
            'package_id' => $packageId,
            'quantity' => $quantity
        ]);
        
        $response = $this->makeRequest('/api/connection/purchase', 'POST', $data);
        
        if ($response && $response['status'] === 'success') {
            return $response['data'];
        }
        
        return null;
    }
    
    private function makeRequest($endpoint, $method = 'GET', $data = null) {
        $url = $this->baseUrl . $endpoint;
        
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_HTTPHEADER, [
            'Content-Type: application/json'
        ]);
        
        if ($method === 'POST') {
            curl_setopt($ch, CURLOPT_POST, true);
            if ($data) {
                curl_setopt($ch, CURLOPT_POSTFIELDS, $data);
            }
        }
        
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        
        if ($httpCode === 200) {
            return json_decode($response, true);
        }
        
        return null;
    }
}

// Ejemplo de uso
$api = new Revendedores51API();

// Login
$user = $api->login('usuario@ejemplo.com', 'contraseña123');
if ($user) {
    echo "Usuario: " . $user['name'] . "\n";
    echo "Saldo: $" . number_format($user['balance'], 2) . "\n";
    
    // Comprar PIN
    if ($user['balance'] >= 0.66) {
        $purchase = $api->buyPin($user['user_id'], 1, 1);
        if ($purchase) {
            echo "PIN obtenido: " . $purchase['pin'] . "\n";
            echo "Nuevo saldo: $" . number_format($purchase['new_balance'], 2) . "\n";
        }
    }
}
?>
```

## 🛡️ Códigos de Estado HTTP

| Código | Descripción |
|--------|-------------|
| 200 | ✅ Éxito |
| 400 | ❌ Error de validación (datos incorrectos) |
| 401 | 🔒 No autorizado (credenciales incorrectas) |
| 404 | 🔍 No encontrado (usuario/paquete inexistente) |
| 405 | 🚫 Método no permitido |
| 500 | 💥 Error interno del servidor |

## 📝 Estructura de Respuestas

Todas las respuestas siguen el mismo formato:

### Respuesta Exitosa
```json
{
  "status": "success",
  "message": "Descripción del éxito",
  "data": {
    // Datos específicos del endpoint
  }
}
```

### Respuesta de Error
```json
{
  "status": "error",
  "message": "Descripción del error"
}
```

## 🔧 Configuración

### Variables de Entorno

```bash
# Opcional: Clave secreta personalizada
CONNECTION_API_SECRET_KEY=tu_clave_secreta_aqui

# Opcional: Ruta personalizada de la base de datos
DATABASE_PATH=/ruta/a/tu/base/datos.db
```

### Requisitos

- Python 3.7+
- Flask
- SQLite3
- Werkzeug
- Requests (para pruebas)

```bash
pip install flask werkzeug requests
```

## 🧪 Pruebas

### Ejecutar Pruebas Automáticas

```bash
# Ejecutar todas las pruebas
python test_connection_api.py
```

### Crear Usuario de Prueba

Para que las pruebas funcionen, necesitas crear un usuario de prueba:

1. Accede a tu web: https://revendedores51.onrender.com/
2. Registra un usuario con:
   - Email: `test@ejemplo.com`
   - Contraseña: `test123`
3. Agrega saldo al usuario desde el panel de administración

### Pruebas Manuales con cURL

```bash
# Health check
curl http://localhost:5002/api/connection/health

# Login
curl -X POST http://localhost:5002/api/connection/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@ejemplo.com","password":"test123"}'

# Obtener saldo (reemplaza 123 con el user_id real)
curl http://localhost:5002/api/connection/balance/123

# Obtener paquetes
curl http://localhost:5002/api/connection/packages

# Comprar PIN
curl -X POST http://localhost:5002/api/connection/purchase \
  -H "Content-Type: application/json" \
  -d '{"user_id":123,"package_id":1,"quantity":1}'
```

## 🚀 Despliegue en Producción

### 1. Configuración de Seguridad

```python
# En producción, usar variables de entorno seguras
import os

# Clave secreta fuerte
CONNECTION_API_SECRET_KEY = os.environ.get('CONNECTION_API_SECRET_KEY')

# Base de datos en ubicación segura
DATABASE_PATH = os.environ.get('DATABASE_PATH', '/secure/path/usuarios.db')
```

### 2. Usar HTTPS

En producción, asegúrate de usar HTTPS para todas las comunicaciones.

### 3. Autenticación Mejorada

Para producción, considera implementar:
- JWT tokens con expiración
- Rate limiting
- Autenticación por API key
- Logs de auditoría

### 4. Monitoreo

Implementa monitoreo para:
- Disponibilidad de la API
- Tiempo de respuesta
- Errores y excepciones
- Uso de recursos

## 🆘 Solución de Problemas

### Error: "No se puede conectar a la API"

1. Verifica que la API esté corriendo:
   ```bash
   python connection_api.py
   ```

2. Verifica el puerto (debe ser 5002):
   ```bash
   netstat -an | grep 5002
   ```

### Error: "Credenciales incorrectas"

1. Verifica que el usuario exista en la base de datos
2. Verifica que la contraseña sea correcta
3. Crea un usuario de prueba si es necesario

### Error: "Sin stock disponible"

1. Verifica el stock disponible:
   ```bash
   curl http://localhost:5002/api/connection/stock
   ```

2. Agrega PINs al stock desde el panel de administración

### Error: "Saldo insuficiente"

1. Verifica el saldo del usuario:
   ```bash
   curl http://localhost:5002/api/connection/balance/USER_ID
   ```

2. Agrega saldo desde el panel de administración

## 📞 Soporte

Para soporte técnico o preguntas sobre la API:

1. Revisa esta documentación
2. Ejecuta las pruebas automáticas
3. Verifica los logs de la API
4. Contacta al equipo de desarrollo

---

## 📄 Licencia

Esta API es parte del sistema Revendedores51 y está sujeta a los términos de uso del proyecto.

---

**🔗 API de Conexión - Revendedores51**  
*Conecta tu web externa con nuestro sistema de forma segura y eficiente*
