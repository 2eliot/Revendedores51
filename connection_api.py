#!/usr/bin/env python3
"""
API de Conexión para Revendedores51
Permite autenticación, verificación de saldo y obtención de PINs con descuento automático
"""

from flask import Flask, jsonify, request
import sqlite3
import hashlib
import os
import secrets
from datetime import datetime
import random
import string
from werkzeug.security import check_password_hash
from pin_manager import create_pin_manager

# Crear aplicación Flask para API de conexión
connection_app = Flask(__name__)

# Configuración de seguridad
connection_app.secret_key = os.environ.get('CONNECTION_API_SECRET_KEY', secrets.token_hex(32))

# Configuración de la base de datos (usar la misma que la aplicación principal)
DATABASE = os.environ.get('DATABASE_PATH', 'usuarios.db')

def get_db_connection():
    """Obtiene una conexión a la base de datos"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def verify_password(password, hashed):
    """Verifica la contraseña hasheada (compatible con métodos antiguos y nuevos)"""
    # Primero intentar con el nuevo método (PBKDF2)
    if hashed.startswith('pbkdf2:'):
        return check_password_hash(hashed, password)
    
    # Si no es PBKDF2, verificar con SHA256 (método anterior)
    sha256_hash = hashlib.sha256(password.encode()).hexdigest()
    return hashed == sha256_hash

def get_user_by_email(email):
    """Obtiene un usuario por su email"""
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM usuarios WHERE correo = ?', (email,)).fetchone()
    conn.close()
    return user

def get_package_info_with_prices():
    """Obtiene información de paquetes con precios dinámicos"""
    conn = get_db_connection()
    packages = conn.execute('''
        SELECT id, nombre, precio, descripcion 
        FROM precios_paquetes 
        WHERE activo = TRUE 
        ORDER BY id
    ''').fetchall()
    conn.close()
    
    # Convertir a diccionario para fácil acceso
    package_dict = {}
    for package in packages:
        package_dict[package['id']] = {
            'nombre': package['nombre'],
            'precio': package['precio'],
            'descripcion': package['descripcion']
        }
    
    return package_dict

def create_transaction_record(user_id, pin_code, package_info, precio):
    """Crea un registro de transacción"""
    # Generar datos de la transacción
    numero_control = ''.join(random.choices(string.digits, k=10))
    transaccion_id = 'API-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    conn = get_db_connection()
    try:
        # Registrar la transacción
        conn.execute('''
            INSERT INTO transacciones (usuario_id, numero_control, pin, transaccion_id, monto)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, numero_control, pin_code, transaccion_id, -precio))
        
        # Limitar transacciones a 30 por usuario
        conn.execute('''
            DELETE FROM transacciones 
            WHERE usuario_id = ? AND id NOT IN (
                SELECT id FROM transacciones 
                WHERE usuario_id = ? 
                ORDER BY fecha DESC 
                LIMIT 30
            )
        ''', (user_id, user_id))
        
        conn.commit()
        return {
            'numero_control': numero_control,
            'transaccion_id': transaccion_id
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# ============= ENDPOINTS DE LA API DE CONEXIÓN =============

@connection_app.route('/api/connection/health', methods=['GET'])
def health_check():
    """Endpoint para verificar que la API de conexión está funcionando"""
    return jsonify({
        'status': 'success',
        'message': 'API de Conexión funcionando correctamente',
        'service': 'Revendedores51 Connection API',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

@connection_app.route('/api/connection/login', methods=['POST'])
def api_login():
    """
    Endpoint de autenticación para la API de conexión
    
    Body JSON:
    {
        "email": "usuario@ejemplo.com",
        "password": "contraseña"
    }
    
    Response:
    {
        "status": "success",
        "message": "Login exitoso",
        "data": {
            "user_id": 123,
            "name": "Juan Pérez",
            "email": "usuario@ejemplo.com",
            "balance": 15.50,
            "token": "auth_token_here"
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No se recibieron datos JSON'
            }), 400
        
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({
                'status': 'error',
                'message': 'Email y contraseña son requeridos'
            }), 400
        
        # Buscar usuario en la base de datos
        user = get_user_by_email(email)
        
        if not user or not verify_password(password, user['contraseña']):
            return jsonify({
                'status': 'error',
                'message': 'Credenciales incorrectas'
            }), 401
        
        # Generar token simple (en producción usar JWT)
        auth_token = secrets.token_urlsafe(32)
        
        return jsonify({
            'status': 'success',
            'message': 'Login exitoso',
            'data': {
                'user_id': user['id'],
                'name': f"{user['nombre']} {user['apellido']}",
                'email': user['correo'],
                'balance': float(user['saldo']),
                'token': auth_token,
                'phone': user['telefono']
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error en autenticación: {str(e)}'
        }), 500

@connection_app.route('/api/connection/balance/<int:user_id>', methods=['GET'])
def get_user_balance(user_id):
    """
    Obtiene el saldo actual de un usuario
    
    Response:
    {
        "status": "success",
        "data": {
            "user_id": 123,
            "balance": 15.50,
            "last_updated": "2024-01-15T10:30:00"
        }
    }
    """
    try:
        conn = get_db_connection()
        user = conn.execute('''
            SELECT id, nombre, apellido, saldo 
            FROM usuarios WHERE id = ?
        ''', (user_id,)).fetchone()
        conn.close()
        
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'Usuario no encontrado'
            }), 404
        
        return jsonify({
            'status': 'success',
            'data': {
                'user_id': user['id'],
                'name': f"{user['nombre']} {user['apellido']}",
                'balance': float(user['saldo']),
                'last_updated': datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error al obtener saldo: {str(e)}'
        }), 500

@connection_app.route('/api/connection/packages', methods=['GET'])
def get_available_packages():
    """
    Obtiene todos los paquetes disponibles con precios
    
    Response:
    {
        "status": "success",
        "data": [
            {
                "id": 1,
                "name": "110 💎",
                "price": 0.66,
                "description": "110 Diamantes Free Fire"
            }
        ]
    }
    """
    try:
        packages_info = get_package_info_with_prices()
        
        packages_list = []
        for package_id, package_data in packages_info.items():
            packages_list.append({
                'id': package_id,
                'name': package_data['nombre'],
                'price': float(package_data['precio']),
                'description': package_data['descripcion']
            })
        
        return jsonify({
            'status': 'success',
            'data': packages_list,
            'total': len(packages_list)
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error al obtener paquetes: {str(e)}'
        }), 500

@connection_app.route('/api/connection/purchase', methods=['POST'])
def purchase_pin():
    """
    Compra un PIN verificando saldo y descontándolo automáticamente
    
    Body JSON:
    {
        "user_id": 123,
        "package_id": 1,
        "quantity": 1
    }
    
    Response:
    {
        "status": "success",
        "message": "PIN obtenido exitosamente",
        "data": {
            "pin": "ABCD-EFGH-1234",
            "package_name": "110 💎",
            "price": 0.66,
            "transaction_id": "API-ABC123",
            "control_number": "1234567890",
            "new_balance": 14.84,
            "timestamp": "2024-01-15T10:30:00"
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No se recibieron datos JSON'
            }), 400
        
        user_id = data.get('user_id')
        package_id = data.get('package_id')
        quantity = data.get('quantity', 1)
        
        if not user_id or not package_id:
            return jsonify({
                'status': 'error',
                'message': 'user_id y package_id son requeridos'
            }), 400
        
        # Validar cantidad
        if quantity < 1 or quantity > 10:
            return jsonify({
                'status': 'error',
                'message': 'La cantidad debe estar entre 1 y 10'
            }), 400
        
        # Obtener información del usuario
        conn = get_db_connection()
        user = conn.execute('''
            SELECT id, nombre, apellido, saldo 
            FROM usuarios WHERE id = ?
        ''', (user_id,)).fetchone()
        
        if not user:
            conn.close()
            return jsonify({
                'status': 'error',
                'message': 'Usuario no encontrado'
            }), 404
        
        # Obtener información del paquete
        packages_info = get_package_info_with_prices()
        package_info = packages_info.get(package_id)
        
        if not package_info:
            conn.close()
            return jsonify({
                'status': 'error',
                'message': 'Paquete no encontrado'
            }), 404
        
        precio_unitario = package_info['precio']
        precio_total = precio_unitario * quantity
        saldo_actual = user['saldo']
        
        # Verificar saldo suficiente
        if saldo_actual < precio_total:
            conn.close()
            return jsonify({
                'status': 'error',
                'message': f'Saldo insuficiente. Necesitas ${precio_total:.2f} pero tienes ${saldo_actual:.2f}'
            }), 400
        
        # Usar pin manager para obtener PINs
        pin_manager = create_pin_manager(DATABASE)
        
        if quantity == 1:
            # Para un solo PIN
            result = pin_manager.request_pin(package_id)
            
            if result.get('status') != 'success':
                conn.close()
                return jsonify({
                    'status': 'error',
                    'message': f'Sin stock disponible para este paquete: {result.get("message", "Error desconocido")}'
                }), 400
            
            pin_code = result.get('pin_code')
            pins_list = [pin_code]
        else:
            # Para múltiples PINs
            result = pin_manager.request_multiple_pins(package_id, quantity)
            
            if result.get('status') not in ['success', 'partial_success']:
                conn.close()
                return jsonify({
                    'status': 'error',
                    'message': f'Error al obtener PINs: {result.get("message", "Error desconocido")}'
                }), 400
            
            pines_data = result.get('pins', [])
            pins_list = [pin['pin_code'] for pin in pines_data]
            
            if len(pins_list) < quantity:
                # Ajustar cantidad y precio si no se obtuvieron todos los PINs
                quantity = len(pins_list)
                precio_total = precio_unitario * quantity
        
        # Descontar saldo
        nuevo_saldo = saldo_actual - precio_total
        conn.execute('UPDATE usuarios SET saldo = ? WHERE id = ?', (nuevo_saldo, user_id))
        
        # Crear registro de transacción
        pins_texto = '\n'.join(pins_list)
        transaction_data = create_transaction_record(user_id, pins_texto, package_info, precio_total)
        
        conn.commit()
        conn.close()
        
        # Preparar respuesta
        response_data = {
            'package_name': package_info['nombre'],
            'package_description': package_info['descripcion'],
            'price_per_unit': float(precio_unitario),
            'quantity': quantity,
            'total_price': float(precio_total),
            'transaction_id': transaction_data['transaccion_id'],
            'control_number': transaction_data['numero_control'],
            'new_balance': float(nuevo_saldo),
            'timestamp': datetime.now().isoformat()
        }
        
        if quantity == 1:
            response_data['pin'] = pins_list[0]
        else:
            response_data['pins'] = pins_list
        
        return jsonify({
            'status': 'success',
            'message': f'{"PIN obtenido" if quantity == 1 else f"{quantity} PINs obtenidos"} exitosamente',
            'data': response_data
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error al procesar compra: {str(e)}'
        }), 500

@connection_app.route('/api/connection/stock', methods=['GET'])
def get_stock_status():
    """
    Obtiene el estado del stock de PINs disponibles
    
    Response:
    {
        "status": "success",
        "data": {
            "1": 50,
            "2": 30,
            "3": 25
        },
        "total_pins": 105
    }
    """
    try:
        pin_manager = create_pin_manager(DATABASE)
        local_stock = pin_manager.get_local_stock()
        
        return jsonify({
            'status': 'success',
            'data': local_stock,
            'total_pins': sum(local_stock.values())
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error al obtener stock: {str(e)}'
        }), 500

@connection_app.route('/api/connection/user/<int:user_id>/transactions', methods=['GET'])
def get_user_transactions(user_id):
    """
    Obtiene las transacciones recientes de un usuario
    
    Response:
    {
        "status": "success",
        "data": [
            {
                "id": 123,
                "transaction_id": "API-ABC123",
                "control_number": "1234567890",
                "amount": -0.66,
                "date": "2024-01-15T10:30:00",
                "pin": "ABCD-EFGH-1234"
            }
        ]
    }
    """
    try:
        limit = request.args.get('limit', 10, type=int)
        if limit > 50:
            limit = 50
        
        conn = get_db_connection()
        
        # Verificar que el usuario existe
        user = conn.execute('SELECT id FROM usuarios WHERE id = ?', (user_id,)).fetchone()
        if not user:
            conn.close()
            return jsonify({
                'status': 'error',
                'message': 'Usuario no encontrado'
            }), 404
        
        transactions = conn.execute('''
            SELECT id, numero_control, pin, transaccion_id, monto, fecha
            FROM transacciones 
            WHERE usuario_id = ? 
            ORDER BY fecha DESC 
            LIMIT ?
        ''', (user_id, limit)).fetchall()
        conn.close()
        
        transactions_list = []
        for transaction in transactions:
            transactions_list.append({
                'id': transaction['id'],
                'transaction_id': transaction['transaccion_id'],
                'control_number': transaction['numero_control'],
                'amount': float(transaction['monto']),
                'date': transaction['fecha'],
                'pin': transaction['pin']
            })
        
        return jsonify({
            'status': 'success',
            'data': transactions_list,
            'total': len(transactions_list)
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error al obtener transacciones: {str(e)}'
        }), 500

# Manejo de errores
@connection_app.errorhandler(404)
def not_found(error):
    return jsonify({
        'status': 'error',
        'message': 'Endpoint no encontrado',
        'available_endpoints': [
            'GET /api/connection/health',
            'POST /api/connection/login',
            'GET /api/connection/balance/<user_id>',
            'GET /api/connection/packages',
            'POST /api/connection/purchase',
            'GET /api/connection/stock',
            'GET /api/connection/user/<user_id>/transactions'
        ]
    }), 404

@connection_app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        'status': 'error',
        'message': 'Método no permitido'
    }), 405

@connection_app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'status': 'error',
        'message': 'Error interno del servidor'
    }), 500

if __name__ == '__main__':
    print("🔗 Iniciando API de Conexión para Revendedores51...")
    print("=" * 60)
    print("📍 Endpoints disponibles:")
    print("   GET  /api/connection/health - Verificar estado de la API")
    print("   POST /api/connection/login - Autenticación de usuario")
    print("   GET  /api/connection/balance/<user_id> - Obtener saldo de usuario")
    print("   GET  /api/connection/packages - Obtener paquetes disponibles")
    print("   POST /api/connection/purchase - Comprar PIN con descuento automático")
    print("   GET  /api/connection/stock - Obtener estado del stock")
    print("   GET  /api/connection/user/<user_id>/transactions - Obtener transacciones")
    print("=" * 60)
    print("🌐 API de Conexión corriendo en: http://localhost:5002")
    print("🔗 URL de tu web: https://revendedores51.onrender.com/")
    print("=" * 60)
    
    connection_app.run(debug=True, port=5002, host='0.0.0.0')
