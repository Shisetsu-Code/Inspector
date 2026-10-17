"""Evidencia de paylines, roles de símbolos y escala monetaria.

Analiza fragmentos de escena y doInit. Solo exporta metadatos permitidos:
nunca ejecuta JS ni infiere que el cliente decida premios.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re

from .client_evidence import _resource_map, MAX_SCENE

SCHEMA = "inspector/line-stake-evidence/v1"
NUMERIC = re.compile(r"^\d+(?:\.\d+)?$")
MONEY = re.compile(r"^\d{1,3}(?:,\d{3})*(?:\.\d+)?$|^\d+(?:\.\d+)?$")
SYMBOL = re.compile(r"^[A-Za-z0-9]{1,12}$")
MAX_LINES = 400
MAX_COMPONENTS = 200000
MAX_VECTOR = 16


def _dec(s: str | None, *, thousands: bool = False) -> Decimal | None:
    if not isinstance(s, str) or len(s) > 40:
        return None
    if not (MONEY if thousands else NUMERIC).fullmatch(s):
        return None
    try:
        value = Decimal(s.replace(",", "") if thousands else s)
    except InvalidOperation:
        return None
    return value if value.is_finite() and value >= 0 else None


def _number_text(x: Decimal | None) -> str | None:
    return format(x, "f") if x is not None else None


def inspect_stake_declarations(init: dict) -> dict:
    """Campos anunciados: sc, bls y límites. c*l es hipótesis, no contrato.

    Igualdad con el mínimo anunciado = pista de compatibilidad, nunca prueba
    de coste base ni de función, ni de uso de todos los elementos de bls.
    """
    scales = []
    for s in str(init.get("sc", "")).split(",")[:256]:
        d = _dec(s)
        if d is not None:
            scales.append(d)
    levels = []
    for s in str(init.get("bls", "")).split(",")[:256]:
        if s.isdigit() and 0 < int(s) <= 100000:
            levels.append(int(s))
    minimum = _dec(init.get("total_bet_min"), thousands=True)
    maximum = _dec(init.get("total_bet_max"), thousands=True)
    current_coin = _dec(init.get("c"))
    current_line = int(init["l"]) if str(init.get("l", "")).isdigit() and int(init["l"]) <= 100000 else None
    hypothetical = [v * n for v in scales for n in levels]
    low = min(hypothetical) if hypothetical else None
    high = max(hypothetical) if hypothetical else None
    return {
        "status": "INIT_DECLARATIONS_PARSED" if scales and levels else "PARTIAL_DECLARATIONS",
        "source": "doInit",
        "sc_values": [_number_text(x) for x in scales],
        "bls_values": levels,
        "sc_count": len(scales),
        "bls_count": len(levels),
        "total_bet_min_declared": _number_text(minimum),
        "total_bet_max_declared": _number_text(maximum),
        "current_c_declared": _number_text(current_coin),
        "current_l_declared": current_line,
        "hypothetical_sc_times_bls": {
            "formula": "sc × bls",
            "minimum": _number_text(low),
            "maximum": _number_text(high),
            "minimum_matches_advertised": low == minimum if low is not None and minimum is not None else None,
            "maximum_matches_advertised": high == maximum if high is not None and maximum is not None else None,
            "formula_proven_as_real_stake": False,
        },
        "payment_unit": "UNKNOWN",
        "actual_stake_for_arbitrary_screen": "UNKNOWN",
        "payout_cash_scaling_proven": False,
        "notes": [
            "sc y bls son campos del servidor, no se presume que bls represente líneas activas",
            "Un mínimo de producto coincidente no demuestra fórmula de liquidación",
            "El límite máximo puede incluir otros modos; no se atribuye su causa sin evidencia",
        ],
    }


def _shape(x) -> dict:
    """Diagnóstico acotado, sin publicar valores de atributos arbitrarios."""
    if x is None:
        return {"type": "null"}
    if isinstance(x, bool):
        return {"type": "bool"}
    if isinstance(x, int):
        return {"type": "int", "value": x if abs(x) < 100_000 else None}
    if isinstance(x, float):
        return {"type": "float"}
    if isinstance(x, list):
        types = sorted({type(v).__name__ for v in x[:50]})
        nested = sorted({v.get("nestedFieldType") for v in x[:50] if isinstance(v, dict)
                         and isinstance(v.get("nestedFieldType"), str)})
        return {"type": "list", "length": len(x), "item_types": types,
                "nested_types": [t[:50] for t in nested][:12]}
    if isinstance(x, dict):
        return {"type": "object", "keys": sorted(
            k for k in x if isinstance(k, str) and len(k) < 45)[:25]}
    return {"type": "string" if isinstance(x, str) else type(x).__name__}


def _iter_nodes(x, *, depth=0):
    if depth > 6:
        return
    if isinstance(x, dict):
        if x.get("nestedFieldType") == "LineInfo":
            yield x.get("serializableData") or {}
        for v in list(x.values())[:300]:
            yield from _iter_nodes(v, depth=depth+1)
    elif isinstance(x, list):
        for v in x[:MAX_LINES]:
            yield from _iter_nodes(v, depth=depth+1)


def _valid_path(line: dict, width: int, height: int):
    indices = line.get("symbolIndices")
    if not isinstance(indices, list) or len(indices) != width or len(indices) > MAX_VECTOR:
        return None
    if any(isinstance(i, bool) or not isinstance(i, int)
           or not 0 <= i < width * height for i in indices):
        return None
    # Las posiciones se indexan por filas en el cliente compartido. Con esta
    # convención debe existir exactamente un símbolo por columna en la ruta.
    if any(i % width != column for column, i in enumerate(indices)):
        return None
    direction = line.get("isRightToLeft")
    return {"positions_row_major": indices,
            "direction": ("RIGHT_TO_LEFT" if direction is True
                          else "LEFT_TO_RIGHT" if direction is False else "UNKNOWN"),
            "index_origin": "SCENE_LineInfo.symbolIndices",
            "server_payline_used_for_current_bet": "UNKNOWN"}


def inspect_line_scene(har_path: str | Path, game_symbol: str | None,
                       width: int, height: int) -> dict:
    """Busca LineInfo completos, componentes de símbolos y evidencias de Wild."""
    _, fragments, note = _resource_map(har_path, game_symbol)
    out = {
        "status": "NOT_AVAILABLE",
        "scene_chunks": sorted(fragments),
        "vs_lines_definitions_count": 0,
        "declared_line_counts": [],
        "line_component_shapes": [],
        "lines_recovered": [],
        "line_path_coverage": "NOT_AVAILABLE",
        "complete_all_active_paylines_known": False,
        "complete_declared_scene_paths_recovered": False,
        "line_direction_known_for_all": False,
        "active_line_count_selected_in_session": "UNKNOWN",
        "wild_substitution_semantics": "UNKNOWN",
        "wild_candidates_from_scene_names": [],
        "wild_substitution_rules_complete": False,
        "symbol_components_observed": 0,
        "symbol_graphic_ids": [],
        "status_of_graphic_ids_as_math_symbols": "UNVERIFIED",
        "notes": [],
    }
    if not fragments:
        return out
    keys = sorted(fragments)
    if keys != list(range(keys[-1] + 1)):
        out["status"] = "INCOMPLETE_SCENE"
        return out
    blob = b"".join(fragments[i] for i in keys)
    if len(blob) > MAX_SCENE:
        out["status"] = "SCENE_TOO_LARGE"
        return out
    try:
        scene = json.loads(blob)
    except (ValueError, UnicodeDecodeError):
        out["status"] = "SCENE_NOT_PARSEABLE"
        return out
    roots = scene.get("resources")
    if not isinstance(roots, list):
        out["status"] = "SCENE_NOT_PARSEABLE"
        return out
    if not 1 <= width <= 12 or not 1 <= height <= 12:
        out["status"] = "UNKNOWN_GEOMETRY"
        return out
    out["status"] = "PARSED"
    refs, names, scanned = set(), set(), 0
    for asset in roots:
        if not isinstance(asset, dict) or asset.get("type") != "GameObject":
            continue
        game_roots = (asset.get("data") or {}).get("root") or []
        if not isinstance(game_roots, list):
            continue
        for obj in game_roots:
            if not isinstance(obj, dict):
                continue
            for comp in (obj.get("components") or []):
                if not isinstance(comp, dict):
                    continue
                scanned += 1
                if scanned > MAX_COMPONENTS:
                    out["notes"].append("Límite de componentes alcanzado")
                    break
                typ = comp.get("componentType")
                d = comp.get("serializableData")
                if not isinstance(d, dict):
                    d = {}
                if typ == "VS_LinesDefinitions":
                    out["vs_lines_definitions_count"] += 1
                    if isinstance(d.get("lines"), int) and not isinstance(d.get("lines"), bool):
                        out["declared_line_counts"].append(d["lines"])
                    out["line_component_shapes"].append({
                        key: _shape(value)
                        for key, value in sorted(d.items())
                        if key in {"lines","reels","symbolSquares","symbols","xtEnabled","patterns","lineDefinitions"}
                    })
                    for possible in _iter_nodes(d):
                        path = _valid_path(possible, width, height)
                        if path is not None:
                            key = tuple(path["positions_row_major"])
                            if key not in refs:
                                refs.add(key)
                                out["lines_recovered"].append(path)
                elif typ == "VS_Symbol":
                    out["symbol_components_observed"] += 1
                    symid = d.get("symbolId")
                    if isinstance(symid, int) and not isinstance(symid, bool) and 0 <= symid < 1000:
                        names.add(symid)
                    objname = obj.get("name", "")
                    if (isinstance(objname, str) and re.search("wild", objname, re.I)
                            and re.fullmatch(r"[A-Za-z0-9_-]{1,32}",objname)):
                        out["wild_candidates_from_scene_names"].append(objname)
            if scanned > MAX_COMPONENTS:
                break
        if scanned > MAX_COMPONENTS:
            break
    out["symbol_graphic_ids"] = sorted(names)[:100]
    out["wild_candidates_from_scene_names"] = sorted(
        set(out["wild_candidates_from_scene_names"]))[:30]
    counts = out["declared_line_counts"]
    rows = out["lines_recovered"]
    if rows and counts and all(v == len(rows) for v in counts):
        out["line_path_coverage"] = "MATCHES_DECLARED_SCENE_LINE_COUNT"
        out["complete_declared_scene_paths_recovered"] = all(
            line["direction"] != "UNKNOWN" for line in rows)
        # La escena no prueba que estas líneas estuvieran habilitadas en una
        # apuesta concreta; esa evidencia requiere el estado de sesión.
    elif rows:
        out["line_path_coverage"] = "PARTIAL_OR_CONFLICTING_LINE_COUNT"
    elif counts:
        out["line_path_coverage"] = "COUNT_ONLY_NO_PATHS"
    else:
        out["line_path_coverage"] = "NOT_DECLARED"
    out["line_direction_known_for_all"] = bool(rows) and all(
        line["direction"] != "UNKNOWN" for line in rows)
    out["notes"].append(
        "Líneas declaradas en escena no acreditan qué líneas/modalidades estaban habilitadas por servidor")
    out["notes"].append(
        "Un nombre o ID gráfico Wild no demuestra qué símbolos sustituye ni multiplicadores")
    return out


def inspect_wild_alphabets(reel_sets: dict) -> dict:
    """Solo posición de 'W' en tiras. No implica Wild efectivo."""
    data = {}
    for set_id, reels in reel_sets.items():
        data[str(set_id)] = [
            i + 1 for i, strip in enumerate(reels)
            if "W" in strip.get("alphabet", []) or "W" in strip.get("sequence","")
        ]
    return {
        "symbol_identifier": "W",
        "source": "doInit.reel_setN",
        "reels_containing_W_directly_by_set": data,
        "meaning_as_substitute_for_other_symbols": "UNKNOWN",
        "wild_multiplier": "UNKNOWN",
        "valid_on_all_modes": "UNKNOWN",
        "notes": "W es un identificador literal en las tiras, no demostración de semántica Wild",
    }


def line_hypothetical(screen: str, path: list[int], paytable: dict,
                      *, width: int, height: int, direction: str = "LEFT_TO_RIGHT") -> dict:
    """Evalúa coincidencias literales por posiciones explícitas, sin Wild.

    Útil solo si la línea es parte del contrato demostrado. No calcula moneda.
    """
    if not isinstance(screen, str) or len(screen) != width * height or not 1 <= width <= 12:
        raise ValueError("Pantalla incompatible con geometría declarada")
    if not isinstance(path, list) or len(path) != width or any(
            isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < len(screen)
            for i in path):
        raise ValueError("Ruta inválida")
    if direction not in ("LEFT_TO_RIGHT", "RIGHT_TO_LEFT"):
        raise ValueError("Dirección no demostrada")
    selected = [screen[i] for i in path]
    if direction == "RIGHT_TO_LEFT":
        selected = list(reversed(selected))
    base = selected[0]
    count = 0
    for sym in selected:
        if sym != base:
            break
        count += 1
    payout = (paytable.get(base) or {}).get(str(count))
    return {
        "row_major_path": path,
        "evaluated_symbols_in_direction": "".join(selected),
        "literal_prefix_count": count,
        "declared_paytable_entry": payout,
        "symbol": base,
        "wild_and_feature_processing": "NOT_APPLIED",
        "actual_payout_in_money": "UNKNOWN",
        "server_award_validity": "UNKNOWN",
        "scope": "HYPOTHETICAL_PAYLINE_LITERAL_ONLY",
    }
