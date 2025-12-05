from flask import Flask, jsonify, request
import sqlite3
import hashlib
import os
import secrets
from datetime import timedelta, datetime
import pytz
from werkzeug.security import generate_password_hash, check_password_hash
import threading

# Crear aplicación Flask para API
api_app = Flask(__name__)

# Configuración de seguridad
api_app.secret_key = os.environ.get('API_SECRET_KEY', secrets.token_hex(32))

# Configuración de la base de datos (usar una separada para testing)
API_DATABASE = os.environ.get('API_DATABASE_PATH', 'api_test.db')

# Crear directorio para la base de datos si no existe
db_dir = os.path.dirname(API_DATABASE)
if db_dir and not os.path.exists(db_dir):
    os.makedirs(db_dir, exist_ok=True)

def init_api_db():
    """Inicializa la base de datos de la API con las tablas necesarias"""
    conn = sqlite3.connect(API_DATABASE)
    cursor = conn.cursor()
    
    # Tabla de usuarios
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            apellido TEXT NOT NULL,
            telefono TEXT NOT NULL,
            correo TEXT UNIQUE NOT NULL,
            contraseña TEXT NOT NULL,
            saldo REAL DEFAULT 0.0,
            fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabla de transacciones
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transacciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            numero_control TEXT NOT NULL,
            pin TEXT NOT NULL,
            transaccion_id TEXT NOT NULL,
            monto REAL DEFAULT 0.0,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')
    
    # Tabla de pines de Free Fire
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pines_freefire (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            monto_id INTEGER NOT NULL,
            pin_codigo TEXT NOT NULL,
            usado BOOLEAN DEFAULT FALSE,
            fecha_agregado DATETIME DEFAULT CURRENT_TIMESTAMP,
            fecha_usado DATETIME NULL,
            usuario_id INTEGER NULL,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')
    
    # Tabla de precios de paquetes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS precios_paquetes (
            id INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL,
            precio REAL NOT NULL,
            descripcion TEXT NOT NULL,
            activo BOOLEAN DEFAULT TRUE,
            fecha_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insertar precios por defecto si no existen
    cursor.execute('SELECT COUNT(*) FROM precios_paquetes')
    if cursor.fetchone()[0] == 0:
        precios_default = [
            (1, '110 💎', 0.66, '110 Diamantes Free Fire', True),
            (2, '341 💎', 2.25, '341 Diamantes Free Fire', True),
            (3, '572 💎', 3.66, '572 Diamantes Free Fire', True),
            (4, '1.166 💎', 7.10, '1.166 Diamantes Free Fire', True),
            (5, '2.376 💎', 14.44, '2.376 Diamantes Free Fire', True),
            (6, '6.138 💎', 33.10, '6.138 Diamantes Free Fire', True),
            (7, 'Tarjeta básica', 0.50, 'Tarjeta básica Free Fire', True),
            (8, 'Tarjeta semanal', 1.55, 'Tarjeta semanal Free Fire', True),
            (9, 'Tarjeta mensual', 7.10, 'Tarjeta mensual Free Fire', True)
        ]
        cursor.executemany('''
            INSERT INTO precios_paquetes (id, nombre, precio, descripcion, activo)
            VALUES (?, ?, ?, ?, ?)
        ''', precios_default)
    
    conn.commit()
    conn.close()

def get_api_db_connection():
    """Obtiene una conexión a la base de datos de la API"""
    conn = sqlite3.connect(API_DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    """Hashea la contraseña usando Werkzeug"""
    return generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)

def verify_password(password, hashed):
    """Verifica la contraseña hasheada"""
    if hashed.startswith('pbkdf2:'):
        return check_password_hash(hashed, password)
    
    # Compatibilidad con SHA256 anterior
    sha256_hash = hashlib.sha256(password.encode()).hexdigest()
    return hashed == sha256_hash

# Inicializar la base de datos al iniciar la API
init_api_db()

# ============= ENDPOINTS DE LA API =============

@api_app.route('/api/health', methods=['GET'])
def health_check():
    """Endpoint para verificar que la API está funcionando"""
    return jsonify({
        'status': 'success',
        'message': 'API funcionando correctamente',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

@api_app.route('/api/usuarios', methods=['GET'])
def get_usuarios():
    """Obtiene todos los usuarios registrados"""
    try:
        conn = get_api_db_connection()
        usuarios = conn.execute('''
            SELECT id, nombre, apellido, telefono, correo, saldo, fecha_registro 
            FROM usuarios ORDER BY fecha_registro DESC
        ''').fetchall()
        conn.close()
        
        usuarios_list = []
        for usuario in usuarios:
            usuarios_list.append({
                'id': usuario['id'],
                'nombre': usuario['nombre'],
                'apellido': usuario['apellido'],
                'telefono': usuario['telefono'],
                'correo': usuario['correo'],
                'saldo': usuario['saldo'],
                'fecha_registro': usuario['fecha_registro']
            })
        
        return jsonify({
            'status': 'success',
            'data': usuarios_list,
            'total': len(usuarios_list)
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error al obtener usuarios: {str(e)}'
        }), 500

@api_app.route('/api/usuarios', methods=['POST'])
def crear_usuario():
    """Crea un nuevo usuario"""
    try:
        data = request.get_json()
        
        # Validar campos requeridos
        required_fields = ['nombre', 'apellido', 'telefono', 'correo', 'contraseña']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'status': 'error',
                    'message': f'Campo requerido: {field}'
                }), 400
        
        # Verificar si el usuario ya existe
        conn = get_api_db_connection()
        existing_user = conn.execute('SELECT id FROM usuarios WHERE correo = ?', (data['correo'],)).fetchone()
        
        if existing_user:
            conn.close()
            return jsonify({
                'status': 'error',
                'message': 'El correo electrónico ya está registrado'
            }), 400
        
        # Crear nuevo usuario
        hashed_password = hash_password(data['contraseña'])
        cursor = conn.execute('''
            INSERT INTO usuarios (nombre, apellido, telefono, correo, contraseña, saldo)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (data['nombre'], data['apellido'], data['telefono'], data['correo'], hashed_password, 0.0))
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'message': 'Usuario creado exitosamente',
            'data': {
                'id': user_id,
                'nombre': data['nombre'],
                'apellido': data['apellido'],
                'correo': data['correo'],
                'saldo': 0.0
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error al crear usuario: {str(e)}'
        }), 500

@api_app.route('/api/usuarios/<int:user_id>', methods=['GET'])
def get_usuario(user_id):
    """Obtiene información de un usuario específico"""
    try:
        conn = get_api_db_connection()
        usuario = conn.execute('''
            SELECT id, nombre, apellido, telefono, correo, saldo, fecha_registro 
            FROM usuarios WHERE id = ?
        ''', (user_id,)).fetchone()
        conn.close()
        
        if not usuario:
            return jsonify({
                'status': 'error',
                'message': 'Usuario no encontrado'
            }), 404
        
        return jsonify({
            'status': 'success',
            'data': {
                'id': usuario['id'],
                'nombre': usuario['nombre'],
                'apellido': usuario['apellido'],
                'telefono': usuario['telefono'],
                'correo': usuario['correo'],
                'saldo': usuario['saldo'],
                'fecha_registro': usuario['fecha_registro']
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error al obtener usuario: {str(e)}'
        }), 500

@api_app.route('/api/usuarios/<int:user_id>/saldo', methods=['PUT'])
def actualizar_saldo(user_id):
    """Actualiza el saldo de un usuario"""
    try:
        data = request.get_json()
        
        if 'saldo' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Campo requerido: saldo'
            }), 400
        
        nuevo_saldo = float(data['saldo'])
        if nuevo_saldo < 0:
            return jsonify({
                'status': 'error',
                'message': 'El saldo no puede ser negativo'
            }), 400
        
        conn = get_api_db_connection()
        
        # Verificar que el usuario existe
        usuario = conn.execute('SELECT id FROM usuarios WHERE id = ?', (user_id,)).fetchone()
        if not usuario:
            conn.close()
            return jsonify({
                'status': 'error',
                'message': 'Usuario no encontrado'
            }), 404
        
        # Actualizar saldo
        conn.execute('UPDATE usuarios SET saldo = ? WHERE id = ?', (nuevo_saldo, user_id))
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'message': 'Saldo actualizado exitosamente',
            'data': {
                'user_id': user_id,
                'nuevo_saldo': nuevo_saldo
            }
        })
        
    except ValueError:
        return jsonify({
            'status': 'error',
            'message': 'El saldo debe ser un número válido'
        }), 400
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error al actualizar saldo: {str(e)}'
        }), 500

@api_app.route('/api/paquetes', methods=['GET'])
def get_paquetes():
    """Obtiene todos los paquetes disponibles con sus precios"""
    try:
        conn = get_api_db_connection()
        paquetes = conn.execute('''
            SELECT id, nombre, precio, descripcion, activo 
            FROM precios_paquetes 
            WHERE activo = TRUE 
            ORDER BY id
        ''').fetchall()
        conn.close()
        
        paquetes_list = []
        for paquete in paquetes:
            paquetes_list.append({
                'id': paquete['id'],
                'nombre': paquete['nombre'],
                'precio': paquete['precio'],
                'descripcion': paquete['descripcion'],
                'activo': bool(paquete['activo'])
            })
        
        return jsonify({
            'status': 'success',
            'data': paquetes_list,
            'total': len(paquetes_list)
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error al obtener paquetes: {str(e)}'
        }), 500

@api_app.route('/api/paquetes/<int:paquete_id>/precio', methods=['PUT'])
def actualizar_precio_paquete(paquete_id):
    """Actualiza el precio de un paquete"""
    try:
        data = request.get_json()
        
        if 'precio' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Campo requerido: precio'
            }), 400
        
        nuevo_precio = float(data['precio'])
        if nuevo_precio < 0:
            return jsonify({
                'status': 'error',
                'message': 'El precio no puede ser negativo'
            }), 400
        
        conn = get_api_db_connection()
        
        # Verificar que el paquete existe
        paquete = conn.execute('SELECT nombre FROM precios_paquetes WHERE id = ?', (paquete_id,)).fetchone()
        if not paquete:
            conn.close()
            return jsonify({
                'status': 'error',
                'message': 'Paquete no encontrado'
            }), 404
        
        # Actualizar precio
        conn.execute('''
            UPDATE precios_paquetes 
            SET precio = ?, fecha_actualizacion = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (nuevo_precio, paquete_id))
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'message': 'Precio actualizado exitosamente',
            'data': {
                'paquete_id': paquete_id,
                'nombre': paquete['nombre'],
                'nuevo_precio': nuevo_precio
            }
        })
        
    except ValueError:
        return jsonify({
            'status': 'error',
            'message': 'El precio debe ser un número válido'
        }), 400
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error al actualizar precio: {str(e)}'
        }), 500

