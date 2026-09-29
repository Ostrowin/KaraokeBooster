"""UltraStar -> MIDI dla korektora (decyzja 0010).

MIDI ma stałe tempo 120 BPM i PPQ 960, a pozycje liczymy z sekund:
    tick = round(sekundy * 120/60 * 960) = round(sekundy * 1920)
Dzięki temu REAPER (import bez mapy tempa) stawia nuty dokładnie tam, gdzie
wskazuje UltraStar, niezależnie od BPM piosenki.

Na ścieżce:
- nuty tylko dla typów z wysokością (':' i '*'); F/R/G bez nut;
- tekst (lyrics) dla każdej sylaby, także F/R/G;
- CC BYPASS_CC: 127 = korekcja wyłączona (przerwy, F/R/G), 0 = włączona w trakcie nuty.
"""

from __future__ import annotations

from dataclasses import dataclass

import mido

from .ultrastar import Note, Song

TEMPO_BPM = 120
PPQ = 960
TICKS_PER_SECOND = TEMPO_BPM / 60 * PPQ  # 1920
BYPASS_CC = 85
BYPASS_ON = 127
BYPASS_OFF = 0
VELOCITY = 100


def seconds_to_ticks(seconds: float) -> int:
    return round(seconds * TICKS_PER_SECOND)


# Środek wygodnego zakresu męskiego głosu: G3 (MIDI 55). Zakres ok. G2-G4.
DEFAULT_VOICE_CENTER = 55


def auto_octave(song: Song, voice_center: int = DEFAULT_VOICE_CENTER) -> int:
    """Przesunięcie w oktawach, które stawia medianę nut piosenki najbliżej środka zakresu głosu.

    Naprawia pliki z inną konwencją oktaw (np. ultrasongs zapisuje o 3 oktawy za wysoko).
    Nie zmienia melodii, tylko przenosi ją w całości w górę lub w dół.
    """
    pitches = sorted(n.pitch_midi for n in song.notes if n.is_pitched)
    if not pitches:
        return 0
    median = pitches[len(pitches) // 2]
    return round((voice_center - median) / 12)


@dataclass(frozen=True)
class TargetNote:
    start_s: float
    end_s: float
    pitch: int


def target_notes(song: Song, octave: int = 0, merge_below_ms: float = 0.0) -> list[TargetNote]:
    """Nuty docelowe dla korektora: tylko z wysokością, przesunięte o oktawy, scalone."""
    shift = 12 * octave
    result: list[TargetNote] = []
    for n in sorted((n for n in song.notes if n.is_pitched), key=lambda n: n.start_s):
        pitch = n.pitch_midi + shift
        if not 0 <= pitch <= 127:
            raise ValueError(
                f"Nuta '{n.syllable}' ({n.start_s:.2f} s) po przesunięciu o {octave} okt. "
                f"wychodzi poza zakres MIDI: {pitch}")
        short = n.dur_s * 1000 < merge_below_ms
        if short and result and n.start_s - result[-1].end_s <= 0.010:
            prev = result[-1]
            result[-1] = TargetNote(prev.start_s, max(prev.end_s, n.end_s), prev.pitch)
            continue
        result.append(TargetNote(n.start_s, n.end_s, pitch))
    return result


def song_to_midi(song: Song, octave: int = 0, merge_below_ms: float = 0.0) -> mido.MidiFile:
    notes = target_notes(song, octave, merge_below_ms)

    # (tick, priorytet, wiadomość); przy tym samym ticku: note_off, CC, lyrics, note_on
    events: list[tuple[int, int, mido.Message | mido.MetaMessage]] = [
        (0, 1, mido.Message("control_change", control=BYPASS_CC, value=BYPASS_ON)),
    ]
    for i, t in enumerate(notes):
        on, off = seconds_to_ticks(t.start_s), seconds_to_ticks(t.end_s)
        if off <= on:
            off = on + 1
        events.append((on, 1, mido.Message("control_change", control=BYPASS_CC, value=BYPASS_OFF)))
        events.append((on, 3, mido.Message("note_on", note=t.pitch, velocity=VELOCITY)))
        events.append((off, 0, mido.Message("note_off", note=t.pitch, velocity=0)))
        nxt = notes[i + 1] if i + 1 < len(notes) else None
        if nxt is None or seconds_to_ticks(nxt.start_s) > off:
            events.append((off, 1, mido.Message("control_change", control=BYPASS_CC, value=BYPASS_ON)))
    for n in song.notes:
        if n.syllable:
            events.append((seconds_to_ticks(n.start_s), 2, mido.MetaMessage("lyrics", text=n.syllable)))

    events.sort(key=lambda e: (e[0], e[1]))

    track = mido.MidiTrack()
    track.append(mido.MetaMessage("track_name", name=f"{song.artist} - {song.title}".strip(" -"), time=0))
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(TEMPO_BPM), time=0))
    last = 0
    for tick, _, msg in events:
        track.append(msg.copy(time=tick - last))
        last = tick
    track.append(mido.MetaMessage("end_of_track", time=0))

    mid = mido.MidiFile(type=0, ticks_per_beat=PPQ, charset="utf-8")
    mid.tracks.append(track)
    return mid


def note_count(song: Song) -> int:
    return sum(1 for n in song.notes if n.is_pitched)


__all__ = ["BYPASS_CC", "PPQ", "TEMPO_BPM", "TargetNote", "Note", "seconds_to_ticks",
           "song_to_midi", "target_notes", "note_count"]
