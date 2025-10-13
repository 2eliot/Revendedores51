from flask import Flask, render_template, request, redirect, session, flash, jsonify
import sqlite3
import hashlib
import os
import secrets
from datetime import timedelta, datetime
import pytz
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
import threading
from pin_manager import create_pin_manager
from functools import lru_cache
import random
import string

app = Flask(__name__)

# Configuración de seguridad
# En producción, usar variables de entorno
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Configuración de cookies seguras (solo en producción con HTTPS)
is_production = os.environ.get('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_SECURE'] = is_production  # Solo HTTPS en producción
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevenir XSS
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Protección CSRF

# Configuración de duración de sesión (30 minutos)
app.permanent_session_lifetime = timedelta(minutes=30)

# Configuración de correo electrónico (solo 2 variables necesarias)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']

# Inicializar Flask-Mail
mail = Mail(app)

# Configuración de la base de datos con optimizaciones y compatibilidad con Render
def get_render_compatible_db_path():
    """Obtiene la ruta de la base de datos compatible con Render"""
    # Priorizar DATABASE_PATH si está configurado (para disco persistente)
    if os.environ.get('DATABASE_PATH'):
        return os.environ.get('DATABASE_PATH')
    elif os.environ.get('RENDER'):
        # En Render sin disco persistente, usar directorio raíz
        return 'usuarios.db'
    else:
        # En desarrollo local
        return 'usuarios.db'

DATABASE = get_render_compatible_db_path()

# Crear directorio para la base de datos si no existe (tanto local como Render con disco)
db_dir = os.path.dirname(DATABASE)
if db_dir and not os.path.exists(db_dir):
    try:
        os.makedirs(db_dir, exist_ok=True)
        print(f"Directorio creado para base de datos: {db_dir}")
    except Exception as e:
        print(f"Error creando directorio de base de datos: {e}")
        # Si no se puede crear el directorio, usar ruta por defecto
        DATABASE = 'usuarios.db'

def get_db_connection_optimized():
    """Obtiene una conexión optimizada con configuraciones SQLite mejoradas"""
    conn = sqlite3.connect(DATABASE, timeout=20.0)
    conn.row_factory = sqlite3.Row
    # Optimizaciones SQLite para mejor rendimiento
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA cache_size=10000')
    conn.execute('PRAGMA temp_store=MEMORY')
    return conn

def return_db_connection(conn):
    """Cierra la conexión (sin pool para evitar problemas de threading)"""
    conn.close()

def init_db():
    """Inicializa la base de datos con las tablas necesarias - Compatible con Render"""
    conn = None
    try:
        conn = get_db_connection_optimized()
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
    
        # Tabla de pines de Free Fire LATAM
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
        
        # Tabla de pines de Free Fire (nuevo juego)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pines_freefire_global (
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
    
        # Tabla de precios de Free Fire (nuevo juego)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS precios_freefire_global (
                id INTEGER PRIMARY KEY,
                nombre TEXT NOT NULL,
                precio REAL NOT NULL,
                descripcion TEXT NOT NULL,
                activo BOOLEAN DEFAULT TRUE,
                fecha_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP
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
        
        # Tabla de precios de Blood Striker
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS precios_bloodstriker (
                id INTEGER PRIMARY KEY,
                nombre TEXT NOT NULL,
                precio REAL NOT NULL,
                descripcion TEXT NOT NULL,
                activo BOOLEAN DEFAULT TRUE,
                fecha_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla de transacciones de Blood Striker
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transacciones_bloodstriker (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER,
                player_id TEXT NOT NULL,
                paquete_id INTEGER NOT NULL,
                numero_control TEXT NOT NULL,
                transaccion_id TEXT NOT NULL,
                monto REAL DEFAULT 0.0,
                estado TEXT DEFAULT 'pendiente',
                fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
                fecha_procesado DATETIME NULL,
                admin_id INTEGER NULL,
                notas TEXT NULL,
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id),
                FOREIGN KEY (admin_id) REFERENCES usuarios (id)
            )
        ''')
        
        # Tabla de configuración de fuentes de pines por monto
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS configuracion_fuentes_pines (
                monto_id INTEGER PRIMARY KEY,
                fuente TEXT NOT NULL DEFAULT 'local',
                activo BOOLEAN DEFAULT TRUE,
                fecha_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP,
                CHECK (fuente IN ('local', 'api_externa'))
            )
        ''')
        
        # Tabla de créditos de billetera
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS creditos_billetera (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER,
                monto REAL DEFAULT 0.0,
                saldo_anterior REAL DEFAULT 0.0,
                fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
                visto BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
            )
        ''')
        
        # Tabla de noticias
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS noticias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                contenido TEXT NOT NULL,
                importante BOOLEAN DEFAULT FALSE,
                fecha DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla de noticias vistas por usuario
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS noticias_vistas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER,
                noticia_id INTEGER,
                fecha_vista DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id),
                FOREIGN KEY (noticia_id) REFERENCES noticias (id),
                UNIQUE(usuario_id, noticia_id)
            )
        ''')
        
        # Tabla de notificaciones personalizadas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notificaciones_personalizadas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER,
                titulo TEXT NOT NULL,
                mensaje TEXT NOT NULL,
                tipo TEXT DEFAULT 'info',
                visto BOOLEAN DEFAULT FALSE,
                fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
            )
        ''')
        
        # Insertar configuración por defecto si no existe (todos en local)
        cursor.execute('SELECT COUNT(*) FROM configuracion_fuentes_pines')
        if cursor.fetchone()[0] == 0:
            configuracion_default = [(i, 'local', True) for i in range(1, 10)]
            cursor.executemany('''
                INSERT INTO configuracion_fuentes_pines (monto_id, fuente, activo)
                VALUES (?, ?, ?)
            ''', configuracion_default)
    
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
        
        # Insertar precios de Blood Striker por defecto si no existen
        cursor.execute('SELECT COUNT(*) FROM precios_bloodstriker')
        if cursor.fetchone()[0] == 0:
            precios_bloodstriker = [
                (1, '100+16 🪙', 0.82, '100+16 Monedas Blood Striker', True),
                (2, '300+52 🪙', 2.60, '300+52 Monedas Blood Striker', True),
                (3, '500+94 🪙', 4.30, '500+94 Monedas Blood Striker', True),
                (4, '1,000+210 🪙', 8.65, '1,000+210 Monedas Blood Striker', True),
                (5, '2,000+486 🪙', 17.30, '2,000+486 Monedas Blood Striker', True),
                (6, '5,000+1,380 🪙', 43.15, '5,000+1,380 Monedas Blood Striker', True),
                (7, 'Pase Elite 🎖️', 3.50, 'Pase Elite Blood Striker', True),
                (8, 'Pase Elite (Plus) 🎖️', 8.00, 'Pase Elite Plus Blood Striker', True),
                (9, 'Pase de Mejora 🔫', 1.85, 'Pase de Mejora Blood Striker', True),
                (10, 'Cofre Camuflaje Ultra 💼', 0.50, 'Cofre Camuflaje Ultra Blood Striker', True)
            ]
            cursor.executemany('''
                INSERT INTO precios_bloodstriker (id, nombre, precio, descripcion, activo)
                VALUES (?, ?, ?, ?, ?)
            ''', precios_bloodstriker)
        
        # Insertar precios de Free Fire Global por defecto si no existen
        cursor.execute('SELECT COUNT(*) FROM precios_freefire_global')
        if cursor.fetchone()[0] == 0:
            precios_freefire_global = [
                (1, '100+10 💎', 0.86, '100+10 Diamantes Free Fire', True),
                (2, '310+31 💎', 2.90, '310+31 Diamantes Free Fire', True),
                (3, '520+52 💎', 4.00, '520+52 Diamantes Free Fire', True),
                (4, '1.060+106 💎', 7.75, '1.060+106 Diamantes Free Fire', True),
                (5, '2.180+218 💎', 15.30, '2.180+218 Diamantes Free Fire', True),
                (6, '5.600+560 💎', 38.00, '5.600+560 Diamantes Free Fire', True)
            ]
            cursor.executemany('''
                INSERT INTO precios_freefire_global (id, nombre, precio, descripcion, activo)
                VALUES (?, ?, ?, ?, ?)
            ''', precios_freefire_global)
        
        # Tabla de precios de compra (costos) para gestión de rentabilidad
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS precios_compra (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                juego TEXT NOT NULL,
                paquete_id INTEGER NOT NULL,
                precio_compra REAL NOT NULL DEFAULT 0.0,
                fecha_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP,
                activo BOOLEAN DEFAULT TRUE,
                UNIQUE(juego, paquete_id)
            )
        ''')
        
        # Tabla de estadísticas de ventas semanales
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ventas_semanales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                juego TEXT NOT NULL,
                paquete_id INTEGER NOT NULL,
                paquete_nombre TEXT NOT NULL,
                precio_venta REAL NOT NULL,
                precio_compra REAL NOT NULL DEFAULT 0.0,
                ganancia_unitaria REAL NOT NULL DEFAULT 0.0,
                cantidad_vendida INTEGER NOT NULL DEFAULT 1,
                ganancia_total REAL NOT NULL DEFAULT 0.0,
                fecha_venta DATETIME DEFAULT CURRENT_TIMESTAMP,
                semana_year TEXT NOT NULL,
                CHECK (cantidad_vendida > 0)
            )
        ''')
        
        # Insertar precios de compra por defecto si no existen
        cursor.execute('SELECT COUNT(*) FROM precios_compra')
        if cursor.fetchone()[0] == 0:
            precios_compra_default = [
                # Free Fire LATAM
                ('freefire_latam', 1, 0.59),  # 110 💎 - costo $0.59, venta $0.66
                ('freefire_latam', 2, 2.00),  # 341 💎 - costo $2.00, venta $2.25
                ('freefire_latam', 3, 3.20),  # 572 💎 - costo $3.20, venta $3.66
                ('freefire_latam', 4, 6.50),  # 1.166 💎 - costo $6.50, venta $7.10
                ('freefire_latam', 5, 13.00), # 2.376 💎 - costo $13.00, venta $14.44
                ('freefire_latam', 6, 30.00), # 6.138 💎 - costo $30.00, venta $33.10
                ('freefire_latam', 7, 0.40),  # Tarjeta básica - costo $0.40, venta $0.50
                ('freefire_latam', 8, 1.30),  # Tarjeta semanal - costo $1.30, venta $1.55
                ('freefire_latam', 9, 6.50),  # Tarjeta mensual - costo $6.50, venta $7.10
                
                # Free Fire Global
                ('freefire_global', 1, 0.75), # 100+10 💎 - costo $0.75, venta $0.86
                ('freefire_global', 2, 2.50), # 310+31 💎 - costo $2.50, venta $2.90
                ('freefire_global', 3, 3.50), # 520+52 💎 - costo $3.50, venta $4.00
                ('freefire_global', 4, 7.00), # 1.060+106 💎 - costo $7.00, venta $7.75
                ('freefire_global', 5, 14.00), # 2.180+218 💎 - costo $14.00, venta $15.30
                ('freefire_global', 6, 35.00), # 5.600+560 💎 - costo $35.00, venta $38.00
                
                # Blood Striker
                ('bloodstriker', 1, 0.70),   # 100+16 🪙 - costo $0.70, venta $0.82
                ('bloodstriker', 2, 2.30),   # 300+52 🪙 - costo $2.30, venta $2.60
                ('bloodstriker', 3, 3.80),   # 500+94 🪙 - costo $3.80, venta $4.30
                ('bloodstriker', 4, 7.80),   # 1,000+210 🪙 - costo $7.80, venta $8.65
                ('bloodstriker', 5, 15.50),  # 2,000+486 🪙 - costo $15.50, venta $17.30
                ('bloodstriker', 6, 39.00),  # 5,000+1,380 🪙 - costo $39.00, venta $43.15
                ('bloodstriker', 7, 3.00),   # Pase Elite - costo $3.00, venta $3.50
                ('bloodstriker', 8, 7.20),   # Pase Elite Plus - costo $7.20, venta $8.00
                ('bloodstriker', 9, 1.60),   # Pase de Mejora - costo $1.60, venta $1.85
                ('bloodstriker', 10, 0.40),  # Cofre Camuflaje - costo $0.40, venta $0.50
            ]
            cursor.executemany('''
                INSERT INTO precios_compra (juego, paquete_id, precio_compra)
                VALUES (?, ?, ?)
            ''', precios_compra_default)
    
        # Crear índices optimizados para mejor rendimiento
        create_optimized_indexes(cursor)
        
        conn.commit()
        
    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        raise e
    finally:
        if conn:
            return_db_connection(conn)

def create_optimized_indexes(cursor):
    """Crea índices optimizados para consultas frecuentes"""
    indexes = [
        'CREATE INDEX IF NOT EXISTS idx_usuarios_correo ON usuarios(correo)',
        'CREATE INDEX IF NOT EXISTS idx_transacciones_usuario_fecha ON transacciones(usuario_id, fecha DESC)',
        'CREATE INDEX IF NOT EXISTS idx_transacciones_fecha ON transacciones(fecha DESC)',
        'CREATE INDEX IF NOT EXISTS idx_pines_monto_usado ON pines_freefire(monto_id, usado)',
        'CREATE INDEX IF NOT EXISTS idx_pines_global_monto_usado ON pines_freefire_global(monto_id, usado)',
        'CREATE INDEX IF NOT EXISTS idx_ventas_semanales_juego_semana ON ventas_semanales(juego, semana_year)',
        'CREATE INDEX IF NOT EXISTS idx_precios_compra_juego_paquete ON precios_compra(juego, paquete_id, activo)',
        'CREATE INDEX IF NOT EXISTS idx_bloodstriker_estado ON transacciones_bloodstriker(estado, fecha DESC)',
        'CREATE INDEX IF NOT EXISTS idx_creditos_usuario_visto ON creditos_billetera(usuario_id, visto)',
        'CREATE INDEX IF NOT EXISTS idx_noticias_fecha ON noticias(fecha DESC)'
    ]
    
    for index_sql in indexes:
        try:
            cursor.execute(index_sql)
        except Exception as e:
            print(f"Error creando índice: {e}")

# Cache en memoria para datos frecuentes
@lru_cache(maxsize=128)
def get_package_info_with_prices_cached():
    """Versión cacheada de información de paquetes Free Fire LATAM"""
    conn = get_db_connection_optimized()
    try:
        packages = conn.execute('''
            SELECT id, nombre, precio, descripcion 
            FROM precios_paquetes 
            WHERE activo = TRUE 
            ORDER BY id
        ''').fetchall()
        
        package_dict = {}
        for package in packages:
            package_dict[package['id']] = {
                'nombre': package['nombre'],
                'precio': package['precio'],
                'descripcion': package['descripcion']
            }
        return package_dict
    finally:
        return_db_connection(conn)

@lru_cache(maxsize=128)
def get_bloodstriker_prices_cached():
    """Versión cacheada de precios de Blood Striker"""
    conn = get_db_connection_optimized()
    try:
        packages = conn.execute('''
            SELECT id, nombre, precio, descripcion 
            FROM precios_bloodstriker 
            WHERE activo = TRUE 
            ORDER BY id
        ''').fetchall()
        
        package_dict = {}
        for package in packages:
            package_dict[package['id']] = {
                'nombre': package['nombre'],
                'precio': package['precio'],
                'descripcion': package['descripcion']
            }
        return package_dict
    finally:
        return_db_connection(conn)

@lru_cache(maxsize=128)
def get_freefire_global_prices_cached():
    """Versión cacheada de precios de Free Fire Global"""
    conn = get_db_connection_optimized()
    try:
        packages = conn.execute('''
            SELECT id, nombre, precio, descripcion 
            FROM precios_freefire_global 
            WHERE activo = TRUE 
            ORDER BY id
        ''').fetchall()
        
        package_dict = {}
        for package in packages:
            package_dict[package['id']] = {
                'nombre': package['nombre'],
                'precio': package['precio'],
                'descripcion': package['descripcion']
            }
        return package_dict
    finally:
        return_db_connection(conn)

def clear_price_cache():
    """Limpia el cache de precios cuando se actualizan"""
    get_package_info_with_prices_cached.cache_clear()
    get_bloodstriker_prices_cached.cache_clear()
    get_freefire_global_prices_cached.cache_clear()

@lru_cache(maxsize=1000)
def convert_to_venezuela_time_cached(utc_datetime_str):
    """Versión optimizada con cache de conversión de zona horaria"""
    try:
        utc_dt = datetime.strptime(utc_datetime_str, '%Y-%m-%d %H:%M:%S')
        utc_dt = pytz.utc.localize(utc_dt)
        venezuela_tz = pytz.timezone('America/Caracas')
        venezuela_dt = utc_dt.astimezone(venezuela_tz)
        return venezuela_dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return utc_datetime_str

# Funciones de stock optimizadas
def get_pin_stock_optimized():
    """Versión optimizada que usa una sola query en lugar de 9"""
    conn = get_db_connection_optimized()
    try:
        results = conn.execute('''
            SELECT monto_id, COUNT(*) as count 
            FROM pines_freefire 
            WHERE usado = FALSE 
            GROUP BY monto_id
        ''').fetchall()
        
        stock = {i: 0 for i in range(1, 10)}
        for result in results:
            stock[result['monto_id']] = result['count']
        return stock
    finally:
        return_db_connection(conn)

def get_pin_stock_freefire_global_optimized():
    """Versión optimizada para Free Fire Global"""
    conn = get_db_connection_optimized()
    try:
        results = conn.execute('''
            SELECT monto_id, COUNT(*) as count 
            FROM pines_freefire_global 
            WHERE usado = FALSE 
            GROUP BY monto_id
        ''').fetchall()
        
        stock = {i: 0 for i in range(1, 7)}
        for result in results:
            stock[result['monto_id']] = result['count']
        return stock
    finally:
        return_db_connection(conn)

def hash_password(password):
    """Hashea la contraseña usando Werkzeug (más seguro que SHA256)"""
    return generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)

def verify_password(password, hashed):
    """Verifica la contraseña hasheada (compatible con métodos antiguos y nuevos)"""
    # Intentar con Werkzeug (maneja pbkdf2, scrypt, etc.)
    if hashed.startswith(('pbkdf2:', 'scrypt:')):
        return check_password_hash(hashed, password)
    
    # Si no es un hash de Werkzeug, verificar con SHA256 (método anterior)
    sha256_hash = hashlib.sha256(password.encode()).hexdigest()
    return hashed == sha256_hash


def get_db_connection():
    """Obtiene una conexión a la base de datos"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def convert_to_venezuela_time(utc_datetime_str):
    """Convierte una fecha UTC a la zona horaria de Venezuela (UTC-4)"""
    try:
        # Parsear la fecha UTC desde la base de datos
        utc_dt = datetime.strptime(utc_datetime_str, '%Y-%m-%d %H:%M:%S')
        
        # Establecer como UTC
        utc_dt = pytz.utc.localize(utc_dt)
        
        # Convertir a zona horaria de Venezuela (UTC-4)
        venezuela_tz = pytz.timezone('America/Caracas')
        venezuela_dt = utc_dt.astimezone(venezuela_tz)
        
        # Retornar en formato legible
        return venezuela_dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        # Si hay error, retornar la fecha original
        return utc_datetime_str

def get_user_by_email(email):
    """Obtiene un usuario por su email"""
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM usuarios WHERE correo = ?', (email,)).fetchone()
    conn.close()
    return user

def create_user(nombre, apellido, telefono, correo, contraseña):
    """Crea un nuevo usuario en la base de datos"""
    conn = get_db_connection()
    hashed_password = hash_password(contraseña)
    try:
        cursor = conn.execute('''
            INSERT INTO usuarios (nombre, apellido, telefono, correo, contraseña, saldo)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (nombre, apellido, telefono, correo, hashed_password, 0.0))
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return user_id
    except sqlite3.IntegrityError:
        conn.close()
        return None

