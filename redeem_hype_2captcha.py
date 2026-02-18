import logging
import os
import re
import time
import json

import httpx

from pin_redeemer import PinRedeemResult

logger = logging.getLogger(__name__)

BASE_URL = "https://redeem.hype.games/"
VALIDATE_URL = "https://redeem.hype.games/validate"
VALIDATE_ACCOUNT_URL = "https://redeem.hype.games/validate/account"
CONFIRM_URL = "https://redeem.hype.games/confirm"
RECAPTCHA_SITEKEY = "6Lf_DWEpAAAAAEg4rjruIXopl29ai0v9o6Vafx0A"

TWOCAPTCHA_IN = "https://api.2captcha.com/in.php"
TWOCAPTCHA_RES = "https://api.2captcha.com/res.php"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def _solve_recaptcha_v3(api_key: str, pageurl: str, sitekey: str,
                        action: str = "validate", min_score: float = 0.3,
                        timeout_s: int = 120, poll_interval: int = 5) -> str:
    """Resuelve reCAPTCHA v3 usando la API de 2Captcha."""
    params = {
        "key": api_key,
        "method": "userrecaptcha",
        "googlekey": sitekey,
        "pageurl": pageurl,
        "version": "v3",
        "action": action,
        "min_score": str(min_score),
        "json": "1",
    }

    resp = httpx.post(TWOCAPTCHA_IN, data=params, timeout=30)
    data = resp.json()

    if data.get("status") != 1:
        raise RuntimeError(f"2Captcha rechazó la tarea: {data.get('request', data)}")

    task_id = data["request"]
    logger.info(f"[2Captcha] Tarea creada: {task_id}")

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        time.sleep(poll_interval)

        res = httpx.get(TWOCAPTCHA_RES, params={
            "key": api_key,
            "action": "get",
            "id": task_id,
            "json": "1",
        }, timeout=15)
        result = res.json()

        if result.get("status") == 1:
            token = result["request"]
            logger.info(f"[2Captcha] Token obtenido (len={len(token)})")
            return token

        if result.get("request") == "CAPCHA_NOT_READY":
            continue

        raise RuntimeError(f"2Captcha error: {result.get('request', result)}")

    raise TimeoutError(f"2Captcha no resolvió en {timeout_s}s")


def _extract_hidden_fields(html: str) -> dict:
    """Extrae campos ocultos del HTML de respuesta."""
    fields = {}
    for m in re.finditer(r'<input[^>]*type=["\']hidden["\'][^>]*>', html, re.IGNORECASE):
        tag = m.group(0)
        name_m = re.search(r'name=["\']([^"\']+)["\']', tag)
        val_m = re.search(r'value=["\']([^"\']*)["\']', tag)
        if name_m:
            fields[name_m.group(1)] = val_m.group(1) if val_m else ""
    return fields


def _build_form_data(hidden_fields, nombre, born_at, nacionalidad, player_id):
    """Construye form data exactamente como jQuery serialize() del formulario real.
    El HTML tiene campos con Name='Customer.X' (primer attr) y name='X' (segundo).
    El browser usa el primer atributo, así que necesitamos AMBOS."""
    data = {}
    data.update(hidden_fields)
    # Campos del cliente (inputs visibles en el formulario)
    data["Customer.Name"] = nombre
    data["Customer.BornAt"] = born_at
    data["Customer.NationalityAlphaCode"] = nacionalidad
    data["GameAccountId"] = player_id
    data["privacy"] = "on"
    # Campos ocultos con prefijo Customer.* (ASP.NET model binding)
    data["Customer.CountryId"] = hidden_fields.get("CountryId", "5")
    data["Customer.CompanyName"] = hidden_fields.get("CompanyName", "HypeMexico")
    return data


PIN_UUID_REGEX = re.compile(
    r'^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$'
)
PLAYER_ID_REGEX = re.compile(r'^\d{5,20}$')

ERRORES_NO_REINTENTABLES = [
    "pin usado", "pin already", "already redeemed", "pin expirado", "pin expired",
    "pin inválido", "invalid pin", "pin not found", "não encontrado",
    "account (failed)", "cuenta no encontrada", "account not found",
]


