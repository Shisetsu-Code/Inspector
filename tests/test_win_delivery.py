"""Distinguir parser de premios del servidor y resaltado visual; sin falsos OK."""
import json
import unittest
from inspector.win_delivery import inspect_win_delivery

class WinDeliveryTests(unittest.TestCase):
    def test_parser_and_visual_highlighting_are_not_math_proof(self):
        js = """
        var SECRET_TOKEN='DONOTLEAK';
        VSProtocolParser.ParseWinLines=function(data){
          var x=data[GameProtocolDictionary.winLines(0)];
          var a=new VsWinLine;
          a.LineNumber=1; a.WinAmount=2; a.WinPositions=[1,2];
          return a;
        };
        VSProtocolParser.ParseWinGroups=function(data){
          var groups=data[GameProtocolDictionary.winWayGroups];
          var a=new VsWinLine;
          a.WinAmount=2; a.WinPositions=[1,2];
          a.waysCount=1; a.waysLength=3; a.payingDirection="left";
          return a;
        };
        WinLineVisual.prototype.OnWinLineShow=function(){
          var x=Vars.ReceivedWinLines;
          for(var i of x.WinPositions)this.linesDefinitions.symbolSquares[i].SetActive(true);
        };
        """
        trace = inspect_win_delivery(js.encode())
        self.assertTrue(trace["server_may_send_winning_amount_and_positions"])
        self.assertTrue(trace["client_can_visualize_received_win_positions"])
        self.assertFalse(trace["money_won_validation_proven"])
        self.assertFalse(trace["server_rng_rules_known"])
        self.assertNotIn("DONOTLEAK", json.dumps(trace))

    def test_no_js_never_claims_a_validating_engine(self):
        t=inspect_win_delivery(b"")
        self.assertFalse(t["client_can_visualize_received_win_positions"])
        self.assertFalse(t["server_may_send_winning_amount_and_positions"])
        self.assertEqual(t["active_protocol_family_observed"],"NO_SPIN_CAPTURED")

    def test_visual_symbol_squares_alone_not_proof_of_payment(self):
        s='WinLineVisual.prototype.OnWinLineShow=function(){this.symbolSquares[i].SetActive(true);};'
        t=inspect_win_delivery(s.encode())
        self.assertFalse(t["server_may_send_winning_amount_and_positions"])
        self.assertFalse(t["client_can_visualize_received_win_positions"])

    def test_parser_amount_without_win_positions_insufficient(self):
        s='VSProtocolParser.ParseWinLines=function(x){return x.WinAmount;}'
        t=inspect_win_delivery(s.encode())
        self.assertFalse(t["server_may_send_winning_amount_and_positions"])

if __name__=="__main__":
    unittest.main()
