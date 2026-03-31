from flask import Blueprint, jsonify, request
import os
import re
from datetime import datetime, timedelta
import pytz
from pg_compat import get_db_connection, table_exists as pg_table_exists

bp = Blueprint('admin_stats', __name__)


def get_conn():
    return get_db_connection()


def table_exists(conn, table_name: str) -> bool:
    return pg_table_exists(conn, table_name)


def get_admin_exclusions():
    ids_env = os.environ.get('ADMIN_USER_IDS', '').strip()
    emails_env = os.environ.get('ADMIN_EMAILS', '').strip()
    single_email = os.environ.get('ADMIN_EMAIL', '').strip()
    ids = []
    emails = []
    if ids_env:
        for part in ids_env.split(','):
            part = part.strip()
            if part.isdigit():
                ids.append(int(part))
    if emails_env:
        for part in emails_env.split(','):
            part = part.strip()
            if part:
                emails.append(part)
    # Fallback/alias: ADMIN_EMAIL
    if single_email and single_email not in emails:
        emails.append(single_email)
    return ids, emails


def _parse_utc_datetime(raw_value):
    if raw_value is None:
        return None
    if isinstance(raw_value, datetime):
        dt_value = raw_value
    else:
        raw_text = str(raw_value).strip()
        if not raw_text:
            return None
        try:
            dt_value = datetime.fromisoformat(raw_text.replace('Z', '+00:00'))
        except Exception:
            try:
                dt_value = datetime.strptime(raw_text.split('.')[0], '%Y-%m-%d %H:%M:%S')
            except Exception:
                return None
    if dt_value.tzinfo is None:
        return pytz.utc.localize(dt_value)
    return dt_value.astimezone(pytz.utc)


def _is_truthy_db_value(value):
    if isinstance(value, str):
        return value.strip().lower() in ('1', 'true', 't', 'yes', 'y', 'on')
    return bool(value)


def _load_cost_map(conn):
    cost_map = {}
    if not table_exists(conn, 'precios_compra'):
        return cost_map
    try:
        rows = conn.execute(
            "SELECT juego, paquete_id, precio_compra FROM precios_compra WHERE activo = 1"
        ).fetchall()
        for row in rows:
            cost_map[(str(row['juego']), int(row['paquete_id']))] = float(row['precio_compra'] or 0)
    except Exception:
        return {}
    return cost_map


def _resolve_whitelabel_game_key(game_type, package_id):
    game_type = str(game_type or '').strip().lower()
    if game_type == 'bloodstriker':
        return 'bloodstriker'
    if game_type == 'freefire_id':
        return 'freefire_id'
    if game_type != 'dynamic':
        return None

    try:
        from dynamic_games import get_dynamic_game_by_id, get_dynamic_package_by_id

        pkg = get_dynamic_package_by_id(int(package_id))
        if not pkg:
            return None
        game = get_dynamic_game_by_id(pkg.get('juego_id'))
        slug = str((game or {}).get('slug') or '').strip()
        if not slug:
            return None
        return f'dyn_{slug}'
    except Exception:
        return None


def _merge_profit_series(*series_groups):
    merged = {}
    for series in series_groups:
        for item in series or []:
            day = str(item.get('day') or '').strip()
            if not day:
                continue
            merged[day] = merged.get(day, 0.0) + float(item.get('profit') or 0.0)
    return [
        {'day': day, 'profit': round(amount, 6)}
        for day, amount in sorted(merged.items())
    ]


def _overlay_profit_series(base_series, override_series):
    merged = {
        str(item.get('day') or '').strip(): float(item.get('profit') or 0.0)
        for item in base_series or []
        if str(item.get('day') or '').strip()
    }
    for item in override_series or []:
        day = str(item.get('day') or '').strip()
        if not day:
            continue
        merged[day] = float(item.get('profit') or 0.0)
    return [
        {'day': day, 'profit': round(amount, 6)}
        for day, amount in sorted(merged.items())
    ]


def _extract_dashboard_quantity(package_name, pin_text):
    raw_name = str(package_name or '').strip()
    match = re.search(r'\sx(\d+)\s*$', raw_name, re.IGNORECASE)
    if match:
        try:
            return max(1, int(match.group(1)))
        except Exception:
            pass

    raw_pin = str(pin_text or '')
    pin_lines = [
        line.strip() for line in raw_pin.replace('\r', '').split('\n')
        if line.strip() and not line.strip().startswith('[') and not line.strip().startswith('ID:')
    ]
    if len(pin_lines) > 1:
        return len(pin_lines)
    return 1


def _extract_base_package_amount(package_name):
    raw_name = str(package_name or '').strip()
    if not raw_name:
        return None

    amount_match = re.search(r'(\d{1,3}(?:[\.,]\d{3})+|\d+)', raw_name)
    if not amount_match:
        return None

    raw_amount = amount_match.group(1)
    normalized_amount = re.sub(r'[^\d]', '', raw_amount)
    if not normalized_amount:
        return None
    try:
        return int(normalized_amount)
    except Exception:
        return None


def _normalize_dashboard_package_name(package_name, item_name):
    raw_name = str(package_name or '').strip()
    raw_name = re.sub(r'\sx\d+\s*$', '', raw_name, flags=re.IGNORECASE)
    raw_name = re.sub(r'\s*\([^)]*\)\s*$', '', raw_name)
    raw_name = raw_name.replace('"', '').replace("'", '').replace('“', '').replace('”', '').strip()
    if ' - ' in raw_name:
        _, raw_name = raw_name.split(' - ', 1)
        raw_name = raw_name.strip()

    lower_name = raw_name.lower()
    if item_name in ('Free Fire', 'Free Fire LATAM', 'Blood Striker'):
        if any(word in lower_name for word in ['tarjeta', 'pase', 'elite', 'cofre']):
            return raw_name
        base_amount = _extract_base_package_amount(raw_name)
        if base_amount is not None:
            return str(base_amount)
    return raw_name or 'Paquete'


def _load_dynamic_game_names(conn):
    if not table_exists(conn, 'juegos_dinamicos'):
        return []
    try:
        rows = conn.execute('SELECT nombre FROM juegos_dinamicos').fetchall()
        return [str(row['nombre'] or '').strip() for row in rows if str(row['nombre'] or '').strip()]
    except Exception:
        return []


def _infer_dashboard_item_name(package_name, dynamic_game_names):
    raw_name = str(package_name or '').strip()
    lower_name = raw_name.lower()
    if '🪙' in raw_name or 'blood' in lower_name:
        return 'Blood Striker'
    for dynamic_name in dynamic_game_names:
        if raw_name.startswith(dynamic_name + ' - ') or raw_name == dynamic_name:
            return dynamic_name
    if '💎' in raw_name or 'free fire' in lower_name or 'ff id' in lower_name or 'tarjeta' in lower_name:
        if any(x in raw_name for x in ['110 💎', '341 💎', '572 💎', '1.166 💎', '2.376 💎', '6.138 💎']) or 'tarjeta' in lower_name:
            return 'Free Fire LATAM'
        return 'Free Fire'
    return 'Otros'


