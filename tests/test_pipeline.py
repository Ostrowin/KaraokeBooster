"""Potok Song Studio (karaokebooster/pipeline.py) z podstawionym ultrasongs (tests/fake_ultrasongs.py)."""

import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from karaokebooster import pipeline as P
from karaokebooster.lyrics_text import REFRAIN_MARKER

HERE = Path(__file__).parent
FAKE = [sys.executable, str(HERE / "fake_ultrasongs.py")]
LYRICS = "La la la\nla la /x2\n"


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    songs = tmp_path / "songs"
    songs.mkdir()
    shutil.copy(HERE / "fixtures" / "template.rpp", songs / P.TEMPLATE_NAME)
    calls = tmp_path / "calls.txt"
    monkeypatch.setenv("FAKE_CALLS", str(calls))
    monkeypatch.delenv("FAKE_MODE", raising=False)
    c = P.Config(songs_dir=songs, ultrasongs_cmd=FAKE, align_engine="yin")
    c.calls = calls
    return c


@pytest.fixture
def audio(tmp_path):
    p = tmp_path / "Muzyka" / "Jan Testowy - Łódka.mp3"
    p.parent.mkdir()
    sf.write(str(p), np.zeros(1600), 16000, format="MP3")
    return p


def calls(cfg):
    return cfg.calls.read_text(encoding="utf-8").splitlines() if cfg.calls.exists() else []


def new_song(cfg, audio, lyrics=LYRICS, quality="fast"):
    return P.create_song(cfg, audio, "Jan Testowy", "Łódka", lyrics, quality)


# --- nazwy -------------------------------------------------------------------

@pytest.mark.parametrize("name,expected", [
    ("Jan Testowy - Łódka.mp3", ("Jan Testowy", "Łódka")),
    ("Łódka.mp3", ("", "Łódka")),
    ("A - B - C.mp3", ("A", "B - C")),
    ("  A  -  B .flac", ("A", "B")),
    ("A-B.mp3", ("", "A-B")),
])
def test_split_filename(name, expected):
    assert P.split_filename(name) == expected


@pytest.mark.parametrize("artist,title,slug", [
    ("Krzysztof Krawczyk", "Za tobą pójdę jak na bal", "krzysztof-krawczyk-za-toba-pojde-jak-na"),
    ("A", "b" * 100, "a-" + "b" * 38),
    ("ŁĄKA", "Żółć: *?<>|", "laka-zolc"),
    ("", "???", "piosenka"),
])
def test_slugify(artist, title, slug):
    assert P.slugify(artist, title) == slug


def test_unique_slug(tmp_path):
    assert P.unique_slug(tmp_path, "a") == "a"
    (tmp_path / "a").mkdir()
    (tmp_path / "a-2").mkdir()
    assert P.unique_slug(tmp_path, "a") == "a-3"


# --- reguły okienka (D13) ------------------------------------------------------------

@pytest.mark.parametrize("status,editor,expected", [
    ("queued", True, {"log", "unqueue"}),
    ("running", True, {"log"}),
    ("interrupted", True, {"log", "resume"}),
    ("error", True, {"log", "resume"}),
    ("needs_review", True, {"log", "sing", "lyrics", "import_txt", "recalc", "regenerate", "editor", "accept"}),
    ("needs_review", False, {"log", "sing", "lyrics", "import_txt", "recalc", "regenerate", "accept"}),
    ("ready", True, {"log", "sing", "lyrics", "import_txt", "recalc", "regenerate", "editor"}),
    ("ready", False, {"log", "sing", "lyrics", "import_txt", "recalc", "regenerate"}),
])
def test_library_actions(status, editor, expected):
    assert P.library_actions(status, editor) == expected


def test_can_enqueue(audio):
    assert P.can_enqueue("A", "T", audio, "tekst") == (True, "")
    assert not P.can_enqueue("A", "T", None, "tekst")[0]
    assert not P.can_enqueue("A", "T", audio.with_name("brak.mp3"), "tekst")[0]
    assert not P.can_enqueue(" ", "T", audio, "tekst")[0]
    assert not P.can_enqueue("A", "", audio, "tekst")[0]
    assert not P.can_enqueue("A", "T", audio, "  \n")[0]
    ok, reason = P.can_enqueue("A", "T", audio, f"a\n\n{REFRAIN_MARKER}\n")
    assert not ok and "refren" in reason


