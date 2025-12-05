# 🔗 API Simple de Conexión - Revendedores51

## 📋 Descripción

La API Simple de Conexión permite a tu web externa conectarse directamente con https://revendedores51.onrender.com/ usando un formato simple de URL con parámetros GET, similar a la API de inefableshop.net.

## ✅ Funcionalidades

- 🔐 **Autenticación** con email y contraseña
- 💰 **Verificación automática** de saldo
- 🎯 **Obtención de PINs** con descuento automático
- 📊 **Integración completa** con el sistema existente

## 🚀 URL de la API

### Producción (Tu web):
```
https://revendedores51.onrender.com/api.php
```

### Desarrollo (Local):
```
http://localhost:5003/api.php
```

## 📡 Formato de la API

### URL Completa:
```
https://revendedores51.onrender.com/api.php?action=recarga&usuario=EMAIL&clave=PASSWORD&tipo=recargaPinFreefire&monto=PACKAGE_ID&numero=QUANTITY
```

### Parámetros:

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `action` | string | ✅ | Siempre debe ser `"recarga"` |
| `usuario` | string | ✅ | Email del usuario registrado |
| `clave` | string | ✅ | Contraseña del usuario |
| `tipo` | string | ✅ | Siempre debe ser `"recargaPinFreefire"` |
| `monto` | integer | ✅ | ID del paquete (1-9) |
| `numero` | integer | ❌ | Cantidad de PINs (1-10, por defecto 1) |

## 📦 Paquetes Disponibles

| ID | Paquete | Precio | Descripción |
|----|---------|--------|-------------|
| 1 | 110 💎 | $0.66 | 110 Diamantes Free Fire |
| 2 | 341 💎 | $2.25 | 341 Diamantes Free Fire |
| 3 | 572 💎 | $3.66 | 572 Diamantes Free Fire |
| 4 | 1.166 💎 | $7.10 | 1.166 Diamantes Free Fire |
| 5 | 2.376 💎 | $14.44 | 2.376 Diamantes Free Fire |
| 6 | 6.138 💎 | $33.10 | 6.138 Diamantes Free Fire |
| 7 | Tarjeta básica | $0.50 | Tarjeta básica Free Fire |
| 8 | Tarjeta semanal | $1.55 | Tarjeta semanal Free Fire |
| 9 | Tarjeta mensual | $7.10 | Tarjeta mensual Free Fire |

## 💡 Ejemplos de Uso

### 1. Comprar 1 PIN del paquete más barato:
```
https://revendedores51.onrender.com/api.php?action=recarga&usuario=test@ejemplo.com&clave=test123&tipo=recargaPinFreefire&monto=1&numero=1
```

### 2. Comprar 3 PINs del paquete de $2.25:
```
https://revendedores51.onrender.com/api.php?action=recarga&usuario=test@ejemplo.com&clave=test123&tipo=recargaPinFreefire&monto=2&numero=3
```

### 3. Comprar 1 PIN del paquete más caro:
```
https://revendedores51.onrender.com/api.php?action=recarga&usuario=test@ejemplo.com&clave=test123&tipo=recargaPinFreefire&monto=6&numero=1
```

## 📝 Respuestas de la API

### ✅ Respuesta Exitosa (200):

#### Un solo PIN:
```json
{
  "status": "success",
  "code": "200",
  "message": "PIN obtenido exitosamente",
  "data": {
    "usuario": "Juan Pérez",
    "email": "test@ejemplo.com",
    "paquete": "110 💎",
    "precio_unitario": 0.66,
    "cantidad": 1,
    "precio_total": 0.66,
    "saldo_anterior": 10.00,
    "saldo_nuevo": 9.34,
    "numero_control": "1234567890",
    "transaccion_id": "API-ABC123XYZ",
    "fecha": "2024-01-15 10:30:00",
    "pin": "ABCD-EFGH-1234-5678"
  }
}
```

