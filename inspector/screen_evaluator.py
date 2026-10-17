"""Cálculo hipotético de símbolos literales por línea declarada en escena.

No procesa Wild, sustituciones, estados de bonus ni apuestas activas; no puede
aprobar cobros comerciales ni afirmar que una pantalla sea permitida por RNG.
"""
from __future__ import annotations

from .line_stake_evidence import line_hypothetical

SPECIAL = frozenset("WSTUVXY")
MAX_TESTED_LINES = 400


def evaluate_screen_literals(screen: str, payment: dict, evidence: dict,
                             width: int, height: int) -> dict:
    if not isinstance(screen, str) or not (1 <= width <= 12 and 1 <= height <= 12):
        raise ValueError("Pantalla/geometría no válidas")
    if len(screen) != width * height or not screen.isalnum():
        raise ValueError("Pantalla: se requieren exactamente ancho × alto símbolos alfanuméricos")
    line_scene = evidence.get("paylines") or {}
    paths = line_scene.get("lines_recovered") or []
    result = {
        "schema": "inspector/literal-screen-evaluation/v1",
        "status": "NO_DECLARED_LINE_PATHS" if not paths else "SCENE_LINE_CANDIDATES",
        "screen_length": len(screen),
        "line_path_coverage": line_scene.get("line_path_coverage", "NOT_AVAILABLE"),
        "active_line_set_verified": False,
        "wild_substitution_applied": False,
        "bonus_state_known": False,
        "server_outcome_validity": "UNKNOWN",
        "cash_amount": "UNKNOWN",
        "matches": [],
        "conditional_payout_candidates": 0,
        "note": (
            "Cada coeficiente es una entrada de paytable sobre una línea de escena, "
            "no un pago final. Sin líneas activas, Wild y factor monetario, "
            "el resultado real sigue siendo desconocido."
        ),
    }
    paytable = payment.get("symbols") or {}
    raw = {
        k: v.get("payouts_by_count") or {}
        for k, v in paytable.items() if isinstance(v, dict)
    }
    for idx, row in enumerate(paths[:MAX_TESTED_LINES]):
        if not isinstance(row, dict):
            continue
        path = row.get("positions_row_major")
        direction = row.get("direction")
        if not isinstance(path, list) or direction not in ("LEFT_TO_RIGHT", "RIGHT_TO_LEFT"):
            continue
        # No afirmar pagos por símbolos especiales cuyo papel no está demostrado.
        line = "".join(screen[i] for i in path) if (
            len(path) == width and all(isinstance(i, int) and not isinstance(i, bool)
                                       and 0 <= i < len(screen) for i in path)) else ""
        if len(line) != width:
            continue
        candidate = line_hypothetical(
            screen, path, raw, width=width, height=height, direction=direction)
        specials = sorted(set(line).intersection(SPECIAL))
        if specials:
            candidate["status"] = "SPECIAL_SYMBOL_SEMANTICS_UNKNOWN"
            candidate["declared_paytable_entry"] = None
        elif candidate["declared_paytable_entry"] is not None:
            candidate["status"] = "LITERAL_PREFIX_HAS_PAYTABLE_ENTRY"
            result["conditional_payout_candidates"] += 1
        else:
            candidate["status"] = "NO_LITERAL_PREFIX_PAYTABLE_ENTRY"
        result["matches"].append({
            "scene_line_index": idx,
            "row_major_positions": path,
            "direction": direction,
            "line_symbols": line,
            "literal_prefix_count": candidate["literal_prefix_count"],
            "paytable_multiplier_if_conditions_met": candidate["declared_paytable_entry"],
            "status": candidate["status"],
            "cash_prize": "UNKNOWN",
        })
    return result
