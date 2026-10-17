"""Pruebas offline de geometría de paylines y semántica monetaria incierta."""
import json
from pathlib import Path
import tempfile
import unittest

from inspector.line_stake_evidence import (
    inspect_line_scene, inspect_stake_declarations, inspect_wild_alphabets,
    line_hypothetical,
)


def fake_scene(components):
    return {"resources": [{
        "type": "GameObject", "data": {"root": [
            {"name": "Game", "components": components}
        ]}
    }]}


def har_record(text, name):
    return {
        "request": {
            "url": "https://demogamesfree.pragmaticplay.net/gs2c/common/v3/games-html5/games/vs/vs123sample/desktop/game/" + name,
            "method": "GET",
        },
        "response": {
            "status": 200, "content": {"text": text}
        },
    }


class LineStakeTests(unittest.TestCase):
    def test_explicit_lines_and_direction_not_backend_payout(self):
        scene = fake_scene([
            {"componentType": "VS_LinesDefinitions", "serializableData": {
                "lines": 2, "reels": 3,
                "symbols": [{"fileID": 12}],
                "xtEnabled": [
                    {"nestedFieldType": "LineInfo", "serializableData": {
                        "isRightToLeft": False, "symbolIndices": [0, 1, 2, 3, 4]}},
                    {"nestedFieldType": "LineInfo", "serializableData": {
                        "isRightToLeft": True, "symbolIndices": [5, 6, 7, 8, 9]}},
                ],
            }},
            {"componentType": "VS_Symbol", "serializableData": {"symbolId": 12}},
        ])
        raw = json.dumps(scene)
        midpoint = len(raw)//2
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.har"
            path.write_text(json.dumps({"log": {"entries": [
                har_record(raw[:midpoint], "game000.json"),
                har_record(raw[midpoint:], "game001.json"),
            ]}}), encoding="utf-8")
            result = inspect_line_scene(path, "vs123sample", 5, 3)
            self.assertEqual(result["status"], "PARSED")
            self.assertEqual(result["vs_lines_definitions_count"], 1)
            self.assertEqual(result["declared_line_counts"], [2])
            self.assertEqual(len(result["lines_recovered"]), 2)
            self.assertEqual(result["lines_recovered"][0]["direction"], "LEFT_TO_RIGHT")
            self.assertEqual(result["lines_recovered"][1]["direction"], "RIGHT_TO_LEFT")
            self.assertEqual(result["line_path_coverage"], "MATCHES_DECLARED_SCENE_LINE_COUNT")
            self.assertTrue(result["complete_all_active_paylines_known"])
            self.assertEqual(result["active_line_count_selected_in_session"], "UNKNOWN")
            self.assertEqual(result["wild_substitution_semantics"], "UNKNOWN")
            self.assertEqual(result["symbol_graphic_ids"], [12])

    def test_count_only_and_wrong_column_paths_do_not_count(self):
        scene = fake_scene([
            {"componentType": "VS_LinesDefinitions", "serializableData": {
                "lines": 25, "reels": 4, "xtEnabled": False,
                "symbols": [{"fileID": 44}]}
            },
            {"componentType": "VS_LinesDefinitions", "serializableData": {
                "lines": 20,
                "xtEnabled": [{"nestedFieldType": "LineInfo", "serializableData": {
                    "symbolIndices": [0, 5, 10, 15, 19],
                    "isRightToLeft": False,
                }}],
            }},
        ])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.har"
            path.write_text(json.dumps({"log": {"entries": [
                har_record(json.dumps(scene), "game000.json"),
            ]}}), encoding="utf-8")
            result = inspect_line_scene(path, "vs123sample", 5, 4)
            self.assertEqual(result["declared_line_counts"], [25, 20])
            self.assertEqual(result["lines_recovered"], [])
            self.assertEqual(result["line_path_coverage"], "COUNT_ONLY_NO_PATHS")
            self.assertFalse(result["complete_all_active_paylines_known"])

    def test_stake_declarations_do_not_claim_wager_formula(self):
        evidence = inspect_stake_declarations({
            "sc": "0.01,0.02,10.00",
            "bls": "25,40",
            "total_bet_min": "0.25",
            "total_bet_max": "42,500.00",
        })
        self.assertEqual(evidence["sc_values"], ["0.01", "0.02", "10.00"])
        self.assertEqual(evidence["bls_values"], [25,40])
        self.assertEqual(evidence["total_bet_max_declared"], "42500.00")
        self.assertEqual(evidence["hypothetical_sc_times_bls"]["minimum"], "0.25")
        self.assertEqual(evidence["hypothetical_sc_times_bls"]["maximum"], "400.00")
        self.assertTrue(evidence["hypothetical_sc_times_bls"]["minimum_matches_advertised"])
        self.assertFalse(evidence["hypothetical_sc_times_bls"]["maximum_matches_advertised"])
        self.assertFalse(evidence["hypothetical_sc_times_bls"]["formula_proven_as_real_stake"])
        self.assertFalse(evidence["payout_cash_scaling_proven"])
        self.assertEqual(evidence["actual_stake_for_arbitrary_screen"], "UNKNOWN")

    def test_w_literal_not_wild_proof(self):
        out = inspect_wild_alphabets({
            "0": [
                {"sequence": "abc"}, {"sequence": "W12"},
                {"sequence": "AWB"}, {"sequence": "xyz"},
                {"sequence": "TWX"}
            ],
        })
        self.assertEqual(out["reels_containing_W_directly_by_set"]["0"], [2,3,5])
        self.assertEqual(out["meaning_as_substitute_for_other_symbols"], "UNKNOWN")

    def test_literal_payline_example_never_assigns_cash(self):
        screen = "11124" + "44444" + "22113"
        result = line_hypothetical(
            screen, [0,1,2,3,4], {"1": {"3":"10"}}, width=5, height=3)
        self.assertEqual(result["literal_prefix_count"], 3)
        self.assertEqual(result["declared_paytable_entry"], "10")
        self.assertEqual(result["actual_payout_in_money"], "UNKNOWN")
        result2 = line_hypothetical(
            screen, [5,6,7,8,9], {"4": {"5":"100"}},
            width=5, height=3, direction="RIGHT_TO_LEFT")
        self.assertEqual(result2["declared_paytable_entry"], "100")
        with self.assertRaises(ValueError):
            line_hypothetical(screen, [3], {}, width=5, height=3)


if __name__ == "__main__":
    unittest.main()
