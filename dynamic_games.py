"""
Sistema de Juegos Dinámicos — Blueprint Flask
Permite crear juegos vinculados a GamePoint desde el panel admin,
con auto-generación de página, menú, historial y sincronización de precios.
"""
import json
import os
import re
import secrets
from datetime import datetime, timedelta
from pg_compat import get_db_connection as _pg_get_conn, table_exists as _pg_table_exists
import time as time_module
import logging

from flask import Blueprint, jsonify, request, render_template, session, flash, redirect
from csrf_utils import csrf_protect

logger = logging.getLogger(__name__)

bp = Blueprint('dynamic_games', __name__)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_conn():
    return _pg_get_conn()


# ---------------------------------------------------------------------------
# Tasa de cambio para GamePoint (compartida entre Blood Strike y juegos dinámicos)
# ---------------------------------------------------------------------------

GP_MYR_RATE_KEY = 'gp_myr_to_usd_rate'  # legado (MYR -> USD)
GP_USD_TO_MYR_RATE_KEY = 'gp_usd_to_myr_rate'  # nuevo (USD -> MYR)
_GP_USD_TO_MYR_RATE_DEFAULT = 3.94


def get_gp_usd_to_myr_rate():
    """Lee la tasa USD→MYR desde BD (nuevo formato) con fallback compatible legado."""
    try:
        conn = _get_conn()
        row_new = conn.execute(
            'SELECT valor FROM configuracion_redeemer WHERE clave = ?', (GP_USD_TO_MYR_RATE_KEY,)
        ).fetchone()
        if row_new and row_new['valor']:
            conn.close()
            return float(row_new['valor'])

        # Compatibilidad con tasa anterior MYR->USD.
        row_old = conn.execute(
            'SELECT valor FROM configuracion_redeemer WHERE clave = ?', (GP_MYR_RATE_KEY,)
        ).fetchone()
        conn.close()
        if row_old and row_old['valor']:
            old_myr_to_usd = float(row_old['valor'])
            if old_myr_to_usd > 0:
                return round(1.0 / old_myr_to_usd, 6)
    except Exception:
        pass

    # Fallback env: preferir USD->MYR; si solo existe el legado, convertir.
    env_usd_to_myr = os.environ.get('BLOODSTRIKE_USD_TO_MYR_RATE')
    if env_usd_to_myr:
        try:
            parsed = float(env_usd_to_myr)
            if parsed > 0:
                return parsed
        except Exception:
            pass

    env_myr_to_usd = os.environ.get('BLOODSTRIKE_MYR_TO_USD_RATE')
    if env_myr_to_usd:
        try:
            parsed_old = float(env_myr_to_usd)
            if parsed_old > 0:
                return round(1.0 / parsed_old, 6)
        except Exception:
            pass

    return float(_GP_USD_TO_MYR_RATE_DEFAULT)


def get_gp_myr_rate():
    """Devuelve la tasa efectiva MYR→USD usada en cálculos: 1 / (USD→MYR)."""
    usd_to_myr = float(get_gp_usd_to_myr_rate())
    if usd_to_myr <= 0:
        usd_to_myr = float(_GP_USD_TO_MYR_RATE_DEFAULT)
    return 1.0 / usd_to_myr


def set_gp_usd_to_myr_rate(rate: float):
    """Guarda la tasa USD→MYR en la BD y actualiza el espejo legado MYR→USD."""
    myr_to_usd = 1.0 / float(rate)
    conn = _get_conn()
    conn.execute(
        "INSERT INTO configuracion_redeemer (clave, valor, fecha_actualizacion) "
        "VALUES (?, ?, datetime('now')) "
        "ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor, fecha_actualizacion = EXCLUDED.fecha_actualizacion",
        (GP_USD_TO_MYR_RATE_KEY, str(rate))
    )
    # Guardar también la clave anterior para compatibilidad con instancias viejas.
    conn.execute(
        "INSERT INTO configuracion_redeemer (clave, valor, fecha_actualizacion) "
        "VALUES (?, ?, datetime('now')) "
        "ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor, fecha_actualizacion = EXCLUDED.fecha_actualizacion",
        (GP_MYR_RATE_KEY, str(myr_to_usd))
    )
    conn.commit()
    conn.close()


