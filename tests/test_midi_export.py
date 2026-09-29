import mido
import pytest

from karaokebooster.midi_export import (
    BYPASS_CC,
    PPQ,
    seconds_to_ticks,
    song_to_midi,
    target_notes,
)
from karaokebooster.ultrastar import parse

# BPM 300 -> beat = 0.05 s; GAP 1000 -> beat 0 = 1.0 s
SONG = """#TITLE:T
#ARTIST:A
#BPM:300
#GAP:1000
: 0 4 5 Za
: 4 4 7 żó
- 10
F 12 4 0 hej
* 20 8 -12 łć
E
"""


def absolute(mid):
    t, out = 0, []
    for msg in mid.tracks[0]:
        t += msg.time
        out.append((t, msg))
    return out


def notes_on(mid):
    return [(t, m.note) for t, m in absolute(mid) if m.type == "note_on"]


def test_seconds_to_ticks_at_120bpm_ppq960():
    assert seconds_to_ticks(1.0) == 1920
    assert seconds_to_ticks(0.05) == 96


def test_header_tempo_and_ppq():
    mid = song_to_midi(parse(SONG))
    assert mid.ticks_per_beat == PPQ == 960
    tempos = [m for m in mid.tracks[0] if m.type == "set_tempo"]
    assert len(tempos) == 1 and mido.tempo2bpm(tempos[0].tempo) == pytest.approx(120)


def test_note_positions_from_seconds():
    mid = song_to_midi(parse(SONG))
    assert notes_on(mid) == [(1920, 65), (1920 + 384, 67), (1920 + 1920, 48)]
    offs = [(t, m.note) for t, m in absolute(mid) if m.type == "note_off"]
    assert offs[0] == (1920 + 384, 65)


def test_freestyle_has_no_midi_note_but_has_lyric():
    mid = song_to_midi(parse(SONG))
    assert 60 not in [n for _, n in notes_on(mid)]
    lyrics = [(t, m.text) for t, m in absolute(mid) if m.type == "lyrics"]
    assert (seconds_to_ticks(1.6), "hej") in lyrics
    assert [x for _, x in lyrics] == ["Za", "żó", "hej", "łć"]


def test_bypass_cc_sequence():
    mid = song_to_midi(parse(SONG))
    cc = [(t, m.value) for t, m in absolute(mid) if m.type == "control_change" and m.control == BYPASS_CC]
    # start: bypass; nuta 1 i 2 stykają się -> bez bypassu pomiędzy; przerwa i F -> bypass
    assert cc == [(0, 127), (1920, 0), (2304, 0), (2688, 127), (3840, 0), (4608, 127)]


def test_same_tick_order_off_before_on():
    text = "#BPM:300\n: 0 4 0 a\n: 4 4 0 b\n"
    events = absolute(song_to_midi(parse(text)))
    at = [m.type for t, m in events if t == seconds_to_ticks(0.2) and m.type.startswith("note")]
    assert at == ["note_off", "note_on"]


def test_octave_shift():
    mid = song_to_midi(parse(SONG), octave=-1)
    assert [n for _, n in notes_on(mid)] == [53, 55, 36]


def test_octave_out_of_range_raises():
    with pytest.raises(ValueError, match="zakres MIDI"):
        target_notes(parse("#BPM:100\n: 0 1 60 a\n"), octave=1)


def test_merge_short_notes_into_previous():
    text = "#BPM:300\n: 0 4 0 a\n: 4 1 5 ~\n: 5 4 2 b\n"
    notes = target_notes(parse(text), merge_below_ms=60)
    assert [(round(n.start_s, 3), round(n.end_s, 3), n.pitch) for n in notes] == [
        (0.0, 0.25, 60), (0.25, 0.45, 62)]


def test_merge_does_not_glue_across_gap():
    text = "#BPM:300\n: 0 4 0 a\n: 8 1 5 x\n"
    assert len(target_notes(parse(text), merge_below_ms=60)) == 2


def test_roundtrip_file(tmp_path):
    out = tmp_path / "s.mid"
    song_to_midi(parse(SONG)).save(str(out))
    loaded = mido.MidiFile(str(out), charset="utf-8")
    assert notes_on(loaded) == notes_on(song_to_midi(parse(SONG)))


# --- automatyczna oktawa -------------------------------------------------

from karaokebooster.midi_export import auto_octave  # noqa: E402


@pytest.mark.parametrize("pitch_in_file, expected", [
    (-5, 0),    # MIDI 55 = G3: już w zakresie
    (0, -0),    # C4 (60): bliżej zostać niż schodzić o oktawę
    (7, -1),    # G4 (67) -> G3
    (53, -5),   # jak z ultrasongs: MIDI 113 -> 53
    (-24, 2),   # C2 (36) -> C4
])
def test_auto_octave(pitch_in_file, expected):
    song = parse(f"#BPM:300\n: 0 4 {pitch_in_file} a\n: 4 4 {pitch_in_file} b\n")
    assert auto_octave(song) == expected


def test_auto_octave_ignores_freestyle_and_custom_center():
    song = parse("#BPM:300\n: 0 4 12 a\nF 4 4 -40 b\n")  # C5 = 72
    assert auto_octave(song) == -1
    assert auto_octave(song, voice_center=72) == 0


def test_auto_octave_no_pitched_notes():
    assert auto_octave(parse("#BPM:300\nF 0 4 0 a\n")) == 0