#### Múltiples PINs:
```json
{
  "status": "success",
  "code": "200",
  "message": "3 PINs obtenidos exitosamente",
  "data": {
    "usuario": "Juan Pérez",
    "email": "test@ejemplo.com",
    "paquete": "110 💎",
    "precio_unitario": 0.66,
    "cantidad": 3,
    "precio_total": 1.98,
    "saldo_anterior": 10.00,
    "saldo_nuevo": 8.02,
    "numero_control": "0987654321",
    "transaccion_id": "API-DEF456ABC",
    "fecha": "2024-01-15 10:35:00",
    "pines": [
      "ABCD-EFGH-1234-5678",
      "IJKL-MNOP-9012-3456",
      "QRST-UVWX-7890-1234"
    ]
  }
}
```

### ❌ Respuestas de Error:

#### Credenciales incorrectas (401):
```json
{
  "status": "error",
  "code": "401",
  "message": "Credenciales incorrectas"
}
```

#### Saldo insuficiente (402):
```json
{
  "status": "error",
  "code": "402",
  "message": "Saldo insuficiente. Necesitas $0.66 pero tienes $0.50"
}
```

#### Sin stock (503):
```json
{
  "status": "error",
  "code": "503",
  "message": "Sin stock disponible para este paquete"
}
```

#### Parámetros inválidos (400):
```json
{
  "status": "error",
  "code": "400",
  "message": "Parámetros requeridos: action, usuario, clave, tipo"
}
```

## 🛡️ Códigos de Estado HTTP

| Código | Descripción |
|--------|-------------|
| 200 | ✅ Éxito - PIN(s) obtenido(s) |
| 400 | ❌ Error de validación |
| 401 | 🔒 Credenciales incorrectas |
| 402 | 💰 Saldo insuficiente |
| 404 | 🔍 Paquete no encontrado |
| 405 | 🚫 Método no permitido (usar GET) |
| 503 | 📦 Sin stock disponible |
| 500 | 💥 Error interno del servidor |

## 🔧 Implementación en tu Web

### JavaScript/Fetch:
```javascript
async function comprarPin(email, password, packageId, quantity = 1) {
    const url = `https://revendedores51.onrender.com/api.php?action=recarga&usuario=${encodeURIComponent(email)}&clave=${encodeURIComponent(password)}&tipo=recargaPinFreefire&monto=${packageId}&numero=${quantity}`;
    
    try {
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.status === 'success') {
            console.log('PIN obtenido:', data.data.pin || data.data.pines);
            console.log('Nuevo saldo:', data.data.saldo_nuevo);
            return data.data;
        } else {
            console.error('Error:', data.message);
            return null;
        }
    } catch (error) {
        console.error('Error de conexión:', error);
        return null;
    }
}

// Ejemplo de uso
comprarPin('test@ejemplo.com', 'test123', 1, 1)
    .then(result => {
        if (result) {
            alert(`PIN obtenido: ${result.pin}`);
        }
    });
```

### PHP/cURL:
```php
<?php
function comprarPin($email, $password, $packageId, $quantity = 1) {
    $url = "https://revendedores51.onrender.com/api.php?" . http_build_query([
        'action' => 'recarga',
        'usuario' => $email,
        'clave' => $password,
        'tipo' => 'recargaPinFreefire',
        'monto' => $packageId,
        'numero' => $quantity
    ]);
    
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, 30);
    
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    
    if ($httpCode === 200) {
        $data = json_decode($response, true);
        
        if ($data['status'] === 'success') {
            return $data['data'];
        } else {
            echo "Error: " . $data['message'];
            return null;
        }
    } else {
        echo "Error HTTP: " . $httpCode;
        return null;
    }
}

// Ejemplo de uso
$result = comprarPin('test@ejemplo.com', 'test123', 1, 1);
if ($result) {
    echo "PIN obtenido: " . $result['pin'] . "\n";
    echo "Nuevo saldo: $" . $result['saldo_nuevo'] . "\n";
}
?>
```

### Python/Requests:
```python
import requests
import urllib.parse

