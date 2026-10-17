"""Rastreo estático de protocolos de premios hacia resaltado de pantalla.

No ejecuta JavaScript de terceros, no simula RNG ni publica fragmentos del
bundle. Los métodos comunes podrían estar compilados sin activarse en este juego.
"""
from __future__ import annotations

import re
from .animation_trace import _balanced_function

METHODS = {
    "classic_win_lines": ("VSProtocolParser.ParseWinLines", [
        "GameProtocolDictionary.winLines", "LineNumber", "WinAmount", "WinPositions"]),
    "ways_groups": ("VSProtocolParser.ParseWinGroups", [
        "GameProtocolDictionary.winWayGroups", "WinAmount", "WinPositions",
        "waysCount", "waysLength", "payingDirection"]),
    "paytable": ("VSProtocolParser.ParsePaytable", [
        "GameProtocolDictionary.paytable", "ClassicPaytable"]),
    "show_line": ("WinLineVisual.prototype.OnWinLineShow", [
        "Vars.ReceivedWinLines", "WinPositions", "symbolSquares", "SetActive"]),
    "hide_line": ("WinLineVisual.prototype.OnWinLineHide", [
        "Vars.ReceivedWinLines", "WinPositions", "symbolSquares", "SetActive"]),
    "scene_lines": ("VS_LinesDefinitions.prototype.XTInitVariablesAndEvents", [
        "Vars.LinesDefinitionsObject"]),
}

def _extract(source: str, name: str):
    pattern = re.compile(re.escape(name) + r"\s*=\s*function\s*\([^()]{0,450}\)\s*\{")
    match = pattern.search(source)
    if not match:
        return None, False
    return _balanced_function(source, match.end())


def inspect_win_delivery(build: bytes | None) -> dict:
    result = {
        "schema": "inspector/win-delivery-trace/v1",
        "build_js_captured": bool(build),
        "method_evidence": {},
        "server_may_send_winning_amount_and_positions": False,
        "client_can_visualize_received_win_positions": False,
        "local_payline_calculation_proven": False,
        "money_won_validation_proven": False,
        "active_protocol_family_observed": "NO_SPIN_CAPTURED",
        "payline_geometries_complete": False,
        "server_rng_rules_known": False,
        "limitations": [
            "Un método compilado puede estar inactivo en la modalidad actual",
            "El cliente puede resaltar premios comunicados por el backend sin verificarlos",
            "La existencia de un protocolo no determina todas las combinaciones posibles",
            "Solo doInit no permite observar WinAmount, WinPositions ni WinGroups reales",
        ],
        "source_excerpt_published": False,
    }
    if not build:
        return result
    source = build.decode("utf-8","replace")
    for key,(method,marks) in METHODS.items():
        body, complete = _extract(source,method)
        flags = {token: bool(body is not None and token in body) for token in marks}
        result["method_evidence"][key] = {
            "method": method,
            "found": body is not None,
            "parse_complete": complete,
            "expected_fields_found": flags,
            "all_expected_fields_found": bool(complete and all(flags.values())),
        }
    classic=result["method_evidence"]["classic_win_lines"]["all_expected_fields_found"]
    ways=result["method_evidence"]["ways_groups"]["all_expected_fields_found"]
    highlighter=result["method_evidence"]["show_line"]["all_expected_fields_found"]
    result["server_may_send_winning_amount_and_positions"] = bool(classic or ways)
    result["client_can_visualize_received_win_positions"] = bool(highlighter)
    result["payout_source_status"] = (
        "PARSER_ACCEPTS_SERVER_AWARDS_AND_DISPLAY_CAN_HIGHLIGHT"
        if (classic or ways) and highlighter else
        "INCOMPLETE_STATIC_EVIDENCE"
    )
    return result
