"""Diagnóstico de LineInfo en cualquier campo de VS_LinesDefinitions.

No presupone que symbolSquares sea una tabla de paylines: observa estructura,
rangos y compatibilidad con geometría por filas o por columnas. Exporta
únicamente índices numéricos acotados, sin sesiones ni código de terceros.
"""
from __future__ import annotations
from collections import Counter
import json
from pathlib import Path

from .client_evidence import _resource_map, MAX_SCENE

MAX_CANDIDATES = 500


def scan_line_candidates(har_path: str | Path, symbol: str | None, width: int, height: int) -> dict:
    out = {
        "schema": "inspector/lineinfo-candidates/v1",
        "status": "NOT_AVAILABLE",
        "geometry": {"width": width, "height": height},
        "candidate_fields": [],
        "candidate_total": 0,
        "unique_index_vectors_total": 0,
        "contains_repeated_identical_lineinfo": False,
        "validated_payline_paths": False,
        "active_paylines_known": False,
        "server_rng_known": False,
        "explanation": (
            "LineInfo puede aparecer en campos que no son recorridos de premio. "
            "Los índices se comprueban en ambos órdenes; no se confirma "
            "su papel matemático por el nombre de la estructura."),
    }
    if not 1 <= width <= 12 or not 1 <= height <= 12:
        out["status"] = "UNKNOWN_GEOMETRY"
        return out
    _, fragments, _ = _resource_map(har_path, symbol)
    if not fragments or sorted(fragments) != list(range(max(fragments) + 1)):
        out["status"] = "MISSING_SCENE_PARTS"
        return out
    joined = b"".join(fragments[i] for i in sorted(fragments))
    if len(joined) > MAX_SCENE:
        out["status"] = "SCENE_TOO_LARGE"
        return out
    try:
        resources = json.loads(joined).get("resources", [])
    except (UnicodeError, ValueError, TypeError):
        out["status"] = "SCENE_UNPARSEABLE"
        return out
    if not isinstance(resources, list):
        out["status"] = "SCENE_UNPARSEABLE"
        return out
    out["status"] = "SCANNED"
    for res in resources:
        if not isinstance(res, dict) or res.get("type") != "GameObject":
            continue
        roots = (res.get("data") or {}).get("root")
        if not isinstance(roots, list):
            continue
        for obj in roots:
            if not isinstance(obj, dict):
                continue
            for component in obj.get("components") or []:
                if not isinstance(component, dict) or component.get("componentType") != "VS_LinesDefinitions":
                    continue
                data = component.get("serializableData") or {}
                if not isinstance(data, dict):
                    continue
                for field, values in data.items():
                    if not isinstance(field, str) or len(field) > 55 or not isinstance(values, list):
                        continue
                    candidates = [v for v in values[:MAX_CANDIDATES]
                                  if isinstance(v, dict) and v.get("nestedFieldType") == "LineInfo"]
                    if not candidates:
                        continue
                    evidence = {
                        "field": field, "list_length": len(values),
                        "line_info_records": len(candidates),
                        "source_declares_as_paylines": False,
                        "row_major_compatible_count": 0,
                        "column_major_compatible_count": 0,
                        "both_compatible_count": 0,
                        "invalid_or_wrong_length": 0,
                        "unknown_directions": 0,
                        "unique_index_vectors": 0,
                        "duplicated_lineinfo_records": 0,
                        "all_indices_identical": False,
                        "distinct_payline_paths_proven": False,
                        "records": [],
                    }
                    for row in candidates:
                        d = row.get("serializableData") or {}
                        indices = d.get("symbolIndices") if isinstance(d, dict) else None
                        if (not isinstance(indices, list) or len(indices) != width
                                or any(type(x) is not int or not 0 <= x < width*height for x in indices)):
                            evidence["invalid_or_wrong_length"] += 1
                            continue
                        row_major = all(v % width == c for c,v in enumerate(indices))
                        column_major = all(v // height == c for c,v in enumerate(indices))
                        evidence["row_major_compatible_count"] += int(row_major)
                        evidence["column_major_compatible_count"] += int(column_major)
                        evidence["both_compatible_count"] += int(row_major and column_major)
                        dr = d.get("isRightToLeft")
                        if type(dr) is not bool:
                            evidence["unknown_directions"] += 1
                        evidence["records"].append({
                            "indices": indices, "row_major": row_major,
                            "column_major": column_major,
                            "direction": ("RIGHT_TO_LEFT" if dr is True
                                          else "LEFT_TO_RIGHT" if dr is False else "UNKNOWN")
                        })
                    unique = {tuple(x["indices"]) for x in evidence["records"]}
                    evidence["unique_index_vectors"] = len(unique)
                    evidence["duplicated_lineinfo_records"] = len(evidence["records"]) - len(unique)
                    evidence["all_indices_identical"] = bool(unique) and len(unique) == 1
                    if evidence["all_indices_identical"] and len(evidence["records"]) > 1:
                        evidence["interpretation"] = "REPEATED_IDENTICAL_VECTORS_NOT_DISTINCT_PAYLINES"
                    else:
                        evidence["interpretation"] = "UNVERIFIED_INDEX_RECORDS"
                    out["candidate_fields"].append(evidence)
                    out["candidate_total"] += len(candidates)
    if not out["candidate_fields"]:
        out["status"] = "NO_LINEINFO_FIELDS"
    else:
        out["unique_index_vectors_total"] = len({
            tuple(row["indices"])
            for field in out["candidate_fields"] for row in field["records"]
        })
        out["contains_repeated_identical_lineinfo"] = any(
            field["all_indices_identical"] and field["line_info_records"] > 1
            for field in out["candidate_fields"])
    return out
