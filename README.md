# 🎮 INEFABLE STORE - Sistema de Venta de PINs Free Fire

Una aplicación web completa para la venta de PINs de Free Fire con sistema de usuarios, billetera virtual y panel de administración.

## ✨ Características

### 🔐 Sistema de Autenticación
- **Login/Registro** de usuarios con validación
- **Sesiones seguras** con duración de 30 minutos
- **Panel de administrador** con credenciales configurables
- **Migración automática** de contraseñas a formato seguro (PBKDF2)

### 💎 Tienda de PINs Free Fire
- **6 paquetes de diamantes** (110 💎 a 6.138 💎)
- **3 tipos de tarjetas** (básica, semanal, mensual)
- **Stock en tiempo real** con gestión automática
- **Transacciones seguras** con números de control únicos

### 💰 Sistema de Billetera
- **Créditos virtuales** para compras
- **Historial de transacciones** (hasta 20 por usuario)
- **Gestión de saldo** en tiempo real
- **Recarga de créditos** desde panel admin

### 🛠️ Panel de Administración
- **Gestión de usuarios** (crear, editar, eliminar)
- **Control de stock** de PINs
- **Administración de saldos** y créditos
- **Vista completa** de todas las transacciones

## 🚀 Instalación y Configuración

### Requisitos Previos
- Python 3.7+
- pip (gestor de paquetes de Python)

### 1. Clonar el Repositorio
```bash
git clone https://github.com/tu-usuario/inefable-store.git
cd inefable-store
```

### 2. Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 3. Configurar Variables de Entorno (Opcional)
```bash
# Para desarrollo local (usar valores por defecto)
python app.py

# Para configuración personalizada
python change_admin_credentials.py

# Para producción completa
python production_config.py
```

### 4. Ejecutar la Aplicación
```bash
python app.py
```

La aplicación estará disponible en: `http://127.0.0.1:5000`

## 🔑 Credenciales por Defecto

### Administrador
- **Email:** `admin@inefable.com`
- **Contraseña:** `InefableAdmin2024!`

⚠️ **IMPORTANTE:** Cambiar estas credenciales en producción usando `change_admin_credentials.py`

## 📦 Paquetes Disponibles

### 💎 Diamantes Free Fire
| Paquete | Diamantes | Precio |
|---------|-----------|--------|
| Básico | 110 💎 | $0.66 |
| Estándar | 341 💎 | $2.25 |
| Premium | 572 💎 | $3.66 |
| Deluxe | 1.166 💎 | $7.10 |
| Elite | 2.376 💎 | $14.44 |
| Ultimate | 6.138 💎 | $33.10 |

### 🎫 Tarjetas Especiales
| Tipo | Descripción | Precio |
|------|-------------|--------|
| Básica | Beneficios básicos | $0.50 |
| Semanal | Beneficios por 7 días | $1.55 |
| Mensual | Beneficios por 30 días | $7.10 |

## 🛡️ Seguridad

### Características de Seguridad Implementadas
- ✅ **Contraseñas hasheadas** con PBKDF2 + SHA256 + salt
- ✅ **Sesiones seguras** con cookies HttpOnly y SameSite
- ✅ **Variables de entorno** para credenciales sensibles
- ✅ **Protección XSS y CSRF**
- ✅ **Consultas parametrizadas** contra SQL injection
- ✅ **Validación de entrada** en todos los formularios

### Variables de Entorno
```bash
# Configuración de seguridad
SECRET_KEY=tu_clave_secreta_de_flask
ADMIN_EMAIL=admin@tudominio.com
ADMIN_PASSWORD=tu_contraseña_segura
DATABASE_PATH=ruta/a/tu/base_de_datos.db
FLASK_ENV=production
FLASK_DEBUG=False
```

## 📁 Estructura del Proyecto

```
inefable-store/
├── app.py                          # Aplicación principal Flask
├── requirements.txt                # Dependencias Python
├── production_config.py            # Configuración de producción
├── change_admin_credentials.py     # Script para cambiar credenciales
├── SECURITY_README.md              # Guía de seguridad
├── usuarios.db                     # Base de datos SQLite (no incluida en Git)
├── static/                         # Archivos estáticos (CSS)
│   ├── admin.css
│   ├── auth.css
│   ├── freefire_latam.css
│   └── styles.css
├── templates/                      # Plantillas HTML
│   ├── admin.html
│   ├── auth.html
│   ├── billetera.html
│   ├── freefire_latam.html
│   └── index.html
└── logs/                          # Logs de la aplicación (no incluidos en Git)
```

## 🔧 Configuración para Producción

### 1. Generar Configuración Segura
```bash
python production_config.py
```

### 2. Configurar Variables de Entorno en el Servidor
```bash
export SECRET_KEY='clave_generada'
export ADMIN_EMAIL='admin@tudominio.com'
export ADMIN_PASSWORD='contraseña_segura'
export DATABASE_PATH='/ruta/segura/usuarios.db'
export FLASK_ENV='production'
export FLASK_DEBUG='False'
```

### 3. Usar Servidor WSGI (Recomendado)
```bash
# Instalar Gunicorn
pip install gunicorn

# Ejecutar en producción
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

## 📊 Base de Datos

### Tablas Principales
- **usuarios**: Información de usuarios registrados
- **transacciones**: Historial de compras de PINs
- **pines_freefire**: Stock de PINs disponibles
- **creditos_billetera**: Historial de recargas de créditos

### Backup Automático
```bash
# Crear backup manual
python -c "
import shutil
import datetime
timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
shutil.copy2('usuarios.db', f'backup_usuarios_{timestamp}.db')
print(f'Backup creado: backup_usuarios_{timestamp}.db')
"
```

## 🤝 Contribuir

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📝 Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles.

## 📞 Soporte

Para soporte técnico o preguntas:
- 📧 Email: admin@inefable.com
- 🐛 Issues: [GitHub Issues](https://github.com/tu-usuario/inefable-store/issues)

## 🔄 Changelog

### v1.0.0 (2025-01-07)
- ✅ Sistema completo de autenticación
- ✅ Tienda de PINs Free Fire funcional
- ✅ Panel de administración completo
- ✅ Sistema de billetera virtual
- ✅ Seguridad implementada (PBKDF2, sesiones seguras)
- ✅ Configuración para producción

---

**⚠️ Nota de Seguridad:** Este sistema maneja información sensible de usuarios. Asegúrate de seguir las mejores prácticas de seguridad descritas en `SECURITY_README.md` antes de desplegar en producción.
