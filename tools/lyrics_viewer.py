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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pythonosc.dispatcher import Dispatcher  # noqa: E402
from pythonosc.osc_server import ThreadingOSCUDPServer  # noqa: E402

from karaokebooster.lyrics import TransportClock, phrases, view_at  # noqa: E402
from karaokebooster.ultrastar import UltraStarError, load  # noqa: E402

COLORS = {"past": "#4fc3f7", "current": "#ffd54f", "future": "#eeeeee"}
BG = "#111111"


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


class ViewerApp:
    def __init__(self, root: tk.Tk, song, clock: TransportClock, lock: threading.Lock):
        self.root, self.clock, self.lock = root, clock, lock
        self.lines = phrases(song)
        root.title(f"KaraokeBooster - {song.artist} - {song.title}")
        root.configure(bg=BG)
        root.geometry("1100x300")
        self.line = tk.Text(root, height=1, bg=BG, bd=0, font=("Segoe UI", 40, "bold"),
                            highlightthickness=0, wrap="none")
        self.next = tk.Label(root, bg=BG, fg="#777777", font=("Segoe UI", 26))
        self.info = tk.Label(root, bg=BG, fg="#555555", font=("Segoe UI", 12))
        for tag, color in COLORS.items():
            self.line.tag_configure(tag, foreground=color)
        self.line.tag_configure("center", justify="center")
        self.line.pack(fill="x", pady=(50, 10))
        self.next.pack(fill="x")
        self.info.pack(side="bottom", fill="x", pady=8)
        self.tick()

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
        self.info.configure(text=f"{'▶' if playing else '⏸'} {t:6.1f} s{cd}")
        self.root.after(30, self.tick)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Podgląd tekstu zsynchronizowany z REAPER (OSC).")
    p.add_argument("song", type=Path)
    p.add_argument("--port", type=int, default=9000, help="port UDP, na który REAPER wysyła OSC")
    p.add_argument("--offset-ms", type=float, default=0.0,
                   help="opóźnij tekst o tyle ms (np. opóźnienie wyjścia audio)")
    p.add_argument("--demo", action="store_true", help="bez REAPER: startuje od 0 s")
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

    root = tk.Tk()
    app = ViewerApp(root, song, clock, lock)
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
