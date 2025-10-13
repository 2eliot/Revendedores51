#!/usr/bin/env python3
"""
API Simple de Conexión para Revendedores51
Formato compatible con: https://revendedores51.onrender.com/api.php?action=recarga&usuario=X&clave=X&tipo=recargaPinFreefire&monto=1&numero=0
"""

from flask import Flask, request, jsonify
import sqlite3
import hashlib
import os
import secrets
from datetime import datetime
import random
import string
from werkzeug.security import check_password_hash
from pin_manager import create_pin_manager

# Crear aplicación Flask
app = Flask(__name__)

# Configuración de la base de datos (usar la misma que la aplicación principal)
DATABASE = os.environ.get('DATABASE_PATH', 'usuarios.db')

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
        # Obtener parámetros
        action = request.args.get('action', '').lower()
        usuario = request.args.get('usuario', '')
        clave = request.args.get('clave', '')
        tipo = request.args.get('tipo', '').lower()
        monto = request.args.get('monto', '1')
        numero = request.args.get('numero', '1')
        
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
        
        # Obtener información del paquete
        packages_info = get_package_info_with_prices()
        package_info = packages_info.get(package_id)
        
        if not package_info:
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
            return jsonify({
                'status': 'error',
                'code': '402',
                'message': f'Saldo insuficiente. Necesitas ${precio_total:.2f} pero tienes ${saldo_actual:.2f}'
            }), 402
        
        # Usar pin manager para obtener PINs
        pin_manager = create_pin_manager(DATABASE)
        
        if quantity == 1:
            # Para un solo PIN
            result = pin_manager.request_pin(package_id)
            
            if result.get('status') != 'success':
                return jsonify({
                    'status': 'error',
                    'code': '503',
                    'message': f'Sin stock disponible para este paquete'
                }), 503
            
            pin_code = result.get('pin_code')
            pins_list = [pin_code]
        else:
            # Para múltiples PINs
            result = pin_manager.request_multiple_pins(package_id, quantity)
            
            if result.get('status') not in ['success', 'partial_success']:
                return jsonify({
                    'status': 'error',
                    'code': '503',
                    'message': f'Error al obtener PINs: {result.get("message", "Sin stock disponible")}'
                }), 503
            
            pines_data = result.get('pins', [])
            pins_list = [pin['pin_code'] for pin in pines_data]
            
            if len(pins_list) < quantity:
                # Ajustar cantidad y precio si no se obtuvieron todos los PINs
                quantity = len(pins_list)
                precio_total = precio_unitario * quantity
        
        # Descontar saldo
        conn = get_db_connection()
        nuevo_saldo = saldo_actual - precio_total
        conn.execute('UPDATE usuarios SET saldo = ? WHERE id = ?', (nuevo_saldo, user['id']))
        
        # Crear registro de transacción
        pins_texto = '\n'.join(pins_list)
        transaction_data = create_transaction_record(user['id'], pins_texto, package_info, precio_total)
        
        conn.commit()
        conn.close()
        
        # Preparar respuesta exitosa
        response_data = {
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
        
        # Agregar PIN(s) a la respuesta
        if quantity == 1:
            response_data['data']['pin'] = pins_list[0]
        else:
            response_data['data']['pines'] = pins_list
        
        return jsonify(response_data)
        
    except Exception as e:
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
        'example': 'https://revendedores51.onrender.com/api.php?action=recarga&usuario=test@ejemplo.com&clave=test123&tipo=recargaPinFreefire&monto=1&numero=1',
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
    print("   https://revendedores51.onrender.com/api.php?action=recarga&usuario=EMAIL&clave=PASSWORD&tipo=recargaPinFreefire&monto=PACKAGE_ID&numero=QUANTITY")
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
    print("🔗 Para producción: https://revendedores51.onrender.com/")
    print("=" * 70)
    
    app.run(debug=True, port=5003, host='0.0.0.0')
