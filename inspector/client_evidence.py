"""Evidencia estática sobre responsabilidades del cliente, sin ejecutar JS.

Lee recursos incorporados al HAR original, únicamente del origen demo oficial.
No publica código de terceros, cookies, URLs completas ni identificadores.
Separa expresamente el renderizado de la matemática de producción.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from .core import DEMO_HOST, MAX_RESPONSE, har_body

SCHEMA = "inspector/client-evidence/v1"
BUILD_RE = re.compile(r"/games/[^/]+/([^/]+)/desktop/build\.js$")
SCENE_RE = re.compile(r"/games/[^/]+/([^/]+)/desktop/game/game(\d{3})\.json$")
MAX_SCENE = 24 * 1024 * 1024
MAX_COMPONENT_EXAMPLES = 40
SPECIAL_COMPONENTS = {
    "RequestProvider", "VS_ReelsManager", "V4ServerAdapter_Symbols",
    "VS_LinesDefinitions", "ProtocolGroupsParser", "VS_Reel", "StageSpin",
    "GameLogicRuntime", "ServerLink", "ServerInterface", "OfflineServer",
    "VideoSlotsConnection", "RandomCATStarter",
}


def _resource_map(har_path: str | Path, symbol: str | None) -> tuple[bytes, dict[int, bytes], dict]:
    """Leer solo build.js y gameNNN.json del juego, nunca URLs de sesión."""
    har = json.loads(Path(har_path).read_text(encoding="utf-8-sig"))
    build = b""
    parts: dict[int, bytes] = {}
    note = {"game_symbol": symbol, "build_js_found": False, "scene_parts": [],
            "ignored_oversized_resources": 0}
    for entry in har.get("log", {}).get("entries", []):
        req, resp = entry.get("request") or {}, entry.get("response") or {}
        if req.get("method") != "GET" or resp.get("status") != 200:
            continue
        parsed = urlsplit(req.get("url", ""))
        if parsed.scheme != "https" or parsed.hostname != DEMO_HOST:
            continue
        match_build, match_scene = BUILD_RE.search(parsed.path), SCENE_RE.search(parsed.path)
        if match_build:
            resource_symbol = match_build.group(1)
        elif match_scene:
            resource_symbol = match_scene.group(1)
        else:
            continue
        if symbol and resource_symbol != symbol:
            continue
        payload = har_body(resp.get("content") or {})
        if not payload or len(payload) > MAX_RESPONSE:
            note["ignored_oversized_resources"] += 1
            continue
        if match_build:
            build = payload
            note["build_js_found"] = True
        else:
            index = int(match_scene.group(2))
            if index < 100:
                parts[index] = payload
    note["scene_parts"] = sorted(parts)
    return build, parts, note


def _inspect_source(build: bytes) -> dict:
    result = {
        "status": "NOT_CAPTURED" if not build else "INSPECTED",
        "proofs": {},
        "source_excerpt_published": False,
        "limitations": ["Las funciones de cliente no demuestran el RNG ni las reglas de producción del servidor."],
    }
    if not build:
        return result
    text = build.decode("utf-8", "replace")
    name = "VS_Reel.prototype.GetNextSymbol=function"
    at = text.find(name)
    if at < 0:
        result["proofs"]["get_next_symbol_method"] = "NOT_LOCATED"
    else:
        # Limitar la búsqueda a la función observada, no al resto del bundle.
        snippet = text[at: at + 2800]
        server_screen = ("Vars.ResultScreenSymbols" in snippet and
                         "GetReelScreenSymbols" in snippet and
                         "stopOnScreenSymbols" in snippet)
        raw_strip = ("this.symbolList" in snippet and
                     "this.stopPosition" in snippet)
        result["proofs"]["get_next_symbol_method"] = "LOCATED"
        result["proofs"]["stopping_branch_reads_result_screen_symbols"] = server_screen
        result["proofs"]["alternative_branch_reads_visual_symbol_list"] = raw_strip
        result["proofs"]["method_location_offset"] = at
    request_name = "RequestProvider.prototype.NewRequest=function"
    result["proofs"]["request_provider_online_branch"] = (
        request_name in text and "ServerOptions.isOnline" in
        text[text.find(request_name): text.find(request_name)+450]
    )
    result["proofs"]["generic_offline_server_class_present"] = (
        "OfflineServer.prototype" in text)
    result["proofs"]["protocol_parser_symbol_present"] = (
        "VSProtocolParser" in text)
    result["proofs"]["client_randomness_is_not_backend_rng_evidence"] = True
    return result


def _scene_components(parts: dict[int, bytes]) -> dict:
    report = {
        "status": "NOT_CAPTURED",
        "parsed_parts": sorted(parts),
        "component_types_count": 0,
        "component_counts": {},
        "selected_components": [],
        "offline_server_attachment": "UNKNOWN",
        "reel_stop_uses_response_symbols": "UNKNOWN",
        "server_symbol_mapping_keys": [],
        "screen_symbol_keys": [],
        "line_paths_declarative": [],
        "line_paths_directions": [],
        "line_component_structure": [],
        "explicit_line_path_status": "NOT_DECLARED",
        "line_paths_are_server_math_proof": False,
        "notes": [],
    }
    if not parts:
        return report
    ids = sorted(parts)
    if ids[0] != 0 or ids != list(range(ids[-1] + 1)):
        report["status"] = "INCOMPLETE_PARTS"
        report["notes"].append("Faltan fragmentos gameNNN.json; no se completa la escena")
        return report
    source = b"".join(parts[n] for n in ids)
    if len(source) > MAX_SCENE:
        report["status"] = "SCENE_TOO_LARGE"
        return report
    try:
        parsed = json.loads(source)
    except (ValueError, UnicodeDecodeError):
        report["status"] = "SCENE_NOT_PARSEABLE"
        return report
    count = Counter()
    matches = []
    entries = parsed.get("resources") or []
    if not isinstance(entries, list):
        report["status"] = "SCENE_NOT_PARSEABLE"
        return report
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("type") != "GameObject":
            continue
        roots = (entry.get("data") or {}).get("root") or []
        if not isinstance(roots, list):
            continue
        for obj in roots:
            if not isinstance(obj, dict):
                continue
            for comp in obj.get("components", []):
                if not isinstance(comp, dict):
                    continue
                comp_type = comp.get("componentType")
                if not isinstance(comp_type, str):
                    continue
                count[comp_type] += 1
                if comp_type in SPECIAL_COMPONENTS:
                    matches.append((comp_type, comp.get("serializableData") or {}))
    report["status"] = "PARSED"
    report["component_types_count"] = len(count)
    report["component_counts"] = {k: count[k] for k in sorted(SPECIAL_COMPONENTS) if count[k]}
    report["selected_components"] = sorted(set(k for k, _ in matches))
    for comp_type, data in matches:
        if not isinstance(data, dict):
            continue
        if comp_type == "RequestProvider" and "offlineServer" in data:
            x = data["offlineServer"]
            report["offline_server_attachment"] = "NULL" if x is None else "NON_NULL_REFERENCE"
        elif comp_type == "VS_ReelsManager" and "stopOnScreenSymbols" in data:
            report["reel_stop_uses_response_symbols"] = bool(data["stopOnScreenSymbols"])
        elif comp_type == "V4ServerAdapter_Symbols":
            for src, dest in [
                ("s_markKeysToRemap", "server_symbol_mapping_keys"),
                ("screenSymbolsKeys", "screen_symbol_keys"),
            ]:
                keys = data.get(src)
                if isinstance(keys, list):
                    report[dest] = [k for k in keys[:30]
                                    if isinstance(k, str) and len(k) < 30]
        elif comp_type == "VS_LinesDefinitions":
            lines = data.get("xtEnabled")
            declared_count = data.get("lines")
            count = declared_count if type(declared_count) is int and 0 <= declared_count <= 500 else None
            shape = {
                "scene_field_names": sorted(
                    key for key in data.keys()
                    if isinstance(key, str) and len(key) <= 48)[:50],
                "declared_line_count": count,
                "declared_reel_count": (
                    data.get("reels") if type(data.get("reels")) is int else None),
                "symbol_refs_count": (
                    len(data["symbols"]) if isinstance(data.get("symbols"), list) else None),
                "xt_enabled_entries": len(lines) if isinstance(lines, list) else None,
                "xt_first_entry_field_names": (
                    sorted(lines[0]) if isinstance(lines, list)
                    and lines and isinstance(lines[0], dict) else []),
                "xt_first_nested_type": (
                    lines[0].get("nestedFieldType") if isinstance(lines, list)
                    and lines and isinstance(lines[0], dict)
                    and isinstance(lines[0].get("nestedFieldType"), str) else None),
                "xt_first_serialized_field_names": (
                    sorted((lines[0].get("serializableData") or {}).keys())
                    if isinstance(lines, list) and lines and isinstance(lines[0], dict)
                    and isinstance(lines[0].get("serializableData"), dict) else []),
            }
            report["line_component_structure"].append(shape)
            if isinstance(lines, list):
                for entry in lines[:500]:
                    if not isinstance(entry, dict) or entry.get("nestedFieldType") != "LineInfo":
                        continue
                    record = entry.get("serializableData") or {}
                    path = record.get("symbolIndices")
                    if isinstance(path, list) and 2 <= len(path) <= 12 and all(
                            type(v) is int and 0 <= v <= 250 for v in path):
                        report["line_paths_declarative"].append(path)
                        direction = record.get("isRightToLeft")
                        report["line_paths_directions"].append(
                            direction if type(direction) is bool else None)
            verified = len(report["line_paths_declarative"])
            if count is not None and count > 0 and verified == count:
                report["explicit_line_path_status"] = "COMPLETE_DECLARATION"
            elif count is not None and count > 0:
                report["explicit_line_path_status"] = "COUNT_ONLY_OR_PARTIAL_PATHS"
            elif verified:
                report["explicit_line_path_status"] = "PATHS_WITHOUT_COUNT"
            else:
                report["explicit_line_path_status"] = "NO_EXPLICIT_LINES_IN_COMPONENT"

    return report


def inspect_client_har(har_path: str | Path, game_symbol: str | None = None,
                       *, observed_wire_keys: dict | None = None) -> dict:
    build, parts, captured = _resource_map(har_path, game_symbol)
    code, scene = _inspect_source(build), _scene_components(parts)
    from .animation_trace import analyze_animation_origin
    animation = analyze_animation_origin(build, scene, observed_wire_keys)
    from .win_delivery import inspect_win_delivery
    win_delivery = inspect_win_delivery(build)
    source_branch = code["proofs"].get("stopping_branch_reads_result_screen_symbols") is True
    scene_stop = scene["reel_stop_uses_response_symbols"] is True
    offline_detached = scene["offline_server_attachment"] == "NULL"
    return {
        "schema": SCHEMA,
        "game_symbol": game_symbol,
        "assets": captured,
        "client_code": code,
        "scene": scene,
        "animation_origin_trace": animation,
        "win_delivery_trace": win_delivery,
        "conclusions": {
            "client_has_server_result_symbol_stop_path": source_branch,
            "captured_scene_activates_result_symbol_stops": scene_stop,
            "server_result_drives_visual_stop_evidence": (
                "STRONG_CLIENT_EVIDENCE" if source_branch and scene_stop else "INCOMPLETE"),
            "generic_offline_engine_exists_in_bundle": code["proofs"].get(
                "generic_offline_server_class_present", False),
            "generic_offline_engine_not_connected_in_captured_scene": offline_detached,
            "complete_server_outcome_rules_recovered": False,
            "global_allowed_or_forbidden_spin_set": "UNKNOWN",
        },
        "scope": ("Análisis del código de cliente y de los componentes de escena. "
                  "No se ejecuta JavaScript y no se publica código propietario."),
    }
