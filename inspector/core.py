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
    official_features = None
    counters = Counter()
    for entry in entries:
        request, response = entry.get("request") or {}, entry.get("response") or {}
        url = request.get("url", "")
        try:
            parsed = urlsplit(url)
        except ValueError:
            continue
        if (parsed.scheme == "https" and parsed.hostname in
                {"www.pragmaticplay.com", "pragmaticplay.com"}
                and request.get("method") == "GET"
                and response.get("status") == 200
                and re.fullmatch(r"/(?:en|es)/games/[a-z0-9-]+/?", parsed.path)):
            from .official_rules import extract_official_feature_rules
            source = har_body(response.get("content") or {})
            if 0 < len(source) <= 10_000_000:
                slug = parsed.path.rstrip("/").split("/")[-1]
                found = extract_official_feature_rules(source, game_slug=slug)
                if found["status"] == "PUBLIC_DESCRIPTION_CONDITION_PARSED":
                    official_features = found
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
    selector_raw = response.get("reel_set")
    # No persistir el valor sin validarlo; podría contener un payload inesperado.
    if isinstance(selector_raw, str) and re.fullmatch(r"[0-9]{1,3}", selector_raw):
        current_set_id = str(int(selector_raw))
        current_status = ("DECLARED_AND_PRESENT_IN_INIT_SETS"
                          if current_set_id in sets else "DECLARED_BUT_NOT_IN_INIT_SETS")
    elif selector_raw is None:
        current_set_id = None
        current_status = "NOT_OBSERVED"
    else:
        current_set_id = None
        current_status = "UNRECOGNIZED_FORMAT"
    selected_set_model = direct["sets"].get(current_set_id, {}) if current_set_id else {}
    selector_evidence = {
        "source": "doInit", "selector_key": "reel_set",
        "status": current_status,
        "current_reel_set": current_set_id,
        "current_set_direct_model_unique_screens": selected_set_model.get("unique_screen_count"),
        "future_set_transition_inferred": False,
        "global_server_mathematics_known": False,
        "observed_doSpin_selectors": [],
    }
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
    from .line_evaluator import extract_line_contract
    line_contract = extract_line_contract(client["scene"], width, height)
    from .payment_contract import build_payment_contract
    pay_contract = build_payment_contract(
        paytable,
        scatter_data=response.get("scatters"),
        line_paths=client["scene"].get("line_paths_declarative") or [],
        client_methods=[
            x["name"] for x in animation["parser_and_reel_methods"]
            if isinstance(x, dict) and isinstance(x.get("name"), str)
        ],
    )
    if official_features is None:
        official_features = {
            "schema": "inspector/official-feature-rules/v1",
            "status": "NOT_AVAILABLE_IN_HAR",
            "bonus_trigger": None,
            "server_feature_execution_verified": False,
            "complete_feature_rules_proven": False,
        }
    pay_contract["official_description_feature_rules"] = official_features
    pay_contract["explicit_line_geometry_status"] = line_contract["status"]
    pay_contract["payline_geometry_complete"] = line_contract["geometry_complete"]
    from .line_stake_evidence import (inspect_line_scene, inspect_wild_alphabets,
                                      inspect_stake_declarations)
    line_scene = inspect_line_scene(src, symbol, width, height)
    from .line_candidates import scan_line_candidates
    line_candidates = scan_line_candidates(src, symbol, width, height)
    stake = inspect_stake_declarations(response)
    wild = inspect_wild_alphabets(sets)
    full_evidence = {
        "schema": "inspector/line-stake-bundle/v1",
        "game_symbol": symbol,
        "paylines": line_scene,
        "monetary": stake,
        "wild": wild,
        "actual_win_validation": "UNAVAILABLE_WITHOUT_COMPLETE_SEMANTICS",
        "server_generator_extracted": False,
    }
    # Solo líneas con referencias espaciales coherentes, y no sobreafirmar
    # que el servidor las haya habilitado para la apuesta actual.
    pay_contract["declared_line_paths"] = [
        row["positions_row_major"] for row in line_scene["lines_recovered"]
    ]
    pay_contract["scene_declared_line_paths_recovered"] = bool(
        line_scene["complete_declared_scene_paths_recovered"]
    )
    pay_contract["payline_geometry_complete"] = False
    pay_contract["active_line_set_verified"] = False
    pay_contract["bet_denominator_known"] = False
    summary = {
        "schema": SCHEMA, "game_symbol": symbol,
        "doInit_count": len(initializations), "historical_spins": len(spins),
        "extractor_spins_sent": 0, "assets_indexed": len(static_assets),
        "has_build_js": any(x.endswith("/build.js") for x in static_assets),
        "reel_set_count": len(sets),
        "reel_strip_count": sum(len(x) for x in sets.values()),
        "geometry": {"width": width, "height": height, "type": response.get("st")},
        "paytable_symbols": len(paytable),
        "declared_payline_count": line_contract["declared_line_count"],
        "line_geometry_status": line_contract["status"],
        "explicit_paths_ready": len(line_contract["extracted_paths"]),
        "payment_line_cash_validation_possible": False,
        "payline_components": line_scene["vs_lines_definitions_count"],
        "recovered_line_paths": len(line_scene["lines_recovered"]),
        "line_scene_scan_status": line_scene["line_path_coverage"],
        "lineinfo_fields": {
            v["field"]: v["line_info_records"]
            for v in line_candidates["candidate_fields"]
        },
        "wild_W_reels": wild["reels_containing_W_directly_by_set"],
        "stake_sc_values_count": stake["sc_count"],
        "stake_bls_values": stake["bls_values"],
        "stake_sc_times_bls_min": stake["hypothetical_sc_times_bls"]["minimum"],
        "stake_sc_times_bls_max": stake["hypothetical_sc_times_bls"]["maximum"],
        "stake_formula_proven": False,
        "paytable_two_symbol_paying_ids": pay_contract["symbols_with_2_count_payout"],
        "paytable_three_symbol_paying_ids": pay_contract["symbols_with_3_count_payout"],
        "scatter_declaration_status": pay_contract["scatter"]["status"],
        "free_spins_trigger_verified": False,
        "official_feature_rules_status": official_features["status"],
        "official_bonus_min_money_symbols": (
            official_features["bonus_trigger"]["minimum_money_symbols"]
            if official_features.get("bonus_trigger") else None),
        "official_initial_free_spins": (
            official_features["bonus_trigger"]["awarded_free_spins"]
            if official_features.get("bonus_trigger") else None),
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
        "initial_reel_set_status": selector_evidence["status"],
        "initial_reel_set": selector_evidence["current_reel_set"],
        "initial_direct_screen_count": selector_evidence["current_set_direct_model_unique_screens"],
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
    write_json(out / "payment_contract.json", pay_contract)
    write_json(out / "line_geometry.json", line_contract)
    write_json(out / "line_stake_evidence.json", full_evidence)
    write_json(out / "line_candidates.json", line_candidates)
    write_json(out / "official_feature_rules.json", official_features)
    write_json(out / "direct_model.json", direct)
    write_json(out / "client_evidence.json", client)
    write_json(out / "animation_origin_trace.json", animation)
    write_json(out / "reel_set_selector_evidence.json", selector_evidence)
    write_json(out / "assets_index.json", static_assets)
    write_json(out / "historical_audit.json", audits)
    # HAR depurado y reducido: solo doInit y claves públicas conocidas.
    # Sin cookies, cabeceras, tokens, sesión, giros, scripts propietarios.
    safe_entries = []
    for init in initializations:
        r = init["response"]
        safe = {k: v for k, v in r.items()
                if k in PUBLIC_INIT or REEL_NAME.fullmatch(k)}
        # Solo exportar scatters en su gramática numérica validada, nunca tokens.
        if pay_contract["scatter"]["status"] == "DECLARED_TABLE_PARSED":
            from .payment_contract import SCATTER_RE
            if "scatters" in r and SCATTER_RE.fullmatch(r["scatters"]):
                safe["scatters"] = r["scatters"]
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
        "Selector inicial reel_set: " + str(selector_evidence["current_reel_set"])
        + " [" + selector_evidence["status"] + "]",
        "Pantallas modelo directo para reel_set inicial: "
        + str(selector_evidence["current_set_direct_model_unique_screens"]),
        "Origen de símbolos (estático): " + animation["interpretation"],
        "Selectores observados en la captura: " + ", ".join(summary["animation_server_selector_observed_in_capture"]),
        "Evidencia de parada visual desde resultado del servidor: " + client["conclusions"]["server_result_drives_visual_stop_evidence"],
        "Simulador local acoplado a escena: " + str(client["scene"]["offline_server_attachment"]),
        "Recursos estáticos indexados: " + str(len(static_assets)),
        "build.js observado: " + str(summary["has_build_js"]),
        "LineInfo por campo: " + ", ".join(
            f"{x['field']}={x['line_info_records']}" for x in line_candidates["candidate_fields"]),
        "Líneas extraídas de escena: " + str(len(line_scene["lines_recovered"]))
        + "; cobertura: " + line_scene["line_path_coverage"],
        "sc declaradas: " + str(stake["sc_count"])
        + "; bls declaradas: " + str(stake["bls_values"]),
        "Hipótesis sc*bls mínimo/máximo: "
        + str(stake["hypothetical_sc_times_bls"]["minimum"]) + "/"
        + str(stake["hypothetical_sc_times_bls"]["maximum"]),
        "Fórmula de apuesta real/semántica W: DESCONOCIDAS",
        "Geometría de líneas: " + line_contract["status"],
        "Líneas declaradas: " + str(line_contract["declared_line_count"]),
        "Recorridos de línea verificados: " + str(len(line_contract["extracted_paths"])),
        "Símbolos con premio declarado desde 2 coincidencias: "
        + ", ".join(summary["paytable_two_symbol_paying_ids"]),
        "Símbolos con premio declarado desde 3 coincidencias: "
        + ", ".join(summary["paytable_three_symbol_paying_ids"]),
        "Tabla scatter/free spins: " + summary["scatter_declaration_status"],
        "Ficha oficial de features: " + summary["official_feature_rules_status"],
        "Umbral de money symbols indicado en ficha oficial: " + str(summary["official_bonus_min_money_symbols"]),
        "Free spins iniciales indicados en ficha oficial: " + str(summary["official_initial_free_spins"]),
        "Verificación completa del disparo de free spins: NO",
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
