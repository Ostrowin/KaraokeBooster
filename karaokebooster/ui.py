"""Drobne wspólne rzeczy dla okienek tkinter (Song Studio, podgląd tekstu)."""

from __future__ import annotations

import sys


def dpi_aware() -> None:
    """Ostre okno i prawdziwe rozmiary przy skalowaniu ekranu Windows (np. 150%).
    Wywołać przed utworzeniem tk.Tk()."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