def _load_dashboard_profit_catalog(conn):
    cost_map = _load_cost_map(conn)
    catalog = {}

    def add_entry(game_key, item_name, package_id, raw_package_name, sale_price):
        try:
            package_id = int(package_id)
            sale_price = float(sale_price or 0.0)
        except Exception:
            return
        profit_unit = round(sale_price - float(cost_map.get((game_key, package_id), 0.0)), 6)
        normalized_package = _normalize_dashboard_package_name(raw_package_name, item_name)
        key = (str(item_name or '').strip(), normalized_package)
        catalog.setdefault(key, []).append({
            'profit_unit': profit_unit,
            'sale_price': sale_price,
            'game_key': str(game_key or '').strip(),
            'package_id': package_id,
        })

    table_specs = [
        ('precios_freefire_id', 'freefire_id', 'Free Fire'),
        ('precios_freefire_global', 'freefire_global', 'Free Fire'),
        ('precios_paquetes', 'freefire_latam', 'Free Fire LATAM'),
        ('precios_bloodstriker', 'bloodstriker', 'Blood Striker'),
    ]
    for table_name, game_key, item_name in table_specs:
        if not table_exists(conn, table_name):
            continue
        try:
            rows = conn.execute(f'SELECT id, nombre, precio FROM {table_name}').fetchall()
        except Exception:
            continue
        for row in rows:
            add_entry(game_key, item_name, row['id'], row['nombre'], row['precio'])

    if table_exists(conn, 'paquetes_dinamicos') and table_exists(conn, 'juegos_dinamicos'):
        try:
            rows = conn.execute(
                '''
                SELECT pd.id, pd.nombre, pd.precio, jd.nombre AS juego_nombre, jd.slug
                FROM paquetes_dinamicos pd
                JOIN juegos_dinamicos jd ON jd.id = pd.juego_id
                '''
            ).fetchall()
            for row in rows:
                item_name = str(row['juego_nombre'] or '').strip()
                slug = str(row['slug'] or '').strip()
                if not item_name or not slug:
                    continue
                add_entry(f'dyn_{slug}', item_name, row['id'], row['nombre'], row['precio'])
        except Exception:
            pass

    return catalog


def _resolve_dashboard_profit_unit(catalog, item_name, package_name, sale_unit):
    candidates = catalog.get((str(item_name or '').strip(), str(package_name or '').strip()), [])
    if not candidates:
        return None

    try:
        sale_unit = float(sale_unit or 0.0)
    except Exception:
        sale_unit = 0.0

    exact_match = None
    nearest_match = None
    nearest_delta = None
    for candidate in candidates:
        delta = abs(float(candidate.get('sale_price') or 0.0) - sale_unit)
        if delta <= 0.011:
            exact_match = candidate
            break
        if nearest_delta is None or delta < nearest_delta:
            nearest_match = candidate
            nearest_delta = delta

    chosen = exact_match or nearest_match
    if not chosen:
        return None
    return float(chosen.get('profit_unit') or 0.0)


def _is_dashboard_business_sale_for_admin(row):
    try:
        saldo_antes = float(row['saldo_antes'] or 0.0)
        saldo_despues = float(row['saldo_despues'] or 0.0)
    except Exception:
        saldo_antes = 0.0
        saldo_despues = 0.0
    pin_text = str(row['pin'] or '').strip()
    return pin_text.startswith('ID:') and abs(saldo_antes) < 0.000001 and abs(saldo_despues) < 0.000001


def _should_exclude_history_row_profit(row, admin_ids, admin_emails):
    user_id = row['usuario_id']
    email = str(row['correo'] or '').strip().lower()
    is_admin_user = user_id in admin_ids or email in admin_emails
    is_no_profit_user = _is_truthy_db_value(row['sin_ganancia'])

    if not is_admin_user and not is_no_profit_user:
        return False

    # Keep business sales that are only tracked under admin-like accounts
    # without consuming a user wallet balance.
    if _is_dashboard_business_sale_for_admin(row):
        return False

    return True


def _load_dashboard_sales_rows(conn, start_utc: str, end_utc: str, tz_name: str = 'America/Caracas'):
    if not table_exists(conn, 'historial_compras'):
        return []

    tz = pytz.timezone(tz_name)
    start_dt = _parse_utc_datetime(start_utc)
    end_dt = _parse_utc_datetime(end_utc)
    if start_dt is None or end_dt is None:
        return []

    start_day = start_dt.astimezone(tz).date().isoformat()
    end_day = end_dt.astimezone(tz).date().isoformat()

    return conn.execute(
        '''
        SELECT h.usuario_id, h.monto, h.fecha, h.paquete_nombre, h.pin,
               h.saldo_antes, h.saldo_despues, u.correo, u.sin_ganancia,
               DATE(h.fecha, '-4 hours') AS local_day
        FROM historial_compras h
        LEFT JOIN usuarios u ON u.id = h.usuario_id
        WHERE h.tipo_evento = 'compra'
          AND DATE(h.fecha, '-4 hours') >= ?
          AND DATE(h.fecha, '-4 hours') < ?
        ORDER BY h.fecha
        ''',
        (start_day, end_day)
    ).fetchall()


def compute_dashboard_profit_by_day(conn, start_utc: str, end_utc: str, tz_name: str = 'America/Caracas'):
    if not table_exists(conn, 'historial_compras') or not table_exists(conn, 'usuarios') or not table_exists(conn, 'precios_compra'):
        return []

    admin_ids, admin_emails = get_admin_exclusions()
    admin_ids = set(admin_ids)
    admin_emails = {str(email).strip().lower() for email in admin_emails if str(email).strip()}
    dynamic_game_names = _load_dynamic_game_names(conn)
    profit_catalog = _load_dashboard_profit_catalog(conn)
    rows = _load_dashboard_sales_rows(conn, start_utc, end_utc, tz_name)

    grouped_sales = {}
    for row in rows:
        try:
            if _should_exclude_history_row_profit(row, admin_ids, admin_emails):
                continue

            package_name = str(row['paquete_nombre'] or '').strip()
            if not package_name:
                continue

            quantity = max(1, _extract_dashboard_quantity(package_name, row['pin']))
            item_name = _infer_dashboard_item_name(package_name, dynamic_game_names)
            normalized_package = _normalize_dashboard_package_name(package_name, item_name)
            local_day = str(row['local_day'] or '').strip()
            if not local_day:
                continue

            grouped_key = (local_day, item_name, normalized_package)
            group = grouped_sales.setdefault(grouped_key, {
                'quantity': 0,
                'sale_total': 0.0,
            })
            group['quantity'] += quantity
            group['sale_total'] += abs(float(row['monto'] or 0.0))
        except Exception:
            continue

    profit_by_day = {}
    for (local_day, item_name, normalized_package), group in grouped_sales.items():
        try:
            quantity = max(1, int(group.get('quantity') or 1))
            sale_total = float(group.get('sale_total') or 0.0)
            sale_unit = round(sale_total / quantity, 6) if quantity else sale_total
            profit_unit = _resolve_dashboard_profit_unit(profit_catalog, item_name, normalized_package, sale_unit)
            if profit_unit is None:
                continue
            profit_by_day[local_day] = profit_by_day.get(local_day, 0.0) + round(profit_unit * quantity, 6)
        except Exception:
            continue

    return [
        {'day': day, 'profit': round(amount, 6)}
        for day, amount in sorted(profit_by_day.items())
    ]


def _load_profit_daily_aggregate_rows(conn, start_day: str, end_day: str):
    if not table_exists(conn, 'profit_daily_aggregate'):
        return []
    rows = conn.execute(
        "SELECT day, profit_total AS profit FROM profit_daily_aggregate WHERE day >= ? AND day < ? ORDER BY day",
        (start_day, end_day)
    ).fetchall()
    return [dict(row) for row in rows]


def sync_closed_dashboard_profit_days(conn, start_utc: str, end_utc: str, tz_name: str = 'America/Caracas'):
    if not table_exists(conn, 'profit_daily_aggregate'):
        return []

    tz = pytz.timezone(tz_name)
    today_local = datetime.now(tz).date().isoformat()
    dashboard_rows = compute_dashboard_profit_by_day(conn, start_utc, end_utc, tz_name)
    closed_days = [
        item for item in dashboard_rows
        if str(item.get('day') or '').strip() and str(item.get('day')) < today_local
    ]
    if not closed_days:
        return []

    cur = conn.cursor()
    changed = False
    for item in closed_days:
        day = str(item.get('day') or '').strip()
        total = round(float(item.get('profit') or 0.0), 6)
        existing = cur.execute(
            "SELECT profit_total FROM profit_daily_aggregate WHERE day = ?",
            (day,)
        ).fetchone()
        if existing:
            existing_total = round(float(existing['profit_total'] if hasattr(existing, 'keys') else existing[0]) or 0.0, 6)
            if abs(existing_total - total) > 0.000001:
                cur.execute(
                    "UPDATE profit_daily_aggregate SET profit_total = ?, updated_at = datetime('now') WHERE day = ?",
                    (total, day)
                )
                changed = True
        else:
            cur.execute(
                "INSERT INTO profit_daily_aggregate(day, profit_total) VALUES(?, ?)",
                (day, total)
            )
            changed = True

    if changed:
        conn.commit()
    return closed_days


