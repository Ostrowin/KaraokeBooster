"""Podgląd tekstu karaoke zsynchronizowany z REAPER przez OSC.

REAPER: Preferences -> Control/OSC/web -> Add -> OSC (Default.ReaperOSC),
tryb "Configure device IP+local port", Device IP 127.0.0.1, Device port = --port.

Użycie:
    .venv\\Scripts\\python tools\\lyrics_viewer.py piosenka.txt --port 9000
    .venv\\Scripts\\python tools\\lyrics_viewer.py piosenka.txt --demo   (bez REAPER)
"""

from __future__ import annotations

import argparse
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pythonosc.dispatcher import Dispatcher  # noqa: E402
from pythonosc.osc_server import ThreadingOSCUDPServer  # noqa: E402
from pythonosc.udp_client import SimpleUDPClient  # noqa: E402

from karaokebooster.lyrics import TransportClock, fit_font_size, line_texts, phrases, view_at  # noqa: E402
from karaokebooster.ui import dpi_aware  # noqa: E402
from karaokebooster.ultrastar import UltraStarError, load  # noqa: E402

COLORS = {"past": "#4fc3f7", "current": "#ffd54f", "future": "#eeeeee"}
BG = "#111111"
MAX_LINE_PT = 60   # górny limit; fit() zmniejsza tak, żeby najdłuższa linia się zmieściła
MAX_NEXT_PT = 36


def make_dispatcher(clock: TransportClock, lock: threading.Lock) -> Dispatcher:
    def handler(fn):
        def _h(_addr, *args):
            if args:
                with lock:
                    fn(float(args[0]))
        return _h

    d = Dispatcher()
    d.map("/time", handler(clock.on_time))
    d.map("/play", handler(clock.on_play))
    d.map("/pause", handler(clock.on_pause_or_stop))
    d.map("/stop", handler(clock.on_pause_or_stop))
    return d


def start_osc(clock: TransportClock, lock: threading.Lock, port: int) -> ThreadingOSCUDPServer:
    server = ThreadingOSCUDPServer(("127.0.0.1", port), make_dispatcher(clock, lock))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


# Akcje REAPER wysyłane przez OSC (wzorzec ACTION z Default.ReaperOSC: /action <numer>)
ACTION_PLAY_PAUSE = 40073   # Transport: Play/pause
ACTION_GO_TO_START = 40042  # Transport: Go to start of project
HINT = "Spacja: start / pauza    Home: od początku    Esc: zamknij tekst"
NO_REAPER = ("REAPER nie odpowiada na spację: ustaw w REAPER port nasłuchu OSC {port} "
             "(docs/reaper-setup.md, blok H) albo wciśnij spację w oknie REAPER.")


class ReaperRemote:
    """Sterowanie transportem REAPER przez OSC (REAPER musi nasłuchiwać na `port`)."""

    def __init__(self, port: int):
        self.port = port
        self.client = SimpleUDPClient("127.0.0.1", port) if port else None

    def action(self, number: int) -> bool:
        if not self.client:
            return False
        try:
            self.client.send_message("/action", number)
            return True
        except OSError:
            return False


