#!/usr/bin/env python3
"""
API Simple de Conexión para Revendedores51
Formato compatible con: https://inefablerevendedores.co/api.php?action=recarga&usuario=X&clave=X&tipo=recargaPinFreefire&monto=1&numero=0
"""

from flask import Flask, request, jsonify
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
from request_security import consume_rate_limit, get_request_client_ip

# Crear aplicación Flask
app = Flask(__name__)

# Configuración de la base de datos (usar la misma que la aplicación principal)
DATABASE = os.environ.get('DATABASE_PATH', 'usuarios.db')
SIMPLE_API_RATE_LIMIT_REQUESTS = max(int(os.environ.get('SIMPLE_API_RATE_LIMIT_REQUESTS', '90')), 1)
SIMPLE_API_RATE_LIMIT_WINDOW_SECONDS = max(int(os.environ.get('SIMPLE_API_RATE_LIMIT_WINDOW_SECONDS', '60')), 1)


def _rate_limited_response(message, rate_state):
    response = jsonify({'status': 'error', 'code': '429', 'message': message})
    response.status_code = 429
    response.headers['Retry-After'] = str(rate_state['retry_after'])
    response.headers['X-RateLimit-Limit'] = str(rate_state['limit'])
    response.headers['X-RateLimit-Remaining'] = str(rate_state['remaining'])
    response.headers['X-RateLimit-Window'] = str(rate_state['window_seconds'])
    return response

