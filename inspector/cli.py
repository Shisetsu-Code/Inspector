"""CLI: python -m inspector.cli analyze|capture."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

from .core import analyze_har
from .capture import capture_official_demo
from .direct_model import check_screen
from .payment_contract import evaluate_symbol_count, evaluate_literal_line, evaluate_declared_bonus
from .line_evaluator import evaluate_literal_screen


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspector Pragmatic — sin giros ni compras")
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("analyze", help="Analizar HAR offline")
    a.add_argument("har", type=Path)
    a.add_argument("--out", type=Path, default=Path("output"))
    a.add_argument("--require-init", action="store_true")
    c = sub.add_parser("capture", help="Capturar una demo oficial y analizarla")
    c.add_argument("url")
    c.add_argument("--out", type=Path, default=Path("output"))
    c.add_argument("--seconds", type=int, default=70)
    c.add_argument("--keep-raw-har", type=Path, default=None,
                   help="Guardar HAR completo PRIVADO (nunca subir al repositorio)")
    c.add_argument("--require-init", action="store_true")
    k = sub.add_parser("check", help="Comprobar pantalla contra ventanas directas")
    k.add_argument("result_folder", type=Path)
    k.add_argument("screen", help="Cadena row-major o column-major de ancho x alto")
    p = sub.add_parser("pay-count", help="Consultar entrada de paytable por símbolo y cantidad")
    p.add_argument("result_folder", type=Path)
    p.add_argument("symbol")
    p.add_argument("count", type=int)
    l = sub.add_parser("pay-line", help="Simular prefijo literal de línea, NO cobro real")
    l.add_argument("result_folder", type=Path)
    l.add_argument("symbols")
    b = sub.add_parser("bonus-check", help="Evaluar condición pública de money symbols + Collect")
    b.add_argument("result_folder", type=Path)
    b.add_argument("money_symbols", type=int)
    b.add_argument("--collect-reel5", action="store_true",
                   help="Confirmar Collect en el carrete 5")
    b.add_argument("--plus-one", action="store_true",
                   help="Collect +1 spin en la misma tirada")
    e = sub.add_parser("screen-pay", help="Condiciones literales por líneas de escena; NO cobro real")
    e.add_argument("result_folder", type=Path)
    e.add_argument("screen", help="Pantalla en orden de filas, ancho × alto símbolos")
    s = sub.add_parser("evaluate-screen", help="Premios literales condicionados a líneas explícitas")
    s.add_argument("result_folder", type=Path)
    s.add_argument("screen", help="Cadena de símbolos codificados, no valores monetarios")
    args = parser.parse_args(argv)
    try:
        if args.command == "screen-pay":
            # Alias histórico: ahora exige líneas explícitas verificadas por
            # la misma validación estricta usada en evaluate-screen y la GUI.
            folder = args.result_folder
            lines = json.loads((folder / "line_geometry.json").read_text(encoding="utf-8"))
            payment = json.loads((folder / "payment_contract.json").read_text(encoding="utf-8"))
            result = evaluate_literal_screen(args.screen, lines, payment)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "evaluate-screen":
            folder = args.result_folder
            lines = json.loads((folder / "line_geometry.json").read_text(encoding="utf-8"))
            payment = json.loads((folder / "payment_contract.json").read_text(encoding="utf-8"))
            result = evaluate_literal_screen(args.screen, lines, payment)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "bonus-check":
            contract = json.loads((args.result_folder / "payment_contract.json").read_text(encoding="utf-8"))
            result = evaluate_declared_bonus(
                contract, money_symbol_count=args.money_symbols,
                collect_on_reel_5=args.collect_reel5, collect_plus_one=args.plus_one)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command in {"pay-count", "pay-line"}:
            contract = json.loads((args.result_folder / "payment_contract.json").read_text(encoding="utf-8"))
            result = (evaluate_symbol_count(contract, args.symbol, args.count)
                      if args.command == "pay-count" else evaluate_literal_line(contract, args.symbols))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "check":
            model = json.loads((args.result_folder / "reel_rules.json").read_text(encoding="utf-8"))
            summary = json.loads((args.result_folder / "summary.json").read_text(encoding="utf-8"))
            result = check_screen(model["sets"], summary["geometry"]["width"],
                                  summary["geometry"]["height"], args.screen)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "analyze":
            result = analyze_har(args.har, args.out)
        else:
            if args.keep_raw_har is not None:
                raw = args.keep_raw_har
                capture = capture_official_demo(args.url, raw, duration_s=args.seconds)
                result = analyze_har(raw, args.out)
            else:
                with tempfile.TemporaryDirectory(prefix="inspector_raw_") as temp:
                    raw = Path(temp) / "network.har"
                    capture = capture_official_demo(args.url, raw, duration_s=args.seconds)
                    result = analyze_har(raw, args.out)
            # Diagnóstico sin cookies ni URL dinámica del launcher.
            (args.out / "capture_status.json").write_text(
                json.dumps({k: v for k, v in capture.items() if k != "source"},
                           indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.require_init and result["doInit_count"] == 0:
            print("ERROR: no se observó doInit; no hay modelo de carretes", file=sys.stderr)
            return 2
        return 0
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
