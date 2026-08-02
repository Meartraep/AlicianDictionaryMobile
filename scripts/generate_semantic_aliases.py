#!/usr/bin/env python3
"""Compatibility entry point for the semantic-alias generation package."""

from __future__ import annotations

if __package__:
    from .semantic_aliases import *
else:
    from semantic_aliases import *


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        log("interrupted; database was not changed")
        raise SystemExit(130)
