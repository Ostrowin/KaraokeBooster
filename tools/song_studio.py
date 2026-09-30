"""Song Studio: nowa piosenka z mp3 jednym kliknięciem (docs/designs/song-studio.md).

Zakładka "Dodaj piosenkę": plik audio, wykonawca/tytuł, tekst (wklejony albo z tekstowo.pl),
jakość, kolejka. Zakładka "Biblioteka": status piosenek i "Śpiewaj" (REAPER + tekst na ekranie).

Okienko tylko rysuje i wywołuje karaokebooster.pipeline; reguły (przyciski wg statusu itd.)
są tam i mają testy. Worker w osobnym wątku wysyła zdarzenia przez queue.Queue.

Użycie (bez okna konsoli):
    .venv\\Scripts\\pythonw.exe tools\\song_studio.py
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from karaokebooster import lyrics_text  # noqa: E402
from karaokebooster import pipeline as P  # noqa: E402

TOOLS = Path(__file__).resolve().parent
AUDIO_TYPES = [("Audio", "*.mp3 *.wav *.flac *.ogg *.m4a"), ("Wszystkie pliki", "*.*")]
QUALITY_LABELS = {"fast": "Szybka (~30-40 min)", "accurate": "Dokładna (~1-2 h)"}
NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
REAPER_REMINDER = ("Jeśli ten projekt jest otwarty w REAPER, zamknij go (bez zapisywania zmian), "
                   "zanim projekt zostanie przebudowany.\n\nKontynuować?")


@dataclass
class Job:
    song_dir: Path
    force: frozenset = field(default_factory=frozenset)


class Worker(threading.Thread):
    """Jeden wątek, kolejka po kolei (GPU 4 GB). Pomija piosenki zdjęte z kolejki."""

    def __init__(self, cfg: P.Config, ui: queue.Queue):
        super().__init__(daemon=True)
        self.cfg, self.ui = cfg, ui
        self.jobs: queue.Queue[Job] = queue.Queue()
        self.current: Path | None = None

    def submit(self, song_dir: Path, force=frozenset()) -> None:
        P.set_queued(song_dir, True)
        self.jobs.put(Job(song_dir, frozenset(force)))
        self.ui.put(("refresh", "", ""))

    def run(self) -> None:
        while True:
            job = self.jobs.get()
            try:
                if not P.load_state(job.song_dir).get("queued"):
                    continue  # zdjęta z kolejki
                self.current = job.song_dir
                name = job.song_dir.name
                P.run(job.song_dir, self.cfg, lambda k, t: self.ui.put((k, name, t)), job.force)
            except Exception as e:  # noqa: BLE001  worker nie może zginąć po cichu
                self.ui.put(("warn", job.song_dir.name, f"Błąd: {type(e).__name__}: {e}"))
            finally:
                self.current = None
                self.ui.put(("refresh", "", ""))


class SongStudio:
    def __init__(self, root: tk.Tk, cfg: P.Config):
        self.root, self.cfg = root, cfg
        self.ui: queue.Queue = queue.Queue()
        self.worker = Worker(cfg, self.ui)
        self.viewer: subprocess.Popen | None = None
        self.progress: dict[str, str] = {}   # slug -> ostatni krok / linia logu
        self.autofill: tuple[str, str] = ("", "")

        root.title("KaraokeBooster: Song Studio")
        self.scale = scale = root.winfo_fpixels("1i") / 96  # skalowanie ekranu Windows
        root.geometry(f"{int(980 * scale)}x{int(720 * scale)}")
        root.minsize(int(820 * scale), int(600 * scale))
        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        self.nb = nb
        self.add_tab = ttk.Frame(nb, padding=10)
        self.lib_tab = ttk.Frame(nb, padding=10)
        nb.add(self.add_tab, text="Dodaj piosenkę")
        nb.add(self.lib_tab, text="Biblioteka")
        self._build_add()
        self._build_library()
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        for d in P.all_songs(cfg):
            P.mark_interrupted(d)
        self.worker.start()
        for d in P.all_songs(cfg):
            if P.load_state(d).get("queued"):
                self.worker.jobs.put(Job(d))
        self.refresh()
        self.poll()

    # --- zakładka Dodaj -----------------------------------------------------------

    def _build_add(self) -> None:
        f = self.add_tab
        f.columnconfigure(1, weight=1)
        self.audio_var, self.artist_var, self.title_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.quality_var = tk.StringVar(value="fast")
        self.fetch_status = tk.StringVar()

        ttk.Label(f, text="Plik audio").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Entry(f, textvariable=self.audio_var, state="readonly").grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(f, text="Wybierz…", command=self.pick_audio).grid(row=0, column=2)
        ttk.Label(f, text="Wykonawca").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Entry(f, textvariable=self.artist_var).grid(row=1, column=1, columnspan=2, sticky="ew", padx=6)
        ttk.Label(f, text="Tytuł").grid(row=2, column=0, sticky="w", pady=3)
        ttk.Entry(f, textvariable=self.title_var).grid(row=2, column=1, columnspan=2, sticky="ew", padx=6)

        row = ttk.Frame(f)
        row.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(8, 2))
        ttk.Label(row, text="Tekst").pack(side="left")
        self.fetch_btn = ttk.Button(row, text="Pobierz z tekstowo.pl", command=self.fetch_lyrics)
        self.fetch_btn.pack(side="left", padx=8)
        ttk.Label(row, textvariable=self.fetch_status, foreground="#666").pack(side="left")

        box = ttk.Frame(f)
        box.grid(row=4, column=0, columnspan=3, sticky="nsew")
        f.rowconfigure(4, weight=1)
        self.lyrics = tk.Text(box, height=12, wrap="word", undo=True, font=("Consolas", 10))
        sb = ttk.Scrollbar(box, command=self.lyrics.yview)
        self.lyrics.configure(yscrollcommand=sb.set)
        self.lyrics.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        ttk.Label(f, text="Linia po linii. \"/x2\" na końcu linii powtarza zwrotkę do tego miejsca.",
                  foreground="#666").grid(row=5, column=0, columnspan=3, sticky="w")

        q = ttk.Frame(f)
        q.grid(row=6, column=0, columnspan=3, sticky="ew", pady=6)
        ttk.Label(q, text="Jakość").pack(side="left")
        for key, label in QUALITY_LABELS.items():
            ttk.Radiobutton(q, text=label, value=key, variable=self.quality_var).pack(side="left", padx=8)
        ttk.Button(q, text="Dodaj do kolejki", command=self.enqueue).pack(side="right")

        ttk.Label(f, text="Kolejka", font=("Segoe UI", 10, "bold")).grid(row=7, column=0, sticky="w", pady=(8, 2))
        self.queue_view = ttk.Treeview(f, columns=("song", "status", "step"), show="headings", height=5)
        for col, text, w in (("song", "Piosenka", 320), ("status", "Status", 100), ("step", "Postęp", 380)):
            self.queue_view.heading(col, text=text)
            self.queue_view.column(col, width=int(w * self.scale), stretch=col == "step")
        self.queue_view.grid(row=8, column=0, columnspan=3, sticky="nsew")
        self.queue_view.bind("<Double-1>", lambda _e: self.show_log(self._selected(self.queue_view)))

    def pick_audio(self) -> None:
        path = filedialog.askopenfilename(title="Wybierz plik audio", filetypes=AUDIO_TYPES)
        if not path:
            return
        self.audio_var.set(path)
        artist, title = P.split_filename(path)
        # nadpisuj tylko pola, których użytkownik nie zmienił ręcznie
        if self.artist_var.get() in ("", self.autofill[0]):
            self.artist_var.set(artist)
        if self.title_var.get() in ("", self.autofill[1]):
            self.title_var.set(title)
        self.autofill = (artist, title)

    def fetch_lyrics(self) -> None:
        artist, title = self.artist_var.get().strip(), self.title_var.get().strip()
        if not title:
            messagebox.showinfo("Tekst", "Uzupełnij najpierw tytuł (i wykonawcę).")
            return
        if self.lyrics.get("1.0", "end").strip() and not messagebox.askyesno(
                "Tekst", "Pole tekstu nie jest puste. Zastąpić pobranym tekstem?"):
            return
        self.fetch_btn.state(["disabled"])
        self.fetch_status.set("Pobieram…")

        def work():
            try:
                self.ui.put(("lyrics_ok", "", lyrics_text.fetch(artist, title)))
            except lyrics_text.LyricsNotFound as e:
                self.ui.put(("lyrics_err", "", f"{e} Wklej tekst ręcznie."))
            except OSError as e:
                self.ui.put(("lyrics_err", "", f"Brak połączenia z tekstowo.pl ({e}). Wklej tekst ręcznie."))
        threading.Thread(target=work, daemon=True).start()

    def enqueue(self) -> None:
        audio = Path(self.audio_var.get()) if self.audio_var.get() else None
        artist, title = self.artist_var.get().strip(), self.title_var.get().strip()
        text = self.lyrics.get("1.0", "end").strip() + "\n"
        ok, reason = P.can_enqueue(artist, title, audio, text)
        if not ok:
            messagebox.showwarning("Dodaj piosenkę", reason)
            return
        existing = P.find_song(self.cfg, artist, title)
        if existing:
            answer = messagebox.askyesnocancel(
                "Piosenka już jest",
                f"\"{artist} - {title}\" jest już w bibliotece.\n\n"
                "Tak: pokaż istniejącą\nNie: dodaj jako nową (osobny folder)\nAnuluj: nic nie rób")
            if answer is None:
                return
            if answer:
                self.nb.select(self.lib_tab)
                self._select(self.lib_view, existing.name)
                return
        try:
            song_dir = P.create_song(self.cfg, audio, artist, title, text, self.quality_var.get())
        except (P.PipelineError, OSError) as e:
            messagebox.showerror("Dodaj piosenkę", str(e))
            return
        self.worker.submit(song_dir)
        self.audio_var.set("")
        self.artist_var.set("")
        self.title_var.set("")
        self.autofill = ("", "")
        self.lyrics.delete("1.0", "end")
        self.fetch_status.set(f"Dodano: {artist} - {title}")

    # --- zakładka Biblioteka --------------------------------------------------------------

    def _build_library(self) -> None:
        f = self.lib_tab
        f.columnconfigure(0, weight=1)
        f.rowconfigure(0, weight=1)
        self.lib_view = ttk.Treeview(f, columns=("song", "status", "note"), show="headings")
        for col, text, w in (("song", "Piosenka", 320), ("status", "Status", 110), ("note", "Uwagi", 420)):
            self.lib_view.heading(col, text=text)
            self.lib_view.column(col, width=int(w * self.scale), stretch=col == "note")
        self.lib_view.grid(row=0, column=0, sticky="nsew")
        self.lib_view.bind("<<TreeviewSelect>>", lambda _e: self.update_buttons())
        self.lib_view.bind("<Double-1>", lambda _e: self.do_action("sing"))

        bar = ttk.Frame(f)
        bar.grid(row=1, column=0, sticky="ew", pady=6)
        self.buttons: dict[str, ttk.Button] = {}
        for key, label in (("sing", "Śpiewaj"), ("log", "Log"), ("resume", "Wznów"),
                           ("editor", "Edytor nut"), ("import_txt", "Importuj .txt"), ("recalc", "Przelicz"),
                           ("accept", "Akceptuj mimo to"), ("regenerate", "Generuj ponownie"),
                           ("unqueue", "Usuń z kolejki")):
            b = ttk.Button(bar, text=label, command=lambda k=key: self.do_action(k))
            b.pack(side="left", padx=2)
            self.buttons[key] = b

        foot = ttk.Frame(f)
        foot.grid(row=2, column=0, sticky="ew")
        self.template_info = tk.StringVar()
        ttk.Label(foot, textvariable=self.template_info, foreground="#666").pack(side="left")
        ttk.Button(foot, text="Odśwież projekty z szablonu", command=self.refresh_projects).pack(side="right")
        ttk.Button(foot, text="Ustaw szablon z projektu…", command=self.set_template).pack(side="right", padx=6)
        ttk.Label(f, text="\"Śpiewaj\" otwiera projekt w REAPER i tekst na pełnym ekranie (Esc zamyka). "
                          "Start: spacja w REAPER.", foreground="#666").grid(row=3, column=0, sticky="w", pady=(6, 0))

    def _song_row(self, d: Path) -> tuple[str, str, str, set[str]]:
        st = P.load_state(d)
        status = P.song_status(st)
        files = P.song_files(d, st)
        note = ""
        if status == "error":
            step = next(s for s in P.STEPS if st["steps"][s]["status"] == "error")
            note = f"krok {step}: " + (st["steps"][step]["error"] or "").splitlines()[0]
        elif status == "interrupted":
            note = "przerwana, kliknij Wznów"
        elif st.get("alignment"):
            note = st["alignment"]["message"]
            if st.get("accepted"):
                note = "zaakceptowana mimo ostrzeżenia. " + note
        if status in ("ready", "needs_review") and P.template_stale(st, self.cfg):
            note = "projekt nieaktualny (zmieniony szablon). " + note
        actions = P.library_actions(status, st.get("base_name") is not None and files["editor"].exists())
        return f"{st['artist']} - {st['title']}", status, note, actions

    def refresh(self) -> None:
        sel_lib, sel_q = self._selected(self.lib_view), self._selected(self.queue_view)
        self.rows: dict[str, set[str]] = {}
        self.lib_view.delete(*self.lib_view.get_children())
        self.queue_view.delete(*self.queue_view.get_children())
        for d in P.all_songs(self.cfg):
            try:
                name, status, note, actions = self._song_row(d)
            except (OSError, ValueError, KeyError):
                continue
            self.rows[d.name] = actions
            self.lib_view.insert("", "end", iid=d.name, values=(name, P.STATUS_LABELS[status], note))
            if status in ("queued", "running"):
                self.queue_view.insert("", "end", iid=d.name,
                                       values=(name, P.STATUS_LABELS[status], self.progress.get(d.name, "")))
        self._select(self.lib_view, sel_lib)
        self._select(self.queue_view, sel_q)
        t = self.cfg.template_path
        self.template_info.set(f"Szablon: {t}" if t.exists()
                               else f"Brak szablonu {t.name}: kliknij \"Ustaw szablon z projektu…\"")
        self.update_buttons()

    def update_buttons(self) -> None:
        actions = self.rows.get(self._selected(self.lib_view) or "", set())
        for key, b in self.buttons.items():
            b.state(["!disabled"] if key in actions else ["disabled"])

    @staticmethod
    def _selected(view: ttk.Treeview) -> str | None:
        sel = view.selection()
        return sel[0] if sel else None

    @staticmethod
    def _select(view: ttk.Treeview, iid: str | None) -> None:
        if iid and view.exists(iid):
            view.selection_set(iid)
            view.see(iid)

    def do_action(self, key: str) -> None:
        slug = self._selected(self.lib_view)
        if not slug or key not in self.rows.get(slug, set()):
            return
        d = self.cfg.songs_dir / slug
        st = P.load_state(d)
        files = P.song_files(d, st)
        if key == "sing":
            self.sing(d, st, files)
        elif key == "log":
            self.show_log(slug)
        elif key == "resume":
            self.worker.submit(d)
        elif key == "editor":
            os.startfile(files["editor"])  # noqa: S606  plik lokalny z ultrasongs
        elif key == "import_txt":
            src = filedialog.askopenfilename(title="Poprawiony plik UltraStar",
                                             filetypes=[("UltraStar", "*.txt"), ("Wszystkie pliki", "*.*")])
            if not src:
                return
            try:
                bak = P.import_txt(d, Path(src))
            except Exception as e:  # noqa: BLE001  parser zgłasza różne błędy formatu
                messagebox.showerror("Importuj .txt", f"Nie mogę użyć tego pliku: {e}")
                return
            if messagebox.askokcancel("Importuj .txt", (f"Poprzednia wersja: {bak.name}\n\n" if bak else "")
                                      + REAPER_REMINDER):
                self.worker.submit(d, {"midi", "rpp"})
        elif key == "recalc":
            if messagebox.askokcancel("Przelicz", REAPER_REMINDER):
                self.worker.submit(d, {"midi", "rpp"})
        elif key == "accept":
            P.accept(d)
            self.refresh()
        elif key == "regenerate":
            self.regenerate(d, st)
        elif key == "unqueue":
            P.set_queued(d, False)
            self.refresh()

    def regenerate(self, d: Path, st: dict) -> None:
        win = tk.Toplevel(self.root)
        win.title("Generuj ponownie")
        win.transient(self.root)
        win.grab_set()
        q = tk.StringVar(value="accurate" if st["quality"] == "fast" else st["quality"])
        ttk.Label(win, text=f"{st['artist']} - {st['title']}\nultrasongs od nowa (Twoje poprawki .txt "
                            "trafią do kopii .bak).", padding=10).pack()
        for key, label in QUALITY_LABELS.items():
            ttk.Radiobutton(win, text=label, value=key, variable=q).pack(anchor="w", padx=16)

        def ok():
            win.destroy()
            if messagebox.askokcancel("Generuj ponownie", f"To potrwa: {QUALITY_LABELS[q.get()]}.\n\n"
                                      + REAPER_REMINDER):
                P.set_queued(d, True, quality=q.get())
                self.worker.submit(d, {"ultrasongs"})
        row = ttk.Frame(win, padding=10)
        row.pack()
        ttk.Button(row, text="Generuj", command=ok).pack(side="left", padx=4)
        ttk.Button(row, text="Anuluj", command=win.destroy).pack(side="left")

    def refresh_projects(self) -> None:
        if not self.cfg.template_path.exists():
            messagebox.showwarning("Odśwież projekty", "Najpierw ustaw szablon.")
            return
        songs = [d for d in P.all_songs(self.cfg) if P.song_status(P.load_state(d)) in ("ready", "needs_review")]
        if not songs:
            messagebox.showinfo("Odśwież projekty", "Brak gotowych piosenek.")
            return
        if messagebox.askokcancel("Odśwież projekty", f"Przebudować {len(songs)} projekt(y)?\n\n" + REAPER_REMINDER):
            for d in songs:
                self.worker.submit(d, {"rpp"})

    def set_template(self) -> None:
        src = filedialog.askopenfilename(title="Projekt REAPER ze ścieżkami Podklad, ghost, wokal",
                                         filetypes=[("REAPER", "*.rpp")])
        if not src:
            return
        try:
            target = P.make_template(self.cfg, Path(src))
        except Exception as e:  # noqa: BLE001  RppError, OSError, błędy kodowania
            messagebox.showerror("Szablon", f"Nie mogę użyć tego projektu: {e}")
            return
        messagebox.showinfo("Szablon", f"Zapisano {target}.\nKliknij \"Odśwież projekty z szablonu\", "
                                       "żeby przenieść go do piosenek.")
        self.refresh()

    def sing(self, d: Path, st: dict, files: dict[str, Path]) -> None:
        if not self.cfg.reaper_exe.exists():
            messagebox.showerror("Śpiewaj", f"Nie ma REAPER: {self.cfg.reaper_exe}\n"
                                            "(ścieżka w karaokebooster.local.toml, pole reaper_exe)")
            return
        if P.song_status(st) == "needs_review" and not messagebox.askokcancel(
                "Śpiewaj", "Wyrównanie nut ma ostrzeżenie:\n\n" + st["alignment"]["message"] + "\n\nŚpiewać mimo to?"):
            return
        self.close_viewer()
        subprocess.Popen([str(self.cfg.reaper_exe), str(files["rpp"])])
        pyw = Path(sys.executable).with_name("pythonw.exe")
        self.viewer = subprocess.Popen(
            [str(pyw if pyw.exists() else sys.executable), str(TOOLS / "lyrics_viewer.py"), str(files["txt"]),
             "--port", str(self.cfg.osc_port), "--offset-ms", str(self.cfg.offset_ms), "--fullscreen"],
            creationflags=NO_WINDOW)

    def close_viewer(self) -> None:
        if self.viewer and self.viewer.poll() is None:
            self.viewer.terminate()
            try:
                self.viewer.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.viewer.kill()
        self.viewer = None

    def show_log(self, slug: str | None) -> None:
        if not slug:
            return
        path = self.cfg.songs_dir / slug / P.LOG_FILE
        win = tk.Toplevel(self.root)
        win.title(f"Log: {slug}")
        win.geometry("820x480")
        text = tk.Text(win, wrap="none", font=("Consolas", 9))
        sb = ttk.Scrollbar(win, command=text.yview)
        text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        text.insert("1.0", path.read_text(encoding="utf-8", errors="replace") if path.exists() else "(pusty log)")
        text.see("end")
        text.configure(state="disabled")

    # --- pętla zdarzeń ------------------------------------------------------------------------

    def poll(self) -> None:
        refresh = False
        try:
            while True:
                kind, slug, text = self.ui.get_nowait()
                if kind == "lyrics_ok":
                    self.lyrics.delete("1.0", "end")
                    self.lyrics.insert("1.0", text)
                    marker = lyrics_text.REFRAIN_MARKER in text
                    self.fetch_status.set("Pobrano. Sprawdź tekst" + (": brakuje refrenu, wklej go w "
                                          "miejsce znacznika!" if marker else " przed dodaniem."))
                    self.fetch_btn.state(["!disabled"])
                elif kind == "lyrics_err":
                    self.fetch_status.set(text)
                    self.fetch_btn.state(["!disabled"])
                elif kind == "refresh":
                    refresh = True
                else:
                    self.progress[slug] = text.splitlines()[0][:160] if text else ""
                    if kind == "step" and self.queue_view.exists(slug):
                        self.queue_view.set(slug, "status", P.STATUS_LABELS["running"])
                    if kind in ("step", "warn"):
                        refresh = True
                    elif self.queue_view.exists(slug):
                        self.queue_view.set(slug, "step", self.progress[slug])
        except queue.Empty:
            pass
        if refresh:
            self.refresh()
        self.root.after(100, self.poll)

    def on_close(self) -> None:
        if self.worker.current is not None and not messagebox.askyesno(
                "Zamknij", "Trwa generowanie piosenki. Zamknięcie przerwie je (dokończysz przyciskiem "
                           "Wznów). Zamknąć?"):
            return
        self.close_viewer()
        self.root.destroy()


def dpi_aware() -> None:
    """Ostre okno przy skalowaniu ekranu Windows (np. 150%)."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass


def main() -> int:
    dpi_aware()
    try:
        cfg = P.load_config()
    except (P.PipelineError, ValueError) as e:
        messagebox.showerror("Song Studio", f"Błąd konfiguracji: {e}")
        return 1
    try:
        lock = P.InstanceLock(cfg.songs_dir)
    except P.AlreadyRunning as e:
        messagebox.showinfo("Song Studio", str(e))
        return 1
    root = tk.Tk()
    try:
        SongStudio(root, cfg)
        root.mainloop()
    finally:
        lock.release()
    return 0


if __name__ == "__main__":
    sys.exit(main())
