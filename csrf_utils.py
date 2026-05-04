import functools
import hmac
import secrets

from flask import flash, jsonify, redirect, request, session


CSRF_SESSION_KEY = '_csrf_token'
CSRF_FIELD_NAME = 'csrf_token'


def get_csrf_token() -> str:
    token = str(session.get(CSRF_SESSION_KEY) or '').strip()
    if token:
        return token

    token = secrets.token_urlsafe(32)
    session[CSRF_SESSION_KEY] = token
    return token


def get_submitted_csrf_token() -> str:
    json_data = request.get_json(silent=True) or {}
    token = (
        request.form.get(CSRF_FIELD_NAME)
        or json_data.get(CSRF_FIELD_NAME)
        or request.headers.get('X-CSRF-Token')
        or ''
    )
    return str(token).strip()


def is_valid_csrf_token(token: str | None = None) -> bool:
    expected = str(session.get(CSRF_SESSION_KEY) or '').strip()
    provided = str(token if token is not None else get_submitted_csrf_token()).strip()
    if not expected or not provided:
        return False
    return hmac.compare_digest(provided, expected)


def csrf_protect(on_error_redirect: str = '/admin', error_message: str = 'Sesión expirada o solicitud inválida. Intenta de nuevo.'):
    def decorator(func):
        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            if not session.get('is_admin'):
                return func(*args, **kwargs)

            if is_valid_csrf_token():
                return func(*args, **kwargs)

            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'ok': False, 'error': 'CSRF token inválido o faltante'}), 403

            flash(error_message, 'error')
            return redirect(on_error_redirect)

        return wrapped

    return decorator