def comprar_pin(email, password, package_id, quantity=1):
    params = {
        'action': 'recarga',
        'usuario': email,
        'clave': password,
        'tipo': 'recargaPinFreefire',
        'monto': str(package_id),
        'numero': str(quantity)
    }
    
    url = f"https://revendedores51.onrender.com/api.php?{urllib.parse.urlencode(params)}"
    
    try:
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            if data['status'] == 'success':
                return data['data']
            else:
                print(f"Error: {data['message']}")
                return None
        else:
            print(f"Error HTTP: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"Error de conexión: {e}")
        return None

# Ejemplo de uso
result = comprar_pin('test@ejemplo.com', 'test123', 1, 1)
if result:
    print(f"PIN obtenido: {result['pin']}")
    print(f"Nuevo saldo: ${result['saldo_nuevo']:.2f}")
```

## 🧪 Pruebas

### Crear Usuario de Prueba:
1. Ve a: https://revendedores51.onrender.com/
2. Registra un usuario con:
   - Email: `test@ejemplo.com`
   - Contraseña: `test123`
3. Agrega saldo desde el panel de administración

### Probar con cURL:
```bash
# Comprar 1 PIN del paquete más barato
curl "https://revendedores51.onrender.com/api.php?action=recarga&usuario=test@ejemplo.com&clave=test123&tipo=recargaPinFreefire&monto=1&numero=1"

# Comprar 3 PINs
curl "https://revendedores51.onrender.com/api.php?action=recarga&usuario=test@ejemplo.com&clave=test123&tipo=recargaPinFreefire&monto=1&numero=3"
```

### Script de Pruebas Automáticas:
```bash
# Ejecutar pruebas locales
python test_simple_api.py
```

## 🔒 Seguridad

- ✅ **Autenticación segura** con hash de contraseñas
- ✅ **Validación completa** de parámetros
- ✅ **Verificación de saldo** antes de procesar
- ✅ **Manejo robusto** de errores
- ✅ **Integración segura** con base de datos

## 🚀 Ventajas

1. **Formato Simple**: URL con parámetros GET, fácil de implementar
2. **Compatible**: Funciona igual que inefableshop.net
3. **Integrado**: Usa tu sistema existente de usuarios y PINs
4. **Automático**: Descuenta saldo y registra transacciones automáticamente
5. **Confiable**: Manejo completo de errores y validaciones

## 📞 Soporte

- 🌐 **URL de producción**: https://revendedores51.onrender.com/api.php
- 📧 **Formato**: Igual que inefableshop.net pero con tu dominio
- 🔧 **Integración**: Funciona con tu sistema existente
- 📊 **Monitoreo**: Todas las transacciones se registran en tu panel

---

## 🎯 Ejemplo Completo

```javascript
// Función completa para integrar en tu web
class Revendedores51API {
    constructor() {
        this.baseUrl = 'https://revendedores51.onrender.com/api.php';
    }
    
    async comprarPin(email, password, packageId, quantity = 1) {
        const params = new URLSearchParams({
            action: 'recarga',
            usuario: email,
            clave: password,
            tipo: 'recargaPinFreefire',
            monto: packageId.toString(),
            numero: quantity.toString()
        });
        
        const url = `${this.baseUrl}?${params}`;
        
        try {
            const response = await fetch(url);
            const data = await response.json();
            
            return {
                success: data.status === 'success',
                data: data.data || null,
                error: data.status === 'error' ? data.message : null,
                code: data.code
            };
        } catch (error) {
            return {
                success: false,
                data: null,
                error: 'Error de conexión: ' + error.message,
                code: '500'
            };
        }
    }
}

// Uso
const api = new Revendedores51API();

api.comprarPin('test@ejemplo.com', 'test123', 1, 1)
    .then(result => {
        if (result.success) {
            console.log('✅ PIN obtenido:', result.data.pin);
            console.log('💰 Nuevo saldo:', result.data.saldo_nuevo);
        } else {
            console.error('❌ Error:', result.error);
        }
    });
```

---

**🔗 API Simple de Conexión - Revendedores51**  
*Formato compatible con inefableshop.net pero conectado a tu sistema*
