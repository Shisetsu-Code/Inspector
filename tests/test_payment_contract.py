"""Regresiones offline para tabla de pagos y Free Spins sin inventar reglas."""
import unittest

from inspector.official_rules import extract_official_feature_rules
from inspector.payment_contract import (
    build_payment_contract, evaluate_literal_line, evaluate_symbol_count,
    extract_scatter_declarations,
)


class PaymentContractTests(unittest.TestCase):
    def setUp(self):
        self.contract = build_payment_contract({
            "1": {"2":"3","3":"10","4":"60","5":"200"},
            "2": {"2":"2","3":"10","4":"50","5":"160"},
            "3": {"2":"2","3":"10","4":"50","5":"160"},
            "4": {"3":"10","4":"40","5":"100"},
            "5": {"3":"10","4":"40","5":"100"},
            "a": {"3":"5","4":"10","5":"40"},
        }, client_methods=[
            "VSProtocolParser.ParseWinLines",
            "VSProtocolParser.ParseWinGroups",
            "VSProtocolParser.ParseScatters",
            "VSProtocolParser.ParseVsFreeSpin",
            "VSProtocolParser.ParseVsResponse",
        ])

    def test_real_deep_sea_paytable_thresholds(self):
        self.assertEqual(self.contract["symbols_with_2_count_payout"], ["1", "2", "3"])
        self.assertEqual(evaluate_symbol_count(self.contract,"1",2)["declared_multiplier"],"3")
        self.assertEqual(evaluate_symbol_count(self.contract,"2",2)["declared_multiplier"],"2")
        self.assertFalse(evaluate_symbol_count(self.contract,"4",2)["table_entry_exists"])
        self.assertEqual(evaluate_symbol_count(self.contract,"4",3)["declared_multiplier"],"10")
        self.assertEqual(evaluate_symbol_count(self.contract,"a",3)["declared_multiplier"],"5")

    def test_payout_is_conditional_not_server_win(self):
        record = evaluate_symbol_count(self.contract,"1",2)
        self.assertEqual(record["status"],"TABLE_ENTRY_EXISTS")
        self.assertEqual(record["screen_is_paid"],"UNKNOWN")
        self.assertEqual(record["server_payout_validity"],"UNKNOWN")
        self.assertEqual(record["free_spins_triggered"],"UNKNOWN")
        self.assertFalse(self.contract["full_payout_validation_possible"])

    def test_literal_line_is_a_hypothetical_only(self):
        r = evaluate_literal_line(self.contract,"11142")
        self.assertEqual(r["left_prefix_matching_symbols"],3)
        self.assertEqual(r["declared_multiplier"],"10")
        self.assertFalse(r["actual_paying_line_confirmed"])
        r = evaluate_literal_line(self.contract,"44112")
        self.assertFalse(r["table_entry_exists"])
        with self.assertRaises(ValueError):
            evaluate_literal_line(self.contract,"?42")


    def test_deep_sea_official_description_gives_distinct_trigger(self):
        html = """
        <html><head><script>window.secret='SHOULD_NOT_BE_USED';</script></head>
        <body><h1>Deep Sea Frenzy</h1>
        <p>Shark money symbols can land on reels 1-4 with random values of up
        to 200x, while collect symbols can hit on reel five carrying up to
        5x multipliers.</p><p>When eight or more money symbols land on the
        same spin as a collect symbol, their combined value is boosted by
        any multiplier present and awarded, before the bonus game triggers
        with five free spins. The +1 Spin collect symbol adds an extra spin
        to the total.</p></body></html>
        """
        rules = extract_official_feature_rules(html,game_slug="deep-sea-frenzy")
        self.assertEqual(rules["status"],"PUBLIC_DESCRIPTION_CONDITION_PARSED")
        self.assertEqual(rules["bonus_trigger"]["minimum_money_symbols"],8)
        self.assertEqual(rules["bonus_trigger"]["money_symbol_reels"],[1,2,3,4])
        self.assertEqual(rules["bonus_trigger"]["collect_symbol_reel"],5)
        self.assertEqual(rules["bonus_trigger"]["awarded_free_spins"],5)
        self.assertTrue(rules["extra_spin"]["collect_plus_one_can_add_one_spin"])
        self.assertFalse(rules["server_feature_execution_verified"])
        self.assertFalse(rules["complete_feature_rules_proven"])
        self.assertNotIn("SHOULD_NOT_BE_USED",str(rules))

    def test_other_game_description_cannot_be_assigned_same_trigger(self):
        doc = """<h1>Wild Depths</h1><p>3 scatter symbols trigger
            free spins, with 6, 9 or 12 free spins.</p>"""
        rules = extract_official_feature_rules(doc,game_slug="wild-depths")
        self.assertEqual(rules["status"],"NOT_RECOGNIZED")
        self.assertIsNone(rules["bonus_trigger"])

    def test_scatter_parser_preserves_no_proof_of_activation(self):
        scatter = extract_scatter_declarations("12~0,0,10,20~0,0,10,15~1,1,2,2")
        self.assertEqual(scatter["status"],"DECLARED_TABLE_PARSED")
        self.assertFalse(scatter["free_spins_activation_verified"])
        self.assertIsNone(scatter["free_spins_trigger_threshold"])
        self.assertFalse(scatter["variants"][0][0]["array_index_to_screen_count_confirmed"])
        self.assertEqual(scatter["variants"][0][0]["free_spins_array_client_order"],[15,10,0,0])

    def test_reject_malformed_scatter_and_secret(self):
        self.assertEqual(extract_scatter_declarations("TOKENabc=secret")["status"],"UNRECOGNIZED_FORMAT")
        self.assertEqual(extract_scatter_declarations("12~0,1~0,5")["status"],"UNRECOGNIZED_FORMAT")
        self.assertEqual(extract_scatter_declarations(None)["status"],"NOT_DECLARED")

    def test_paytable_never_infers_scatter_from_s(self):
        r = evaluate_symbol_count(self.contract,"S",3)
        self.assertEqual(r["status"],"UNKNOWN_SYMBOL")
        self.assertEqual(r["free_spins_triggered"],"UNKNOWN")
        self.assertEqual(self.contract["scatter"]["status"],"NOT_DECLARED")


if __name__ == "__main__":
    unittest.main()
