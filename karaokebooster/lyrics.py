"""Logika podglądu tekstu: zegar zsynchronizowany z REAPER i widok w danej chwili.

REAPER (Default.ReaperOSC) wysyła m.in.:
    /time <sekundy>   pozycja odtwarzania (często w trakcie grania)
    /play <0|1>       1 = gra
    /pause <0|1>      1 = pauza
    /stop <0|1>       1 = stop

OSC przychodzi nieregularnie, więc zegar liczy czas lokalnie od ostatniej znanej
pozycji i koryguje się każdym /time. Gdy REAPER milknie w trakcie grania dłużej
niż STALE_S, zegar staje (nie ucieka z tekstem do przodu).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from .ultrastar import Note, Song

STALE_S = 1.0


class TransportClock:
    def __init__(self, now: Callable[[], float] = time.monotonic, offset_s: float = 0.0):
        self._now = now
        self.offset_s = offset_s        # np. opóźnienie wyjścia audio
        self._anchor_pos = 0.0
        self._anchor_t = now()
        self._last_msg_t = self._anchor_t
        self.playing = False

    def _position_raw(self, t: float) -> float:
        if not self.playing:
            return self._anchor_pos
        return self._anchor_pos + min(t - self._anchor_t, STALE_S + (self._last_msg_t - self._anchor_t))

    def _reanchor(self) -> None:
        t = self._now()
        self._anchor_pos = self._position_raw(t)
        self._anchor_t = t

    def on_time(self, seconds: float) -> None:
        t = self._now()
        self._anchor_pos, self._anchor_t, self._last_msg_t = float(seconds), t, t

    def on_play(self, value: float) -> None:
        if value >= 0.5 and not self.playing:
            self._reanchor()
            self.playing = True
        self._last_msg_t = self._now()

    def on_pause_or_stop(self, value: float) -> None:
        if value >= 0.5 and self.playing:
            self._reanchor()
            self.playing = False
        self._last_msg_t = self._now()

    def position(self) -> float:
        return self._position_raw(self._now()) - self.offset_s


@dataclass(frozen=True)
class Syllable:
    text: str
    state: str   # "past" | "current" | "future"


@dataclass(frozen=True)
class LyricsView:
    line: list[Syllable]
    next_line: str
    countdown_s: float | None   # ile do pierwszej nuty frazy, gdy jeszcze nie zaczęta


def phrases(song: Song) -> list[list[Note]]:
    lines: dict[int, list[Note]] = {}
    for n in song.notes:
        lines.setdefault(n.phrase, []).append(n)
    return [lines[k] for k in sorted(lines)]


def display(syllable: str) -> str:
    """Tekst sylaby na ekran: "~" w UltraStar oznacza przedłużenie poprzedniej sylaby, nie literę."""
    return syllable.replace("~", "")


def line_texts(lines: list[list[Note]]) -> list[str]:
    return ["".join(display(n.syllable) for n in line).strip() for line in lines]


def fit_font_size(texts: list[str], measure: Callable[[int, str], float], width: float,
                  max_size: int, min_size: int = 12) -> int:
    """Największy rozmiar czcionki (<= max_size), przy którym najdłuższa linia mieści się w `width`.
    `measure(rozmiar, tekst)` zwraca szerokość w pikselach. Jeden rozmiar dla całej piosenki,
    żeby tekst nie skakał między liniami."""
    longest = max(texts, key=len, default="")
    if not longest:
        return max_size
    size = max_size
    while size > min_size and measure(size, longest) > width:
        size -= 1
    # najdłuższa znakowo nie musi być najszersza: sprawdź wszystkie przy znalezionym rozmiarze
    while size > min_size and max(measure(size, t) for t in texts) > width:
        size -= 1
    return size


def view_at(lines: list[list[Note]], t: float) -> LyricsView:
    if not lines:
        return LyricsView([], "", None)
    idx = len(lines) - 1
    for i, line in enumerate(lines):
        if t < line[-1].end_s:
            idx = i
            break
    line = lines[idx]
    parts = []
    for n in line:
        if t >= n.end_s:
            state = "past"
        elif t >= n.start_s:
            state = "current"
        else:
            state = "future"
        parts.append(Syllable(display(n.syllable), state))
    next_line = "".join(display(n.syllable) for n in lines[idx + 1]) if idx + 1 < len(lines) else ""
    first = line[0].start_s
    countdown = first - t if t < first else None
    return LyricsView(parts, next_line.strip(), countdown)
