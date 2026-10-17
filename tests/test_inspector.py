"""Regresiones 100 % offline. Se ejecutan con python -m unittest discover."""
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlencode

from inspector.capture import permitted_url
from inspector.core import analyze_har, circular_windows, observe_spin, parse_paytable
from inspector.direct_model import compute_direct_model, check_screen


def record(action, response, symbol="vs10sample"):
    return {
        "request": {
            "method": "POST",
            "url": "https://demogamesfree.pragmaticplay.net/gs2c/ge/v5/gameService",
            "postData": {
                "text": "action=" + action + "&symbol=" + symbol
                + "&mgckey=SENSITIVE_SECRET_VALUE"
            },
            "headers": [{"name": "Cookie", "value": "SENSITIVE_SECRET_VALUE"}],
        },
        "response": {
            "status": 200,
            "content": {"mimeType": "text/plain", "text": urlencode(response)}
        },
    }


class InspectorTests(unittest.TestCase):
    def test_circular_windows(self):
        self.assertEqual(circular_windows("abcd", 3),
                         ["abc", "bcd", "cda", "dab"])
        self.assertEqual(circular_windows("", 3), [])

    def test_paytable(self):
        self.assertEqual(parse_paytable("a~3:2,4:5;W~2:10"),
                         {"a": {"3": "2", "4": "5"}, "W": {"2": "10"}})

    def test_url_allowlist(self):
        self.assertTrue(permitted_url(
            "https://www.pragmaticplay.com/en/games/big-bass-vegas-1000/"))
        self.assertTrue(permitted_url(
            "https://demogamesfree.pragmaticplay.net/gs2c/openGame.do?gameSymbol=abc"))
        self.assertFalse(permitted_url("http://www.pragmaticplay.com/en/games/a/"))
        self.assertFalse(permitted_url("https://evil.example/play"))
        self.assertFalse(permitted_url(
            "https://demogamesfree.pragmaticplay.net/gs2c/ge/v5/gameService"))

    def test_har_analysis_and_redaction(self):
        events = [
            record("doInit", {
                "reel_set0": "abc~def~ghi~jkl~mno",
                "reel_set1": "abc~def~ghi~jkl~mno",
                "sw": "5", "sh": "3", "st": "rect", "paytable": "a~3:5",
                "token": "SENSITIVE_SECRET_VALUE",
            }),
            record("doSpin", {"s": "adgjmbehkncfilo", "w": "100"}),
            {
                "request": {
                    "method": "GET",
                    "url": "https://demogamesfree.pragmaticplay.net/gs2c/common/v3/games-html5/games/vs/vs10sample/desktop/build.js",
                },
                "response": {"status": 200,
                             "content": {"text": "const reel_set0=1; const winLines=5;"}},
            },
        ]
        with tempfile.TemporaryDirectory() as td:
            har = Path(td) / "input.har"
            out = Path(td) / "result"
            har.write_text(json.dumps({"log": {"entries": events}}), encoding="utf-8")
            summary = analyze_har(har, out)
            self.assertEqual(summary["doInit_count"], 1)
            self.assertEqual(summary["historical_spins"], 1)
            self.assertEqual(summary["reel_set_count"], 2)
            self.assertEqual(summary["reel_strip_count"], 10)
            self.assertTrue(summary["has_build_js"])
            self.assertFalse(summary["complete_server_math_known"])
            self.assertEqual(summary["extractor_spins_sent"], 0)
            txt = (out / "sanitized-init.har").read_text(encoding="utf-8")
            self.assertNotIn("SENSITIVE_SECRET_VALUE", txt)
            self.assertNotIn("doSpin", txt)
            self.assertNotIn("token", txt)
            self.assertEqual(len(json.loads(txt)["log"]["entries"]), 1)
            for filename in ("report.md", "summary.json", "assets_index.json",
                             "paytable.json", "historical_audit.json", "direct_model.json"):
                self.assertTrue((out / filename).exists(), filename)


    def test_direct_union_exact_with_overlap(self):
        def strip(seq):
            return {"sequence": seq}
        reel_sets = {
            "0": [strip("ab"), strip("cd")],
            "1": [strip("abx"), strip("cdy")],
        }
        model = compute_direct_model(reel_sets, 2, 2)
        self.assertTrue(model["valid_model"])
        self.assertEqual(model["sets"]["0"]["unique_screen_count"], 4)
        self.assertEqual(model["sets"]["1"]["unique_screen_count"], 9)
        self.assertEqual(model["union_unique_screen_count"], 12)
        self.assertEqual(model["duplicated_across_sets"], 1)
        self.assertEqual(model["special_symbol_count_histogram"], {"0": 12})

    def test_direct_screen_membership_does_not_prove_rng_validity(self):
        reel_sets = {"0": [{"sequence": "ab"}, {"sequence": "cd"}]}
        match = check_screen(reel_sets, 2, 2, "acbd")
        self.assertTrue(match["direct_model_compatible"])
        self.assertEqual(match["server_outcome_validity"], "UNKNOWN")
        missing = check_screen(reel_sets, 2, 2, "zzzz")
        self.assertFalse(missing["direct_model_compatible"])
        self.assertEqual(missing["server_outcome_validity"], "UNKNOWN")
        with self.assertRaises(ValueError):
            check_screen(reel_sets, 2, 2, "abc")

    def test_direct_special_symbol_count_histogram(self):
        reels = {"0": [{"sequence": "SSab"}, {"sequence": "cd"}]}
        d = compute_direct_model(reels, 2, 2)
        self.assertEqual(d["union_unique_screen_count"], 8)
        self.assertEqual(d["special_symbol_count_histogram"],
                         {"0": 2, "1": 4, "2": 2})

    def test_direct_model_is_not_global_validity(self):
        strips = {"0": [
            {"sequence": "abc", "direct_circular_windows": {"3": ["abc","bca","cab"]}}
            for _ in range(5)
        ]}
        check = observe_spin("zzzzzzzzzzzzzzz", strips, 5, 3)
        self.assertTrue(check["geometry_matches"])
        self.assertFalse(check["direct_stop_model_match"])
        self.assertEqual(check["global_server_validity"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
