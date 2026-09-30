"""Projekt REAPER z szablonu (karaokebooster/rpp.py)."""

import base64
import re
from pathlib import Path

import mido
import pytest

from karaokebooster import rpp
from karaokebooster.midi_export import song_to_midi
from karaokebooster.ultrastar import parse

TEMPLATE = (Path(__file__).parent / "fixtures" / "template.rpp").read_text(encoding="utf-8")
SONG = parse("#TITLE:T\n#ARTIST:A\n#BPM:300\n#GAP:1000\n: 0 4 5 Za\n: 4 4 7 żó\n- 10\n: 20 8 -12 łć\nE\n")
MID = song_to_midi(SONG)
PODKLAD = rpp.ItemSpec("A - T_accompaniment.mp3", 12.5, "A - T_accompaniment.mp3")
GHOST = rpp.ItemSpec("A - T_vocals.mp3", 12.5, "A - T_vocals.mp3")
WOKAL = rpp.ItemSpec("a-t.mid", 3.0, "A - T")


def build(text=TEMPLATE):
    return rpp.build(text, PODKLAD, GHOST, WOKAL, MID)


def tracks(text):
    return {rpp.track_name(c).lower(): c for c in rpp.parse(text).children
            if isinstance(c, rpp.Block) and c.name == "TRACK"}


def items(track):
    return [c for c in track.children if isinstance(c, rpp.Block) and c.name == "ITEM"]


def test_parse_dump_roundtrip_keeps_nested_blocks():
    root = rpp.parse(TEMPLATE)
    again = rpp.parse(rpp.dump(root))
    assert rpp.dump(again) == rpp.dump(root)
    wokal = tracks(TEMPLATE)["wokal"]
    fx = [c for c in wokal.children if isinstance(c, rpp.Block) and c.name == "FXCHAIN"][0]
    assert any(isinstance(c, rpp.Block) and c.name == "VST" for c in fx.children)


@pytest.mark.parametrize("bad", ["", "<REAPER_PROJECT 0.1\n", "<OTHER\n>\n", "<REAPER_PROJECT\n>\n>\n",
                                 "tekst\n<REAPER_PROJECT\n>\n"])
def test_parse_rejects_broken_files(bad):
    with pytest.raises(rpp.RppError):
        rpp.parse(bad)


def test_build_replaces_items_and_keeps_fx_and_settings():
    text, warnings = build()
    assert warnings == []
    t = tracks(text)
    assert set(t) == {"podklad", "ghost", "wokal"}
    for name in t:
        assert len(items(t[name])) == 1
    assert "stary podkład" not in text
    assert "MARKER" not in text
    assert "VOLPAN 0.25 0 -1 -1 1" in text          # poziom ghosta z szablonu
    assert "ZmFrZSBzdGF0ZQ==" in text                 # stan wtyczki z szablonu
    src = [c for c in items(t["podklad"])[0].children if isinstance(c, rpp.Block)][0]
    assert src.header == "SOURCE MP3"
    assert src.children == ['FILE "A - T_accompaniment.mp3" 1']
    assert "LENGTH 12.500000" in items(t["ghost"])[0].children


def test_build_gives_unique_guids():
    text, _ = build()
    guids = re.findall(r"\b(?:I?GUID|POOLEDEVTS) (\{[0-9A-F-]+\})", text)
    assert len(guids) == len(set(guids)) >= 7


def test_midi_is_embedded_with_all_events():
    text, _ = build()
    src = [c for c in items(tracks(text)["wokal"])[0].children if isinstance(c, rpp.Block)][0]
    assert src.header == "SOURCE MIDI" and src.children[0] == "HASDATA 1 960 QN"
    t, notes, lyrics = 0, [], []
    for c in src.children:
        if isinstance(c, str) and c.startswith("E "):
            p = c.split()
            t += int(p[1])
            if p[2] == "90":
                notes.append((t, int(p[3], 16)))
        elif isinstance(c, rpp.Block) and c.name == "X":
            t += int(c.header.split()[1])
            data = b"".join(base64.b64decode(x) for x in c.children)
            if data[:2] == b"\xff\x05":
                lyrics.append(data[2:].decode("utf-8"))
    expected = [(round(n.start_s * 1920), n.pitch_midi) for n in SONG.notes if n.is_pitched]
    assert notes == expected
    assert lyrics == ["Za", "żó", "łć"]


def test_missing_track_is_clear_error():
    broken = TEMPLATE.replace("NAME ghost", "NAME Chórki")
    with pytest.raises(rpp.RppError, match="'ghost'"):
        build(broken)


def test_track_names_ignore_case_and_polish_letters():
    text, _ = build(TEMPLATE.replace("NAME Podklad", 'NAME "Podkład"').replace("NAME wokal", "NAME WOKAL"))
    assert len(tracks(text)) == 3


def test_tempo_forced_to_120_with_warning():
    text, warnings = build(TEMPLATE.replace("TEMPO 120 4 4 0", "TEMPO 100 3 4 0"))
    assert "TEMPO 120 3 4 0" in text
    assert warnings and "120" in warnings[0]


def test_missing_tempo_line_added():
    text, _ = build(TEMPLATE.replace("  TEMPO 120 4 4 0\n", ""))
    assert "TEMPO 120 4 4" in text


def test_unsupported_audio_format():
    with pytest.raises(rpp.RppError):
        rpp.build(TEMPLATE, rpp.ItemSpec("x.aac", 1, "x"), GHOST, WOKAL, MID)


def test_wrong_ppq_rejected():
    with pytest.raises(rpp.RppError, match="PPQ"):
        rpp.build(TEMPLATE, PODKLAD, GHOST, WOKAL, mido.MidiFile(ticks_per_beat=480))


def test_strip_items_makes_template():
    stripped = rpp.strip_items(TEMPLATE)
    assert "<ITEM" not in stripped and "MARKER" not in stripped and "FXCHAIN" in stripped


@pytest.mark.parametrize("s,out", [("Ty", "Ty"), (" jed", '" jed"'), ("", '""'),
                                   ('a "b"', "'a \"b\"'"), ("~", "~")])
def test_quote(s, out):
    assert rpp._quote(s) == out