def _validate_inputs(pin_code, player_id):
    """Validación previa de formato ANTES de gastar saldo en captcha."""
    errors = []
    if not pin_code or not PIN_UUID_REGEX.match(str(pin_code).strip()):
        errors.append(f"Formato de PIN inválido: '{pin_code}' (debe ser UUID)")
    if not player_id or not PLAYER_ID_REGEX.match(str(player_id).strip()):
        errors.append(f"Formato de Player ID inválido: '{player_id}' (debe ser 5-20 dígitos)")
    return errors


def _is_error_no_reintentable(mensaje):
    """Detecta errores que NO se solucionan reintentando (PIN usado, expirado, etc.)."""
    if not mensaje:
        return False
    low = mensaje.lower()
    return any(err in low for err in ERRORES_NO_REINTENTABLES)


def redeem_pin_2captcha(pin_code, player_id, config=None):
    """
    Modo 2Captcha (sin Playwright).
    Flujo: POST /validate -> POST /confirm
    
    Protecciones de ahorro:
      - Validación de formato ANTES de pedir captcha (no gasta saldo)
      - Máximo 2 intentos por redención
      - Cancela inmediato si el error no es reintentable (PIN usado, expirado, etc.)
    """
    cfg = dict(config or {})
    max_intentos = int(cfg.get("max_intentos_captcha", 2))

    # ========== VALIDACIÓN PREVIA (gratis, no gasta captcha) ==========
    errores_formato = _validate_inputs(pin_code, player_id)
    if errores_formato:
        msg = "; ".join(errores_formato)
        logger.warning(f"[2Captcha] Validación previa falló (sin gastar captcha): {msg}")
        return PinRedeemResult(False, msg, pin_code, player_id)

    api_key = cfg.get("twocaptcha_api_key") or os.environ.get("TWOCAPTCHA_API_KEY", "").strip()
    if not api_key:
        return PinRedeemResult(
            False,
            "Falta TWOCAPTCHA_API_KEY (configúrala en .env o config)",
            pin_code, player_id,
        )

    nombre = cfg.get("nombre_completo") or cfg.get("nombre_cliente") or "Usuario Revendedor"
    born_at = cfg.get("fecha_nacimiento") or "01/01/1995"
    nacionalidad = cfg.get("nacionalidad") or "VE"
    timeout_s = float(cfg.get("http_timeout_s") or 30)
    captcha_timeout = int(cfg.get("captcha_timeout_s", 120))
    captcha_min_score = float(cfg.get("captcha_min_score", 0.3))

    headers = {
        "Accept": "*/*",
        "Origin": "https://redeem.hype.games",
        "Referer": "https://redeem.hype.games/",
        "User-Agent": DEFAULT_USER_AGENT,
        "X-Requested-With": "XMLHttpRequest",
        "PartnerIdentifier": "",
    }

    ultimo_error = "Error desconocido"

    for intento in range(1, max_intentos + 1):
        logger.info(f"[2Captcha] === Intento {intento}/{max_intentos} para PIN {pin_code[:8]}... ===")

        try:
            with httpx.Client(timeout=timeout_s, follow_redirects=True, headers=headers) as client:
                # 0) Visitar página principal para cookies de sesión
                client.get(BASE_URL)

                # ========== PASO 1: POST /validate (validar PIN) ==========
                logger.info(f"[2Captcha] Paso 1/2: Resolviendo captcha para /validate...")
                try:
                    token1 = _solve_recaptcha_v3(
                        api_key=api_key, pageurl=BASE_URL, sitekey=RECAPTCHA_SITEKEY,
                        action="validate", min_score=captcha_min_score, timeout_s=captcha_timeout,
                    )
                except Exception as e:
                    ultimo_error = f"Error 2Captcha (validate): {e}"
                    logger.error(f"[2Captcha] {ultimo_error}")
                    continue

                resp1 = client.post(VALIDATE_URL, data={
                    "Key": pin_code,
                    "CaptchaToken": token1,
                    "origin": "redeem",
                })
                logger.info(f"[2Captcha] /validate -> HTTP {resp1.status_code}")

                if resp1.status_code != 200:
                    ultimo_error = f"Validate HTTP {resp1.status_code}"
                    continue

                html1 = resp1.text
                if "StatusCode" in html1 and "Message" in html1:
                    try:
                        err = json.loads(html1)
                        if err.get("StatusCode"):
                            err_msg = err.get("Message", "Error en validate")
                            if _is_error_no_reintentable(err_msg):
                                logger.warning(f"[2Captcha] Error no reintentable en validate: {err_msg}")
                                return PinRedeemResult(False, err_msg, pin_code, player_id)
                            ultimo_error = err_msg
                            continue
                    except Exception:
                        pass

                hidden_fields = _extract_hidden_fields(html1)
                logger.info(f"[2Captcha] Hidden fields: {hidden_fields}")

                form_data = _build_form_data(hidden_fields, nombre, born_at, nacionalidad, player_id)

                # ========== PASO 2: POST /confirm (redención final) ==========
                logger.info(f"[2Captcha] Paso 2/2: Resolviendo captcha para /confirm...")
                try:
                    token2 = _solve_recaptcha_v3(
                        api_key=api_key, pageurl=BASE_URL, sitekey=RECAPTCHA_SITEKEY,
                        action="KEY_REDEEM", min_score=captcha_min_score, timeout_s=captcha_timeout,
                    )
                except Exception as e:
                    ultimo_error = f"Error 2Captcha (confirm): {e}"
                    logger.error(f"[2Captcha] {ultimo_error}")
                    continue

                confirm_data = dict(form_data)
                confirm_data["CaptchaToken"] = token2
                confirm_data["origin"] = "redeem"

                resp2 = client.post(CONFIRM_URL, data=confirm_data)
                logger.info(f"[2Captcha] /confirm -> HTTP {resp2.status_code}")

                html2 = resp2.text
                logger.info(f"[2Captcha] /confirm body (500 chars): {html2[:500]}")

                if resp2.status_code == 200:
                    low = html2.lower()
                    if any(kw in low for kw in ["succes", "exitosa", "completad", "confirmad", "resgatado"]):
                        logger.info(f"[2Captcha] Redención exitosa en intento {intento}!")
                        return PinRedeemResult(True, "Recarga completada (2Captcha)", pin_code, player_id)

                    error_match = re.search(r'class=["\'][^"\']*error[^"\']*["\'][^>]*>([^<]+)', html2, re.IGNORECASE)
                    if error_match:
                        err_msg = error_match.group(1).strip()
                        if _is_error_no_reintentable(err_msg):
                            logger.warning(f"[2Captcha] Error no reintentable: {err_msg}")
                            return PinRedeemResult(False, err_msg, pin_code, player_id)
                        ultimo_error = err_msg
                        continue

                    logger.info(f"[2Captcha] /confirm 200 OK - asumiendo éxito")
                    return PinRedeemResult(True, "Recarga completada (2Captcha)", pin_code, player_id)
                else:
                    ultimo_error = f"Confirm HTTP {resp2.status_code}"
                    logger.warning(f"[2Captcha] {ultimo_error}: {html2[:300]}")
                    if _is_error_no_reintentable(html2):
                        return PinRedeemResult(False, ultimo_error, pin_code, player_id)
                    continue

        except Exception as e:
            ultimo_error = f"Error: {str(e)}"
            logger.error(f"[2Captcha] Error general intento {intento}: {e}")
            continue

        # Esperar antes del siguiente intento
        if intento < max_intentos:
            logger.info(f"[2Captcha] Esperando 3s antes del intento {intento + 1}...")
            time.sleep(3)

    # Si llegamos aquí, se agotaron los intentos
    logger.warning(f"[2Captcha] ALERTA: {max_intentos} intentos agotados para PIN {pin_code[:8]}...")
    return PinRedeemResult(False, f"Falló tras {max_intentos} intentos: {ultimo_error}", pin_code, player_id)
