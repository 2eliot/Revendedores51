import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from playwright.async_api import async_playwright

logger = logging.getLogger("redeemer_service")
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

HYPE_BASE_URL = "https://redeem.hype.games/"
HYPE_API_URL = "https://redeem.hype.games/api/v1/account"

RECAPTCHA_SITEKEY = "6Lf_DWEpAAAAEg4rEg_3N5H0G7-O"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class RedeemRequest(BaseModel):
    Key: str

    Customer_Name: str = Field(alias="Customer.Name")
    Customer_BornAt: str = Field(alias="Customer.BornAt")
    Customer_NationalityAlphaCode: str = Field(default="VE", alias="Customer.NationalityAlphaCode")

    GameAccountId: str

    RedeemCountryId: str = "5"
    CountryId: str = "5"
    CompanyName: str = "HypeMexico"
    ProductId: str = "2630"

    class Config:
        populate_by_name = True


class RedeemResponse(BaseModel):
    success: bool
    status_code: int
    data: Dict[str, Any]
    captcha_token_present: bool


async def _get_recaptcha_token(*, timeout_ms: int, user_agent: str) -> str:
    """Obtiene CaptchaToken usando Playwright y cierra el navegador inmediatamente."""
    async with async_playwright() as p:
        browser = None
        try:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context = await browser.new_context(
                user_agent=user_agent,
                viewport={"width": 1366, "height": 768},
                locale="es-VE",
            )
            page = await context.new_page()

            await page.goto(HYPE_BASE_URL, wait_until="domcontentloaded", timeout=timeout_ms)
            await page.wait_for_load_state("networkidle", timeout=timeout_ms)

            # Esperar a que cargue grecaptcha
            await page.wait_for_function(
                "() => typeof window.grecaptcha !== 'undefined' && typeof window.grecaptcha.execute === 'function'",
                timeout=timeout_ms,
            )

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
                raise RuntimeError("No se pudo obtener CaptchaToken válido")

            return token
        finally:
            if browser:
                await browser.close()


def _parse_httpx_response(resp: httpx.Response) -> Dict[str, Any]:
    ct = (resp.headers.get("content-type") or "").lower()
    if "application/json" in ct:
        try:
            return resp.json()
        except Exception:
            return {"raw": resp.text}
    return {"raw": resp.text}


async def _redeem_with_httpx(*, payload: Dict[str, Any], timeout_s: float, user_agent: str) -> httpx.Response:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8",
        "Origin": "https://redeem.hype.games",
        "Referer": "https://redeem.hype.games/",
        "User-Agent": user_agent,
    }

    timeout = httpx.Timeout(timeout_s, connect=timeout_s)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
        # Warm-up para cookies/sesión
        await client.get(HYPE_BASE_URL)
        return await client.post(HYPE_API_URL, content=json.dumps(payload))


app = FastAPI(title="Inefable Redeemer Service", version="1.0.0")


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/redeem", response_model=RedeemResponse)
async def redeem(req: RedeemRequest):
    timeout_ms = int(os.environ.get("PW_TIMEOUT_MS", "30000"))
    http_timeout_s = float(os.environ.get("HTTP_TIMEOUT_S", "30"))
    user_agent = os.environ.get("USER_AGENT", DEFAULT_USER_AGENT)

    # Fase de seguridad: Playwright -> CaptchaToken
    try:
        captcha_token = await _get_recaptcha_token(timeout_ms=timeout_ms, user_agent=user_agent)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Timeout obteniendo CaptchaToken")
    except Exception as e:
        logger.exception("Error obteniendo CaptchaToken")
        raise HTTPException(status_code=502, detail=f"Error obteniendo CaptchaToken: {str(e)}")

    # Fase de ejecución: HTTPX -> POST directo
    payload = {
        "Key": req.Key,
        "Customer.Name": req.Customer_Name,
        "Customer.BornAt": req.Customer_BornAt,
        "Customer.NationalityAlphaCode": req.Customer_NationalityAlphaCode,
        "GameAccountId": req.GameAccountId,
        "CaptchaToken": captcha_token,
        "RedeemCountryId": str(req.RedeemCountryId),
        "CountryId": str(req.CountryId),
        "CompanyName": str(req.CompanyName),
        "ProductId": str(req.ProductId),
    }

    try:
        resp = await _redeem_with_httpx(payload=payload, timeout_s=http_timeout_s, user_agent=user_agent)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout en POST /api/v1/account")
    except Exception as e:
        logger.exception("Error en POST /api/v1/account")
        raise HTTPException(status_code=502, detail=f"Error HTTP: {str(e)}")

    data = _parse_httpx_response(resp)
    success = 200 <= resp.status_code < 300

    return RedeemResponse(
        success=success,
        status_code=resp.status_code,
        data=data if isinstance(data, dict) else {"raw": str(data)},
        captcha_token_present=True,
    )
