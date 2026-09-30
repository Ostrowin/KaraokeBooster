"""Potok Song Studio: nowa piosenka z mp3 + tekstu do projektu REAPER (docs/designs/song-studio.md).

    Dodaj ──► queued ──► lyrics ─► ultrasongs ─► midi (+ wyrównanie) ─► rpp ──► ready / needs_review
                            │           │              │                  │
                            └───────────┴── error ─────┴──────────────────┘   (Wznów = krok z błędem)

Każdy krok ma `inputs_hash` (sha256 plików wejściowych i parametrów). Krok ze statusem `done`
i niezmienionym hashem jest pomijany, więc poprawka `.txt` przelicza tylko midi + rpp, a zmiana
szablonu tylko rpp. Stan piosenki leży w `songs/<slug>/song.json` (zapis atomowy).

Jeden proces (decyzja D8 przeglądu): okienko trzyma blokadę `songs/.studio.lock`.
Reguły okienka (przyciski wg statusu, nazwa pliku → wykonawca/tytuł) są tu jako czyste funkcje (D13).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
import unicodedata
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import mido
import soundfile as sf

from . import rpp
from .alignment import available_engine, check_alignment
from .lyrics_text import REFRAIN_MARKER, expand
from .midi_export import resolve_octave, song_to_midi
from .ultrastar import UltraStarError, UltraStarWarning, load

ROOT = Path(__file__).resolve().parents[1]
STEPS = ("lyrics", "ultrasongs", "midi", "rpp")
QUALITY = {"fast": (3, 3), "accurate": (7, 5)}  # (transcribe_runs, whisperx_align_runs)
STATE_FILE = "song.json"
LOG_FILE = "log.txt"
LYRICS_INPUT = "lyrics_input.txt"
LYRICS_FILE = "lyrics.txt"
LOCK_FILE = ".studio.lock"
TEMPLATE_NAME = "_szablon.rpp"

Event = Callable[[str, str], None]  # (rodzaj, tekst): "log" | "step" | "warn"


class PipelineError(Exception):
    """Krok się nie udał; komunikat jest dla użytkownika."""


# --- konfiguracja ---------------------------------------------------------

@dataclass
class Config:
    songs_dir: Path = ROOT / "songs"
    ultrasongs_dir: Path = ROOT.parent / "ultrasongs"
    reaper_exe: Path = Path(r"C:\Program Files\REAPER (x64)\reaper.exe")
    template: Path | None = None           # domyślnie songs/_szablon.rpp
    osc_port: int = 9000            # REAPER wysyła tu czas (podgląd tekstu nasłuchuje)
    reaper_osc_port: int = 8000     # REAPER nasłuchuje tu (spacja w oknie tekstu = start/pauza)
    offset_ms: float = 0.0
    language: str = "pl"
    align_engine: str = "crepe"
    # Polecenie uruchamiające ultrasongs; None = <ultrasongs>/.venv/Scripts/python -m cli
    ultrasongs_cmd: list[str] | None = None

    @property
    def template_path(self) -> Path:
        return self.template or self.songs_dir / TEMPLATE_NAME

    def ultrasongs_prefix(self) -> list[str]:
        if self.ultrasongs_cmd:
            return list(self.ultrasongs_cmd)
        return [str(self.ultrasongs_dir / ".venv" / "Scripts" / "python.exe"), "-m", "cli"]


def load_config(path: Path = ROOT / "karaokebooster.local.toml") -> Config:
    """Konfiguracja z pliku TOML (opcjonalny); brakujące pola mają wartości domyślne."""
    cfg = Config()
    if not path.exists():
        return cfg
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    for key, value in data.items():
        if not hasattr(cfg, key):
            raise PipelineError(f"{path.name}: nieznane pole '{key}'.")
        if key in ("songs_dir", "ultrasongs_dir", "reaper_exe", "template"):
            value = Path(value)
        setattr(cfg, key, value)
    return cfg


# --- nazwy ------------------------------------------------------------------

def split_filename(name: str) -> tuple[str, str]:
    """"Wykonawca - Tytuł.mp3" → (wykonawca, tytuł). Bez " - ": ("", cała nazwa)."""
    stem = Path(name).stem.strip()
    if " - " in stem:
        artist, title = stem.split(" - ", 1)
        return artist.strip(), title.strip()
    return "", stem


def slugify(artist: str, title: str) -> str:
    text = f"{artist} {title}".replace("ł", "l").replace("Ł", "L")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:40].strip("-") or "piosenka"  # krótko: limit ścieżek Windows


def unique_slug(songs_dir: Path, slug: str) -> str:
    if not (songs_dir / slug).exists():
        return slug
    n = 2
    while (songs_dir / f"{slug}-{n}").exists():
        n += 1
    return f"{slug}-{n}"


# --- stan piosenki ------------------------------------------------------------

def _new_state(artist: str, title: str, slug: str, source_original: str, source_file: str,
               quality: str) -> dict:
    return {
        "version": 1, "artist": artist, "title": title, "slug": slug,
        "source_original": source_original, "source_file": source_file, "quality": quality,
        "queued": True, "created": time.time(),
        "base_name": None, "txt_hash": None, "rpp_hash": None, "template_hash": None,
        "alignment": None, "accepted": False,
        "steps": {s: {"status": "pending", "inputs_hash": None, "error": None} for s in STEPS},
    }


def load_state(song_dir: Path) -> dict:
    return json.loads((song_dir / STATE_FILE).read_text(encoding="utf-8"))


def save_state(song_dir: Path, state: dict) -> None:
    tmp = song_dir / (STATE_FILE + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, song_dir / STATE_FILE)


def find_song(cfg: Config, artist: str, title: str) -> Path | None:
    """Folder istniejącej piosenki o tym samym slugu (bez przyrostków), jeśli jest."""
    d = cfg.songs_dir / slugify(artist, title)
    return d if (d / STATE_FILE).exists() else None


def create_song(cfg: Config, audio: Path, artist: str, title: str, lyrics: str,
                quality: str = "fast") -> Path:
    """Nowy folder piosenki (nigdy nie nadpisuje istniejącego) z kopią audio (D10) i tekstem."""
    ok, reason = can_enqueue(artist, title, audio, lyrics)
    if not ok:
        raise PipelineError(reason)
    if quality not in QUALITY:
        raise PipelineError(f"Nieznana jakość: {quality}")
    cfg.songs_dir.mkdir(parents=True, exist_ok=True)
    slug = unique_slug(cfg.songs_dir, slugify(artist, title))
    song_dir = cfg.songs_dir / slug
    song_dir.mkdir()
    source_file = "source" + audio.suffix.lower()
    shutil.copy2(audio, song_dir / source_file)
    (song_dir / LYRICS_INPUT).write_text(lyrics, encoding="utf-8")
    save_state(song_dir, _new_state(artist, title, slug, str(audio), source_file, quality))
    return song_dir


def all_songs(cfg: Config) -> list[Path]:
    if not cfg.songs_dir.exists():
        return []
    dirs = [d for d in cfg.songs_dir.iterdir() if (d / STATE_FILE).exists()]
    return sorted(dirs, key=lambda d: load_state(d).get("created", 0))


def mark_interrupted(song_dir: Path) -> bool:
    """Przy starcie okienka: krok `running` z poprzedniego uruchomienia = przerwany."""
    state = load_state(song_dir)
    changed = False
    for step in state["steps"].values():
        if step["status"] == "running":
            step["status"], step["error"] = "interrupted", "Przerwano (okienko zamknięte w trakcie)."
            changed = True
    if changed:
        state["queued"] = False
        save_state(song_dir, state)
    return changed


def song_status(state: dict) -> str:
    steps = [state["steps"][s]["status"] for s in STEPS]
    if "running" in steps:
        return "running"
    if state.get("queued"):
        return "queued"
    if "error" in steps:
        return "error"
    if "interrupted" in steps or any(s != "done" for s in steps):
        return "interrupted"
    al = state.get("alignment")
    if al and not al.get("ok") and not state.get("accepted"):
        return "needs_review"
    return "ready"


STATUS_LABELS = {
    "queued": "w kolejce", "running": "w trakcie", "interrupted": "przerwana",
    "error": "błąd", "needs_review": "do sprawdzenia", "ready": "gotowa",
}


def library_actions(status: str, has_editor: bool) -> set[str]:
    """Przyciski aktywne dla piosenki (tabela statusów z projektu)."""
    actions = {"log"}
    if status != "running":
        actions.add("delete")
    if status == "queued":
        actions.add("unqueue")
    elif status in ("interrupted", "error"):
        actions.add("resume")
    elif status in ("needs_review", "ready"):
        actions |= {"sing", "lyrics", "import_txt", "recalc", "regenerate"}
        if has_editor:
            actions.add("editor")
        if status == "needs_review":
            actions.add("accept")
    return actions


def can_enqueue(artist: str, title: str, audio: Path | None, lyrics: str) -> tuple[bool, str]:
    if audio is None or not Path(audio).is_file():
        return False, "Wybierz plik audio."
    if not artist.strip() or not title.strip():
        return False, "Uzupełnij wykonawcę i tytuł."
    if not lyrics.strip():
        return False, "Wklej albo pobierz tekst piosenki."
    if REFRAIN_MARKER in lyrics:
        return False, f"Tekst ma znacznik \"{REFRAIN_MARKER}\": wklej refren w to miejsce."
    return True, ""


def template_stale(state: dict, cfg: Config) -> bool:
    """Projekt powstał z innej wersji szablonu niż obecna."""
    t = cfg.template_path
    return bool(state.get("template_hash")) and t.exists() and _hash_files(t) != state["template_hash"]


# --- hashe i pliki --------------------------------------------------------------

def _hash_files(*paths: Path, extra: str = "") -> str:
    h = hashlib.sha256(extra.encode("utf-8"))
    for p in paths:
        h.update(str(p.name).encode("utf-8"))
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    return h.hexdigest()


def _backup(path: Path) -> Path:
    bak = path.with_name(f"{path.name}.{time.strftime('%Y%m%d-%H%M%S')}.bak")
    shutil.copy2(path, bak)
    return bak


def song_files(song_dir: Path, state: dict) -> dict[str, Path]:
    base = state.get("base_name") or ""
    return {
        "txt": song_dir / f"{base}.txt",
        "vocals": song_dir / f"{base}_vocals.mp3",
        "accompaniment": song_dir / f"{base}_accompaniment.mp3",
        "editor": song_dir / f"{base}_editor.html",
        "editor_json": song_dir / f"{base}_editor.json",
        "mid": song_dir / f"{state['slug']}.mid",
        "rpp": song_dir / f"{state['slug']}.rpp",
    }


def import_txt(song_dir: Path, src: Path) -> Path | None:
    """Poprawiony plik UltraStar (np. z edytora nut) zamiast obecnego; stara wersja do .bak."""
    state = load_state(song_dir)
    if not state.get("base_name"):
        raise PipelineError("Piosenka nie ma jeszcze pliku UltraStar (krok ultrasongs niezakończony).")
    load(src)  # odrzuć plik, którego parser nie wczyta
    dst = song_files(song_dir, state)["txt"]
    bak = _backup(dst) if dst.exists() else None
    shutil.copyfile(src, dst)
    return bak


def delete_song(cfg: Config, song_dir: Path, trash: Callable[[Path], None] | None = None) -> None:
    """Przenosi folder piosenki do Kosza (da się przywrócić). Tylko foldery piosenek z songs_dir."""
    song_dir = song_dir.resolve()
    if song_dir.parent != cfg.songs_dir.resolve() or not (song_dir / STATE_FILE).exists():
        raise PipelineError(f"To nie jest folder piosenki: {song_dir}")
    if song_status(load_state(song_dir)) == "running":
        raise PipelineError("Piosenka jest właśnie generowana; usuń ją po zakończeniu.")
    (trash or send_to_recycle_bin)(song_dir)


def send_to_recycle_bin(path: Path) -> None:
    """Kosz Windows przez SHFileOperationW (FO_DELETE + FOF_ALLOWUNDO), bez okien dialogowych."""
    if sys.platform != "win32":
        raise PipelineError("Kosz jest obsługiwany tylko w Windows.")
    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR),
                    ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_uint16), ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]

    op = SHFILEOPSTRUCTW()
    op.wFunc = 3                                  # FO_DELETE
    op.pFrom = str(path) + "\0"                   # lista zakończona podwójnym zerem
    op.fFlags = 0x40 | 0x10 | 0x4 | 0x400         # ALLOWUNDO | NOCONFIRMATION | SILENT | NOERRORUI
    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if result != 0 or op.fAnyOperationsAborted or path.exists():
        raise PipelineError(f"Nie udało się przenieść do Kosza (kod {result}). Zamknij pliki piosenki "
                            "(np. projekt w REAPER) i spróbuj ponownie.")


def accept(song_dir: Path) -> None:
    state = load_state(song_dir)
    state["accepted"] = True
    save_state(song_dir, state)


def set_queued(song_dir: Path, queued: bool, quality: str | None = None) -> None:
    state = load_state(song_dir)
    state["queued"] = queued
    if quality is not None:
        if quality not in QUALITY:
            raise PipelineError(f"Nieznana jakość: {quality}")
        state["quality"] = quality
    save_state(song_dir, state)


# --- kroki ------------------------------------------------------------------------

class _Log:
    def __init__(self, song_dir: Path, on_event: Event | None):
        self.path = song_dir / LOG_FILE
        self.on_event = on_event

    def __call__(self, text: str, kind: str = "log") -> None:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {text}\n")
        if self.on_event:
            self.on_event(kind, text)


def _inputs(step: str, song_dir: Path, state: dict, cfg: Config) -> str | None:
    """Hash wejść kroku albo None, gdy wejścia jeszcze nie istnieją."""
    f = song_files(song_dir, state)
    try:
        if step == "lyrics":
            return _hash_files(song_dir / LYRICS_INPUT)
        if step == "ultrasongs":
            params = json.dumps([state["artist"], state["title"], state["quality"], cfg.language])
            return _hash_files(song_dir / state["source_file"], song_dir / LYRICS_FILE, extra=params)
        if step == "midi":
            return _hash_files(f["txt"], f["vocals"], extra=cfg.align_engine)
        if step == "rpp":
            return _hash_files(cfg.template_path, f["mid"], f["accompaniment"], f["vocals"])
    except (OSError, TypeError):
        return None
    raise ValueError(step)


def _step_lyrics(song_dir: Path, state: dict, cfg: Config, log: _Log) -> None:
    text = (song_dir / LYRICS_INPUT).read_text(encoding="utf-8")
    if REFRAIN_MARKER in text:
        raise PipelineError(f"Tekst ma znacznik \"{REFRAIN_MARKER}\".")
    out = expand(text)
    (song_dir / LYRICS_FILE).write_text(out, encoding="utf-8")
    log(f"Tekst: {sum(1 for l in out.splitlines() if l.strip())} linii.")


REQUIRED_OUTPUT = (".txt", "_vocals.mp3", "_accompaniment.mp3")
OPTIONAL_OUTPUT = ("_editor.html", "_editor.json")


def _step_ultrasongs(song_dir: Path, state: dict, cfg: Config, log: _Log) -> None:
    # ultrasongs powtarza "Wykonawca - Tytuł" w nazwie folderu i pliku; krótki folder roboczy
    # w %TEMP% trzyma ścieżki poniżej limitu 260 znaków Windows także przy długich tytułach.
    out_dir = Path(tempfile.mkdtemp(prefix="kb_"))
    try:
        _ultrasongs_into(out_dir, song_dir, state, cfg, log)
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def _ultrasongs_into(out_dir: Path, song_dir: Path, state: dict, cfg: Config, log: _Log) -> None:
    runs, align_runs = QUALITY[state["quality"]]
    cmd = cfg.ultrasongs_prefix() + [
        "-o", f"whisper_language={cfg.language},transcribe_runs={runs},whisperx_align_runs={align_runs}",
        "process", "--mp3", str(song_dir / state["source_file"]),
        "--lyrics", str(song_dir / LYRICS_FILE),
        "--title", state["title"], "--artist", state["artist"], "--output", str(out_dir),
    ]
    cwd = cfg.ultrasongs_dir if cfg.ultrasongs_cmd is None else None
    if cwd is not None and not Path(cmd[0]).exists():
        raise PipelineError(f"Nie ma ultrasongs: {cmd[0]} (instrukcja: docs/ultrasongs-setup.md).")
    log("ultrasongs: " + " ".join(cmd[-14:]))
    tail = _run_process(cmd, cwd, log)
    if tail is not None:
        raise PipelineError("ultrasongs zakończył się błędem:\n" + "\n".join(tail))

    subdirs = [d for d in out_dir.iterdir() if d.is_dir()]
    if len(subdirs) != 1:
        raise PipelineError(f"Oczekiwano jednego folderu wyniku w {out_dir}, jest {len(subdirs)}.")
    result, base = subdirs[0], subdirs[0].name
    missing = [base + s for s in REQUIRED_OUTPUT if not (result / (base + s)).exists()]
    if missing:
        raise PipelineError("W wyniku ultrasongs brakuje: " + ", ".join(missing))

    files = song_files(song_dir, {**state, "base_name": base})
    if files["txt"].exists() and state.get("txt_hash") and _hash_files(files["txt"]) != state["txt_hash"]:
        bak = _backup(files["txt"])
        log(f"Twoje poprawki w {files['txt'].name} zapisane w {bak.name}.", "warn")
    for suffix in REQUIRED_OUTPUT + OPTIONAL_OUTPUT:
        src = result / (base + suffix)
        if src.exists():
            shutil.copyfile(src, song_dir / (base + suffix))
    state["base_name"] = base
    state["txt_hash"] = _hash_files(files["txt"])


def _step_midi(song_dir: Path, state: dict, cfg: Config, log: _Log) -> None:
    f = song_files(song_dir, state)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", UltraStarWarning)
        try:
            song = load(f["txt"])
        except UltraStarError as e:
            raise PipelineError(f"Plik UltraStar: {e}") from None
    for w in caught:
        log(f"UltraStar: {w.message}")
    octave = resolve_octave(song)
    song_to_midi(song, octave=octave).save(str(f["mid"]))
    engine, note = available_engine(cfg.align_engine)
    if note:
        log(note, "warn")
    log(f"MIDI: oktawa {octave:+d}. Sprawdzam wyrównanie ({engine})...")
    report = check_alignment(song, f["vocals"], engine=engine)
    state["alignment"] = {"ok": report.ok, "offset_ms": report.offset_ms, "message": report.message,
                          "octave": octave}
    state["accepted"] = False
    log(report.message, "log" if report.ok else "warn")


def _step_rpp(song_dir: Path, state: dict, cfg: Config, log: _Log) -> None:
    f = song_files(song_dir, state)
    template = cfg.template_path
    if not template.exists():
        raise PipelineError(f"Brak szablonu projektu REAPER: {template}")
    mid = mido.MidiFile(str(f["mid"]))
    items = [rpp.ItemSpec(p.name, sf.info(str(p)).duration, p.name)
             for p in (f["accompaniment"], f["vocals"])]
    wokal = rpp.ItemSpec(f["mid"].name, mid.length, f"{state['artist']} - {state['title']}")
    try:
        text, warns = rpp.build(template.read_text(encoding="utf-8"), items[0], items[1], wokal, mid)
    except rpp.RppError as e:
        raise PipelineError(f"Szablon {template.name}: {e}") from None
    for w in warns:
        log(w, "warn")
    if f["rpp"].exists() and state.get("rpp_hash") and _hash_files(f["rpp"]) != state["rpp_hash"]:
        bak = _backup(f["rpp"])
        log(f"Projekt był zmieniony w REAPER; poprzednia wersja w {bak.name}.", "warn")
    f["rpp"].write_text(text, encoding="utf-8")
    state["rpp_hash"] = _hash_files(f["rpp"])
    state["template_hash"] = _hash_files(template)
    log(f"Projekt: {f['rpp'].name}")


STEP_FUNCS = {"lyrics": _step_lyrics, "ultrasongs": _step_ultrasongs, "midi": _step_midi, "rpp": _step_rpp}


def run(song_dir: Path, cfg: Config, on_event: Event | None = None, force: set[str] | frozenset = frozenset()) -> str:
    """Wykonuje brakujące kroki piosenki; zwraca jej status. Błąd kroku kończy przebieg (status error)."""
    log = _Log(song_dir, on_event)
    state = load_state(song_dir)
    state["queued"] = False
    save_state(song_dir, state)
    for step in STEPS:
        info = state["steps"][step]
        h = _inputs(step, song_dir, state, cfg)
        if info["status"] == "done" and h is not None and h == info["inputs_hash"] and step not in force:
            continue
        info.update(status="running", error=None)
        save_state(song_dir, state)
        log(f"Krok: {step}", "step")
        try:
            STEP_FUNCS[step](song_dir, state, cfg, log)
        except Exception as e:  # noqa: BLE001  każdy błąd kroku ma trafić do statusu i logu
            msg = str(e) if isinstance(e, PipelineError) else f"{type(e).__name__}: {e}"
            info.update(status="error", error=msg)
            save_state(song_dir, state)
            log(f"BŁĄD w kroku {step}: {msg}", "warn")
            return song_status(state)
        info.update(status="done", inputs_hash=_inputs(step, song_dir, state, cfg), error=None)
        save_state(song_dir, state)
    status = song_status(state)
    log(f"Gotowe: {STATUS_LABELS[status]}.", "step")
    return status


# --- proces ultrasongs -------------------------------------------------------------

def _run_process(cmd: list[str], cwd: Path | None, log: _Log) -> list[str] | None:
    """Uruchamia proces bez okna konsoli, w Job Object (ginie razem z okienkiem).
    None = sukces, inaczej ostatnie linie wyjścia."""
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    try:
        proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, creationflags=flags, env=env)
    except OSError as e:
        raise PipelineError(f"Nie mogę uruchomić ultrasongs: {e}") from None
    job = _KillOnCloseJob.attach(proc)
    tail: list[str] = []
    try:
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace").rstrip()
            if line:
                log(line)
                tail = (tail + [line])[-15:]
        code = proc.wait()
    finally:
        if job:
            job.close()
    return None if code == 0 else tail + [f"(kod wyjścia {code})"]


class _KillOnCloseJob:
    """Windows Job Object z JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE (przez ctypes, bez pywin32).

    Uchwyt zadania trzyma proces okienka; gdy okienko się zamknie albo padnie, system zamyka
    uchwyt i kończy ultrasongs razem z jego procesami potomnymi (np. ffmpeg).
    """

    def __init__(self, handle):
        self.handle = handle

    @classmethod
    def attach(cls, proc: subprocess.Popen) -> "_KillOnCloseJob | None":
        if sys.platform != "win32":
            return None
        import ctypes
        from ctypes import wintypes

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [(n, ctypes.c_ulonglong) for n in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class BASIC(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class EXTENDED(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", BASIC), ("IoInfo", IO_COUNTERS),
                        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateJobObjectW.restype = wintypes.HANDLE
        k32.OpenProcess.restype = wintypes.HANDLE
        job = k32.CreateJobObjectW(None, None)
        if not job:
            return None
        info = EXTENDED()
        info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ok = k32.SetInformationJobObject(wintypes.HANDLE(job), 9, ctypes.byref(info), ctypes.sizeof(info))
        hproc = k32.OpenProcess(0x0100 | 0x0001, False, proc.pid)  # SET_QUOTA | TERMINATE
        if ok and hproc:
            ok = k32.AssignProcessToJobObject(wintypes.HANDLE(job), wintypes.HANDLE(hproc))
        if hproc:
            k32.CloseHandle(wintypes.HANDLE(hproc))
        if not ok:
            k32.CloseHandle(wintypes.HANDLE(job))
            return None
        return cls(job)

    def close(self) -> None:
        import ctypes
        from ctypes import wintypes
        if self.handle:
            ctypes.WinDLL("kernel32").CloseHandle(wintypes.HANDLE(self.handle))
            self.handle = None


# --- jedno okienko naraz ----------------------------------------------------------------

class AlreadyRunning(Exception):
    pass


class InstanceLock:
    """Blokada pliku trzymana przez system: zwalnia się sama, gdy proces padnie (bez PID)."""

    def __init__(self, songs_dir: Path):
        songs_dir.mkdir(parents=True, exist_ok=True)
        self.path = songs_dir / LOCK_FILE
        self.f = open(self.path, "a+b")
        try:
            if sys.platform == "win32":
                import msvcrt
                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.f.close()
            raise AlreadyRunning("Song Studio już działa.") from None

    def release(self) -> None:
        if self.f.closed:
            return
        if sys.platform == "win32":
            import msvcrt
            self.f.seek(0)
            try:
                msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        self.f.close()


# --- szablon ----------------------------------------------------------------------------

def make_template(cfg: Config, project: Path) -> Path:
    """Szablon z istniejącego projektu (np. po blokach E-G): ścieżki i FX, bez elementów."""
    text = rpp.strip_items(project.read_text(encoding="utf-8"))
    rpp.build(text, *(rpp.ItemSpec("x.mp3", 1, "x"),) * 3, mido.MidiFile(ticks_per_beat=960))
    target = cfg.template_path
    if target.exists():
        _backup(target)
    target.write_text(text, encoding="utf-8")
    return target