def compute_admin_profit_by_day(conn, start_utc: str, end_utc: str, tz_name: str = 'America/Caracas'):
    tz = pytz.timezone(tz_name)
    start_dt = _parse_utc_datetime(start_utc)
    end_dt = _parse_utc_datetime(end_utc)
    if start_dt is None or end_dt is None:
        return []

    start_day = start_dt.astimezone(tz).date().isoformat()
    end_day = end_dt.astimezone(tz).date().isoformat()

    aggregate_rows = []
    if table_exists(conn, 'profit_daily_aggregate'):
        try:
            sync_closed_dashboard_profit_days(conn, start_utc, end_utc, tz_name)
        except Exception:
            pass
        aggregate_rows = _load_profit_daily_aggregate_rows(conn, start_day, end_day)

    dashboard_rows = compute_dashboard_profit_by_day(conn, start_utc, end_utc, tz_name)
    today_local = datetime.now(tz).date().isoformat()
    aggregate_days = {
        str(item.get('day') or '').strip()
        for item in aggregate_rows
        if str(item.get('day') or '').strip()
    }

    live_rows = []
    for item in dashboard_rows:
        day = str(item.get('day') or '').strip()
        if not day:
            continue
        if day == today_local or day not in aggregate_days:
            live_rows.append({'day': day, 'profit': round(float(item.get('profit') or 0.0), 6)})

    combined_rows = _overlay_profit_series(aggregate_rows, live_rows)
    if combined_rows:
        return combined_rows

    return compute_profit_ledger_by_day(conn, start_utc, end_utc, tz_name)


def _get_inefable_profit_config():
    ff_tipo = os.environ.get('WEBB_FF_TIPO', 'freefire_id').strip().lower()
    if ff_tipo == 'freefire_global':
        return 'freefire_global', 'precios_freefire_global'
    if ff_tipo == 'latam':
        return 'freefire_latam', 'precios_paquetes'
    return 'freefire_id', 'precios_freefire_id'


def compute_missing_inefable_profit_by_day(conn, start_utc: str, end_utc: str, tz_name: str = 'America/Caracas'):
    if not table_exists(conn, 'transacciones') or not table_exists(conn, 'precios_compra'):
        return []

    juego_key, price_table = _get_inefable_profit_config()
    if not table_exists(conn, price_table):
        return []

    tz = pytz.timezone(tz_name)
    cost_map = _load_cost_map(conn)
    package_rows = conn.execute(
        f"SELECT id, nombre FROM {price_table}"
    ).fetchall()
    package_by_name = {}
    for row in package_rows:
        package_name = str(row['nombre'] or '').strip().lower()
        if package_name and package_name not in package_by_name:
            package_by_name[package_name] = int(row['id'])

    rows = conn.execute(
        """
        SELECT t.transaccion_id, t.paquete_nombre, t.monto, t.fecha
        FROM transacciones t
        WHERE t.transaccion_id LIKE 'INEFABLE-%'
          AND t.fecha >= ?
          AND t.fecha < ?
          AND NOT EXISTS (
              SELECT 1
              FROM profit_ledger pl
              WHERE pl.transaccion_id = t.transaccion_id
          )
        ORDER BY t.fecha
        """,
        (start_utc, end_utc)
    ).fetchall()

    profit_by_day = {}
    for row in rows:
        try:
            package_name = str(row['paquete_nombre'] or '').strip().lower()
            package_id = package_by_name.get(package_name)
            if package_id is None:
                continue

            costo_unit = float(cost_map.get((juego_key, int(package_id)), 0.0))
            sale_total = abs(float(row['monto'] or 0.0))
            profit_total = round(sale_total - costo_unit, 6)
            fecha_utc = _parse_utc_datetime(row['fecha'])
            if fecha_utc is None:
                continue

            day = fecha_utc.astimezone(tz).date().isoformat()
            profit_by_day[day] = profit_by_day.get(day, 0.0) + profit_total
        except Exception:
            continue

    return [
        {'day': day, 'profit': round(amount, 6)}
        for day, amount in sorted(profit_by_day.items())
    ]


def compute_missing_connection_api_profit_by_day(conn, start_utc: str, end_utc: str, tz_name: str = 'America/Caracas'):
    if not table_exists(conn, 'transacciones') or not table_exists(conn, 'usuarios') or not table_exists(conn, 'precios_paquetes'):
        return []

    admin_ids, admin_emails = get_admin_exclusions()
    admin_ids = set(admin_ids)
    admin_emails = {str(email).strip().lower() for email in admin_emails if str(email).strip()}
    tz = pytz.timezone(tz_name)
    cost_map = _load_cost_map(conn)

    package_rows = conn.execute('SELECT id, nombre FROM precios_paquetes').fetchall()
    package_by_name = {}
    for row in package_rows:
        package_name = _normalize_dashboard_package_name(row['nombre'], 'Free Fire LATAM').strip().lower()
        if package_name and package_name not in package_by_name:
            package_by_name[package_name] = int(row['id'])

    rows = conn.execute(
        """
        SELECT t.usuario_id, t.transaccion_id, t.paquete_nombre, t.pin, t.monto, t.fecha,
               u.correo, u.sin_ganancia
        FROM transacciones t
        LEFT JOIN usuarios u ON u.id = t.usuario_id
        WHERE t.transaccion_id LIKE 'API-%'
          AND t.fecha >= ?
          AND t.fecha < ?
          AND NOT EXISTS (
              SELECT 1
              FROM profit_ledger pl
              WHERE pl.transaccion_id = t.transaccion_id
          )
        ORDER BY t.fecha
        """,
        (start_utc, end_utc)
    ).fetchall()

    profit_by_day = {}
    for row in rows:
        try:
            if row['usuario_id'] in admin_ids:
                continue
            if str(row['correo'] or '').strip().lower() in admin_emails:
                continue
            if _is_truthy_db_value(row['sin_ganancia']):
                continue

            quantity = max(1, _extract_dashboard_quantity(row['paquete_nombre'], row['pin']))
            normalized_package = _normalize_dashboard_package_name(row['paquete_nombre'], 'Free Fire LATAM').strip().lower()
            package_id = package_by_name.get(normalized_package)
            if package_id is None:
                continue

            sale_total = abs(float(row['monto'] or 0.0))
            sale_unit = round(sale_total / quantity, 6)
            costo_unit = float(cost_map.get(('freefire_latam', int(package_id)), 0.0))
            profit_total = round((sale_unit - costo_unit) * quantity, 6)
            fecha_utc = _parse_utc_datetime(row['fecha'])
            if fecha_utc is None:
                continue

            day = fecha_utc.astimezone(tz).date().isoformat()
            profit_by_day[day] = profit_by_day.get(day, 0.0) + profit_total
        except Exception:
            continue

    return [
        {'day': day, 'profit': round(amount, 6)}
        for day, amount in sorted(profit_by_day.items())
    ]