def get_all_dynamic_games(only_active=False):
    conn = _get_conn()
    if only_active:
        rows = conn.execute('SELECT * FROM juegos_dinamicos WHERE activo = TRUE ORDER BY nombre').fetchall()
    else:
        rows = conn.execute('SELECT * FROM juegos_dinamicos ORDER BY nombre').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_dynamic_game_by_slug(slug):
    conn = _get_conn()
    row = conn.execute('SELECT * FROM juegos_dinamicos WHERE slug = ?', (slug,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_dynamic_game_by_id(game_id):
    conn = _get_conn()
    row = conn.execute('SELECT * FROM juegos_dinamicos WHERE id = ?', (game_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_dynamic_packages(game_id, only_active=False):
    conn = _get_conn()
    if only_active:
        rows = conn.execute(
            'SELECT * FROM paquetes_dinamicos WHERE juego_id = ? AND activo = TRUE ORDER BY orden, id',
            (game_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            'SELECT * FROM paquetes_dinamicos WHERE juego_id = ? ORDER BY orden, id',
            (game_id,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_dynamic_package_by_id(pkg_id):
    conn = _get_conn()
    row = conn.execute('SELECT * FROM paquetes_dinamicos WHERE id = ?', (pkg_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def parse_campos_config(game):
    """Parse the JSON campos_config from a game dict."""
    raw = game.get('campos_config', '{}') or '{}'
    try:
        return json.loads(raw)
    except Exception:
        return {}


def slugify(text):
    """Generate a URL-safe slug from text."""
    text = text.lower().strip()
    text = re.sub(r'[áàäâ]', 'a', text)
    text = re.sub(r'[éèëê]', 'e', text)
    text = re.sub(r'[íìïî]', 'i', text)
    text = re.sub(r'[óòöô]', 'o', text)
    text = re.sub(r'[úùüû]', 'u', text)
    text = re.sub(r'[ñ]', 'n', text)
    text = re.sub(r'[^a-z0-9]+', '-', text)
    text = text.strip('-')
    return text or 'juego'


# ---------------------------------------------------------------------------
# GamePoint helpers — import from app at runtime to avoid circular imports
# ---------------------------------------------------------------------------

def _gp_helpers():
    """Lazy import of GamePoint helper functions from app module."""
    import app as _app
    return (
        _app._gameclub_get_token,
        _app._gameclub_post,
        _app._gameclub_order_validate,
        _app._gameclub_order_create,
        _app._gameclub_order_inquiry,
    )


def _normalize_gamepoint_text(value):
    return re.sub(r'\s+', ' ', str(value or '').strip()).upper()


def _classify_gamepoint_inquiry(inquiry_data, serial_key='', is_gift_card=True):
    """Map an order/inquiry payload to success, failed or pending."""
    if _is_real_serial(serial_key):
        return 'success', ''

    data = inquiry_data or {}
    status_text = _normalize_gamepoint_text(data.get('status'))
    message_text = _normalize_gamepoint_text(data.get('message') or data.get('error'))
    combined = ' '.join(part for part in (status_text, message_text) if part)

    success_tokens = ('SUCCESS', 'COMPLETED', 'COMPLETE', 'APPROVED', 'DELIVERED', 'DONE')
    failure_tokens = ('FAIL', 'FAILED', 'ERROR', 'REJECT', 'REJECTED', 'DENIED', 'CANCEL', 'EXPIRE', 'INVALID')
    pending_tokens = ('PENDING', 'PROCESS', 'QUEUE', 'WAIT')

    if any(token in status_text for token in success_tokens):
        if is_gift_card:
            return 'pending', str(data.get('message') or data.get('status') or '').strip()
        return 'success', str(data.get('message') or data.get('status') or '').strip()

    if any(token in combined for token in failure_tokens):
        provider_note = str(data.get('message') or data.get('error') or data.get('status') or 'Error reportado por GamePoint').strip()
        return 'failed', provider_note

    if any(token in combined for token in pending_tokens):
        return 'pending', str(data.get('message') or data.get('status') or '').strip()

    if not is_gift_card and data.get('referenceno'):
        return 'success', str(data.get('message') or data.get('status') or '').strip()

    return 'pending', str(data.get('message') or data.get('status') or '').strip()


def _build_dynamic_pin_info(tx):
    serial_key = str(tx.get('pin_entregado') or '').strip()
    reference_no = str(tx.get('gamepoint_referenceno') or '').strip()
    estado = str(tx.get('estado') or '').strip().lower()
    notas = re.sub(r'\s+', ' ', str(tx.get('notas') or '').strip())

    if _is_real_serial(serial_key):
        pin_info = f"Código: {serial_key}"
        if reference_no:
            pin_info = f"{pin_info} - Ref: {reference_no}"
        return pin_info

    player_bits = [str(tx.get('player_id') or '').strip()]
    if str(tx.get('player_id2') or '').strip():
        player_bits.append(str(tx.get('player_id2') or '').strip())
    player_text = ' / '.join([bit for bit in player_bits if bit])
    detail_parts = []
    if player_text:
        detail_parts.append(f"ID: {player_text}")
    if str(tx.get('ingame_name') or '').strip():
        detail_parts.append(f"Jugador: {str(tx.get('ingame_name')).strip()}")
    if reference_no:
        detail_parts.append(f"Ref: {reference_no}")

    if estado in ('rechazado', 'error', 'fallida'):
        failure_text = notas or 'Recarga fallida'
        pin_info = f"❌ {failure_text}"
        if reference_no:
            pin_info = f"{pin_info} - Ref: {reference_no}"
        return pin_info

    if estado in ('pendiente', 'procesando'):
        pending_parts = ['⏳ Recarga en proceso']
        pending_parts.extend(detail_parts)
        return ' - '.join([part for part in pending_parts if part])

    if detail_parts:
        return ' - '.join(detail_parts)

    if reference_no:
        return f"Ref: {reference_no}"

    return ''


def _upsert_dynamic_general_transaction(conn, transaction_id, *, duracion_segundos=None):
    tx = conn.execute('''
        SELECT td.usuario_id, td.player_id, td.player_id2, td.paquete_id, td.numero_control,
               td.transaccion_id, td.monto, td.estado, td.gamepoint_referenceno,
               td.ingame_name, td.pin_entregado, td.notas, jd.nombre AS juego_nombre,
               pd.nombre AS paquete_nombre
        FROM transacciones_dinamicas td
        JOIN juegos_dinamicos jd ON td.juego_id = jd.id
        JOIN paquetes_dinamicos pd ON td.paquete_id = pd.id
        WHERE td.id = ?
    ''', (transaction_id,)).fetchone()
    if not tx:
        return False

    display_package_name = f"{tx['juego_nombre']} - {tx['paquete_nombre']}"
    pin_info = _build_dynamic_pin_info(tx)
    existing_row = conn.execute('SELECT id FROM transacciones WHERE transaccion_id = ?', (tx['transaccion_id'],)).fetchone()
    amount_value = -abs(float(tx['monto'] or 0.0))

    if existing_row:
        if duracion_segundos is None:
            conn.execute('''
                UPDATE transacciones
                SET pin = ?, paquete_nombre = ?, monto = ?
                WHERE transaccion_id = ?
            ''', (pin_info, display_package_name, amount_value, tx['transaccion_id']))
        else:
            conn.execute('''
                UPDATE transacciones
                SET pin = ?, paquete_nombre = ?, monto = ?, duracion_segundos = ?
                WHERE transaccion_id = ?
            ''', (pin_info, display_package_name, amount_value, duracion_segundos, tx['transaccion_id']))
    else:
        conn.execute('''
            INSERT INTO transacciones (usuario_id, numero_control, pin, transaccion_id, paquete_nombre, monto, duracion_segundos, request_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            tx['usuario_id'],
            tx['numero_control'],
            pin_info,
            tx['transaccion_id'],
            display_package_name,
            amount_value,
            duracion_segundos,
            tx['numero_control'],
        ))
    return True


def _build_existing_dynamic_payload(tx, package_name):
    estado_db = str(tx.get('estado') or '').strip().lower()
    serial_key = str(tx.get('pin_entregado') or '').strip()

    if _is_real_serial(serial_key):
        estado = 'completado'
    elif estado_db == 'pendiente':
        estado = 'pendiente_serial'
    elif estado_db == 'procesando':
        estado = 'procesando'
    elif estado_db in ('rechazado', 'error', 'fallida'):
        estado = 'error'
    else:
        estado = 'completado'

    return {
        'paquete_nombre': package_name,
        'monto_compra': abs(float(tx.get('monto') or 0.0)),
        'numero_control': tx.get('numero_control') or '',
        'transaccion_id': tx.get('transaccion_id') or '',
        'player_id': str(tx.get('player_id') or '').strip(),
        'player_id2': str(tx.get('player_id2') or '').strip(),
        'servidor': str(tx.get('servidor') or '').strip(),
        'player_name': str(tx.get('ingame_name') or '').strip(),
        'estado': estado,
        'gamepoint_ref': str(tx.get('gamepoint_referenceno') or '').strip(),
        'serial_key': serial_key if _is_real_serial(serial_key) else '',
        'error_mensaje': str(tx.get('notas') or '').strip(),
    }


def _find_dynamic_purchase_by_request_id(user_id, request_id):
    conn = _get_conn()
    try:
        row = conn.execute('''
            SELECT td.id, td.numero_control, td.transaccion_id, td.monto, td.estado, td.player_id, td.player_id2,
                   td.servidor, td.ingame_name, td.pin_entregado, td.notas, td.gamepoint_referenceno,
                   pd.nombre AS paquete_nombre
            FROM transacciones_dinamicas
            JOIN paquetes_dinamicos pd ON pd.id = td.paquete_id
            WHERE usuario_id = ?
              AND request_id = ?
            LIMIT 1
        ''', (int(user_id), str(request_id or '').strip())).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _refund_without_session(conn, user_id, precio):
    conn.execute('UPDATE usuarios SET saldo = saldo + ? WHERE id = ?', (precio, user_id))
    logger.info(f"[DynGame] Saldo ${precio} reembolsado al usuario {user_id} desde poller")


# ---------------------------------------------------------------------------
# ADMIN: Tasa MYR → USD
# ---------------------------------------------------------------------------

@bp.route('/admin/dynamic-games/gp-rate', methods=['GET'])
def admin_get_gp_rate():
    if not session.get('is_admin'):
        return jsonify({'error': 'Acceso denegado'}), 403
    usd_to_myr = float(get_gp_usd_to_myr_rate())
    return jsonify({
        'rate': usd_to_myr,
        'usd_to_myr_rate': usd_to_myr,
        'myr_to_usd_rate': round(1.0 / usd_to_myr, 6),
    })


@bp.route('/admin/dynamic-games/gp-rate', methods=['POST'])
@csrf_protect('/admin')
def admin_set_gp_rate():
    if not session.get('is_admin'):
        return jsonify({'error': 'Acceso denegado'}), 403
    data = request.get_json() or {}
    try:
        rate = float(data.get('rate', 0))
        if rate <= 0:
            return jsonify({'error': 'Tasa inválida, debe ser mayor a 0'}), 400
        # Si envían una tasa antigua < 1 (MYR->USD), convertirla automáticamente.
        usd_to_myr = (1.0 / rate) if rate < 1 else rate
        set_gp_usd_to_myr_rate(usd_to_myr)

        # Sincronizar Blood Strike inmediatamente con la nueva tasa.
        bloodstrike_sync = None
        try:
            import app as _app
            bloodstrike_sync = _app._bloodstrike_sync_prices_internal()
        except Exception as e:
            bloodstrike_sync = {'error': str(e)}

        # Aplicar inmediatamente la nueva tasa en los precios locales de juegos dinámicos.
        # Esto evita esperar al ciclo automático en background para ver cambios en layouts.
        sync_results = sync_all_dynamic_games_prices()
        synced_games = 0
        updated_packages = 0
        errors = []
        for item in sync_results:
            result = item.get('result') or {}
            if result.get('success'):
                synced_games += 1
                updated_packages += int(result.get('packages_updated', 0) or 0)
            if item.get('error') or result.get('error'):
                errors.append({'game': item.get('game'), 'error': item.get('error') or result.get('error')})

        return jsonify({
            'ok': True,
            'rate': usd_to_myr,
            'usd_to_myr_rate': usd_to_myr,
            'myr_to_usd_rate': round(1.0 / usd_to_myr, 6),
            'bloodstrike_sync': bloodstrike_sync,
            'dynamic_sync': {
                'games_synced': synced_games,
                'packages_updated': updated_packages,
                'errors': errors,
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


# ---------------------------------------------------------------------------
# ADMIN: CRUD juegos dinámicos
# ---------------------------------------------------------------------------

@bp.route('/admin/dynamic-games')
def admin_dynamic_games_page():
    if not session.get('is_admin'):
        flash('Acceso denegado.', 'error')
        return redirect('/auth')
    games = get_all_dynamic_games()
    for g in games:
        g['_campos'] = parse_campos_config(g)
        g['_packages'] = get_dynamic_packages(g['id'])

        # Load purchase cost per package for real-time profit display in admin UI
        try:
            conn = _get_conn()
            juego_key = f"dyn_{g['slug']}"
            rows = conn.execute(
                'SELECT paquete_id, precio_compra FROM precios_compra WHERE juego = ?',
                (juego_key,)
            ).fetchall()
            conn.close()
            costs = {int(r['paquete_id']): float(r['precio_compra']) for r in rows}
        except Exception:
            costs = {}
        for p in g['_packages']:
            try:
                p['_costo_compra'] = costs.get(int(p['id']))
            except Exception:
                p['_costo_compra'] = None
    return render_template('admin_dynamic_games.html', games=games)


@bp.route('/admin/dynamic-games/create', methods=['POST'])
@csrf_protect('/admin')
def admin_create_game():
    if not session.get('is_admin'):
        return jsonify({'error': 'Acceso denegado'}), 403
    data = request.get_json() or request.form
    nombre = (data.get('nombre') or '').strip()
    product_id = data.get('gamepoint_product_id')
    modo = data.get('modo', 'id')
    color = data.get('color_tema', '#a78bfa')
    icono = data.get('icono', '🎮')
    descripcion = data.get('descripcion', '')
    ganancia = float(data.get('ganancia_default', 0.10))

    # Build campos_config JSON
    campos = {}
    # Primary ID field
    campos['campo_id'] = {
        'label': data.get('campo_id_label', 'ID de Jugador'),
        'placeholder': data.get('campo_id_placeholder', 'Ingresa tu ID'),
        'required': True,
        'pattern': data.get('campo_id_pattern', ''),
        'pattern_msg': data.get('campo_id_pattern_msg', ''),
    }
    # Dual ID (e.g. Mobile Legends Zone ID)
    if data.get('dual_id') in (True, 'true', '1', 'on') or data.get('campo_id2_label'):
        campos['campo_id2'] = {
            'enabled': True,
            'label': data.get('campo_id2_label', 'Zone ID'),
            'placeholder': data.get('campo_id2_placeholder', 'Ingresa tu Zone ID'),
            'required': True,
            'pattern': data.get('campo_id2_pattern', ''),
            'pattern_msg': data.get('campo_id2_pattern_msg', ''),
        }
    # Server selector
    if data.get('servidor_enabled') in (True, 'true', '1', 'on') or data.get('campo_servidor') in (True, 'true', '1', 'on'):
        opciones_raw = data.get('servidor_opciones', '')
        opciones = [o.strip() for o in opciones_raw.split(',') if o.strip()] if isinstance(opciones_raw, str) else opciones_raw
        campos['servidor'] = {
            'enabled': True,
            'label': data.get('servidor_label', 'Servidor'),
            'opciones': opciones,
        }

    if not nombre or not product_id:
        return jsonify({'error': 'Nombre y Product ID son obligatorios'}), 400

    slug = slugify(nombre)

    # Check slug uniqueness
    existing = get_dynamic_game_by_slug(slug)
    if existing:
        slug = slug + '-' + secrets.token_hex(2)

    conn = _get_conn()
    try:
        cur = conn.execute('''
            INSERT INTO juegos_dinamicos (nombre, slug, gamepoint_product_id, modo, color_tema, icono, activo, campos_config, descripcion, ganancia_default)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
        ''', (nombre, slug, int(product_id), modo, color, icono, False, json.dumps(campos), descripcion, ganancia))
        game_id = cur.fetchone()[0]
        conn.commit()
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500
    conn.close()

    if request.is_json:
        return jsonify({'success': True, 'game_id': game_id, 'slug': slug})
    flash(f'Juego "{nombre}" creado. Ahora añade paquetes en la pestaña Precios.', 'success')
    return redirect('/admin#tab=precios')


@bp.route('/admin/dynamic-games/<int:game_id>/update', methods=['POST'])
@csrf_protect('/admin')
def admin_update_game(game_id):
    if not session.get('is_admin'):
        return jsonify({'error': 'Acceso denegado'}), 403
    data = request.get_json() or request.form
    game = get_dynamic_game_by_id(game_id)
    if not game:
        return jsonify({'error': 'Juego no encontrado'}), 404

    nombre = (data.get('nombre') or game['nombre']).strip()
    product_id = data.get('gamepoint_product_id', game['gamepoint_product_id'])
    modo = data.get('modo', game['modo'])
    color = data.get('color_tema', game['color_tema'])
    icono = data.get('icono', game['icono'])
    descripcion = data.get('descripcion', game['descripcion'])
    ganancia = float(data.get('ganancia_default', game['ganancia_default']))
    activo = data.get('activo')
    if activo is not None:
        activo = activo in (True, 'true', '1', 'on', 1)
    else:
        activo = game['activo']

    # Rebuild campos_config
    campos = {}
    campos['campo_id'] = {
        'label': data.get('campo_id_label', 'ID de Jugador'),
        'placeholder': data.get('campo_id_placeholder', 'Ingresa tu ID'),
        'required': True,
        'pattern': data.get('campo_id_pattern', ''),
        'pattern_msg': data.get('campo_id_pattern_msg', ''),
    }
    if data.get('dual_id') in (True, 'true', '1', 'on'):
        campos['campo_id2'] = {
            'enabled': True,
            'label': data.get('campo_id2_label', 'Zone ID'),
            'placeholder': data.get('campo_id2_placeholder', 'Ingresa tu Zone ID'),
            'required': True,
            'pattern': data.get('campo_id2_pattern', ''),
            'pattern_msg': data.get('campo_id2_pattern_msg', ''),
        }
    if data.get('servidor_enabled') in (True, 'true', '1', 'on'):
        opciones_raw = data.get('servidor_opciones', '')
        opciones = [o.strip() for o in opciones_raw.split(',') if o.strip()] if isinstance(opciones_raw, str) else opciones_raw
        campos['servidor'] = {
            'enabled': True,
            'label': data.get('servidor_label', 'Servidor'),
            'opciones': opciones,
        }

    conn = _get_conn()
    conn.execute('''
        UPDATE juegos_dinamicos SET nombre=?, gamepoint_product_id=?, modo=?, color_tema=?, icono=?, activo=?,
        campos_config=?, descripcion=?, ganancia_default=?, fecha_actualizacion=CURRENT_TIMESTAMP
        WHERE id=?
    ''', (nombre, int(product_id), modo, color, icono, activo, json.dumps(campos), descripcion, ganancia, game_id))
    conn.commit()
    conn.close()

    if request.is_json:
        return jsonify({'success': True})
    flash(f'Juego "{nombre}" actualizado.', 'success')
    return redirect('/admin/dynamic-games')


@bp.route('/admin/dynamic-games/<int:game_id>/toggle', methods=['POST'])
@csrf_protect('/admin')
def admin_toggle_game(game_id):
    if not session.get('is_admin'):
        return jsonify({'error': 'Acceso denegado'}), 403
    game = get_dynamic_game_by_id(game_id)
    if not game:
        return jsonify({'error': 'Juego no encontrado'}), 404
    new_state = not game['activo']
    new_state_sql = 'TRUE' if new_state else 'FALSE'
    conn = _get_conn()
    conn.execute(f'UPDATE juegos_dinamicos SET activo={new_state_sql}, fecha_actualizacion=CURRENT_TIMESTAMP WHERE id=?', (game_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'activo': new_state})


@bp.route('/admin/dynamic-games/<int:game_id>/delete', methods=['POST'])
@csrf_protect('/admin')
def admin_delete_game(game_id):
    if not session.get('is_admin'):
        return jsonify({'error': 'Acceso denegado'}), 403
    conn = _get_conn()
    conn.execute('DELETE FROM paquetes_dinamicos WHERE juego_id=?', (game_id,))
    conn.execute('DELETE FROM transacciones_dinamicas WHERE juego_id=?', (game_id,))
    conn.execute('DELETE FROM juegos_dinamicos WHERE id=?', (game_id,))
    conn.commit()
    conn.close()
    if request.is_json:
        return jsonify({'success': True})
    flash('Juego eliminado.', 'success')
    return redirect('/admin/dynamic-games')


# ---------------------------------------------------------------------------
# ADMIN: Paquetes de un juego dinámico
# ---------------------------------------------------------------------------

@bp.route('/admin/dynamic-games/<int:game_id>/packages', methods=['GET'])
def admin_get_packages(game_id):
    if not session.get('is_admin'):
        return jsonify({'error': 'Acceso denegado'}), 403
    pkgs = get_dynamic_packages(game_id)
    return jsonify({'packages': pkgs})


@bp.route('/admin/dynamic-games/<int:game_id>/packages/add', methods=['POST'])
@csrf_protect('/admin')
def admin_add_package(game_id):
    if not session.get('is_admin'):
        return jsonify({'error': 'Acceso denegado'}), 403
    try:
        data = request.get_json(silent=True) or request.form
        nombre = (data.get('nombre') or '').strip()
        descripcion = (data.get('descripcion') or '').strip()
        gp_pkg_id = data.get('gamepoint_package_id')
        game_script_only = str(data.get('game_script_only', 'false')).strip().lower() in ('1', 'true', 'yes', 'on')

        try:
            precio = float(data.get('precio', 0) or 0)
        except (TypeError, ValueError):
            return jsonify({'error': 'El precio debe ser numérico'}), 400

        try:
            orden = int(data.get('orden', 0) or 0)
        except (TypeError, ValueError):
            return jsonify({'error': 'El orden debe ser numérico'}), 400

        try:
            gp_pkg_id = int(gp_pkg_id) if gp_pkg_id not in (None, '', 'null') else None
        except (TypeError, ValueError):
            return jsonify({'error': 'El GamePoint Package ID debe ser numérico'}), 400

        if not nombre or precio <= 0:
            return jsonify({'error': 'Nombre y precio son obligatorios'}), 400

        conn = _get_conn()
        if not _pg_table_exists(conn, 'juegos_dinamicos') or not _pg_table_exists(conn, 'paquetes_dinamicos'):
            conn.close()
            return jsonify({'error': 'Las tablas de juegos dinámicos no existen en la base de datos PostgreSQL'}), 500

        row = conn.execute('SELECT * FROM juegos_dinamicos WHERE id = ?', (game_id,)).fetchone()
        game = dict(row) if row else None
        if not game:
            conn.close()
            return jsonify({'error': 'Juego no encontrado'}), 404

        cur = conn.execute('''
            INSERT INTO paquetes_dinamicos (juego_id, nombre, precio, descripcion, gamepoint_package_id, game_script_only, activo, orden)
            VALUES (?, ?, ?, ?, ?, ?, TRUE, ?)
            RETURNING id
        ''', (game_id, nombre, precio, descripcion, gp_pkg_id, game_script_only, orden))
        pkg_id = cur.fetchone()[0]
        conn.commit()

        if gp_pkg_id:
            juego_key = f'dyn_{game["slug"]}'
            costo_estimado = max(0, precio - game.get('ganancia_default', 0.10))
            try:
                conn.execute(
                    'INSERT INTO precios_compra (juego, paquete_id, precio_compra) VALUES (?, ?, ?) ON CONFLICT (juego, paquete_id) DO UPDATE SET precio_compra = EXCLUDED.precio_compra',
                    (juego_key, pkg_id, costo_estimado)
                )
                conn.commit()
            except Exception:
                pass

        return jsonify({'success': True, 'package_id': pkg_id})
    except Exception as e:
        logger.exception('Error agregando paquete dinámico al juego %s', game_id)
        return jsonify({'error': f'No se pudo agregar el paquete: {str(e)}'}), 500
    finally:
        try:
            conn.close()
        except Exception:
            pass


@bp.route('/admin/dynamic-games/packages/<int:pkg_id>/update', methods=['POST'])
@csrf_protect('/admin')
def admin_update_package(pkg_id):
    if not session.get('is_admin'):
        return jsonify({'error': 'Acceso denegado'}), 403
    data = request.get_json() or request.form
    pkg = get_dynamic_package_by_id(pkg_id)
    if not pkg:
        return jsonify({'error': 'Paquete no encontrado'}), 404

    nombre = (data.get('nombre') or pkg['nombre']).strip()
    precio = float(data.get('precio', pkg['precio']))
    descripcion = (data.get('descripcion') or pkg.get('descripcion', '')).strip()
    gp_pkg_id = data.get('gamepoint_package_id', pkg.get('gamepoint_package_id'))
    activo = data.get('activo')
    orden = int(data.get('orden', pkg.get('orden', 0)))
    if activo is not None:
        activo = activo in (True, 'true', '1', 'on', 1)
    else:
        activo = pkg['activo']

    conn = _get_conn()
    conn.execute('''
        UPDATE paquetes_dinamicos SET nombre=?, precio=?, descripcion=?, gamepoint_package_id=?, activo=?, orden=?,
        fecha_actualizacion=CURRENT_TIMESTAMP WHERE id=?
    ''', (nombre, precio, descripcion, int(gp_pkg_id) if gp_pkg_id else None, activo, orden, pkg_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@bp.route('/admin/dynamic-games/packages/<int:pkg_id>/delete', methods=['POST'])
@csrf_protect('/admin')
def admin_delete_package(pkg_id):
    if not session.get('is_admin'):
        return jsonify({'error': 'Acceso denegado'}), 403
    conn = _get_conn()
    conn.execute('DELETE FROM paquetes_dinamicos WHERE id=?', (pkg_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# ADMIN: Auto-import packages from GamePoint catalog
# ---------------------------------------------------------------------------

@bp.route('/admin/dynamic-games/<int:game_id>/auto-import-packages', methods=['POST'])
@csrf_protect('/admin')
def admin_auto_import_packages(game_id):
    """Fetch GP catalog and auto-create local packages (name + gp_id mapped, price $0)."""
    if not session.get('is_admin'):
        return jsonify({'error': 'Acceso denegado'}), 403
    try:
        game = get_dynamic_game_by_id(game_id)
        if not game:
            return jsonify({'error': 'Juego no encontrado'}), 404

        get_token, gp_post, *_ = _gp_helpers()
        gc_token, gc_err = get_token()
        if not gc_token:
            return jsonify({'error': (gc_err or {}).get('message', 'No se pudo obtener token de GamePoint')}), 500

        _, detail = gp_post('product/detail', {'token': gc_token, 'productid': game['gamepoint_product_id']})
        if (detail or {}).get('code') != 200:
            return jsonify({'error': (detail or {}).get('message', 'Error obteniendo catálogo de GamePoint')}), 500

        gp_packages = (detail or {}).get('package', [])
        if not gp_packages:
            return jsonify({'error': 'No se encontraron paquetes en GamePoint para este producto'}), 404

        conn = _get_conn()
        existing_gp_ids = set()
        for row in conn.execute('SELECT gamepoint_package_id FROM paquetes_dinamicos WHERE juego_id = ? AND gamepoint_package_id IS NOT NULL', (game_id,)):
            existing_gp_ids.add(int(row['gamepoint_package_id']))

        created = 0
        skipped = 0
        for idx, gp_pkg in enumerate(gp_packages):
            gp_id = int(gp_pkg['id'])
            if gp_id in existing_gp_ids:
                skipped += 1
                continue
            gp_name = gp_pkg.get('name', f'Paquete {gp_id}')
            clean_name = re.sub(r'<[^>]+>', ' ', gp_name).strip()
            clean_name = ' '.join(clean_name.split())
            conn.execute('''
                INSERT INTO paquetes_dinamicos (juego_id, nombre, precio, descripcion, gamepoint_package_id, activo, orden)
                VALUES (?, ?, 0.0, '', ?, FALSE, ?)
            ''', (game_id, clean_name, gp_id, idx))
            created += 1

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'created': created,
            'skipped': skipped,
            'total_gp': len(gp_packages),
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error interno: {str(e)}'}), 500


# ---------------------------------------------------------------------------
# ADMIN: Fetch GamePoint catalog for a product (to help mapping)
# ---------------------------------------------------------------------------

@bp.route('/admin/dynamic-games/<int:game_id>/gp-catalog', methods=['GET'])
def admin_gp_catalog(game_id):
    if not session.get('is_admin'):
        return jsonify({'error': 'Acceso denegado'}), 403
    game = get_dynamic_game_by_id(game_id)
    if not game:
        return jsonify({'error': 'Juego no encontrado'}), 404

    get_token, gp_post, *_ = _gp_helpers()
    gc_token, gc_err = get_token()
    if not gc_token:
        return jsonify({'error': (gc_err or {}).get('message', 'No se pudo obtener token')}), 500

    _, detail = gp_post('product/detail', {'token': gc_token, 'productid': game['gamepoint_product_id']})
    if (detail or {}).get('code') != 200:
        return jsonify({'error': (detail or {}).get('message', 'Error obteniendo catálogo')}), 500

    packages = (detail or {}).get('package', [])
    return jsonify({'success': True, 'packages': packages})


# ---------------------------------------------------------------------------
# ADMIN: Mapping for GameClub tab (same pattern as Blood Strike)
# ---------------------------------------------------------------------------

@bp.route('/admin/dynamic-games/<int:game_id>/gamepoint_packages')
def admin_dyn_gamepoint_packages(game_id):
    """Returns GP catalog + local packages for mapping UI (like Blood Strike)."""
    if not session.get('is_admin'):
        return jsonify({'error': 'Acceso denegado'}), 403
    game = get_dynamic_game_by_id(game_id)
    if not game:
        return jsonify({'error': 'Juego no encontrado'}), 404

    get_token, gp_post, *_ = _gp_helpers()
    gc_token, gc_err = get_token()
    if not gc_token:
        return jsonify({'error': (gc_err or {}).get('message', 'No se pudo obtener token')}), 500

    _, detail = gp_post('product/detail', {'token': gc_token, 'productid': game['gamepoint_product_id']})
    if (detail or {}).get('code') != 200:
        return jsonify({'error': (detail or {}).get('message', 'Error')}), 500

    conn = _get_conn()
    local_packages = conn.execute(
        'SELECT id, nombre, precio, gamepoint_package_id FROM paquetes_dinamicos WHERE juego_id = ? ORDER BY orden, id',
        (game_id,)
    ).fetchall()
    conn.close()

    return jsonify({
        'gamepoint_packages': (detail or {}).get('package', []),
        'local_packages': [dict(lp) for lp in local_packages],
        'product_id': game['gamepoint_product_id'],
        'game_name': game['nombre'],
    })


@bp.route('/admin/dynamic-games/<int:game_id>/set_gamepoint_id', methods=['POST'])
@csrf_protect('/admin')
def admin_dyn_set_gamepoint_id(game_id):
    """Assign a gamepoint_package_id to a local dynamic package."""
    if not session.get('is_admin'):
        return jsonify({'error': 'Acceso denegado'}), 403
    data = request.get_json() or request.form
    local_id = data.get('local_id')
    gp_id = data.get('gamepoint_package_id')
    if not local_id:
        return jsonify({'error': 'Falta local_id'}), 400

    conn = _get_conn()
    pkg = conn.execute('SELECT id, nombre FROM paquetes_dinamicos WHERE id = ? AND juego_id = ?', (local_id, game_id)).fetchone()
    if not pkg:
        conn.close()
        return jsonify({'error': 'Paquete no encontrado'}), 404

    gp_val = int(gp_id) if gp_id and str(gp_id).strip() else None
    conn.execute('UPDATE paquetes_dinamicos SET gamepoint_package_id = ?, fecha_actualizacion = CURRENT_TIMESTAMP WHERE id = ?',
                 (gp_val, local_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'local_id': int(local_id), 'nombre': pkg['nombre'], 'gamepoint_package_id': gp_val})


# ---------------------------------------------------------------------------
# ADMIN: Sync prices for a specific dynamic game
# ---------------------------------------------------------------------------

def sync_dynamic_game_prices(game_id):
    """Sync prices for one dynamic game. Returns dict result."""
    game = get_dynamic_game_by_id(game_id)
    if not game:
        return {'error': 'Juego no encontrado'}

    myr_to_usd = get_gp_myr_rate()
    default_profit = game.get('ganancia_default', 0.10)
    juego_key = f'dyn_{game["slug"]}'

    get_token, gp_post, *_ = _gp_helpers()
    gc_token, gc_err = get_token()
    if not gc_token:
        return {'error': (gc_err or {}).get('message', 'No se pudo obtener token')}

    _, detail = gp_post('product/detail', {'token': gc_token, 'productid': game['gamepoint_product_id']})
    if (detail or {}).get('code') != 200:
        return {'error': (detail or {}).get('message', 'Error obteniendo catálogo')}

    gp_packages = (detail or {}).get('package', [])
    if not gp_packages:
        return {'error': 'No se encontraron paquetes en GamePoint'}

    conn = _get_conn()
    local_pkgs = conn.execute('SELECT * FROM paquetes_dinamicos WHERE juego_id = ?', (game_id,)).fetchall()

    # Load current costs
    local_costs = {}
    for row in conn.execute("SELECT paquete_id, precio_compra FROM precios_compra WHERE juego = ?", (juego_key,)).fetchall():
        local_costs[int(row['paquete_id'])] = float(row['precio_compra'])

    # Map gp_package_id -> local package
    gp_to_local = {}
    for lp in local_pkgs:
        if lp['gamepoint_package_id']:
            gp_to_local[int(lp['gamepoint_package_id'])] = dict(lp)

    report = []
    updated = 0

    for gp_pkg in gp_packages:
        gp_id = int(gp_pkg['id'])
        gp_name = gp_pkg.get('name', '')
        gp_price_myr = float(gp_pkg.get('price', 0))
        nuevo_costo = round(gp_price_myr * myr_to_usd, 4)

        local = gp_to_local.get(gp_id)
        if local:
            costo_actual = local_costs.get(local['id'], 0)
            if costo_actual > 0:
                ganancia = round(local['precio'] - costo_actual, 4)
            else:
                # Si falta costo histórico, inferir margen desde precio actual para
                # mantener estable el precio base y que próximos cambios sigan el delta GP.
                ganancia = round(float(local['precio']) - float(nuevo_costo), 4)
            nuevo_precio = round(nuevo_costo + ganancia, 2)

            entry = {
                'gp_id': gp_id, 'gp_name': gp_name, 'gp_myr': gp_price_myr,
                'costo_anterior': round(costo_actual, 4), 'costo_nuevo': round(nuevo_costo, 4),
                'ganancia': round(ganancia, 4), 'precio_nuevo': nuevo_precio,
                'local_id': local['id'], 'local_nombre': local['nombre'],
                'precio_anterior': local['precio'],
                'cambio': round(nuevo_precio - local['precio'], 4),
            }
            activo = True if float(nuevo_precio) > 0 else False
            conn.execute('UPDATE paquetes_dinamicos SET precio=?, activo=?, fecha_actualizacion=CURRENT_TIMESTAMP WHERE id=?',
                         (nuevo_precio, activo, local['id']))
            conn.execute('INSERT INTO precios_compra (juego, paquete_id, precio_compra) VALUES (?, ?, ?) ON CONFLICT (juego, paquete_id) DO UPDATE SET precio_compra = EXCLUDED.precio_compra',
                         (juego_key, local['id'], nuevo_costo))
            updated += 1
        else:
            nuevo_precio = round(nuevo_costo + default_profit, 2)
            entry = {
                'gp_id': gp_id, 'gp_name': gp_name, 'gp_myr': gp_price_myr,
                'costo_nuevo': round(nuevo_costo, 4), 'ganancia': default_profit,
                'precio_nuevo': nuevo_precio, 'local_id': None,
                'nota': 'Sin mapeo local',
            }
        report.append(entry)

    conn.commit()
    conn.close()

    return {
        'success': True,
        'game': game['nombre'],
        'packages_updated': updated,
        'total_gp': len(gp_packages),
        'report': report,
    }


@bp.route('/admin/dynamic-games/<int:game_id>/sync-prices', methods=['POST'])
@csrf_protect('/admin')
def admin_sync_game_prices(game_id):
    if not session.get('is_admin'):
        return jsonify({'error': 'Acceso denegado'}), 403
    result = sync_dynamic_game_prices(game_id)
    if result.get('error'):
        return jsonify(result), 500
    return jsonify(result)


def sync_all_dynamic_games_prices():
    """Sync prices for all dynamic games (activos e inactivos)."""
    games = get_all_dynamic_games(only_active=False)
    results = []
    for g in games:
        try:
            r = sync_dynamic_game_prices(g['id'])
            results.append({'game': g['nombre'], 'result': r})
        except Exception as e:
            results.append({'game': g['nombre'], 'error': str(e)})
    return results


# ---------------------------------------------------------------------------
# USER: Dynamic game page
# ---------------------------------------------------------------------------

@bp.route('/juego/d/<slug>')
def dynamic_game_page(slug):
    if 'usuario' not in session:
        return redirect('/auth')

    game = get_dynamic_game_by_slug(slug)
    if not game:
        flash('Juego no encontrado.', 'error')
        return redirect('/')

    is_admin = session.get('is_admin', False)
    if not is_admin and not game['activo']:
        flash('Este juego está desactivado temporalmente.', 'error')
        return redirect('/')

    # Refresh balance from DB
    user_id = session.get('user_db_id')
    if user_id:
        conn = _get_conn()
        user = conn.execute('SELECT saldo FROM usuarios WHERE id = ?', (user_id,)).fetchone()
        if user:
            session['saldo'] = user['saldo']
        conn.close()

    packages = get_dynamic_packages(game['id'], only_active=not is_admin)
    campos = parse_campos_config(game)

    # Check for successful purchase (no URL param required — handles browser timeout on redirect)
    compra_exitosa = False
    compra_error = False
    compra_data = {}
    if f'compra_dyn_{slug}_exitosa' in session:
        compra_exitosa = True
        compra_data = session.pop(f'compra_dyn_{slug}_exitosa')
    elif f'compra_dyn_{slug}_error' in session:
        compra_error = True
        compra_data = session.pop(f'compra_dyn_{slug}_error')

    # Generate one-time nonce for form submission
    nonce = secrets.token_urlsafe(16)
    session[f'dg_nonce_{slug}'] = nonce

    # Lazy import to avoid circular dependency
    from app import get_games_active
    games_active = get_games_active()
    dynamic_games_menu = get_all_dynamic_games(only_active=True)

    return render_template('juego_dinamico.html',
                           game=game,
                           packages=packages,
                           campos=campos,
                           user_id=session.get('id', '00000'),
                           balance=session.get('saldo', 0),
                           is_admin=is_admin,
                           compra_exitosa=compra_exitosa,
                           compra_error=compra_error,
                           games_active=games_active,
                           dynamic_games_menu=dynamic_games_menu,
                           dg_form_nonce=nonce,
                           **compra_data)


# ---------------------------------------------------------------------------
# USER: Purchase flow
# ---------------------------------------------------------------------------

@bp.route('/validar/dinamico/<slug>', methods=['POST'])
def validar_dinamico(slug):
    if 'usuario' not in session:
        return redirect('/auth')

    game = get_dynamic_game_by_slug(slug)
    if not game:
        flash('Juego no encontrado.', 'error')
        return redirect('/')

    is_admin = session.get('is_admin', False)
    if not is_admin and not game['activo']:
        flash('Este juego está desactivado temporalmente.', 'error')
        return redirect('/')

    campos = parse_campos_config(game)
    redirect_url = f'/juego/d/{slug}'

    def redirect_dynamic_error(message, package_name='', amount=None):
        session[f'compra_dyn_{slug}_error'] = {
            'paquete_nombre': package_name,
            'monto_compra': amount or 0,
            'player_id': player_id,
            'player_id2': player_id2,
            'servidor': servidor,
            'estado': 'error',
            'error_mensaje': message,
        }
        return redirect(f'{redirect_url}?compra=error')

    # Validate one-time nonce (prevents double charges on browser retry / web down)
    nonce_form = request.form.get('dg_form_nonce')
    nonce_session = session.pop(f'dg_nonce_{slug}', None)
    if not nonce_form or not nonce_session or nonce_form != nonce_session:
        player_id = ''
        player_id2 = ''
        servidor = ''
        return redirect_dynamic_error('Solicitud duplicada o expirada. Recarga la pagina e intenta nuevamente.')

    # Collect form fields
    package_id = request.form.get('monto')
    player_id = request.form.get('player_id', '').strip()
    player_id2 = request.form.get('player_id2', '').strip()
    servidor = request.form.get('servidor', '').strip()

    if not package_id:
        return redirect_dynamic_error('Selecciona un paquete.')

    # Validate required fields based on game mode
    if game['modo'] == 'id':
        if not player_id:
            return redirect_dynamic_error('Ingresa tu ID de jugador.')
        # Validate patterns
        campo_id_cfg = campos.get('campo_id', {})
        pattern = campo_id_cfg.get('pattern', '')
        if pattern:
            if not re.match(pattern, player_id):
                return redirect_dynamic_error(campo_id_cfg.get('pattern_msg', 'Formato de ID invalido.'))
        # Dual ID
        campo_id2_cfg = campos.get('campo_id2', {})
        if campo_id2_cfg.get('enabled') and not player_id2:
            return redirect_dynamic_error(f'Ingresa tu {campo_id2_cfg.get("label", "Zone ID")}.')
        if campo_id2_cfg.get('enabled') and campo_id2_cfg.get('pattern'):
            if not re.match(campo_id2_cfg['pattern'], player_id2):
                return redirect_dynamic_error(campo_id2_cfg.get('pattern_msg', 'Formato invalido.'))
        # Server
        srv_cfg = campos.get('servidor', {})
        if srv_cfg.get('enabled') and not servidor:
            return redirect_dynamic_error(f'Selecciona un {srv_cfg.get("label", "servidor")}.')

    package_id = int(package_id)
    user_id = session.get('user_db_id')
    request_id = (request.form.get('request_id') or '').strip()
    pkg = get_dynamic_package_by_id(package_id)
    if not pkg or pkg['juego_id'] != game['id']:
        return redirect_dynamic_error('Paquete no encontrado.')

    if not is_admin and not pkg['activo']:
        return redirect_dynamic_error('Paquete no disponible.')

    precio = pkg['precio']
    script_only = bool(pkg.get('game_script_only'))
    script_package_key = pkg.get('game_script_package_key')
    script_package_title = pkg.get('game_script_package_title')
    gp_package_id = pkg.get('gamepoint_package_id')
    if script_only and slug == 'blood-strike' and not script_package_key:
        return redirect_dynamic_error('Este paquete esta marcado como Solo Game pero no tiene mapeo configurado.', pkg['nombre'], precio)

    if not script_only and not gp_package_id:
        return redirect_dynamic_error('Este paquete no tiene configurado el ID de GamePoint.', pkg['nombre'], precio)

    if not request_id:
        return redirect_dynamic_error('Solicitud invalida. Recarga la pagina e intenta nuevamente.', pkg['nombre'], precio)

    import app as _app
    from app import begin_idempotent_purchase, save_processing_idempotent_purchase, complete_idempotent_purchase, clear_idempotent_purchase
    endpoint_key = f'dynamic_game:{game["slug"]}'
    conn_idempotency = _get_conn()
    try:
        idempotency_state = begin_idempotent_purchase(conn_idempotency, user_id, endpoint_key, request_id)
        conn_idempotency.commit()
    except Exception:
        conn_idempotency.rollback()
        conn_idempotency.close()
        return redirect_dynamic_error('No se pudo registrar la solicitud de compra. Intenta nuevamente.', pkg['nombre'], precio)
    finally:
        try:
            conn_idempotency.close()
        except Exception:
            pass

    if idempotency_state['state'] == 'completed':
        session[f'compra_dyn_{slug}_exitosa'] = idempotency_state.get('payload') or {}
        flash('La compra ya había sido procesada. Se muestra el resultado anterior.', 'info')
        return redirect(f'/juego/d/{slug}?compra=exitosa')

    if idempotency_state['state'] == 'processing':
        existing_tx = _find_dynamic_purchase_by_request_id(user_id, request_id)
        if existing_tx:
            existing_payload = _build_existing_dynamic_payload(existing_tx, existing_tx.get('paquete_nombre') or pkg['nombre'])
            session[f'compra_dyn_{slug}_exitosa'] = existing_payload
            flash('Esta orden ya se esta procesando. Se muestra el estado actual hasta que GamePoint la confirme.', 'info')
            return redirect(f'/juego/d/{slug}?compra=exitosa')
        return redirect_dynamic_error('Esta compra ya se esta procesando. Espera unos segundos.', pkg['nombre'], precio)

    # Check balance
    if not is_admin:
        conn = _get_conn()
        row = conn.execute('SELECT saldo FROM usuarios WHERE id = ?', (user_id,)).fetchone()
        conn.close()
        saldo_actual = row['saldo'] if row else 0
        session['saldo'] = saldo_actual
        if saldo_actual < precio:
            conn_cleanup = _get_conn()
            clear_idempotent_purchase(conn_cleanup, user_id, endpoint_key, request_id)
            conn_cleanup.commit()
            conn_cleanup.close()
            return redirect_dynamic_error(f'Saldo insuficiente. Necesitas ${precio:.2f} pero tienes ${saldo_actual:.2f}', pkg['nombre'], precio)

    # === PURCHASE VIA GAMEPOINT ===
    _start = time_module.time()
    get_token, gp_post, order_validate, order_create, order_inquiry = _gp_helpers()
    _tx_procesando_id = None

    try:
        # 1. Deduct balance atomically
        if not is_admin:
            conn = _get_conn()
            cursor = conn.execute('UPDATE usuarios SET saldo = saldo - ? WHERE id = ? AND saldo >= ?', (precio, user_id, precio))
            if cursor.rowcount == 0:
                clear_idempotent_purchase(conn, user_id, endpoint_key, request_id)
                conn.commit()
                conn.close()
                return redirect_dynamic_error('Saldo insuficiente al momento de procesar.', pkg['nombre'], precio)
            conn.commit()
            new_saldo = conn.execute('SELECT saldo FROM usuarios WHERE id = ?', (user_id,)).fetchone()
            conn.close()
            session['saldo'] = new_saldo['saldo'] if new_saldo else 0

        # 1b. Insert 'procesando' record BEFORE GamePoint calls.
        # Duplicate refreshes are blocked by request_id + nonce, not by a timed cooldown.
        merchant_code = f"DG{game['id']}-" + secrets.token_hex(6).upper()
        numero_control = f"DG-{secrets.token_hex(4).upper()}"
        try:
            conn_proc = _get_conn()
            cur_proc = conn_proc.execute('''
                INSERT INTO transacciones_dinamicas
                (juego_id, usuario_id, player_id, player_id2, servidor, paquete_id,
                 numero_control, transaccion_id, monto, estado, request_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'procesando', ?)
                RETURNING id
            ''', (game['id'], user_id, player_id, player_id2 or None, servidor or None,
                  package_id, numero_control, merchant_code, precio, request_id))
            _tx_procesando_id = cur_proc.fetchone()[0]
            conn_proc.commit()
            conn_proc.close()
        except Exception as e_proc:
            logger.error(f"[DynGame:{game['slug']}] Error insertando procesando: {e_proc}")
            _refund(user_id, precio, is_admin)
            conn_cleanup = _get_conn()
            clear_idempotent_purchase(conn_cleanup, user_id, endpoint_key, request_id)
            conn_cleanup.commit()
            conn_cleanup.close()
            return redirect_dynamic_error('Error al procesar. Tu saldo ha sido devuelto.', pkg['nombre'], precio)

        if slug == 'blood-strike' and script_only:
            from app import _game_script_buy, register_weekly_sale

            script_result = _game_script_buy(player_id, script_package_key, request_id)
            script_ok = bool((script_result or {}).get('success'))
            script_processing = bool((script_result or {}).get('processing'))
            provider_ref = (script_result or {}).get('orden') or (script_result or {}).get('requestId') or request_id
            provider_player = (script_result or {}).get('jugador') or ''
            provider_error = (script_result or {}).get('error') or (script_result or {}).get('message') or 'Error desconocido del proveedor'
            _duration = round(time_module.time() - _start, 1)

            if script_ok or script_processing:
                estado_db = 'aprobado' if script_ok else 'procesando'
                estado_txt = 'completado' if script_ok else 'procesando'

                conn = _get_conn()
                conn.execute('''
                    UPDATE transacciones_dinamicas
                    SET estado = ?, gamepoint_referenceno = ?, ingame_name = ?, notas = ?, fecha_procesado = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (estado_db, provider_ref, provider_player or None, f'SCRIPT:{script_package_key}|ESTADO:{estado_txt}|USUARIO:{provider_player or ""}', _tx_procesando_id))

                paquete_display = f"{game['nombre']} - {pkg['nombre']}"
                if script_package_title:
                    paquete_display = f"{game['nombre']} - {pkg['nombre']} ({script_package_title})"

                pin_info = f"ID: {player_id}"
                if provider_player:
                    pin_info = f"ID: {player_id} - Jugador: {provider_player}"

                transaccion_id = merchant_code
                conn.execute('''
                    INSERT INTO transacciones (usuario_id, numero_control, pin, transaccion_id, paquete_nombre, monto, duracion_segundos, request_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, numero_control, pin_info, transaccion_id, paquete_display, -precio, _duration, request_id))

                _saldo_row = conn.execute('SELECT saldo FROM usuarios WHERE id = ?', (user_id,)).fetchone()
                _saldo = _saldo_row['saldo'] if _saldo_row else 0
                conn.execute('''
                    INSERT INTO historial_compras (usuario_id, monto, paquete_nombre, pin, tipo_evento, duracion_segundos, saldo_antes, saldo_despues)
                    VALUES (?, ?, ?, ?, 'compra', ?, ?, ?)
                ''', (user_id, precio, paquete_display, pin_info, _duration, _saldo + precio, _saldo))

                try:
                    juego_key = f'dyn_{game["slug"]}'
                    costo_row = conn.execute('SELECT precio_compra FROM precios_compra WHERE juego=? AND paquete_id=?',
                                             (juego_key, package_id)).fetchone()
                    costo_unit = costo_row['precio_compra'] if costo_row else 0
                    profit_unit = round(precio - costo_unit, 4)
                    conn.execute('''
                        INSERT INTO profit_ledger (usuario_id, juego, paquete_id, cantidad, precio_venta_unit, costo_unit, profit_unit, profit_total, transaccion_id)
                        VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)
                    ''', (user_id, juego_key, package_id, precio, costo_unit, profit_unit, profit_unit, transaccion_id))
                except Exception:
                    pass

                if not is_admin:
                    try:
                        from update_monthly_spending import update_monthly_spending
                        update_monthly_spending(conn, user_id, precio)
                    except Exception:
                        pass

                if not is_admin:
                    try:
                        register_weekly_sale(f'dyn_{game["slug"]}', package_id, pkg['nombre'], precio, 1)
                    except Exception:
                        pass

                success_payload = {
                    'paquete_nombre': pkg['nombre'],
                    'monto_compra': precio,
                    'numero_control': numero_control,
                    'transaccion_id': transaccion_id,
                    'player_id': player_id,
                    'player_id2': player_id2,
                    'servidor': servidor,
                    'player_name': provider_player,
                    'estado': estado_txt,
                }
                complete_idempotent_purchase(conn, user_id, endpoint_key, request_id, success_payload, transaccion_id, numero_control)
                conn.commit()
                conn.close()
                session[f'compra_dyn_{slug}_exitosa'] = success_payload
                return redirect(f'/juego/d/{slug}?compra=exitosa')

            conn = _get_conn()
            conn.execute('''
                UPDATE transacciones_dinamicas
                SET estado = 'rechazado', gamepoint_referenceno = ?, notas = ?, fecha_procesado = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (provider_ref, provider_error, _tx_procesando_id))
            conn.commit()
            conn.close()

            _refund(user_id, precio, is_admin)
            conn_cleanup = _get_conn()
            clear_idempotent_purchase(conn_cleanup, user_id, endpoint_key, request_id)
            conn_cleanup.commit()
            conn_cleanup.close()
            return redirect_dynamic_error(f'La recarga fallo: {provider_error}. Tu saldo ha sido devuelto.', pkg['nombre'], precio)

        # 2. Get GamePoint token
        gc_token, gc_err = get_token()
        if not gc_token:
            _update_tx_error(_tx_procesando_id, 'No se pudo obtener token GP')
            _refund(user_id, precio, is_admin)
            conn_cleanup = _get_conn()
            clear_idempotent_purchase(conn_cleanup, user_id, endpoint_key, request_id)
            conn_cleanup.commit()
            conn_cleanup.close()
            return redirect_dynamic_error('Error de conexion con proveedor. Tu saldo ha sido devuelto.', pkg['nombre'], precio)

        # 3. Validate order — build input fields
        input_fields = {'input1': str(player_id)}
        if player_id2:
            input_fields['input2'] = str(player_id2)
        if servidor:
            input_fields['input3'] = str(servidor)

        validate_data = order_validate(gc_token, game['gamepoint_product_id'], input_fields)
        validate_code = (validate_data or {}).get('code')

        if validate_code != 200 or not (validate_data or {}).get('validation_token'):
            _update_tx_error(_tx_procesando_id, f"validate failed: code={validate_code}")
            _refund(user_id, precio, is_admin)
            conn_cleanup = _get_conn()
            clear_idempotent_purchase(conn_cleanup, user_id, endpoint_key, request_id)
            conn_cleanup.commit()
            conn_cleanup.close()
            err_msg = (validate_data or {}).get('message', 'Error validando orden')
            logger.error(f"[DynGame:{game['slug']}] validate failed: code={validate_code} msg={err_msg}")
            return redirect_dynamic_error(f'Error al validar: {err_msg}. Tu saldo ha sido devuelto.', pkg['nombre'], precio)

        validation_token = validate_data['validation_token']
        # validate NO devuelve ingamename según docs — solo code, message, validation_token
        ingame_name = ''
        logger.info(f"[DynGame:{game['slug']}] validate OK | player={player_id}")

        # 4. Create order
        create_data = order_create(gc_token, validation_token, gp_package_id, merchant_code)
        create_code = (create_data or {}).get('code')
        reference_no = (create_data or {}).get('referenceno', '')

        # 4.1 order/inquiry — extraer ingamename y serialkey (Gift Cards)
        # es_gift_card: True para vouchers/pins, False para recargas directas (ID)
        es_gift_card = (game.get('modo', 'id') != 'id')
        inq_data = None
        item_name = ''
        serial_key = ''
        try:
            if reference_no:
                # Retry inquiry con delay para dar tiempo a que el pedido se procese
                for _attempt in range(3):
                    if _attempt > 0:
                        time_module.sleep(1.5)
                    inq_data = order_inquiry(gc_token, reference_no)
                    ingame_name = (inq_data or {}).get('ingamename') or ''
                    item_name = (inq_data or {}).get('item') or ''
                    # Solo extraer serial para Gift Cards/vouchers, no para recargas directas
                    if es_gift_card:
                        serial_key = _extract_serial_from_inquiry(inq_data)
                    logger.info(f"[DynGame:{game['slug']}] inquiry attempt {_attempt+1}: ingamename='{ingame_name}' | item='{item_name}' | serialkey='{serial_key}' | all_fields={list((inq_data or {}).keys())}")
                    if ingame_name or serial_key:
                        break
                # Limpiar HTML del item (ej: "Blood Strike<br />300 + 20 Gold")
                if item_name:
                    item_name = re.sub(r'<[^>]+>', ' ', item_name).strip()
                    item_name = ' '.join(item_name.split())
        except Exception as e:
            logger.error(f"[DynGame:{game['slug']}] inquiry FAILED: {e}")

        _duration = round(time_module.time() - _start, 1)

        if create_code in (100, 101):
            inquiry_state, inquiry_note = _classify_gamepoint_inquiry(
                inq_data if reference_no else None,
                serial_key,
                is_gift_card=es_gift_card,
            )
            transaccion_id = merchant_code

            if not _is_real_serial(serial_key):
                serial_key = ''

            if inquiry_state == 'failed':
                err_msg = inquiry_note or (create_data or {}).get('message') or 'GamePoint rechazo la recarga'
                logger.error(f"[DynGame:{game['slug']}] inquiry reported failure: {err_msg} | user={user_id} ref={reference_no}")

                conn = _get_conn()
                conn.execute('''
                    UPDATE transacciones_dinamicas
                    SET estado = 'rechazado', gamepoint_referenceno = ?, ingame_name = ?, pin_entregado = ?,
                        notas = ?, fecha_procesado = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (reference_no, ingame_name or None, serial_key or None, err_msg, _tx_procesando_id))
                _upsert_dynamic_general_transaction(conn, _tx_procesando_id, duracion_segundos=_duration)
                conn.commit()
                conn.close()

                _refund(user_id, precio, is_admin)
                conn_cleanup = _get_conn()
                clear_idempotent_purchase(conn_cleanup, user_id, endpoint_key, request_id)
                conn_cleanup.commit()
                conn_cleanup.close()
                return redirect_dynamic_error(f'La recarga fallo: {err_msg}. Tu saldo ha sido devuelto.', pkg['nombre'], precio)

            if inquiry_state == 'success':
                estado_db = 'aprobado'
            elif es_gift_card:
                estado_db = 'pendiente'
            else:
                estado_db = 'procesando'

            conn = _get_conn()
            # Idempotencia: si ya existe OTRA transacción con este gamepoint_referenceno, no duplicar
            if reference_no:
                dup_td = conn.execute(
                    'SELECT id FROM transacciones_dinamicas WHERE gamepoint_referenceno = ? AND id != ?',
                    (reference_no, _tx_procesando_id)
                ).fetchone()
                if dup_td:
                    if serial_key:
                        estado_txt = 'completado'
                    elif estado_db == 'pendiente':
                        estado_txt = 'pendiente_serial'
                    elif estado_db == 'procesando':
                        estado_txt = 'procesando'
                    else:
                        estado_txt = 'completado'

                    success_payload = {
                        'paquete_nombre': pkg['nombre'],
                        'monto_compra': precio,
                        'numero_control': numero_control,
                        'transaccion_id': transaccion_id,
                        'player_id': player_id,
                        'player_id2': player_id2,
                        'servidor': servidor,
                        'player_name': ingame_name,
                        'estado': estado_txt,
                        'gamepoint_ref': reference_no,
                        'serial_key': serial_key,
                    }
                    conn.execute('DELETE FROM transacciones_dinamicas WHERE id = ?', (_tx_procesando_id,))
                    if estado_txt == 'completado':
                        complete_idempotent_purchase(conn, user_id, endpoint_key, request_id, success_payload, transaccion_id, numero_control)
                    else:
                        save_processing_idempotent_purchase(conn, user_id, endpoint_key, request_id, success_payload, transaccion_id, numero_control)
                    conn.commit()
                    conn.close()
                    session[f'compra_dyn_{slug}_exitosa'] = success_payload
                    return redirect(f'/juego/d/{slug}?compra=exitosa')

            # Actualizar registro y reflejarlo en el historial general.
            conn.execute('''
                UPDATE transacciones_dinamicas
                SET estado = ?, gamepoint_referenceno = ?, ingame_name = ?, pin_entregado = ?,
                    notas = ?, fecha_procesado = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (estado_db, reference_no, ingame_name, serial_key or None, inquiry_note or None, _tx_procesando_id))

            if estado_db == 'aprobado':
                _app.sync_dynamic_purchase_records(conn, _tx_procesando_id)
            else:
                _upsert_dynamic_general_transaction(conn, _tx_procesando_id, duracion_segundos=_duration)

            if serial_key:
                estado_txt = 'completado'
            elif estado_db == 'pendiente':
                estado_txt = 'pendiente_serial'
            elif estado_db == 'procesando':
                estado_txt = 'procesando'
            else:
                estado_txt = 'completado'
            logger.info(f"[DynGame:{game['slug']}] storing in session: player_name='{ingame_name}' | player_id={player_id} | ref={reference_no}")
            success_payload = {
                'paquete_nombre': pkg['nombre'],
                'monto_compra': precio,
                'numero_control': numero_control,
                'transaccion_id': transaccion_id,
                'player_id': player_id,
                'player_id2': player_id2,
                'servidor': servidor,
                'player_name': ingame_name,
                'estado': estado_txt,
                'gamepoint_ref': reference_no,
                'serial_key': serial_key,
            }
            if estado_db == 'aprobado':
                complete_idempotent_purchase(conn, user_id, endpoint_key, request_id, success_payload, transaccion_id, numero_control)
            else:
                save_processing_idempotent_purchase(conn, user_id, endpoint_key, request_id, success_payload, transaccion_id, numero_control)
            conn.commit()
            conn.close()
            session[f'compra_dyn_{slug}_exitosa'] = success_payload
            return redirect(f'/juego/d/{slug}?compra=exitosa')

        else:
            # === FAILURE ===
            err_msg = (create_data or {}).get('message', 'Error creando orden')
            logger.error(f"[DynGame:{game['slug']}] create failed: code={create_code} msg={err_msg} | user={user_id}")

            conn = _get_conn()
            conn.execute('''
                UPDATE transacciones_dinamicas
                SET estado = 'rechazado', gamepoint_referenceno = ?, notas = ?,
                    fecha_procesado = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (reference_no, err_msg, _tx_procesando_id))
            conn.commit()
            conn.close()

            _refund(user_id, precio, is_admin)
            conn_cleanup = _get_conn()
            clear_idempotent_purchase(conn_cleanup, user_id, endpoint_key, request_id)
            conn_cleanup.commit()
            conn_cleanup.close()
            return redirect_dynamic_error(f'La recarga fallo: {err_msg}. Tu saldo ha sido devuelto.', pkg['nombre'], precio)

    except Exception as e:
        logger.error(f"[DynGame:{game['slug']}] Error general: {str(e)}")
        _update_tx_error(_tx_procesando_id, str(e)[:500])
        _refund(user_id, precio, is_admin)
        try:
            conn_cleanup = _get_conn()
            clear_idempotent_purchase(conn_cleanup, user_id, endpoint_key, request_id)
            conn_cleanup.commit()
            conn_cleanup.close()
        except Exception:
            pass
        return redirect_dynamic_error('Error al procesar la compra. Tu saldo ha sido devuelto.', pkg['nombre'], precio)


def _is_real_serial(s):
    """True si 's' parece un código voucher real y no un código de estado de API."""
    if not s:
        return False
    s = str(s).strip()
    if re.fullmatch(r'-?\d+(?:\.\d+)?', s):
        return False
    # Los códigos de estado son puramente numéricos y cortos (ej: '100', '101')
    if s.isdigit() and len(s) <= 6:
        return False
    return len(s) >= 4


# Campos que NO son seriales (metadatos de la respuesta)
_NON_SERIAL_FIELDS = {
    'code', 'message', 'referenceno', 'merchantcode', 'merchant_code',
    'ingamename', 'ingame_name', 'item', 'productid', 'product_id',
    'packageid', 'package_id', 'status', 'orderid', 'order_id',
    'userid', 'user_id', 'token', 'timestamp', 'date', 'time', 'amount',
}


def _extract_serial_from_inquiry(inq_data):
    """
    Extrae el código/serial de gift card de la respuesta de order_inquiry.
    Prueba campos conocidos primero; si no encuentra nada, escanea todos los
    valores de la respuesta buscando uno que parezca un código real.
    """
    if not inq_data:
        return ''
    # 1. Campos conocidos por nombre (orden de prioridad)
    known = [
        'serialkey', 'serial_key', 'pincode', 'pin_code', 'voucher',
        'giftcode', 'gift_code', 'giftcardcode', 'gift_card_code',
        'cardcode', 'card_code', 'redeemcode', 'redeem_code',
        'redemptioncode', 'redemption_code', 'coupon', 'couponcode',
        'coupon_code', 'serial', 'pin', 'code',
    ]
    for field in known:
        val = str(inq_data.get(field) or '').strip()
        if _is_real_serial(val):
            return val
    # 2. Fallback genérico: primer valor de cadena que parezca un serial real
    for key, val in inq_data.items():
        if key.lower() in _NON_SERIAL_FIELDS:
            continue
        val_str = str(val or '').strip()
        if _is_real_serial(val_str):
            logger.info(f"[ExtractSerial] serial encontrado en campo inesperado '{key}': '{val_str}'")
            return val_str
    return ''


def _should_recheck_dynamic_row(row):
    estado = str(row['estado'] or '').strip().lower()
    modo = str(row['modo'] or 'id').strip().lower()
    serial_key = str(row['pin_entregado'] or '').strip()

    if estado in ('pendiente', 'procesando'):
        return True

    if estado == 'aprobado' and modo != 'id' and not _is_real_serial(serial_key):
        return True

    return False


def poll_pending_dynamic_transactions():
    """
    Consulta GamePoint para transacciones de Gift Cards:
    - Estado 'pendiente': aún esperando serial
    - Estado 'aprobado' con serial falso (numérico corto = código de estado API)
    Actualiza a 'aprobado' y guarda el serial/código cuando está disponible.
    Llamar desde un hilo de fondo cada 60 segundos.
    """
    try:
        conn = _get_conn()
        cutoff_ts = datetime.utcnow() - timedelta(hours=48)
        rows = conn.execute('''
                    SELECT td.id, td.transaccion_id, td.gamepoint_referenceno, td.juego_id,
                       td.usuario_id, td.monto, td.estado, td.pin_entregado, td.numero_control,
                       td.request_id, td.player_id, td.player_id2, td.servidor, td.ingame_name, td.notas,
                        jd.nombre as juego_nombre, jd.slug, jd.modo, pd.nombre as paquete_nombre
            FROM transacciones_dinamicas td
            JOIN juegos_dinamicos jd ON td.juego_id = jd.id
                    JOIN paquetes_dinamicos pd ON pd.id = td.paquete_id
            WHERE td.gamepoint_referenceno IS NOT NULL
              AND td.gamepoint_referenceno != ''
                            AND td.fecha >= ?
            ''', (cutoff_ts,)).fetchall()
        conn.close()
    except Exception as e:
        logger.error(f"[DynGame Poll] Error consultando pendientes: {e}")
        return

    rows = [row for row in rows if _should_recheck_dynamic_row(row)]

    if not rows:
        return

    logger.info(f"[DynGame Poll] {len(rows)} transacciones pendientes a verificar")

    get_token, gp_post, order_validate, order_create, order_inquiry = _gp_helpers()
    import app as _app

    try:
        gc_token, gc_err = get_token()
        if not gc_token:
            logger.warning(f"[DynGame Poll] No se pudo obtener token GP: {gc_err}")
            return
    except Exception as e:
        logger.error(f"[DynGame Poll] Error obteniendo token: {e}")
        return

    for row in rows:
        try:
            inq_data = order_inquiry(gc_token, row['gamepoint_referenceno'])
            serial_key = _extract_serial_from_inquiry(inq_data)
            inquiry_state, inquiry_note = _classify_gamepoint_inquiry(
                inq_data,
                serial_key,
                is_gift_card=(str(row['modo'] or 'id').strip().lower() != 'id'),
            )
            logger.info(f"[DynGame Poll] tx={row['transaccion_id']} ref={row['gamepoint_referenceno']} state={inquiry_state} serial='{serial_key}' fields={list((inq_data or {}).keys())}")

            if inquiry_state == 'failed':
                conn2 = _get_conn()
                conn2.execute('''
                    UPDATE transacciones_dinamicas
                    SET estado = 'rechazado', notas = ?, fecha_procesado = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (inquiry_note or 'Error reportado por GamePoint', row['id']))
                _upsert_dynamic_general_transaction(conn2, row['id'])
                if not _app._is_admin_target_user(conn2, row['usuario_id']):
                    _refund_without_session(conn2, row['usuario_id'], abs(float(row['monto'] or 0.0)))
                if str(row['request_id'] or '').strip():
                    _app.clear_idempotent_purchase(conn2, row['usuario_id'], f"dynamic_game:{row['slug']}", str(row['request_id']).strip())
                conn2.commit()
                conn2.close()
                logger.info(f"[DynGame Poll] ❌ tx={row['transaccion_id']} RECHAZADO por inquiry")
            elif inquiry_state == 'success':
                conn2 = _get_conn()
                conn2.execute('''
                    UPDATE transacciones_dinamicas
                    SET estado = 'aprobado', pin_entregado = ?, ingame_name = COALESCE(NULLIF(?, ''), ingame_name), notas = ?, fecha_procesado = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (
                    serial_key if _is_real_serial(serial_key) else None,
                    str((inq_data or {}).get('ingamename') or '').strip(),
                    inquiry_note or None,
                    row['id'],
                ))
                _app.sync_dynamic_purchase_records(conn2, row['id'])
                if str(row['request_id'] or '').strip():
                    success_row = dict(row)
                    success_row['estado'] = 'aprobado'
                    success_row['pin_entregado'] = serial_key if _is_real_serial(serial_key) else ''
                    success_row['ingame_name'] = str((inq_data or {}).get('ingamename') or '').strip() or str(row['ingame_name'] or '').strip()
                    success_row['notas'] = inquiry_note or ''
                    success_payload = _build_existing_dynamic_payload(success_row, success_row.get('paquete_nombre') or '')
                    _app.complete_idempotent_purchase(
                        conn2,
                        row['usuario_id'],
                        f"dynamic_game:{row['slug']}",
                        str(row['request_id']).strip(),
                        success_payload,
                        row['transaccion_id'],
                        row['numero_control'],
                    )
                conn2.commit()
                conn2.close()
                logger.info(f"[DynGame Poll] ✅ tx={row['transaccion_id']} APROBADO")
            else:
                conn2 = _get_conn()
                pending_state = 'pendiente' if str(row['modo'] or 'id').strip().lower() != 'id' else 'procesando'
                conn2.execute('''
                    UPDATE transacciones_dinamicas
                    SET estado = ?, notas = ?, fecha_procesado = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (pending_state, inquiry_note or 'Esperando confirmacion de GamePoint', row['id']))
                _upsert_dynamic_general_transaction(conn2, row['id'])
                if str(row['request_id'] or '').strip():
                    pending_row = dict(row)
                    pending_row['estado'] = pending_state
                    pending_row['notas'] = inquiry_note or 'Esperando confirmacion de GamePoint'
                    processing_payload = _build_existing_dynamic_payload(pending_row, pending_row.get('paquete_nombre') or '')
                    _app.save_processing_idempotent_purchase(
                        conn2,
                        row['usuario_id'],
                        f"dynamic_game:{row['slug']}",
                        str(row['request_id']).strip(),
                        processing_payload,
                        row['transaccion_id'],
                        row['numero_control'],
                    )
                conn2.commit()
                conn2.close()
                logger.debug(f"[DynGame Poll] tx={row['transaccion_id']} sigue pendiente")

            time_module.sleep(0.5)  # Rate limit entre consultas
        except Exception as e:
            logger.error(f"[DynGame Poll] Error procesando tx {row['transaccion_id']}: {e}")


def _update_tx_error(tx_id, notas=''):
    """Mark a 'procesando' transaction as 'error'."""
    if not tx_id:
        return
    try:
        conn = _get_conn()
        conn.execute(
            'UPDATE transacciones_dinamicas SET estado = ?, notas = ?, fecha_procesado = CURRENT_TIMESTAMP WHERE id = ?',
            ('error', str(notas)[:500], tx_id)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _refund(user_id, precio, is_admin):
    """Refund balance to user."""
    if is_admin:
        return
    try:
        conn = _get_conn()
        conn.execute('UPDATE usuarios SET saldo = saldo + ? WHERE id = ?', (precio, user_id))
        conn.commit()
        conn.close()
        session['saldo'] = session.get('saldo', 0) + precio
        logger.info(f"[DynGame] Saldo ${precio} reembolsado al usuario {user_id}")
    except Exception as e:
        logger.error(f"[DynGame] Error reembolsando: {e}")