@api_app.route('/api/stock', methods=['GET'])
def get_stock():
    """Obtiene el stock de pines disponibles"""
    try:
        conn = get_api_db_connection()
        stock = {}
        
        for i in range(1, 10):  # monto_id del 1 al 9
            count = conn.execute('''
                SELECT COUNT(*) FROM pines_freefire 
                WHERE monto_id = ? AND usado = FALSE
            ''', (i,)).fetchone()[0]
            stock[i] = count
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'data': stock,
            'total_pines': sum(stock.values())
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error al obtener stock: {str(e)}'
        }), 500

@api_app.route('/api/pines', methods=['POST'])
def agregar_pin():
    """Agrega un pin al stock"""
    try:
        data = request.get_json()
        
        # Validar campos requeridos
        if not data.get('monto_id') or not data.get('pin_codigo'):
            return jsonify({
                'status': 'error',
                'message': 'Campos requeridos: monto_id, pin_codigo'
            }), 400
        
        monto_id = int(data['monto_id'])
        pin_codigo = data['pin_codigo'].strip()
        
        if monto_id < 1 or monto_id > 9:
            return jsonify({
                'status': 'error',
                'message': 'monto_id debe estar entre 1 y 9'
            }), 400
        
        if not pin_codigo:
            return jsonify({
                'status': 'error',
                'message': 'pin_codigo no puede estar vacío'
            }), 400
        
        conn = get_api_db_connection()
        
        # Verificar si el pin ya existe
        existing_pin = conn.execute('''
            SELECT id FROM pines_freefire 
            WHERE pin_codigo = ? AND monto_id = ?
        ''', (pin_codigo, monto_id)).fetchone()
        
        if existing_pin:
            conn.close()
            return jsonify({
                'status': 'error',
                'message': 'Este pin ya existe en el stock'
            }), 400
        
        # Agregar pin
        cursor = conn.execute('''
            INSERT INTO pines_freefire (monto_id, pin_codigo)
            VALUES (?, ?)
        ''', (monto_id, pin_codigo))
        
        pin_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'message': 'Pin agregado exitosamente',
            'data': {
                'id': pin_id,
                'monto_id': monto_id,
                'pin_codigo': pin_codigo
            }
        }), 201
        
    except ValueError:
        return jsonify({
            'status': 'error',
            'message': 'monto_id debe ser un número entero'
        }), 400
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error al agregar pin: {str(e)}'
        }), 500