def _state(steps, queued=False, alignment=None, accepted=False):
    return {"queued": queued, "alignment": alignment, "accepted": accepted,
            "steps": {s: {"status": st} for s, st in zip(P.STEPS, steps)}}


@pytest.mark.parametrize("state,status", [
    (_state(["pending"] * 4, queued=True), "queued"),
    (_state(["done", "running", "pending", "pending"]), "running"),
    (_state(["done", "error", "pending", "pending"]), "error"),
    (_state(["done", "interrupted", "pending", "pending"]), "interrupted"),
    (_state(["done", "done", "pending", "pending"]), "interrupted"),
    (_state(["done"] * 4, alignment={"ok": True}), "ready"),
    (_state(["done"] * 4, alignment={"ok": False}), "needs_review"),
    (_state(["done"] * 4, alignment={"ok": False}, accepted=True), "ready"),
])
def test_song_status(state, status):
    assert P.song_status(state) == status


# --- dodawanie -----------------------------------------------------------------------

def test_create_song_copies_audio_and_never_overwrites(cfg, audio):
    d1 = new_song(cfg, audio)
    d2 = new_song(cfg, audio)
    assert d1.name == "jan-testowy-lodka" and d2.name == "jan-testowy-lodka-2"
    st = P.load_state(d1)
    assert st["queued"] and st["source_file"] == "source.mp3" and (d1 / "source.mp3").exists()
    assert P.find_song(cfg, "Jan Testowy", "Łódka") == d1
    assert P.find_song(cfg, "Ktoś", "Inny") is None
    assert [d.name for d in P.all_songs(cfg)] == [d1.name, d2.name]


def test_create_song_rejects_bad_form(cfg, audio):
    with pytest.raises(P.PipelineError):
        P.create_song(cfg, audio, "A", "T", REFRAIN_MARKER, "fast")
    with pytest.raises(P.PipelineError):
        P.create_song(cfg, audio, "A", "T", "tekst", "turbo")
    assert list(cfg.songs_dir.iterdir()) == [cfg.songs_dir / P.TEMPLATE_NAME]


# --- pełny przebieg ------------------------------------------------------------------

def test_full_run_ready(cfg, audio):
    d = new_song(cfg, audio)
    events = []
    assert P.run(d, cfg, lambda k, t: events.append((k, t))) == "ready"
    st = P.load_state(d)
    base = "Jan Testowy - Łódka"
    assert st["base_name"] == base and not st["queued"]
    assert all(st["steps"][s]["status"] == "done" for s in P.STEPS)
    assert st["alignment"]["ok"]
    assert (d / "lyrics.txt").read_text(encoding="utf-8") == "La la la\nla la\nLa la la\nla la\n"
    for name in (f"{base}.txt", f"{base}_vocals.mp3", f"{base}_accompaniment.mp3", f"{base}_editor.html",
                 "jan-testowy-lodka.mid", "jan-testowy-lodka.rpp", "log.txt"):
        assert (d / name).exists(), name
    rpp_text = (d / "jan-testowy-lodka.rpp").read_text(encoding="utf-8")
    assert f'FILE "{base}_accompaniment.mp3" 1' in rpp_text and "<SOURCE MIDI" in rpp_text
    assert calls(cfg) == ["whisper_language=pl,transcribe_runs=3,whisperx_align_runs=3"]
    assert ("step", "Krok: ultrasongs") in events
    assert "fake ultrasongs" in (d / "log.txt").read_text(encoding="utf-8")


def test_second_run_skips_everything(cfg, audio):
    d = new_song(cfg, audio)
    P.run(d, cfg)
    before = (d / "log.txt").read_text(encoding="utf-8")
    assert P.run(d, cfg) == "ready"
    after = (d / "log.txt").read_text(encoding="utf-8")[len(before):]
    assert "Krok:" not in after and len(calls(cfg)) == 1


def test_source_copy_used_after_original_removed(cfg, audio):
    d = new_song(cfg, audio)
    audio.unlink()
    assert P.run(d, cfg) == "ready"


def test_ultrasongs_failure_then_resume(cfg, audio, monkeypatch):
    d = new_song(cfg, audio)
    monkeypatch.setenv("FAKE_MODE", "fail")
    assert P.run(d, cfg) == "error"
    st = P.load_state(d)
    assert st["steps"]["ultrasongs"]["status"] == "error"
    assert "CUDA out of memory" in st["steps"]["ultrasongs"]["error"]
    assert "kod wyjścia 1" in st["steps"]["ultrasongs"]["error"]
    monkeypatch.setenv("FAKE_MODE", "ok")
    assert P.run(d, cfg) == "ready"
    assert len(calls(cfg)) == 2