def compute_missing_whitelabel_profit_by_day(conn, start_utc: str, end_utc: str, tz_name: str = 'America/Caracas'):
    if not table_exists(conn, 'api_orders') or not table_exists(conn, 'usuarios'):
        return []

    admin_ids, admin_emails = get_admin_exclusions()
    admin_ids = set(admin_ids)
    admin_emails = {str(email).strip().lower() for email in admin_emails if str(email).strip()}
    tz = pytz.timezone(tz_name)
    cost_map = _load_cost_map(conn)

    rows = conn.execute(
        """
        SELECT ao.id, ao.usuario_id, ao.game_type, ao.package_id, ao.precio,
               COALESCE(ao.fecha_completada, ao.fecha) AS fecha,
               u.correo, u.sin_ganancia
        FROM api_orders ao
        LEFT JOIN usuarios u ON u.id = ao.usuario_id
        WHERE ao.estado = 'completada'
          AND COALESCE(ao.fecha_completada, ao.fecha) >= ?
          AND COALESCE(ao.fecha_completada, ao.fecha) < ?
          AND NOT EXISTS (
              SELECT 1
              FROM profit_ledger pl
              WHERE pl.transaccion_id = ('WL-API-' || ao.id)
          )
        ORDER BY COALESCE(ao.fecha_completada, ao.fecha)
        """,
        (start_utc, end_utc)
    ).fetchall()

    profit_by_day = {}
    for row in rows:
        try:
            if row['usuario_id'] in admin_ids:
                continue
            if str(row['correo'] or '').strip().lower() in admin_emails:
                continue
            if _is_truthy_db_value(row['sin_ganancia']):
                continue

            juego_key = _resolve_whitelabel_game_key(row['game_type'], row['package_id'])
            if not juego_key:
                continue

            costo_unit = float(cost_map.get((juego_key, int(row['package_id'])), 0.0))
            profit_total = round(float(row['precio'] or 0.0) - costo_unit, 6)
            fecha_utc = _parse_utc_datetime(row['fecha'])
            if fecha_utc is None:
                continue

            day = fecha_utc.astimezone(tz).date().isoformat()
            profit_by_day[day] = profit_by_day.get(day, 0.0) + profit_total
        except Exception:
            continue

    return [
        {'day': day, 'profit': round(amount, 6)}
        for day, amount in sorted(profit_by_day.items())
    ]


def compute_profit_ledger_base_by_day(conn, start_utc: str, end_utc: str, tz_name: str = 'America/Caracas'):
    if not table_exists(conn, 'profit_ledger') or not table_exists(conn, 'usuarios'):
        return _merge_profit_series(
            compute_missing_connection_api_profit_by_day(conn, start_utc, end_utc, tz_name),
            compute_missing_whitelabel_profit_by_day(conn, start_utc, end_utc, tz_name),
            compute_missing_inefable_profit_by_day(conn, start_utc, end_utc, tz_name)
        )

    admin_ids, admin_emails = get_admin_exclusions()
    admin_ids = set(admin_ids)
    admin_emails = {str(email).strip().lower() for email in admin_emails if str(email).strip()}
    tz = pytz.timezone(tz_name)
    rows = conn.execute(
        """
        SELECT pl.usuario_id, pl.profit_total, pl.fecha, pl.transaccion_id, u.correo, u.sin_ganancia
        FROM profit_ledger pl
        LEFT JOIN usuarios u ON u.id = pl.usuario_id
        WHERE pl.fecha >= ? AND pl.fecha < ?
        ORDER BY pl.fecha
        """,
        (start_utc, end_utc)
    ).fetchall()

    profit_by_day = {}
    for row in rows:
        try:
            transaccion_id = str(row['transaccion_id'] or '').strip()
            is_inefable_sale = transaccion_id.startswith('INEFABLE-')
            if not is_inefable_sale:
                if row['usuario_id'] in admin_ids:
                    continue
                if str(row['correo'] or '').strip().lower() in admin_emails:
                    continue
                if _is_truthy_db_value(row['sin_ganancia']):
                    continue

            profit_total = float(row['profit_total'] or 0)
            fecha_utc = _parse_utc_datetime(row['fecha'])
            if fecha_utc is None:
                continue
            day = fecha_utc.astimezone(tz).date().isoformat()
            profit_by_day[day] = profit_by_day.get(day, 0.0) + profit_total
        except Exception:
            continue

    ledger_rows = [
        {'day': day, 'profit': round(amount, 6)}
        for day, amount in sorted(profit_by_day.items())
    ]
    missing_connection_rows = compute_missing_connection_api_profit_by_day(conn, start_utc, end_utc, tz_name)
    missing_whitelabel_rows = compute_missing_whitelabel_profit_by_day(conn, start_utc, end_utc, tz_name)
    missing_inefable_rows = compute_missing_inefable_profit_by_day(conn, start_utc, end_utc, tz_name)
    return _merge_profit_series(ledger_rows, missing_connection_rows, missing_whitelabel_rows, missing_inefable_rows)


def compute_profit_ledger_by_day(conn, start_utc: str, end_utc: str, tz_name: str = 'America/Caracas'):
    tz = pytz.timezone(tz_name)
    base_rows = compute_profit_ledger_base_by_day(conn, start_utc, end_utc, tz_name)

    aggregate_rows = []
    if table_exists(conn, 'profit_daily_aggregate'):
        try:
            sync_closed_dashboard_profit_days(conn, start_utc, end_utc, tz_name)
        except Exception:
            pass

        start_dt = _parse_utc_datetime(start_utc)
        end_dt = _parse_utc_datetime(end_utc)
        if start_dt is not None and end_dt is not None:
            start_day = start_dt.astimezone(tz).date().isoformat()
            end_day = end_dt.astimezone(tz).date().isoformat()
            aggregate_rows = _load_profit_daily_aggregate_rows(conn, start_day, end_day)

    dashboard_today = []
    today_local = datetime.now(tz).date().isoformat()
    for item in compute_dashboard_profit_by_day(conn, start_utc, end_utc, tz_name):
        day = str(item.get('day') or '').strip()
        if day == today_local:
            dashboard_today.append(item)

    merged_rows = _overlay_profit_series(base_rows, aggregate_rows)
    return _overlay_profit_series(merged_rows, dashboard_today)


def compute_legacy_profit_by_day(conn, start_utc: str, end_utc: str):
    admin_ids, admin_emails = get_admin_exclusions()
    params = [start_utc, end_utc]
    filters = []
    if admin_ids:
        placeholders = ','.join('?' for _ in admin_ids)
        filters.append(f"u.id NOT IN ({placeholders})")
        params.extend(admin_ids)
    if admin_emails:
        placeholders = ','.join('?' for _ in admin_emails)
        filters.append(f"u.correo NOT IN ({placeholders})")
        params.extend(admin_emails)
    # Excluir cuentas sin_ganancia
    filters.append("COALESCE(u.sin_ganancia,FALSE)=FALSE")
    where_ex = (" AND " + " AND ".join(filters)) if filters else ""

    # Traer transacciones en rango, excluyendo admin y sin_ganancia
    tx_rows = conn.execute(
        f"""
        SELECT t.usuario_id, t.monto, t.fecha
        FROM transacciones t
        JOIN usuarios u ON u.id = t.usuario_id
        WHERE t.fecha >= ? AND t.fecha < ? {where_ex}
        """,
        params
    ).fetchall()

    # Mapear precios por juego
    def load_price_map(table_name, juego):
        lst = conn.execute(f"SELECT id, precio FROM {table_name}").fetchall()
        return [(row['id'], float(row['precio']), juego) for row in lst]

    prices = []
    try:
        prices.extend(load_price_map('precios_paquetes', 'freefire_latam'))
    except Exception:
        pass
    try:
        prices.extend(load_price_map('precios_freefire_global', 'freefire_global'))
    except Exception:
        pass
    try:
        prices.extend(load_price_map('precios_bloodstriker', 'bloodstriker'))
    except Exception:
        pass
    try:
        prices.extend(load_price_map('precios_freefire_id', 'freefire_id'))
    except Exception:
        pass

    # Costos por juego/paquete
    cost_map = {}
    try:
        for row in conn.execute("SELECT juego, paquete_id, precio_compra FROM precios_compra WHERE activo = 1"):
            cost_map[(row['juego'], row['paquete_id'])] = float(row['precio_compra'])
    except Exception:
        pass

    # Helper para encontrar paquete por monto (tolerancia 0.01)
    def match_package_by_amount(amount):
        best = None
        for pid, precio, juego in prices:
            if abs(amount - precio) < 0.011:  # ligera tolerancia
                best = (pid, precio, juego)
                break
        return best

    # Agrupar por día
    profit_by_day = {}
    for tx in tx_rows:
        try:
            # Considerar monto de venta como valor absoluto
            sale = abs(float(tx['monto'] or 0.0))
            if sale <= 0:
                continue
            match = match_package_by_amount(sale)
            if not match:
                continue
            pid, precio_vta, juego = match
            costo = cost_map.get((juego, pid), 0.0)
            profit = max(precio_vta - float(costo), 0.0)
            day = str(tx['fecha'])[:10]
            profit_by_day[day] = profit_by_day.get(day, 0.0) + profit
        except Exception:
            continue

    # Convertir a lista ordenada
    out = [{'day': day, 'profit': round(amount, 6)} for day, amount in sorted(profit_by_day.items())]
    return out


