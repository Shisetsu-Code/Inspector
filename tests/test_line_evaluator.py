"""Paylines explícitos: pruebas de geometría completa y evaluación literal parcial."""
import unittest

from inspector.line_evaluator import extract_line_contract, evaluate_literal_screen
from inspector.payment_contract import build_payment_contract


def scene(*, declared=2, paths=None, directions=None, symbols=15, structure=True):
    if paths is None:
        paths = [[0,1,2,3,4],[5,6,7,8,9]]
    if directions is None:
        directions = [False, False]
    return {
        "line_component_structure": ([{
            "declared_line_count": declared,
            "declared_reel_count": 5,
            "symbol_refs_count": symbols,
            "xt_enabled_entries": len(paths),
            "scene_field_names": ["lines", "reels", "symbols", "xtEnabled"],
            "xt_first_serialized_field_names": ["symbolIndices", "isRightToLeft"],
        }] if structure else []),
        "line_paths_declarative": paths,
        "line_paths_directions": directions,
    }


class LineGeometryTests(unittest.TestCase):
    def setUp(self):
        self.pay = build_payment_contract({
            "1":{"2":"3","3":"10","4":"30","5":"50"},
            "2":{"3":"5","4":"20","5":"80"},
        })

    def test_valid_explicit_row_major_lines(self):
        g = extract_line_contract(scene(), 5, 3)
        self.assertEqual(g["status"],"EXPLICIT_LINE_GEOMETRY_CONFIRMED")
        self.assertEqual(g["reading_order"],"ROW_MAJOR")
        self.assertEqual(g["declared_line_count"],2)
        self.assertTrue(g["geometry_complete"])
        self.assertFalse(g["cash_payout_validation_possible"])
        result = evaluate_literal_screen("1112a2222a34567",g,self.pay)
        self.assertEqual(result["evaluation_status"],
                         "LITERAL_LINES_EVALUATED_NONAUTHORITATIVE")
        self.assertEqual(result["literal_paytable_units_total"],"30")
        self.assertIsNone(result["total_cash_win"])
        self.assertEqual(result["server_win_validity"],"UNKNOWN")

    def test_reject_incomplete_line_configuration(self):
        g = extract_line_contract(scene(declared=50,paths=[]),5,4)
        self.assertEqual(g["status"],"LINE_COUNT_ONLY")
        screen = evaluate_literal_screen("11111111111111111111",g,self.pay)
        self.assertEqual(screen["evaluation_status"],
                         "NOT_EVALUABLE_WITHOUT_EXPLICIT_LINES")
        self.assertIsNone(screen["literal_paytable_units_total"])

    def test_reject_partial_paths_and_unknown_direction(self):
        g = extract_line_contract(scene(declared=50),5,3)
        self.assertEqual(g["status"],"COUNT_PATHS_MISMATCH")
        g = extract_line_contract(scene(directions=[None,False]),5,3)
        self.assertEqual(g["status"],"UNKNOWN_LINE_DIRECTION")
        g = extract_line_contract(scene(paths=[[0,1,2,3,4],[0,1,2,3,3]]),5,3)
        self.assertEqual(g["status"],"INVALID_PATH_INDICES")

    def test_unknown_special_symbol_never_assume_no_win(self):
        g = extract_line_contract(scene(),5,3)
        result = evaluate_literal_screen("W12342222a34567",g,self.pay)
        self.assertEqual(result["evaluation_status"],
                         "PARTIAL_SPECIAL_SYMBOL_UNRESOLVED")
        self.assertEqual(result["unresolved_lines"][0]["reason"],
                         "UNIDENTIFIED_OR_SPECIAL_SYMBOL")
        self.assertEqual(result["server_win_validity"],"UNKNOWN")

    def test_column_major_mapping_requires_explicit_all_reels(self):
        scen = scene(declared=1,paths=[[0,3,6]],directions=[False],symbols=9)
        scen["line_component_structure"][0]["declared_reel_count"]=3
        g = extract_line_contract(scen,3,3)
        self.assertEqual(g["status"],"EXPLICIT_LINE_GEOMETRY_CONFIRMED")
        self.assertEqual(g["reading_order"],"COLUMN_MAJOR")
        self.assertEqual(g["extracted_paths"][0]["symbol_indices"],[0,3,6])

    def test_sample_client_scene_marked_not_generation_proof(self):
        import zipfile, json
        # Estructura real resumida del VS_LinesDefinitions del HAR vs10bbveg1000
        # Solo índices y dirección, no assets ni código propietario.
        example = scene(
            declared=3,
            paths=[[5,6,7,8,9],[0,1,2,3,4],[10,11,12,13,14]],
            directions=[False,False,False],symbols=15)
        g = extract_line_contract(example,5,3)
        self.assertEqual(g["status"],"EXPLICIT_LINE_GEOMETRY_CONFIRMED")
        self.assertEqual(g["reading_order"],"ROW_MAJOR")
        self.assertFalse(g["cash_payout_validation_possible"])


if __name__ == "__main__":
    unittest.main()
