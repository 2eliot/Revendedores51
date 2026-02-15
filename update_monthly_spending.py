"""
Helper function to update monthly user spending table.
This ensures top clients data persists even when old transactions are deleted.
"""
from datetime import datetime
import pytz

def update_monthly_spending(conn, usuario_id, monto_gastado):
    """
    Actualiza la tabla monthly_user_spending con el gasto de un usuario.
    Esta tabla persiste independientemente de la limpieza de transacciones.
    
    Args:
        conn: Conexión a la base de datos
        usuario_id: ID del usuario
        monto_gastado: Monto gastado (valor positivo)
    """
    try:
        # Usar zona horaria de Venezuela
        venezuela_tz = pytz.timezone('America/Caracas')
        now_venezuela = datetime.now(venezuela_tz)
        year_month = now_venezuela.strftime('%Y-%m')
        
        # Verificar si ya existe un registro para este usuario y mes
        existing = conn.execute('''
            SELECT total_spent, purchases_count 
            FROM monthly_user_spending 
            WHERE usuario_id = ? AND year_month = ?
        ''', (usuario_id, year_month)).fetchone()
        
        if existing:
            # Actualizar registro existente
            new_total = existing['total_spent'] + monto_gastado
            new_count = existing['purchases_count'] + 1
            
            conn.execute('''
                UPDATE monthly_user_spending 
                SET total_spent = ?, purchases_count = ?, updated_at = datetime('now')
                WHERE usuario_id = ? AND year_month = ?
            ''', (new_total, new_count, usuario_id, year_month))
        else:
            # Crear nuevo registro
            conn.execute('''
                INSERT INTO monthly_user_spending 
                (usuario_id, year_month, total_spent, purchases_count)
                VALUES (?, ?, ?, 1)
            ''', (usuario_id, year_month, monto_gastado))
    except Exception as e:
        # No fallar la transacción principal si esto falla
        print(f"Error updating monthly spending: {e}")
