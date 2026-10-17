"""Modelo exacto de paradas directas, NO de la matemática RNG del servidor.

Cada carrete produce una ventana circular literal de longitud igual a la altura.
Los carretes se consideran independientes y se selecciona UN reel_set completo.
La unión entre sets se calcula por inclusión-exclusión, sin enumerar pantallas.
"""
from __future__ import annotations

from collections import Counter
from itertools import combinations
from math import prod

from .core import circular_windows

MAX_EXACT_SETS = 12


def _windows(record: dict, height: int) -> set[str]:
    known = (record.get("direct_circular_windows") or {}).get(str(height))
    if isinstance(known, list):
        return set(known)
    return set(circular_windows(record.get("sequence", ""), height))


def _mult_histograms(histograms: list[Counter]) -> Counter:
    result = Counter({0: 1})
    for counts in histograms:
        next_result = Counter()
        for previous, total in result.items():
            for n, amount in counts.items():
                next_result[previous + n] += total * amount
        result = next_result
    return result


def _histogram_for_sets(windows_per_reel: list[set[str]], symbol: str) -> Counter:
    counts = [Counter(w.count(symbol) for w in windows) for windows in windows_per_reel]
    return _mult_histograms(counts)


def compute_direct_model(sets: dict, width: int, height: int, *, special_symbol: str = "S") -> dict:
    """Cuenta pantallas distintas, no paradas ponderadas por repetición.

    Si la entrada tiene demasiados conjuntos, se calculan cotas sin afirmar
    que la unión esté completa.
    """
    result = {
        "schema": "inspector/direct-model/v1",
        "scope": "DIRECT_CIRCULAR_RAW_STOPS_INDEPENDENT_REELS_NO_TRANSFORMATIONS",
        "server_outcome_validity": "UNKNOWN",
        "assumptions": [
            "Cada columna contiene una ventana circular literal de altura sh",
            "Las paradas entre carretes se combinan independientemente",
            "Cada pantalla pertenece a un reel_set completo (no mezclado)",
            "No se aplican modificaciones, cascadas ni sustituciones de símbolos",
            "No se deduce ni se aproxima ninguna probabilidad",
        ],
        "geometry": {"width": width, "height": height},
        "sets": {},
        "union_unique_screen_count": None,
        "sum_of_set_screen_counts": 0,
        "duplicated_across_sets": None,
        "special_symbol": special_symbol,
        "special_symbol_count_histogram": None,
        "global_math_completeness": False,
        "global_forbidden_screens_proven": [],
        "valid_model": False,
        "notes": [],
    }
    if not 1 <= width <= 12 or not 1 <= height <= 12 or not sets:
        result["notes"].append("Sin geometría o conjuntos válidos")
        return result

    group_windows = {}
    for set_id, strips in sets.items():
        if not isinstance(strips, list) or len(strips) != width:
            result["notes"].append("Conjunto {}: geometría inconsistente".format(set_id))
            continue
        candidate = [_windows(strip, height) for strip in strips]
        if any(not options for options in candidate):
            result["notes"].append("Conjunto {}: faltan ventanas".format(set_id))
            continue
        per_reel = [len(options) for options in candidate]
        screen_count = prod(per_reel)
        group_windows[str(set_id)] = candidate
        result["sets"][str(set_id)] = {
            "unique_windows_per_reel": per_reel,
            "unique_screen_count": screen_count,
            "alphabet_per_reel": ["".join(sorted(set("".join(ws)))) for ws in candidate],
            "special_symbol_max_per_reel": [max(w.count(special_symbol) for w in ws)
                                              for ws in candidate],
        }

    if not group_windows:
        result["notes"].append("Ningún conjunto utilizable")
        return result
    result["valid_model"] = True
    result["sum_of_set_screen_counts"] = sum(
        row["unique_screen_count"] for row in result["sets"].values())
    ids = list(group_windows)
    result["set_count_in_model"] = len(ids)
    if len(ids) > MAX_EXACT_SETS:
        result["notes"].append(
            "Más de {} conjuntos: se publican solo cotas para evitar explosión combinatoria".format(MAX_EXACT_SETS))
        result["union_bounds"] = {
            "minimum": max(row["unique_screen_count"] for row in result["sets"].values()),
            "maximum": result["sum_of_set_screen_counts"],
        }
        return result

    total = 0
    symbol_hist = Counter()
    for n in range(1, len(ids) + 1):
        sign = 1 if n % 2 else -1
        for chosen in combinations(ids, n):
            common_windows = [
                set.intersection(*(group_windows[set_id][reel] for set_id in chosen))
                for reel in range(width)
            ]
            if any(not ws for ws in common_windows):
                continue
            screen_count = prod(len(ws) for ws in common_windows)
            total += sign * screen_count
            for k, count in _histogram_for_sets(common_windows, special_symbol).items():
                symbol_hist[k] += sign * count

    result["union_unique_screen_count"] = total
    result["duplicated_across_sets"] = result["sum_of_set_screen_counts"] - total
    result["special_symbol_count_histogram"] = {
        str(k): v for k, v in sorted(symbol_hist.items()) if v
    }
    if sum(symbol_hist.values()) != total or any(v < 0 for v in symbol_hist.values()):
        raise AssertionError("Histograma inconsistente con unión exacta")
    return result


def check_screen(sets: dict, width: int, height: int, screen: str) -> dict:
    """Comprueba ambas orientaciones; nunca afirma 'prohibido por servidor'."""
    if not 1 <= width <= 12 or not 1 <= height <= 12:
        raise ValueError("Geometría inexistente o inválida")
    if len(screen) != width * height:
        raise ValueError("La pantalla debe contener {} símbolos".format(width * height))

    matches = []
    closest = []
    for set_id, strips in sets.items():
        if len(strips) != width:
            continue
        possibilities = [_windows(rec, height) for rec in strips]
        for orientation in ("row_major", "column_major"):
            cols = [
                "".join(screen[row * width + col] for row in range(height))
                if orientation == "row_major" else screen[col*height:(col+1)*height]
                for col in range(width)
            ]
            comparison = [column in options for column, options in zip(cols, possibilities)]
            entry = {
                "reel_set": str(set_id),
                "orientation": orientation,
                "matching_reels": sum(comparison),
                "total_reels": width,
                "columns": cols,
                "per_reel_match": comparison,
            }
            closest.append(entry)
            if all(comparison):
                matches.append(entry)
    closest.sort(key=lambda x: x["matching_reels"], reverse=True)
    return {
        "screen": screen, "geometry": {"width": width, "height": height},
        "direct_model_compatible": bool(matches),
        "direct_model_status": "MATCH" if matches else "NOT_IN_DIRECT_MODEL",
        "server_outcome_validity": "UNKNOWN",
        "matching_sets_and_orientations": matches,
        "closest_direct_model_matches": closest[:5],
        "explanation": (
            "La coincidencia solo verifica ventanas circulares directas. "
            "Una no coincidencia NO demuestra una tirada prohibida por el servidor."
        ),
    }