class ViewerApp:
    def __init__(self, root: tk.Tk, song, clock: TransportClock, lock: threading.Lock,
                 remote: ReaperRemote | None = None):
        self.root, self.clock, self.lock, self.remote = root, clock, lock, remote
        self.lines = phrases(song)
        self.texts = line_texts(self.lines)
        self.warning = ""
        root.title(f"KaraokeBooster - {song.artist} - {song.title}")
        root.configure(bg=BG)
        scale = root.winfo_fpixels("1i") / 96
        root.geometry(f"{int(1100 * scale)}x{int(300 * scale)}")
        self.font = tkfont.Font(root, family="Segoe UI", size=MAX_LINE_PT, weight="bold")
        self.next_font = tkfont.Font(root, family="Segoe UI", size=MAX_NEXT_PT)
        self.line = tk.Text(root, height=1, bg=BG, bd=0, font=self.font, highlightthickness=0, wrap="none",
                            cursor="arrow", takefocus=0)
        self.next = tk.Label(root, bg=BG, fg="#777777", font=self.next_font)
        self.info = tk.Label(root, bg=BG, fg="#555555", font=("Segoe UI", 12))
        for tag, color in COLORS.items():
            self.line.tag_configure(tag, foreground=color)
        self.line.tag_configure("center", justify="center")
        # tekst na środku wysokości okna: puste ramki nad i pod nim dzielą wolne miejsce
        self.info.pack(side="bottom", fill="x", pady=8)
        tk.Frame(root, bg=BG).pack(fill="both", expand=True)
        self.line.pack(fill="x", pady=(0, 10))
        self.next.pack(fill="x")
        tk.Frame(root, bg=BG).pack(fill="both", expand=True)
        root.bind("<Configure>", self.fit)
        root.bind("<space>", lambda _e: self.send(ACTION_PLAY_PAUSE))
        root.bind("<Home>", lambda _e: self.send(ACTION_GO_TO_START))
        self._fitted_width = 0
        self.tick()

    def fit(self, _event=None) -> None:
        """Rozmiar czcionki tak, żeby najdłuższa linia piosenki mieściła się w oknie."""
        width = self.root.winfo_width()
        if width <= 1 or width == self._fitted_width:
            return
        self._fitted_width = width
        usable = width * 0.94

        def measure(font):
            def m(size, text):
                font.configure(size=size)
                return font.measure(text)
            return m
        self.font.configure(size=fit_font_size(self.texts, measure(self.font), usable, MAX_LINE_PT, 14))
        self.next_font.configure(size=fit_font_size(self.texts, measure(self.next_font), usable, MAX_NEXT_PT, 10))

    def send(self, action: int) -> None:
        if not self.remote or not self.remote.action(action):
            self.warning = NO_REAPER.format(port=self.remote.port if self.remote else "-")
            return
        if action == ACTION_PLAY_PAUSE:
            with self.lock:
                was_playing = self.clock.playing
            # REAPER odpowiada przez OSC w ułamku sekundy; brak zmiany = REAPER nie nasłuchuje
            self.root.after(1500, lambda: self._check_response(was_playing))

    def _check_response(self, was_playing: bool) -> None:
        with self.lock:
            playing = self.clock.playing
        self.warning = "" if playing != was_playing else NO_REAPER.format(port=self.remote.port)

    def tick(self):
        with self.lock:
            t = self.clock.position()
            playing = self.clock.playing
        v = view_at(self.lines, t)
        self.line.configure(state="normal")
        self.line.delete("1.0", "end")
        for s in v.line:
            self.line.insert("end", s.text, (s.state, "center"))
        self.line.configure(state="disabled")
        self.next.configure(text=v.next_line)
        cd = f"   za {v.countdown_s:.1f} s" if v.countdown_s and v.countdown_s < 5 else ""
        state = f"{'▶' if playing else '⏸'} {t:6.1f} s{cd}"
        self.info.configure(text=self.warning or f"{state}      {HINT}",
                            fg="#e57373" if self.warning else "#555555")
        self.root.after(30, self.tick)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Podgląd tekstu zsynchronizowany z REAPER (OSC).")
    p.add_argument("song", type=Path)
    p.add_argument("--port", type=int, default=9000, help="port UDP, na który REAPER wysyła OSC")
    p.add_argument("--reaper-port", type=int, default=8000,
                   help="port, na którym REAPER nasłuchuje OSC (spacja = start/pauza; 0 = wyłączone)")
    p.add_argument("--offset-ms", type=float, default=0.0,
                   help="opóźnij tekst o tyle ms (np. opóźnienie wyjścia audio)")
    p.add_argument("--demo", action="store_true", help="bez REAPER: startuje od 0 s")
    p.add_argument("--fullscreen", action="store_true", help="pełny ekran (Esc zamyka)")
    args = p.parse_args(argv)

    try:
        song = load(args.song)
    except (UltraStarError, OSError) as e:
        print(f"BŁĄD: {e}", file=sys.stderr)
        return 1

    lock = threading.Lock()
    clock = TransportClock(offset_s=args.offset_ms / 1000)
    if args.demo:
        # w demo zegar sam "dostaje" /time, żeby nie stawał po STALE_S
        clock.on_time(0.0)
        clock.on_play(1)
    else:
        try:
            start_osc(clock, lock, args.port)
        except OSError as e:
            print(f"BŁĄD: nie mogę nasłuchiwać na porcie {args.port}: {e}", file=sys.stderr)
            return 1
        print(f"Nasłuchuję OSC z REAPER na 127.0.0.1:{args.port}")

    dpi_aware()
    root = tk.Tk()
    remote = None if args.demo else ReaperRemote(args.reaper_port)
    app = ViewerApp(root, song, clock, lock, remote)
    root.bind("<Escape>", lambda _e: root.destroy())
    if args.fullscreen:
        root.attributes("-fullscreen", True)
    root.focus_force()
    if args.demo:
        def keepalive():
            with lock:
                clock.on_time(clock.position() + clock.offset_s)
            root.after(200, keepalive)
        keepalive()
    root.mainloop()
    del app
    return 0


if __name__ == "__main__":
    sys.exit(main())
