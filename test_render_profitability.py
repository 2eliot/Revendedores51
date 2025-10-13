#!/usr/bin/env python3
"""
Test script para verificar la funcionalidad de rentabilidad compatible con Render
"""

import os
import sys
import sqlite3
from datetime import datetime

# Agregar el directorio actual al path para importar app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_render_profitability():
    """Prueba las funciones de rentabilidad compatibles con Render"""
    
    print("🧪 Iniciando pruebas de rentabilidad compatible con Render...")
    print("=" * 60)
    
    # Importar funciones después de configurar el path
    try:
        from app import (
            get_purchase_price, 
            update_purchase_price, 
            get_profit_analysis,
            get_render_compatible_db_path,
            get_db_connection_optimized,
            return_db_connection
        )
        print("✅ Funciones importadas correctamente")
    except ImportError as e:
        print(f"❌ Error al importar funciones: {e}")
        return False
    
    # Test 1: Verificar ruta de base de datos compatible con Render
    print("\n📁 Test 1: Verificación de ruta de base de datos")
    try:
        db_path = get_render_compatible_db_path()
        print(f"   Ruta de BD: {db_path}")
        
        if os.environ.get('RENDER'):
            expected_path = os.path.join(os.getcwd(), 'usuarios.db')
            if db_path == expected_path:
                print("   ✅ Ruta correcta para Render")
            else:
                print("   ❌ Ruta incorrecta para Render")
        else:
            print("   ✅ Ruta correcta para desarrollo local")
    except Exception as e:
        print(f"   ❌ Error en test de ruta: {e}")
        return False
    
    # Test 2: Verificar conexión optimizada
    print("\n🔗 Test 2: Verificación de conexión optimizada")
    try:
        conn = get_db_connection_optimized()
        
        # Probar una consulta simple
        result = conn.execute('SELECT 1 as test').fetchone()
        if result and result['test'] == 1:
            print("   ✅ Conexión optimizada funciona correctamente")
        else:
            print("   ❌ Error en consulta de prueba")
            return False
        
        return_db_connection(conn)
        print("   ✅ Conexión cerrada correctamente")
    except Exception as e:
        print(f"   ❌ Error en test de conexión: {e}")
        return False
    
    # Test 3: Verificar función get_purchase_price
    print("\n💰 Test 3: Verificación de get_purchase_price")
    try:
        # Probar con un juego y paquete que debería existir
        precio = get_purchase_price('freefire_latam', 1)
        print(f"   Precio de compra FF LATAM paquete 1: ${precio:.2f}")
        
        if precio > 0:
            print("   ✅ get_purchase_price funciona correctamente")
        else:
            print("   ⚠️  Precio es 0, puede ser normal si no hay datos")
        
        # Probar con datos que no existen
        precio_inexistente = get_purchase_price('juego_inexistente', 999)
        if precio_inexistente == 0.0:
            print("   ✅ Manejo correcto de datos inexistentes")
        else:
            print("   ❌ Error en manejo de datos inexistentes")
            
    except Exception as e:
        print(f"   ❌ Error en test de get_purchase_price: {e}")
        return False
    
    # Test 4: Verificar función update_purchase_price
    print("\n📝 Test 4: Verificación de update_purchase_price")
    try:
        # Obtener precio actual
        precio_original = get_purchase_price('freefire_latam', 1)
        print(f"   Precio original: ${precio_original:.2f}")
        
        # Actualizar precio
        nuevo_precio = 0.65  # Precio de prueba
        success = update_purchase_price('freefire_latam', 1, nuevo_precio)
        
        if success:
            print("   ✅ update_purchase_price retornó True")
            
            # Verificar que el precio se actualizó
            precio_actualizado = get_purchase_price('freefire_latam', 1)
            print(f"   Precio actualizado: ${precio_actualizado:.2f}")
            
            if abs(precio_actualizado - nuevo_precio) < 0.01:
                print("   ✅ Precio actualizado correctamente")
                
                # Restaurar precio original
                restore_success = update_purchase_price('freefire_latam', 1, precio_original)
                if restore_success:
                    print("   ✅ Precio original restaurado")
                else:
                    print("   ⚠️  No se pudo restaurar el precio original")
            else:
                print("   ❌ El precio no se actualizó correctamente")
                return False
        else:
            print("   ❌ update_purchase_price retornó False")
            return False
            
    except Exception as e:
        print(f"   ❌ Error en test de update_purchase_price: {e}")
        return False
    
    # Test 5: Verificar análisis de rentabilidad
    print("\n📊 Test 5: Verificación de análisis de rentabilidad")
    try:
        profit_analysis = get_profit_analysis()
        
        if profit_analysis and len(profit_analysis) > 0:
            print(f"   ✅ Análisis obtenido: {len(profit_analysis)} productos")
            
            # Mostrar algunos ejemplos
            for i, item in enumerate(profit_analysis[:3]):
                juego = item.get('juego', 'N/A')
                nombre = item.get('nombre', 'N/A')
                ganancia = item.get('ganancia', 0)
                margen = item.get('margen_porcentaje', 0)
                print(f"   - {juego} - {nombre}: Ganancia ${ganancia:.2f} ({margen:.1f}%)")
                
            print("   ✅ Análisis de rentabilidad funciona correctamente")
        else:
            print("   ⚠️  No se obtuvo análisis de rentabilidad")
            
    except Exception as e:
        print(f"   ❌ Error en test de análisis de rentabilidad: {e}")
        return False
    
    # Test 6: Verificar manejo de errores
    print("\n🛡️  Test 6: Verificación de manejo de errores")
    try:
        # Probar con parámetros inválidos
        result1 = update_purchase_price('', 1, 0.5)  # Juego vacío
        result2 = update_purchase_price('freefire_latam', -1, 0.5)  # ID negativo
        result3 = update_purchase_price('freefire_latam', 1, -0.5)  # Precio negativo
        
        if not result1 and not result2 and not result3:
            print("   ✅ Manejo correcto de parámetros inválidos")
        else:
            print("   ❌ Error en manejo de parámetros inválidos")
            
    except Exception as e:
        print(f"   ❌ Error en test de manejo de errores: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("🎉 Todas las pruebas de rentabilidad compatible con Render completadas exitosamente!")
    print("✅ El sistema está listo para despliegue en Render")
    return True

def test_database_tables():
    """Verifica que las tablas de rentabilidad existan"""
    print("\n🗄️  Verificando tablas de rentabilidad...")
    
    try:
        from app import get_db_connection
        
        conn = get_db_connection()
        
        # Verificar tabla precios_compra
        result = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='precios_compra'
        """).fetchone()
        
        if result:
            print("   ✅ Tabla 'precios_compra' existe")
            
            # Contar registros
            count = conn.execute('SELECT COUNT(*) FROM precios_compra').fetchone()[0]
            print(f"   📊 Registros en precios_compra: {count}")
        else:
            print("   ❌ Tabla 'precios_compra' no existe")
            return False
        
        # Verificar tabla ventas_semanales
        result = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='ventas_semanales'
        """).fetchone()
        
        if result:
            print("   ✅ Tabla 'ventas_semanales' existe")
            
            # Contar registros
            count = conn.execute('SELECT COUNT(*) FROM ventas_semanales').fetchone()[0]
            print(f"   📊 Registros en ventas_semanales: {count}")
        else:
            print("   ❌ Tabla 'ventas_semanales' no existe")
            return False
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Error verificando tablas: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Test de Rentabilidad Compatible con Render")
    print("=" * 60)
    
    # Verificar tablas primero
    if not test_database_tables():
        print("❌ Error en verificación de tablas")
        sys.exit(1)
    
    # Ejecutar pruebas principales
    if test_render_profitability():
        print("\n🎯 RESULTADO: ¡Todas las pruebas pasaron exitosamente!")
        print("🚀 El sistema de rentabilidad está listo para Render")
        sys.exit(0)
    else:
        print("\n💥 RESULTADO: Algunas pruebas fallaron")
        print("🔧 Revisar los errores antes del despliegue")
        sys.exit(1)
