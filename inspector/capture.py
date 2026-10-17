"""Captura pasiva de la demo oficial con Playwright, sin acciones de juego.

El HAR original debe mantenerse privado: puede incluir identificadores de sesión.
Este archivo NO omite cookies del HAR crudo: es la etapa de análisis la que
genera artefactos reducidos y seguros para subir a GitHub Actions.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
import re
import time
from urllib.parse import parse_qsl, urlsplit

OFFICIAL = {"www.pragmaticplay.com", "pragmaticplay.com"}
DEMO = "demogamesfree.pragmaticplay.net"
GAME_ACTION = re.compile(r"/(?:ge/v\d+/)?gameService$")


def permitted_url(url: str) -> bool:
    try:
        p = urlsplit(url)
    except ValueError:
        return False
    if p.scheme != "https":
        return False
    if p.hostname in OFFICIAL:
        return bool(re.fullmatch(r"/(?:en|es)/games/[A-Za-z0-9_-]+/?", p.path))
    return (p.hostname == DEMO and p.path.endswith("/openGame.do")
            and "gameSymbol=" in p.query)


def should_allow_request(request) -> bool:
    """Permite GET/HEAD y el doInit oficial; no lee POST binarios de terceros.

    Algunos CDNs y sistemas de telemetría hacen POST con bytes no UTF-8.
    La propiedad post_data de Playwright lanza UnicodeDecodeError al intentar
    decodificarlos. Por eso solo se inspecciona ese cuerpo tras validar host,
    ruta y método.
    """
    method = request.method.upper()
    if method in {"GET", "HEAD"}:
        return True
    if method != "POST":
        return False
    try:
        parsed = urlsplit(request.url)
    except ValueError:
        return False
    if parsed.scheme != "https" or parsed.hostname != DEMO or not GAME_ACTION.search(parsed.path):
        return False
    try:
        body = dict(parse_qsl(request.post_data or "", keep_blank_values=True))
    except (UnicodeError, ValueError, TypeError):
        return False
    return body.get("action") == "doInit"


def capture_official_demo(url: str, har_file: str | Path,
                          *, duration_s: int = 70, headless: bool = True) -> dict:
    if not permitted_url(url):
        raise ValueError("Solo se admite la ficha oficial del juego o su launcher demo")
    if not 10 <= duration_s <= 180:
        raise ValueError("duration_s debe estar entre 10 y 180 segundos")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Instalar Playwright: pip install playwright") from exc
    destination = Path(har_file)
    destination.parent.mkdir(parents=True, exist_ok=True)
    report = {"source": url, "init_observed": 0, "blocked_mutations": 0,
              "navigation_warnings": [], "spin_requests_sent_by_inspector": 0}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context(
            service_workers="block",
            accept_downloads=False,
            viewport={"width": 1280, "height": 800},
            record_har_path=str(destination),
            record_har_content="embed",
            record_har_mode="full",
        )
        def restrict(route):
            if should_allow_request(route.request):
                route.continue_()
            else:
                report["blocked_mutations"] += 1
                route.abort()

        context.route("**/*", restrict)

        def count_initializations(response):
            try:
                req = response.request
                p = urlsplit(response.url)
                if (req.method == "POST" and p.hostname == DEMO
                        and GAME_ACTION.search(p.path)
                        and should_allow_request(req)
                        and response.status == 200):
                    report["init_observed"] += 1
            except Exception:
                pass

        context.on("response", count_initializations)
        try:
            page = context.new_page()
            candidate = url if urlsplit(url).hostname == DEMO else None
            if not candidate:
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                except Exception as exc:
                    report["navigation_warnings"].append(
                        "Ficha no completó la navegación: " + type(exc).__name__)
                # Encontrar la demo sin pulsar Play. Puede figurar en data-game-src.
                try:
                    elements = page.locator("iframe[data-game-src],iframe[src]")
                    for i in range(min(elements.count(), 30)):
                        item = elements.nth(i)
                        link = item.get_attribute("data-game-src") or item.get_attribute("src")
                        if link:
                            link = html.unescape(link)
                        if link and permitted_url(link) and urlsplit(link).hostname == DEMO:
                            candidate = link
                            break
                except Exception as exc:
                    report["navigation_warnings"].append("DOM: " + type(exc).__name__)
                if not candidate:
                    markup = page.content()
                    for found in re.findall(r"data-game-src=[\"']([^\"']+)", markup):
                        found = html.unescape(found)
                        if permitted_url(found) and urlsplit(found).hostname == DEMO:
                            candidate = found
                            break
            if not candidate:
                raise RuntimeError("No se encontró el launcher demo en la ficha oficial")
            report["demo_origin"] = DEMO
            try:
                page.goto(candidate, wait_until="domcontentloaded", timeout=30000)
            except Exception as exc:
                report["navigation_warnings"].append(
                    "Launcher no completó la navegación: " + type(exc).__name__)
            first_init_time = None
            end = time.monotonic() + duration_s
            while time.monotonic() < end:
                try:
                    page.wait_for_timeout(1000)
                except Exception as exc:
                    report["navigation_warnings"].append("Navegador: " + type(exc).__name__)
                    break
                if report["init_observed"] and first_init_time is None:
                    first_init_time = time.monotonic()
                # Dejar tiempo para el código estático después de doInit.
                if first_init_time is not None and time.monotonic() - first_init_time >= 12:
                    break
        finally:
            context.close()  # vuelca el HAR a disco
            browser.close()
    return report
