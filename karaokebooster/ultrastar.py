"""Wspólny parser plików UltraStar (.txt). Jedyne miejsce, które liczy czas nut.

Decyzje: docs/decisions/0012 (zakres formatu), 0013 (kodowanie).

Oś czasu:

    beat (z pliku) ──(#RELATIVE: + offset linii)──> beat bezwzględny
    beat bezwzględny ──> sekundy = GAP/1000 + beat · 60 / (BPM · 4)

    UltraStar podaje BPM jako ćwierć-beaty, stąd dzielnik 4.
    Wysokość: pitch_midi = pitch_z_pliku + 60 (0 w pliku = C4, MIDI 60).
"""

from __future__ import annotations

import codecs
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path

NOTE_TYPES = {":": "normal", "*": "golden", "F": "freestyle", "R": "rap", "G": "rap_golden"}
PITCHED_TYPES = {"normal", "golden"}

SUPPORTED_TAGS = {"TITLE", "ARTIST", "BPM", "GAP", "MP3", "AUDIO", "RELATIVE", "START", "END",
                  "VERSION", "ENCODING"}
IGNORED_TAGS = {"VIDEO", "VIDEOGAP"}

_ENCODING_TAG = re.compile(rb"^#ENCODING:([^\r\n]*)", re.MULTILINE | re.IGNORECASE)


class UltraStarError(ValueError):
    """Pliku nie da się poprawnie wczytać."""


class UltraStarWarning(UserWarning):
    """Coś pominięto albo zgadnięto; plik nadal jest używalny."""


@dataclass(frozen=True)
class Note:
    type: str          # normal | golden | freestyle | rap | rap_golden
    beat: int          # beat bezwzględny (po #RELATIVE)
    length: int        # w beatach
    pitch_midi: int
    syllable: str
    phrase: int        # numer frazy, od 0
    start_s: float
    dur_s: float

    @property
    def end_s(self) -> float:
        return self.start_s + self.dur_s

    @property
    def is_pitched(self) -> bool:
        return self.type in PITCHED_TYPES


@dataclass
class Song:
    title: str
    artist: str
    bpm: float
    gap_ms: float
    audio: str | None
    relative: bool
    start_s: float | None
    end_ms: float | None
    encoding: str
    notes: list[Note]
    phrase_breaks_s: list[float] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def beat_to_seconds(self, beat: float) -> float:
        return beat_to_seconds(beat, self.bpm, self.gap_ms)


def beat_to_seconds(beat: float, bpm: float, gap_ms: float) -> float:
    return gap_ms / 1000.0 + beat * 60.0 / (bpm * 4.0)


def load(path: str | Path) -> Song:
    raw = Path(path).read_bytes()
    text, encoding, enc_warnings = _decode(raw)
    return parse(text, encoding=encoding, source=str(path), extra_warnings=enc_warnings)


def _decode(raw: bytes) -> tuple[str, str, list[str]]:
    if raw.startswith(codecs.BOM_UTF8):
        return raw[len(codecs.BOM_UTF8):].decode("utf-8"), "utf-8-sig", []

    tag = _ENCODING_TAG.search(raw)
    if tag:
        declared = tag.group(1).decode("ascii", errors="replace").strip()
        try:
            return raw.decode(_normalize_encoding(declared)), _normalize_encoding(declared), []
        except (LookupError, UnicodeDecodeError):
            pass  # zły tag: próbujemy dalej jak dla pliku bez tagu

    try:
        return raw.decode("utf-8"), "utf-8", []
    except UnicodeDecodeError:
        msg = "Plik nie jest w UTF-8 i nie ma poprawnego #ENCODING; zgaduję CP1250."
        return raw.decode("cp1250", errors="replace"), "cp1250", [msg]


def _normalize_encoding(name: str) -> str:
    n = name.strip().lower().replace("_", "-")
    aliases = {"cp1250": "cp1250", "windows-1250": "cp1250", "win1250": "cp1250",
               "cp1252": "cp1252", "windows-1252": "cp1252", "utf8": "utf-8", "utf-8": "utf-8",
               "latin1": "latin-1", "iso-8859-2": "iso-8859-2"}
    return codecs.lookup(aliases.get(n, n)).name


