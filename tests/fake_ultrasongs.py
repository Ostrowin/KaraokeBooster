"""Podstawiony ultrasongs do testów potoku: te same argumenty, wynik z syntetycznych plików.

Tryb z FAKE_MODE: ok (domyślnie) | fail (kod 1) | missing (bez _vocals.mp3) | shift (wokal 150 ms później).
Każde wywołanie dopisuje linię do pliku FAKE_CALLS (jeśli ustawiony).
"""

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_alignment_e2e import SONG, SR, synth_vocals  # noqa: E402

from karaokebooster.ultrastar import parse  # noqa: E402


def main() -> int:
    argv = sys.argv[1:]
    if "-o" in argv:
        i = argv.index("-o")
        options = argv[i + 1]
        del argv[i:i + 2]
    else:
        options = ""
    p = argparse.ArgumentParser()
    p.add_argument("command")
    p.add_argument("--mp3", required=True)
    p.add_argument("--lyrics", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--artist", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args(argv)

    if os.environ.get("FAKE_CALLS"):
        with open(os.environ["FAKE_CALLS"], "a", encoding="utf-8") as f:
            f.write(options + "\n")
    print(f"fake ultrasongs: {args.artist} - {args.title} ({options})")
    mode = os.environ.get("FAKE_MODE", "ok")
    if mode == "fail":
        print("CUDA out of memory (udawane)", file=sys.stderr)
        return 1

    base = f"{args.artist} - {args.title}"
    out = Path(args.output) / base
    out.mkdir(parents=True)
    (out / f"{base}.txt").write_text(f"#TITLE:{args.title}\n#ARTIST:{args.artist}\n" + SONG.split("\n", 1)[1],
                                     encoding="utf-8")
    song = parse(SONG)
    if mode != "missing":
        shift = 0.15 if mode == "shift" else 0.0
        sf.write(str(out / f"{base}_vocals.mp3"), synth_vocals(song, shift_s=shift), SR, format="MP3")
    sf.write(str(out / f"{base}_accompaniment.mp3"), np.zeros(SR * 12), SR, format="MP3")
    (out / f"{base}_editor.html").write_text("<html>edytor</html>", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
