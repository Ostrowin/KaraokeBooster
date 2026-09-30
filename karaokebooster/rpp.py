"""Projekt REAPER (.rpp) piosenki z szablonu (Song Studio, docs/designs/song-studio.md).

Szablon to zwykły projekt REAPER z trzema ścieżkami o stałych nazwach (wielkość liter i polskie
znaki bez znaczenia): Podklad, ghost, wokal. Ich FX, routing i poziomy zostają. Generator:
  1. czyta szablon jako drzewo bloków `<...` / `>` (ITEM zawiera zagnieżdżone SOURCE, X itd.);
  2. usuwa wszystkie ITEM i znaczniki MARKER, wymusza TEMPO 120 (decyzja 0010);
  3. wstawia nowe elementy od pozycji 0: mp3 podkładu i ghosta jako odwołania do plików, a nuty
     MIDI osadzone w projekcie w formacie, który REAPER zapisuje przy imporcie
     (`<SOURCE MIDI` / `HASDATA 1 960 QN` / zdarzenia `E` i `<X` dla meta).
"""

from __future__ import annotations

import base64
import io
import unicodedata
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import mido

from .midi_export import PPQ, TEMPO_BPM

TRACKS = ("podklad", "ghost", "wokal")

AUDIO_SOURCES = {".mp3": "MP3", ".wav": "WAVE", ".flac": "FLAC", ".ogg": "VORBIS"}


class RppError(ValueError):
    """Szablonu nie da się użyć."""


@dataclass
class Block:
    """Blok `<NAZWA args` ... `>`. Dzieci to linie (str) albo bloki."""
    header: str
    children: list = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.header.split(None, 1)[0]


def parse(text: str) -> Block:
    stack: list[Block] = []
    root: Block | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("<"):
            block = Block(line[1:])
            if stack:
                stack[-1].children.append(block)
            elif root is None:
                root = block
            else:
                raise RppError("Plik .rpp ma więcej niż jeden blok główny.")
            stack.append(block)
        elif line == ">":
            if not stack:
                raise RppError("Nadmiarowe '>' w pliku .rpp.")
            stack.pop()
        elif stack:
            stack[-1].children.append(line)
        else:
            raise RppError(f"Tekst poza blokiem REAPER_PROJECT: {line[:40]!r}")
    if root is None or stack:
        raise RppError("Niekompletny plik .rpp (brak zamknięcia bloku).")
    if root.name != "REAPER_PROJECT":
        raise RppError("To nie jest projekt REAPER (brak REAPER_PROJECT).")
    return root


def dump(block: Block, depth: int = 0) -> str:
    pad = "  " * depth
    out = [f"{pad}<{block.header}"]
    for c in block.children:
        out.append(dump(c, depth + 1) if isinstance(c, Block) else f"{pad}  {c}")
    out.append(f"{pad}>")
    return "\n".join(out)


def _key(name: str) -> str:
    s = unicodedata.normalize("NFKD", name.replace("ł", "l").replace("Ł", "L"))
    return "".join(ch for ch in s if not unicodedata.combining(ch)).casefold().strip().strip('"')


def track_name(track: Block) -> str:
    for c in track.children:
        if isinstance(c, str) and c.startswith("NAME "):
            return c[5:].strip().strip('"')
    return ""


def _quote(s: str) -> str:
    """Łańcuch w stylu REAPER: w cudzysłowie, gdy ma spacje albo jest pusty."""
    if s and not any(ch.isspace() for ch in s) and s[0] not in "\"'`":
        return s
    for q in ('"', "'", "`"):
        if q not in s:
            return f"{q}{s}{q}"
    return '"' + s.replace('"', "'") + '"'


def _guid() -> str:
    return "{" + str(uuid.uuid4()).upper() + "}"


@dataclass(frozen=True)
class ItemSpec:
    path: str            # ścieżka zapisana w projekcie (względna do folderu projektu)
    length_s: float
    name: str


def _item(spec: ItemSpec, iid: int, source: Block) -> Block:
    return Block("ITEM", [
        "POSITION 0", "SNAPOFFS 0", f"LENGTH {spec.length_s:.6f}", "LOOP 0", "ALLTAKES 0",
        "FADEIN 1 0 0 1 0 0 0 1 0 0 1 0 0", "FADEOUT 1 0 0 1 0 0 0 1 0 0 1 0 0",
        "MUTE 0 0", "SEL 0", f"IGUID {_guid()}", f"IID {iid}", f"NAME {_quote(spec.name)}",
        "VOLPAN 1 0 1 -1", "SOFFS 0", "PLAYRATE 1 1 0 -1 0 0.0025", "CHANMODE 0",
        f"GUID {_guid()}", source,
    ])


def audio_item(spec: ItemSpec, iid: int) -> Block:
    kind = AUDIO_SOURCES.get(Path(spec.path).suffix.lower())
    if kind is None:
        raise RppError(f"Nieobsługiwany format audio: {spec.path}")
    return _item(spec, iid, Block(f"SOURCE {kind}", [f"FILE {_quote(spec.path)} 1"]))


def _b64_lines(data: bytes) -> list[str]:
    # REAPER dzieli dane co 40 bajtów i każdy kawałek koduje osobno
    return [base64.b64encode(data[i:i + 40]).decode("ascii") for i in range(0, len(data), 40)]


