"""Regresiones para LineInfo sin atribuir automáticamente sentido de paylines."""
import json
from pathlib import Path
import tempfile
import unittest

from inspector.line_candidates import scan_line_candidates


class LineCandidatesTest(unittest.TestCase):
    def test_can_distinguish_two_index_orders_inside_non_payline_field(self):
        vecs = [
            {"nestedFieldType": "LineInfo", "serializableData": {
                "symbolIndices": [0, 4, 8, 12, 16], "isRightToLeft": False}},
            {"nestedFieldType": "LineInfo", "serializableData": {
                "symbolIndices": [0, 1, 2, 3, 4], "isRightToLeft": True}},
            {"nestedFieldType": "LineInfo", "serializableData": {
                "symbolIndices": [0, 1, 5, 7, 10], "isRightToLeft": False}},
        ]
        scene = {"resources": [{"type": "GameObject", "data": {"root": [{
            "name": "WinLines",
            "components": [{
                "componentType": "VS_LinesDefinitions",
                "serializableData": {
                    "lines": [], "symbolSquares": vecs,
                    "reels": 15, "xtEnabled": 2,
                    "SECRET": "NEVER_EXPORT"
                },
            }],
        }]}}]}
        def entry(body):
            return {
                "request": {
                    "method": "GET",
                    "url": "https://demogamesfree.pragmaticplay.net/gs2c/common/v3/games-html5/games/vs/vs50frenzy/desktop/game/game000.json",
                },
                "response": {"status": 200, "content": {"text": body}},
            }
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"fixture.har"
            path.write_text(json.dumps({"log": {"entries": [entry(json.dumps(scene))]}}),
                            encoding="utf-8")
            result = scan_line_candidates(path, "vs50frenzy", 5, 4)
            self.assertEqual(result["status"], "SCANNED")
            self.assertEqual(result["candidate_total"], 3)
            group = result["candidate_fields"][0]
            self.assertEqual(group["field"], "symbolSquares")
            self.assertEqual(group["row_major_compatible_count"], 1)
            self.assertEqual(group["unique_index_vectors"], 3)
            self.assertEqual(group["duplicated_lineinfo_records"], 0)
            self.assertFalse(group["all_indices_identical"])
            self.assertEqual(group["column_major_compatible_count"], 1)
            self.assertFalse(result["validated_payline_paths"])
            self.assertFalse(result["active_paylines_known"])
            self.assertNotIn("NEVER_EXPORT", json.dumps(result))

    def test_many_identical_lineinfo_records_are_not_distinct_paylines(self):
        template = {"nestedFieldType": "LineInfo", "serializableData": {
            "symbolIndices": [0, 1, 2, 3, 4], "isRightToLeft": False
        }}
        scene = {"resources": [{"type": "GameObject", "data": {"root": [{
            "name": "WinLines",
            "components": [{
                "componentType": "VS_LinesDefinitions",
                "serializableData": {"symbolSquares": [template for _ in range(50)],
                                     "xtEnabled": 2, "lines": []}
            }]
        }]}}]}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "same.har"
            path.write_text(json.dumps({"log": {"entries": [{
                "request": {"method": "GET",
                  "url": "https://demogamesfree.pragmaticplay.net/gs2c/common/v3/games-html5/games/vs/vs50frenzy/desktop/game/game000.json"},
                "response": {"status": 200, "content": {"text": json.dumps(scene)}}
            }]}}))
            result = scan_line_candidates(path, "vs50frenzy", 5, 4)
            self.assertEqual(result["candidate_total"], 50)
            self.assertEqual(result["unique_index_vectors_total"], 1)
            self.assertTrue(result["contains_repeated_identical_lineinfo"])
            rows = result["candidate_fields"][0]
            self.assertEqual(rows["unique_index_vectors"], 1)
            self.assertEqual(rows["duplicated_lineinfo_records"], 49)
            self.assertFalse(result["validated_payline_paths"])
            self.assertEqual(rows["interpretation"],
                             "REPEATED_IDENTICAL_VECTORS_NOT_DISTINCT_PAYLINES")

    def test_missing_game_scene_does_not_create_payline_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"empty.har"
            path.write_text('{"log":{"entries":[]}}')
            result = scan_line_candidates(path, "vs50frenzy", 5, 4)
            self.assertEqual(result["status"], "MISSING_SCENE_PARTS")
            self.assertEqual(result["candidate_total"], 0)
            self.assertFalse(result["validated_payline_paths"])


if __name__ == "__main__":
    unittest.main()
