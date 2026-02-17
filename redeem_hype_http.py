import json
import os
import logging
import httpx

from pin_redeemer import PinRedeemResult

logger = logging.getLogger(__name__)

API_URL = "https://redeem.hype.games/api/v1/account"
BASE_URL = "https://redeem.hype.games/"


def _build_payload(
    *,
    pin_uuid: str,
    player_id: str,
    nombre_cliente: str,
    fecha_nacimiento: str,
    nacionalidad: str,
    captcha_token: str,
    redeem_country_id: str = "5",
    country_id: str = "5",
    company_name: str = "HypeMexico",
    product_id: str = "2630",
):
    payload = {
        "Key": pin_uuid,
        "RedeemCountryId": redeem_country_id,
        "CountryId": country_id,
        "CompanyName": company_name,
        "ProductId": product_id,
        "Customer": {
            "Name": nombre_cliente,
            "BornAt": fecha_nacimiento,
            "NationalityAlphaCode": nacionalidad,
        },
        "GameAccountId": player_id,
        "privacy": "on",
        "CaptchaToken": captcha_token,
    }

    payload_alt = {
        "Key": pin_uuid,
        "RedeemCountryId": redeem_country_id,
        "CountryId": country_id,
        "CompanyName": company_name,
        "ProductId": product_id,
        "Customer.Name": nombre_cliente,
        "Customer.BornAt": fecha_nacimiento,
        "Customer.NationalityAlphaCode": nacionalidad,
        "GameAccountId": player_id,
        "privacy": "on",
        "CaptchaToken": captcha_token,
    }

    return payload, payload_alt


def _parse_response(resp: httpx.Response):
    content_type = (resp.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        try:
            return resp.json()
        except Exception:
            return {"raw": resp.text}
    return {"raw": resp.text}


def redeem_pin_http(pin_code, player_id, config=None):
    cfg = dict(config or {})

    captcha_token = cfg.get("captcha_token") or os.environ.get("HYPE_CAPTCHA_TOKEN", "").strip()
    if not captcha_token:
        return PinRedeemResult(
            False,
            "Falta CaptchaToken (define HYPE_CAPTCHA_TOKEN o config['captcha_token'])",
            pin_code,
            player_id,
        )

    nombre = cfg.get("nombre_completo") or cfg.get("nombre_cliente") or "Usuario Revendedor"
    born_at = cfg.get("fecha_nacimiento") or "01/01/1995"
    nacionalidad = cfg.get("nacionalidad") or "VE"

    redeem_country_id = str(cfg.get("redeem_country_id") or "5")
    country_id = str(cfg.get("country_id") or "5")
    company_name = str(cfg.get("company_name") or "HypeMexico")
    product_id = str(cfg.get("product_id") or "2630")

    timeout_s = float(cfg.get("http_timeout_s") or 30)

    payload, payload_alt = _build_payload(
        pin_uuid=pin_code,
        player_id=player_id,
        nombre_cliente=nombre,
        fecha_nacimiento=born_at,
        nacionalidad=nacionalidad,
        captcha_token=captcha_token,
        redeem_country_id=redeem_country_id,
        country_id=country_id,
        company_name=company_name,
        product_id=product_id,
    )

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8",
        "Origin": "https://redeem.hype.games",
        "Referer": "https://redeem.hype.games/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def _attempt(_payload):
        with httpx.Client(timeout=timeout_s, follow_redirects=True, headers=headers) as client:
            client.get(BASE_URL)
            r = client.post(API_URL, content=json.dumps(_payload))
            return r

    try:
        resp = _attempt(payload)
        data = _parse_response(resp)
        if 200 <= resp.status_code < 300:
            msg = data.get("message") if isinstance(data, dict) else None
            return PinRedeemResult(True, msg or "Recarga completada", pin_code, player_id)

        resp2 = _attempt(payload_alt)
        data2 = _parse_response(resp2)
        if 200 <= resp2.status_code < 300:
            msg = data2.get("message") if isinstance(data2, dict) else None
            return PinRedeemResult(True, msg or "Recarga completada", pin_code, player_id)

        err_msg = None
        if isinstance(data, dict):
            err_msg = data.get("message") or data.get("error")
        if not err_msg and isinstance(data2, dict):
            err_msg = data2.get("message") or data2.get("error")
        if not err_msg:
            err_msg = f"HTTP {resp.status_code} / {resp2.status_code}"

        logger.warning(f"[PinRedeemerHTTP] Fallo redencion: {err_msg} | resp1={data} resp2={data2}")
        return PinRedeemResult(False, str(err_msg), pin_code, player_id)

    except Exception as e:
        logger.error(f"[PinRedeemerHTTP] Error en redencion HTTP: {e}")
        return PinRedeemResult(False, f"Error HTTP: {str(e)}", pin_code, player_id)
