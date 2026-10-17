"""Analizador HAR offline: sin peticiones de red, giros ni cambios de sesión.

Alcance: declaraciones de doInit, assets estáticos y modelo restringido de
paradas circulares. Nunca certifica la validez global del RNG del servidor.
"""
from __future__ import annotations

import base64
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import parse_qsl, urlencode, urlsplit

SCHEMA = "inspector/pragmatic-static/v1"
DEMO_HOST = "demogamesfree.pragmaticplay.net"
GAME_PATH = re.compile(r"/(?:ge/v\d+/)?gameService$")
REEL_NAME = re.compile(r"reel_set(\d+)$")
STATIC_PATH = re.compile(r"/gs2c/common/v3/games-html5/games/[^/]+/[^/]+/desktop/.+\.(?:js|json)$")
MAX_HAR = 750 * 1024 * 1024
MAX_RESPONSE = 16 * 1024 * 1024
PUBLIC_INIT = {
    "sw", "sh", "st", "sver", "bls", "sc", "reel_set_size",
    "total_bet_min", "total_bet_max", "paytable",
}
CODE_MARKERS = {
    "reel_set": r"reel_set|reelStrip|ReelStrip|reelSet",
    "screen_result": r"ResultScreenSymbols|screenSymbols|ScreenSymbols",
    "paytable": r"paytable|payTable|winLines|payLines",
    "transformation": r"replaceSymbols|splitSymbol|expand|transform",
    "bonus": r"freeSpin|respin|Bonus|bonus",
    "rng_word_not_proof": r"Math\.random|randomGenerator|\bRNG\b",
}


def form(text: str) -> dict[str, str]:
    if not text:
        return {}
    # Los pares de Pragmatic se codifican en formato URL-encoded.
    return dict(parse_qsl(text, keep_blank_values=True, errors="replace"))


def har_body(content: dict) -> bytes:
    value = content.get("text", "")
    if not isinstance(value, str):
        return b""
    if content.get("encoding") == "base64":
        try:
            return base64.b64decode(value, validate=True)
        except (ValueError, base64.binascii.Error):
            return b""
    return value.encode("utf-8", "replace")


def circular_windows(sequence: str, length: int) -> list[str]:
    if not sequence or length < 1 or length > len(sequence):
        return []
    return sorted({(sequence + sequence[:length-1])[i:i+length]
                   for i in range(len(sequence))})


def parse_paytable(value: str) -> dict:
    result = {}
    for unit in value.split(";"):
        if "~" not in unit:
            continue
        symbol, payouts = unit.split("~", 1)
        if not symbol or len(symbol) > 12:
            continue
        row = {}
        for entry in payouts.split(","):
            if ":" in entry:
                count, amount = entry.split(":", 1)
                if count.isdigit():
                    row[count] = amount
        if row:
            result[symbol] = row
    return result


def reel_sets(response: dict) -> dict:
    result = {}
    for key, value in response.items():
        match = REEL_NAME.fullmatch(key)
        if not match or not isinstance(value, str):
            continue
        strips = []
        for index, sequence in enumerate(value.split("~")):
            if not sequence or len(sequence) > 200000:
                continue
            symbols = dict(sorted(Counter(sequence).items()))
            strips.append({
                "index": index, "length": len(sequence),
                "sequence": sequence, "alphabet": sorted(symbols),
                "symbol_counts": symbols,
                "direct_circular_windows": {
                    str(n): circular_windows(sequence, n)
                    for n in range(1, min(4, len(sequence)) + 1)
                },
            })
        if strips:
            result[match.group(1)] = strips
    return dict(sorted(result.items(), key=lambda it: int(it[0])))


