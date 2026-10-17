"""Contrato parcial de pagos, derivado de doInit; NO valida premios del backend.

La tabla puede incluir premios desde 2 símbolos, y las condiciones de línea,
wilds/scatters y estados de free spins son independientes. No convertir un
multiplicador en una ganancia confirmada sin la modalidad y el contrato de pago.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re

SCHEMA = "inspector/payment-contract/v1"
SCATTER_RE = re.compile(r"^[0-9,;~#.+-]{1,65536}$")
SYMBOL_RE = re.compile(r"^[A-Za-z0-9]{1,12}$")


def _safe_number(raw: str) -> str | None:
    if not isinstance(raw, str) or not re.fullmatch(r"\d{1,12}(?:\.\d{1,9})?", raw):
        return None
    try:
        number = Decimal(raw)
    except InvalidOperation:
        return None
    if not number.is_finite() or number < 0:
        return None
    return format(number.normalize(), "f")


def extract_scatter_declarations(raw: str | None) -> dict:
    """Lee tabla anunciada, sin inferir desplazamiento de índice ni evento bonus.

    ParseScatters de la librería compartida usa symbol~pays~freespins~multipliers,
    separador ; para símbolos y # para variantes. Invierte los arrays en memoria.
    Sus índices NO prueban automáticamente un umbral de disparo de free spins.
    """
    result = {
        "status": "NOT_DECLARED" if raw is None else "UNRECOGNIZED_FORMAT",
        "variants": [],
        "free_spins_trigger_threshold": None,
        "free_spins_activation_verified": False,
        "meaning_of_array_index": "UNKNOWN",
        "scope": "DECLARED_SCATTER_TABLE_NO_VERIFIED_TRIGGER",
    }
    if not isinstance(raw, str) or not SCATTER_RE.fullmatch(raw):
        return result
    variants = []
    for variant in raw.split("#"):
        entries = []
        for item in variant.split(";"):
            sections = item.split("~")
            if len(sections) != 4:
                return result
            symbol_id, *arrays = sections
            if not symbol_id.isdigit():
                return result
            parsed = []
            for csv in arrays:
                values = csv.split(",")
                if len(values) > 100 or not values or any(not re.fullmatch(r"\d{1,9}", x) for x in values):
                    return result
                parsed.append(list(reversed([int(x) for x in values])))
            entries.append({
                "numeric_symbol_id": int(symbol_id),
                "payout_array_client_order": parsed[0],
                "free_spins_array_client_order": parsed[1],
                "multiplier_array_client_order": parsed[2],
                "array_index_to_screen_count_confirmed": False,
            })
        variants.append(entries)
    result["status"] = "DECLARED_TABLE_PARSED"
    result["variants"] = variants
    return result


def build_payment_contract(paytable: dict, *,
                           scatter_data: str | None = None,
                           line_paths: list | None = None,
                           client_methods: list[str] | None = None) -> dict:
    symbols = {}
    warnings = []
    for symbol, payouts in paytable.items():
        if not isinstance(symbol, str) or not SYMBOL_RE.fullmatch(symbol) or not isinstance(payouts, dict):
            warnings.append("Entrada paytable ignorada por formato inválido")
            continue
        result = {}
        for count_text, amount in payouts.items():
            if not isinstance(count_text, str) or not count_text.isdigit() or not 1 <= int(count_text) <= 20:
                continue
            x = _safe_number(str(amount))
            if x is not None:
                result[str(int(count_text))] = x
        if result:
            counts = sorted(int(x) for x in result)
            symbols[symbol] = {
                "minimum_declared_count": counts[0],
                "payouts_by_count": dict(sorted(result.items(), key=lambda p: int(p[0]))),
            }
    lines = []
    for line in line_paths or []:
        if isinstance(line, list) and 2 <= len(line) <= 12 and all(
                isinstance(v, int) and 0 <= v <= 255 for v in line):
            lines.append(line)
    methods = set(client_methods or [])
    return {
        "schema": SCHEMA,
        "status": "PAYTABLE_PARSED" if symbols else "PAYTABLE_UNAVAILABLE",
        "symbols": symbols,
        "symbols_with_2_count_payout": sorted(
            k for k, v in symbols.items() if "2" in v["payouts_by_count"]),
        "symbols_with_3_count_payout": sorted(
            k for k, v in symbols.items() if "3" in v["payouts_by_count"]),
        "declared_line_paths": lines,
        "payline_geometry_complete": False,
        "symbol_substitution_rules_complete": False,
        "winning_direction_known": False,
        "bet_denominator_known": False,
        "server_win_protocol_parser_methods": {
            name: name in methods
            for name in [
                "VSProtocolParser.ParseWinLines",
                "VSProtocolParser.ParseWinGroups",
                "VSProtocolParser.ParseScatters",
                "VSProtocolParser.ParseVsFreeSpin",
                "VSProtocolParser.ParseVsResponse",
            ]
        },
        "scatter": extract_scatter_declarations(scatter_data),
        "feature_trigger_conditions_complete": False,
        "full_payout_validation_possible": False,
        "server_outcome_validity": "UNKNOWN",
        "limitations": [
            "Paytable describe multiplicadores declarados, no confirma que una pantalla tenga una línea pagada",
            "Dos símbolos pueden pagar para algunos IDs y no para otros",
            "Las posiciones, wilds, scatters, bonos y la modalidad de apuesta pueden modificar el cobro",
            "El cliente puede visualizar premios enviados por servidor sin recalcularlos de manera autoritativa",
            "Un disparo de free spins solo puede certificarse con reglas de activación completas",
        ] + warnings,
    }


def evaluate_symbol_count(contract: dict, symbol: str, count: int) -> dict:
    """Evalúa una fila de paytable, NO cualquier par de símbolos en pantalla."""
    if not isinstance(count, int) or not 0 <= count <= 20:
        raise ValueError("count fuera de rango: 0..20")
    if not isinstance(symbol, str) or not SYMBOL_RE.fullmatch(symbol):
        raise ValueError("símbolo inválido")
    symbols = contract.get("symbols", {})
    entry = symbols.get(symbol)
    key = str(count)
    value = entry["payouts_by_count"].get(key) if entry else None
    return {
        "symbol": symbol,
        "count": count,
        "table_entry_exists": value is not None,
        "declared_multiplier": value,
        "minimum_declared_count": entry["minimum_declared_count"] if entry else None,
        "status": ("TABLE_ENTRY_EXISTS" if value is not None else
                   "NO_TABLE_ENTRY" if entry is not None else "UNKNOWN_SYMBOL"),
        "screen_is_paid": "UNKNOWN",
        "server_payout_validity": "UNKNOWN",
        "free_spins_triggered": "UNKNOWN",
        "scope": "PAYTABLE_ROW_ONLY_REQUIRES_WINNING_CONFIGURATION",
    }


def evaluate_literal_line(contract: dict, symbols: str) -> dict:
    """Ejemplo restringido: mismo símbolo consecutivo desde el inicio.

    No usa wild, scatter, jackpots, derecha->izquierda ni geometría de
    paylines no declarada. Nunca sustituye al balance del servidor.
    """
    if not isinstance(symbols, str) or not re.fullmatch(r"[A-Za-z0-9]{2,12}", symbols):
        raise ValueError("Ingresar 2..12 IDs de símbolos simples")
    first = symbols[0]
    count = 0
    for s in symbols:
        if s != first:
            break
        count += 1
    row = evaluate_symbol_count(contract, first, count)
    row.update({
        "line": symbols, "left_prefix_matching_symbols": count,
        "assumed_direction": "LEFT_TO_RIGHT",
        "wild_substitutions_applied": False,
        "actual_paying_line_confirmed": False,
        "multiplier_is_not_cash_win": True,
        "feature_bonus_status": "UNKNOWN",
    })
    return row



def evaluate_declared_bonus(contract: dict, *,
                            money_symbol_count: int,
                            collect_on_reel_5: bool,
                            collect_plus_one: bool = False) -> dict:
    """Evalúa condiciones declaradas en ficha oficial, sin afirmar cobro server.

    Se reciben cantidades semánticas de money symbols y presencia de Collect en
    la 5ª columna; su correspondencia con IDs de s se desconoce y no se inventa.
    """
    if not isinstance(money_symbol_count, int) or not 0 <= money_symbol_count <= 50:
        raise ValueError("money_symbol_count inválido")
    if not isinstance(collect_on_reel_5, bool) or not isinstance(collect_plus_one, bool):
        raise ValueError("collect_on_reel_5 y collect_plus_one deben ser booleanos")

    declared = contract.get("official_description_feature_rules") or {}
    bonus = declared.get("bonus_trigger")
    extra = declared.get("extra_spin")
    if declared.get("status") != "PUBLIC_DESCRIPTION_CONDITION_PARSED" or not isinstance(bonus, dict):
        return {
            "status": "CONTRACT_UNKNOWN",
            "source": "PUBLIC_OFFICIAL_GAME_DESCRIPTION",
            "bonus_trigger_declared_match": None,
            "predicted_initial_free_spins": None,
            "server_feature_activation_verified": False,
            "server_outcome_validity": "UNKNOWN",
        }
    threshold = bonus.get("minimum_money_symbols")
    reel = bonus.get("collect_symbol_reel")
    if not isinstance(threshold, int) or reel != 5:
        return {
            "status": "CONTRACT_UNKNOWN",
            "source": "PUBLIC_OFFICIAL_GAME_DESCRIPTION",
            "bonus_trigger_declared_match": None,
            "predicted_initial_free_spins": None,
            "server_feature_activation_verified": False,
            "server_outcome_validity": "UNKNOWN",
        }
    meets_rule = money_symbol_count >= threshold and collect_on_reel_5
    extra_spin = (
        meets_rule and collect_plus_one and
        bool((extra or {}).get("collect_plus_one_can_add_one_spin")))
    return {
        "status": "DECLARED_RULE_MATCH" if meets_rule else "DECLARED_RULE_NOT_MET",
        "money_symbols": money_symbol_count,
        "required_money_symbols": threshold,
        "collect_on_reel_5": collect_on_reel_5,
        "collect_plus_one": collect_plus_one,
        "bonus_trigger_declared_match": meets_rule,
        "predicted_initial_free_spins": (
            bonus["awarded_free_spins"] + int(extra_spin) if meets_rule else 0),
        "cash_payout_from_symbols": "UNKNOWN_WITHOUT_VALUES_AND_MULTIPLIER",
        "source": "PUBLIC_OFFICIAL_GAME_DESCRIPTION",
        "server_feature_activation_verified": False,
        "server_outcome_validity": "UNKNOWN",
        "assumptions": [
            "Los conteos representan MONEY SYMBOLS, no cualquier símbolo coincidente",
            "Collect está presente en el carrete cinco",
            "La descripción pública está completa para esta condición",
        ],
    }
