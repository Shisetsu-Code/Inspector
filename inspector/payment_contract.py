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
