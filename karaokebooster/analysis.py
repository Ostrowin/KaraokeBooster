"""Analiza suchych nagrań śpiewaka względem nut UltraStar (krok 9 w docs/design.md).

Metryki:
  (a) % udźwięcznionych ramek (pewność >= 0.5, w trakcie nuty z wysokością) z błędem > 3 półtony (mod 12)
  (b) mediana przesunięcia RĘCZNIE oznaczonych początków sylab względem startów nut [ms]
  (c) 80. percentyl |błędu| (mod 12) [półtony]
  skuteczność detektora: % znaczników, przy których detektor wskazał początek w ±50 ms

Reguły (docs/design.md, "Reguły parametrów"):
  duże błędy = (a) > 30% lub (b) > 120 ms  -> domyślny tryb etapu 2: łagodny + ghost
  D = 80. percentyl ograniczony do 3..7 półtonów
  W = max(150 ms, 1.5 * mediana spóźnienia)
  skuteczność < 80% -> zmiana celu wg zegara z oknem W
"""

from __future__ import annotations

import csv
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .alignment import detect_onsets
from .pitch import hz_to_midi
from .ultrastar import Song

CONF_MIN = 0.5
ERR_LIMIT = 3.0
MATCH_WINDOW_S = 0.5
DETECT_TOL_S = 0.050


class AnalysisError(ValueError):
    pass


@dataclass(frozen=True)
class TakeReport:
    voiced_frames: int
    frames_off_pct: float | None       # (a)
    onset_lag_median_ms: float | None  # (b)
    error_p80: float | None            # (c)
    detector_hit_pct: float | None
    markers: int
    large_errors: bool | None
    default_mode: str | None
    D: float | None
    W_ms: float | None
    target_switch: str | None

    def to_dict(self) -> dict:
        return asdict(self)


def fold12(err: np.ndarray) -> np.ndarray:
    """Błąd w półtonach sprowadzony do [-6, 6) (oktawa obok nie jest błędem)."""
    return (err + 6) % 12 - 6


def target_at(song: Song, times: np.ndarray, octave: int = 0) -> np.ndarray:
    target = np.full(times.shape, np.nan)
    for n in song.notes:
        if n.is_pitched:
            mask = (times >= n.start_s) & (times < n.end_s)
            target[mask] = n.pitch_midi + 12 * octave
    return target


def pitch_errors(song: Song, times: np.ndarray, f0: np.ndarray, conf: np.ndarray,
                 octave: int = 0) -> np.ndarray:
    sung = hz_to_midi(f0)
    target = target_at(song, times, octave)
    ok = (conf >= CONF_MIN) & ~np.isnan(sung) & ~np.isnan(target)
    return fold12(sung[ok] - target[ok])


def read_markers(path: str | Path) -> np.ndarray:
    """Znaczniki: CSV z REAPER (kolumna Start/Position), etykiety Audacity (TAB) albo jedna liczba na linię."""
    text = Path(path).read_text(encoding="utf-8-sig")
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        raise AnalysisError(f"{path}: plik znaczników jest pusty.")
    if "\t" in lines[0]:
        return np.array(sorted(_seconds(l.split("\t")[0]) for l in lines))
    rows = list(csv.reader(lines))
    header = [h.strip().lower() for h in rows[0]]
    col = next((header.index(k) for k in ("start", "position", "time") if k in header), None)
    if col is not None:
        return np.array(sorted(_seconds(r[col]) for r in rows[1:] if len(r) > col and r[col].strip()))
    return np.array(sorted(_seconds(r[0]) for r in rows))


def _seconds(value: str) -> float:
    v = value.strip()
    m = re.fullmatch(r"(?:(\d+):)?(\d+):(\d+(?:[.,]\d+)?)", v)
    try:
        if m:
            h = int(m.group(1) or 0)
            return h * 3600 + int(m.group(2)) * 60 + float(m.group(3).replace(",", "."))
        return float(v.replace(",", "."))
    except ValueError:
        raise AnalysisError(f"Nie rozumiem czasu znacznika: {value!r}") from None


def onset_lags(song: Song, markers: np.ndarray) -> np.ndarray:
    starts = np.array([n.start_s for n in song.notes])
    lags = []
    for m in markers:
        d = m - starts
        best = d[np.argmin(np.abs(d))]
        if abs(best) <= MATCH_WINDOW_S:
            lags.append(best)
    return np.array(lags)


def detector_hit_rate(markers: np.ndarray, detected: np.ndarray, tol_s: float = DETECT_TOL_S) -> float:
    if len(markers) == 0:
        return float("nan")
    if len(detected) == 0:
        return 0.0
    hits = sum(1 for m in markers if np.min(np.abs(detected - m)) <= tol_s)
    return 100.0 * hits / len(markers)


def analyze(song: Song, times: np.ndarray, f0: np.ndarray, conf: np.ndarray,
            samples: np.ndarray | None = None, sr: int | None = None,
            markers: np.ndarray | None = None, octave: int = 0) -> TakeReport:
    err = np.abs(pitch_errors(song, times, f0, conf, octave))
    a = float(100.0 * np.mean(err > ERR_LIMIT)) if len(err) else None
    c = float(np.percentile(err, 80)) if len(err) else None

    b = hit = None
    n_markers = 0
    if markers is not None:
        n_markers = len(markers)
        lags = onset_lags(song, markers)
        b = float(np.median(lags) * 1000) if len(lags) else None
        if samples is not None and sr:
            hit = detector_hit_rate(markers, detect_onsets(samples, sr))

    large = None if a is None else (a > 30.0 or (b is not None and b > 120.0))
    D = None if c is None else float(np.clip(c, 3.0, 7.0))
    W = None if b is None else float(max(150.0, 1.5 * b))
    switch = None if hit is None else ("sylaba" if hit >= 80.0 else "zegar + okno W")
    return TakeReport(
        voiced_frames=int(len(err)), frames_off_pct=a, onset_lag_median_ms=b, error_p80=c,
        detector_hit_pct=hit, markers=n_markers, large_errors=large,
        default_mode=None if large is None else ("łagodny + ghost" if large else "twardy"),
        D=D, W_ms=W, target_switch=switch)


def format_report(r: TakeReport, name: str = "") -> str:
    def f(v, fmt, unit=""):
        return "brak danych" if v is None else f"{v:{fmt}}{unit}"
    lines = [
        f"== {name} ==" if name else "== Analiza ==",
        f"ramki z głosem w nutach:        {r.voiced_frames}",
        f"(a) ramki > 3 półtony od nuty:  {f(r.frames_off_pct, '.1f', ' %')}",
        f"(b) mediana spóźnienia sylab:   {f(r.onset_lag_median_ms, '+.0f', ' ms')}"
        + ("" if r.markers else "  (brak pliku znaczników)"),
        f"(c) 80. percentyl błędu:        {f(r.error_p80, '.2f', ' półtonu')}",
        f"skuteczność detektora (±50 ms): {f(r.detector_hit_pct, '.0f', ' %')}",
        "-- wnioski --",
        f"duże błędy śpiewaka:            {f(r.large_errors, '')}",
        f"domyślny tryb etapu 2:          {f(r.default_mode, '')}",
        f"D (siła korekcji 100% do):      {f(r.D, '.1f', ' półtonu')}",
        f"W (okno zmiany celu):           {f(r.W_ms, '.0f', ' ms')}",
        f"zmiana nuty docelowej wg:       {f(r.target_switch, '')}",
    ]
    return "\n".join(lines)
