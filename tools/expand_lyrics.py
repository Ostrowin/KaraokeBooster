"""Rozwija skróty powtórzeń w tekście piosenki ("/x2", "/x4") przed generowaniem w ultrasongs.

Zasada: w zwrotce z markerem "/xN" linie od początku zwrotki do markera powtarzają się N razy,
a linie po markerze zostają raz.

Użycie:
    .venv\\Scripts\\python tools\\expand_lyrics.py wejście.txt wyjście.txt
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

MARKER = re.compile(r"\s*/x(\d+)\s*$", re.IGNORECASE)


def expand(text: str) -> str:
    out = []
    for stanza in re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip()):
        lines = [l.rstrip() for l in stanza.strip().splitlines()]
        for i, line in enumerate(lines):
            m = MARKER.search(line)
            if m:
                block = lines[:i] + [line[: m.start()]]
                out.append("\n".join(block * int(m.group(1)) + lines[i + 1:]))
                break
        else:
            out.append("\n".join(lines))
    return "\n\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 2:
        print(__doc__, file=sys.stderr)
        return 1
    src, dst = Path(args[0]), Path(args[1])
    text = expand(src.read_text(encoding="utf-8-sig"))
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8")
    words = len(text.split())
    print(f"Zapisano {dst}: {sum(1 for l in text.splitlines() if l.strip())} linii, {words} słów.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
