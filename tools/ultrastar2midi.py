"""UltraStar .txt -> MIDI dla MotTune MIDI w REAPER (+ kontrola wyrównania).

Użycie:
    .venv\\Scripts\\python tools\\ultrastar2midi.py piosenka.txt -o song.mid --vocals vocals.wav
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from karaokebooster.alignment import check_alignment  # noqa: E402
from karaokebooster.midi_export import (  # noqa: E402
    DEFAULT_VOICE_CENTER,
    auto_octave,
    note_count,
    song_to_midi,
)
from karaokebooster.ultrastar import UltraStarError, UltraStarWarning, load  # noqa: E402

EXIT_OK, EXIT_ERROR, EXIT_MISALIGNED = 0, 1, 2


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="UltraStar -> MIDI (120 BPM, PPQ 960) dla korektora.")
    p.add_argument("song", type=Path, help="plik UltraStar .txt")
    p.add_argument("-o", "--output", type=Path, help="plik .mid (domyślnie obok .txt)")
    p.add_argument("--octave", default="auto",
                   help="przesunięcie w oktawach (np. -1) albo 'auto': dopasuj do zakresu głosu (domyślnie)")
    p.add_argument("--voice-center", type=int, default=DEFAULT_VOICE_CENTER,
                   help=f"środek zakresu głosu jako numer MIDI dla --octave auto (domyślnie {DEFAULT_VOICE_CENTER} = G3)")
    p.add_argument("--merge-ms", type=float, default=0.0,
                   help="scal nuty krótsze niż tyle ms z poprzednią")
    p.add_argument("--vocals", type=Path, help="vocals.wav z Demucs do kontroli wyrównania")
    p.add_argument("--tolerance-ms", type=float, default=30.0)
    args = p.parse_args(argv)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", UltraStarWarning)
        try:
            song = load(args.song)
            if args.octave == "auto":
                octave = auto_octave(song, args.voice_center)
            else:
                try:
                    octave = int(args.octave)
                except ValueError:
                    raise ValueError(f"--octave musi być liczbą albo 'auto', a jest {args.octave!r}") from None
            mid = song_to_midi(song, octave=octave, merge_below_ms=args.merge_ms)
        except (UltraStarError, ValueError, OSError) as e:
            print(f"BŁĄD: {e}", file=sys.stderr)
            return EXIT_ERROR
    for w in caught:
        print(f"OSTRZEŻENIE: {w.message}", file=sys.stderr)

    out = args.output or args.song.with_suffix(".mid")
    mid.save(str(out))
    how = " (auto)" if args.octave == "auto" else ""
    print(f"Zapisano {out} ({note_count(song)} nut, oktawa {octave:+d}{how}, kodowanie {song.encoding}).")

    if args.vocals:
        try:
            report = check_alignment(song, args.vocals, tolerance_ms=args.tolerance_ms)
        except (OSError, RuntimeError) as e:
            print(f"BŁĄD odczytu wokalu: {e}", file=sys.stderr)
            return EXIT_ERROR
        print(report.message, file=sys.stdout if report.ok else sys.stderr)
        if not report.ok:
            return EXIT_MISALIGNED
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
