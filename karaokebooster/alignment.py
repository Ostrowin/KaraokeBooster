"""Kontrola wyrównania nut UltraStar z wokalem z Demucs (decyzje 0010 i 0016).

Metoda (0016): porównanie wysokości.
1. Wysokość wokalu co 10 ms (crepe albo yin, `karaokebooster.pitch`).
2. Nuta docelowa w każdej ramce (tylko nuty z wysokością).
3. Przesuwamy nuty o k·10 ms w oknie ±300 ms. Dla każdego przesunięcia liczymy
   zgodność = ramki, w których śpiew (pewność >= 0.5) jest w ±1 półtonie od nuty (bez oktawy),
   podzielone przez ramki, w których jest nuta LUB śpiew. Cisza w trakcie nuty i śpiew
   poza nutą obniżają wynik, więc przesunięcie "w ciszę" nie wygrywa.
4. Wygrywa przesunięcie z najwyższą zgodnością. Dodatnie = wokal później niż nuty.
5. Pewność: najlepsza zgodność musi być >= 2x mediany zgodności w oknie ±1 s.
   Kalibracja na "Za tobą pójdę jak na bal": właściwa melodia 4.4x, obca melodia 1.4x.
   Bezwzględny % zależy od silnika (crepe 55%, yin 33% na tej samej piosence), więc nie jest progiem.
6. Pewność (2): trafienia wśród ramek, gdzie jest i śpiew, i nuta, >= 50%.
   Sam rytm daje szczyt kontrastu także dla złej melodii (losowa melodia w tym rytmie: 2.5x),
   a trafienia to rozróżniają: właściwa 84-87% (yin/crepe), losowa 14%.

detect_onsets() zostaje dla analizy nagrań (skuteczność detektora sylab).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from .pitch import HOP_S, hz_to_midi
from .ultrastar import Song

MIN_SILENCE_S = 0.050
SEARCH_MS = 300
CONF_MIN = 0.5
MATCH_SEMITONES = 1.0
CONTEXT_MS = 1000       # okno odniesienia dla oceny pewności
MIN_CONTRAST = 2.0      # najlepsze przesunięcie >= 2x mediana zgodności w oknie ±1 s
MIN_HIT_PCT = 50.0      # trafienia wśród ramek śpiew∧nuta; przypadkiem ok. 14-25%
MIN_FRAMES = 200


@dataclass(frozen=True)
class AlignmentReport:
    offset_ms: float | None   # dodatnie = wokal później niż nuty
    match_pct: float | None   # zgodność wysokości przy najlepszym przesunięciu
    contrast: float | None    # najlepsza zgodność / mediana zgodności w oknie ±1 s
    hit_pct: float | None     # % ramek śpiew∧nuta w ±1 półtonie przy najlepszym przesunięciu
    frames: int               # porównane ramki przy najlepszym przesunięciu
    tolerance_ms: float
    message: str

    @property
    def confident(self) -> bool:
        return (self.contrast is not None and self.contrast >= MIN_CONTRAST
                and self.hit_pct is not None and self.hit_pct >= MIN_HIT_PCT)

    @property
    def ok(self) -> bool:
        return self.offset_ms is not None and self.confident and abs(self.offset_ms) <= self.tolerance_ms


def detect_onsets(samples: np.ndarray, sr: int, threshold_db: float = -30.0) -> np.ndarray:
    """Początki śpiewu po co najmniej 50 ms ciszy (energia RMS w oknach 10 ms)."""
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


def _target_grid(song: Song, n_frames: int, t0: float) -> np.ndarray:
    """Nuta docelowa (MIDI) w każdej ramce siatki t0 + i*HOP_S; NaN poza nutami."""
    target = np.full(n_frames, np.nan)
    for note in song.notes:
        if not note.is_pitched:
            continue
        a = max(0, int(np.ceil((note.start_s - t0) / HOP_S - 1e-9)))
        b = min(n_frames, int(np.ceil((note.end_s - t0) / HOP_S - 1e-9)))
        if a < b:
            target[a:b] = note.pitch_midi
    return target


def check_alignment_pitch(song: Song, times: np.ndarray, f0: np.ndarray, conf: np.ndarray,
                          tolerance_ms: float = 30.0, search_ms: int = SEARCH_MS) -> AlignmentReport:
    """Szuka przesunięcia nut względem śpiewu. Czasy muszą być siatką co HOP_S."""
    if len(times) == 0:
        return AlignmentReport(None, None, None, None, 0, tolerance_ms, "Pusty plik wokalu.")
    sung = hz_to_midi(np.asarray(f0, dtype=float))
    valid = (np.asarray(conf) >= CONF_MIN) & ~np.isnan(sung)
    if valid.sum() < MIN_FRAMES:
        return AlignmentReport(None, None, None, None, int(valid.sum()), tolerance_ms,
                               "Nie wykryto śpiewu w pliku wokalu; nie da się sprawdzić wyrównania.")
    target = _target_grid(song, len(times), float(times[0]))
    k_search = int(round(search_ms / 1000 / HOP_S))
    k_ctx = max(k_search, int(round(CONTEXT_MS / 1000 / HOP_S)))
    n = len(times)
    scores: dict[int, tuple[float, int, int]] = {}
    for k in range(-k_ctx, k_ctx + 1):
        # nuty przesunięte o +k ramek: śpiew w ramce i porównujemy z nutą z ramki i-k
        if abs(k) >= n:
            continue
        if k >= 0:
            s, t, v = sung[k:], target[: n - k], valid[k:]
        else:
            s, t, v = sung[: n + k], target[-k:], valid[: n + k]
        has_t = ~np.isnan(t)
        m = v & has_t
        union = int((v | has_t).sum())
        if union == 0:
            continue
        err = np.abs((s[m] - t[m] + 6) % 12 - 6)
        # trafienia / (ramki z nutą LUB ze śpiewem): cisza w nucie i śpiew poza nutą obniżają wynik
        hits = int(np.sum(err <= MATCH_SEMITONES))
        scores[k] = (hits / union, int(m.sum()), hits)

    in_search = [k for k in scores if abs(k) <= k_search]
    if not in_search:
        return AlignmentReport(None, None, None, None, 0, tolerance_ms, "Nuty nie pokrywają się z nagraniem.")
    # najwyższa zgodność; przy remisie przesunięcie bliższe zera
    k = max(in_search, key=lambda i: (scores[i][0], -abs(i)))
    score, cnt, hits = scores[k]
    if cnt < MIN_FRAMES:
        return AlignmentReport(None, None, None, None, cnt, tolerance_ms,
                               "Za mało ramek śpiewu w trakcie nut; sprawdź, czy wokal pasuje do pliku UltraStar.")
    baseline = float(np.median([v[0] for v in scores.values()]))
    contrast = score / baseline if baseline > 0 else float("inf")
    offset_ms = k * HOP_S * 1000
    pct = 100 * score
    hit_pct = 100 * hits / cnt
    if contrast < MIN_CONTRAST or hit_pct < MIN_HIT_PCT:
        msg = (f"UWAGA: brak wyraźnego dopasowania melodii (trafienia {hit_pct:.0f}% / wymagane "
               f"{MIN_HIT_PCT:.0f}%, kontrast {contrast:.1f}x / wymagane {MIN_CONTRAST:.0f}x). "
               f"Nuty mogą być przesunięte o więcej niż {search_ms} ms albo wokal nie pasuje do pliku UltraStar.")
    elif abs(offset_ms) <= tolerance_ms:
        msg = (f"Wyrównanie OK: przesunięcie {offset_ms:+.0f} ms "
               f"(trafienia {hit_pct:.0f}%, kontrast {contrast:.1f}x, {cnt} ramek).")
    else:
        kier = "później" if offset_ms > 0 else "wcześniej"
        msg = (f"UWAGA: wokal jest {abs(offset_ms):.0f} ms {kier} niż nuty (tolerancja {tolerance_ms:.0f} ms, "
               f"kontrast {contrast:.1f}x). Popraw #GAP o {offset_ms:+.0f} ms.")
    return AlignmentReport(offset_ms, pct, contrast, hit_pct, cnt, tolerance_ms, msg)


def check_alignment_samples(song: Song, samples: np.ndarray, sr: int, tolerance_ms: float = 30.0,
                            engine: str = "crepe") -> AlignmentReport:
    from .pitch import track
    times, f0, conf = track(samples, sr, engine=engine)
    return check_alignment_pitch(song, times, f0, conf, tolerance_ms)


def check_alignment(song: Song, vocals_path: str | Path, tolerance_ms: float = 30.0,
                    engine: str = "crepe") -> AlignmentReport:
    samples, sr = sf.read(str(vocals_path), always_2d=False)
    return check_alignment_samples(song, np.asarray(samples), sr, tolerance_ms, engine)
