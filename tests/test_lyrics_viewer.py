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


# --- dopasowanie czcionki i sterowanie REAPER --------------------------------------

from karaokebooster.lyrics import fit_font_size, line_texts  # noqa: E402


def fake_measure(size, text):
    return size * len(text)  # 1 znak = `size` pikseli


def test_fit_font_size_shrinks_to_longest_line():
    texts = ["krótka", "a" * 50, "b" * 20]
    assert fit_font_size(texts, fake_measure, width=1000, max_size=40) == 20
    assert fit_font_size(texts, fake_measure, width=5000, max_size=40) == 40


def test_fit_font_size_respects_minimum_and_empty():
    assert fit_font_size(["x" * 1000], fake_measure, width=100, max_size=40, min_size=12) == 12
    assert fit_font_size([], fake_measure, width=100, max_size=40) == 40


def test_fit_font_size_checks_widest_not_only_longest():
    measure = lambda size, t: size * sum(3 if c == "W" else 1 for c in t)  # noqa: E731
    assert fit_font_size(["iiiiiiiiii", "WWWW"], measure, width=240, max_size=40) == 20


def test_line_texts():
    assert line_texts(phrases(parse(SONG))) == ["Zażółć", "gęślą"]


def test_reaper_remote_sends_action():
    from pythonosc.dispatcher import Dispatcher
    from pythonosc.osc_server import ThreadingOSCUDPServer
    got = []
    d = Dispatcher()
    d.map("/action", lambda addr, *a: got.append(a))
    server = ThreadingOSCUDPServer(("127.0.0.1", 0), d)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        remote = lyrics_viewer.ReaperRemote(server.server_address[1])
        assert remote.action(lyrics_viewer.ACTION_PLAY_PAUSE)
        for _ in range(100):
            if got:
                break
            time.sleep(0.01)
        assert got == [(40073,)]
    finally:
        server.shutdown()


def test_reaper_remote_disabled():
    assert not lyrics_viewer.ReaperRemote(0).action(lyrics_viewer.ACTION_PLAY_PAUSE)


def test_tilde_hidden_on_screen():
    song = parse("#BPM:300\n#GAP:0\n: 0 4 0 powie\n: 4 4 0 ~dzieć\n: 8 4 0 ~\n- 20\n: 30 4 0 cią~gnie\nE\n")
    lines = phrases(song)
    assert line_texts(lines) == ["powiedzieć", "ciągnie"]
    v = view_at(lines, 0.1)
    assert "".join(s.text for s in v.line) == "powiedzieć" and v.next_line == "ciągnie"


# --- linia zostaje po końcu, żeby ostatnia sylaba była widoczna -------------------

def test_line_held_after_last_syllable(lines):
    v = view_at(lines, 1.45)  # fraza 1 skończona o 1.4, fraza 2 od 2.0: przełączenie o 1.5
    assert [(s.text, s.state) for s in v.line] == [("Za", "past"), ("żółć", "past")]
    assert v.next_line == "gęślą"


def test_line_switches_lead_before_next_start():
    # przerwa 3 s: linia trzyma się 1 s po końcu, potem następna
    song = parse("#BPM:300\n#GAP:0\n: 0 4 0 a\n- 10\n: 80 4 0 b\nE\n")  # a: 0-0.2, b: 4.0-4.2
    ls = phrases(song)
    assert [s.text for s in view_at(ls, 1.1).line] == ["a"]
    assert [s.text for s in view_at(ls, 1.25).line] == ["b"]


def test_short_gap_switches_at_line_end():
    song = parse("#BPM:300\n#GAP:0\n: 0 4 0 a\n- 5\n: 6 4 0 b\nE\n")  # a: 0-0.2, b: 0.3-0.5
    ls = phrases(song)
    assert [s.text for s in view_at(ls, 0.19).line] == ["a"]
    assert [s.text for s in view_at(ls, 0.21).line] == ["b"]


# --- przesunięcie tekstu i wokal (klawisze w oknie tekstu) --------------------------

def test_song_settings_roundtrip(tmp_path):
    f = tmp_path / "viewer.json"
    s = lyrics_viewer.SongSettings(f)
    assert s.lead_ms == 0
    s.lead_ms = 150
    s.save()
    assert lyrics_viewer.SongSettings(f).lead_ms == 150


@pytest.mark.parametrize("content", ["", "nie json", "[1, 2]", '{"lead_ms": "abc"}'])
def test_song_settings_broken_file_is_zero(tmp_path, content):
    f = tmp_path / "viewer.json"
    f.write_text(content, encoding="utf-8")
    assert lyrics_viewer.SongSettings(f).lead_ms == 0


def test_song_settings_without_path_does_not_save():
    s = lyrics_viewer.SongSettings(None)
    s.lead_ms = 50
    s.save()  # nic nie robi, bez błędu


@pytest.mark.parametrize("ms,text", [(0, "tekst: bez przesunięcia"), (150, "tekst: 150 ms wcześniej"),
                                     (-60, "tekst: 60 ms później")])
def test_lead_label(ms, text):
    assert lyrics_viewer.lead_label(ms) == text


def test_lead_moves_text_earlier(ft):
    c = TransportClock(now=ft, offset_s=0.1)
    c.on_time(10.0)
    base = c.offset_s
    c.offset_s = base - 0.25   # lead 250 ms, jak w ViewerApp._apply_offset
    assert c.position() == pytest.approx(10.15)


def test_dispatcher_extra_handler_for_ghost_mute():
    c = TransportClock()
    got = []
    d = lyrics_viewer.make_dispatcher(c, threading.Lock(), {"/track/2/mute": got.append})
    d.call_handlers_for_packet(_msg("/track/2/mute", 1.0), ("127.0.0.1", 1))
    assert got == [1.0]


def _msg(address, value):
    from pythonosc.osc_message_builder import OscMessageBuilder
    b = OscMessageBuilder(address)
    b.add_arg(value)
    return b.build().dgram