def midi_source(mid: mido.MidiFile) -> Block:
    if mid.ticks_per_beat != PPQ:
        raise RppError(f"MIDI ma PPQ {mid.ticks_per_beat}, oczekiwano {PPQ} (decyzja 0010).")
    # Zapis i ponowny odczyt: meta-teksty wracają jako bajty z pliku (zapisane w UTF-8,
    # odczytane jako latin-1), więc msg.bytes() daje dokładnie bajty, które zapisałby REAPER.
    buf = io.BytesIO()
    mid.save(file=buf)
    buf.seek(0)
    mid = mido.MidiFile(file=buf)
    children: list = ["HASDATA 1 960 QN", "CCINTERP 32", f"POOLEDEVTS {_guid()}"]
    pending = 0  # czas pominiętych zdarzeń (tempo, koniec ścieżki) przechodzi na następne
    for msg in mido.merge_tracks(mid.tracks):
        delta = pending + msg.time
        if msg.is_meta:
            if msg.type in ("set_tempo", "end_of_track", "time_signature"):
                pending = delta
                continue
            raw = bytes(msg.bytes())
            # REAPER zapisuje meta bez bajtu długości: FF typ dane
            data = raw[:2] + raw[2 + _varlen_size(raw[2:]):]
            text = data[2:].decode("utf-8", errors="replace")  # tylko opis; dane są w base64
            children.append(Block(f"X {delta} 0 0 0 {raw[1]} {_quote(text)}", _b64_lines(data)))
        else:
            children.append("E {} {}".format(delta, " ".join(f"{b:02x}" for b in msg.bytes())))
        pending = 0
    children += ["CCINTERP 32", "CHASE_CC_TAKEOFFS 1", f"GUID {_guid()}",
                 f"IGNTEMPO 0 {TEMPO_BPM} 4 4"]
    return Block("SOURCE MIDI", children)


def _varlen_size(b: bytes) -> int:
    n = 0
    for byte in b:
        n += 1
        if byte < 0x80:
            break
    return n


def midi_item(spec: ItemSpec, mid: mido.MidiFile, iid: int) -> Block:
    return _item(spec, iid, midi_source(mid))


def build(template_text: str, podklad: ItemSpec, ghost: ItemSpec, wokal: ItemSpec,
          mid: mido.MidiFile) -> tuple[str, list[str]]:
    """(tekst projektu, ostrzeżenia). RppError, gdy szablon nie ma którejś ścieżki."""
    root = parse(template_text)
    warnings: list[str] = []
    tracks: dict[str, Block] = {}
    kept = []
    for c in root.children:
        if isinstance(c, str) and c.startswith("MARKER "):
            continue
        if isinstance(c, str) and c.startswith("TEMPO "):
            parts = c.split()
            if len(parts) < 2 or parts[1] != str(TEMPO_BPM):
                warnings.append(f"Szablon miał '{c}'; ustawiono tempo {TEMPO_BPM} (decyzja 0010).")
                c = " ".join(["TEMPO", str(TEMPO_BPM)] + parts[2:]) if len(parts) > 2 \
                    else f"TEMPO {TEMPO_BPM} 4 4"
        if isinstance(c, Block) and c.name == "TRACK":
            c.children = [x for x in c.children if not (isinstance(x, Block) and x.name == "ITEM")]
            key = _key(track_name(c))
            if key in TRACKS and key not in tracks:
                tracks[key] = c
        kept.append(c)
    if not any(isinstance(c, str) and c.startswith("TEMPO ") for c in kept):
        kept.insert(0, f"TEMPO {TEMPO_BPM} 4 4")
    root.children = kept
    missing = [t for t in TRACKS if t not in tracks]
    if missing:
        raise RppError("Szablon nie ma ścieżki: " + ", ".join(f"'{m}'" for m in missing)
                       + " (potrzebne: Podklad, ghost, wokal).")
    tracks["podklad"].children.append(audio_item(podklad, 1))
    _set_mute(tracks["ghost"], True)  # karaoke: oryginalny wokal na start wyłączony (klawisz G w tekście)
    tracks["ghost"].children.append(audio_item(ghost, 2))
    tracks["wokal"].children.append(midi_item(wokal, mid, 3))
    return dump(root) + "\n", warnings


def _set_mute(track: Block, muted: bool) -> None:
    """MUTESOLO <mute> <solo> <...>: pierwsze pole to wyciszenie."""
    for i, c in enumerate(track.children):
        if isinstance(c, str) and c.startswith("MUTESOLO"):
            parts = c.split()
            parts[1:2] = ["1" if muted else "0"]
            track.children[i] = " ".join(parts + ["0"] * (4 - len(parts)))
            return
    track.children.insert(1, f"MUTESOLO {1 if muted else 0} 0 0")


def track_number(project_text: str, name: str) -> int | None:
    """Numer ścieżki (od 1, jak w REAPER i w OSC /track/N/...) o danej nazwie."""
    n = 0
    for c in parse(project_text).children:
        if isinstance(c, Block) and c.name == "TRACK":
            n += 1
            if _key(track_name(c)) == _key(name):
                return n
    return None


def strip_items(template_text: str) -> str:
    """Szablon z istniejącego projektu: bez elementów i znaczników."""
    root = parse(template_text)
    root.children = [c for c in root.children if not (isinstance(c, str) and c.startswith("MARKER "))]
    for c in root.children:
        if isinstance(c, Block) and c.name == "TRACK":
            c.children = [x for x in c.children if not (isinstance(x, Block) and x.name == "ITEM")]
    return dump(root) + "\n"
