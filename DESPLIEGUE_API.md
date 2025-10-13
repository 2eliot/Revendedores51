# 🚀 INSTRUCCIONES DE DESPLIEGUE - API DE CONEXIÓN

## ✅ **ESTADO ACTUAL**
- ✅ API completamente integrada en `app.py`
- ✅ Todas las funciones probadas localmente
- ✅ Usuario de prueba creado: `test@ejemplo.com` / `test123`
- ✅ 50 PINs de prueba disponibles
- ⏳ **PENDIENTE**: Subir cambios a producción

## 🔄 **PASOS PARA DESPLEGAR**

### 1. **Subir cambios a GitHub**
```bash
git add .
git commit -m "Integrar API de conexión simple - Formato compatible con inefableshop.net"
git push origin main
```

### 2. **Verificar despliegue en Render**
- Render detectará automáticamente los cambios
- El despliegue tomará 2-3 minutos
- La API estará disponible en: `https://revendedores51.onrender.com/api.php`

### 3. **Probar la API en producción**
```bash
# Ejemplo de prueba
curl "https://revendedores51.onrender.com/api.php?action=recarga&usuario=test@ejemplo.com&clave=test123&tipo=recargaPinFreefire&monto=1&numero=1"
```

## 🔗 **URL FINAL DE LA API**
```
https://revendedores51.onrender.com/api.php?action=recarga&usuario=EMAIL&clave=PASSWORD&tipo=recargaPinFreefire&monto=PACKAGE_ID&numero=QUANTITY
```

## 📋 **PARÁMETROS OBLIGATORIOS**
- `action=recarga`
- `usuario=EMAIL_DEL_USUARIO`
- `clave=CONTRASEÑA_DEL_USUARIO`
- `tipo=recargaPinFreefire`
- `monto=1-9` (ID del paquete)
- `numero=1-10` (cantidad de PINs, opcional)

## 🧪 **DATOS DE PRUEBA**
- **Usuario**: `test@ejemplo.com`
- **Contraseña**: `test123`
- **Saldo**: $100.00
- **PINs disponibles**: 10 por cada paquete (1-5)

## 📊 **RESPUESTA EXITOSA**
```json
{
  "status": "success",
  "code": "200",
  "message": "PIN obtenido exitosamente",
  "data": {
    "usuario": "Usuario Prueba",
    "email": "test@ejemplo.com",
    "paquete": "110 💎",
    "precio_unitario": 0.64,
    "cantidad": 1,
    "precio_total": 0.64,
    "saldo_anterior": 100.0,
    "saldo_nuevo": 99.36,
    "numero_control": "1234567890",
    "transaccion_id": "API-ABC12345",
    "fecha": "2025-08-22 18:30:00",
    "pin": "ABCD1234EFGH"
  }
}
```

## ⚠️ **CÓDIGOS DE ERROR**
- **400**: Parámetros faltantes o inválidos
- **401**: Credenciales incorrectas
- **402**: Saldo insuficiente
- **404**: Paquete no encontrado
- **405**: Método no permitido (usar GET)
- **503**: Sin stock disponible
- **500**: Error interno del servidor

## 🔧 **VERIFICACIÓN POST-DESPLIEGUE**

### 1. **Health Check**
```
https://revendedores51.onrender.com/api.php
```
Debería devolver información de la API.

### 2. **Prueba de autenticación**
```
https://revendedores51.onrender.com/api.php?action=recarga&usuario=test@ejemplo.com&clave=test123&tipo=recargaPinFreefire&monto=1&numero=1
```

### 3. **Prueba de error (credenciales incorrectas)**
```
https://revendedores51.onrender.com/api.php?action=recarga&usuario=invalid@test.com&clave=wrong&tipo=recargaPinFreefire&monto=1&numero=1
```
Debería devolver error 401.

## 💡 **NOTAS IMPORTANTES**
- La API está integrada directamente en `app.py`
- No requiere configuración adicional
- Usa la misma base de datos que la aplicación principal
- Compatible con el sistema de usuarios existente
- Maneja automáticamente el stock de PINs

## 🎯 **PRÓXIMOS PASOS DESPUÉS DEL DESPLIEGUE**
1. Probar la API con usuarios reales
2. Monitorear logs de errores
3. Agregar más PINs al stock si es necesario
4. Documentar la API para otros desarrolladores

---
**Una vez desplegado, la API estará 100% funcional y lista para usar.**