def observe_spin(screen: str, sets: dict, width: int, height: int) -> dict:
    """Contraste con modelo directo, sin asumir que sea el generador real."""
    result = {"screen_length": len(screen), "geometry_matches": False,
              "direct_stop_model_match": False, "tested_variants": []}
    if width < 1 or height < 1 or width > 12 or height > 12:
        return result
    if len(screen) != width * height:
        return result
    result["geometry_matches"] = True
    for set_id, strips in sets.items():
        if len(strips) != width:
            continue
        for direction in ("row_major", "column_major"):
            columns = [
                "".join(screen[row * width + col] for row in range(height))
                if direction == "row_major" else screen[col*height:(col+1)*height]
                for col in range(width)
            ]
            matches = sum(
                col in strips[i]["direct_circular_windows"].get(str(height), [])
                if height <= 4 else col in circular_windows(strips[i]["sequence"], height)
                for i, col in enumerate(columns)
            )
            result["tested_variants"].append(
                {"reel_set": set_id, "orientation": direction,
                 "matched_columns": matches, "total_columns": width})
            if matches == width:
                result["direct_stop_model_match"] = True
    result["global_server_validity"] = "UNKNOWN"
    return result


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def analyze_har(har_path: str | Path, output_dir: str | Path) -> dict:
    src, out = Path(har_path), Path(output_dir)
    if not src.is_file() or src.stat().st_size > MAX_HAR:
        raise ValueError("HAR inexistente o supera 750 MiB")
    data = json.loads(src.read_text(encoding="utf-8-sig"))
    entries = data.get("log", {}).get("entries", [])
    if not isinstance(entries, list):
        raise ValueError("HAR inválido: log.entries no es una lista")
    initializations, spins, static_assets = [], [], {}
    counters = Counter()
    for entry in entries:
        request, response = entry.get("request") or {}, entry.get("response") or {}
        url = request.get("url", "")
        try:
            parsed = urlsplit(url)
        except ValueError:
            continue
        if parsed.scheme != "https" or parsed.hostname != DEMO_HOST:
            continue
        method = request.get("method", "")
        status = response.get("status", 0)
        path = parsed.path
        if method == "POST" and GAME_PATH.search(path):
            req_form = form((request.get("postData") or {}).get("text", ""))
            action = req_form.get("action")
            counters["provider_actions_in_input"] += 1
            if status != 200 or action not in {"doInit", "doSpin"}:
                continue
            raw = har_body(response.get("content") or {})
            if len(raw) > MAX_RESPONSE:
                continue
            resp_form = form(raw.decode("utf-8", "replace"))
            if action == "doInit" and any(REEL_NAME.fullmatch(k) for k in resp_form):
                initializations.append({"symbol": req_form.get("symbol"),
                                        "response": resp_form})
            elif action == "doSpin":
                spins.append({"screen": resp_form.get("s", ""),
                              "action": "doSpin",
                              "observed_fields": sorted(set(resp_form).intersection({
                                  "reel_set", "n_reel_set", "reel_set_size",
                                  "tmb", "srf", "n_rsl", "msr"}))})
            continue
        if method == "GET" and status == 200 and STATIC_PATH.search(path):
            content = har_body(response.get("content") or {})
            if not content or len(content) > MAX_RESPONSE:
                continue
            filename = path.rsplit("/", 1)[-1]
            code_indicators = {}
            if filename.endswith(".js"):
                text = content.decode("utf-8", "replace")
                code_indicators = {k: len(re.findall(pattern, text, re.I))
                                   for k, pattern in CODE_MARKERS.items()}
            static_assets[path] = {
                "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
                "indicators": code_indicators,
            }
    latest = initializations[-1] if initializations else {"symbol": None, "response": {}}
    response = latest["response"]
    sets = reel_sets(response)
    paytable = parse_paytable(response.get("paytable", ""))
    width = int(response.get("sw", "0")) if response.get("sw", "").isdigit() else 0
    height = int(response.get("sh", "0")) if response.get("sh", "").isdigit() else 0
    from .direct_model import compute_direct_model
    from .client_evidence import inspect_client_har
    direct = compute_direct_model(sets, width, height)
    audits = [observe_spin(x["screen"], sets, width, height)
              for x in spins if isinstance(x["screen"], str) and len(x["screen"]) <= 300]
    symbol = latest.get("symbol")
    if not symbol:
        for p in static_assets:
            match = re.search(r"/games/[^/]+/([^/]+)/desktop/", p)
            if match:
                symbol = match.group(1)
                break
    observed = {
        "doInit": sorted(set().union(*(
            set(item["response"]).intersection({
                "reel_set", "n_reel_set", "reel_set_size",
                "tmb", "srf", "n_rsl", "msr"})
            for item in initializations
        )) if initializations else set()),
        "doSpin": sorted(set().union(*(
            set(item.get("observed_fields", [])) for item in spins
        )) if spins else set()),
    }
    client = inspect_client_har(src, symbol, observed_wire_keys=observed)
    animation = client["animation_origin_trace"]
    summary = {
        "schema": SCHEMA, "game_symbol": symbol,
        "doInit_count": len(initializations), "historical_spins": len(spins),
        "extractor_spins_sent": 0, "assets_indexed": len(static_assets),
        "has_build_js": any(x.endswith("/build.js") for x in static_assets),
        "reel_set_count": len(sets),
        "reel_strip_count": sum(len(x) for x in sets.values()),
        "geometry": {"width": width, "height": height, "type": response.get("st")},
        "paytable_symbols": len(paytable),
        "complete_server_math_known": False,
        "final_outcome_universe_known": False,
        "forbidden_final_outcomes_proven": [],
        "scope": "DIRECT_CIRCULAR_RAW_STOP_NO_TRANSFORMATIONS",
        "status": "OK_INIT" if initializations else "NO_INIT",
        "historical_direct_model_audit": audits,
        "direct_model_union_unique_screen_count": direct["union_unique_screen_count"],
        "direct_model_duplicates_removed": direct["duplicated_across_sets"],
        "client_evidence_status": client["scene"]["status"],
        "client_server_result_visual_stop_evidence": client["conclusions"]["server_result_drives_visual_stop_evidence"],
        "animation_protocol_origin": animation["interpretation"],
        "animation_server_selector_observed_in_capture": [
            k for k, v in animation["protocol_fields"].items()
            if v["status"] == "OBSERVED_IN_CAPTURE"
        ],
    }
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "summary.json", summary)
    write_json(out / "reel_rules.json", {
        "scope": summary["scope"], "game_symbol": symbol, "sets": sets,
        "does_not_prove_final_outcome_impossibility": True,
    })
    write_json(out / "paytable.json", paytable)
    write_json(out / "direct_model.json", direct)
    write_json(out / "client_evidence.json", client)
    write_json(out / "animation_origin_trace.json", animation)
    write_json(out / "assets_index.json", static_assets)
    write_json(out / "historical_audit.json", audits)
    # HAR depurado y reducido: solo doInit y claves públicas conocidas.
    # Sin cookies, cabeceras, tokens, sesión, giros, scripts propietarios.
    safe_entries = []
    for init in initializations:
        r = init["response"]
        safe = {k: v for k, v in r.items()
                if k in PUBLIC_INIT or REEL_NAME.fullmatch(k)}
        safe_entries.append({
            "request": {"url": "https://" + DEMO_HOST + "/gs2c/ge/v5/gameService",
                        "method": "POST",
                        "postData": {"mimeType": "application/x-www-form-urlencoded",
                                     "text": urlencode({"action": "doInit", "symbol": init["symbol"] or ""})}},
            "response": {"status": 200,
                         "content": {"mimeType": "text/plain", "text": urlencode(safe)}},
        })
    write_json(out / "sanitized-init.har", {"log": {"version": "1.2",
                                                    "creator": {"name": "Inspector", "version": "1"},
                                                    "entries": safe_entries}})
    lines = [
        "# Informe de Inspector",
        "",
        "Juego: " + str(symbol),
        "Estado: " + summary["status"],
        "Inicializaciones: " + str(len(initializations)),
        "Conjuntos: " + str(len(sets)),
        "Tiras: " + str(summary["reel_strip_count"]),
        "Pantallas únicas en modelo directo: " + str(direct["union_unique_screen_count"]),
        "Duplicados entre conjuntos: " + str(direct["duplicated_across_sets"]),
        "Escena del cliente: " + client["scene"]["status"],
        "Origen de símbolos (estático): " + animation["interpretation"],
        "Selectores observados en la captura: " + ", ".join(summary["animation_server_selector_observed_in_capture"]),
        "Evidencia de parada visual desde resultado del servidor: " + client["conclusions"]["server_result_drives_visual_stop_evidence"],
        "Simulador local acoplado a escena: " + str(client["scene"]["offline_server_attachment"]),
        "Recursos estáticos indexados: " + str(len(static_assets)),
        "build.js observado: " + str(summary["has_build_js"]),
        "Giros enviados por Inspector: 0",
        "Giros históricos observados en el HAR: " + str(len(spins)),
        "",
        "## Límite demostrado",
        "Las tiras describen paradas directas circulares sin transformaciones.",
        "Que una pantalla no coincida NO significa que el servidor la prohíba.",
        "Las probabilidades y el universo de resultados finales permanecen DESCONOCIDOS.",
        "Los indicadores del JavaScript son búsquedas léxicas, no evidencia de RNG local.",
        "",
        "## Privacidad",
        "sanitized-init.har solo contiene doInit con claves de configuración permitidas.",
        "Nunca publicar el HAR original ni archivos que puedan incluir identificadores de sesión.",
    ]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary
