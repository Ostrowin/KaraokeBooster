import codecs
from pathlib import Path

import pytest

from karaokebooster.ultrastar import (
    UltraStarError,
    UltraStarWarning,
    beat_to_seconds,
    load,
    parse,
)

FIXTURES = Path(__file__).parent / "fixtures"

POLISH = "#TITLE:Zażółć\n#BPM:300\n#GAP:0\n: 0 4 0 gęślą\n: 4 4 2 jaźń\nE\n"


def write(tmp_path, data: bytes, name="song.txt"):
    p = tmp_path / name
    p.write_bytes(data)
    return p


# --- czas ---------------------------------------------------------------

def test_beat_to_seconds_formula():
    # BPM 300 -> beat = 60/(300*4) = 0.05 s
    assert beat_to_seconds(0, 300, 1000) == pytest.approx(1.0)
    assert beat_to_seconds(20, 300, 1000) == pytest.approx(2.0)


def test_basic_fixture_times_and_pitches():
    song = load(FIXTURES / "basic.txt")
    first = song.notes[0]
    assert first.start_s == pytest.approx(1.0)
    assert first.dur_s == pytest.approx(0.2)
    assert first.pitch_midi == 65
    assert song.notes[2].type == "golden"
    assert song.notes[-1].pitch_midi == 48  # -12 -> oktawa niżej od C4
    assert song.notes[-1].start_s == pytest.approx(1.0 + 32 * 0.05)


def test_note_types_and_pitched_flag():
    song = load(FIXTURES / "basic.txt")
    types = [n.type for n in song.notes]
    assert types == ["normal", "normal", "golden", "freestyle", "rap", "rap_golden", "normal"]
    assert [n.is_pitched for n in song.notes] == [True, True, True, False, False, False, True]


def test_phrases_and_end_marker():
    song = load(FIXTURES / "basic.txt")
    assert [n.phrase for n in song.notes] == [0, 0, 0, 1, 1, 1, 1]
    assert song.phrase_breaks_s == [pytest.approx(2.0)]
    assert all(n.syllable != "po_końcu" for n in song.notes)  # nic po E


def test_headers():
    song = load(FIXTURES / "basic.txt")
    assert song.title == "Testowa piosenka"
    assert song.audio == "song.mp3"
    assert song.bpm == 300
    assert song.gap_ms == 1000


def test_audio_tag_wins_over_mp3():
    song = parse("#MP3:old.mp3\n#AUDIO:new.ogg\n#BPM:100\n: 0 1 0 a\n")
    assert song.audio == "new.ogg"


def test_decimal_comma_bpm_and_gap():
    song = parse("#BPM:150,5\n#GAP:250,5\n: 0 1 0 a\n")
    assert song.bpm == 150.5
    assert song.gap_ms == 250.5


def test_start_end_headers():
    song = parse("#BPM:100\n#START:12,5\n#END:90000\n: 0 1 0 a\n")
    assert song.start_s == 12.5
    assert song.end_ms == 90000


def test_relative_mode_offsets_after_phrase_break():
    text = "#BPM:300\n#GAP:0\n#RELATIVE:yes\n: 0 4 0 a\n- 6 10\n: 0 4 0 b\n- 8\n: 2 4 0 c\n"
    song = parse(text)
    assert [n.beat for n in song.notes] == [0, 10, 20]
    assert song.notes[1].start_s == pytest.approx(0.5)
    assert song.phrase_breaks_s == [pytest.approx(0.3), pytest.approx(0.9)]


def test_syllable_keeps_leading_space():
    song = parse("#BPM:100\n: 0 1 0 Hej\n: 1 1 0  ho\n")
    assert song.notes[1].syllable == " ho"


# --- błędy --------------------------------------------------------------

@pytest.mark.parametrize("text, fragment", [
    ("#BPM:100\nP1\n: 0 1 0 a\n", "duetów"),
    ("#BPM:100\n: 0 x 0 a\n", "Linia 2"),
    ("#BPM:100\nX 0 1 0 a\n", "nieznany typ"),
    ("#BPM:100\n- a\n", "podział frazy"),
    ("#TITLE:x\n: 0 1 0 a\n", "#BPM"),
    ("#BPM:0\n: 0 1 0 a\n", "dodatnie"),
    ("#BPM:abc\n: 0 1 0 a\n", "nie jest liczbą"),
    ("#BPM:100\n", "żadnych nut"),
    ("#BPM:100\n: 0 1 0 a\n#GAP:10\n", "po rozpoczęciu"),
])
def test_errors(text, fragment):
    with pytest.raises(UltraStarError, match=fragment):
        parse(text)


def test_ignored_and_unknown_tags_warn():
    with pytest.warns(UltraStarWarning) as rec:
        song = parse("#BPM:100\n#VIDEO:v.mp4\n#VIDEOGAP:1\n#FOO:bar\n: 0 1 0 a\n")
    msgs = " ".join(str(w.message) for w in rec)
    assert "#VIDEO" in msgs and "#FOO" in msgs
    assert len(song.warnings) == 3


# --- kodowanie (decyzja 0013) -------------------------------------------

def test_utf8(tmp_path):
    song = load(write(tmp_path, POLISH.encode("utf-8")))
    assert song.encoding == "utf-8"
    assert song.notes[0].syllable == "gęślą"


def test_utf8_bom(tmp_path):
    song = load(write(tmp_path, codecs.BOM_UTF8 + POLISH.encode("utf-8")))
    assert song.encoding == "utf-8-sig"
    assert song.title == "Zażółć"


def test_cp1250_with_encoding_tag(tmp_path):
    data = ("#ENCODING:CP1250\n" + POLISH).encode("cp1250")
    song = load(write(tmp_path, data))
    assert song.encoding == "cp1250"
    assert song.notes[1].syllable == "jaźń"
    assert not song.warnings


def test_cp1250_without_tag_falls_back_with_warning(tmp_path):
    with pytest.warns(UltraStarWarning, match="CP1250"):
        song = load(write(tmp_path, POLISH.encode("cp1250")))
    assert song.encoding == "cp1250"
    assert song.title == "Zażółć"


def test_bogus_encoding_tag_falls_back_to_utf8(tmp_path):
    data = ("#ENCODING:nie-ma-takiego\n" + POLISH).encode("utf-8")
    song = load(write(tmp_path, data))
    assert song.encoding == "utf-8"
    assert song.notes[0].syllable == "gęślą"
