import sqlite3

DB_PATH = 'usuarios.db'

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Crear tabla de usuarios
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

# Crear tabla de transacciones
cursor.execute('''
CREATE TABLE IF NOT EXISTS transacciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER,
    monto REAL,
    tipo TEXT,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
)
''')

# Crear tabla de pines_freefire
cursor.execute('''
CREATE TABLE IF NOT EXISTS pines_freefire (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    monto_id INTEGER NOT NULL,
    pin_codigo TEXT NOT NULL,
    usado BOOLEAN DEFAULT FALSE,
    fecha_agregado DATETIME DEFAULT CURRENT_TIMESTAMP,
    fecha_usado DATETIME NULL,
    usuario_id INTEGER NULL
)
''')

# Crear tabla de creditos_billetera
cursor.execute('''
CREATE TABLE IF NOT EXISTS creditos_billetera (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER,
    monto REAL DEFAULT 0.0,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    visto BOOLEAN DEFAULT FALSE,
    FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
)
''')

conn.commit()
conn.close()

print('Base de datos usuarios.db inicializada correctamente.')
