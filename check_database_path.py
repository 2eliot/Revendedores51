#!/usr/bin/env python3
"""
Script para verificar la ruta de la base de datos
"""
import os
import sqlite3

def get_render_compatible_db_path():
    """Obtiene la ruta de la base de datos compatible con Render"""
    if os.environ.get('RENDER'):
        # En Render, usar directamente el directorio raíz del proyecto
        return 'usuarios.db'
    else:
        # En desarrollo local, permitir configuración personalizada
        return os.environ.get('DATABASE_PATH', 'usuarios.db')

def main():
    print("=== CONFIGURACIÓN DE BASE DE DATOS ===")
    print()
    
    # Verificar variables de entorno
    print("Variables de entorno:")
    print(f"  RENDER: {os.environ.get('RENDER', 'No configurado')}")
    print(f"  DATABASE_PATH: {os.environ.get('DATABASE_PATH', 'No configurado')}")
    print()
    
    # Obtener ruta de la base de datos
    db_path = get_render_compatible_db_path()
    print(f"Ruta de la base de datos: {db_path}")
    
    # Verificar si es ruta absoluta o relativa
    if os.path.isabs(db_path):
        print(f"Tipo: Ruta absoluta")
        full_path = db_path
    else:
        print(f"Tipo: Ruta relativa")
        full_path = os.path.abspath(db_path)
    
    print(f"Ruta completa: {full_path}")
    print()
    
    # Verificar si el archivo existe
    if os.path.exists(full_path):
        print("✅ El archivo de base de datos EXISTE")
        
        # Obtener información del archivo
        file_size = os.path.getsize(full_path)
        print(f"   Tamaño: {file_size} bytes ({file_size/1024:.2f} KB)")
        
        # Verificar si se puede conectar
        try:
            conn = sqlite3.connect(full_path)
            cursor = conn.cursor()
            
            # Listar tablas
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            print(f"   Tablas encontradas ({len(tables)}):")
            for table in tables:
                print(f"     - {table[0]}")
            
            conn.close()
            print("✅ Conexión a la base de datos EXITOSA")
            
        except Exception as e:
            print(f"❌ Error al conectar a la base de datos: {e}")
    else:
        print("❌ El archivo de base de datos NO EXISTE")
        print(f"   Se creará en: {full_path}")
    
    print()
    print("=== DIRECTORIO ACTUAL ===")
    print(f"Directorio de trabajo: {os.getcwd()}")
    print()
    
    # Listar archivos .db en el directorio actual
    print("Archivos .db en el directorio actual:")
    db_files = [f for f in os.listdir('.') if f.endswith('.db')]
    if db_files:
        for db_file in db_files:
            file_path = os.path.abspath(db_file)
            file_size = os.path.getsize(db_file)
            print(f"  - {db_file} ({file_size} bytes) -> {file_path}")
    else:
        print("  No se encontraron archivos .db")

if __name__ == '__main__':
    main()
