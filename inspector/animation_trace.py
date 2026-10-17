"""Trazado estático conservador: respuesta del servidor -> parser -> animación.

No ejecuta código del proveedor ni reproduce el RNG. No publica fragmentos
de JavaScript; solo nombres acotados de métodos/propiedades y booleanos de
evidencia. Los datos se extraen exclusivamente del HAR original, en memoria.
"""
from __future__ import annotations

from collections import Counter
import re

SCHEMA = "inspector/animation-origin-trace/v1"
# Las claves se verifican contra literales del diccionario y los parsers.
# Son candidatos al protocolo común; su presencia no demuestra uso por juego.
FIELDS = {
    "reel_set_current": ("reelSetIndexCurrent", "reel_set", "ReelSetIndexCurrent"),
    "reel_set_next": ("reelSetIndex", "n_reel_set", "ReelSetIndex"),
    "reel_sets_count": ("numberOfReelSets", "reel_set_size", None),
    "replacement_data": ("symbolReplacementData", "srf", "SymbolReplacementData"),
    "tumbling": ("Tumbling", "tmb", "TumblingData"),
    "next_reel_symbols": ("NextReelsSymbolsList", "n_rsl", "NextReelsSymbolsList"),
    "random_mystery_symbol": ("randomMysterySymbol", "msr", "RandomMysterySymbolId"),
}

FUNCTION_RE = re.compile(
    r"(?<![\w$])(?P<qualified>(?:VSProtocolParser|VS_Reel|VS_ReelsManager"
    r"|V4ServerAdapter_Symbols|RequestProvider|OfflineServer)"
    r"(?:\.prototype)?\.[A-Za-z_$][\w$]*)\s*=\s*function\s*"
    r"\([^()]{0,450}\)\s*\{"
)
MAX_METHOD_CHARS = 90_000
MAX_METHODS = 500
LABELS = {
    "server_result_screen": "ResultScreenSymbols",
    "initial_result_screen": "InitialResultScreenSymbols",
    "raw_symbol_list": "this.symbolList",
    "visual_random": "Math.random(",
    "symbol_replacement_method": "ReplaceSymbol(",
    "protocol_dict": "GameProtocolDictionary.",
    "reel_set_index_parser": "GameProtocolDictionary.reelSetIndex",
    "reel_set_current_parser": "GameProtocolDictionary.reelSetIndexCurrent",
    "tumbling_parser": "GameProtocolDictionary.Tumbling",
    "replacement_parser": "GameProtocolDictionary.symbolReplacementData",
}


def _balanced_function(source: str, start: int) -> tuple[str, bool]:
    """Extrae cuerpo de función evitando llaves dentro de cadenas/comentarios.

    No es un parser completo de JavaScript: literales regexp y plantillas
    con interpolación compleja pueden impedir la prueba. Reportar truncamiento,
    nunca tratar el método incompleto como evidencia negativa definitiva.
    """
    depth = 1
    idx = start
    quote = None
    escape = False
    comment = None
    until = min(len(source), start + MAX_METHOD_CHARS)
    while idx < until:
        ch = source[idx]
        nx = source[idx + 1] if idx + 1 < len(source) else ""
        if comment == "line":
            if ch == "\n":
                comment = None
        elif comment == "block":
            if ch == "*" and nx == "/":
                comment = None
                idx += 1
        elif quote is not None:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                quote = None
        elif ch == "/" and nx == "/":
            comment = "line"
            idx += 1
        elif ch == "/" and nx == "*":
            comment = "block"
            idx += 1
        elif ch in ("'", '"', "\x60"):
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[start:idx], True
        idx += 1
    return source[start:until], False


def _methods(source: str) -> list[dict]:
    methods = []
    for match in FUNCTION_RE.finditer(source):
        if len(methods) >= MAX_METHODS:
            break
        body, complete = _balanced_function(source, match.end())
        marks = [name for name, token in LABELS.items() if token in body]
        if not marks and not any(
            token in body for token in ("ReelSetIndex", "TumblingData",
                                        "SymbolReplacementData", "ReelSets",
                                        "GetReelScreenSymbols")
        ):
            continue
        methods.append({
            "name": match.group("qualified"),
            "complete_function_parse": complete,
            "observed_markers": marks,
        })
    return methods