def get_db_connection():
    """Obtiene una conexión a la base de datos"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def verify_password(password, hashed):
    """Verifica la contraseña hasheada (compatible con métodos antiguos y nuevos)"""
    # Intentar con Werkzeug (maneja pbkdf2, scrypt, etc.)
    if hashed.startswith(('pbkdf2:', 'scrypt:')):
        return check_password_hash(hashed, password)
    
    # Si no es un hash de Werkzeug, verificar con SHA256 (método anterior)
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
    conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_tx_user_request_id_simple ON transacciones(usuario_id, request_id)')

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

@app.route('/api.php', methods=['GET'])
def api_endpoint():
    """
    Endpoint principal de la API
    
    Formato: /api.php?action=recarga&usuario=email&clave=password&tipo=recargaPinFreefire&monto=1&numero=0
    
    Parámetros:
    - action: Siempre debe ser "recarga"
    - usuario: Email del usuario
    - clave: Contraseña del usuario
    - tipo: Tipo de recarga (recargaPinFreefire)
    - monto: ID del paquete (1-9)
    - numero: Cantidad de PINs (por defecto 1, máximo 10)
    """

    try:
        rate_state = consume_rate_limit(
            'simple_connection_api',
            get_request_client_ip(request),
            SIMPLE_API_RATE_LIMIT_REQUESTS,
            SIMPLE_API_RATE_LIMIT_WINDOW_SECONDS,
        )
        if not rate_state['allowed']:
            return _rate_limited_response('Demasiadas solicitudes a la API Simple.', rate_state)

        # Obtener parámetros
        action = request.args.get('action', '').lower()
        usuario = request.args.get('usuario', '')
        clave = request.args.get('clave', '')
        tipo = request.args.get('tipo', '').lower()
        monto = request.args.get('monto', '1')
        numero = request.args.get('numero', '1')
        request_id = (request.args.get('request_id', '') or '').strip()
        
        # Validar parámetros básicos
        if not all([action, usuario, clave, tipo]):
            return jsonify({
                'status': 'error',
                'code': '400',
                'message': 'Parámetros requeridos: action, usuario, clave, tipo'
            }), 400
        
        # Validar action
        if action != 'recarga':
            return jsonify({
                'status': 'error',
                'code': '400',
                'message': 'Action debe ser "recarga"'
            }), 400
        
        # Validar tipo
        if tipo != 'recargapinfreefire':
            return jsonify({
                'status': 'error',
                'code': '400',
                'message': 'Tipo debe ser "recargaPinFreefire"'
            }), 400
        
        # Validar y convertir monto (package_id)
        try:
            package_id = int(monto)
            if package_id < 1 or package_id > 9:
                return jsonify({
                    'status': 'error',
                    'code': '400',
                    'message': 'Monto debe estar entre 1 y 9'
                }), 400
        except ValueError:
            return jsonify({
                'status': 'error',
                'code': '400',
                'message': 'Monto debe ser un número válido'
            }), 400
        
        # Validar y convertir numero (quantity)
        try:
            quantity = int(numero) if numero else 1
            if quantity < 1 or quantity > 10:
                return jsonify({
                    'status': 'error',
                    'code': '400',
                    'message': 'Numero debe estar entre 1 y 10'
                }), 400
        except ValueError:
            return jsonify({
                'status': 'error',
                'code': '400',
                'message': 'Numero debe ser un número válido'
            }), 400
        
        # Autenticar usuario
        user = get_user_by_email(usuario)
        
        if not user or not verify_password(clave, user['contraseña']):
            return jsonify({
                'status': 'error',
                'code': '401',
                'message': 'Credenciales incorrectas'
            }), 401

        endpoint_key = 'simple_connection_api_purchase'
        if request_id:
            conn_idem = get_db_connection()
            try:
                idem_state = begin_idempotent_purchase(conn_idem, user['id'], endpoint_key, request_id)
                conn_idem.commit()
            except Exception:
                conn_idem.rollback()
                conn_idem.close()
                return jsonify({'status': 'error', 'code': '500', 'message': 'No se pudo registrar la solicitud idempotente'}), 500
            finally:
                try:
                    conn_idem.close()
                except Exception:
                    pass

            if idem_state['state'] == 'completed' and idem_state.get('payload'):
                return jsonify(idem_state['payload'])
            if idem_state['state'] == 'processing':
                return jsonify({'status': 'error', 'code': '409', 'message': 'Esta compra ya se está procesando'}), 409
        
        # Obtener información del paquete
        packages_info = get_package_info_with_prices()
        package_info = packages_info.get(package_id)
        
        if not package_info:
            if request_id:
                conn_cleanup = get_db_connection()
                clear_idempotent_purchase(conn_cleanup, user['id'], endpoint_key, request_id)
                conn_cleanup.commit()
                conn_cleanup.close()
            return jsonify({
                'status': 'error',
                'code': '404',
                'message': 'Paquete no encontrado'
            }), 404
        
        precio_unitario = package_info['precio']
        precio_total = precio_unitario * quantity
        saldo_actual = user['saldo']
        
        # Verificar saldo suficiente
        if saldo_actual < precio_total:
            if request_id:
                conn_cleanup = get_db_connection()
                clear_idempotent_purchase(conn_cleanup, user['id'], endpoint_key, request_id)
                conn_cleanup.commit()
                conn_cleanup.close()
            return jsonify({
                'status': 'error',
                'code': '402',
                'message': f'Saldo insuficiente. Necesitas ${precio_total:.2f} pero tienes ${saldo_actual:.2f}'
            }), 402
        
        # Usar pin manager para obtener PINs
        pin_manager = create_pin_manager(DATABASE)
        pins_list = []
        local_pins_reserved = []
        
        if quantity == 1:
            # Para un solo PIN
            result = pin_manager.request_pin(package_id)
            
            if result.get('status') != 'success':
                if request_id:
                    conn_cleanup = get_db_connection()
                    clear_idempotent_purchase(conn_cleanup, user['id'], endpoint_key, request_id)
                    conn_cleanup.commit()
                    conn_cleanup.close()
                return jsonify({
                    'status': 'error',
                    'code': '503',
                    'message': f'Sin stock disponible para este paquete'
                }), 503
            
            pin_code = result.get('pin_code')
            pins_list = [pin_code]
            if result.get('source') == 'local_stock' and pin_code:
                local_pins_reserved = [pin_code]
        else:
            # Para múltiples PINs
            result = pin_manager.request_multiple_pins(package_id, quantity)
            
            if result.get('status') not in ['success', 'partial_success']:
                if request_id:
                    conn_cleanup = get_db_connection()
                    clear_idempotent_purchase(conn_cleanup, user['id'], endpoint_key, request_id)
                    conn_cleanup.commit()
                    conn_cleanup.close()
                return jsonify({
                    'status': 'error',
                    'code': '503',
                    'message': f'Error al obtener PINs: {result.get("message", "Sin stock disponible")}'
                }), 503
            
            pines_data = result.get('pins', [])
            pins_list = [pin['pin_code'] for pin in pines_data]
            local_pins_reserved = [pin['pin_code'] for pin in pines_data if pin.get('source') == 'local_stock' and pin.get('pin_code')]
            
            if len(pins_list) < quantity:
                # Ajustar cantidad y precio si no se obtuvieron todos los PINs
                quantity = len(pins_list)
                precio_total = precio_unitario * quantity
        
        conn = get_db_connection()
        try:
            debit_result = debit_user_balance_atomic(conn, user['id'], precio_total)
            if not debit_result['ok']:
                if local_pins_reserved:
                    pin_manager.restore_local_pins(package_id, local_pins_reserved)
                    local_pins_reserved = []
                if request_id:
                    clear_idempotent_purchase(conn, user['id'], endpoint_key, request_id)
                return jsonify({
                    'status': 'error',
                    'code': '402',
                    'message': f'Saldo insuficiente. Necesitas ${precio_total:.2f} pero tienes ${debit_result["saldo_actual"]:.2f}'
                }), 402

            saldo_actual = debit_result['saldo_antes']
            nuevo_saldo = debit_result['saldo_despues']

            # Crear registro de transacción en la misma transacción
            pins_texto = '\n'.join(pins_list)
            paquete_nombre = f"{package_info['nombre']} x{quantity}" if quantity > 1 else package_info['nombre']
            transaction_data = create_transaction_record(user['id'], pins_texto, paquete_nombre, precio_total, conn=conn, request_id=request_id)
            persist_purchase_metrics(
                conn,
                user['id'],
                package_id,
                quantity,
                paquete_nombre,
                pins_texto,
                precio_total,
                saldo_actual,
                nuevo_saldo,
                transaction_data['transaccion_id']
            )

            final_payload = {
                'status': 'success',
                'code': '200',
                'message': f'{"PIN obtenido" if quantity == 1 else f"{quantity} PINs obtenidos"} exitosamente',
                'data': {
                    'usuario': f"{user['nombre']} {user['apellido']}",
                    'email': user['correo'],
                    'paquete': package_info['nombre'],
                    'precio_unitario': float(precio_unitario),
                    'cantidad': quantity,
                    'precio_total': float(precio_total),
                    'saldo_anterior': float(saldo_actual),
                    'saldo_nuevo': float(nuevo_saldo),
                    'numero_control': transaction_data['numero_control'],
                    'transaccion_id': transaction_data['transaccion_id'],
                    'fecha': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            }
            if quantity == 1:
                final_payload['data']['pin'] = pins_list[0]
            else:
                final_payload['data']['pines'] = pins_list

            if request_id:
                complete_idempotent_purchase(conn, user['id'], endpoint_key, request_id, final_payload, transaction_data['transaccion_id'], transaction_data['numero_control'])

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
            'code': '500',
            'message': f'Error interno del servidor: {str(e)}'
        }), 500

@app.route('/api.php', methods=['POST'])
def api_endpoint_post():
    """Endpoint POST (redirige al GET para compatibilidad)"""
    return jsonify({
        'status': 'error',
        'code': '405',
        'message': 'Usar método GET con parámetros en la URL'
    }), 405

@app.route('/health', methods=['GET'])
def health_check():
    """Health check simple"""
    return jsonify({
        'status': 'success',
        'code': '200',
        'message': 'API Revendedores51 funcionando correctamente',
        'service': 'Revendedores51 Simple API',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'version': '1.0.0'
    })

@app.route('/', methods=['GET'])
def root():
    """Página de información de la API"""
    return jsonify({
        'status': 'success',
        'message': 'API de Conexión Revendedores51',
        'service': 'Revendedores51 Simple API',
        'version': '1.0.0',
        'endpoints': {
            'recarga': '/api.php?action=recarga&usuario=EMAIL&clave=PASSWORD&tipo=recargaPinFreefire&monto=PACKAGE_ID&numero=QUANTITY',
            'health': '/health'
        },
        'example': 'https://inefablerevendedores.co/api.php?action=recarga&usuario=test@ejemplo.com&clave=test123&tipo=recargaPinFreefire&monto=1&numero=1',
        'documentation': 'Contacta al administrador para más información'
    })

# Manejo de errores
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'status': 'error',
        'code': '404',
        'message': 'Endpoint no encontrado. Usar: /api.php?action=recarga&usuario=EMAIL&clave=PASSWORD&tipo=recargaPinFreefire&monto=PACKAGE_ID&numero=QUANTITY'
    }), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        'status': 'error',
        'code': '405',
        'message': 'Método no permitido. Usar GET con parámetros en la URL'
    }), 405

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'status': 'error',
        'code': '500',
        'message': 'Error interno del servidor'
    }), 500

if __name__ == '__main__':
    print("🔗 Iniciando API Simple de Conexión para Revendedores51...")
    print("=" * 70)
    print("📍 Formato de URL:")
    print("   https://inefablerevendedores.co/api.php?action=recarga&usuario=EMAIL&clave=PASSWORD&tipo=recargaPinFreefire&monto=PACKAGE_ID&numero=QUANTITY")
    print()
    print("📋 Parámetros:")
    print("   • action: recarga (obligatorio)")
    print("   • usuario: Email del usuario (obligatorio)")
    print("   • clave: Contraseña del usuario (obligatorio)")
    print("   • tipo: recargaPinFreefire (obligatorio)")
    print("   • monto: ID del paquete 1-9 (obligatorio)")
    print("   • numero: Cantidad de PINs 1-10 (opcional, por defecto 1)")
    print()
    print("💡 Ejemplo:")
    print("   /api.php?action=recarga&usuario=test@ejemplo.com&clave=test123&tipo=recargaPinFreefire&monto=1&numero=1")
    print("=" * 70)
    print("🌐 API corriendo en: http://localhost:5003")
    print("🔗 Para producción: https://inefablerevendedores.co/")
    print("=" * 70)
    
    app.run(debug=True, port=5003, host='0.0.0.0')