def test_missing_output_file_is_error(cfg, audio, monkeypatch):
    d = new_song(cfg, audio)
    monkeypatch.setenv("FAKE_MODE", "missing")
    assert P.run(d, cfg) == "error"
    assert "_vocals.mp3" in P.load_state(d)["steps"]["ultrasongs"]["error"]


def test_missing_ultrasongs_install(cfg, audio, tmp_path):
    d = new_song(cfg, audio)
    cfg.ultrasongs_cmd, cfg.ultrasongs_dir = None, tmp_path / "brak"
    assert P.run(d, cfg) == "error"
    assert "ultrasongs-setup" in P.load_state(d)["steps"]["ultrasongs"]["error"]


def test_error_in_midi_step_does_not_rerun_ultrasongs(cfg, audio):
    d = new_song(cfg, audio)
    P.run(d, cfg)
    st = P.load_state(d)
    txt = d / f"{st['base_name']}.txt"
    good = txt.read_text(encoding="utf-8")
    txt.write_text("to nie jest UltraStar\n", encoding="utf-8")
    assert P.run(d, cfg) == "error"
    assert P.load_state(d)["steps"]["midi"]["status"] == "error"
    txt.write_text(good, encoding="utf-8")
    assert P.run(d, cfg) == "ready"
    assert len(calls(cfg)) == 1


def test_misaligned_needs_review_then_accept_then_txt_change_clears(cfg, audio, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "shift")
    d = new_song(cfg, audio)
    assert P.run(d, cfg) == "needs_review"
    st = P.load_state(d)
    assert not st["alignment"]["ok"] and "#GAP" in st["alignment"]["message"]
    P.accept(d)
    assert P.song_status(P.load_state(d)) == "ready"
    txt = d / f"{st['base_name']}.txt"
    txt.write_text(txt.read_text(encoding="utf-8").replace("#TITLE", "#TITLE:x\n#VERSION:1.0.0\n#X"), encoding="utf-8")
    assert P.run(d, cfg) == "needs_review"
    assert not P.load_state(d)["accepted"]


