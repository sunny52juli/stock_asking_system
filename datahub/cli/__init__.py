"""CLI for datahub: product + action subcommands, JSON screening_scripts."""

from __future__ import annotations

import sys

from datahub import __version__

from .args import build_parser, get_opts
from .handlers import run


def main() -> None:
    parser = build_parser()
    ns = parser.parse_args()

    if getattr(ns, "version", False):
        print(__version__)
        sys.exit(0)

    product = getattr(ns, "product", None)
    action = getattr(ns, "action", None)
    if product is None:
        parser.print_help()
        sys.exit(0)
    opts = get_opts(ns)
    code = run(product, action, opts)
    sys.exit(code)


__all__ = ["main"]
