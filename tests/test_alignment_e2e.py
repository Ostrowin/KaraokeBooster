"""Kontrola wyrównania po wysokości (decyzja 0016) i E2E: .txt + syntetyczny wokal -> MIDI + raport."""

import sys
from dataclasses import replace
from pathlib import Path

import mido
import numpy as np
import pytest
import soundfile as sf

from karaokebooster.alignment import (
    check_alignment,
    check_alignment_pitch,
    check_alignment_samples,
    detect_onsets,
)
from karaokebooster.pitch import HOP_S
from karaokebooster.ultrastar import parse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import ultrastar2midi  # noqa: E402

SR = 16000
# BPM 300 -> beat 0.05 s, GAP 500 ms. 20 nut o różnej długości, nieregularne odstępy i różne wysokości,
# żeby przesunięcie o jeden "takt" nie wyglądało na dopasowanie.
_STARTS, _t = [], 0
for i in range(20):
    _STARTS.append(_t)
    _t += 6 + (i * 7) % 5
SONG = "#TITLE:T\n#BPM:300\n#GAP:500\n" + "".join(
    f": {s} {4 + (i % 3)} {(i * 5) % 12 - 5} la{i}\n" for i, s in enumerate(_STARTS)) + "E\n"


def synth_vocals(song, shift_s=0.0, total_s=12.0, pitch_shift=0):
    t = np.arange(int(total_s * SR)) / SR
    y = np.zeros_like(t)
    for n in song.notes:
        start = n.start_s + shift_s
        mask = (t >= start) & (t < start + n.dur_s)
        y[mask] = 0.5 * np.sin(2 * np.pi * 440 * 2 ** ((n.pitch_midi + pitch_shift - 69) / 12) * t[mask])
    return y


def check(y, song=None, **kw):
    return check_alignment_samples(song or parse(SONG), y, SR, engine="yin", **kw)


# --- detect_onsets (zostaje dla analizy nagrań) ---------------------------

def test_detect_onsets_on_bursts():
    song = parse(SONG)
    onsets = detect_onsets(synth_vocals(song), SR)
    starts = np.array([n.start_s for n in song.notes])
    # każdy wykryty początek leży przy starcie nuty; nuty bez >= 50 ms ciszy przed sobą się łączą
    assert len(onsets) >= 15
    assert all(np.min(np.abs(starts - o)) <= 0.011 for o in onsets)
    assert onsets[0] == pytest.approx(0.5, abs=0.011)


# --- wyrównanie po wysokości ----------------------------------------------

@pytest.mark.parametrize("shift_ms, ok", [(0, True), (20, True), (-30, True), (100, False), (-80, False),
                                          (250, False)])
def test_alignment_detects_shift(shift_ms, ok):
    r = check(synth_vocals(parse(SONG), shift_ms / 1000))
    assert r.confident
    assert r.offset_ms == pytest.approx(shift_ms, abs=HOP_S * 1000 + 1)
    assert r.ok is ok


def test_octave_lower_singer_still_aligned():
    r = check(synth_vocals(parse(SONG), pitch_shift=-12))
    assert r.ok and r.offset_ms == pytest.approx(0, abs=11)


def test_misaligned_message_suggests_gap_fix():
    r = check(synth_vocals(parse(SONG), 0.1))
    assert "Popraw #GAP o +100 ms" in r.message or "Popraw #GAP o +90 ms" in r.message or \
        "Popraw #GAP o +110 ms" in r.message


def test_silent_vocals_do_not_crash():
    r = check(np.zeros(SR * 3))
    assert not r.ok and r.offset_ms is None and "Nie wykryto" in r.message


def test_wrong_melody_is_not_confident():
    song = parse(SONG)
    rng = np.random.default_rng(7)
    other = replace(song, notes=[replace(n, pitch_midi=int(rng.integers(50, 74))) for n in song.notes])
    r = check(synth_vocals(other), song=song)  # ten sam rytm, zupełnie inna (losowa) melodia
    assert not r.confident and not r.ok
    assert "brak wyraźnego dopasowania" in r.message


def test_shift_beyond_search_window_is_not_ok():
    r = check(synth_vocals(parse(SONG), 0.6))
    assert not r.ok


def test_empty_grid():
    r = check_alignment_pitch(parse(SONG), np.array([]), np.array([]), np.array([]))
    assert not r.ok and "Pusty" in r.message


def test_stereo_file(tmp_path):
    song = parse(SONG)
    y = synth_vocals(song)
    path = tmp_path / "vocals.wav"
    sf.write(str(path), np.stack([y, y], axis=1), SR)
    assert check_alignment(song, path, engine="yin").ok


# --- E2E przez CLI -------------------------------------------------------

def make_files(tmp_path, shift_s=0.0):
    txt = tmp_path / "song.txt"
    txt.write_text(SONG, encoding="utf-8")
    wav = tmp_path / "vocals.wav"
    sf.write(str(wav), synth_vocals(parse(SONG), shift_s), SR)
    return txt, wav


def test_cli_ok(tmp_path, capsys):
    txt, wav = make_files(tmp_path)
    out = tmp_path / "out.mid"
    assert ultrastar2midi.main([str(txt), "-o", str(out), "--vocals", str(wav), "--engine", "yin"]) == 0
    assert "Wyrównanie OK" in capsys.readouterr().out
    assert sum(1 for m in mido.MidiFile(str(out)).tracks[0] if m.type == "note_on") == 20


def test_cli_misaligned_exit_code(tmp_path, capsys):
    txt, wav = make_files(tmp_path, shift_s=0.1)
    assert ultrastar2midi.main([str(txt), "--vocals", str(wav), "--engine", "yin"]) == 2
    assert "Popraw #GAP" in capsys.readouterr().err
    assert (tmp_path / "song.mid").exists()


def test_cli_bad_file(tmp_path, capsys):
    bad = tmp_path / "bad.txt"
    bad.write_text("#BPM:100\nP1\n: 0 1 0 a\n", encoding="utf-8")
    assert ultrastar2midi.main([str(bad)]) == 1
    assert "duetów" in capsys.readouterr().err


def test_cli_missing_vocals(tmp_path, capsys):
    txt, _ = make_files(tmp_path)
    assert ultrastar2midi.main([str(txt), "--vocals", str(tmp_path / "brak.wav"), "--engine", "yin"]) == 1


def test_cli_octave_auto_default_and_manual(tmp_path, capsys):
    txt = tmp_path / "hi.txt"
    txt.write_text("#BPM:300\n: 0 4 53 a\n: 4 4 55 b\n", encoding="utf-8")  # MIDI 113/115
    out = tmp_path / "hi.mid"
    assert ultrastar2midi.main([str(txt), "-o", str(out)]) == 0
    assert "oktawa -5 (auto)" in capsys.readouterr().out
    notes = [m.note for m in mido.MidiFile(str(out)).tracks[0] if m.type == "note_on"]
    assert notes == [53, 55]
    assert ultrastar2midi.main([str(txt), "-o", str(out), "--octave", "-4"]) == 0
    assert ultrastar2midi.main([str(txt), "--octave", "dwa"]) == 1