def test_import_txt_backs_up_and_recalc_fixes_gap(cfg, audio, monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_MODE", "shift")
    d = new_song(cfg, audio)
    assert P.run(d, cfg) == "needs_review"
    st = P.load_state(d)
    txt = d / f"{st['base_name']}.txt"
    fixed = tmp_path / "Pobrane" / "poprawiony.txt"
    fixed.parent.mkdir()
    fixed.write_text(txt.read_text(encoding="utf-8").replace("#GAP:500", "#GAP:650"), encoding="utf-8")
    bak = P.import_txt(d, fixed)
    assert bak is not None and bak.exists() and "#GAP:500" in bak.read_text(encoding="utf-8")
    assert P.run(d, cfg) == "ready"
    assert len(calls(cfg)) == 1


def test_import_txt_rejects_broken_file(cfg, audio, tmp_path):
    d = new_song(cfg, audio)
    P.run(d, cfg)
    bad = tmp_path / "zly.txt"
    bad.write_text("#BPM:abc\n", encoding="utf-8")
    with pytest.raises(Exception):
        P.import_txt(d, bad)


def test_import_txt_before_ultrasongs(cfg, audio, tmp_path):
    d = new_song(cfg, audio)
    with pytest.raises(P.PipelineError):
        P.import_txt(d, tmp_path / "x.txt")


def test_regenerate_with_other_quality_backs_up_edited_txt(cfg, audio):
    d = new_song(cfg, audio)
    P.run(d, cfg)
    st = P.load_state(d)
    txt = d / f"{st['base_name']}.txt"
    txt.write_text(txt.read_text(encoding="utf-8") + "\n", encoding="utf-8")   # "ręczna poprawka"
    P.set_queued(d, True, quality="accurate")
    events = []
    assert P.run(d, cfg, lambda k, t: events.append((k, t))) == "ready"
    assert calls(cfg)[-1] == "whisper_language=pl,transcribe_runs=7,whisperx_align_runs=5"
    assert list(d.glob("*.txt.*.bak"))
    assert any(k == "warn" and "poprawki" in t for k, t in events)


def test_regenerate_same_quality_with_force(cfg, audio):
    d = new_song(cfg, audio)
    P.run(d, cfg)
    P.run(d, cfg, force={"ultrasongs"})
    assert len(calls(cfg)) == 2
    assert not list(d.glob("*.txt.*.bak"))   # .txt bez zmian: bez kopii


def test_template_change_rebuilds_only_rpp_and_backs_up_edited_project(cfg, audio):
    d = new_song(cfg, audio)
    P.run(d, cfg)
    project = d / "jan-testowy-lodka.rpp"
    project.write_text(project.read_text(encoding="utf-8") + "\n", encoding="utf-8")  # zapis w REAPER
    tpl = cfg.template_path
    tpl.write_text(tpl.read_text(encoding="utf-8").replace("VOLPAN 0.25", "VOLPAN 0.5"), encoding="utf-8")
    assert P.template_stale(P.load_state(d), cfg)
    before = (d / "log.txt").read_text(encoding="utf-8")
    assert P.run(d, cfg) == "ready"
    log = (d / "log.txt").read_text(encoding="utf-8")[len(before):]
    assert "Krok: rpp" in log and "Krok: midi" not in log and "Krok: ultrasongs" not in log
    assert "VOLPAN 0.5" in project.read_text(encoding="utf-8")
    assert list(d.glob("*.rpp.*.bak"))
    assert not P.template_stale(P.load_state(d), cfg)


def test_missing_template(cfg, audio):
    cfg.template_path.unlink()
    d = new_song(cfg, audio)
    assert P.run(d, cfg) == "error"
    assert "szablonu" in P.load_state(d)["steps"]["rpp"]["error"]


def test_refrain_marker_in_saved_lyrics_is_error(cfg, audio):
    d = new_song(cfg, audio)
    (d / P.LYRICS_INPUT).write_text(REFRAIN_MARKER, encoding="utf-8")
    assert P.run(d, cfg) == "error"


# --- przerwanie, zapis, blokada ------------------------------------------------------

def test_mark_interrupted(cfg, audio):
    d = new_song(cfg, audio)
    st = P.load_state(d)
    st["steps"]["ultrasongs"]["status"] = "running"
    P.save_state(d, st)
    assert P.mark_interrupted(d)
    st = P.load_state(d)
    assert P.song_status(st) == "interrupted" and not st["queued"]
    assert not P.mark_interrupted(d)
    assert P.run(d, cfg) == "ready"


def test_save_state_is_atomic(cfg, audio, monkeypatch):
    d = new_song(cfg, audio)
    good = (d / P.STATE_FILE).read_text(encoding="utf-8")

    def boom(*a, **k):
        raise OSError("dysk pełny")
    monkeypatch.setattr(P.os, "replace", boom)
    with pytest.raises(OSError):
        P.save_state(d, {"zepsute": True})
    assert (d / P.STATE_FILE).read_text(encoding="utf-8") == good
    assert json.loads(good)["slug"] == "jan-testowy-lodka"


def test_instance_lock(tmp_path):
    first = P.InstanceLock(tmp_path)
    with pytest.raises(P.AlreadyRunning):
        P.InstanceLock(tmp_path)
    first.release()
    second = P.InstanceLock(tmp_path)
    second.release()


# --- konfiguracja i szablon ------------------------------------------------------------

def test_load_config(tmp_path):
    assert P.load_config(tmp_path / "brak.toml") == P.Config()
    f = tmp_path / "k.toml"
    f.write_text('osc_port = 9001\nsongs_dir = "D:/piosenki"\nalign_engine = "yin"\n', encoding="utf-8")
    c = P.load_config(f)
    assert c.osc_port == 9001 and c.songs_dir == Path("D:/piosenki") and c.align_engine == "yin"
    assert c.template_path == Path("D:/piosenki") / P.TEMPLATE_NAME
    f.write_text("costam = 1\n", encoding="utf-8")
    with pytest.raises(P.PipelineError, match="costam"):
        P.load_config(f)


def test_make_template_from_project(cfg, tmp_path):
    project = tmp_path / "moj.rpp"
    shutil.copy(HERE / "fixtures" / "template.rpp", project)
    time.sleep(0.01)
    target = P.make_template(cfg, project)
    text = target.read_text(encoding="utf-8")
    assert "<ITEM" not in text and "FXCHAIN" in text
    assert list(cfg.songs_dir.glob("_szablon.rpp.*.bak"))
