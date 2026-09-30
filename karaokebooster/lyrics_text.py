"""Tekst piosenki przed ultrasongs: rozwijanie powtórzeń, czyszczenie, pobieranie z tekstowo.pl.

Song Studio (docs/designs/song-studio.md). Czyszczenie:
  - etykiety części ("Ref.:", "Refren (x2):", "2x Ref.", "[Zwrotka 2]") są usuwane; etykietą jest
    tylko coś, co tak wygląda (dwukropek, nawias, kropka, krotność albo sama w linii);
  - krotność przy etykiecie ("Ref. x2") albo w osobnej linii ("(x2)") powtarza zwrotkę / linię nad nią;
  - zwrotka będąca samą etykietą refrenu ("Ref.", "Ref. x2") dostaje tekst pierwszego refrenu
    (bez własnej krotności bierze krotność tamtego); gdy refrenu nigdzie nie ma, zostaje
    REFRAIN_MARKER (okienko blokuje dodanie);
  - "x2", "(x2)", "2x" na końcu linii zamieniane na składnię "/x2" z expand().
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

# powtórzenie: "x2", "2x", "(x2)", "[2x]", "×2"
_REPEAT = r"[\[(]?\s*(?:[x×]\s*\d+|\d+\s*[x×])\s*[\])]?"
REPEAT_ONLY = re.compile(r"^\s*" + _REPEAT + r"\s*(?:razy)?\s*:?\s*$", re.IGNORECASE)
REPEAT_AT_END = re.compile(r"(?:\s+|(?=[\[(]))" + _REPEAT + r"\s*$", re.IGNORECASE)

_CHORUS = r"(?:ref(?:ren)?|refrain|chorus)"
_LABEL_WORDS = _CHORUS + r"|zwrotka|verse|bridge|mostek|intro|outro|przedrefren|pre-?chorus"
# Etykieta części piosenki, np. "Ref.:", "Refren (x2):", "2x Ref.", "[Zwrotka 2]", "/Ref./".
LABEL = re.compile(
    r"^\s*(?:(?P<pre>\d+\s*[x×])\s+)?"
    r"(?P<open>[\[(/])?\s*"
    r"(?P<word>" + _LABEL_WORDS + r")(?!\w)(?P<dot>\.)?"
    r"(?:\s*\d+(?!\s*[x×]))?\s*\.?"          # numer zwrotki/refrenu
    r"(?:\s*(?P<rep>" + _REPEAT + r"))?"
    r"\s*(?P<close>[\])/]\.?)?"
    r"\s*(?P<colon>:)?"
    r"\s*(?P<rest>.*)$",
    re.IGNORECASE)


def _count(token: str | None) -> int | None:
    m = re.search(r"\d+", token or "")
    return int(m.group()) if m else None


def _stanzas(text: str) -> list[list[str]]:
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip())
    return [[l.strip() for l in b.splitlines() if l.strip()] for b in blocks if b.strip()]


def _label(line: str) -> tuple[str, int | None, str] | None:
    """(słowo etykiety, liczba powtórzeń albo None, reszta linii) albo None, gdy to zwykła linia.

    Etykietą jest tylko coś, co tak wygląda: stoi samo w linii albo ma dwukropek, nawias, kropkę
    ("Ref.") lub krotność. "Zwrotka raz" na początku linii tekstu nie jest etykietą."""
    m = LABEL.match(line)
    if not m:
        return None
    rest = m.group("rest").strip()
    marked = any(m.group(g) for g in ("colon", "close", "dot", "pre", "rep")) or (m.group("open") and not rest)
    if rest and not marked:
        return None
    return m.group("word").lower(), _count(m.group("pre") or m.group("rep")), rest


def _is_chorus(word: str | None) -> bool:
    return word is not None and re.fullmatch(_CHORUS, word, re.IGNORECASE) is not None


def _with_repeat(line: str, n: int | None) -> str:
    """Linia z markerem "/xN" dla expand() (zastępuje zapis "x2" na końcu linii)."""
    if MARKER.search(line):
        return line
    line = REPEAT_AT_END.sub("", line).rstrip()
    return f"{line} /x{n}" if n and n > 1 else line


def _merge_repeat_lines(lines: list[str]) -> tuple[list[str], int | None]:
    """Linia z samym "(x2)" dotyczy linii nad nią. Zwraca też krotność sprzed pierwszej linii."""
    out: list[str] = []
    leading = None
    for line in lines:
        if REPEAT_ONLY.match(line):
            if out:
                out[-1] = _with_repeat(out[-1], _count(line))
            else:
                leading = _count(line)
        else:
            out.append(line)
    return out, leading


def clean(text: str) -> str:
    """Tekst z tekstowo.pl → tekst dla ultrasongs ze składnią "/xN" dla expand()."""
    parsed: list[tuple[str | None, int | None, list[str]]] = []
    for st in _stanzas(text):
        lab = _label(st[0])
        if lab:
            word, count, rest = lab
            lines = ([rest] if rest else []) + st[1:]
        else:
            word, count, lines = None, None, st
        lines, leading = _merge_repeat_lines(lines)
        parsed.append((word, count or leading, lines))

    # pierwszy refren z tekstem: źródło dla późniejszych samych "Ref."
    chorus = next(((lines, count) for word, count, lines in parsed if _is_chorus(word) and lines), None)

    out: list[list[str]] = []
    for word, count, lines in parsed:
        if not lines:
            if _is_chorus(word):
                if chorus is None:
                    out.append([REFRAIN_MARKER])
                    continue
                lines, count = list(chorus[0]), count or chorus[1]
            elif count and out:
                # samo "(x2)" w osobnej zwrotce: powtórz poprzednią
                out[-1][-1] = _with_repeat(out[-1][-1], count)
                continue
            else:
                continue
        lines = [_with_repeat(l, _count(REPEAT_AT_END.search(l).group()) if REPEAT_AT_END.search(l) else None)
                 for l in lines]
        if count and count > 1:
            lines[-1] = _with_repeat(lines[-1], count)
        out.append(lines)
    return "\n\n".join("\n".join(st) for st in out) + "\n" if out else ""


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
