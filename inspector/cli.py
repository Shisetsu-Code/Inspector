"""CLI: python -m inspector.cli analyze|capture."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

from .core import analyze_har
from .capture import capture_official_demo


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
    args = parser.parse_args(argv)
    try:
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
