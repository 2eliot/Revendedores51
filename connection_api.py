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
import pytz
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

def ensure_idempotency_schema(conn):
    """Asegura columnas y tabla necesarias para idempotencia en compras API."""
    conn.execute('''
        CREATE TABLE IF NOT EXISTS purchase_request_idempotency (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            endpoint TEXT NOT NULL,
            request_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'processing',
            response_payload TEXT,
            transaccion_id TEXT,
            numero_control TEXT,
            fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
            fecha_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(usuario_id, endpoint, request_id)
        )
    ''')
    try:
        conn.execute('ALTER TABLE transacciones ADD COLUMN request_id TEXT')
    except Exception:
        pass
    conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_tx_user_request_id_connection ON transacciones(usuario_id, request_id)')

def debit_user_balance_atomic(conn, user_id, amount):
    """Descuenta saldo de forma atómica y valida fondos en la misma operación."""
    amount = round(float(amount), 2)
    cursor = conn.execute(
        'UPDATE usuarios SET saldo = saldo - ? WHERE id = ? AND saldo >= ?',
        (amount, user_id, amount)
    )

    if cursor.rowcount == 0:
        row = conn.execute('SELECT saldo FROM usuarios WHERE id = ?', (user_id,)).fetchone()
        return {
            'ok': False,
            'saldo_actual': float(row['saldo']) if row else 0.0,
        }

    row = conn.execute('SELECT saldo FROM usuarios WHERE id = ?', (user_id,)).fetchone()
    saldo_despues = float(row['saldo']) if row else 0.0
    return {
        'ok': True,
        'saldo_antes': round(saldo_despues + amount, 2),
        'saldo_despues': saldo_despues,
    }

def begin_idempotent_purchase(conn, user_id, endpoint, request_id):
    ensure_idempotency_schema(conn)
    try:
        conn.execute(
            'INSERT INTO purchase_request_idempotency (usuario_id, endpoint, request_id, status) VALUES (?, ?, ?, ?)',
            (user_id, endpoint, request_id, 'processing')
        )
        return {'state': 'new'}
    except Exception:
        row = conn.execute(
            'SELECT status, response_payload FROM purchase_request_idempotency WHERE usuario_id = ? AND endpoint = ? AND request_id = ?',
            (user_id, endpoint, request_id)
        ).fetchone()
        payload = {}
        if row and row['response_payload']:
            try:
                payload = json.loads(row['response_payload'])
            except Exception:
                payload = {}
        return {'state': row['status'] if row else 'processing', 'payload': payload}

def complete_idempotent_purchase(conn, user_id, endpoint, request_id, payload, transaction_id='', control_number=''):
    conn.execute(
        '''UPDATE purchase_request_idempotency
           SET status = 'completed', response_payload = ?, transaccion_id = ?, numero_control = ?, fecha_actualizacion = CURRENT_TIMESTAMP
           WHERE usuario_id = ? AND endpoint = ? AND request_id = ?''',
        (json.dumps(payload, ensure_ascii=False), transaction_id, control_number, user_id, endpoint, request_id)
    )

def clear_idempotent_purchase(conn, user_id, endpoint, request_id):
    conn.execute(
        'DELETE FROM purchase_request_idempotency WHERE usuario_id = ? AND endpoint = ? AND request_id = ?',
        (user_id, endpoint, request_id)
    )

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

