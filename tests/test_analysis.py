import json
import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from karaokebooster.analysis import (
    AnalysisError,
    analyze,
    detector_hit_rate,
    fold12,
    onset_lags,
    read_markers,
)
from karaokebooster.pitch import hz_to_midi, yin
from karaokebooster.ultrastar import parse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import analyze_takes  # noqa: E402

SR = 16000
# BPM 300 -> beat 0.05 s, GAP 500. 4 nuty po 0.5 s, odstęp 0.2 s. Wysokości: 57, 59, 60, 62 (MIDI)
SONG = "#BPM:300\n#GAP:500\n: 0 10 -3 a\n: 14 10 -1 b\n: 28 10 0 c\nF 40 4 0 hej\n: 42 10 2 d\nE\n"


def midi_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def sing(song, pitch_shift=0.0, lag_s=0.0, total_s=3.5):
    t = np.arange(int(total_s * SR)) / SR
    y = np.zeros_like(t)
    for n in song.notes:
        if not n.is_pitched:
            continue
        s = n.start_s + lag_s
        mask = (t >= s) & (t < s + n.dur_s)
        y[mask] = 0.4 * np.sin(2 * np.pi * midi_hz(n.pitch_midi + pitch_shift) * t[mask])
    return y


# --- wysokość (yin) -----------------------------------------------------

@pytest.mark.parametrize("hz", [98.0, 220.0, 440.0])
def test_yin_detects_sine(hz):
    t = np.arange(SR) / SR
    times, f0, conf = yin(0.5 * np.sin(2 * np.pi * hz * t), SR)
    voiced = f0[conf > 0.5]
    assert len(voiced) > 0.8 * len(f0)
    assert np.median(voiced) == pytest.approx(hz, rel=0.01)


def test_yin_silence_is_unvoiced():
    times, f0, conf = yin(np.zeros(SR), SR)
    assert np.all(f0 == 0)


def test_hz_to_midi():
    m = hz_to_midi(np.array([440.0, 0.0, 220.0]))
    assert m[0] == pytest.approx(69) and np.isnan(m[1]) and m[2] == pytest.approx(57)


def test_fold12():
    assert list(fold12(np.array([0.0, 12.0, -12.0, 5.0, 7.0, -7.0]))) == [0, 0, 0, 5, -5, 5]


# --- metryki ---------------------------------------------------------------

def run(y, song, markers=None, octave=0):
    times, f0, conf = yin(y, SR)
    return analyze(song, times, f0, conf, samples=y, sr=SR, markers=markers, octave=octave)


def test_perfect_singer():
    song = parse(SONG)
    r = run(sing(song), song)
    assert r.voiced_frames > 100
    assert r.frames_off_pct == pytest.approx(0, abs=3)
    assert r.error_p80 < 0.3
    assert r.large_errors is False and r.default_mode == "twardy"
    assert r.D == 3.0


def test_octave_lower_is_not_an_error():
    song = parse(SONG)
    r = run(sing(song, pitch_shift=-12), song)
    assert r.frames_off_pct == pytest.approx(0, abs=3)


def test_five_semitones_off():
    song = parse(SONG)
    r = run(sing(song, pitch_shift=5), song)
    assert r.frames_off_pct > 90
    assert r.error_p80 == pytest.approx(5, abs=0.3)
    assert r.large_errors is True and r.default_mode == "łagodny + ghost"
    assert r.D == pytest.approx(5, abs=0.3)


def test_octave_param_shifts_target():
    song = parse(SONG)
    # śpiewa 2 półtony niżej od oktawy niżej -> z --octave -1 błąd 2 (nie 10)
    r = run(sing(song, pitch_shift=-14), song, octave=-1)
    assert r.error_p80 == pytest.approx(2, abs=0.3)


def test_markers_give_lag_and_window():
    song = parse(SONG)
    lag = 0.15
    y = sing(song, lag_s=lag)
    markers = np.array([n.start_s + lag for n in song.notes if n.is_pitched])
    r = run(y, song, markers=markers)
    assert r.onset_lag_median_ms == pytest.approx(150, abs=1)
    assert r.W_ms == pytest.approx(225, abs=2)
    assert r.large_errors is True  # (b) > 120 ms
    assert r.detector_hit_pct == 100.0 and r.target_switch == "sylaba"


def test_no_markers_leaves_b_empty():
    song = parse(SONG)
    r = run(sing(song), song)
    assert r.onset_lag_median_ms is None and r.detector_hit_pct is None and r.markers == 0


def test_onset_lags_ignore_far_markers():
    song = parse(SONG)
    assert len(onset_lags(song, np.array([0.55, 9.0]))) == 1


def test_detector_hit_rate():
    assert detector_hit_rate(np.array([1.0, 2.0]), np.array([1.03, 2.2])) == 50.0
    assert detector_hit_rate(np.array([1.0]), np.array([])) == 0.0


def test_silent_take_has_no_data():
    song = parse(SONG)
    r = run(np.zeros(SR * 3), song)
    assert r.voiced_frames == 0 and r.frames_off_pct is None and r.large_errors is None


# --- znaczniki ---------------------------------------------------------------

def test_markers_reaper_csv(tmp_path):
    p = tmp_path / "m.csv"
    p.write_text("#,Name,Start,End,Length\nM1,a,0:01.500,,\nM2,b,1:02.250,,\n", encoding="utf-8")
    assert list(read_markers(p)) == [1.5, 62.25]


def test_markers_audacity_labels(tmp_path):
    p = tmp_path / "m.txt"
    p.write_text("2,000000\t2,000000\tb\n1.500000\t1.500000\ta\n", encoding="utf-8")
    assert list(read_markers(p)) == [1.5, 2.0]


def test_markers_plain(tmp_path):
    p = tmp_path / "m.txt"
    p.write_text("0.5\n1.25\n", encoding="utf-8")
    assert list(read_markers(p)) == [0.5, 1.25]


@pytest.mark.parametrize("content", ["", "abc\n"])
def test_markers_bad(tmp_path, content):
    p = tmp_path / "m.txt"
    p.write_text(content, encoding="utf-8")
    with pytest.raises(AnalysisError):
        read_markers(p)


# --- CLI -----------------------------------------------------------------

def test_cli_end_to_end(tmp_path, capsys):
    song = parse(SONG)
    txt = tmp_path / "s.txt"
    txt.write_text(SONG, encoding="utf-8")
    wav = tmp_path / "take1.wav"
    sf.write(str(wav), sing(song, pitch_shift=5), SR)
    out = tmp_path / "r.json"
    assert analyze_takes.main([str(txt), str(wav), "--engine", "yin", "--json", str(out)]) == 0
    assert "(a) ramki" in capsys.readouterr().out
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["take1.wav"]["default_mode"] == "łagodny + ghost"


def test_cli_markers_count_mismatch(tmp_path, capsys):
    txt = tmp_path / "s.txt"
    txt.write_text(SONG, encoding="utf-8")
    code = analyze_takes.main([str(txt), "a.wav", "b.wav", "--markers", "m.csv", "--engine", "yin"])
    assert code == 1 and "liczba plików" in capsys.readouterr().err


def test_cli_missing_take(tmp_path, capsys):
    txt = tmp_path / "s.txt"
    txt.write_text(SONG, encoding="utf-8")
    assert analyze_takes.main([str(txt), str(tmp_path / "brak.wav"), "--engine", "yin"]) == 1
