"""Extrae reglas publicadas en la ficha oficial: evidencias no matemáticas.

Este módulo NO interpreta el RNG ni sustituye la demostración del protocolo.
Produce sólo una versión normalizada y limitada de la condición publicada, y
registra su procedencia. No copia textos completos del proveedor.
"""
from __future__ import annotations

from html.parser import HTMLParser
import re


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip = 0
        self.fragments = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "noscript", "template"}:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "noscript", "template"}:
            self._skip = max(0, self._skip - 1)

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.fragments.append(data.strip())


NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}


def _num(value: str) -> int | None:
    return int(value) if value.isdigit() else NUMBERS.get(value.lower())


def extract_official_feature_rules(html: str | bytes, *, game_slug: str | None = None) -> dict:
    """Detecta únicamente la regla de money symbols + Collect de Deep Sea Frenzy.

    El extractor es intencionalmente estricto. Si cambia la página o aparecen
    condiciones distintas, devuelve NOT_RECOGNIZED sin completar por heurísticas.
    """
    result = {
        "schema": "inspector/official-feature-rules/v1",
        "status": "NOT_RECOGNIZED",
        "source_type": "PUBLIC_OFFICIAL_GAME_DESCRIPTION",
        "game_slug": game_slug if game_slug and re.fullmatch(r"[a-z0-9-]{1,80}", game_slug) else None,
        "bonus_trigger": None,
        "feature_win": None,
        "extra_spin": None,
        "server_feature_execution_verified": False,
        "complete_feature_rules_proven": False,
        "limitations": [
            "Las condiciones son declaraciones comerciales del proveedor, no código del generador RNG",
            "La ficha puede simplificar o no detallar estados especiales",
            "No se infieren las probabilidades ni se confirma la liquidación de servidor",
        ],
    }
    if isinstance(html, bytes):
        text = html.decode("utf-8", "replace")
    elif isinstance(html, str):
        text = html
    else:
        return result
    if not text or len(text) > 15_000_000:
        return result
    parser = _VisibleText()
    try:
        parser.feed(text)
    except ValueError:
        return result
    plain = re.sub(r"\s+", " ", " ".join(parser.fragments)).lower()
    # Evitar interpretar textos genéricos sobre otros títulos. Debe haber
    # contexto del juego más ambos papeles y umbral en la misma descripción.
    if "deep sea frenzy" not in plain:
        return result
    money = re.search(r"shark money symbols can land on reels? 1\s*[-–]\s*4", plain)
    collect = re.search(r"collect symbols? can (?:hit|land) on reel five", plain)
    trigger = re.search(
        r"when\s+(eight|[0-9]{1,2})\s+or more money symbols"
        r".{0,125}?(?:a|the)\s+collect symbol", plain
    )
    awarded = re.search(
        r"bonus game triggers? with\s+(five|[0-9]{1,2})\s+free spins", plain
    )
    extra = re.search(
        r"\+1 spin collect symbol adds an extra spin", plain
    )
    if not (money and collect and trigger and awarded):
        return result
    required, initial = _num(trigger.group(1)), _num(awarded.group(1))
    if required is None or initial is None or not (1 <= required <= 24 and 1 <= initial <= 50):
        return result
    result["status"] = "PUBLIC_DESCRIPTION_CONDITION_PARSED"
    result["bonus_trigger"] = {
        "minimum_money_symbols": required,
        "money_symbol_reels": [1, 2, 3, 4],
        "requires_collect_symbol": True,
        "collect_symbol_reel": 5,
        "awarded_free_spins": initial,
        "payment_before_bonus": "DECLARED",
        "trigger_proven_in_server": False,
    }
    result["feature_win"] = {
        "money_symbol_values_summed_then_collect_multiplier_applied": (
            bool(re.search(r"their combined value is boosted by any multiplier", plain))),
        "amount_payable_from_arbitrary_screen": "UNKNOWN",
    }
    result["extra_spin"] = {
        "collect_plus_one_can_add_one_spin": bool(extra),
        "exact_state_transitions_known": False,
    }
    return result
