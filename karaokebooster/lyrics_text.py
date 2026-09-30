"""Tekst piosenki przed ultrasongs: rozwijanie powtórzeń, czyszczenie, pobieranie z tekstowo.pl.

Song Studio (docs/designs/song-studio.md). Reguły czyszczenia działają w kolejności 2 → 1 → 3:
  2. zwrotka będąca samą etykietą refrenu ("Ref.", "[Refren] x2") dostaje tekst pierwszego
     refrenu; gdy refrenu nigdzie nie ma, zostaje REFRAIN_MARKER (okienko blokuje dodanie);
  1. etykiety na początku zwrotki ("Ref.:", "[Refren]", "Zwrotka 1:") są usuwane;
  3. "x2", "(x2)", "2x" na końcu linii zamieniane na składnię "/x2" z expand().
"""

from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser

# --- rozwijanie powtórzeń (przeniesione z tools/expand_lyrics.py) ---------

MARKER = re.compile(r"\s*/x(\d+)\s*$", re.IGNORECASE)


def expand(text: str) -> str:
    """Rozwija "/xN": w zwrotce z markerem linie od początku zwrotki do markera powtarzają się
    N razy, a linie po markerze zostają raz."""
    out = []
    for stanza in re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip()):
        lines = [l.rstrip() for l in stanza.strip().splitlines()]
        for i, line in enumerate(lines):
            m = MARKER.search(line)
            if m:
                block = lines[:i] + [line[: m.start()]]
                out.append("\n".join(block * int(m.group(1)) + lines[i + 1:]))
                break
        else:
            out.append("\n".join(lines))
    return "\n\n".join(out) + "\n"


# --- czyszczenie tekstu z tekstowo.pl ------------------------------------

REFRAIN_MARKER = "!!! WKLEJ REFREN !!!"

_REPEAT = r"(?:[x×]\s*(\d+)|(\d+)\s*[x×])"
# etykieta refrenu, np. "Ref.", "Ref:", "Refren 2:", "[Ref]", "/Ref./", "(Refren)"
_CHORUS = r"(?:ref(?:ren)?|refrain|chorus)"
_LABEL_WORDS = _CHORUS + r"|zwrotka|verse|bridge|mostek|intro|outro|przedrefren|pre-?chorus"
LABEL = re.compile(
    r"^\s*[\[(/]?\s*(?P<word>" + _LABEL_WORDS + r")(?!\w)\.?\s*\d*\s*\.?\s*[\])/]?\s*:?\s*",
    re.IGNORECASE)
REPEAT_AT_END = re.compile(r"\s*[\[(]?\s*" + _REPEAT + r"\s*[\])]?\s*$", re.IGNORECASE)


def _stanzas(text: str) -> list[list[str]]:
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip())
    return [[l.strip() for l in b.splitlines() if l.strip()] for b in blocks if b.strip()]


def _label(line: str) -> tuple[str | None, str]:
    """(słowo etykiety małymi literami albo None, reszta linii po etykiecie)."""
    m = LABEL.match(line)
    if not m:
        return None, line
    return m.group("word").lower(), line[m.end():].strip()


def _is_chorus(word: str | None) -> bool:
    return word is not None and re.fullmatch(_CHORUS, word, re.IGNORECASE) is not None


def _repeat_count(text: str) -> int | None:
    m = REPEAT_AT_END.fullmatch(text) if text else None
    if not m:
        return None
    return int(m.group(1) or m.group(2))


def clean(text: str) -> str:
    stanzas = _stanzas(text)

    # reguła 2: zastępniki refrenu
    chorus: list[str] | None = None
    for st in stanzas:
        word, rest = _label(st[0])
        if _is_chorus(word) and (rest and _repeat_count(rest) is None or len(st) > 1):
            chorus = ([rest] if rest else []) + st[1:]
            break
    out: list[list[str]] = []
    for st in stanzas:
        word, rest = _label(st[0])
        placeholder = len(st) == 1 and _is_chorus(word) and (not rest or _repeat_count(rest))
        if placeholder:
            if chorus is None:
                out.append([REFRAIN_MARKER])
                continue
            body = list(chorus)
            n = _repeat_count(rest) if rest else None
            if n and n > 1:
                body[-1] = f"{body[-1]} /x{n}"
            out.append(body)
            continue
        # reguła 1: etykieta na początku zwrotki
        if word is not None:
            st = ([rest] if rest else []) + st[1:]
        if st:
            out.append(st)

    # reguła 3: powtórzenia na końcu linii
    result = []
    for st in out:
        lines = []
        for line in st:
            if MARKER.search(line):
                lines.append(line)
                continue
            m = REPEAT_AT_END.search(line)
            if m and m.start() > 0:
                line = f"{line[: m.start()].rstrip()} /x{int(m.group(1) or m.group(2))}"
            lines.append(line)
        result.append("\n".join(lines))
    return "\n\n".join(result) + "\n" if result else ""