def create_transaction_record(user_id, pin_code, paquete_nombre, precio, conn=None, request_id=None):
    """Crea un registro de transacción, persistiendo paquete_nombre"""
    # Generar datos de la transacción
    numero_control = ''.join(random.choices(string.digits, k=10))
    transaccion_id = 'API-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

    owns_connection = conn is None
    if owns_connection:
        conn = get_db_connection()

    try:
        ensure_idempotency_schema(conn)
        # Asegurar columna paquete_nombre (si la API corre independiente del init)
        try:
            conn.execute("ALTER TABLE transacciones ADD COLUMN paquete_nombre TEXT")
        except Exception:
            pass
        # Registrar la transacción
        conn.execute('''
            INSERT INTO transacciones (usuario_id, numero_control, pin, transaccion_id, paquete_nombre, monto, request_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, numero_control, pin_code, transaccion_id, paquete_nombre, -precio, request_id))
        
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

        if owns_connection:
            conn.commit()
        return {
            'numero_control': numero_control,
            'transaccion_id': transaccion_id
        }
    except Exception as e:
        if owns_connection:
            conn.rollback()
        raise e
    finally:
        if owns_connection:
            conn.close()


def persist_purchase_metrics(conn, user_id, package_id, quantity, paquete_nombre, pin_text, precio_total, saldo_antes, saldo_despues, transaccion_id):
    try:
        conn.execute('''
            INSERT INTO historial_compras (usuario_id, monto, paquete_nombre, pin, tipo_evento, duracion_segundos, saldo_antes, saldo_despues)
            VALUES (?, ?, ?, ?, 'compra', NULL, ?, ?)
        ''', (user_id, precio_total, paquete_nombre, pin_text, saldo_antes, saldo_despues))
    except Exception:
        pass

    try:
        user_row = conn.execute('SELECT sin_ganancia FROM usuarios WHERE id = ?', (user_id,)).fetchone()
        if user_row and user_row['sin_ganancia']:
            return

        quantity = max(1, int(quantity or 1))
        precio_unitario = round(float(precio_total) / quantity, 6)
        costo_row = conn.execute(
            'SELECT precio_compra FROM precios_compra WHERE juego = ? AND paquete_id = ? AND activo = 1',
            ('freefire_latam', int(package_id))
        ).fetchone()
        costo_unit = float(costo_row['precio_compra']) if costo_row else 0.0
        profit_unit = round(precio_unitario - costo_unit, 6)
        profit_total = round(profit_unit * quantity, 6)

        conn.execute('''
            INSERT INTO profit_ledger (usuario_id, juego, paquete_id, cantidad, precio_venta_unit, costo_unit, profit_unit, profit_total, transaccion_id)
            VALUES (?, 'freefire_latam', ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, int(package_id), quantity, precio_unitario, costo_unit, profit_unit, profit_total, transaccion_id))

        tz = pytz.timezone(os.environ.get('DEFAULT_TZ', 'America/Caracas'))
        day = datetime.now(tz).date().isoformat()
        existing = conn.execute('SELECT profit_total FROM profit_daily_aggregate WHERE day = ?', (day,)).fetchone()
        if existing:
            conn.execute(
                "UPDATE profit_daily_aggregate SET profit_total = ?, updated_at = CURRENT_TIMESTAMP WHERE day = ?",
                (round(float(existing['profit_total'] or 0.0) + profit_total, 6), day)
            )
        else:
            conn.execute(
                'INSERT INTO profit_daily_aggregate (day, profit_total) VALUES (?, ?)',
                (day, profit_total)
            )
    except Exception:
        pass

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
        request_id = str(data.get('request_id', '')).strip()
        
        if not user_id or not package_id:
            return jsonify({
                'status': 'error',
                'message': 'user_id y package_id son requeridos'
            }), 400

        endpoint_key = 'connection_api_purchase'
        if request_id:
            conn_idem = get_db_connection()
            try:
                idem_state = begin_idempotent_purchase(conn_idem, user_id, endpoint_key, request_id)
                conn_idem.commit()
            except Exception:
                conn_idem.rollback()
                conn_idem.close()
                return jsonify({'status': 'error', 'message': 'No se pudo registrar la solicitud idempotente'}), 500
            finally:
                try:
                    conn_idem.close()
                except Exception:
                    pass

            if idem_state['state'] == 'completed' and idem_state.get('payload'):
                return jsonify(idem_state['payload'])
            if idem_state['state'] == 'processing':
                return jsonify({'status': 'error', 'message': 'Esta compra ya se está procesando'}), 409
        
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
            if request_id:
                conn_cleanup = get_db_connection()
                clear_idempotent_purchase(conn_cleanup, user_id, endpoint_key, request_id)
                conn_cleanup.commit()
                conn_cleanup.close()
            return jsonify({
                'status': 'error',
                'message': 'Usuario no encontrado'
            }), 404
        
        # Obtener información del paquete
        packages_info = get_package_info_with_prices()
        package_info = packages_info.get(package_id)
        
        if not package_info:
            conn.close()
            if request_id:
                conn_cleanup = get_db_connection()
                clear_idempotent_purchase(conn_cleanup, user_id, endpoint_key, request_id)
                conn_cleanup.commit()
                conn_cleanup.close()
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
            if request_id:
                conn_cleanup = get_db_connection()
                clear_idempotent_purchase(conn_cleanup, user_id, endpoint_key, request_id)
                conn_cleanup.commit()
                conn_cleanup.close()
            return jsonify({
                'status': 'error',
                'message': f'Saldo insuficiente. Necesitas ${precio_total:.2f} pero tienes ${saldo_actual:.2f}'
            }), 400
        
        # Usar pin manager para obtener PINs
        pin_manager = create_pin_manager(DATABASE)
        pins_list = []
        local_pins_reserved = []
        
        if quantity == 1:
            # Para un solo PIN
            result = pin_manager.request_pin(package_id)
            
            if result.get('status') != 'success':
                conn.close()
                if request_id:
                    conn_cleanup = get_db_connection()
                    clear_idempotent_purchase(conn_cleanup, user_id, endpoint_key, request_id)
                    conn_cleanup.commit()
                    conn_cleanup.close()
                return jsonify({
                    'status': 'error',
                    'message': f'Sin stock disponible para este paquete: {result.get("message", "Error desconocido")}'
                }), 400
            
            pin_code = result.get('pin_code')
            pins_list = [pin_code]
            if result.get('source') == 'local_stock' and pin_code:
                local_pins_reserved = [pin_code]
        else:
            # Para múltiples PINs
            result = pin_manager.request_multiple_pins(package_id, quantity)
            
            if result.get('status') not in ['success', 'partial_success']:
                conn.close()
                if request_id:
                    conn_cleanup = get_db_connection()
                    clear_idempotent_purchase(conn_cleanup, user_id, endpoint_key, request_id)
                    conn_cleanup.commit()
                    conn_cleanup.close()
                return jsonify({
                    'status': 'error',
                    'message': f'Error al obtener PINs: {result.get("message", "Error desconocido")}'
                }), 400
            
            pines_data = result.get('pins', [])
            pins_list = [pin['pin_code'] for pin in pines_data]
            local_pins_reserved = [pin['pin_code'] for pin in pines_data if pin.get('source') == 'local_stock' and pin.get('pin_code')]
            
            if len(pins_list) < quantity:
                # Ajustar cantidad y precio si no se obtuvieron todos los PINs
                quantity = len(pins_list)
                precio_total = precio_unitario * quantity
        
        try:
            debit_result = debit_user_balance_atomic(conn, user_id, precio_total)
            if not debit_result['ok']:
                if local_pins_reserved:
                    pin_manager.restore_local_pins(package_id, local_pins_reserved)
                    local_pins_reserved = []
                if request_id:
                    clear_idempotent_purchase(conn, user_id, endpoint_key, request_id)
                return jsonify({
                    'status': 'error',
                    'message': f'Saldo insuficiente. Necesitas ${precio_total:.2f} pero tienes ${debit_result["saldo_actual"]:.2f}'
                }), 400

            saldo_actual = debit_result['saldo_antes']
            nuevo_saldo = debit_result['saldo_despues']

            # Crear registro de transacción en la misma transacción
            pins_texto = '\n'.join(pins_list)
            paquete_nombre = f"{package_info['nombre']} x{quantity}" if quantity > 1 else package_info['nombre']
            transaction_data = create_transaction_record(user_id, pins_texto, paquete_nombre, precio_total, conn=conn, request_id=request_id)
            persist_purchase_metrics(
                conn,
                user_id,
                package_id,
                quantity,
                paquete_nombre,
                pins_texto,
                precio_total,
                saldo_actual,
                nuevo_saldo,
                transaction_data['transaccion_id']
            )

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

            final_payload = {
                'status': 'success',
                'message': f'{"PIN obtenido" if quantity == 1 else f"{quantity} PINs obtenidos"} exitosamente',
                'data': response_data
            }
            if request_id:
                complete_idempotent_purchase(conn, user_id, endpoint_key, request_id, final_payload, transaction_data['transaccion_id'], transaction_data['numero_control'])

            conn.commit()
        except Exception:
            conn.rollback()
            if local_pins_reserved:
                pin_manager.restore_local_pins(package_id, local_pins_reserved)
                local_pins_reserved = []
            raise
        finally:
            conn.close()

        return jsonify(final_payload)
        
    except Exception as e:
        try:
            if 'pin_manager' in locals() and local_pins_reserved:
                pin_manager.restore_local_pins(package_id, local_pins_reserved)
        except Exception:
            pass
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