def tz_ranges(tz_name: str):
    tz = pytz.timezone(tz_name)
    now_local = datetime.now(tz)
    today_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today_start.replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)
    prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
    return {
        'today_start': today_start,
        'today_end': today_start + timedelta(days=1),
        'yesterday_start': today_start - timedelta(days=1),
        'yesterday_end': today_start,
        'dby_start': today_start - timedelta(days=2),
        'dby_end': today_start - timedelta(days=1),
        'week_start': today_start - timedelta(days=6),
        'week_end': today_start + timedelta(days=1),
        'month_start': month_start,
        'month_end': next_month,
        'prev_month_start': prev_month_start,
        'prev_month_end': month_start,
        'tz': tz
    }


def to_utc_iso(dt_local):
    if dt_local.tzinfo is None:
        raise ValueError('Expected timezone-aware datetime')
    return dt_local.astimezone(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')


@bp.route('/top-clients')
def top_clients():
    tz_name = request.args.get('tz', 'America/Caracas')
    rng = tz_ranges(tz_name)
    ms = to_utc_iso(rng['month_start'])
    me = to_utc_iso(rng['month_end'])
    try:
        conn = get_conn()
        if table_exists(conn, 'users') and table_exists(conn, 'spent_ledger') and table_exists(conn, 'package_purchases_ledger'):
            sql = """
            WITH spent AS (
              SELECT sl.user_id, COALESCE(SUM(sl.amount), 0) AS total_spent
              FROM spent_ledger sl
              WHERE sl.created_at >= ? AND sl.created_at < ?
              GROUP BY sl.user_id
            ),
            purchases AS (
              SELECT ppl.user_id, SUM(CASE WHEN ppl.quantity > 0 THEN 1 ELSE 0 END) AS purchases_count
              FROM package_purchases_ledger ppl
              WHERE ppl.created_at >= ? AND ppl.created_at < ?
              GROUP BY ppl.user_id
            ),
            combined AS (
              SELECT u.id AS user_id,
                     COALESCE(u.name, u.email) AS display_name,
                     u.email AS email,
                     COALESCE(spent.total_spent, 0) AS total_spent,
                     COALESCE(purchases.purchases_count, 0) AS purchases_count
              FROM users u
              LEFT JOIN spent ON spent.user_id = u.id
              LEFT JOIN purchases ON purchases.user_id = u.id
              WHERE (COALESCE(spent.total_spent,0) > 0 OR COALESCE(purchases.purchases_count,0) > 0)
            ),
            max_total AS (
              SELECT MAX(total_spent) AS max_total FROM combined
            )
            SELECT c.user_id, c.display_name, c.email, c.total_spent, c.purchases_count,
                   CASE WHEN mt.max_total > 0 THEN (c.total_spent * 100.0 / mt.max_total) ELSE 0 END AS pct
            FROM combined c, max_total mt
            ORDER BY c.total_spent DESC, c.purchases_count DESC
            LIMIT 5
            """
            rows = conn.execute(sql, (ms, me, ms, me)).fetchall()
        else:
            # Legacy schema: usar monthly_user_spending si existe, sino transacciones
            if table_exists(conn, 'monthly_user_spending'):
                # Calcular year_month del rango
                from datetime import datetime
                import pytz
                tz = pytz.timezone('America/Caracas')
                start_local = datetime.fromisoformat(ms.replace(' ', 'T')).replace(tzinfo=pytz.utc).astimezone(tz)
                year_month = start_local.strftime('%Y-%m')
                
                sql = """
                WITH combined AS (
                  SELECT u.id AS user_id,
                         COALESCE(u.nombre || ' ' || u.apellido, u.correo) AS display_name,
                         u.correo AS email,
                         COALESCE(mus.total_spent, 0) AS total_spent,
                         COALESCE(mus.purchases_count, 0) AS purchases_count
                  FROM monthly_user_spending mus
                  JOIN usuarios u ON u.id = mus.usuario_id
                  WHERE mus.year_month = ? AND COALESCE(u.sin_ganancia,FALSE)=FALSE
                ),
                max_total AS (
                  SELECT MAX(total_spent) AS max_total FROM combined
                )
                SELECT c.user_id,
                       c.display_name,
                       c.email,
                       c.total_spent,
                       c.purchases_count,
                       CASE WHEN mt.max_total > 0 THEN (c.total_spent * 100.0 / mt.max_total) ELSE 0 END AS pct
                FROM combined c, max_total mt
                ORDER BY c.total_spent DESC, c.purchases_count DESC
                LIMIT 5
                """
                rows = conn.execute(sql, (year_month,)).fetchall()
            else:
                # Fallback a transacciones (menos confiable por la limpieza)
                sql = """
                WITH base AS (
                  SELECT t.usuario_id AS user_id,
                         SUM(CASE WHEN t.monto < 0 THEN -t.monto ELSE t.monto END) AS total_spent,
                         COUNT(*) AS purchases_count
                  FROM transacciones t
                  WHERE t.fecha >= ? AND t.fecha < ?
                  GROUP BY t.usuario_id
                ),
                combined AS (
                  SELECT u.id AS user_id,
                         COALESCE(u.nombre || ' ' || u.apellido, u.correo) AS display_name,
                         u.correo AS email,
                         COALESCE(b.total_spent,0) AS total_spent,
                         COALESCE(b.purchases_count,0) AS purchases_count
                  FROM base b
                  JOIN usuarios u ON u.id = b.user_id
                  WHERE COALESCE(u.sin_ganancia,FALSE)=FALSE
                ),
                max_total AS (
                  SELECT MAX(total_spent) AS max_total FROM combined
                )
                SELECT c.user_id,
                       c.display_name,
                       c.email,
                       c.total_spent,
                       c.purchases_count,
                       CASE WHEN mt.max_total > 0 THEN (COALESCE(c.total_spent,0) * 100.0 / mt.max_total) ELSE 0 END AS pct
                FROM combined c, max_total mt
                ORDER BY c.total_spent DESC, c.purchases_count DESC
                LIMIT 5
                """
                rows = conn.execute(sql, (ms, me)).fetchall()
        conn.close()
        data = [dict(r) for r in rows]
        # Rename admin accounts
        admin_ids, admin_emails = get_admin_exclusions()
        if admin_ids or admin_emails:
            for r in data:
                try:
                    if (r.get('user_id') in admin_ids) or (r.get('email') in admin_emails):
                        r['display_name'] = 'Admin'
                except Exception:
                    pass
        # Clean email from output (not needed on front)
        for r in data:
            if 'email' in r:
                del r['email']
        return jsonify({
            'top_clients_month': data,
            'period': {
                'from': ms,
                'to': me,
                'tz': tz_name
            }
        })
    except Exception as e:
        return jsonify({'error': 'query_failed', 'message': str(e)}), 500


@bp.route('/summary')
def summary():
    parts = {}
    tz_name = request.args.get('tz', 'America/Caracas')
    rng = tz_ranges(tz_name)
    ms = to_utc_iso(rng['month_start'])
    me = to_utc_iso(rng['month_end'])
    # Fechas locales para consultas en tablas legacy agregadas por día
    month_start_day = rng['month_start'].date().isoformat()
    month_end_day = rng['month_end'].date().isoformat()
    try:
        conn = get_conn()
        if table_exists(conn, 'spent_ledger'):
            row = conn.execute("SELECT COALESCE(SUM(amount),0) AS total_spent_all_time FROM spent_ledger").fetchone()
        else:
            row = conn.execute("SELECT COALESCE(SUM(CASE WHEN monto < 0 THEN -monto ELSE monto END),0) AS total_spent_all_time FROM transacciones").fetchone()
        parts['total_spent_all_time'] = row['total_spent_all_time'] if row else 0
    except Exception as e:
        parts['total_spent_all_time_error'] = str(e)
    try:
        conn = get_conn()
        if table_exists(conn, 'user_balances') and table_exists(conn, 'users'):
            row = conn.execute(
                "SELECT COALESCE(SUM(ub.balance),0) AS active_balance_total FROM user_balances ub JOIN users u ON u.id = ub.user_id WHERE COALESCE(u.is_admin,0)=0"
            ).fetchone()
        else:
            row = conn.execute("SELECT COALESCE(SUM(saldo),0) AS active_balance_total FROM usuarios WHERE COALESCE(sin_ganancia,FALSE)=FALSE").fetchone()
        parts['active_balance_total'] = row['active_balance_total'] if row else 0
    except Exception as e:
        parts['active_balance_total_error'] = str(e)
    try:
        conn = get_conn()
        if table_exists(conn, 'menu_item_pins') and table_exists(conn, 'menu_item_packages'):
            row = conn.execute(
                """
                WITH valid_pins AS (
                  SELECT mip.menu_item_package_id FROM menu_item_pins mip
                  JOIN menu_item_packages p ON p.id = mip.menu_item_package_id
                  WHERE COALESCE(mip.is_used,0)=0
                )
                SELECT COUNT(*) AS pins_available_total,
                       COALESCE(SUM(p.price),0) AS pins_balance_total
                FROM valid_pins vp
                JOIN menu_item_packages p ON p.id = vp.menu_item_package_id
                """
            ).fetchone()
            parts['pins_available_total'] = row['pins_available_total'] if row else 0
            parts['pins_balance_total'] = row['pins_balance_total'] if row else 0
        else:
            # Legacy: pines_freefire (+ _global) and price tables
            # available count
            row1 = conn.execute("SELECT COUNT(*) c FROM pines_freefire WHERE usado = FALSE").fetchone()
            row2 = None
            if table_exists(conn, 'pines_freefire_global'):
                row2 = conn.execute("SELECT COUNT(*) c FROM pines_freefire_global WHERE usado = FALSE").fetchone()
            pins_available_total = (row1['c'] if row1 else 0) + ((row2['c'] if row2 else 0) if row2 else 0)
            # balance total: sum per monto_id * precio
            sum_latam = conn.execute(
                """
                SELECT COALESCE(SUM(pp.precio * cnt.c),0) AS s
                FROM (
                  SELECT monto_id, COUNT(*) AS c FROM pines_freefire WHERE usado = FALSE GROUP BY monto_id
                ) cnt
                JOIN precios_paquetes pp ON pp.id = cnt.monto_id
                """
            ).fetchone()
            sum_global = {'s': 0}
            if table_exists(conn, 'pines_freefire_global') and table_exists(conn, 'precios_freefire_global'):
                sum_global = conn.execute(
                    """
                    SELECT COALESCE(SUM(pfg.precio * cnt.c),0) AS s
                    FROM (
                      SELECT monto_id, COUNT(*) AS c FROM pines_freefire_global WHERE usado = FALSE GROUP BY monto_id
                    ) cnt
                    JOIN precios_freefire_global pfg ON pfg.id = cnt.monto_id
                    """
                ).fetchone()
            parts['pins_available_total'] = pins_available_total
            parts['pins_balance_total'] = (sum_latam['s'] if sum_latam else 0) + (sum_global['s'] if sum_global else 0)
    except Exception as e:
        parts['pins_error'] = str(e)
    # Total de usuarios (canónico o legacy)
    try:
        conn = get_conn()
        if table_exists(conn, 'users'):
            r = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()
            parts['users_total'] = r['c'] if r else 0
        else:
            r = conn.execute("SELECT COUNT(*) AS c FROM usuarios").fetchone()
            parts['users_total'] = r['c'] if r else 0
        conn.close()
    except Exception as e:
        parts['users_total_error'] = str(e)
    # Profit total del mes (excluyendo admin)
    try:
        conn = get_conn()
        if table_exists(conn, 'historial_compras') or table_exists(conn, 'profit_daily_aggregate'):
            lst = compute_admin_profit_by_day(conn, ms, me, tz_name)
            parts['profit_month_total'] = round(sum(item.get('profit', 0) for item in lst), 6) if lst else 0
        elif table_exists(conn, 'profit_ledger') and table_exists(conn, 'usuarios'):
            lst = compute_profit_ledger_by_day(conn, ms, me, tz_name)
            parts['profit_month_total'] = round(sum(item.get('profit', 0) for item in lst), 6) if lst else 0
        elif table_exists(conn, 'package_purchases_ledger') and table_exists(conn, 'users'):
            r = conn.execute(
                """
                SELECT COALESCE(SUM(ppl.profit),0) AS profit
                FROM package_purchases_ledger ppl
                JOIN users u ON u.id = ppl.user_id
                WHERE COALESCE(u.is_admin,0)=0 AND ppl.created_at >= ? AND ppl.created_at < ?
                """,
                (ms, me)
            ).fetchone()
            parts['profit_month_total'] = r['profit'] if r else 0
        else:
            # Legacy persistente: usar agregados diarios
            if table_exists(conn, 'profit_daily_aggregate'):
                row = conn.execute(
                    "SELECT COALESCE(SUM(profit_total),0) AS s FROM profit_daily_aggregate WHERE day >= ? AND day < ?",
                    (month_start_day, month_end_day)
                ).fetchone()
                parts['profit_month_total'] = row['s'] if row else 0
            else:
                # Fallback: calcular al vuelo
                lst = compute_legacy_profit_by_day(conn, ms, me)
                if isinstance(lst, list):
                    parts['profit_month_total'] = round(sum(item.get('profit', 0) for item in lst), 6)
                else:
                    parts['profit_month_total'] = 0
    except Exception as e:
        parts['profit_month_total_error'] = str(e)
    return jsonify({'summary': parts})


@bp.route('/pins-daily')
def pins_daily():
    tz_name = request.args.get('tz', 'America/Caracas')
    rng = tz_ranges(tz_name)
    periods = [
        ('today', rng['today_start'], rng['today_end']),
        ('yesterday', rng['yesterday_start'], rng['yesterday_end']),
        ('dby', rng['dby_start'], rng['dby_end'])
    ]
    out = []
    for key, start, end in periods:
        s = to_utc_iso(start)
        e = to_utc_iso(end)
        try:
            conn = get_conn()
            if table_exists(conn, 'menu_item_pins') and table_exists(conn, 'menu_item_pins_used'):
                a1 = conn.execute("SELECT COUNT(*) c FROM menu_item_pins WHERE created_at >= ? AND created_at < ?", (s, e)).fetchone()
                a2 = conn.execute("SELECT COUNT(*) c FROM menu_item_pins_used WHERE created_at >= ? AND created_at < ?", (s, e)).fetchone()
                u1 = conn.execute("SELECT COUNT(*) c FROM menu_item_pins_used WHERE used_at >= ? AND used_at < ?", (s, e)).fetchone()
                pins_added = (a1['c'] if a1 else 0) + (a2['c'] if a2 else 0)
                pins_used = u1['c'] if u1 else 0
            else:
                # Legacy: count aggregated per day using fecha_agregado and fecha_usado
                a_latam = conn.execute("SELECT COUNT(*) c FROM pines_freefire WHERE fecha_agregado >= ? AND fecha_agregado < ?", (s, e)).fetchone()
                a_global = None
                if table_exists(conn, 'pines_freefire_global'):
                    a_global = conn.execute("SELECT COUNT(*) c FROM pines_freefire_global WHERE fecha_agregado >= ? AND fecha_agregado < ?", (s, e)).fetchone()
                u_latam = conn.execute("SELECT COUNT(*) c FROM pines_freefire WHERE fecha_usado IS NOT NULL AND fecha_usado >= ? AND fecha_usado < ?", (s, e)).fetchone()
                u_global = None
                if table_exists(conn, 'pines_freefire_global'):
                    u_global = conn.execute("SELECT COUNT(*) c FROM pines_freefire_global WHERE fecha_usado IS NOT NULL AND fecha_usado >= ? AND fecha_usado < ?", (s, e)).fetchone()
                pins_added = (a_latam['c'] if a_latam else 0) + ((a_global['c'] if a_global else 0) if a_global else 0)
                pins_used = (u_latam['c'] if u_latam else 0) + ((u_global['c'] if u_global else 0) if u_global else 0)
            conn.close()
            out.append({
                'date': start.date().isoformat(),
                'pins_added': pins_added,
                'pins_used': pins_used
            })
        except Exception as e2:
            out.append({'date': start.date().isoformat(), 'error': str(e2)})
    return jsonify({'pins_daily': out, 'tz': tz_name})


@bp.route('/timeseries')
def timeseries():
    tz_name = request.args.get('tz', 'America/Caracas')
    rng = tz_ranges(tz_name)
    ms, me = to_utc_iso(rng['month_start']), to_utc_iso(rng['month_end'])
    ws, we = to_utc_iso(rng['week_start']), to_utc_iso(rng['week_end'])
    pms, pme = to_utc_iso(rng['prev_month_start']), to_utc_iso(rng['prev_month_end'])
    ms_day, me_day = rng['month_start'].date().isoformat(), rng['month_end'].date().isoformat()
    pms_day, pme_day = rng['prev_month_start'].date().isoformat(), rng['prev_month_end'].date().isoformat()
    res = {
        'daily_spent_month': [],
        'daily_spent_week': [],
        'profit_daily_month': [],
        'profit_daily_prev_month': []
    }
    try:
        conn = get_conn()
        if table_exists(conn, 'spent_ledger'):
            q1 = conn.execute(
                "SELECT date(created_at) AS day, COALESCE(SUM(amount),0) total_spent FROM spent_ledger WHERE created_at >= ? AND created_at < ? GROUP BY date(created_at) ORDER BY day",
                (ms, me)
            ).fetchall()
        else:
            q1 = conn.execute(
                "SELECT date(fecha) AS day, COALESCE(SUM(CASE WHEN monto < 0 THEN -monto ELSE monto END),0) total_spent FROM transacciones WHERE fecha >= ? AND fecha < ? GROUP BY date(fecha) ORDER BY day",
                (ms, me)
            ).fetchall()
        res['daily_spent_month'] = [dict(r) for r in q1]
    except Exception as e:
        res['daily_spent_month_error'] = str(e)
    try:
        conn = get_conn()
        if table_exists(conn, 'spent_ledger'):
            q2 = conn.execute(
                "SELECT date(created_at) AS day, COALESCE(SUM(amount),0) total_spent FROM spent_ledger WHERE created_at >= ? AND created_at < ? GROUP BY date(created_at) ORDER BY day",
                (ws, we)
            ).fetchall()
        else:
            q2 = conn.execute(
                "SELECT date(fecha) AS day, COALESCE(SUM(CASE WHEN monto < 0 THEN -monto ELSE monto END),0) total_spent FROM transacciones WHERE fecha >= ? AND fecha < ? GROUP BY date(fecha) ORDER BY day",
                (ws, we)
            ).fetchall()
        res['daily_spent_week'] = [dict(r) for r in q2]
    except Exception as e:
        res['daily_spent_week_error'] = str(e)
    try:
        conn = get_conn()
        if table_exists(conn, 'historial_compras') or table_exists(conn, 'profit_daily_aggregate'):
            q3 = compute_admin_profit_by_day(conn, ms, me, tz_name)
        elif table_exists(conn, 'profit_ledger') and table_exists(conn, 'usuarios'):
            q3 = compute_profit_ledger_by_day(conn, ms, me, tz_name)
        elif table_exists(conn, 'package_purchases_ledger') and table_exists(conn, 'users'):
            q3 = conn.execute(
                """
                SELECT date(ppl.created_at) AS day, COALESCE(SUM(ppl.profit),0) AS profit
                FROM package_purchases_ledger ppl
                JOIN users u ON u.id = ppl.user_id
                WHERE COALESCE(u.is_admin,0)=0 AND ppl.created_at >= ? AND ppl.created_at < ?
                GROUP BY date(ppl.created_at)
                ORDER BY day
                """,
                (ms, me)
            ).fetchall()
        elif table_exists(conn, 'profit_daily_aggregate'):
            q3 = conn.execute(
                "SELECT day, profit_total AS profit FROM profit_daily_aggregate WHERE day >= ? AND day < ? ORDER BY day",
                (ms_day, me_day)
            ).fetchall()
        elif table_exists(conn, 'transacciones'):
            q3 = compute_legacy_profit_by_day(conn, ms, me)
        else:
            q3 = []
        res['profit_daily_month'] = [dict(r) for r in q3] if isinstance(q3, list) else [dict(r) for r in q3]
    except Exception as e:
        res['profit_daily_month_error'] = str(e)
    try:
        conn = get_conn()
        if table_exists(conn, 'historial_compras') or table_exists(conn, 'profit_daily_aggregate'):
            q4 = compute_admin_profit_by_day(conn, pms, pme, tz_name)
        elif table_exists(conn, 'profit_ledger') and table_exists(conn, 'usuarios'):
            q4 = compute_profit_ledger_by_day(conn, pms, pme, tz_name)
        elif table_exists(conn, 'package_purchases_ledger') and table_exists(conn, 'users'):
            q4 = conn.execute(
                """
                SELECT date(ppl.created_at) AS day, COALESCE(SUM(ppl.profit),0) AS profit
                FROM package_purchases_ledger ppl
                JOIN users u ON u.id = ppl.user_id
                WHERE COALESCE(u.is_admin,0)=0 AND ppl.created_at >= ? AND ppl.created_at < ?
                GROUP BY date(ppl.created_at)
                ORDER BY day
                """,
                (pms, pme)
            ).fetchall()
        elif table_exists(conn, 'profit_daily_aggregate'):
            q4 = conn.execute(
                "SELECT day, profit_total AS profit FROM profit_daily_aggregate WHERE day >= ? AND day < ? ORDER BY day",
                (pms_day, pme_day)
            ).fetchall()
        elif table_exists(conn, 'transacciones'):
            q4 = compute_legacy_profit_by_day(conn, pms, pme)
        else:
            q4 = []
        res['profit_daily_prev_month'] = [dict(r) for r in q4] if isinstance(q4, list) else [dict(r) for r in q4]
    except Exception as e:
        res['profit_daily_prev_month_error'] = str(e)
    return jsonify({'timeseries': res, 'tz': tz_name})


@bp.route('/backfill-legacy-profit', methods=['POST'])
def backfill_legacy_profit():
    """Backfill de agregados diarios de profit para esquema legacy.
    Protegido por token: enviar ?token=... que debe coincidir con BACKFILL_TOKEN en env.
    Parámetros:
      - days: int (default 60)
      - tz: zona horaria (default America/Caracas)
    """
    token = request.args.get('token') or (request.get_json(silent=True) or {}).get('token')
    expected = os.environ.get('BACKFILL_TOKEN')
    if not expected or token != expected:
        return jsonify({'error': 'unauthorized'}), 401
    days = request.args.get('days', type=int) or (request.get_json(silent=True) or {}).get('days') or 60
    tz_name = request.args.get('tz', 'America/Caracas')
    rng = tz_ranges(tz_name)
    tz = rng['tz']
    try:
        conn = get_conn()
        cur = conn.cursor()
        today_local = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
        count = 0
        for i in range(days):
            day_start = today_local - timedelta(days=i)
            day_end = day_start + timedelta(days=1)
            s, e = to_utc_iso(day_start), to_utc_iso(day_end)
            # Calcular usando fallback actual
            lst = compute_legacy_profit_by_day(conn, s, e)
            total = 0.0
            if isinstance(lst, list):
                total = round(sum(item.get('profit', 0) for item in lst), 6)
            # Upsert en profit_daily_aggregate
            day = day_start.date().isoformat()
            ex = cur.execute("SELECT profit_total FROM profit_daily_aggregate WHERE day=?", (day,)).fetchone()
            if ex:
                cur.execute("UPDATE profit_daily_aggregate SET profit_total=?, updated_at=datetime('now') WHERE day=?", (total, day))
            else:
                cur.execute("INSERT INTO profit_daily_aggregate(day, profit_total) VALUES(?, ?)", (day, total))
            count += 1
        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'days_processed': count})
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return jsonify({'error': 'backfill_failed', 'message': str(e)}), 500


