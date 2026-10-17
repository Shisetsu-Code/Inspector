"""Pruebas del trazado animación/protocolo; no requiere HAR real."""
import json
import unittest

from inspector.animation_trace import _balanced_function, analyze_animation_origin


class AnimationOriginTests(unittest.TestCase):
    def test_balanced_method_handles_nested_braces_and_strings(self):
        body = """if(x){var t="no { cierre }"; if(z){test();} }
                    else { let q='} no termina'; } return x} trailing"""
        extracted, complete = _balanced_function(body, 0)
        self.assertTrue(complete)
        self.assertIn("return x", extracted)
        self.assertNotIn("trailing", extracted)

    def test_proof_is_only_of_client_branch_not_server_rng(self):
        source = """
        const SecretPrivateToken="NEVER_INCLUDE_THIS_VALUE";
        var GameProtocolDictionary={
            reelSetIndex:"n_reel_set",reelSetIndexCurrent:"reel_set",
            numberOfReelSets:"reel_set_size",symbolReplacementData:"srf",
            Tumbling:"tmb",NextReelsSymbolsList:"n_rsl",randomMysterySymbol:"msr"};
        VSProtocolParser.ParseVsInitData=function(nameValues){
            var result={};
            result.ReelSetIndex=GameProtocolCommonParser.ParseNulableInt(
                nameValues,GameProtocolDictionary.reelSetIndex);
            result.ReelSetIndexCurrent=GameProtocolCommonParser.ParseNulableInt(
                nameValues,GameProtocolDictionary.reelSetIndexCurrent);
            return result;
        };
        VSProtocolParser.ParseTumblingData=function(source){
            return GameProtocolCommonParser.ParseIfExist(source,
                GameProtocolDictionary.Tumbling);
        };
        VSProtocolParser.ParseSymbolReplacementData=function(source){
            var result={};
            result.SymbolReplacementData=GameProtocolCommonParser.ParseIfExist(
                source,GameProtocolDictionary.symbolReplacementData);
            return result;
        };
        VS_Reel.prototype.GetNextSymbol=function(){
            if(this.reelsManager.stopOnScreenSymbols){
                return this.GetReelScreenSymbols(XT.GetObject(Vars.ResultScreenSymbols))[0];
            }
            if(this.replaceEmptySymbol){
                return this.emptySymbolReplacements[Math.floor(Math.random()*2)];
            }
            return this.symbolList[this.stopPosition];
        };
        OfflineServer.prototype.GetNextRandomSpin=function(){
            return Math.random();
        };
        """
        scene = {"reel_stop_uses_response_symbols": False,
                 "offline_server_attachment": "NULL"}
        data = analyze_animation_origin(source.encode(), scene, {
            "doInit": ["reel_set_size"],
            "doSpin": ["reel_set", "tmb"],
        })
        self.assertTrue(data["build_js_present"])
        self.assertEqual(data["interpretation"],
                         "CLIENT_HAS_DISTINCT_RESULT_AND_VISUAL_REEL_PATHS")
        fields = data["protocol_fields"]
        self.assertEqual(fields["reel_set_current"]["status"], "OBSERVED_IN_CAPTURE")
        self.assertEqual(fields["reel_set_next"]["status"], "CLIENT_KNOWS_FIELD_ONLY")
        self.assertEqual(fields["reel_sets_count"]["status"], "OBSERVED_IN_CAPTURE")
        self.assertEqual(fields["tumbling"]["status"], "OBSERVED_IN_CAPTURE")
        self.assertEqual(fields["replacement_data"]["status"], "CLIENT_KNOWS_FIELD_ONLY")
        self.assertTrue(data["stop_logic"]["visual_randomness_in_method"])
        self.assertTrue(data["stop_logic"]["blank_symbol_random_replacement_branch"])
        self.assertFalse(data["stop_logic"]["scene_stop_on_result_screen_initial"])
        self.assertFalse(data["stop_logic"]["runtime_branch_selection_observed"])
        self.assertFalse(data["server_outcome_rules_known"])
        self.assertEqual(data["global_possible_or_impossible_screen_classification"],
                         "UNKNOWN")
        self.assertNotIn("NEVER_INCLUDE_THIS_VALUE", json.dumps(data))

    def test_missing_build_yields_unknown_no_fabricated_fields(self):
        data = analyze_animation_origin(b"", {}, {"doSpin":["n_reel_set"]})
        self.assertEqual(data["interpretation"], "BUILD_JS_NOT_CAPTURED")
        self.assertFalse(data["stop_logic"]["method_found"])
        self.assertEqual(data["protocol_fields"], {})

    def test_code_dictionary_without_decoder_is_not_confirmed(self):
        source = 'var Foo={reelSetIndex:"n_reel_set"};'
        data = analyze_animation_origin(source.encode(), {}, {})
        field = data["protocol_fields"]["reel_set_next"]
        self.assertTrue(field["dictionary_declared_in_client"])
        self.assertFalse(field["parser_uses_dictionary_field"])
        self.assertEqual(field["status"], "NOT_CONFIRMED")

    def test_uncaptured_selector_is_not_activated_by_class_method_presence(self):
        s = ('var GameProtocolDictionary={reelSetIndexCurrent:"reel_set"};'
             'VSProtocolParser.ParseVsData=function(x){'
             'return GameProtocolCommonParser.ParseNulableInt('
             'x,GameProtocolDictionary.reelSetIndexCurrent);};')
        data = analyze_animation_origin(s.encode(), {}, {"doInit": [], "doSpin":[]})
        self.assertEqual(data["protocol_fields"]["reel_set_current"]["status"],
                         "CLIENT_KNOWS_FIELD_ONLY")
        self.assertFalse(data["protocol_fields"]["reel_set_current"]["observed_in_captured_spin"])


if __name__ == "__main__":
    unittest.main()