def _number(value: str, tag: str, lineno: int) -> float:
    try:
        return float(value.strip().replace(",", "."))
    except ValueError:
        raise UltraStarError(f"Linia {lineno}: #{tag} nie jest liczbą: {value!r}") from None


def parse(text: str, *, encoding: str = "utf-8", source: str = "<string>",
          extra_warnings: list[str] | None = None) -> Song:
    warns: list[str] = list(extra_warnings or [])
    headers: dict[str, str] = {}
    body: list[tuple[int, str]] = []

    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.rstrip("\r\n")
        if not stripped.strip():
            continue
        if stripped.startswith("#") and not body:
            key, sep, value = stripped[1:].partition(":")
            if not sep:
                raise UltraStarError(f"Linia {lineno}: nagłówek bez dwukropka: {stripped!r}")
            key = key.strip().upper()
            if key in IGNORED_TAGS:
                warns.append(f"Pominięto #{key} (nieobsługiwane w etapie 1).")
            elif key not in SUPPORTED_TAGS:
                warns.append(f"Nieznany tag #{key} pominięty.")
            headers[key] = value.strip()
            continue
        body.append((lineno, stripped))

    for key in ("BPM",):
        if key not in headers:
            raise UltraStarError(f"{source}: brak wymaganego nagłówka #{key}.")
    bpm = _number(headers["BPM"], "BPM", 0)
    if bpm <= 0:
        raise UltraStarError(f"{source}: #BPM musi być dodatnie.")
    gap_ms = _number(headers["GAP"], "GAP", 0) if "GAP" in headers else 0.0
    relative = headers.get("RELATIVE", "").strip().lower() in {"yes", "true", "1"}
    audio = headers.get("AUDIO") or headers.get("MP3") or None
    start_s = _number(headers["START"], "START", 0) if "START" in headers else None
    end_ms = _number(headers["END"], "END", 0) if "END" in headers else None

    notes: list[Note] = []
    phrase_breaks: list[float] = []
    phrase = 0
    offset = 0
    ended = False

    for lineno, line in body:
        if ended:
            break
        head = line[0]
        if head in ("P",) and line[1:2].strip().isdigit():
            raise UltraStarError(f"Linia {lineno}: pliki duetów (P1/P2) nie są obsługiwane.")
        if head == "#":
            raise UltraStarError(f"Linia {lineno}: nagłówek po rozpoczęciu nut: {line!r}")
        if head == "E":
            ended = True
            continue
        if head == "-":
            parts = line[1:].split()
            try:
                values = [int(p) for p in parts]
            except ValueError:
                raise UltraStarError(f"Linia {lineno}: niepoprawny podział frazy: {line!r}") from None
            if not values or len(values) > 2:
                raise UltraStarError(f"Linia {lineno}: niepoprawny podział frazy: {line!r}")
            phrase_breaks.append(beat_to_seconds(offset + values[0], bpm, gap_ms))
            if relative:
                offset += values[-1]
            phrase += 1
            continue
        if head in NOTE_TYPES:
            m = re.match(r"^.\s+(-?\d+)\s+(\d+)\s+(-?\d+)(?: (.*))?$", line)
            if not m:
                raise UltraStarError(f"Linia {lineno}: niepoprawna nuta: {line!r}")
            beat = int(m.group(1)) + (offset if relative else 0)
            length = int(m.group(2))
            notes.append(Note(
                type=NOTE_TYPES[head],
                beat=beat,
                length=length,
                pitch_midi=int(m.group(3)) + 60,
                syllable=m.group(4) or "",
                phrase=phrase,
                start_s=beat_to_seconds(beat, bpm, gap_ms),
                dur_s=length * 60.0 / (bpm * 4.0),
            ))
            continue
        raise UltraStarError(f"Linia {lineno}: nieznany typ linii: {line!r}")

    if not notes:
        raise UltraStarError(f"{source}: plik nie zawiera żadnych nut.")

    for w in warns:
        warnings.warn(f"{source}: {w}", UltraStarWarning, stacklevel=2)

    return Song(
        title=headers.get("TITLE", ""),
        artist=headers.get("ARTIST", ""),
        bpm=bpm,
        gap_ms=gap_ms,
        audio=audio,
        relative=relative,
        start_s=start_s,
        end_ms=end_ms,
        encoding=encoding,
        notes=notes,
        phrase_breaks_s=phrase_breaks,
        warnings=warns,
    )
