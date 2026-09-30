"""Rozwija skróty powtórzeń w tekście piosenki ("/x2", "/x4") przed generowaniem w ultrasongs.

Zasada: w zwrotce z markerem "/xN" linie od początku zwrotki do markera powtarzają się N razy,
a linie po markerze zostają raz.

Użycie:
    .venv\\Scripts\\python tools\\expand_lyrics.py wejście.txt wyjście.txt
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from karaokebooster.lyrics_text import expand  # noqa: E402


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
