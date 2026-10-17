"""Evaluador conservador de líneas explícitas, no del RNG comercial.

El cliente debe declarar TODOS los índices de las líneas y sus direcciones,
los cuales deben mapear un símbolo por carrete en row/column major.
Sin ello no se inventan paylines, multiplicadores en moneda ni WILDs.
"""
from __future__ import annotations

from decimal import Decimal
import re

SCHEMA = "inspector/explicit-lines/v1"


def _grid_format(paths: list[list[int]], width: int, height: int) -> str:
    row_major = all([i % width for i in line] == list(range(width)) for line in paths)
    col_major = all([i // height for i in line] == list(range(width)) for line in paths)
    if row_major and not col_major:
        return "ROW_MAJOR"
    if col_major and not row_major:
        return "COLUMN_MAJOR"
    if row_major and col_major:
        return "AMBIGUOUS"
    return "UNRECOGNIZED"


def extract_line_contract(scene: dict, width: int, height: int) -> dict:
    """Evalúa contratos de líneas del componente VS_LinesDefinitions."""
    contract = {
        "schema": SCHEMA,
        "status": "NOT_AVAILABLE",
        "geometry": {"width": width, "height": height},
        "source": "SCENE_VS_LinesDefinitions",
        "declared_line_count": None,
        "extracted_paths": [],
        "reading_order": None,
        "direction_complete": False,
        "geometry_complete": False,
        "wild_semantics_complete": False,
        "line_wager_unit_known": False,
        "cash_payout_validation_possible": False,
        "notes": ["Las líneas descritas en escena no prueban qué resultados permite el servidor"],
    }
    if not (isinstance(width, int) and isinstance(height, int)
            and 1 <= width <= 12 and 1 <= height <= 12):
        contract["status"] = "INVALID_GEOMETRY"
        return contract
    components = scene.get("line_component_structure") or []
    paths = scene.get("line_paths_declarative") or []
    directions = scene.get("line_paths_directions") or []
    if len(components) != 1:
        contract["status"] = ("MULTIPLE_COMPONENTS" if components else "NOT_AVAILABLE")
        return contract
    comp = components[0]
    count = comp.get("declared_line_count")
    contract["declared_line_count"] = count
    contract["declared_reel_count"] = comp.get("declared_reel_count")
    contract["scene_entries"] = comp.get("xt_enabled_entries")
    contract["symbol_reference_count"] = comp.get("symbol_refs_count")
    contract["scene_schema_fields"] = comp.get("scene_field_names") or []
    contract["nested_entry_fields"] = comp.get("xt_first_serialized_field_names") or []
    if not paths:
        contract["status"] = ("LINE_COUNT_ONLY" if isinstance(count, int) and count > 0
                              else "NO_EXPLICIT_LINE_PATHS")
        return contract
    if not isinstance(count, int) or count < 1 or count > 500 or count != len(paths):
        contract["status"] = "COUNT_PATHS_MISMATCH"
        return contract
    if len(directions) != len(paths) or any(type(d) is not bool for d in directions):
        contract["status"] = "UNKNOWN_LINE_DIRECTION"
        return contract
    if any(not isinstance(path, list) or len(path) != width or any(
           type(v) is not int or v < 0 or v >= width*height for v in path)
           or len(set(path)) != width for path in paths):
        contract["status"] = "INVALID_PATH_INDICES"
        return contract
    order = _grid_format(paths, width, height)
    contract["reading_order"] = order
    if order in ("AMBIGUOUS", "UNRECOGNIZED"):
        contract["status"] = "UNCONFIRMED_INDEX_MAPPING"
        return contract
    if comp.get("symbol_refs_count") is not None and comp["symbol_refs_count"] != width * height:
        contract["status"] = "SCENE_SYMBOL_GRID_MISMATCH"
        return contract
    contract["extracted_paths"] = [
        {"line_number_1based": i + 1, "symbol_indices": path,
         "direction": "RIGHT_TO_LEFT" if right else "LEFT_TO_RIGHT"}
        for i, (path, right) in enumerate(zip(paths, directions))
    ]
    contract["status"] = "EXPLICIT_LINE_GEOMETRY_CONFIRMED"
    contract["direction_complete"] = True
    contract["geometry_complete"] = True
    return contract


def evaluate_literal_screen(screen: str, line_contract: dict, paytable_contract: dict) -> dict:
    """Calcular únicamente coincidencias literales; nunca inferir pagos del servidor."""
    geom = line_contract.get("geometry") or {}
    width, height = geom.get("width"), geom.get("height")
    if not isinstance(screen, str) or not re.fullmatch(r"[A-Za-z0-9]{1,144}", screen):
        raise ValueError("Pantalla inválida: IDs simples alfanuméricos")
    if not isinstance(width, int) or not isinstance(height, int) or len(screen) != width*height:
        raise ValueError("La pantalla no coincide con la geometría")
    result = {
        "schema": "inspector/literal-line-screen-evaluation/v1",
        "source": "EXPLICIT_CLIENT_SCENE_PATHS_AND_DOINIT_PAYTABLE",
        "screen": screen,
        "geometry_status": line_contract.get("status"),
        "server_win_validity": "UNKNOWN",
        "total_cash_win": None,
        "literal_paytable_units_total": None,
        "line_results": [],
        "unresolved_lines": [],
        "scope": "ONLY_EXACT_MATCHES_NO_WILD_NO_MONEY_COLLECT_NO_MULTIPLIERS",
    }
    if line_contract.get("status") != "EXPLICIT_LINE_GEOMETRY_CONFIRMED":
        result["evaluation_status"] = "NOT_EVALUABLE_WITHOUT_EXPLICIT_LINES"
        return result
    if paytable_contract.get("status") != "PAYTABLE_PARSED":
        result["evaluation_status"] = "NOT_EVALUABLE_WITHOUT_PAYTABLE"
        return result
    payout_sum = Decimal(0)
    unknown = []
    for line in line_contract["extracted_paths"]:
        path = line["symbol_indices"]
        chars = [screen[i] for i in path]
        reverse = line["direction"] == "RIGHT_TO_LEFT"
        traversal = chars[::-1] if reverse else chars
        symbol = traversal[0]
        length = 0
        for ch in traversal:
            if ch != symbol:
                break
            length += 1
        row = paytable_contract.get("symbols", {}).get(symbol)
        if row is None:
            unknown.append({
                "line_number_1based": line["line_number_1based"],
                "reason": "UNIDENTIFIED_OR_SPECIAL_SYMBOL",
                "prefix_symbol": symbol, "symbols": "".join(chars),
            })
            continue
        pay = row["payouts_by_count"].get(str(length))
        payout = Decimal(pay) if pay is not None else Decimal(0)
        payout_sum += payout
        result["line_results"].append({
            "line_number_1based": line["line_number_1based"],
            "symbols": "".join(chars),
            "direction": line["direction"],
            "literal_prefix_symbol": symbol,
            "literal_prefix_length": length,
            "paytable_entry": pay,
            "contribution_in_table_units": str(payout),
            "win_confirmed_by_server": False,
            "wild_substitutions_applied": False,
        })
    result["unresolved_lines"] = unknown
    result["literal_paytable_units_total"] = str(payout_sum)
    result["evaluation_status"] = (
        "PARTIAL_SPECIAL_SYMBOL_UNRESOLVED" if unknown else
        "LITERAL_LINES_EVALUATED_NONAUTHORITATIVE")
    return result
