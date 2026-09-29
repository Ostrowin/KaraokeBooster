"""Analiza suchych nagrań: jak daleko śpiewak jest od nut (krok 9 w docs/design.md).

Nagranie musi startować w tym samym miejscu co audio z pliku UltraStar (eksport z REAPER od 0:00).

Użycie:
    .venv\\Scripts\\python tools\\analyze_takes.py piosenka.txt take1.wav [take2.wav ...] \\
        --markers take1_markers.csv --octave -1 --json wyniki.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import soundfile as sf  # noqa: E402

from karaokebooster import pitch  # noqa: E402
from karaokebooster.analysis import AnalysisError, analyze, format_report, read_markers  # noqa: E402
from karaokebooster.ultrastar import UltraStarError, load  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Analiza nagrań względem nut UltraStar.")
    p.add_argument("song", type=Path)
    p.add_argument("takes", type=Path, nargs="+", help="suche nagrania .wav")
    p.add_argument("--markers", type=Path, nargs="*", default=[],
                   help="pliki znaczników sylab, w kolejności nagrań")
    p.add_argument("--octave", type=int, default=0, help="przesunięcie nut docelowych w oktawach")
    p.add_argument("--engine", choices=["crepe", "yin"], default="crepe")
    p.add_argument("--json", type=Path, help="zapisz wyniki do pliku JSON")
    args = p.parse_args(argv)

    if args.markers and len(args.markers) != len(args.takes):
        print("BŁĄD: liczba plików --markers musi równać się liczbie nagrań.", file=sys.stderr)
        return 1
    try:
        song = load(args.song)
    except (UltraStarError, OSError) as e:
        print(f"BŁĄD: {e}", file=sys.stderr)
        return 1

    results = {}
    for i, take in enumerate(args.takes):
        try:
            samples, sr = sf.read(str(take), always_2d=False)
            markers = read_markers(args.markers[i]) if args.markers else None
            times, f0, conf = pitch.track(samples, sr, engine=args.engine)
        except (OSError, RuntimeError, AnalysisError, ImportError) as e:
            print(f"BŁĄD ({take.name}): {e}", file=sys.stderr)
            return 1
        report = analyze(song, times, f0, conf, samples=samples, sr=sr,
                         markers=markers, octave=args.octave)
        print(format_report(report, take.name))
        print()
        results[take.name] = report.to_dict()

    if args.json:
        args.json.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Zapisano {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