def get_user_transactions(user_id, is_admin=False, page=1, per_page=10):
    """Obtiene las transacciones de un usuario con información del paquete y paginación"""
    conn = get_db_connection()
    
    # Calcular offset para paginación
    offset = (page - 1) * per_page
    
    if is_admin:
        # Admin ve todas las transacciones de todos los usuarios
        transactions = conn.execute('''
            SELECT t.*, u.nombre, u.apellido
            FROM transacciones t
            JOIN usuarios u ON t.usuario_id = u.id
            ORDER BY t.fecha DESC
            LIMIT ? OFFSET ?
        ''', (per_page, offset)).fetchall()
        
        # Obtener total de transacciones para paginación
        total_count = conn.execute('''
            SELECT COUNT(*) FROM transacciones t
            JOIN usuarios u ON t.usuario_id = u.id
        ''').fetchone()[0]
    else:
        # Usuario normal ve solo sus transacciones
        if user_id:
            transactions = conn.execute('''
                SELECT t.*, u.nombre, u.apellido
                FROM transacciones t
                JOIN usuarios u ON t.usuario_id = u.id
                WHERE t.usuario_id = ? 
                ORDER BY t.fecha DESC
                LIMIT ? OFFSET ?
            ''', (user_id, per_page, offset)).fetchall()
            
            # Obtener total de transacciones del usuario para paginación
            total_count = conn.execute('''
                SELECT COUNT(*) FROM transacciones t
                JOIN usuarios u ON t.usuario_id = u.id
                WHERE t.usuario_id = ?
            ''', (user_id,)).fetchone()[0]
        else:
            transactions = []
            total_count = 0
    
    # Obtener precios dinámicos de la base de datos (Free Fire y Blood Striker)
    packages_info = get_package_info_with_prices()
    bloodstriker_packages_info = get_bloodstriker_prices()
    
    # Agregar información del paquete basado en el monto dinámico
    transactions_with_package = []
    for transaction in transactions:
        transaction_dict = dict(transaction)
        monto = abs(transaction['monto'])  # Usar valor absoluto para comparar
        
        # Buscar el paquete que coincida con el monto (con tolerancia para decimales)
        paquete_encontrado = False
        
        # Primero buscar en paquetes de Free Fire
        for package_id, package_info in packages_info.items():
            if abs(monto - package_info['precio']) < 0.01:  # Tolerancia de 1 centavo
                transaction_dict['paquete'] = package_info['nombre']
                paquete_encontrado = True
                break
        
        # Si no se encuentra en Free Fire, buscar en Blood Striker
        if not paquete_encontrado:
            for package_id, package_info in bloodstriker_packages_info.items():
                if abs(monto - package_info['precio']) < 0.01:  # Tolerancia de 1 centavo
                    transaction_dict['paquete'] = package_info['nombre']
                    paquete_encontrado = True
                    break
        
        # Si no se encuentra coincidencia exacta, usar el nombre por defecto
        if not paquete_encontrado:
            transaction_dict['paquete'] = f"Paquete ${monto:.2f}"
        
        # Convertir fecha a zona horaria de Venezuela
        transaction_dict['fecha'] = convert_to_venezuela_time(transaction_dict['fecha'])
        
        transactions_with_package.append(transaction_dict)
    
    conn.close()
    
    # Calcular información de paginación
    total_pages = (total_count + per_page - 1) // per_page  # Redondear hacia arriba
    has_prev = page > 1
    has_next = page < total_pages
    
    return {
        'transactions': transactions_with_package,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total_count,
            'total_pages': total_pages,
            'has_prev': has_prev,
            'has_next': has_next,
            'prev_num': page - 1 if has_prev else None,
            'next_num': page + 1 if has_next else None
        }
    }