def _field_report(source: str, methods: list[dict], observed: dict[str, list[str]]) -> dict:
    result = {}
    parser_bodies = {}
    # Estas coincidencias exigen el par llave/valor literal, no una semejanza numérica.
    for field, (dictionary_name, wire_name, destination) in FIELDS.items():
        pattern = (r"(?<![\w$])" + re.escape(dictionary_name)
                   + r"\s*:\s*['\"]" + re.escape(wire_name) + r"['\"]")
        declared = bool(re.search(pattern, source))
        parser_uses_key = bool(re.search(
            r"GameProtocolDictionary\." + re.escape(dictionary_name) + r"\b", source))
        destination_assigned = bool(
            destination and re.search(r"\bresult\." + re.escape(destination)
                                      + r"\s*=", source))
        result[field] = {
            "wire_name": wire_name,
            "dictionary_declared_in_client": declared,
            "parser_uses_dictionary_field": parser_uses_key,
            "decoded_to_result_property": destination_assigned,
            "observed_in_captured_init": wire_name in observed.get("doInit", []),
            "observed_in_captured_spin": wire_name in observed.get("doSpin", []),
            "status": (
                "OBSERVED_IN_CAPTURE" if wire_name in observed.get("doInit", [])
                   or wire_name in observed.get("doSpin", [])
                else "CLIENT_KNOWS_FIELD_ONLY" if declared and parser_uses_key
                else "NOT_CONFIRMED"
            ),
        }
    return result


def analyze_animation_origin(build: bytes, scene: dict, observed: dict[str, list[str]] | None = None) -> dict:
    """Analiza exclusivamente el flujo estático del cliente.

    Acepta el informe depurado de escena de client_evidence._scene_components;
    la implementación JavaScript original no sale de este método.
    """
    observed = observed or {"doInit": [], "doSpin": []}
    result = {
        "schema": SCHEMA,
        "build_js_present": bool(build),
        "client_methods_found": 0,
        "parser_and_reel_methods": [],
        "protocol_fields": {},
        "stop_logic": {
            "method_found": False,
            "result_screen_branch_in_method": False,
            "raw_reel_symbols_branch_in_method": False,
            "visual_randomness_in_method": False,
            "blank_symbol_random_replacement_branch": False,
            "scene_stop_on_result_screen_initial": scene.get(
                "reel_stop_uses_response_symbols", "UNKNOWN"),
            "scene_offline_server_attachment": scene.get(
                "offline_server_attachment", "UNKNOWN"),
            "runtime_branch_selection_observed": False,
        },
        "interpretation": "NO_CLIENT_PROOF_OF_PRODUCTION_RNG",
        "server_outcome_rules_known": False,
        "global_possible_or_impossible_screen_classification": "UNKNOWN",
        "limitations": [
            "Los flags de escena son configuración inicial, no una traza dinámica",
            "La existencia de una rama no prueba que haya sido ejecutada",
            "Math.random en animación o simulación no demuestra RNG de producción",
            "Sin giro no se observa qué reel_set/current/next seleccionó el servidor",
        ],
    }
    if not build:
        result["interpretation"] = "BUILD_JS_NOT_CAPTURED"
        return result
    source = build.decode("utf-8", "replace")
    functions = _methods(source)
    result["client_methods_found"] = len(functions)
    result["parser_and_reel_methods"] = functions
    result["protocol_fields"] = _field_report(source, functions, observed)
    method = re.search(
        r"\bVS_Reel\.prototype\.GetNextSymbol\s*=\s*function\s*"
        r"\([^()]{0,450}\)\s*\{", source)
    if method:
        code, complete = _balanced_function(source, method.end())
        result["stop_logic"].update({
            "method_found": True,
            "method_parse_complete": complete,
            "result_screen_branch_in_method": (
                "GetReelScreenSymbols" in code and "Vars.ResultScreenSymbols" in code
                and "stopOnScreenSymbols" in code),
            "raw_reel_symbols_branch_in_method": "this.symbolList" in code,
            "visual_randomness_in_method": "Math.random(" in code,
            "blank_symbol_random_replacement_branch": (
                "Math.random(" in code and "emptySymbolReplacements" in code
                and "replaceEmptySymbol" in code),
        })
    if (result["stop_logic"]["result_screen_branch_in_method"]
            and result["stop_logic"]["raw_reel_symbols_branch_in_method"]):
        result["interpretation"] = "CLIENT_HAS_DISTINCT_RESULT_AND_VISUAL_REEL_PATHS"
    else:
        result["interpretation"] = "CLIENT_RENDERING_ORIGIN_NOT_FULLY_RECONSTRUCTED"
    return result