# --- tekstowo.pl ---------------------------------------------------------

BASE_URL = "https://www.tekstowo.pl"
USER_AGENT = "Mozilla/5.0 (KaraokeBooster; private use)"  # nagłówki HTTP muszą być latin-1
TIMEOUT_S = 10


class LyricsNotFound(Exception):
    """Brak wyniku albo strona ma inny układ niż oczekiwany."""


class _SearchParser(HTMLParser):
    """Linki `<a class="title" href=... title="Wykonawca - Tytuł">` po nagłówku "Znalezione utwory"."""

    def __init__(self):
        super().__init__()
        self.in_results = False
        self.results: list[tuple[str, str]] = []
        self._h2 = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "h2":
            self._h2 = True
        elif tag == "a" and self.in_results and "title" in (a.get("class") or "").split():
            href = a.get("href") or ""
            if href.startswith("/") and a.get("title"):
                self.results.append((a["title"].strip(), href))

    def handle_endtag(self, tag):
        if tag == "h2":
            self._h2 = False

    def handle_data(self, data):
        if self._h2:
            # kolejne nagłówki (np. "Znalezieni wykonawcy") kończą listę utworów
            self.in_results = "znalezione utwory" in data.lower()


def parse_search(page: str) -> list[tuple[str, str]]:
    """[(\"Wykonawca - Tytuł\", \"/sciezka\")] z wyników wyszukiwania."""
    p = _SearchParser()
    p.feed(page)
    return p.results


class _SongParser(HTMLParser):
    """Tekst z pierwszego `div.inner-text` wewnątrz elementu `id="songText"`."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0          # zagnieżdżenie divów od songText
        self.text_depth = None  # głębokość div.inner-text
        self.done = False
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if self.done:
            return
        a = dict(attrs)
        if self.depth == 0:
            if a.get("id") == "songText":
                self.depth = 1
            return
        if tag == "br" and self.text_depth is not None:
            self.parts.append("\n")
        if tag == "div":
            self.depth += 1
            if self.text_depth is None and "inner-text" in (a.get("class") or "").split():
                self.text_depth = self.depth

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag == "div" and self.depth:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.done or self.depth == 0 or tag != "div":
            return
        if self.text_depth == self.depth:
            self.done = True
        self.depth -= 1

    def handle_data(self, data):
        if self.text_depth is not None and not self.done:
            # łamanie linii w HTML to <br>; zwykłe znaki nowej linii w źródle są tylko formatowaniem
            self.parts.append(data.replace("\r", "").replace("\n", ""))


def parse_song(page: str) -> str:
    p = _SongParser()
    p.feed(page)
    if not p.done:
        raise LyricsNotFound("Nie znalazłem tekstu na stronie piosenki (zmienił się układ strony?).")
    lines = [html.unescape(l).strip() for l in "".join(p.parts).split("\n")]
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    if not text:
        raise LyricsNotFound("Strona piosenki nie ma tekstu.")
    return text + "\n"


def _norm(s: str) -> str:
    return re.sub(r"\W+", " ", s.casefold()).strip()


def best_match(results: list[tuple[str, str]], artist: str, title: str) -> str | None:
    """Ścieżka wyniku, którego nazwa zawiera tytuł (i wykonawcę, jeśli jest); inaczej None."""
    want_t, want_a = _norm(title), _norm(artist)
    for name, href in results:
        n = _norm(name)
        if want_t and want_t in n and (not want_a or want_a in n):
            return href
    return None


def _get(url: str, opener=None) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with (opener or urllib.request.urlopen)(req, timeout=TIMEOUT_S) as r:
        return r.read().decode("utf-8", errors="replace")


def fetch(artist: str, title: str, opener=None) -> str:
    """Tekst piosenki z tekstowo.pl po czyszczeniu. LyricsNotFound albo OSError przy problemie."""
    query = urllib.parse.urlencode({"search-query": f"{artist} {title}".strip()})
    href = best_match(parse_search(_get(f"{BASE_URL}/szukaj?{query}", opener)), artist, title)
    if href is None:
        raise LyricsNotFound(f"tekstowo.pl nie ma piosenki \"{artist} - {title}\".")
    return clean(parse_song(_get(BASE_URL + href, opener)))
