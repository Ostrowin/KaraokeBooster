"""Kontrola wyrównania nut UltraStar z wokalem z Demucs (decyzja 0010).

Metoda (tylko numpy, bez AI):
1. Obwiednia RMS w oknach 10 ms.
2. Początek śpiewu = ramka, w której poziom przekracza próg (względem maksimum)
   po co najmniej 50 ms ciszy.
3. Dla pierwszych N nut z wysokością szukamy najbliższego początku w oknie ±300 ms.
4. Przesunięcie = mediana (początek − start nuty). |mediana| > tolerancja -> ostrzeżenie.

Ograniczenie: łapie przesunięcia do ok. ±300 ms. Przy równym rytmie przesunięcie
o całą wielokrotność odstępu między nutami może dopasować się do sąsiednich nut
i wyglądać na małe (albo zerowe) przesunięcie.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from .ultrastar import Song

HOP_S = 0.010
SEARCH_S = 0.300
MIN_SILENCE_S = 0.050


@dataclass(frozen=True)
class AlignmentReport:
    offset_ms: float | None   # dodatnie = wokal później niż nuty
    matched: int
    checked: int
    tolerance_ms: float
    message: str

    @property
    def ok(self) -> bool:
        return self.offset_ms is not None and abs(self.offset_ms) <= self.tolerance_ms


def detect_onsets(samples: np.ndarray, sr: int, threshold_db: float = -30.0) -> np.ndarray:
    if samples.ndim > 1:
        samples = samples.mean(axis=1)
    hop = max(1, int(sr * HOP_S))
    n = len(samples) // hop
    if n == 0:
        return np.array([])
    frames = samples[: n * hop].reshape(n, hop).astype(np.float64)
    rms = np.sqrt((frames ** 2).mean(axis=1))
    peak = rms.max()
    if peak <= 1e-6:
        return np.array([])
    active = 20 * np.log10(np.maximum(rms, 1e-12) / peak) > threshold_db
    min_silent = int(MIN_SILENCE_S / HOP_S)
    onsets, silent_run = [], min_silent
    for i, a in enumerate(active):
        if a and silent_run >= min_silent:
            onsets.append(i * HOP_S)
        silent_run = 0 if a else silent_run + 1
    return np.array(onsets)


def check_alignment(song: Song, vocals_path: str | Path, tolerance_ms: float = 30.0,
                    first_n: int = 8) -> AlignmentReport:
    samples, sr = sf.read(str(vocals_path), always_2d=False)
    return check_alignment_samples(song, np.asarray(samples), sr, tolerance_ms, first_n)


def check_alignment_samples(song: Song, samples: np.ndarray, sr: int,
                            tolerance_ms: float = 30.0, first_n: int = 8) -> AlignmentReport:
    notes = [n for n in song.notes if n.is_pitched][:first_n]
    onsets = detect_onsets(samples, sr)
    if len(onsets) == 0:
        return AlignmentReport(None, 0, len(notes), tolerance_ms,
                               "Nie wykryto śpiewu w pliku wokalu; nie da się sprawdzić wyrównania.")
    deltas = []
    for n in notes:
        d = onsets - n.start_s
        best = d[np.argmin(np.abs(d))]
        if abs(best) <= SEARCH_S:
            deltas.append(best)
    if len(deltas) < max(2, len(notes) // 2):
        return AlignmentReport(None, len(deltas), len(notes), tolerance_ms,
                               f"Za mało dopasowań ({len(deltas)}/{len(notes)}); "
                               "sprawdź #GAP albo czy wokal pasuje do pliku UltraStar.")
    offset_ms = float(np.median(deltas) * 1000)
    if abs(offset_ms) <= tolerance_ms:
        msg = f"Wyrównanie OK: przesunięcie {offset_ms:+.0f} ms ({len(deltas)}/{len(notes)} nut)."
    else:
        kier = "później" if offset_ms > 0 else "wcześniej"
        msg = (f"UWAGA: wokal zaczyna się średnio {abs(offset_ms):.0f} ms {kier} niż nuty "
               f"(tolerancja {tolerance_ms:.0f} ms). Popraw #GAP o {offset_ms:+.0f} ms.")
    return AlignmentReport(offset_ms, len(deltas), len(notes), tolerance_ms, msg)