@bp.route('/packages-history')
def packages_history():
    tz_name = request.args.get('tz', 'America/Caracas')
    period = request.args.get('period', 'month')
    rng = tz_ranges(tz_name)
    if period == 'day':
        rs, re = rng['today_start'], rng['today_end']
    elif period == 'week':
        rs, re = rng['week_start'], rng['week_end']
    else:
        rs, re = rng['month_start'], rng['month_end']
    s, e = to_utc_iso(rs), to_utc_iso(re)
    try:
        conn = get_conn()
        if table_exists(conn, 'package_purchases_ledger') and table_exists(conn, 'menu_item_packages'):
            sql = (
                "SELECT mip.menu_item_id AS category_id, mip.name AS package_name, COALESCE(SUM(ppl.quantity),0) AS total_quantity "
                "FROM package_purchases_ledger ppl "
                "JOIN menu_item_packages mip ON mip.id = ppl.menu_item_package_id "
                "JOIN users u ON u.id = ppl.user_id AND COALESCE(u.is_admin,0)=0 "
                "WHERE ppl.created_at >= ? AND ppl.created_at < ? "
                "GROUP BY mip.menu_item_id, mip.name ORDER BY total_quantity DESC"
            )
            rows = conn.execute(sql, (s, e)).fetchall()
        elif table_exists(conn, 'ventas_semanales'):
            rows = conn.execute(
                "SELECT paquete_id AS category_id, paquete_nombre AS package_name, COALESCE(SUM(cantidad_vendida),0) AS total_quantity FROM ventas_semanales WHERE fecha_venta >= ? AND fecha_venta < ? GROUP BY paquete_id, paquete_nombre ORDER BY total_quantity DESC",
                (s, e)
            ).fetchall()
        else:
            rows = []
        conn.close()
        return jsonify({f'packages_history_{period}': [dict(r) for r in rows], 'period': {'from': s, 'to': e, 'tz': tz_name}})
    except Exception as e:
        return jsonify({'error': 'query_failed', 'message': str(e)}), 500


