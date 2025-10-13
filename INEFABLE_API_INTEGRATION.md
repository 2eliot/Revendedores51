# Integración con API Externa de Inefable Shop

## Descripción

Este sistema integra la API externa de Inefable Shop como respaldo automático cuando no hay stock local de pines de Free Fire. La integración es transparente para los usuarios y proporciona un flujo continuo de pines.

## Configuración

### Variables de Entorno

Configura las siguientes variables de entorno para habilitar la API externa:

```bash
# Credenciales de Inefable Shop
INEFABLE_USUARIO=aquiUsuario
INEFABLE_CLAVE=321Naruto%

# Opcional: Configuración avanzada
INEFABLE_TIMEOUT=30
```

### Archivo .env

Agrega estas líneas a tu archivo `.env`:

```env
# API Externa Inefable Shop
INEFABLE_USUARIO=aquiUsuario
INEFABLE_CLAVE=321Naruto%
INEFABLE_TIMEOUT=30
```

## Funcionamiento

### Flujo Automático

1. **Usuario solicita pin**: El usuario selecciona un paquete y cantidad
2. **Verificación de stock local**: El sistema verifica si hay pines disponibles en la base de datos local
3. **Respaldo automático**: Si no hay stock local suficiente, el sistema automáticamente:
   - Solicita pines a la API externa de Inefable Shop
   - Agrega los pines obtenidos al stock local (opcional)
   - Entrega los pines al usuario
4. **Registro de transacción**: Se registra la transacción indicando la fuente del pin

### Mapeo de Montos

El sistema mapea automáticamente los IDs de monto locales a los externos:

| Monto Local | Descripción | Monto Externo | API Tipo |
|-------------|-------------|---------------|----------|
| 1 | 110 💎 | 1 | recargaPinFreefirebs |
| 2 | 341 💎 | 2 | recargaPinFreefirebs |
| 3 | 572 💎 | 3 | recargaPinFreefirebs |
| 4 | 1.166 💎 | 4 | recargaPinFreefirebs |
| 5 | 2.376 💎 | 5 | recargaPinFreefirebs |
| 6 | 6.138 💎 | 6 | recargaPinFreefirebs |
| 7 | Tarjeta básica | 7 | recargaPinFreefirebs |
| 8 | Tarjeta semanal | 8 | recargaPinFreefirebs |
| 9 | Tarjeta mensual | 9 | recargaPinFreefirebs |

## Características

### ✅ Ventajas

- **Respaldo automático**: No se interrumpe el servicio por falta de stock
- **Transparente**: Los usuarios no notan la diferencia
- **Registro completo**: Se registra la fuente de cada pin
- **Manejo de errores**: Gestión robusta de errores de API
- **Configuración flexible**: Fácil activación/desactivación

### 🔧 Funciones Administrativas

#### Panel de Administración

El panel de admin incluye nuevas funciones:

1. **Estado de API Externa**: Muestra si la API está disponible
2. **Probar Conexión**: Botón para probar la conectividad
3. **Solicitar Pin Manual**: Obtener pines manualmente de la API externa
4. **Estado del Stock**: Vista completa del stock local y externo

#### Comandos de Prueba

```bash
# Probar la integración completa
python test_inefable_integration.py

# Probar solo la conexión
python -c "from inefable_api_client import get_inefable_client; client = get_inefable_client(); print(client.test_connection())"
```

## API Externa - Detalles Técnicos

### URL Base
```
https://inefableshop.net/conexion_api/api.php
```

### Parámetros de Solicitud
- `action`: recarga
- `usuario`: Usuario configurado
- `clave`: Contraseña configurada
- `tipo`: recargaPinFreefirebs
- `monto`: ID del monto (1-9)
- `numero`: 0 (fijo)

### Ejemplo de Solicitud
```
GET https://inefableshop.net/conexion_api/api.php?action=recarga&usuario=aquiUsuario&clave=321Naruto%&tipo=recargaPinFreefirebs&monto=1&numero=0
```

### Respuestas Esperadas

#### Éxito
```json
{
  "status": "success",
  "pin": "CODIGO_DEL_PIN_AQUI"
}
```

