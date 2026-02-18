import asyncio
import logging
import os
import json
import httpx
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

from pin_redeemer import PinRedeemResult, ensure_chromium_installed

logger = logging.getLogger(__name__)

BASE_URL = "https://redeem.hype.games/"
REDEEM_URL = "https://redeem.hype.games/api/v1/account"
RECAPTCHA_SITEKEY = "6Lf_DWEpAAAAEg4rEg_3N5H0G7-O"


async def _extract_captcha_token_with_playwright(url_base: str, timeout_ms: int = 30000):
    """
    Navega a la página de redención, ejecuta grecaptcha.execute() con el
    sitekey de reCAPTCHA v3 para obtener el CaptchaToken, y cierra el
    navegador inmediatamente para liberar RAM.
    """
    async with async_playwright() as p:
        browser = None
        try:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                ]
            )
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1366, 'height': 768},
                locale='es-VE',
            )
            page = await context.new_page()

            # 1) Navegar a la página de redención
            await page.goto(url_base, wait_until='domcontentloaded', timeout=timeout_ms)
            await page.wait_for_load_state('networkidle', timeout=timeout_ms)

            # 2) Esperar a que grecaptcha.execute esté disponible (reCAPTCHA v3)
            await page.wait_for_function(
                "() => typeof window.grecaptcha !== 'undefined' && typeof window.grecaptcha.execute === 'function'",
                timeout=timeout_ms,
            )

            # 3) Ejecutar grecaptcha.execute() activamente con el sitekey
            token = await page.evaluate(
                """
                async ({ sitekey }) => {
                    try {
                        return await window.grecaptcha.execute(sitekey, { action: 'redeem' });
                    } catch (e) {
                        return null;
                    }
                }
                """,
                {"sitekey": RECAPTCHA_SITEKEY},
            )

            if not token or not isinstance(token, str) or len(token) < 20:
                logger.error("[Hybrid] grecaptcha.execute() no devolvió un token válido")
                return None

            logger.info("[Hybrid] CaptchaToken obtenido via grecaptcha.execute()")
            return token

        except PlaywrightTimeout:
            logger.error("[Hybrid] Timeout esperando reCAPTCHA v3")
            return None
        except Exception as e:
            logger.error(f"[Hybrid] Error extrayendo CaptchaToken: {e}")
            return None
        finally:
            if browser:
                await browser.close()


def redeem_pin_hybrid(pin_code, player_id, config=None):
    """
    Modo híbrido:
    1) Usa Playwright solo para obtener el CaptchaToken del flujo real
    2) Usa httpx para hacer el POST ligero a /api/v1/account
    """
    cfg = dict(config or {})
    timeout_ms = int(cfg.get('timeout_ms', 30000))
    url_base = cfg.get('url_base', BASE_URL)

    # 1) Obtener CaptchaToken con Playwright
    logger.info(f"[Hybrid] Obteniendo CaptchaToken para PIN {pin_code[:8]}...")
    ensure_chromium_installed()
    try:
        captcha_token = asyncio.run(_extract_captcha_token_with_playwright(url_base, timeout_ms))
    except Exception as e:
        logger.error(f"[Hybrid] Error al obtener token: {e}")
        return PinRedeemResult(False, f"Error obteniendo CaptchaToken: {e}", pin_code, player_id)

    if not captcha_token:
        return PinRedeemResult(False, "No se pudo obtener CaptchaToken", pin_code, player_id)

    # 2) Construir payload y hacer POST con httpx
    nombre = cfg.get('nombre_completo') or cfg.get('nombre_cliente') or "Usuario Revendedor"
    born_at = cfg.get('fecha_nacimiento') or "01/01/1995"
    nacionalidad = cfg.get('nacionalidad') or "VE"
    redeem_country_id = str(cfg.get('redeem_country_id') or "5")
    country_id = str(cfg.get('country_id') or "5")
    company_name = str(cfg.get('company_name') or "HypeMexico")
    product_id = str(cfg.get('product_id') or "2630")
    timeout_s = float(cfg.get('http_timeout_s') or 30)

    payload = {
        "Key": pin_code,
        "RedeemCountryId": redeem_country_id,
        "CountryId": country_id,
        "CompanyName": company_name,
        "ProductId": product_id,
        "Customer.Name": nombre,
        "Customer.BornAt": born_at,
        "Customer.NationalityAlphaCode": nacionalidad,
        "GameAccountId": player_id,
        "privacy": "on",
        "CaptchaToken": captcha_token,
    }

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

    try:
        with httpx.Client(timeout=timeout_s, follow_redirects=True, headers=headers) as client:
            client.get(BASE_URL)
            resp = client.post(REDEEM_URL, content=json.dumps(payload))
            ct = resp.headers.get("content-type", "")
            if "application/json" in ct.lower():
                data = resp.json()
            else:
                data = {"raw": resp.text}
            if 200 <= resp.status_code < 300:
                msg = data.get("message") if isinstance(data, dict) else None
                return PinRedeemResult(True, msg or "Recarga completada (híbrido)", pin_code, player_id)
            else:
                err_msg = data.get("message") if isinstance(data, dict) else None
                if not err_msg:
                    err_msg = f"HTTP {resp.status_code}"
                logger.warning(f"[Hybrid] Fallo POST: {err_msg}")
                return PinRedeemResult(False, str(err_msg), pin_code, player_id)
    except Exception as e:
        logger.error(f"[Hybrid] Error en POST httpx: {e}")
        return PinRedeemResult(False, f"Error POST: {e}", pin_code, player_id)