@api_app.route('/api/transacciones', methods=['GET'])
def get_transacciones():
    """Obtiene todas las transacciones"""
    try:
        conn = get_api_db_connection()
        transacciones = conn.execute('''
            SELECT t.*, u.nombre, u.apellido, u.correo
            FROM transacciones t
            JOIN usuarios u ON t.usuario_id = u.id
            ORDER BY t.fecha DESC
            LIMIT 50
        ''').fetchall()
        conn.close()
        
        transacciones_list = []
        for transaccion in transacciones:
            transacciones_list.append({
                'id': transaccion['id'],
                'usuario_id': transaccion['usuario_id'],
                'usuario_nombre': f"{transaccion['nombre']} {transaccion['apellido']}",
                'usuario_correo': transaccion['correo'],
                'numero_control': transaccion['numero_control'],
                'pin': transaccion['pin'],
                'transaccion_id': transaccion['transaccion_id'],
                'monto': transaccion['monto'],
                'fecha': transaccion['fecha']
            })
        
        return jsonify({
            'status': 'success',
            'data': transacciones_list,
            'total': len(transacciones_list)
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error al obtener transacciones: {str(e)}'
        }), 500

@api_app.route('/api/usuarios/<int:user_id>/transacciones', methods=['GET'])
def get_transacciones_usuario(user_id):
    """Obtiene las transacciones de un usuario específico"""
    try:
        conn = get_api_db_connection()
        
        # Verificar que el usuario existe
        usuario = conn.execute('SELECT id FROM usuarios WHERE id = ?', (user_id,)).fetchone()
        if not usuario:
            conn.close()
            return jsonify({
                'status': 'error',
                'message': 'Usuario no encontrado'
            }), 404
        
        transacciones = conn.execute('''
            SELECT t.*, u.nombre, u.apellido
            FROM transacciones t
            JOIN usuarios u ON t.usuario_id = u.id
            WHERE t.usuario_id = ? 
            ORDER BY t.fecha DESC
        ''', (user_id,)).fetchall()
        conn.close()
        
        transacciones_list = []
        for transaccion in transacciones:
            transacciones_list.append({
                'id': transaccion['id'],
                'numero_control': transaccion['numero_control'],
                'pin': transaccion['pin'],
                'transaccion_id': transaccion['transaccion_id'],
                'monto': transaccion['monto'],
                'fecha': transaccion['fecha']
            })
        
        return jsonify({
            'status': 'success',
            'data': transacciones_list,
            'total': len(transacciones_list)
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error al obtener transacciones del usuario: {str(e)}'
        }), 500