def get_user_wallet_credits(user_id):
    """Obtiene los créditos de billetera de un usuario"""
    conn = get_db_connection()
    # Crear tabla si no existe
    conn.execute('''
        CREATE TABLE IF NOT EXISTS creditos_billetera (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            monto REAL DEFAULT 0.0,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
            visto BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')
    
    credits = conn.execute('''
        SELECT * FROM creditos_billetera 
        WHERE usuario_id = ? 
        ORDER BY fecha DESC
    ''', (user_id,)).fetchall()
    conn.close()
    return credits

def get_all_wallet_credits():
    """Obtiene todos los créditos de billetera del sistema para el admin"""
    conn = get_db_connection()
    # Crear tabla si no existe
    conn.execute('''
        CREATE TABLE IF NOT EXISTS creditos_billetera (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            monto REAL DEFAULT 0.0,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
            visto BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')
    
    # Agregar columna 'visto' si no existe (para compatibilidad con datos existentes)
    try:
        conn.execute('ALTER TABLE creditos_billetera ADD COLUMN visto BOOLEAN DEFAULT FALSE')
        conn.commit()
    except:
        pass  # La columna ya existe
    
    # Agregar columna 'saldo_anterior' si no existe (para compatibilidad con datos existentes)
    try:
        conn.execute('ALTER TABLE creditos_billetera ADD COLUMN saldo_anterior REAL DEFAULT 0.0')
        conn.commit()
    except:
        pass  # La columna ya existe
    
    try:
        credits = conn.execute('''
            SELECT cb.*, u.nombre, u.apellido, u.correo 
            FROM creditos_billetera cb
            JOIN usuarios u ON cb.usuario_id = u.id
            ORDER BY cb.fecha DESC
            LIMIT 100
        ''').fetchall()
    except Exception as e:
        print(f"Error al obtener créditos de billetera: {e}")
        credits = []
    
    conn.close()
    return credits

def get_wallet_credits_stats():
    """Obtiene estadísticas de créditos de billetera para el admin"""
    conn = get_db_connection()
    # Crear tabla si no existe
    conn.execute('''
        CREATE TABLE IF NOT EXISTS creditos_billetera (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            monto REAL DEFAULT 0.0,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
            visto BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')
    
    try:
        # Total de créditos agregados
        total_credits = conn.execute('''
            SELECT COALESCE(SUM(monto), 0) as total FROM creditos_billetera
        ''').fetchone()['total']
        
        # Créditos agregados hoy
        today_credits = conn.execute('''
            SELECT COALESCE(SUM(monto), 0) as today_total 
            FROM creditos_billetera 
            WHERE DATE(fecha) = DATE('now')
        ''').fetchone()['today_total']
        
        # Número de usuarios que han recibido créditos
        users_with_credits = conn.execute('''
            SELECT COUNT(DISTINCT usuario_id) as count FROM creditos_billetera
        ''').fetchone()['count']
        
        conn.close()
        return {
            'total_credits': total_credits,
            'today_credits': today_credits,
            'users_with_credits': users_with_credits
        }
    except Exception as e:
        print(f"Error al obtener estadísticas de créditos: {e}")
        conn.close()
        return {
            'total_credits': 0,
            'today_credits': 0,
            'users_with_credits': 0
        }

def get_unread_wallet_credits_count(user_id):
    """Obtiene si hay créditos de billetera no vistos (retorna 1 si hay, 0 si no hay)"""
    conn = get_db_connection()
    # Crear tabla si no existe
    conn.execute('''
        CREATE TABLE IF NOT EXISTS creditos_billetera (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            monto REAL DEFAULT 0.0,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
            visto BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')
    
    # Agregar columna 'visto' si no existe (para compatibilidad con datos existentes)
    try:
        conn.execute('ALTER TABLE creditos_billetera ADD COLUMN visto BOOLEAN DEFAULT FALSE')
        conn.commit()
    except:
        pass  # La columna ya existe
    
    count = conn.execute('''
        SELECT COUNT(*) FROM creditos_billetera 
        WHERE usuario_id = ? AND (visto = FALSE OR visto IS NULL)
    ''', (user_id,)).fetchone()[0]
    conn.close()
    
    # Retornar 1 si hay créditos no vistos, 0 si no hay
    return 1 if count > 0 else 0

def mark_wallet_credits_as_read(user_id):
    """Marca todos los créditos de billetera como vistos"""
    conn = get_db_connection()
    # Crear tabla si no existe
    conn.execute('''
        CREATE TABLE IF NOT EXISTS creditos_billetera (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            monto REAL DEFAULT 0.0,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
            visto BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')
    
    # Agregar columna 'visto' si no existe
    try:
        conn.execute('ALTER TABLE creditos_billetera ADD COLUMN visto BOOLEAN DEFAULT FALSE')
        conn.commit()
    except:
        pass  # La columna ya existe
    
    conn.execute('''
        UPDATE creditos_billetera 
        SET visto = TRUE 
        WHERE usuario_id = ?
    ''', (user_id,))
    conn.commit()
    conn.close()

# Funciones para sistema de noticias
def create_news_table():
    """Crea la tabla de noticias si no existe"""
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS noticias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            contenido TEXT NOT NULL,
            importante BOOLEAN DEFAULT FALSE,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def create_news_views_table():
    """Crea la tabla para rastrear noticias vistas por usuario"""
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS noticias_vistas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            noticia_id INTEGER,
            fecha_vista DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id),
            FOREIGN KEY (noticia_id) REFERENCES noticias (id),
            UNIQUE(usuario_id, noticia_id)
        )
    ''')
    conn.commit()
    conn.close()

def create_news(titulo, contenido, importante=False):
    """Crea una nueva noticia"""
    create_news_table()
    conn = get_db_connection()
    cursor = conn.execute('''
        INSERT INTO noticias (titulo, contenido, importante)
        VALUES (?, ?, ?)
    ''', (titulo, contenido, importante))
    news_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return news_id

def get_all_news():
    """Obtiene todas las noticias ordenadas por fecha (más recientes primero)"""
    create_news_table()
    conn = get_db_connection()
    news = conn.execute('''
        SELECT * FROM noticias 
        ORDER BY fecha DESC
    ''').fetchall()
    conn.close()
    return news

def get_user_news(user_id):
    """Obtiene las noticias para un usuario específico"""
    create_news_table()
    create_news_views_table()
    conn = get_db_connection()
    news = conn.execute('''
        SELECT * FROM noticias 
        ORDER BY fecha DESC
        LIMIT 20
    ''').fetchall()
    conn.close()
    return news

def get_unread_news_count(user_id):
    """Obtiene el número de noticias no leídas por un usuario"""
    create_news_table()
    create_news_views_table()
    conn = get_db_connection()
    
    # Contar noticias que el usuario no ha visto
    count = conn.execute('''
        SELECT COUNT(*) FROM noticias n
        WHERE n.id NOT IN (
            SELECT nv.noticia_id FROM noticias_vistas nv 
            WHERE nv.usuario_id = ?
        )
    ''', (user_id,)).fetchone()[0]
    conn.close()
    
    # Retornar 1 si hay noticias no leídas, 0 si no hay
    return 1 if count > 0 else 0

def mark_news_as_read(user_id):
    """Marca todas las noticias como leídas para un usuario"""
    create_news_table()
    create_news_views_table()
    conn = get_db_connection()
    
    # Obtener todas las noticias que el usuario no ha visto
    unread_news = conn.execute('''
        SELECT id FROM noticias 
        WHERE id NOT IN (
            SELECT noticia_id FROM noticias_vistas 
            WHERE usuario_id = ?
        )
    ''', (user_id,)).fetchall()
    
    # Marcar como vistas
    for news in unread_news:
        conn.execute('''
            INSERT OR IGNORE INTO noticias_vistas (usuario_id, noticia_id)
            VALUES (?, ?)
        ''', (user_id, news['id']))
    
    conn.commit()
    conn.close()

def delete_news(news_id):
    """Elimina una noticia y sus registros de vistas"""
    conn = get_db_connection()
    # Eliminar registros de vistas
    conn.execute('DELETE FROM noticias_vistas WHERE noticia_id = ?', (news_id,))
    # Eliminar noticia
    conn.execute('DELETE FROM noticias WHERE id = ?', (news_id,))
    conn.commit()
    conn.close()

# Funciones para notificaciones personalizadas
def create_personal_notification(user_id, titulo, mensaje, tipo='success'):
    """Crea una notificación personalizada para un usuario específico"""
    conn = get_db_connection()
    # Crear tabla si no existe
    conn.execute('''
        CREATE TABLE IF NOT EXISTS notificaciones_personalizadas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            titulo TEXT NOT NULL,
            mensaje TEXT NOT NULL,
            tipo TEXT DEFAULT 'info',
            visto BOOLEAN DEFAULT FALSE,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')
    
    cursor = conn.execute('''
        INSERT INTO notificaciones_personalizadas (usuario_id, titulo, mensaje, tipo)
        VALUES (?, ?, ?, ?)
    ''', (user_id, titulo, mensaje, tipo))
    
    notification_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return notification_id

def get_user_personal_notifications(user_id):
    """Obtiene las notificaciones personalizadas de un usuario"""
    conn = get_db_connection()
    # Crear tabla si no existe
    conn.execute('''
        CREATE TABLE IF NOT EXISTS notificaciones_personalizadas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            titulo TEXT NOT NULL,
            mensaje TEXT NOT NULL,
            tipo TEXT DEFAULT 'info',
            visto BOOLEAN DEFAULT FALSE,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')
    
    notifications = conn.execute('''
        SELECT * FROM notificaciones_personalizadas 
        WHERE usuario_id = ? AND visto = FALSE
        ORDER BY fecha DESC
        LIMIT 10
    ''', (user_id,)).fetchall()
    conn.close()
    return notifications

def get_unread_personal_notifications_count(user_id):
    """Obtiene el número de notificaciones personalizadas no leídas"""
    conn = get_db_connection()
    # Crear tabla si no existe
    conn.execute('''
        CREATE TABLE IF NOT EXISTS notificaciones_personalizadas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            titulo TEXT NOT NULL,
            mensaje TEXT NOT NULL,
            tipo TEXT DEFAULT 'info',
            visto BOOLEAN DEFAULT FALSE,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')
    
    count = conn.execute('''
        SELECT COUNT(*) FROM notificaciones_personalizadas 
        WHERE usuario_id = ? AND visto = FALSE
    ''', (user_id,)).fetchone()[0]
    conn.close()
    
    return 1 if count > 0 else 0

def mark_personal_notifications_as_read(user_id):
    """Marca todas las notificaciones personalizadas como leídas y las elimina"""
    conn = get_db_connection()
    # Crear tabla si no existe
    conn.execute('''
        CREATE TABLE IF NOT EXISTS notificaciones_personalizadas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            titulo TEXT NOT NULL,
            mensaje TEXT NOT NULL,
            tipo TEXT DEFAULT 'info',
            visto BOOLEAN DEFAULT FALSE,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')
    
    # Eliminar todas las notificaciones del usuario (para que desaparezcan después de verlas)
    conn.execute('''
        DELETE FROM notificaciones_personalizadas 
        WHERE usuario_id = ?
    ''', (user_id,))
    conn.commit()
    conn.close()


# Función de debug para mostrar información de la base de datos
def debug_database_info():
    """Muestra información de debug sobre la base de datos"""
    print("=" * 50)
    print("🔍 DEBUG: INFORMACIÓN DE BASE DE DATOS")
    print("=" * 50)
    
    # Variables de entorno
    print(f"RENDER: {os.environ.get('RENDER', 'No configurado')}")
    print(f"DATABASE_PATH: {os.environ.get('DATABASE_PATH', 'No configurado')}")
    print(f"Ruta de BD configurada: {DATABASE}")
    print(f"Ruta absoluta: {os.path.abspath(DATABASE)}")
    print(f"Directorio actual: {os.getcwd()}")
    
    # Verificar si existe el archivo
    if os.path.exists(DATABASE):
        file_size = os.path.getsize(DATABASE)
        print(f"✅ Base de datos existe: {file_size} bytes")
        
        # Verificar tablas
        try:
            conn = get_db_connection_optimized()
            cursor = conn.cursor()
            
            # Listar tablas
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            print(f"📊 Tablas encontradas ({len(tables)}):")
            for table in tables:
                # Contar registros en cada tabla
                try:
                    count = cursor.execute(f"SELECT COUNT(*) FROM {table[0]}").fetchone()[0]
                    print(f"   - {table[0]}: {count} registros")
                except:
                    print(f"   - {table[0]}: Error al contar")
            
            return_db_connection(conn)
            
        except Exception as e:
            print(f"❌ Error conectando a BD: {e}")
    else:
        print(f"❌ Base de datos NO existe en: {DATABASE}")
        
        # Verificar directorio padre
        db_dir = os.path.dirname(DATABASE)
        if db_dir:
            print(f"📁 Directorio padre: {db_dir}")
            print(f"   Existe: {os.path.exists(db_dir)}")
            if os.path.exists(db_dir):
                try:
                    files = os.listdir(db_dir)
                    print(f"   Archivos: {files}")
                except:
                    print("   Error listando archivos")
    
    print("=" * 50)

# Inicializar la base de datos al iniciar la aplicación
debug_database_info()
init_db()

@app.route('/')
def index():
    if 'usuario' not in session:
        return redirect('/auth')
    
    # Ejecutar limpieza automática de transacciones antiguas (solo en la primera carga)
    if request.args.get('page', 1, type=int) == 1:
        try:
            clean_old_transactions()
        except Exception as e:
            print(f"Error en limpieza automática de transacciones: {e}")
    
    # Obtener parámetros de paginación
    page = request.args.get('page', 1, type=int)
    per_page = 30  # Transacciones por página
    
    user_id = session.get('id', '00000')
    transactions_data = {}
    is_admin = session.get('is_admin', False)
    
    if is_admin:
        # Admin ve todas las transacciones de todos los usuarios con paginación
        transactions_data = get_user_transactions(None, is_admin=True, page=page, per_page=per_page)
        
        # Para admin, también agregar transacciones pendientes de Blood Striker solo en la primera página
        if page == 1:
            bloodstriker_transactions = get_pending_bloodstriker_transactions()
            # Combinar transacciones normales con las de Blood Striker
            all_transactions = list(transactions_data['transactions']) + list(bloodstriker_transactions)
            # Ordenar por fecha
            all_transactions.sort(key=lambda x: x.get('fecha', ''), reverse=True)
            # Tomar solo las primeras per_page transacciones
            transactions_data['transactions'] = all_transactions[:per_page]
        
        balance = 0  # Admin no tiene saldo
    else:
        # Usuario normal ve solo sus transacciones
        if 'user_db_id' in session:
            # Actualizar saldo desde la base de datos SIEMPRE
            conn = get_db_connection()
            user = conn.execute('SELECT saldo FROM usuarios WHERE id = ?', (session['user_db_id'],)).fetchone()
            if user:
                session['saldo'] = user['saldo']
                balance = user['saldo']
            else:
                balance = 0
            conn.close()
            
            # Obtener transacciones normales del usuario con paginación
            transactions_data = get_user_transactions(session['user_db_id'], is_admin=False, page=page, per_page=per_page)
            
            # Para usuario normal, también agregar transacciones pendientes de Blood Striker solo en la primera página
            if page == 1:
                user_bloodstriker_transactions = get_user_pending_bloodstriker_transactions(session['user_db_id'])
                # Combinar transacciones normales con las de Blood Striker del usuario
                all_user_transactions = list(transactions_data['transactions']) + list(user_bloodstriker_transactions)
                # Ordenar por fecha
                all_user_transactions.sort(key=lambda x: x.get('fecha', ''), reverse=True)
                # Tomar solo las primeras per_page transacciones
                transactions_data['transactions'] = all_user_transactions[:per_page]
        else:
            balance = 0
            transactions_data = {'transactions': [], 'pagination': {'page': 1, 'total_pages': 0, 'has_prev': False, 'has_next': False}}
    
    # Obtener contador de notificaciones de cartera para usuarios normales
    wallet_notification_count = 0
    if not is_admin and 'user_db_id' in session:
        wallet_notification_count = get_unread_wallet_credits_count(session['user_db_id'])
    
    # Obtener contador de notificaciones de noticias
    news_notification_count = 0
    personal_notification_count = 0
    if 'user_db_id' in session:
        news_notification_count = get_unread_news_count(session['user_db_id'])
        # Obtener contador de notificaciones personalizadas (solo para usuarios normales)
        if not is_admin:
            personal_notification_count = get_unread_personal_notifications_count(session['user_db_id'])
    
    # Combinar notificaciones de noticias y personalizadas
    total_notification_count = news_notification_count + personal_notification_count
    
    return render_template('index.html', 
                         user_id=user_id, 
                         balance=balance, 
                         transactions=transactions_data['transactions'],
                         pagination=transactions_data['pagination'],
                         is_admin=is_admin,
                         wallet_notification_count=wallet_notification_count,
                         news_notification_count=news_notification_count,
                         personal_notification_count=personal_notification_count,
                         total_notification_count=total_notification_count)

@app.route('/auth')
def auth():
    return render_template('auth.html')

@app.route('/login', methods=['POST'])
def login():
    correo = request.form['correo']
    contraseña = request.form['contraseña']
    
    if not correo or not contraseña:
        flash('Por favor, complete todos los campos', 'error')
        return redirect('/auth')
    
    # Verificar credenciales de administrador (desde variables de entorno)
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@inefable.com')
    admin_password = os.environ.get('ADMIN_PASSWORD', 'InefableAdmin2024!')
    
    if correo == admin_email and contraseña == admin_password:
        session.permanent = True  # Activar duración de sesión de 30 minutos
        session['usuario'] = admin_email
        session['nombre'] = 'Administrador'
        session['apellido'] = 'Sistema'
        session['id'] = 'ADMIN'
        session['user_db_id'] = 0
        session['saldo'] = 0
        session['is_admin'] = True
        return redirect('/')
    
    # Buscar usuario en la base de datos
    user = get_user_by_email(correo)
    
    if user and verify_password(contraseña, user['contraseña']):
        # Migrar contraseña antigua a nuevo formato si es necesario
        if not user['contraseña'].startswith('pbkdf2:'):
            # Actualizar contraseña al nuevo formato seguro
            new_hashed_password = hash_password(contraseña)
            conn = get_db_connection()
            conn.execute('UPDATE usuarios SET contraseña = ? WHERE id = ?', 
                        (new_hashed_password, user['id']))
            conn.commit()
            conn.close()
            print(f"Contraseña migrada para usuario: {user['correo']}")
        
        # Login exitoso
        session.permanent = True  # Activar duración de sesión de 30 minutos
        session['usuario'] = user['correo']
        session['nombre'] = user['nombre']
        session['apellido'] = user['apellido']
        session['id'] = str(user['id']).zfill(5)
        session['user_db_id'] = user['id']
        session['saldo'] = user['saldo']
        session['is_admin'] = False
        return redirect('/')
    else:
        flash('Credenciales incorrectas', 'error')
        return redirect('/auth')

@app.route('/register', methods=['POST'])
def register():
    nombre = request.form.get('nombre')
    apellido = request.form.get('apellido')
    telefono = request.form.get('telefono')
    correo = request.form.get('correo')
    contraseña = request.form.get('contraseña')
    
    # Validar que todos los campos estén completos
    if not all([nombre, apellido, telefono, correo, contraseña]):
        flash('Por favor, complete todos los campos', 'error')
        return redirect('/auth')
    
    # Verificar si el usuario ya existe
    if get_user_by_email(correo):
        flash('El correo electrónico ya está registrado', 'error')
        return redirect('/auth')
    
    # Crear nuevo usuario
    user_id = create_user(nombre, apellido, telefono, correo, contraseña)
    
    if user_id:
        # Registro exitoso, iniciar sesión automáticamente
        session.permanent = True  # Activar duración de sesión de 30 minutos
        session['usuario'] = correo
        session['nombre'] = nombre
        session['apellido'] = apellido
        session['id'] = str(user_id).zfill(5)
        session['user_db_id'] = user_id
        session['saldo'] = 0.0  # Saldo inicial
        flash('Registro exitoso. ¡Bienvenido!', 'success')
        return redirect('/')
    else:
        flash('Error al crear la cuenta. Intente nuevamente.', 'error')
        return redirect('/auth')


# Funciones de administrador
def get_all_users():
    """Obtiene todos los usuarios registrados"""
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM usuarios ORDER BY fecha_registro DESC').fetchall()
    conn.close()
    return users

def update_user_balance(user_id, new_balance):
    """Actualiza el saldo de un usuario"""
    conn = get_db_connection()
    conn.execute('UPDATE usuarios SET saldo = ? WHERE id = ?', (new_balance, user_id))
    conn.commit()
    conn.close()

def delete_user(user_id):
    """Elimina un usuario y todos sus datos relacionados"""
    conn = get_db_connection()
    # Eliminar transacciones del usuario
    conn.execute('DELETE FROM transacciones WHERE usuario_id = ?', (user_id,))
    # Eliminar créditos de billetera del usuario
    conn.execute('DELETE FROM creditos_billetera WHERE usuario_id = ?', (user_id,))
    # Eliminar usuario
    conn.execute('DELETE FROM usuarios WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()

def add_credit_to_user(user_id, amount):
    """Añade crédito al saldo de un usuario y registra en billetera"""
    conn = get_db_connection()
    
    # Crear tabla de créditos de billetera si no existe
    conn.execute('''
        CREATE TABLE IF NOT EXISTS creditos_billetera (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            monto REAL DEFAULT 0.0,
            saldo_anterior REAL DEFAULT 0.0,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')
    
    # Agregar columna 'saldo_anterior' si no existe (para compatibilidad con datos existentes)
    try:
        conn.execute('ALTER TABLE creditos_billetera ADD COLUMN saldo_anterior REAL DEFAULT 0.0')
        conn.commit()
    except:
        pass  # La columna ya existe
    
    # Obtener saldo actual del usuario antes de agregar el crédito
    user_data = conn.execute('SELECT saldo FROM usuarios WHERE id = ?', (user_id,)).fetchone()
    saldo_anterior = user_data['saldo'] if user_data else 0.0
    
    # Actualizar saldo del usuario
    conn.execute('UPDATE usuarios SET saldo = saldo + ? WHERE id = ?', (amount, user_id))
    
    # Registrar en créditos de billetera (monto, fecha y saldo anterior)
    conn.execute('''
        INSERT INTO creditos_billetera (usuario_id, monto, saldo_anterior)
        VALUES (?, ?, ?)
    ''', (user_id, amount, saldo_anterior))
    
    # Limitar créditos de billetera a 10 por usuario - eliminar los más antiguos si hay más de 10
    conn.execute('''
        DELETE FROM creditos_billetera 
        WHERE usuario_id = ? AND id NOT IN (
            SELECT id FROM creditos_billetera 
            WHERE usuario_id = ? 
            ORDER BY fecha DESC 
            LIMIT 10
        )
    ''', (user_id, user_id))
    
    conn.commit()
    conn.close()

# Funciones para pines de Free Fire
def add_pin_freefire(monto_id, pin_codigo):
    """Añade un pin de Free Fire al stock"""
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO pines_freefire (monto_id, pin_codigo)
        VALUES (?, ?)
    ''', (monto_id, pin_codigo))
    conn.commit()
    conn.close()

def add_pins_batch(monto_id, pins_list):
    """Añade múltiples pines de Free Fire al stock en lote"""
    conn = get_db_connection()
    try:
        for pin_codigo in pins_list:
            pin_codigo = pin_codigo.strip()
            if pin_codigo:  # Solo agregar si el pin no está vacío
                conn.execute('''
                    INSERT INTO pines_freefire (monto_id, pin_codigo)
                    VALUES (?, ?)
                ''', (monto_id, pin_codigo))
        conn.commit()
        return len([p for p in pins_list if p.strip()])  # Retornar cantidad agregada
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_pin_stock():
    """Obtiene el stock de pines por monto_id"""
    conn = get_db_connection()
    stock = {}
    for i in range(1, 10):  # monto_id del 1 al 9
        count = conn.execute('''
            SELECT COUNT(*) FROM pines_freefire 
            WHERE monto_id = ? AND usado = FALSE
        ''', (i,)).fetchone()[0]
        stock[i] = count
    conn.close()
    return stock

def get_available_pin(monto_id):
    """Obtiene un pin disponible para el monto especificado"""
    conn = get_db_connection()
    pin = conn.execute('''
        SELECT * FROM pines_freefire 
        WHERE monto_id = ? AND usado = FALSE 
        LIMIT 1
    ''', (monto_id,)).fetchone()
    conn.close()
    return pin


def get_all_pins():
    """Obtiene todos los pines para el admin"""
    conn = get_db_connection()
    pins = conn.execute('''
        SELECT p.*, u.nombre, u.apellido 
        FROM pines_freefire p
        LEFT JOIN usuarios u ON p.usuario_id = u.id
        ORDER BY p.fecha_agregado DESC
    ''').fetchall()
    conn.close()
    return pins

def remove_duplicate_pins():
    """Elimina pines duplicados de la base de datos, manteniendo el más reciente de cada código"""
    conn = get_db_connection()
    try:
        # Encontrar pines duplicados y eliminar los más antiguos
        duplicates_removed = conn.execute('''
            DELETE FROM pines_freefire 
            WHERE id NOT IN (
                SELECT MIN(id) 
                FROM pines_freefire 
                GROUP BY pin_codigo, monto_id
            )
        ''').rowcount
        
        conn.commit()
        return duplicates_removed
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_duplicate_pins_count():
    """Obtiene el número de pines duplicados en la base de datos"""
    conn = get_db_connection()
    try:
        # Contar pines duplicados
        result = conn.execute('''
            SELECT COUNT(*) - COUNT(DISTINCT pin_codigo || '-' || monto_id) as duplicates
            FROM pines_freefire
            WHERE usado = FALSE
        ''').fetchone()
        
        return result[0] if result else 0
    finally:
        conn.close()

# Funciones para gestión de precios
def get_all_prices():
    """Obtiene todos los precios de paquetes"""
    conn = get_db_connection()
    prices = conn.execute('''
        SELECT * FROM precios_paquetes 
        ORDER BY id
    ''').fetchall()
    conn.close()
    return prices

def get_price_by_id(monto_id):
    """Obtiene el precio de un paquete específico"""
    conn = get_db_connection()
    price = conn.execute('''
        SELECT precio FROM precios_paquetes 
        WHERE id = ? AND activo = TRUE
    ''', (monto_id,)).fetchone()
    conn.close()
    return price['precio'] if price else 0

def update_package_price(package_id, new_price):
    """Actualiza el precio de un paquete"""
    conn = get_db_connection_optimized()
    try:
        conn.execute('''
            UPDATE precios_paquetes 
            SET precio = ?, fecha_actualizacion = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (new_price, package_id))
        conn.commit()
        # Limpiar cache después de actualizar precios
        clear_price_cache()
    finally:
        return_db_connection(conn)

def update_package_name(package_id, new_name):
    """Actualiza el nombre de un paquete"""
    conn = get_db_connection_optimized()
    try:
        conn.execute('''
            UPDATE precios_paquetes 
            SET nombre = ?, fecha_actualizacion = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (new_name, package_id))
        conn.commit()
        # Limpiar cache después de actualizar nombres
        clear_price_cache()
    finally:
        return_db_connection(conn)

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

# Funciones para Blood Striker
def get_bloodstriker_prices():
    """Obtiene información de paquetes de Blood Striker con precios dinámicos"""
    conn = get_db_connection()
    packages = conn.execute('''
        SELECT id, nombre, precio, descripcion 
        FROM precios_bloodstriker 
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

def get_bloodstriker_price_by_id(package_id):
    """Obtiene el precio de un paquete específico de Blood Striker"""
    conn = get_db_connection()
    price = conn.execute('''
        SELECT precio FROM precios_bloodstriker 
        WHERE id = ? AND activo = TRUE
    ''', (package_id,)).fetchone()
    conn.close()
    return price['precio'] if price else 0

def create_bloodstriker_transaction(user_id, player_id, package_id, precio):
    """Crea una transacción pendiente de Blood Striker"""
    import random
    import string
    
    # Generar datos de la transacción
    numero_control = ''.join(random.choices(string.digits, k=10))
    transaccion_id = 'BS-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    conn = get_db_connection()
    try:
        # Insertar transacción pendiente
        cursor = conn.execute('''
            INSERT INTO transacciones_bloodstriker 
            (usuario_id, player_id, paquete_id, numero_control, transaccion_id, monto, estado)
            VALUES (?, ?, ?, ?, ?, ?, 'pendiente')
        ''', (user_id, player_id, package_id, numero_control, transaccion_id, -precio))
        
        transaction_id = cursor.lastrowid
        conn.commit()
        return {
            'id': transaction_id,
            'numero_control': numero_control,
            'transaccion_id': transaccion_id
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_pending_bloodstriker_transactions():
    """Obtiene todas las transacciones pendientes de Blood Striker para el admin"""
    conn = get_db_connection()
    transactions = conn.execute('''
        SELECT bs.*, u.nombre, u.apellido, u.correo, p.nombre as paquete_nombre
        FROM transacciones_bloodstriker bs
        JOIN usuarios u ON bs.usuario_id = u.id
        JOIN precios_bloodstriker p ON bs.paquete_id = p.id
        WHERE bs.estado = 'pendiente'
        ORDER BY bs.fecha DESC
    ''').fetchall()
    
    # Formatear las transacciones de Blood Striker para que sean compatibles con el template
    formatted_transactions = []
    for transaction in transactions:
        formatted_transaction = {
            'id': transaction['id'],
            'usuario_id': transaction['usuario_id'],
            'numero_control': transaction['numero_control'],
            'transaccion_id': transaction['transaccion_id'],
            'monto': transaction['monto'],
            'fecha': transaction['fecha'],
            'nombre': transaction['nombre'],
            'apellido': transaction['apellido'],
            'paquete': transaction['paquete_nombre'],
            'pin': f"ID: {transaction['player_id']}",  # Mostrar Player ID en lugar de PIN
            'estado': transaction['estado'],
            'is_bloodstriker': True  # Marcar como transacción de Blood Striker
        }
        formatted_transactions.append(formatted_transaction)
    
    conn.close()
    return formatted_transactions

def get_user_pending_bloodstriker_transactions(user_id):
    """Obtiene las transacciones pendientes de Blood Striker de un usuario específico"""
    conn = get_db_connection()
    transactions = conn.execute('''
        SELECT bs.*, u.nombre, u.apellido, p.nombre as paquete_nombre
        FROM transacciones_bloodstriker bs
        JOIN usuarios u ON bs.usuario_id = u.id
        JOIN precios_bloodstriker p ON bs.paquete_id = p.id
        WHERE bs.usuario_id = ? AND bs.estado = 'pendiente'
        ORDER BY bs.fecha DESC
    ''', (user_id,)).fetchall()
    
    # Formatear las transacciones de Blood Striker para que sean compatibles con el template
    formatted_transactions = []
    for transaction in transactions:
        formatted_transaction = {
            'id': transaction['id'],
            'usuario_id': transaction['usuario_id'],
            'numero_control': transaction['numero_control'],
            'transaccion_id': transaction['transaccion_id'],
            'monto': transaction['monto'],
            'fecha': convert_to_venezuela_time(transaction['fecha']),  # Convertir a zona horaria de Venezuela
            'nombre': transaction['nombre'],
            'apellido': transaction['apellido'],
            'paquete': transaction['paquete_nombre'],
            'pin': f"ID: {transaction['player_id']}",  # Mostrar Player ID del usuario
            'estado': transaction['estado'],
            'is_bloodstriker': True  # Marcar como transacción de Blood Striker
        }
        formatted_transactions.append(formatted_transaction)
    
    conn.close()
    return formatted_transactions

def update_bloodstriker_transaction_status(transaction_id, new_status, admin_id, notas=None):
    """Actualiza el estado de una transacción de Blood Striker"""
    conn = get_db_connection()
    conn.execute('''
        UPDATE transacciones_bloodstriker 
        SET estado = ?, admin_id = ?, notas = ?, fecha_procesado = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (new_status, admin_id, notas, transaction_id))
    conn.commit()
    conn.close()

def update_bloodstriker_price(package_id, new_price):
    """Actualiza el precio de un paquete de Blood Striker"""
    conn = get_db_connection_optimized()
    try:
        conn.execute('''
            UPDATE precios_bloodstriker 
            SET precio = ?, fecha_actualizacion = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (new_price, package_id))
        conn.commit()
        # Limpiar cache después de actualizar precios
        clear_price_cache()
    finally:
        return_db_connection(conn)

def update_bloodstriker_name(package_id, new_name):
    """Actualiza el nombre de un paquete de Blood Striker"""
    conn = get_db_connection_optimized()
    try:
        conn.execute('''
            UPDATE precios_bloodstriker 
            SET nombre = ?, fecha_actualizacion = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (new_name, package_id))
        conn.commit()
        # Limpiar cache después de actualizar nombres
        clear_price_cache()
    finally:
        return_db_connection(conn)

def get_all_bloodstriker_prices():
    """Obtiene todos los precios de paquetes de Blood Striker"""
    conn = get_db_connection()
    prices = conn.execute('''
        SELECT * FROM precios_bloodstriker 
        ORDER BY id
    ''').fetchall()
    conn.close()
    return prices

# Funciones para configuración de fuentes de pines
def get_pin_source_config():
    """Obtiene la configuración de fuentes de pines por monto"""
    conn = get_db_connection()
    config = {}
    for i in range(1, 10):
        result = conn.execute('''
            SELECT fuente FROM configuracion_fuentes_pines 
            WHERE monto_id = ? AND activo = TRUE
        ''', (i,)).fetchone()
        config[i] = result['fuente'] if result else 'local'
    conn.close()
    return config

def update_pin_source_config(monto_id, fuente):
    """Actualiza la configuración de fuente para un monto específico"""
    conn = get_db_connection()
    conn.execute('''
        INSERT OR REPLACE INTO configuracion_fuentes_pines (monto_id, fuente, activo, fecha_actualizacion)
        VALUES (?, ?, TRUE, CURRENT_TIMESTAMP)
    ''', (monto_id, fuente))
    conn.commit()
    conn.close()

# Funciones de notificación por correo
def send_email_async(app, msg):
    """Envía correo de forma asíncrona"""
    with app.app_context():
        try:
            mail.send(msg)
            print("Correo de notificación enviado exitosamente")
        except Exception as e:
            print(f"Error al enviar correo: {str(e)}")

def send_bloodstriker_notification(transaction_data):
    """Envía notificación por correo cuando hay una nueva transacción de Blood Striker"""
    # Verificar si las credenciales de correo están configuradas
    if not app.config['MAIL_USERNAME'] or not app.config['MAIL_PASSWORD']:
        print("Credenciales de correo no configuradas. Notificación omitida.")
        return
    
    try:
        # Obtener correo del administrador
        admin_email = os.environ.get('ADMIN_EMAIL', 'admin@inefable.com')
        
        # Crear mensaje
        msg = Message(
            subject='🎯 Nueva Transacción Blood Striker Pendiente',
            recipients=[admin_email],
            sender=app.config['MAIL_DEFAULT_SENDER']
        )
        
        # Contenido del correo
        msg.html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #667eea; text-align: center;">🎯 Nueva Transacción Blood Striker</h2>
                
                <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="color: #333; margin-top: 0;">Detalles de la Transacción:</h3>
                    
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px 0; font-weight: bold;">Usuario:</td>
                            <td style="padding: 8px 0;">{transaction_data['nombre']} {transaction_data['apellido']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; font-weight: bold;">Correo:</td>
                            <td style="padding: 8px 0;">{transaction_data['correo']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; font-weight: bold;">Player ID:</td>
                            <td style="padding: 8px 0; font-family: monospace; background: #e9ecef; padding: 4px 8px; border-radius: 4px;">{transaction_data['player_id']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; font-weight: bold;">Paquete:</td>
                            <td style="padding: 8px 0;">{transaction_data['paquete_nombre']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; font-weight: bold;">Monto:</td>
                            <td style="padding: 8px 0; color: #dc3545; font-weight: bold;">${transaction_data['precio']:.2f}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; font-weight: bold;">Número de Control:</td>
                            <td style="padding: 8px 0; font-family: monospace;">{transaction_data['numero_control']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; font-weight: bold;">ID de Transacción:</td>
                            <td style="padding: 8px 0; font-family: monospace;">{transaction_data['transaccion_id']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; font-weight: bold;">Fecha:</td>
                            <td style="padding: 8px 0;">{transaction_data['fecha']}</td>
                        </tr>
                    </table>
                </div>
                
                <div style="background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 6px; margin: 20px 0;">
                    <p style="margin: 0; color: #856404;">
                        <strong>⏳ Acción Requerida:</strong> Esta transacción está pendiente de aprobación. 
                        Ingresa al panel de administración para aprobar o rechazar la solicitud.
                    </p>
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <p style="color: #6c757d; font-size: 14px;">
                        Este es un correo automático del sistema de notificaciones.<br>
                        No responder a este correo.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Enviar correo de forma asíncrona
        thread = threading.Thread(target=send_email_async, args=(app, msg))
        thread.daemon = True
        thread.start()
        
    except Exception as e:
        print(f"Error al preparar notificación por correo: {str(e)}")

# Rutas de administrador
@app.route('/admin')
def admin_panel():
    if not session.get('is_admin'):
        flash('Acceso denegado. Solo administradores.', 'error')
        return redirect('/auth')
    
    users = get_all_users()
    pin_stock = get_pin_stock_optimized()
    pin_stock_freefire_global = get_pin_stock_freefire_global_optimized()
    prices = get_all_prices()
    freefire_global_prices = get_all_freefire_global_prices()
    bloodstriker_prices = get_all_bloodstriker_prices()
    pin_sources_config = get_pin_source_config()
    noticias = get_all_news()
    
    return render_template('admin.html', 
                         users=users, 
                         pin_stock=pin_stock, 
                         pin_stock_freefire_global=pin_stock_freefire_global,
                         prices=prices, 
                         freefire_global_prices=freefire_global_prices,
                         bloodstriker_prices=bloodstriker_prices,
                         pin_sources_config=pin_sources_config,
                         noticias=noticias)

@app.route('/admin/add_credit', methods=['POST'])
def admin_add_credit():
    if not session.get('is_admin'):
        flash('Acceso denegado. Solo administradores.', 'error')
        return redirect('/auth')
    
    user_id = request.form.get('user_id')
    amount = float(request.form.get('amount', 0))
    
    if user_id and amount > 0:
        add_credit_to_user(user_id, amount)
        flash(f'Se agregaron ${amount:.2f} al usuario ID {user_id}', 'success')
    else:
        flash('Datos inválidos para agregar crédito', 'error')
    
    return redirect('/admin')

@app.route('/admin/update_balance', methods=['POST'])
def admin_update_balance():
    if not session.get('is_admin'):
        flash('Acceso denegado. Solo administradores.', 'error')
        return redirect('/auth')
    
    user_id = request.form.get('user_id')
    new_balance = float(request.form.get('new_balance', 0))
    
    if user_id and new_balance >= 0:
        update_user_balance(user_id, new_balance)
        flash(f'Saldo actualizado a ${new_balance:.2f} para usuario ID {user_id}', 'success')
    else:
        flash('Datos inválidos para actualizar saldo', 'error')
    
    return redirect('/admin')

@app.route('/admin/delete_user', methods=['POST'])
def admin_delete_user():
    if not session.get('is_admin'):
        flash('Acceso denegado. Solo administradores.', 'error')
        return redirect('/auth')
    
    user_id = request.form.get('user_id')
    
    if user_id:
        delete_user(user_id)
        flash(f'Usuario ID {user_id} eliminado exitosamente', 'success')
    else:
        flash('ID de usuario inválido', 'error')
    
    return redirect('/admin')

@app.route('/admin/add_pin', methods=['POST'])
def admin_add_pin():
    if not session.get('is_admin'):
        flash('Acceso denegado. Solo administradores.', 'error')
        return redirect('/auth')
    
    monto_id = request.form.get('monto_id')
    pin_codigo = request.form.get('pin_codigo')
    game_type = request.form.get('game_type')
    
    if monto_id and pin_codigo and game_type:
        if game_type == 'freefire_latam':
            add_pin_freefire(int(monto_id), pin_codigo)
            # Obtener información del paquete dinámicamente
            packages_info = get_package_info_with_prices()
            package_info = packages_info.get(int(monto_id), {})
            juego_nombre = "Free Fire Latam"
        elif game_type == 'freefire_global':
            add_pin_freefire_global(int(monto_id), pin_codigo)
            # Obtener información del paquete dinámicamente
            packages_info = get_freefire_global_prices()
            package_info = packages_info.get(int(monto_id), {})
            juego_nombre = "Free Fire"
        else:
            flash('Tipo de juego inválido', 'error')
            return redirect('/admin')
        
        if package_info:
            paquete_nombre = f"{package_info['nombre']} / ${package_info['precio']:.2f}"
        else:
            paquete_nombre = "Paquete desconocido"
        
        flash(f'Pin agregado exitosamente para {juego_nombre} - {paquete_nombre}', 'success')
    else:
        flash('Datos inválidos para agregar pin', 'error')
    
    return redirect('/admin')

@app.route('/admin/add_pins_batch', methods=['POST'])
def admin_add_pins_batch():
    if not session.get('is_admin'):
        flash('Acceso denegado. Solo administradores.', 'error')
        return redirect('/auth')
    
    monto_id = request.form.get('batch_monto_id')
    pins_text = request.form.get('pins_batch')
    game_type = request.form.get('game_type')
    
    if not monto_id or not pins_text or not game_type:
        flash('Por favor complete todos los campos para el lote de pines', 'error')
        return redirect('/admin')
    
    # Procesar los pines (separados por líneas o comas)
    pins_list = []
    for line in pins_text.replace(',', '\n').split('\n'):
        pin = line.strip()
        if pin:
            pins_list.append(pin)
    
    if not pins_list:
        flash('No se encontraron pines válidos en el texto', 'error')
        return redirect('/admin')
    
    try:
        if game_type == 'freefire_latam':
            added_count = add_pins_batch(int(monto_id), pins_list)
            # Obtener información del paquete dinámicamente
            packages_info = get_package_info_with_prices()
            package_info = packages_info.get(int(monto_id), {})
            juego_nombre = "Free Fire Latam"
        elif game_type == 'freefire_global':
            added_count = add_pins_batch_freefire_global(int(monto_id), pins_list)
            # Obtener información del paquete dinámicamente
            packages_info = get_freefire_global_prices()
            package_info = packages_info.get(int(monto_id), {})
            juego_nombre = "Free Fire"
        else:
            flash('Tipo de juego inválido', 'error')
            return redirect('/admin')
        
        if package_info:
            paquete_nombre = f"{package_info['nombre']} / ${package_info['precio']:.2f}"
        else:
            paquete_nombre = "Paquete desconocido"
        
        flash(f'Se agregaron {added_count} pines exitosamente para {juego_nombre} - {paquete_nombre}', 'success')
        
    except Exception as e:
        flash(f'Error al agregar pines en lote: {str(e)}', 'error')
    
    return redirect('/admin')

@app.route('/admin/remove_duplicates', methods=['POST'])
def admin_remove_duplicates():
    if not session.get('is_admin'):
        flash('Acceso denegado. Solo administradores.', 'error')
        return redirect('/auth')
    
    try:
        duplicates_removed = remove_duplicate_pins()
        if duplicates_removed > 0:
            flash(f'Se eliminaron {duplicates_removed} pines duplicados exitosamente', 'success')
        else:
            flash('No se encontraron pines duplicados para eliminar', 'success')
    except Exception as e:
        flash(f'Error al eliminar pines duplicados: {str(e)}', 'error')
    
    return redirect('/admin')

@app.route('/admin/update_price', methods=['POST'])
def admin_update_price():
    if not session.get('is_admin'):
        flash('Acceso denegado. Solo administradores.', 'error')
        return redirect('/auth')
    
    package_id = request.form.get('package_id')
    new_price = request.form.get('new_price')
    
    if not package_id or not new_price:
        flash('Datos inválidos para actualizar precio', 'error')
        return redirect('/admin')
    
    try:
        new_price = float(new_price)
        if new_price < 0:
            flash('El precio no puede ser negativo', 'error')
            return redirect('/admin')
        
        # Obtener información del paquete antes de actualizar
        conn = get_db_connection()
        package = conn.execute('SELECT nombre FROM precios_paquetes WHERE id = ?', (package_id,)).fetchone()
        conn.close()
        
        if not package:
            flash('Paquete no encontrado', 'error')
            return redirect('/admin')
        
        # Actualizar precio
        update_package_price(int(package_id), new_price)
        flash(f'Precio actualizado exitosamente para {package["nombre"]}: ${new_price:.2f}', 'success')
        
    except ValueError:
        flash('Precio inválido. Debe ser un número válido.', 'error')
    except Exception as e:
        flash(f'Error al actualizar precio: {str(e)}', 'error')
    
    return redirect('/admin')

@app.route('/admin/update_name', methods=['POST'])
def admin_update_name():
    if not session.get('is_admin'):
        flash('Acceso denegado. Solo administradores.', 'error')
        return redirect('/auth')
    
    package_id = request.form.get('package_id')
    new_name = request.form.get('new_name')
    
    if not package_id or not new_name:
        flash('Datos inválidos para actualizar nombre', 'error')
        return redirect('/admin')
    
    try:
        new_name = new_name.strip()
        if len(new_name) < 1:
            flash('El nombre no puede estar vacío', 'error')
            return redirect('/admin')
        
        if len(new_name) > 50:
            flash('El nombre no puede exceder 50 caracteres', 'error')
            return redirect('/admin')
        
        # Obtener información del paquete antes de actualizar
        conn = get_db_connection()
        package = conn.execute('SELECT nombre FROM precios_paquetes WHERE id = ?', (package_id,)).fetchone()
        conn.close()
        
        if not package:
            flash('Paquete no encontrado', 'error')
            return redirect('/admin')
        
        old_name = package['nombre']
        
        # Actualizar nombre
        update_package_name(int(package_id), new_name)
        flash(f'Nombre actualizado exitosamente: "{old_name}" → "{new_name}"', 'success')
        
    except Exception as e:
        flash(f'Error al actualizar nombre: {str(e)}', 'error')
    
    return redirect('/admin')

@app.route('/billetera')
def billetera():
    if 'usuario' not in session:
        return redirect('/auth')
    
    is_admin = session.get('is_admin', False)
    
    if is_admin:
        # Admin ve todos los créditos agregados a usuarios
        wallet_credits = get_all_wallet_credits()
        
        return render_template('billetera.html', 
                             wallet_credits=wallet_credits,
                             user_id=session.get('id', '00000'),
                             balance=0,
                             is_admin=True)
    else:
        # Usuario normal ve solo sus créditos de billetera
        user_id = session.get('user_db_id')
        if not user_id:
            flash('Error al acceder a la billetera', 'error')
            return redirect('/')
        
        # Marcar todas las notificaciones de cartera como vistas
        mark_wallet_credits_as_read(user_id)
        
        # Obtener créditos de billetera del usuario
        wallet_credits = get_user_wallet_credits(user_id)
        
        # Actualizar saldo
        conn = get_db_connection()
        user = conn.execute('SELECT saldo FROM usuarios WHERE id = ?', (user_id,)).fetchone()
        if user:
            session['saldo'] = user['saldo']
        conn.close()
        
        return render_template('billetera.html', 
                             wallet_credits=wallet_credits, 
                             user_id=session.get('id', '00000'),
                             balance=session.get('saldo', 0),
                             is_admin=False)


@app.route('/validar/freefire_latam', methods=['POST'])
def validar_freefire_latam():
    if 'usuario' not in session:
        return redirect('/auth')
    
    monto_id = request.form.get('monto')
    cantidad = request.form.get('cantidad')
    
    if not monto_id or not cantidad:
        flash('Por favor selecciona un paquete y cantidad', 'error')
        return redirect('/juego/freefire_latam')
    
    monto_id = int(monto_id)
    cantidad = int(cantidad)
    user_id = session.get('user_db_id')
    is_admin = session.get('is_admin', False)
    
    # Validar cantidad (entre 1 y 10)
    if cantidad < 1 or cantidad > 10:
        flash('La cantidad debe estar entre 1 y 10 pines', 'error')
        return redirect('/juego/freefire_latam')
    
    # Obtener precio dinámico de la base de datos
    precio_unitario = get_price_by_id(monto_id)
    precio_total = precio_unitario * cantidad
    
    # Obtener información del paquete usando cache
    packages_info = get_package_info_with_prices_cached()
    package_info = packages_info.get(monto_id, {})
    
    paquete_nombre = f"{package_info.get('nombre', 'Paquete')} x{cantidad}"
    
    if precio_unitario == 0:
        flash('Paquete no encontrado o inactivo', 'error')
        return redirect('/juego/freefire_latam')
    
    saldo_actual = session.get('saldo', 0)
    
    # Solo verificar saldo para usuarios normales, admin puede comprar sin saldo
    if not is_admin and saldo_actual < precio_total:
        flash(f'Saldo insuficiente. Necesitas ${precio_total:.2f} pero tienes ${saldo_actual:.2f}', 'error')
        return redirect('/juego/freefire_latam')
    
    # CRÍTICO: Usar pin manager para obtener pines ANTES de descontar saldo
    pin_manager = create_pin_manager(DATABASE)
    
    try:
        # PASO 1: Intentar obtener los pines SIN descontar saldo aún
        if cantidad == 1:
            # Para un solo pin
            result = pin_manager.request_pin(monto_id)
            
            if result.get('status') == 'success':
                pines_codigos = [result.get('pin_code')]
                sources_used = ['local_stock']
            else:
                flash('Sin stock disponible para este paquete.', 'error')
                return redirect('/juego/freefire_latam')
        else:
            # Para múltiples pines
            result = pin_manager.request_multiple_pins(monto_id, cantidad)
            
            if result.get('status') == 'success':
                pines_data = result.get('pins', [])
                pines_codigos = [pin['pin_code'] for pin in pines_data]
                # Determinar fuentes usadas basado en el resultado
                source = result.get('source', 'local_stock')
                sources_used = [source]
            elif result.get('status') == 'partial_success':
                # Algunos pines obtenidos, pero no todos
                pines_data = result.get('pins', [])
                pines_codigos = [pin['pin_code'] for pin in pines_data]
                source = result.get('source', 'local_stock')
                sources_used = [source]
                
                # Actualizar cantidad y precio total para los pines realmente obtenidos
                cantidad_original = cantidad
                cantidad = len(pines_codigos)
                precio_total = precio_unitario * cantidad  # Recalcular precio
                
                flash(f'Advertencia: Solo se obtuvieron {cantidad} pines de los {cantidad_original} solicitados. Precio ajustado a ${precio_total:.2f}', 'warning')
            else:
                flash(f'Error al obtener pines. {result.get("message", "Error desconocido")}', 'error')
                return redirect('/juego/freefire_latam')
        
        # PASO 2: Verificar que se obtuvieron pines exitosamente
        if not pines_codigos:
            flash('No se pudieron obtener pines. Intente nuevamente.', 'error')
            return redirect('/juego/freefire_latam')
        
        # PASO 3: AHORA SÍ verificar saldo final después de saber cuántos pines obtuvimos
        if not is_admin and saldo_actual < precio_total:
            flash(f'Saldo insuficiente para la cantidad obtenida. Necesitas ${precio_total:.2f} pero tienes ${saldo_actual:.2f}', 'error')
            return redirect('/juego/freefire_latam')
        
        # Generar datos de la transacción
        import random
        import string
        numero_control = ''.join(random.choices(string.digits, k=10))
        transaccion_id = 'FF-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        # Procesar la transacción
        conn = get_db_connection()
        try:
            # Solo actualizar saldo si no es admin
            if not is_admin:
                conn.execute('UPDATE usuarios SET saldo = saldo - ? WHERE id = ?', (precio_total, user_id))
            
            # Registrar la transacción
            pines_texto = '\n'.join(pines_codigos)
            
            # Para admin, registrar con monto negativo pero agregar etiqueta [ADMIN]
            if is_admin:
                pines_texto = f"[ADMIN - PRUEBA/GESTIÓN]\n{pines_texto}"
                monto_transaccion = -precio_total  # Registrar monto real para mostrar en historial
            else:
                monto_transaccion = -precio_total
                
                # Agregar información de fuente en el pin si viene de API externa
                if 'inefable_api' in sources_used:
                    pines_texto += f"\n[Fuente: {', '.join(sources_used)}]"
            
            conn.execute('''
                INSERT INTO transacciones (usuario_id, numero_control, pin, transaccion_id, monto)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, numero_control, pines_texto, transaccion_id, monto_transaccion))
            
            # Limitar transacciones a 100 por usuario (aumentado de 30 para evitar eliminaciones frecuentes)
            conn.execute('''
                DELETE FROM transacciones 
                WHERE usuario_id = ? AND id NOT IN (
                    SELECT id FROM transacciones 
                    WHERE usuario_id = ? 
                    ORDER BY fecha DESC 
                    LIMIT 100
                )
            ''', (user_id, user_id))
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            flash('Error al procesar la transacción. Intente nuevamente.', 'error')
            return redirect('/juego/freefire_latam')
        finally:
            conn.close()
        
        # Actualizar saldo en sesión solo si no es admin
        if not is_admin:
            session['saldo'] = saldo_actual - precio_total
        
        # Registrar venta en estadísticas semanales (solo para usuarios normales)
        if not is_admin:
            register_weekly_sale('freefire_latam', monto_id, package_info.get('nombre', 'Paquete'), precio_unitario, cantidad)
        
        # Guardar datos de la compra en la sesión para mostrar después del redirect
        if cantidad == 1:
            # Para un solo pin
            session['compra_exitosa'] = {
                'paquete_nombre': paquete_nombre,
                'monto_compra': precio_total,
                'numero_control': numero_control,
                'pin': pines_codigos[0],
                'transaccion_id': transaccion_id,
                'cantidad_comprada': cantidad,
                'source': sources_used[0] if sources_used else 'local_stock'
            }
        else:
            # Para múltiples pines
            session['compra_exitosa'] = {
                'paquete_nombre': paquete_nombre,
                'monto_compra': precio_total,
                'numero_control': numero_control,
                'pines_list': pines_codigos,
                'transaccion_id': transaccion_id,
                'cantidad_comprada': cantidad,
                'sources_used': sources_used
            }
        
        # Redirect para evitar reenvío del formulario (patrón POST-Redirect-GET)
        return redirect('/juego/freefire_latam?compra=exitosa')
        
    except Exception as e:
        flash(f'Error inesperado al procesar la compra: {str(e)}', 'error')
        return redirect('/juego/freefire_latam')

@app.route('/juego/freefire_latam')
def freefire_latam():
    if 'usuario' not in session:
        return redirect('/auth')
    
    # Actualizar saldo desde la base de datos
    user_id = session.get('user_db_id')
    if user_id:
        conn = get_db_connection()
        user = conn.execute('SELECT saldo FROM usuarios WHERE id = ?', (user_id,)).fetchone()
        if user:
            session['saldo'] = user['saldo']
        conn.close()
    
    # Obtener stock local y configuración de fuentes
    pin_manager = create_pin_manager(DATABASE)
    local_stock = pin_manager.get_local_stock()
    pin_sources_config = get_pin_source_config()
    
    # Preparar información de stock considerando la configuración de fuentes
    stock = {}
    for monto_id in range(1, 10):
        local_count = local_stock.get(monto_id, 0)
        source_config = pin_sources_config.get(monto_id, 'local')
        
        # Si está configurado para API externa, siempre mostrar disponible
        if source_config == 'api_externa':
            stock[monto_id] = {
                'local': local_count,
                'external_available': True,  # Siempre True para API externa
                'total_available': True,     # Siempre disponible cuando usa API externa
            }
        else:
            # Si está configurado para stock local, mostrar según stock real
            stock[monto_id] = {
                'local': local_count,
                'external_available': False,
                'total_available': local_count > 0,  # Solo disponible si hay stock local
            }
    
    # Obtener precios dinámicos
    prices = get_package_info_with_prices()
    
    # Verificar si hay una compra exitosa para mostrar (solo una vez)
    compra_exitosa = False
    compra_data = {}
    
    # Solo mostrar compra exitosa si viene del redirect POST y hay datos en sesión
    if request.args.get('compra') == 'exitosa' and 'compra_exitosa' in session:
        compra_exitosa = True
        compra_data = session.pop('compra_exitosa')  # Remover después de usar para evitar mostrar de nuevo
    
    return render_template('freefire_latam.html', 
                         user_id=session.get('id', '00000'),
                         balance=session.get('saldo', 0),
                         stock=stock,
                         prices=prices,
                         compra_exitosa=compra_exitosa,
                         **compra_data)  # Desempaquetar los datos de la compra

# Rutas para Blood Striker
@app.route('/juego/bloodstriker')
def bloodstriker():
    if 'usuario' not in session:
        return redirect('/auth')
    
    # Actualizar saldo desde la base de datos
    user_id = session.get('user_db_id')
    if user_id:
        conn = get_db_connection()
        user = conn.execute('SELECT saldo FROM usuarios WHERE id = ?', (user_id,)).fetchone()
        if user:
            session['saldo'] = user['saldo']
        conn.close()
    
    # Obtener precios dinámicos de Blood Striker
    prices = get_bloodstriker_prices()
    
    # Verificar si hay una compra exitosa para mostrar (solo una vez)
    compra_exitosa = False
    compra_data = {}
    
    # Solo mostrar compra exitosa si viene del redirect POST y hay datos en sesión
    if request.args.get('compra') == 'exitosa' and 'compra_bloodstriker_exitosa' in session:
        compra_exitosa = True
        compra_data = session.pop('compra_bloodstriker_exitosa')  # Remover después de usar
    
    return render_template('bloodstriker.html', 
                         user_id=session.get('id', '00000'),
                         balance=session.get('saldo', 0),
                         prices=prices,
                         compra_exitosa=compra_exitosa,
                         **compra_data)

@app.route('/validar/bloodstriker', methods=['POST'])
def validar_bloodstriker():
    if 'usuario' not in session:
        return redirect('/auth')
    
    package_id = request.form.get('monto')
    player_id = request.form.get('player_id')
    
    if not package_id or not player_id:
        flash('Por favor complete todos los campos', 'error')
        return redirect('/juego/bloodstriker')
    
    package_id = int(package_id)
    user_id = session.get('user_db_id')
    is_admin = session.get('is_admin', False)
    
    # Obtener precio dinámico de la base de datos
    precio = get_bloodstriker_price_by_id(package_id)
    
    # Obtener información del paquete usando cache
    packages_info = get_bloodstriker_prices_cached()
    package_info = packages_info.get(package_id, {})
    
    paquete_nombre = f"{package_info.get('nombre', 'Paquete')} / ${precio:.2f}"
    
    if precio == 0:
        flash('Paquete no encontrado o inactivo', 'error')
        return redirect('/juego/bloodstriker')
    
    saldo_actual = session.get('saldo', 0)
    
    # Solo verificar saldo para usuarios normales, admin puede comprar sin saldo
    if not is_admin and saldo_actual < precio:
        flash(f'Saldo insuficiente. Necesitas ${precio:.2f} pero tienes ${saldo_actual:.2f}', 'error')
        return redirect('/juego/bloodstriker')
    
    # Procesar la compra (crear transacción pendiente)
    try:
        # Solo descontar saldo si no es admin
        if not is_admin:
            conn = get_db_connection()
            conn.execute('UPDATE usuarios SET saldo = saldo - ? WHERE id = ?', (precio, user_id))
            conn.commit()
            conn.close()
            session['saldo'] = saldo_actual - precio
        
        # Crear transacción pendiente
        transaction_data = create_bloodstriker_transaction(user_id, player_id, package_id, precio)
        
        # Obtener datos del usuario para la notificación
        conn = get_db_connection()
        user_data = conn.execute('''
            SELECT nombre, apellido, correo FROM usuarios WHERE id = ?
        ''', (user_id,)).fetchone()
        conn.close()
        
        # Enviar notificación por correo al admin (solo si no es admin quien hace la compra)
        if not is_admin and user_data:
            notification_data = {
                'nombre': user_data['nombre'],
                'apellido': user_data['apellido'],
                'correo': user_data['correo'],
                'player_id': player_id,
                'paquete_nombre': package_info.get('nombre', 'Paquete desconocido'),
                'precio': precio,
                'numero_control': transaction_data['numero_control'],
                'transaccion_id': transaction_data['transaccion_id'],
                'fecha': convert_to_venezuela_time(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            }
            send_bloodstriker_notification(notification_data)
        
        # Guardar datos de la compra en la sesión para mostrar después del redirect
        session['compra_bloodstriker_exitosa'] = {
            'paquete_nombre': paquete_nombre,
            'monto_compra': precio,
            'numero_control': transaction_data['numero_control'],
            'transaccion_id': transaction_data['transaccion_id'],
            'player_id': player_id,
            'estado': 'pendiente'
        }
        
        # Redirect para evitar reenvío del formulario
        return redirect('/juego/bloodstriker?compra=exitosa')
        
    except Exception as e:
        flash('Error al procesar la compra. Intente nuevamente.', 'error')
        return redirect('/juego/bloodstriker')

# Rutas de administrador para Blood Striker
@app.route('/admin/bloodstriker_transactions')
def admin_bloodstriker_transactions():
    if not session.get('is_admin'):
        flash('Acceso denegado. Solo administradores.', 'error')
        return redirect('/auth')
    
    pending_transactions = get_pending_bloodstriker_transactions()
    return render_template('admin_bloodstriker.html', transactions=pending_transactions)

@app.route('/admin/bloodstriker_approve', methods=['POST'])
def admin_bloodstriker_approve():
    if not session.get('is_admin'):
        flash('Acceso denegado. Solo administradores.', 'error')
        return redirect('/auth')
    
    transaction_id = request.form.get('transaction_id')
    notas = request.form.get('notas', '')
    
    if transaction_id:
        update_bloodstriker_transaction_status(int(transaction_id), 'aprobado', session.get('user_db_id'), notas)
        flash('Transacción aprobada exitosamente', 'success')
    else:
        flash('ID de transacción inválido', 'error')
    
    return redirect('/admin/bloodstriker_transactions')

@app.route('/admin/bloodstriker_reject', methods=['POST'])
def admin_bloodstriker_reject():
    if not session.get('is_admin'):
        flash('Acceso denegado. Solo administradores.', 'error')
        return redirect('/auth')
    
    transaction_id = request.form.get('transaction_id')
    notas = request.form.get('notas', '')
    
    if transaction_id:
        # Obtener información de la transacción para devolver el saldo
        conn = get_db_connection()
        transaction = conn.execute('''
            SELECT usuario_id, monto FROM transacciones_bloodstriker 
            WHERE id = ?
        ''', (transaction_id,)).fetchone()
        
        if transaction:
            # Devolver saldo al usuario (monto es negativo, así que sumamos el valor absoluto)
            conn.execute('UPDATE usuarios SET saldo = saldo + ? WHERE id = ?', 
                        (abs(transaction['monto']), transaction['usuario_id']))
            conn.commit()
        conn.close()
        
        # Actualizar estado de la transacción
        update_bloodstriker_transaction_status(int(transaction_id), 'rechazado', session.get('user_db_id'), notas)
        flash('Transacción rechazada y saldo devuelto al usuario', 'success')
    else:
        flash('ID de transacción inválido', 'error')
    
    return redirect('/admin/bloodstriker_transactions')

@app.route('/admin/update_bloodstriker_price', methods=['POST'])
def admin_update_bloodstriker_price():
    if not session.get('is_admin'):
        flash('Acceso denegado. Solo administradores.', 'error')
        return redirect('/auth')
    
    package_id = request.form.get('package_id')
    new_price = request.form.get('new_price')
    
    if not package_id or not new_price:
        flash('Datos inválidos para actualizar precio', 'error')
        return redirect('/admin')
    
    try:
        new_price = float(new_price)
        if new_price < 0:
            flash('El precio no puede ser negativo', 'error')
            return redirect('/admin')
        
        # Obtener información del paquete antes de actualizar
        conn = get_db_connection()
        package = conn.execute('SELECT nombre FROM precios_bloodstriker WHERE id = ?', (package_id,)).fetchone()
        conn.close()
        
        if not package:
            flash('Paquete no encontrado', 'error')
            return redirect('/admin')
        
        # Actualizar precio
        update_bloodstriker_price(int(package_id), new_price)
        flash(f'Precio de Blood Striker actualizado exitosamente para {package["nombre"]}: ${new_price:.2f}', 'success')
        
    except ValueError:
        flash('Precio inválido. Debe ser un número válido.', 'error')
    except Exception as e:
        flash(f'Error al actualizar precio: {str(e)}', 'error')
    
    return redirect('/admin')

@app.route('/admin/update_bloodstriker_name', methods=['POST'])
def admin_update_bloodstriker_name():
    if not session.get('is_admin'):
        flash('Acceso denegado. Solo administradores.', 'error')
        return redirect('/auth')
    
    package_id = request.form.get('package_id')
    new_name = request.form.get('new_name')
    
    if not package_id or not new_name:
        flash('Datos inválidos para actualizar nombre', 'error')
        return redirect('/admin')
    
    try:
        new_name = new_name.strip()
        if len(new_name) < 1:
            flash('El nombre no puede estar vacío', 'error')
            return redirect('/admin')
        
        if len(new_name) > 50:
            flash('El nombre no puede exceder 50 caracteres', 'error')
            return redirect('/admin')
        
        # Obtener información del paquete antes de actualizar
        conn = get_db_connection()
        package = conn.execute('SELECT nombre FROM precios_bloodstriker WHERE id = ?', (package_id,)).fetchone()
        conn.close()
        
        if not package:
            flash('Paquete no encontrado', 'error')
            return redirect('/admin')
        
        old_name = package['nombre']
        
        # Actualizar nombre
        update_bloodstriker_name(int(package_id), new_name)
        flash(f'Nombre de Blood Striker actualizado exitosamente: "{old_name}" → "{new_name}"', 'success')
        
    except Exception as e:
        flash(f'Error al actualizar nombre: {str(e)}', 'error')
    
    return redirect('/admin')

@app.route('/admin/update_freefire_global_price', methods=['POST'])
def admin_update_freefire_global_price():
    if not session.get('is_admin'):
        flash('Acceso denegado. Solo administradores.', 'error')
        return redirect('/auth')
    
    package_id = request.form.get('package_id')
    new_price = request.form.get('new_price')
    
    if not package_id or not new_price:
        flash('Datos inválidos para actualizar precio', 'error')
        return redirect('/admin')
    
    try:
        new_price = float(new_price)
        if new_price < 0:
            flash('El precio no puede ser negativo', 'error')
            return redirect('/admin')
        
        # Obtener información del paquete antes de actualizar
        conn = get_db_connection()
        package = conn.execute('SELECT nombre FROM precios_freefire_global WHERE id = ?', (package_id,)).fetchone()
        conn.close()
        
        if not package:
            flash('Paquete no encontrado', 'error')
            return redirect('/admin')
        
        # Actualizar precio
        update_freefire_global_price(int(package_id), new_price)
        flash(f'Precio de Free Fire actualizado exitosamente para {package["nombre"]}: ${new_price:.2f}', 'success')
        
    except ValueError:
        flash('Precio inválido. Debe ser un número válido.', 'error')
    except Exception as e:
        flash(f'Error al actualizar precio: {str(e)}', 'error')
    
    return redirect('/admin')

@app.route('/admin/update_freefire_global_name', methods=['POST'])
def admin_update_freefire_global_name():
    if not session.get('is_admin'):
        flash('Acceso denegado. Solo administradores.', 'error')
        return redirect('/auth')
    
    package_id = request.form.get('package_id')
    new_name = request.form.get('new_name')
    
    if not package_id or not new_name:
        flash('Datos inválidos para actualizar nombre', 'error')
        return redirect('/admin')
    
    try:
        new_name = new_name.strip()
        if len(new_name) < 1:
            flash('El nombre no puede estar vacío', 'error')
            return redirect('/admin')
        
        if len(new_name) > 50:
            flash('El nombre no puede exceder 50 caracteres', 'error')
            return redirect('/admin')
        
        # Obtener información del paquete antes de actualizar
        conn = get_db_connection()
        package = conn.execute('SELECT nombre FROM precios_freefire_global WHERE id = ?', (package_id,)).fetchone()
        conn.close()
        
        if not package:
            flash('Paquete no encontrado', 'error')
            return redirect('/admin')
        
        old_name = package['nombre']
        
        # Actualizar nombre
        update_freefire_global_name(int(package_id), new_name)
        flash(f'Nombre de Free Fire actualizado exitosamente: "{old_name}" → "{new_name}"', 'success')
        
    except Exception as e:
        flash(f'Error al actualizar nombre: {str(e)}', 'error')
    
    return redirect('/admin')

@app.route('/admin/approve_bloodstriker/<int:transaction_id>', methods=['POST'])
def approve_bloodstriker_transaction(transaction_id):
    if not session.get('is_admin'):
        flash('Acceso denegado. Solo administradores.', 'error')
        return redirect('/auth')
    
    try:
        # Obtener información de la transacción de Blood Striker
        conn = get_db_connection()
        bs_transaction = conn.execute('''
            SELECT bs.*, u.nombre, u.apellido, p.nombre as paquete_nombre, p.precio
            FROM transacciones_bloodstriker bs
            JOIN usuarios u ON bs.usuario_id = u.id
            JOIN precios_bloodstriker p ON bs.paquete_id = p.id
            WHERE bs.id = ?
        ''', (transaction_id,)).fetchone()
        
        if bs_transaction:
            # Crear transacción normal en el historial
            conn.execute('''
                INSERT INTO transacciones (usuario_id, numero_control, pin, transaccion_id, monto)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                bs_transaction['usuario_id'],
                bs_transaction['numero_control'],
                f"ID: {bs_transaction['player_id']}",
                bs_transaction['transaccion_id'],
                bs_transaction['monto']
            ))
            
            # Limitar transacciones a 100 por usuario (aumentado de 30 para evitar eliminaciones frecuentes)
            conn.execute('''
                DELETE FROM transacciones 
                WHERE usuario_id = ? AND id NOT IN (
                    SELECT id FROM transacciones 
                    WHERE usuario_id = ? 
                    ORDER BY fecha DESC 
                    LIMIT 100
                )
            ''', (bs_transaction['usuario_id'], bs_transaction['usuario_id']))
            
            conn.commit()
            
            # Registrar venta en estadísticas semanales
            register_weekly_sale(
                'bloodstriker', 
                bs_transaction['paquete_id'], 
                bs_transaction['paquete_nombre'], 
                bs_transaction['precio'], 
                1
            )
            
            # Crear notificación personalizada para el usuario
            titulo = "🎯 Recarga Blood Striker Aprobada"
            mensaje = f"Tu recarga de {bs_transaction['paquete_nombre']} por ${bs_transaction['precio']:.2f} ha sido aprobada exitosamente. ID: {bs_transaction['player_id']}"
            create_personal_notification(bs_transaction['usuario_id'], titulo, mensaje, 'success')
        
        conn.close()
        
        # Actualizar estado de la transacción de Blood Striker
        update_bloodstriker_transaction_status(transaction_id, 'aprobado', session.get('user_db_id'))
        flash('Transacción aprobada exitosamente', 'success')
    except Exception as e:
        flash(f'Error al aprobar transacción: {str(e)}', 'error')
    
    return redirect('/')

@app.route('/admin/reject_bloodstriker/<int:transaction_id>', methods=['POST'])
def reject_bloodstriker_transaction(transaction_id):
    if not session.get('is_admin'):
        flash('Acceso denegado. Solo administradores.', 'error')
        return redirect('/auth')
    
    try:
        # Obtener información de la transacción para devolver el saldo
        conn = get_db_connection()
        transaction = conn.execute('''
            SELECT usuario_id, monto FROM transacciones_bloodstriker 
            WHERE id = ?
        ''', (transaction_id,)).fetchone()
        
        if transaction:
            # Devolver saldo al usuario (monto es negativo, así que sumamos el valor absoluto)
            conn.execute('UPDATE usuarios SET saldo = saldo + ? WHERE id = ?', 
                        (abs(transaction['monto']), transaction['usuario_id']))
            conn.commit()
        conn.close()
        
        # Actualizar estado de la transacción
        update_bloodstriker_transaction_status(transaction_id, 'rechazado', session.get('user_db_id'))
        flash('Transacción rechazada y saldo devuelto al usuario', 'success')
    except Exception as e:
        flash(f'Error al rechazar transacción: {str(e)}', 'error')
    
    return redirect('/')

# Rutas de administración para API externa
@app.route('/admin/test_external_api', methods=['POST'])
def admin_test_external_api():
    if not session.get('is_admin'):
        flash('Acceso denegado. Solo administradores.', 'error')
        return redirect('/auth')
    
    try:
        pin_manager = create_pin_manager(DATABASE)
        result = pin_manager.test_external_api()
        
        if result.get('status') == 'success':
            flash(f'✅ API Externa: {result.get("message")}', 'success')
        else:
            flash(f'❌ API Externa: {result.get("message")}', 'error')
    except Exception as e:
        flash(f'Error al probar API externa: {str(e)}', 'error')
    
    return redirect('/admin')


@app.route('/admin/toggle_pin_source', methods=['POST'])
def admin_toggle_pin_source():
    if not session.get('is_admin'):
        flash('Acceso denegado. Solo administradores.', 'error')
        return redirect('/auth')
    
    monto_id = request.form.get('monto_id')
    fuente = request.form.get('fuente')
    
    if not monto_id or not fuente:
        flash('Datos inválidos para cambiar fuente', 'error')
        return redirect('/admin')
    
    try:
        monto_id = int(monto_id)
        if monto_id < 1 or monto_id > 9:
            flash('Monto ID debe estar entre 1 y 9', 'error')
            return redirect('/admin')
        
        if fuente not in ['local', 'api_externa']:
            flash('Fuente inválida. Debe ser "local" o "api_externa"', 'error')
            return redirect('/admin')
        
        # Actualizar configuración
        update_pin_source_config(monto_id, fuente)
        
        # Obtener información del paquete
        packages_info = get_package_info_with_prices()
        package_info = packages_info.get(monto_id, {})
        paquete_nombre = package_info.get('nombre', f'Paquete {monto_id}')
        
        fuente_texto = 'Stock Local' if fuente == 'local' else 'API Externa'
        flash(f'✅ Configuración actualizada: {paquete_nombre} → {fuente_texto}', 'success')
        
    except ValueError:
        flash('Monto ID debe ser un número válido', 'error')
    except Exception as e:
        flash(f'Error al actualizar configuración: {str(e)}', 'error')
    
    return redirect('/admin')

# Rutas para sistema de noticias
@app.route('/noticias')
def noticias():
    if 'usuario' not in session:
        return redirect('/auth')
    
    user_id = session.get('user_db_id')
    is_admin = session.get('is_admin', False)
    
    # Para admin, usar ID 0 y permitir acceso
    if is_admin:
        user_id = 0
    elif not user_id:
        flash('Error al acceder a las noticias', 'error')
        return redirect('/')
    
    # Marcar todas las noticias como leídas (solo para usuarios normales)
    if not is_admin:
        mark_news_as_read(user_id)
    
    # Obtener noticias para mostrar
    noticias_list = get_user_news(user_id)
    
    return render_template('noticias.html', 
                         noticias=noticias_list,
                         user_id=session.get('id', '00000'),
                         is_admin=is_admin)

@app.route('/notificaciones')
def notificaciones():
    """Ruta unificada para ver noticias y notificaciones personalizadas"""
    if 'usuario' not in session:
        return redirect('/auth')
    
    user_id = session.get('user_db_id')
    is_admin = session.get('is_admin', False)
    
    # Para admin, usar ID 0 y permitir acceso
    if is_admin:
        user_id = 0
    elif not user_id:
        flash('Error al acceder a las notificaciones', 'error')
        return redirect('/')
    
    # Para usuarios normales, obtener y procesar notificaciones personalizadas
    notificaciones_personalizadas = []
    if not is_admin:
        # Obtener notificaciones personalizadas antes de marcarlas como leídas
        notificaciones_personalizadas = get_user_personal_notifications(user_id)
        
        # Marcar notificaciones personalizadas como leídas (las elimina)
        if notificaciones_personalizadas:
            mark_personal_notifications_as_read(user_id)
        
        # Marcar noticias como leídas
        mark_news_as_read(user_id)
    
    # Obtener noticias para mostrar
    noticias_list = get_user_news(user_id)
    
    return render_template('noticias.html', 
                         noticias=noticias_list,
                         notificaciones_personalizadas=notificaciones_personalizadas,
                         user_id=session.get('id', '00000'),
                         is_admin=is_admin)

@app.route('/admin/create_news', methods=['POST'])
def admin_create_news():
    if not session.get('is_admin'):
        flash('Acceso denegado. Solo administradores.', 'error')
        return redirect('/auth')
    
    titulo = request.form.get('titulo')
    contenido = request.form.get('contenido')
    importante = request.form.get('importante') == '1'
    
    if not titulo or not contenido:
        flash('Por favor complete todos los campos obligatorios', 'error')
        return redirect('/admin')
    
    # Validar longitud
    if len(titulo) > 200:
        flash('El título no puede exceder 200 caracteres', 'error')
        return redirect('/admin')
    
    if len(contenido) > 2000:
        flash('El contenido no puede exceder 2000 caracteres', 'error')
        return redirect('/admin')
    
    try:
        news_id = create_news(titulo, contenido, importante)
        tipo_noticia = "importante" if importante else "normal"
        flash(f'Noticia {tipo_noticia} creada exitosamente (ID: {news_id})', 'success')
    except Exception as e:
        flash(f'Error al crear la noticia: {str(e)}', 'error')
    
    return redirect('/admin')

@app.route('/admin/delete_news', methods=['POST'])
def admin_delete_news():
    if not session.get('is_admin'):
        flash('Acceso denegado. Solo administradores.', 'error')
        return redirect('/auth')
    
    news_id = request.form.get('news_id')
    
    if not news_id:
        flash('ID de noticia inválido', 'error')
        return redirect('/admin')
    
    try:
        delete_news(int(news_id))
        flash('Noticia eliminada exitosamente', 'success')
    except Exception as e:
        flash(f'Error al eliminar la noticia: {str(e)}', 'error')
    
    return redirect('/admin')

# ============= RUTAS PARA GESTIÓN DE RENTABILIDAD =============

@app.route('/admin/update_purchase_price', methods=['POST'])
def admin_update_purchase_price():
    """Actualiza el precio de compra de un paquete - Compatible con Render"""
    if not session.get('is_admin'):
        flash('Acceso denegado. Solo administradores.', 'error')
        return redirect('/auth')
    
    juego = request.form.get('juego')
    paquete_id = request.form.get('paquete_id')
    nuevo_precio = request.form.get('nuevo_precio')
    
    if not all([juego, paquete_id, nuevo_precio]):
        flash('Datos inválidos para actualizar precio de compra', 'error')
        return redirect('/admin')
    
    try:
        nuevo_precio = float(nuevo_precio)
        paquete_id = int(paquete_id)
        
        if nuevo_precio < 0:
            flash('El precio de compra no puede ser negativo', 'error')
            return redirect('/admin')
        
        # Validar juego
        if juego not in ['freefire_latam', 'freefire_global', 'bloodstriker']:
            flash('Tipo de juego inválido', 'error')
            return redirect('/admin')
        
        # Obtener nombre del paquete para el mensaje
        try:
            if juego == 'freefire_latam':
                packages_info = get_package_info_with_prices()
            elif juego == 'freefire_global':
                packages_info = get_freefire_global_prices()
            else:  # bloodstriker
                packages_info = get_bloodstriker_prices()
            
            package_info = packages_info.get(paquete_id, {})
            paquete_nombre = package_info.get('nombre', f'Paquete {paquete_id}')
        except Exception as e:
            print(f"Error obteniendo información del paquete: {e}")
            paquete_nombre = f'Paquete {paquete_id}'
        
        # Actualizar precio de compra usando función compatible con Render
        success = update_purchase_price(juego, paquete_id, nuevo_precio)
        
        if success:
            juego_display = {
                'freefire_latam': 'Free Fire LATAM',
                'freefire_global': 'Free Fire',
                'bloodstriker': 'Blood Striker'
            }.get(juego, juego)
            
            flash(f'Precio de compra actualizado para {juego_display} - {paquete_nombre}: ${nuevo_precio:.2f}', 'success')
        else:
            flash('Error al actualizar precio de compra en la base de datos', 'error')
        
    except ValueError:
        flash('Precio inválido. Debe ser un número válido.', 'error')
    except Exception as e:
        print(f"Error en admin_update_purchase_price: {e}")
        flash(f'Error al actualizar precio de compra: {str(e)}', 'error')
    
    return redirect('/admin')

@app.route('/admin/profitability')
def admin_profitability():
    """Muestra el análisis de rentabilidad de todos los productos"""
    if not session.get('is_admin'):
        flash('Acceso denegado. Solo administradores.', 'error')
        return redirect('/auth')
    
    try:
        profit_analysis = get_profit_analysis()
        return render_template('admin_profitability.html', profit_analysis=profit_analysis)
    except Exception as e:
        flash(f'Error al obtener análisis de rentabilidad: {str(e)}', 'error')
        return redirect('/admin')

@app.route('/admin/weekly_sales')
def admin_weekly_sales():
    """Muestra las estadísticas de ventas semanales"""
    if not session.get('is_admin'):
        flash('Acceso denegado. Solo administradores.', 'error')
        return redirect('/auth')
    
    try:
        weekly_stats = get_weekly_sales_stats()
        return render_template('admin_weekly_sales.html', **weekly_stats)
    except Exception as e:
        flash(f'Error al obtener estadísticas semanales: {str(e)}', 'error')
        return redirect('/admin')

@app.route('/admin/clean_weekly_sales', methods=['POST'])
def admin_clean_weekly_sales():
    """Limpia manualmente las ventas semanales antiguas"""
    if not session.get('is_admin'):
        flash('Acceso denegado. Solo administradores.', 'error')
        return redirect('/auth')
    
    try:
        deleted_count = clean_old_weekly_sales()
        if deleted_count > 0:
            flash(f'Se eliminaron {deleted_count} registros de ventas antiguas', 'success')
        else:
            flash('No se encontraron registros antiguos para eliminar', 'success')
    except Exception as e:
        flash(f'Error al limpiar ventas antiguas: {str(e)}', 'error')
    
    return redirect('/admin')

@app.route('/admin/reset_all_weekly_sales', methods=['POST'])
def admin_reset_all_weekly_sales():
    """Resetea TODAS las estadísticas de ventas semanales (elimina todos los registros)"""
    if not session.get('is_admin'):
        flash('Acceso denegado. Solo administradores.', 'error')
        return redirect('/auth')
    
    try:
        deleted_count = reset_all_weekly_sales()
        if deleted_count > 0:
            flash(f'Se resetearon todas las estadísticas: {deleted_count} registros eliminados', 'success')
        else:
            flash('No había estadísticas para resetear', 'success')
    except Exception as e:
        flash(f'Error al resetear estadísticas: {str(e)}', 'error')
    
    return redirect('/admin')

@app.route('/admin/simple_stats')
def admin_simple_stats():
    """Obtiene estadísticas simples de ventas para la pestaña de estadísticas"""
    if not session.get('is_admin'):
        return jsonify({'error': 'Acceso denegado'}), 403
    
    try:
        conn = get_db_connection()
        
        # Estadísticas por juego
        stats = {}
        
        # Free Fire LATAM
        ff_latam = conn.execute('''
            SELECT SUM(cantidad_vendida) as total_units, SUM(ganancia_total) as total_profit
            FROM ventas_semanales 
            WHERE juego = 'freefire_latam'
        ''').fetchone()
        
        stats['freefire_latam'] = {
            'units': ff_latam['total_units'] or 0,
            'profit': ff_latam['total_profit'] or 0.0
        }
        
        # Free Fire Global
        ff_global = conn.execute('''
            SELECT SUM(cantidad_vendida) as total_units, SUM(ganancia_total) as total_profit
            FROM ventas_semanales 
            WHERE juego = 'freefire_global'
        ''').fetchone()
        
        stats['freefire_global'] = {
            'units': ff_global['total_units'] or 0,
            'profit': ff_global['total_profit'] or 0.0
        }
        
        # Blood Striker
        bs = conn.execute('''
            SELECT SUM(cantidad_vendida) as total_units, SUM(ganancia_total) as total_profit
            FROM ventas_semanales 
            WHERE juego = 'bloodstriker'
        ''').fetchone()
        
        stats['bloodstriker'] = {
            'units': bs['total_units'] or 0,
            'profit': bs['total_profit'] or 0.0
        }
        
        conn.close()
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/get_purchase_price/<juego>/<int:paquete_id>')
def admin_get_purchase_price(juego, paquete_id):
    """Obtiene el precio de compra actual para un juego y paquete específico"""
    if not session.get('is_admin'):
        return jsonify({'error': 'Acceso denegado'}), 403
    
    try:
        precio_compra = get_purchase_price(juego, paquete_id)
        return jsonify({'precio_compra': precio_compra})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============= FUNCIONES PARA GESTIÓN DE RENTABILIDAD =============

def get_purchase_prices():
    """Obtiene todos los precios de compra por juego y paquete"""
    conn = get_db_connection()
    prices = conn.execute('''
        SELECT * FROM precios_compra 
        WHERE activo = TRUE 
        ORDER BY juego, paquete_id
    ''').fetchall()
    conn.close()
    return prices

def get_purchase_price(juego, paquete_id):
    """Obtiene el precio de compra para un juego y paquete específico - Compatible con Render"""
    conn = None
    try:
        conn = get_db_connection_optimized()
        
        # Usar parámetros seguros y validados
        query = '''
            SELECT precio_compra FROM precios_compra 
            WHERE juego = ? AND paquete_id = ? AND activo = TRUE
        '''
        
        result = conn.execute(query, (str(juego), int(paquete_id))).fetchone()
        
        if result:
            return float(result['precio_compra'])
        else:
            return 0.0
            
    except Exception as e:
        print(f"Error en get_purchase_price: {e}")
        return 0.0
    finally:
        if conn:
            return_db_connection(conn)

def update_purchase_price(juego, paquete_id, nuevo_precio):
    """Actualiza el precio de compra para un juego y paquete específico - Compatible con Render"""
    conn = None
    try:
        conn = get_db_connection_optimized()
        
        # Usar transacción para asegurar consistencia
        conn.execute('BEGIN TRANSACTION')
        
        query = '''
            INSERT OR REPLACE INTO precios_compra (juego, paquete_id, precio_compra, fecha_actualizacion, activo)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, TRUE)
        '''
        
        conn.execute(query, (str(juego), int(paquete_id), float(nuevo_precio)))
        conn.execute('COMMIT')
        
        return True
        
    except Exception as e:
        print(f"Error en update_purchase_price: {e}")
        if conn:
            try:
                conn.execute('ROLLBACK')
            except:
                pass
        return False
    finally:
        if conn:
            return_db_connection(conn)

def get_profit_analysis():
    """Obtiene análisis de rentabilidad por juego y paquete"""
    conn = get_db_connection()
    
    # Análisis para Free Fire LATAM
    freefire_latam_analysis = []
    freefire_latam_prices = get_package_info_with_prices()
    for paquete_id, info in freefire_latam_prices.items():
        precio_compra = get_purchase_price('freefire_latam', paquete_id)
        precio_venta = info['precio']
        ganancia = precio_venta - precio_compra
        margen = (ganancia / precio_venta * 100) if precio_venta > 0 else 0
        
        freefire_latam_analysis.append({
            'juego': 'Free Fire LATAM',
            'paquete_id': paquete_id,
            'nombre': info['nombre'],
            'precio_compra': precio_compra,
            'precio_venta': precio_venta,
            'ganancia': ganancia,
            'margen_porcentaje': margen
        })
    
    # Análisis para Free Fire Global
    freefire_global_analysis = []
    freefire_global_prices = get_freefire_global_prices()
    for paquete_id, info in freefire_global_prices.items():
        precio_compra = get_purchase_price('freefire_global', paquete_id)
        precio_venta = info['precio']
        ganancia = precio_venta - precio_compra
        margen = (ganancia / precio_venta * 100) if precio_venta > 0 else 0
        
        freefire_global_analysis.append({
            'juego': 'Free Fire',
            'paquete_id': paquete_id,
            'nombre': info['nombre'],
            'precio_compra': precio_compra,
            'precio_venta': precio_venta,
            'ganancia': ganancia,
            'margen_porcentaje': margen
        })
    
    # Análisis para Blood Striker
    bloodstriker_analysis = []
    bloodstriker_prices = get_bloodstriker_prices()
    for paquete_id, info in bloodstriker_prices.items():
        precio_compra = get_purchase_price('bloodstriker', paquete_id)
        precio_venta = info['precio']
        ganancia = precio_venta - precio_compra
        margen = (ganancia / precio_venta * 100) if precio_venta > 0 else 0
        
        bloodstriker_analysis.append({
            'juego': 'Blood Striker',
            'paquete_id': paquete_id,
            'nombre': info['nombre'],
            'precio_compra': precio_compra,
            'precio_venta': precio_venta,
            'ganancia': ganancia,
            'margen_porcentaje': margen
        })
    
    conn.close()
    return freefire_latam_analysis + freefire_global_analysis + bloodstriker_analysis

def register_weekly_sale(juego, paquete_id, paquete_nombre, precio_venta, cantidad=1):
    """Registra una venta en las estadísticas diarias (corregido para resetear a las 12 AM)"""
    from datetime import datetime
    import pytz
    
    conn = get_db_connection()
    
    # Obtener precio de compra
    precio_compra = get_purchase_price(juego, paquete_id)
    ganancia_unitaria = precio_venta - precio_compra
    ganancia_total = ganancia_unitaria * cantidad
    
    # Usar zona horaria de Venezuela para calcular el día correcto
    venezuela_tz = pytz.timezone('America/Caracas')
    now_venezuela = datetime.now(venezuela_tz)
    
    # Calcular día del año (formato: YYYY-MM-DD) - resetea a las 12:00 AM
    dia_year = now_venezuela.strftime('%Y-%m-%d')
    
    # Verificar si ya existe un registro para este día y paquete
    existing = conn.execute('''
        SELECT id, cantidad_vendida, ganancia_total FROM ventas_semanales 
        WHERE juego = ? AND paquete_id = ? AND semana_year = ?
    ''', (juego, paquete_id, dia_year)).fetchone()
    
    if existing:
        # Actualizar registro existente
        nueva_cantidad = existing['cantidad_vendida'] + cantidad
        nueva_ganancia_total = existing['ganancia_total'] + ganancia_total
        
        conn.execute('''
            UPDATE ventas_semanales 
            SET cantidad_vendida = ?, ganancia_total = ?, fecha_venta = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (nueva_cantidad, nueva_ganancia_total, existing['id']))
    else:
        # Crear nuevo registro
        conn.execute('''
            INSERT INTO ventas_semanales 
            (juego, paquete_id, paquete_nombre, precio_venta, precio_compra, 
             ganancia_unitaria, cantidad_vendida, ganancia_total, semana_year)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (juego, paquete_id, paquete_nombre, precio_venta, precio_compra, 
              ganancia_unitaria, cantidad, ganancia_total, dia_year))
    
    conn.commit()
    conn.close()

def get_weekly_sales_stats():
    """Obtiene estadísticas de ventas del día actual (corregido para usar días)"""
    from datetime import datetime
    import pytz
    
    # Usar zona horaria de Venezuela para calcular el día correcto
    venezuela_tz = pytz.timezone('America/Caracas')
    now_venezuela = datetime.now(venezuela_tz)
    
    # Calcular día actual (formato: YYYY-MM-DD) - resetea a las 12:00 AM
    dia_actual = now_venezuela.strftime('%Y-%m-%d')
    
    conn = get_db_connection()
    
    # Estadísticas por juego
    stats_by_game = conn.execute('''
        SELECT juego, 
               SUM(cantidad_vendida) as total_unidades,
               SUM(ganancia_total) as ganancia_total_juego,
               COUNT(DISTINCT paquete_id) as paquetes_diferentes
        FROM ventas_semanales 
        WHERE semana_year = ?
        GROUP BY juego
        ORDER BY ganancia_total_juego DESC
    ''', (dia_actual,)).fetchall()
    
    # Estadísticas por paquete
    stats_by_package = conn.execute('''
        SELECT juego, paquete_nombre, precio_venta, precio_compra,
               cantidad_vendida, ganancia_unitaria, ganancia_total
        FROM ventas_semanales 
        WHERE semana_year = ?
        ORDER BY ganancia_total DESC
    ''', (dia_actual,)).fetchall()
    
    # Totales generales
    totals = conn.execute('''
        SELECT SUM(cantidad_vendida) as total_unidades_vendidas,
               SUM(ganancia_total) as ganancia_total_semana,
               SUM(precio_venta * cantidad_vendida) as ingresos_totales,
               SUM(precio_compra * cantidad_vendida) as costos_totales
        FROM ventas_semanales 
        WHERE semana_year = ?
    ''', (dia_actual,)).fetchone()
    
    conn.close()
    
    return {
        'semana_actual': dia_actual,
        'stats_by_game': stats_by_game,
        'stats_by_package': stats_by_package,
        'totals': totals
    }

def clean_old_weekly_sales():
    """Limpia las ventas semanales antiguas (mantiene solo las últimas 4 semanas)"""
    from datetime import datetime, timedelta
    
    conn = get_db_connection()
    
    try:
        # Calcular fecha límite (4 semanas atrás)
        fecha_limite = datetime.now() - timedelta(weeks=4)
        year_limite, week_limite, _ = fecha_limite.isocalendar()
        semana_limite = f"{year_limite}-{week_limite:02d}"
        
        # Obtener todas las semanas existentes y filtrar las que son más antiguas
        all_weeks = conn.execute('''
            SELECT DISTINCT semana_year FROM ventas_semanales
        ''').fetchall()
        
        weeks_to_delete = []
        for week_row in all_weeks:
            week_str = week_row['semana_year']
            try:
                # Parsear la semana (formato YYYY-WW)
                year_str, week_str_num = week_str.split('-')
                year = int(year_str)
                week = int(week_str_num)
                
                # Comparar con la fecha límite
                if year < year_limite or (year == year_limite and week < week_limite):
                    weeks_to_delete.append(week_row['semana_year'])
            except (ValueError, IndexError):
                # Si hay un formato inválido, eliminar ese registro también
                weeks_to_delete.append(week_row['semana_year'])
        
        # Eliminar registros antiguos
        deleted_count = 0
        for week_to_delete in weeks_to_delete:
            count = conn.execute('''
                DELETE FROM ventas_semanales 
                WHERE semana_year = ?
            ''', (week_to_delete,)).rowcount
            deleted_count += count
        
        conn.commit()
        return deleted_count
        
    except Exception as e:
        conn.rollback()
        print(f"Error en clean_old_weekly_sales: {str(e)}")
        return 0
    finally:
        conn.close()

def clean_old_transactions():
    """Limpia transacciones antiguas manteniendo solo las del último mes (mejorado)"""
    from datetime import datetime, timedelta
    
    # Verificar si ya se ejecutó la limpieza hoy
    last_cleanup_file = 'last_cleanup.txt'
    today = datetime.now().strftime('%Y-%m-%d')
    
    try:
        if os.path.exists(last_cleanup_file):
            with open(last_cleanup_file, 'r') as f:
                last_cleanup_date = f.read().strip()
            
            if last_cleanup_date == today:
                # Ya se ejecutó la limpieza hoy, no hacer nada
                return 0
    except:
        pass  # Si hay error leyendo el archivo, continuar con la limpieza
    
    conn = get_db_connection()
    
    try:
        # Calcular fecha límite (1 MES atrás en lugar de 1 semana)
        fecha_limite = datetime.now() - timedelta(days=30)  # 30 días = 1 mes
        fecha_limite_str = fecha_limite.strftime('%Y-%m-%d %H:%M:%S')
        
        # Eliminar transacciones normales más antiguas de 1 mes
        deleted_normal = conn.execute('''
            DELETE FROM transacciones 
            WHERE fecha < ?
        ''', (fecha_limite_str,)).rowcount
        
        # Eliminar transacciones de Blood Striker más antiguas de 1 mes (excepto pendientes)
        deleted_bs = conn.execute('''
            DELETE FROM transacciones_bloodstriker 
            WHERE fecha < ? AND estado != 'pendiente'
        ''', (fecha_limite_str,)).rowcount
        
        conn.commit()
        
        total_deleted = deleted_normal + deleted_bs
        if total_deleted > 0:
            print(f"🧹 Limpieza automática diaria: {total_deleted} transacciones antiguas eliminadas ({deleted_normal} normales, {deleted_bs} Blood Striker)")
        
        # Guardar fecha de última limpieza
        try:
            with open(last_cleanup_file, 'w') as f:
                f.write(today)
        except:
            pass  # Si no se puede escribir el archivo, no es crítico
        
        return total_deleted
        
    except Exception as e:
        conn.rollback()
        print(f"Error en clean_old_transactions: {str(e)}")
        return 0
    finally:
        conn.close()

def reset_all_weekly_sales():
    """Resetea TODAS las estadísticas de ventas semanales (elimina todos los registros)"""
    conn = get_db_connection()
    
    try:
        # Contar registros antes de eliminar
        total_count = conn.execute('SELECT COUNT(*) FROM ventas_semanales').fetchone()[0]
        
        # Eliminar todos los registros
        conn.execute('DELETE FROM ventas_semanales')
        conn.commit()
        
        return total_count
        
    except Exception as e:
        conn.rollback()
        print(f"Error en reset_all_weekly_sales: {str(e)}")
        return 0
    finally:
        conn.close()

# Funciones para Free Fire Global (nuevo juego)
def add_pin_freefire_global(monto_id, pin_codigo):
    """Añade un pin de Free Fire Global al stock"""
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO pines_freefire_global (monto_id, pin_codigo)
        VALUES (?, ?)
    ''', (monto_id, pin_codigo))
    conn.commit()
    conn.close()

def add_pins_batch_freefire_global(monto_id, pins_list):
    """Añade múltiples pines de Free Fire Global al stock en lote"""
    conn = get_db_connection()
    try:
        for pin_codigo in pins_list:
            pin_codigo = pin_codigo.strip()
            if pin_codigo:  # Solo agregar si el pin no está vacío
                conn.execute('''
                    INSERT INTO pines_freefire_global (monto_id, pin_codigo)
                    VALUES (?, ?)
                ''', (monto_id, pin_codigo))
        conn.commit()
        return len([p for p in pins_list if p.strip()])  # Retornar cantidad agregada
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_pin_stock_freefire_global():
    """Obtiene el stock de pines de Free Fire Global por monto_id"""
    conn = get_db_connection()
    stock = {}
    for i in range(1, 7):  # monto_id del 1 al 6 para Free Fire Global
        count = conn.execute('''
            SELECT COUNT(*) FROM pines_freefire_global 
            WHERE monto_id = ? AND usado = FALSE
        ''', (i,)).fetchone()[0]
        stock[i] = count
    conn.close()
    return stock

def get_available_pin_freefire_global(monto_id):
    """Obtiene un pin disponible de Free Fire Global para el monto especificado y lo elimina"""
    conn = get_db_connection()
    pin = conn.execute('''
        SELECT * FROM pines_freefire_global 
        WHERE monto_id = ? AND usado = FALSE 
        LIMIT 1
    ''', (monto_id,)).fetchone()
    
    if pin:
        # Eliminar el pin de la base de datos
        conn.execute('''
            DELETE FROM pines_freefire_global 
            WHERE id = ?
        ''', (pin['id'],))
        conn.commit()
    
    conn.close()
    return pin

def get_freefire_global_prices():
    """Obtiene información de paquetes de Free Fire Global con precios dinámicos"""
    conn = get_db_connection()
    packages = conn.execute('''
        SELECT id, nombre, precio, descripcion 
        FROM precios_freefire_global 
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

def get_freefire_global_price_by_id(monto_id):
    """Obtiene el precio de un paquete específico de Free Fire Global"""
    conn = get_db_connection()
    price = conn.execute('''
        SELECT precio FROM precios_freefire_global 
        WHERE id = ? AND activo = TRUE
    ''', (monto_id,)).fetchone()
    conn.close()
    return price['precio'] if price else 0

def update_freefire_global_price(package_id, new_price):
    """Actualiza el precio de un paquete de Free Fire Global"""
    conn = get_db_connection_optimized()
    try:
        conn.execute('''
            UPDATE precios_freefire_global 
            SET precio = ?, fecha_actualizacion = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (new_price, package_id))
        conn.commit()
        # Limpiar cache después de actualizar precios
        clear_price_cache()
    finally:
        return_db_connection(conn)

def update_freefire_global_name(package_id, new_name):
    """Actualiza el nombre de un paquete de Free Fire Global"""
    conn = get_db_connection_optimized()
    try:
        conn.execute('''
            UPDATE precios_freefire_global 
            SET nombre = ?, fecha_actualizacion = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (new_name, package_id))
        conn.commit()
        # Limpiar cache después de actualizar nombres
        clear_price_cache()
    finally:
        return_db_connection(conn)

def get_all_freefire_global_prices():
    """Obtiene todos los precios de paquetes de Free Fire Global"""
    conn = get_db_connection()
    prices = conn.execute('''
        SELECT * FROM precios_freefire_global 
        ORDER BY id
    ''').fetchall()
    conn.close()
    return prices

# Rutas para Free Fire Global (nuevo juego)
@app.route('/juego/freefire')
def freefire():
    if 'usuario' not in session:
        return redirect('/auth')
    
    # Actualizar saldo desde la base de datos
    user_id = session.get('user_db_id')
    if user_id:
        conn = get_db_connection()
        user = conn.execute('SELECT saldo FROM usuarios WHERE id = ?', (user_id,)).fetchone()
        if user:
            session['saldo'] = user['saldo']
        conn.close()
    
    # Obtener precios dinámicos de Free Fire Global
    prices = get_freefire_global_prices()
    
    # Verificar si hay una compra exitosa para mostrar (solo una vez)
    compra_exitosa = False
    compra_data = {}
    
    # Solo mostrar compra exitosa si viene del redirect POST y hay datos en sesión
    if request.args.get('compra') == 'exitosa' and 'compra_freefire_global_exitosa' in session:
        compra_exitosa = True
        compra_data = session.pop('compra_freefire_global_exitosa')  # Remover después de usar
    
    return render_template('freefire.html', 
                         user_id=session.get('id', '00000'),
                         balance=session.get('saldo', 0),
                         prices=prices,
                         compra_exitosa=compra_exitosa,
                         **compra_data)

@app.route('/validar/freefire', methods=['POST'])
def validar_freefire():
    if 'usuario' not in session:
        return redirect('/auth')
    
    monto_id = request.form.get('monto')
    cantidad = request.form.get('cantidad', '1')
    
    if not monto_id:
        flash('Por favor selecciona un paquete', 'error')
        return redirect('/juego/freefire')
    
    try:
        monto_id = int(monto_id)
        cantidad = int(cantidad)
        
        # Validar cantidad (entre 1 y 5)
        if cantidad < 1 or cantidad > 5:
            flash('La cantidad debe estar entre 1 y 5 pines', 'error')
            return redirect('/juego/freefire')
    except ValueError:
        flash('Datos inválidos', 'error')
        return redirect('/juego/freefire')
    
    user_id = session.get('user_db_id')
    is_admin = session.get('is_admin', False)
    
    # Obtener precio dinámico de la base de datos
    precio_unitario = get_freefire_global_price_by_id(monto_id)
    precio_total = precio_unitario * cantidad
    
    # Obtener información del paquete usando cache
    packages_info = get_freefire_global_prices_cached()
    package_info = packages_info.get(monto_id, {})
    
    paquete_nombre = f"{package_info.get('nombre', 'Paquete')} x{cantidad}" if cantidad > 1 else package_info.get('nombre', 'Paquete')
    
    if precio_unitario == 0:
        flash('Paquete no encontrado o inactivo', 'error')
        return redirect('/juego/freefire')
    
    saldo_actual = session.get('saldo', 0)
    
    # Solo verificar saldo para usuarios normales, admin puede comprar sin saldo
    if not is_admin and saldo_actual < precio_total:
        flash(f'Saldo insuficiente. Necesitas ${precio_total:.2f} pero tienes ${saldo_actual:.2f}', 'error')
        return redirect('/juego/freefire')
    
    # Verificar stock local disponible para la cantidad solicitada
    conn = get_db_connection()
    stock_disponible = conn.execute('''
        SELECT COUNT(*) FROM pines_freefire_global 
        WHERE monto_id = ? AND usado = FALSE
    ''', (monto_id,)).fetchone()[0]
    conn.close()
    
    if stock_disponible < cantidad:
        flash(f'Stock insuficiente. Solo hay {stock_disponible} pines disponibles para este paquete.', 'error')
        return redirect('/juego/freefire')
    
    # Obtener los pines necesarios
    pines_obtenidos = []
    for i in range(cantidad):
        pin_disponible = get_available_pin_freefire_global(monto_id)
        if pin_disponible:
            pines_obtenidos.append(pin_disponible['pin_codigo'])
        else:
            # Si no se pueden obtener todos los pines, devolver error
            flash('Error al obtener todos los pines solicitados.', 'error')
            return redirect('/juego/freefire')
    
    # Generar datos de la transacción
    import random
    import string
    numero_control = ''.join(random.choices(string.digits, k=10))
    transaccion_id = 'FFG-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    # Procesar la transacción
    conn = get_db_connection()
    try:
        # Solo actualizar saldo si no es admin
        if not is_admin:
            conn.execute('UPDATE usuarios SET saldo = saldo - ? WHERE id = ?', (precio_total, user_id))
        
        # Registrar la transacción
        pines_texto = '\n'.join(pines_obtenidos)
        
        # Para admin, registrar con monto negativo pero agregar etiqueta [ADMIN]
        if is_admin:
            pines_texto = f"[ADMIN - PRUEBA/GESTIÓN]\n{pines_texto}"
            monto_transaccion = -precio_total  # Registrar monto real para mostrar en historial
        else:
            monto_transaccion = -precio_total
        
        conn.execute('''
            INSERT INTO transacciones (usuario_id, numero_control, pin, transaccion_id, monto)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, numero_control, pines_texto, transaccion_id, monto_transaccion))
        
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
        
    except Exception as e:
        conn.rollback()
        flash('Error al procesar la transacción. Intente nuevamente.', 'error')
        return redirect('/juego/freefire')
    finally:
        conn.close()
    
    # Actualizar saldo en sesión solo si no es admin
    if not is_admin:
        session['saldo'] = saldo_actual - precio_total
    
    # Registrar venta en estadísticas semanales (solo para usuarios normales)
    if not is_admin:
        register_weekly_sale('freefire_global', monto_id, package_info.get('nombre', 'Paquete'), precio_unitario, cantidad)
    
    # Guardar datos de la compra en la sesión para mostrar después del redirect
    if cantidad == 1:
        # Para un solo pin
        session['compra_freefire_global_exitosa'] = {
            'paquete_nombre': paquete_nombre,
            'monto_compra': precio_total,
            'numero_control': numero_control,
            'pin': pines_obtenidos[0],
            'transaccion_id': transaccion_id
        }
    else:
        # Para múltiples pines
        session['compra_freefire_global_exitosa'] = {
            'paquete_nombre': paquete_nombre,
            'monto_compra': precio_total,
            'numero_control': numero_control,
            'pines_list': pines_obtenidos,
            'transaccion_id': transaccion_id,
            'cantidad_comprada': cantidad
        }
    
    # Redirect para evitar reenvío del formulario (patrón POST-Redirect-GET)
    return redirect('/juego/freefire?compra=exitosa')

@app.route('/dashboard')
def dashboard():
    """Dashboard con filtros de fecha y estadísticas - Accesible para usuarios y admin"""
    if 'usuario' not in session:
        return redirect('/auth')
    
    is_admin = session.get('is_admin', False)
    
    user_id = session.get('user_db_id')
    
    # Para admin, mostrar estadísticas globales
    if is_admin:
        user_id = None  # Admin ve todas las transacciones
    elif not user_id:
        flash('Error al acceder al dashboard', 'error')
        return redirect('/')
    
    # Obtener parámetros de filtro de fecha
    fecha_inicio = request.args.get('inicio', '')
    fecha_fin = request.args.get('fin', '')
    preset = request.args.get('preset', 'hoy')  # Por defecto "hoy"
    
    # Manejar presets de fecha
    from datetime import datetime, timedelta
    today = datetime.now()
    
    if preset == 'hoy' or (not preset and not fecha_inicio and not fecha_fin):
        # Por defecto siempre mostrar "hoy"
        fecha_inicio = today.strftime('%Y-%m-%d')
        fecha_fin = today.strftime('%Y-%m-%d')
        preset = 'hoy'  # Asegurar que el preset esté marcado como activo
    elif preset == 'ayer':
        yesterday = today - timedelta(days=1)
        fecha_inicio = yesterday.strftime('%Y-%m-%d')
        fecha_fin = yesterday.strftime('%Y-%m-%d')
    elif preset == 'antes_ayer':
        day_before_yesterday = today - timedelta(days=2)
        fecha_inicio = day_before_yesterday.strftime('%Y-%m-%d')
        fecha_fin = day_before_yesterday.strftime('%Y-%m-%d')
    elif not fecha_inicio or not fecha_fin:
        # Si no se proporcionan fechas válidas, usar "hoy" por defecto
        fecha_inicio = today.strftime('%Y-%m-%d')
        fecha_fin = today.strftime('%Y-%m-%d')
        preset = 'hoy'
    
    # Actualizar saldo desde la base de datos y obtener transacciones
    conn = get_db_connection()
    
    if is_admin:
        # Admin ve estadísticas globales
        user = None
        
        # Obtener todas las transacciones filtradas por fecha
        transacciones_filtradas = conn.execute('''
            SELECT t.*, u.nombre, u.apellido
            FROM transacciones t
            JOIN usuarios u ON t.usuario_id = u.id
            WHERE DATE(t.fecha) BETWEEN ? AND ?
            ORDER BY t.fecha DESC
        ''', (fecha_inicio, fecha_fin)).fetchall()
        
        # Obtener todas las transacciones de Blood Striker filtradas por fecha
        transacciones_bs = conn.execute('''
            SELECT bs.*, u.nombre, u.apellido, p.nombre as paquete_nombre
            FROM transacciones_bloodstriker bs
            JOIN usuarios u ON bs.usuario_id = u.id
            JOIN precios_bloodstriker p ON bs.paquete_id = p.id
            WHERE DATE(bs.fecha) BETWEEN ? AND ? AND bs.estado = 'aprobado'
            ORDER BY bs.fecha DESC
        ''', (fecha_inicio, fecha_fin)).fetchall()
        
        # Obtener los 2 usuarios con más compras del mes actual (no del período seleccionado)
        from datetime import datetime
        current_month = datetime.now().strftime('%Y-%m')
        
        top_users = conn.execute('''
            SELECT u.nombre, u.apellido, u.correo, COUNT(*) as total_compras, SUM(ABS(t.monto)) as monto_total
            FROM transacciones t
            JOIN usuarios u ON t.usuario_id = u.id
            WHERE strftime('%Y-%m', t.fecha) = ?
            GROUP BY u.id, u.nombre, u.apellido, u.correo
            ORDER BY total_compras DESC, monto_total DESC
            LIMIT 2
        ''', (current_month,)).fetchall()
        
    else:
        # Usuario normal ve solo sus datos
        user = conn.execute('SELECT * FROM usuarios WHERE id = ?', (user_id,)).fetchone()
        if user:
            session['saldo'] = user['saldo']
        
        # Obtener transacciones del usuario filtradas por fecha
        transacciones_filtradas = conn.execute('''
            SELECT t.*, u.nombre, u.apellido
            FROM transacciones t
            JOIN usuarios u ON t.usuario_id = u.id
            WHERE t.usuario_id = ? AND DATE(t.fecha) BETWEEN ? AND ?
            ORDER BY t.fecha DESC
        ''', (user_id, fecha_inicio, fecha_fin)).fetchall()
        
        # Obtener transacciones de Blood Striker del usuario filtradas por fecha
        transacciones_bs = conn.execute('''
            SELECT bs.*, u.nombre, u.apellido, p.nombre as paquete_nombre
            FROM transacciones_bloodstriker bs
            JOIN usuarios u ON bs.usuario_id = u.id
            JOIN precios_bloodstriker p ON bs.paquete_id = p.id
            WHERE bs.usuario_id = ? AND DATE(bs.fecha) BETWEEN ? AND ? AND bs.estado = 'aprobado'
            ORDER BY bs.fecha DESC
        ''', (user_id, fecha_inicio, fecha_fin)).fetchall()
        
        top_users = []  # Los usuarios normales no ven top users
    
    conn.close()
    
    # Procesar transacciones normales
    transacciones_procesadas = []
    monto_total = 0
    
    # Obtener información de paquetes para mostrar nombres correctos
    packages_info = get_package_info_with_prices()
    bloodstriker_packages_info = get_bloodstriker_prices()
    freefire_global_packages_info = get_freefire_global_prices()
    
    for transaction in transacciones_filtradas:
        transaction_dict = dict(transaction)
        monto = abs(transaction['monto'])
        monto_total += monto
        
        # Buscar el paquete que coincida con el monto
        paquete_encontrado = False
        
        # Buscar en Free Fire LATAM
        for package_id, package_info in packages_info.items():
            if abs(monto - package_info['precio']) < 0.01:
                transaction_dict['paquete'] = package_info['nombre']
                paquete_encontrado = True
                break
        
        # Si no se encuentra en Free Fire LATAM, buscar en Free Fire Global
        if not paquete_encontrado:
            for package_id, package_info in freefire_global_packages_info.items():
                if abs(monto - package_info['precio']) < 0.01:
                    transaction_dict['paquete'] = package_info['nombre']
                    paquete_encontrado = True
                    break
        
        # Si no se encuentra en Free Fire Global, buscar en Blood Striker
        if not paquete_encontrado:
            for package_id, package_info in bloodstriker_packages_info.items():
                if abs(monto - package_info['precio']) < 0.01:
                    transaction_dict['paquete'] = package_info['nombre']
                    paquete_encontrado = True
                    break
        
        # Si no se encuentra coincidencia exacta, usar el nombre por defecto
        if not paquete_encontrado:
            transaction_dict['paquete'] = f"Paquete ${monto:.2f}"
        
        # Convertir fecha a zona horaria de Venezuela
        transaction_dict['fecha'] = convert_to_venezuela_time(transaction_dict['fecha'])
        transaction_dict['monto'] = monto
        
        transacciones_procesadas.append(transaction_dict)
    
    # Procesar transacciones de Blood Striker aprobadas
    for bs_transaction in transacciones_bs:
        transaction_dict = {
            'fecha': convert_to_venezuela_time(bs_transaction['fecha']),
            'monto': abs(bs_transaction['monto']),
            'paquete': bs_transaction['paquete_nombre'],
            'numero_control': bs_transaction['numero_control'],
            'transaccion_id': bs_transaction['transaccion_id'],
            'pin': f"ID: {bs_transaction['player_id']}",
            'nombre': bs_transaction['nombre'],
            'apellido': bs_transaction['apellido'],
            'is_bloodstriker': True
        }
        monto_total += transaction_dict['monto']
        transacciones_procesadas.append(transaction_dict)
    
    # Ordenar todas las transacciones por fecha
    transacciones_procesadas.sort(key=lambda x: x['fecha'], reverse=True)
    
    # Calcular estadísticas
    total_transacciones = len(transacciones_procesadas)
    
    # Calcular días analizados
    try:
        fecha_inicio_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d')
        fecha_fin_dt = datetime.strptime(fecha_fin, '%Y-%m-%d')
        dias_analizados = (fecha_fin_dt - fecha_inicio_dt).days + 1
    except:
        dias_analizados = 1
    
    # Estadísticas por juego
    stats_por_juego = {}
    for transaction in transacciones_procesadas:
        # Determinar el juego basado en el paquete o si es Blood Striker
        if transaction.get('is_bloodstriker'):
            juego = 'Blood Striker'
        elif '💎' in transaction['paquete']:
            if 'Tarjeta' in transaction['paquete']:
                juego = 'Free Fire LATAM'
            else:
                # Distinguir entre Free Fire LATAM y Global por el formato del nombre
                if any(x in transaction['paquete'] for x in ['110 💎', '341 💎', '572 💎', '1.166 💎', '2.376 💎', '6.138 💎']):
                    juego = 'Free Fire LATAM'
                else:
                    juego = 'Free Fire Global'
        elif '🪙' in transaction['paquete']:
            juego = 'Blood Striker'
        else:
            juego = 'Otros'
        
        if juego not in stats_por_juego:
            stats_por_juego[juego] = {'cantidad': 0, 'monto': 0}
        
        stats_por_juego[juego]['cantidad'] += 1
        stats_por_juego[juego]['monto'] += transaction['monto']
    
    # Obtener contador de notificaciones de cartera para usuarios normales
    wallet_notification_count = 0
    if not is_admin and user_id:
        wallet_notification_count = get_unread_wallet_credits_count(user_id)
    
    # Obtener contador de notificaciones de noticias
    news_notification_count = 0
    if user_id:
        news_notification_count = get_unread_news_count(user_id)
    
    return render_template('dashboard.html', 
                         user=user,
                         transacciones=transacciones_procesadas,
                         monto_total=monto_total,
                         total_transacciones=total_transacciones,
                         stats_por_juego=stats_por_juego,
                         dias_analizados=dias_analizados,
                         inicio=fecha_inicio,
                         fin=fecha_fin,
                         user_id=session.get('id', '00000'),
                         balance=session.get('saldo', 0),
                         is_admin=is_admin,
                         top_users=top_users,
                         wallet_notification_count=wallet_notification_count,
                         news_notification_count=news_notification_count)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/auth')

# ============= API SIMPLE DE CONEXIÓN =============

@app.route('/api.php', methods=['GET'])
def api_simple_endpoint():
    """
    API Simple de Conexión para Revendedores51
    
    Formato: /api.php?action=recarga&usuario=email&clave=password&tipo=recargaPinFreefire&monto=1&numero=1
    
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
        
        # Generar datos de la transacción
        numero_control = ''.join(random.choices(string.digits, k=10))
        transaccion_id = 'API-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        conn.execute('''
            INSERT INTO transacciones (usuario_id, numero_control, pin, transaccion_id, monto)
            VALUES (?, ?, ?, ?, ?)
        ''', (user['id'], numero_control, pins_texto, transaccion_id, -precio_total))
        
        # Limitar transacciones a 30 por usuario
        conn.execute('''
            DELETE FROM transacciones 
            WHERE usuario_id = ? AND id NOT IN (
                SELECT id FROM transacciones 
                WHERE usuario_id = ? 
                ORDER BY fecha DESC 
                LIMIT 30
            )
        ''', (user['id'], user['id']))
        
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
                'numero_control': numero_control,
                'transaccion_id': transaccion_id,
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
def api_simple_endpoint_post():
    """Endpoint POST para la API simple (redirige al GET)"""
    return jsonify({
        'status': 'error',
        'code': '405',
        'message': 'Usar método GET con parámetros en la URL'
    }), 405

if __name__ == '__main__':
    app.run(debug=True)