@bp.route('/profit-packages-config', methods=['GET', 'POST'])
def profit_packages_config():
    if request.method == 'GET':
        try:
            conn = get_conn()
            if table_exists(conn, 'menu_item_packages') and table_exists(conn, 'package_cost_config'):
                sql = (
                    "SELECT mip.id AS package_id, 'canonical' AS source, mip.menu_item_id AS category_id, mip.name AS package_name, mip.price AS base_price, pcc.cost "
                    "FROM menu_item_packages mip LEFT JOIN package_cost_config pcc ON pcc.menu_item_package_id = mip.id"
                )
                rows = conn.execute(sql).fetchall()
            else:
                # Build union from legacy price tables + precios_compra
                rows = []
                # Freefire LATAM
                latam = conn.execute(
                    """
                    SELECT id AS package_id, 'freefire_latam' AS source, id AS category_id, nombre AS package_name, precio AS base_price, (
                       SELECT precio_compra FROM precios_compra pc WHERE pc.juego='freefire_latam' AND pc.paquete_id = precios_paquetes.id AND pc.activo = 1 LIMIT 1
                     ) AS cost FROM precios_paquetes
                    """
                ).fetchall()
                rows.extend(latam)
                if table_exists(conn, 'precios_freefire_global'):
                    g = conn.execute(
                        """
                        SELECT id AS package_id, 'freefire_global' AS source, id AS category_id, nombre AS package_name, precio AS base_price, (
                           SELECT precio_compra FROM precios_compra pc WHERE pc.juego='freefire_global' AND pc.paquete_id = precios_freefire_global.id AND pc.activo = 1 LIMIT 1
                         ) AS cost FROM precios_freefire_global
                        """
                    ).fetchall()
                    rows.extend(g)
                if table_exists(conn, 'precios_bloodstriker'):
                    b = conn.execute(
                        """
                        SELECT id AS package_id, 'bloodstriker' AS source, id AS category_id, nombre AS package_name, precio AS base_price, (
                           SELECT precio_compra FROM precios_compra pc WHERE pc.juego='bloodstriker' AND pc.paquete_id = precios_bloodstriker.id AND pc.activo = 1 LIMIT 1
                         ) AS cost FROM precios_bloodstriker
                        """
                    ).fetchall()
                    rows.extend(b)
                if table_exists(conn, 'precios_freefire_id'):
                    fi = conn.execute(
                        """
                        SELECT id AS package_id, 'freefire_id' AS source, id AS category_id, nombre AS package_name, precio AS base_price, (
                           SELECT precio_compra FROM precios_compra pc WHERE pc.juego='freefire_id' AND pc.paquete_id = precios_freefire_id.id AND pc.activo = 1 LIMIT 1
                         ) AS cost FROM precios_freefire_id
                        """
                    ).fetchall()
                    rows.extend(fi)
                if table_exists(conn, 'paquetes_dinamicos') and table_exists(conn, 'juegos_dinamicos'):
                    dyn = conn.execute(
                        """
                        SELECT pd.id AS package_id, 'dyn_' || jd.slug AS source, pd.id AS category_id, pd.nombre AS package_name, pd.precio AS base_price, (
                           SELECT precio_compra FROM precios_compra pc WHERE pc.juego = 'dyn_' || jd.slug AND pc.paquete_id = pd.id AND pc.activo = 1 LIMIT 1
                         ) AS cost FROM paquetes_dinamicos pd JOIN juegos_dinamicos jd ON jd.id = pd.juego_id
                        """
                    ).fetchall()
                    rows.extend(dyn)
            conn.close()
            return jsonify({'profit_packages_config': [dict(r) for r in rows]})
        except Exception as e:
            return jsonify({'error': 'query_failed', 'message': str(e)}), 500
    else:
        # POST: upsert costs
        try:
            payload = request.get_json(silent=True) or {}
            items = payload.get('items', [])
            if not isinstance(items, list):
                return jsonify({'error': 'invalid_payload'}), 400
            conn = get_conn()
            cur = conn.cursor()
            if table_exists(conn, 'menu_item_packages') and table_exists(conn, 'package_cost_config'):
                # canonical
                for it in items:
                    pkg_id = it.get('package_id')
                    cost = it.get('cost')
                    if pkg_id is None or cost is None:
                        continue
                    cur.execute("INSERT INTO package_cost_config (menu_item_package_id, cost) VALUES (?, ?) ON CONFLICT(menu_item_package_id) DO UPDATE SET cost=excluded.cost", (pkg_id, float(cost)))
            else:
                # legacy precios_compra
                for it in items:
                    juego = it.get('source')
                    paquete_id = it.get('package_id')
                    cost = it.get('cost')
                    if not juego or paquete_id is None or cost is None:
                        continue
                    # Upsert precios_compra (unique juego, paquete_id). Ensure activo=1
                    cur.execute(
                        """
                        INSERT INTO precios_compra (juego, paquete_id, precio_compra, activo)
                        VALUES (?, ?, ?, 1)
                        ON CONFLICT(juego, paquete_id) DO UPDATE SET precio_compra=excluded.precio_compra, activo=1
                        """,
                        (juego, int(paquete_id), float(cost))
                    )
            conn.commit()
            conn.close()
            return jsonify({'ok': True})
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            return jsonify({'error': 'update_failed', 'message': str(e)}), 500
