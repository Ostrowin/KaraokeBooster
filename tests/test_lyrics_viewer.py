import sys
import threading
import time
from pathlib import Path

import pytest
from pythonosc.udp_client import SimpleUDPClient

from karaokebooster.lyrics import STALE_S, TransportClock, phrases, view_at
from karaokebooster.ultrastar import parse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import lyrics_viewer  # noqa: E402

# BPM 300 -> beat 0.05 s, GAP 1000
SONG = "#BPM:300\n#GAP:1000\n: 0 4 0 Za\n: 4 4 0 żółć\n- 10\n: 20 4 0 gęś\n: 24 4 0 lą\nE\n"


class FakeTime:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


@pytest.fixture
def ft():
    return FakeTime()


# --- zegar ---------------------------------------------------------------

def test_clock_stopped_holds_position(ft):
    c = TransportClock(now=ft)
    c.on_time(5.0)
    ft.t += 3
    assert c.position() == 5.0


def test_clock_advances_while_playing_between_osc(ft):
    c = TransportClock(now=ft)
    c.on_time(5.0)
    c.on_play(1)
    ft.t += 0.4
    assert c.position() == pytest.approx(5.4)
    c.on_time(5.5)  # korekta z REAPER
    ft.t += 0.1
    assert c.position() == pytest.approx(5.6)


def test_clock_pause_freezes(ft):
    c = TransportClock(now=ft)
    c.on_time(1.0)
    c.on_play(1)
    ft.t += 0.5
    c.on_pause_or_stop(1)
    ft.t += 10
    assert c.position() == pytest.approx(1.5)
    assert not c.playing


def test_clock_seek_jumps(ft):
    c = TransportClock(now=ft)
    c.on_play(1)
    c.on_time(42.0)
    assert c.position() == pytest.approx(42.0)


def test_clock_stops_when_osc_goes_silent(ft):
    c = TransportClock(now=ft)
    c.on_time(10.0)
    c.on_play(1)
    ft.t += 30  # REAPER zamknięty, brak /time
    assert c.position() == pytest.approx(10.0 + STALE_S)


def test_clock_offset(ft):
    c = TransportClock(now=ft, offset_s=0.05)
    c.on_time(2.0)
    assert c.position() == pytest.approx(1.95)


def test_play_zero_is_ignored(ft):
    c = TransportClock(now=ft)
    c.on_play(0)
    assert not c.playing


# --- widok ---------------------------------------------------------------

@pytest.fixture
def lines():
    return phrases(parse(SONG))


def test_phrases_split(lines):
    assert [[n.syllable for n in line] for line in lines] == [["Za", "żółć"], ["gęś", "lą"]]


def test_before_first_note_countdown(lines):
    v = view_at(lines, 0.5)
    assert [s.state for s in v.line] == ["future", "future"]
    assert v.countdown_s == pytest.approx(0.5)
    assert v.next_line == "gęślą"


def test_mid_syllable(lines):
    v = view_at(lines, 1.25)  # druga sylaba: 1.2-1.4
    assert [(s.text, s.state) for s in v.line] == [("Za", "past"), ("żółć", "current")]
    assert v.countdown_s is None


def test_between_phrases_shows_next_line_with_countdown(lines):
    v = view_at(lines, 1.6)  # fraza 1 skończona o 1.4, fraza 2 od 2.0
    assert [s.text for s in v.line] == ["gęś", "lą"]
    assert v.countdown_s == pytest.approx(0.4)
    assert v.next_line == ""


def test_after_end_shows_last_line_all_past(lines):
    v = view_at(lines, 99)
    assert [s.state for s in v.line] == ["past", "past"]


def test_empty():
    assert view_at([], 1.0).line == []


# --- OSC -----------------------------------------------------------------

def test_dispatcher_routes_messages(ft):
    c = TransportClock(now=ft)
    d = lyrics_viewer.make_dispatcher(c, threading.Lock())
    for addr, val in [("/time", 3.0), ("/play", 1.0)]:
        for h in d.handlers_for_address(addr):
            h.callback(addr, val)
    assert c.playing and c.position() == pytest.approx(3.0)
    for h in d.handlers_for_address("/stop"):
        h.callback("/stop", 1.0)
    assert not c.playing


def test_osc_over_udp():
    c = TransportClock()
    server = lyrics_viewer.start_osc(c, threading.Lock(), 0)
    try:
        port = server.server_address[1]
        client = SimpleUDPClient("127.0.0.1", port)
        client.send_message("/time", 12.5)
        deadline = time.monotonic() + 2
        while c.position() != pytest.approx(12.5) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert c.position() == pytest.approx(12.5)
    finally:
        server.shutdown()


def test_cli_bad_file(tmp_path, capsys):
    bad = tmp_path / "x.txt"
    bad.write_text("#TITLE:x\n", encoding="utf-8")
    assert lyrics_viewer.main([str(bad)]) == 1
    assert "BŁĄD" in capsys.readouterr().err