#### Error
```json
{
  "status": "error",
  "message": "Descripción del error"
}
```

## Gestión de Errores

### Tipos de Error Manejados

1. **Conexión**: Problemas de red o timeout
2. **Autenticación**: Credenciales incorrectas
3. **Stock**: No hay pines disponibles en la API externa
4. **Formato**: Respuesta inválida de la API
5. **Configuración**: Variables de entorno faltantes

### Logs y Monitoreo

Los errores se registran en:
- Logs de la aplicación Flask
- Mensajes flash para administradores
- Respuestas estructuradas para debugging

## Seguridad

### Credenciales
- Las credenciales se almacenan como variables de entorno
- No se exponen en el código fuente
- Se validan antes de cada solicitud

### Timeouts
- Timeout configurable (default: 30 segundos)
- Previene bloqueos por conexiones lentas
- Failover automático al stock local

### Validación
- Validación de parámetros de entrada
- Sanitización de respuestas de API
- Verificación de formato de pines

## Monitoreo y Mantenimiento

### Métricas Importantes

1. **Tasa de éxito de API externa**: % de solicitudes exitosas
2. **Tiempo de respuesta**: Latencia promedio
3. **Uso de respaldo**: Frecuencia de uso de API externa
4. **Errores por tipo**: Distribución de tipos de error

### Mantenimiento Recomendado

1. **Diario**: Verificar logs de errores
2. **Semanal**: Ejecutar script de prueba completo
3. **Mensual**: Revisar métricas de uso
4. **Según necesidad**: Actualizar credenciales

## Solución de Problemas

### Problemas Comunes

#### 1. API Externa No Responde
```bash
# Verificar conectividad
curl "https://inefableshop.net/conexion_api/api.php?action=recarga&usuario=test&clave=test&tipo=recargaPinFreefire&monto=1&numero=0"

# Verificar configuración
python -c "import os; print('Usuario:', os.environ.get('INEFABLE_USUARIO')); print('Clave configurada:', bool(os.environ.get('INEFABLE_CLAVE')))"
```

#### 2. Credenciales Incorrectas
- Verificar variables de entorno
- Confirmar credenciales con Inefable Shop
- Revisar caracteres especiales en la contraseña

#### 3. Pines Inválidos
- Verificar formato de respuesta de API
- Confirmar mapeo de montos
- Revisar logs de errores

### Comandos de Diagnóstico

```bash
# Prueba completa del sistema
python test_inefable_integration.py

# Verificar configuración
python -c "from inefable_api_client import get_inefable_client; client = get_inefable_client(); print('Config OK' if client.usuario != 'aquiUsuario' else 'Config pendiente')"

# Probar conexión básica
python -c "import requests; r = requests.get('https://inefableshop.net', timeout=10); print('Sitio accesible:', r.status_code == 200)"
```

## Desarrollo y Extensión

### Estructura de Archivos

```
├── inefable_api_client.py      # Cliente de API externa
├── pin_manager.py              # Gestor de pines con respaldo
├── app.py                      # Aplicación principal (modificada)
├── test_inefable_integration.py # Script de pruebas
└── INEFABLE_API_INTEGRATION.md # Esta documentación
```

### Extensiones Futuras

1. **Cache de pines**: Almacenar pines obtenidos para uso futuro
2. **Múltiples proveedores**: Soporte para varias APIs externas
3. **Balanceador de carga**: Distribuir solicitudes entre proveedores
4. **Métricas avanzadas**: Dashboard de monitoreo
5. **Notificaciones**: Alertas por fallas de API

### Contribuir

Para contribuir al desarrollo:

1. Mantener compatibilidad con la interfaz existente
2. Agregar pruebas para nuevas funcionalidades
3. Documentar cambios en este archivo
4. Seguir patrones de manejo de errores existentes

## Contacto y Soporte

Para problemas relacionados con:
- **API Externa**: Contactar a Inefable Shop
- **Integración**: Revisar logs y ejecutar pruebas
- **Configuración**: Verificar variables de entorno

---

**Última actualización**: Enero 2025
**Versión**: 1.0
**Estado**: Producción
