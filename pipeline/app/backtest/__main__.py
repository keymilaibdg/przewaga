"""python -m app.backtest run | ratings [--offline]"""
from __future__ import annotations

import argparse
import json
import logging
import sys

from .run import ratings_only, run


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="python -m app.backtest")
    p.add_argument("cmd", choices=["run", "ratings"])
    p.add_argument("--offline", action="store_true", help="use only cached downloads")
    a = p.parse_args(argv)
    out = run(offline=a.offline) if a.cmd == "run" else ratings_only(offline=a.offline)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