@api_app.route('/api/login', methods=['POST'])
def login():
    """Endpoint de autenticación"""
    try:
        data = request.get_json()
        
        if not data.get('correo') or not data.get('contraseña'):
            return jsonify({
                'status': 'error',
                'message': 'Campos requeridos: correo, contraseña'
            }), 400
        
        conn = get_api_db_connection()
        usuario = conn.execute('''
            SELECT id, nombre, apellido, correo, contraseña, saldo 
            FROM usuarios WHERE correo = ?
        ''', (data['correo'],)).fetchone()
        conn.close()
        
        if not usuario or not verify_password(data['contraseña'], usuario['contraseña']):
            return jsonify({
                'status': 'error',
                'message': 'Credenciales incorrectas'
            }), 401
        
        return jsonify({
            'status': 'success',
            'message': 'Login exitoso',
            'data': {
                'id': usuario['id'],
                'nombre': usuario['nombre'],
                'apellido': usuario['apellido'],
                'correo': usuario['correo'],
                'saldo': usuario['saldo']
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error en login: {str(e)}'
        }), 500

# Manejo de errores
@api_app.errorhandler(404)
def not_found(error):
    return jsonify({
        'status': 'error',
        'message': 'Endpoint no encontrado'
    }), 404

@api_app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        'status': 'error',
        'message': 'Método no permitido'
    }), 405

@api_app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'status': 'error',
        'message': 'Error interno del servidor'
    }), 500

if __name__ == '__main__':
    print("🚀 Iniciando API independiente...")
    print("📍 Endpoints disponibles:")
    print("   GET  /api/health - Verificar estado de la API")
    print("   GET  /api/usuarios - Obtener todos los usuarios")
    print("   POST /api/usuarios - Crear nuevo usuario")
    print("   GET  /api/usuarios/<id> - Obtener usuario específico")
    print("   PUT  /api/usuarios/<id>/saldo - Actualizar saldo de usuario")
    print("   GET  /api/paquetes - Obtener paquetes disponibles")
    print("   PUT  /api/paquetes/<id>/precio - Actualizar precio de paquete")
    print("   GET  /api/stock - Obtener stock de pines")
    print("   POST /api/pines - Agregar pin al stock")
    print("   GET  /api/transacciones - Obtener todas las transacciones")
    print("   GET  /api/usuarios/<id>/transacciones - Obtener transacciones de usuario")
    print("   POST /api/login - Autenticación de usuario")
    print("\n🌐 API corriendo en: http://localhost:5001")
    
    api_app.run(debug=True, port=5001, host='0.0.0.0')
