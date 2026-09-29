"""Kontrola wyrównania i E2E: .txt + syntetyczny wokal -> MIDI + raport (bez Demucs)."""

import sys
from pathlib import Path

import mido
import numpy as np
import pytest
import soundfile as sf

from karaokebooster.alignment import check_alignment, check_alignment_samples, detect_onsets
from karaokebooster.ultrastar import parse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import ultrastar2midi  # noqa: E402

SR = 22050
# BPM 300 -> beat 0.05 s, GAP 500 ms; nuty co 0.6 s
SONG = "#TITLE:T\n#BPM:300\n#GAP:500\n" + "".join(
    f": {i * 12} 6 {i % 5} la{i}\n" for i in range(8)) + "E\n"


def synth_vocals(song, shift_s=0.0, total_s=6.0):
    t = np.arange(int(total_s * SR)) / SR
    y = np.zeros_like(t)
    for n in song.notes:
        start = n.start_s + shift_s
        mask = (t >= start) & (t < start + n.dur_s)
        y[mask] = 0.5 * np.sin(2 * np.pi * 440 * 2 ** ((n.pitch_midi - 69) / 12) * t[mask])
    return y


def test_detect_onsets_on_bursts():
    song = parse(SONG)
    onsets = detect_onsets(synth_vocals(song), SR)
    assert len(onsets) == 8
    assert onsets[0] == pytest.approx(0.5, abs=0.011)


@pytest.mark.parametrize("shift_ms, ok", [(0, True), (20, True), (100, False), (-80, False)])
def test_alignment_tolerance(shift_ms, ok):
    song = parse(SONG)
    r = check_alignment_samples(song, synth_vocals(song, shift_ms / 1000), SR)
    assert r.ok is ok
    assert r.offset_ms == pytest.approx(shift_ms, abs=12)


def test_silent_vocals_do_not_crash():
    r = check_alignment_samples(parse(SONG), np.zeros(SR * 3), SR)
    assert not r.ok and r.offset_ms is None and "Nie wykryto" in r.message


def test_unrelated_vocals_report_too_few_matches():
    # jeden fragment śpiewu daleko od wszystkich nut (nuty kończą się ok. 4.8 s)
    t = np.arange(int(8 * SR)) / SR
    y = np.where((t >= 6.5) & (t < 7.0), 0.5 * np.sin(2 * np.pi * 220 * t), 0.0)
    r = check_alignment_samples(parse(SONG), y, SR)
    assert not r.ok and "Za mało dopasowań" in r.message


def test_stereo_file(tmp_path):
    song = parse(SONG)
    y = synth_vocals(song)
    path = tmp_path / "vocals.wav"
    sf.write(str(path), np.stack([y, y], axis=1), SR)
    assert check_alignment(song, path).ok


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
    assert ultrastar2midi.main([str(txt), "-o", str(out), "--vocals", str(wav)]) == 0
    assert "Wyrównanie OK" in capsys.readouterr().out
    assert sum(1 for m in mido.MidiFile(str(out)).tracks[0] if m.type == "note_on") == 8


def test_cli_misaligned_exit_code(tmp_path, capsys):
    txt, wav = make_files(tmp_path, shift_s=0.1)
    assert ultrastar2midi.main([str(txt), "--vocals", str(wav)]) == 2
    assert "Popraw #GAP" in capsys.readouterr().err
    assert (tmp_path / "song.mid").exists()


def test_cli_bad_file(tmp_path, capsys):
    bad = tmp_path / "bad.txt"
    bad.write_text("#BPM:100\nP1\n: 0 1 0 a\n", encoding="utf-8")
    assert ultrastar2midi.main([str(bad)]) == 1
    assert "duetów" in capsys.readouterr().err


def test_cli_missing_vocals(tmp_path, capsys):
    txt, _ = make_files(tmp_path)
    assert ultrastar2midi.main([str(txt), "--vocals", str(tmp_path / "brak.wav")]) == 1


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
