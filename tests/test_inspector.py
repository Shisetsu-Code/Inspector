"""Regresiones 100 % offline. Se ejecutan con python -m unittest discover."""
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlencode

from inspector.capture import permitted_url, should_allow_request
from inspector.core import analyze_har, circular_windows, observe_spin, parse_paytable
from inspector.direct_model import compute_direct_model, check_screen
from inspector.client_evidence import inspect_client_har


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

    def test_request_filter_never_decodes_binary_analytics_post(self):
        class BinaryRequest:
            method = "POST"
            url = "https://analytics.example.org/collect"
            @property
            def post_data(self):
                raise UnicodeDecodeError("utf-8", b"\xe4", 0, 1, "invalid byte")

        class BinaryAtGameService(BinaryRequest):
            url = "https://demogamesfree.pragmaticplay.net/gs2c/ge/v5/gameService"

        class InitRequest:
            method = "POST"
            url = "https://demogamesfree.pragmaticplay.net/gs2c/ge/v5/gameService"
            post_data = "action=doInit&symbol=vs50frenzy"

        class SpinRequest(InitRequest):
            post_data = "action=doSpin&symbol=vs50frenzy"

        self.assertFalse(should_allow_request(BinaryRequest()))
        self.assertFalse(should_allow_request(BinaryAtGameService()))
        self.assertTrue(should_allow_request(InitRequest()))
        self.assertFalse(should_allow_request(SpinRequest()))

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
                             "paytable.json", "historical_audit.json", "direct_model.json", "client_evidence.json"):
                self.assertTrue((out / filename).exists(), filename)



    def test_client_source_and_scene_are_separated_from_server_rng(self):
        root = {
            "resources": [{"type": "GameObject", "data": {"root": [
                {"name": "ServerConnector", "components": [{
                    "componentType": "RequestProvider",
                    "serializableData": {"offlineServer": None}}]},
                {"name": "ReelsManager", "components": [{
                    "componentType": "VS_ReelsManager",
                    "serializableData": {"stopOnScreenSymbols": True}}]},
                {"name": "Symbols", "components": [{
                    "componentType": "V4ServerAdapter_Symbols",
                    "serializableData": {"screenSymbolsKeys": ["S", "X", "W"]}}]},
                {"name": "WinLines", "components": [{
                    "componentType": "VS_LinesDefinitions",
                    "serializableData": {"xtEnabled": [
                        {"nestedFieldType": "LineInfo",
                         "serializableData": {"symbolIndices": [0, 1, 2]}}
                    ]}}]},
            ]}}]
        }
        blob = json.dumps(root)
        pivot = len(blob) // 2
        code = (
            "VS_Reel.prototype.GetNextSymbol=function(){"
            "if(this.reelsManager.stopOnScreenSymbols){"
            "this.GetReelScreenSymbols(XT.GetObject(Vars.ResultScreenSymbols));"
            "}else{this.stopPosition--;x=this.symbolList[pos%this.symbolList.length];}};"
            "OfflineServer.prototype.Start=function(){};"
            "RequestProvider.prototype.NewRequest=function(){"
            "return ServerOptions.isOnline?a:b};"
            "VSProtocolParser.ParseWinScreenSymbols();"
            "PRIVATE_TOKEN_NOT_FOR_EXPORT"
        )
        def asset(filename, text):
            return {
                "request": {"method": "GET",
                            "url": ("https://demogamesfree.pragmaticplay.net"
                                    "/gs2c/common/v3/games-html5/games/vs/"
                                    "vs10sample/desktop/" + filename)},
                "response": {"status": 200, "content": {"text": text}}
            }
        events = [
            asset("build.js", code),
            asset("game/game000.json", blob[:pivot]),
            asset("game/game001.json", blob[pivot:]),
            asset("game/game002.json", "{}"),  # substituido abajo: no usar fragmento extra
        ][:3]
        with tempfile.TemporaryDirectory() as td:
            har = Path(td) / "input.har"
            har.write_text(json.dumps({"log": {"entries": events}}), encoding="utf-8")
            analysis = inspect_client_har(har, "vs10sample")
            self.assertEqual(analysis["scene"]["status"], "PARSED")
            self.assertTrue(analysis["scene"]["reel_stop_uses_response_symbols"])
            self.assertEqual(analysis["scene"]["offline_server_attachment"], "NULL")
            self.assertEqual(analysis["scene"]["line_paths_declarative"], [[0,1,2]])
            self.assertEqual(analysis["scene"]["screen_symbol_keys"], ["S","X","W"])
            self.assertTrue(analysis["client_code"]["proofs"][
                "stopping_branch_reads_result_screen_symbols"])
            self.assertTrue(analysis["client_code"]["proofs"][
                "alternative_branch_reads_visual_symbol_list"])
            self.assertEqual(analysis["conclusions"][
                "server_result_drives_visual_stop_evidence"], "STRONG_CLIENT_EVIDENCE")
            self.assertFalse(analysis["conclusions"]["complete_server_outcome_rules_recovered"])
            self.assertNotIn("PRIVATE_TOKEN_NOT_FOR_EXPORT", json.dumps(analysis))
            self.assertEqual(analysis["conclusions"]["global_allowed_or_forbidden_spin_set"],
                             "UNKNOWN")

    def test_scene_must_be_complete_not_silently_invented(self):
        entry = {
            "request": {"method": "GET",
                        "url": ("https://demogamesfree.pragmaticplay.net"
                                "/gs2c/common/v3/games-html5/games/vs/"
                                "vs10sample/desktop/game/game001.json")},
            "response": {"status": 200, "content": {"text": "{}"}}
        }
        with tempfile.TemporaryDirectory() as td:
            har = Path(td) / "partial.har"
            har.write_text(json.dumps({"log":{"entries":[entry]}}), encoding="utf-8")
            analysis = inspect_client_har(har, "vs10sample")
            self.assertEqual(analysis["scene"]["status"], "INCOMPLETE_PARTS")
            self.assertEqual(analysis["conclusions"][
                "server_result_drives_visual_stop_evidence"], "INCOMPLETE")

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
