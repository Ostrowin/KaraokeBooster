"""Czyszczenie tekstu i tekstowo.pl (karaokebooster/lyrics_text.py). Bez sieci: HTML to fikstury
z wymyślonym tekstem, odwzorowujące układ strony z 2026-09-30."""

import io
import urllib.request

import pytest

from karaokebooster.lyrics_text import (
    REFRAIN_MARKER,
    LyricsNotFound,
    best_match,
    clean,
    expand,
    fetch,
    parse_search,
    parse_song,
)

SEARCH = """<html><body>
<div class="box-przeboje"><a href="/inny/przebój" class="title" title="Inny - Przebój">Inny - Przebój</a></div>
<h2 class="my-2">Znalezione utwory:</h2>
<div class="box-przeboje"><div class="flex-group"><b>1.</b> <a href="/jan-testowy/lodka"
 class="title" title="Jan Testowy - Łódka">Jan Testowy - Łódka </a></div></div>
<div class="box-przeboje"><div class="flex-group"><b>2.</b> <a href="/jan-testowy/inna"
 class="title" title="Jan Testowy - Inna">Jan Testowy - Inna </a></div></div>
<h2 class="my-2">Znalezieni artyści:</h2>
<a href="/artysta" class="title" title="Jan Testowy">Jan Testowy</a>
</body></html>"""

SONG_PAGE = """<html><body>
<div class="song-text" id="songText" data-id="1">
  <h2 class="mb-2">Tekst piosenki:</h2>
  <div class="inner-text">Płynie łódka po jeziorze <br />
Wiatr ją niesie &amp; kołysze <br />
<br />
Ref.: <br />
Hej, łódko moja <br />
</div>
  <div class="adv-home"><script>reklama()</script></div>
</div>
<div class="tlumaczenie" id="songTranslation"><div class="inner-text">Translation</div></div>
</body></html>"""


# --- expand (przeniesione z tools/expand_lyrics.py; pełne testy w test_expand_lyrics.py) ---

def test_expand_available_from_package():
    assert expand("a /x2\n") == "a\na\n"


# --- clean: reguła 1, etykiety ---

@pytest.mark.parametrize("label", ["Ref.:", "Ref:", "Refren:", "[Refren]", "Zwrotka 1:", "[Zwrotka 2]",
                                   "/Ref./", "Bridge:", "(Refren)"])
def test_labels_removed(label):
    assert clean(f"{label}\nA\nB\n") == "A\nB\n"


def test_label_with_text_on_same_line_keeps_text():
    assert clean("Ref.: Hej ho\nA\n") == "Hej ho\nA\n"


def test_words_starting_like_labels_are_not_labels():
    assert clean("Refleksja nocą\nZwrotkami gram\n") == "Refleksja nocą\nZwrotkami gram\n"


# --- clean: reguła 2, zastępniki refrenu (przed regułą 1) ---

def test_bare_chorus_replaced_by_first_chorus():
    text = "Ref.:\nHej\nHo\n\nZwrotka\nA\n\nRef.\n"
    assert clean(text) == "Hej\nHo\n\nA\n\nHej\nHo\n"


def test_bare_chorus_with_repeat_count():
    assert clean("Ref.:\nHej\nHo\n\nRef. x2\n") == "Hej\nHo\n\nHej\nHo /x2\n"
    assert expand(clean("Ref.:\nHej\n\n[Ref] 2x\n")) == "Hej\n\nHej\nHej\n"


def test_chorus_label_with_inline_first_line_is_found():
    assert clean("Ref.: Hej\nHo\n\nRef.\n") == "Hej\nHo\n\nHej\nHo\n"


def test_bare_chorus_without_any_chorus_gets_marker():
    assert clean("A\n\nRef.\n") == f"A\n\n{REFRAIN_MARKER}\n"


# --- clean: reguła 3, powtórzenia na końcu linii ---

@pytest.mark.parametrize("suffix,n", [("x2", 2), ("(x2)", 2), ("2x", 2), ("x 3", 3), ("[x4]", 4), ("×2", 2)])
def test_repeat_suffix_converted(suffix, n):
    assert clean(f"A\nB {suffix}\n") == f"A\nB /x{n}\n"


def test_existing_marker_kept():
    assert clean("A /x2\n") == "A /x2\n"


def test_empty_and_blank_input():
    assert clean("") == "" and clean("\n\n  \n") == ""


def test_crlf_and_extra_blank_lines():
    assert clean("A\r\nB\r\n\r\n\r\n\r\nC\r\n") == "A\nB\n\nC\n"


# --- tekstowo.pl ---

def test_parse_search_only_song_results():
    assert parse_search(SEARCH) == [("Jan Testowy - Łódka", "/jan-testowy/lodka"),
                                    ("Jan Testowy - Inna", "/jan-testowy/inna")]


def test_parse_search_no_results():
    assert parse_search("<h2>Znalezione utwory:</h2><p>Brak</p>") == []


def test_best_match():
    res = parse_search(SEARCH)
    assert best_match(res, "Jan Testowy", "Łódka") == "/jan-testowy/lodka"
    assert best_match(res, "", "inna") == "/jan-testowy/inna"
    assert best_match(res, "Ktoś Inny", "Łódka") is None
    assert best_match([], "a", "b") is None


def test_parse_song_takes_only_lyrics_block():
    text = parse_song(SONG_PAGE)
    assert text == "Płynie łódka po jeziorze\nWiatr ją niesie & kołysze\n\nRef.:\nHej, łódko moja\n"
    assert "Translation" not in text and "reklama" not in text


@pytest.mark.parametrize("page", ["<html></html>", '<div id="songText"><p>nic</p></div>',
                                  '<div id="songText"><div class="inner-text">  </div></div>'])
def test_parse_song_changed_layout(page):
    with pytest.raises(LyricsNotFound):
        parse_song(page)


class FakeOpener:
    def __init__(self, pages):
        self.pages, self.urls = pages, []

    def __call__(self, req, timeout):
        url = req.full_url
        self.urls.append(url)
        assert timeout == 10
        for key, page in self.pages.items():
            if key in url:
                return io.BytesIO(page.encode("utf-8"))
        raise OSError("brak sieci")


def test_fetch_cleans_result():
    opener = FakeOpener({"/szukaj?": SEARCH, "/jan-testowy/lodka": SONG_PAGE})
    text = fetch("Jan Testowy", "Łódka", opener=opener)
    assert text == "Płynie łódka po jeziorze\nWiatr ją niesie & kołysze\n\nHej, łódko moja\n"
    assert "search-query=Jan+Testowy+%C5%81%C3%B3dka" in opener.urls[0]


def test_fetch_not_found():
    with pytest.raises(LyricsNotFound):
        fetch("Nikt", "Nic", opener=FakeOpener({"/szukaj?": SEARCH}))


def test_fetch_network_error():
    with pytest.raises(OSError):
        fetch("Jan", "Łódka", opener=FakeOpener({}))


def test_default_opener_is_urlopen(monkeypatch):
    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout: calls.append(req) or io.BytesIO(b""))
    with pytest.raises(LyricsNotFound):
        fetch("a", "b")
    assert calls and calls[0].get_header("User-agent").isascii()


# --- krotności przy etykietach i w osobnych liniach (2026-09-30) ---

@pytest.mark.parametrize("text,expected", [
    ("Z1\nZ2\n\nRef. x2\nHej\nHo\n\nZ3", "Z1\nZ2\n\nHej\nHo\nHej\nHo\n\nZ3\n"),   # krotność nad refrenem
    ("Ref. 2x:\nHej\nHo", "Hej\nHo\nHej\nHo\n"),
    ("Refren (x2):\nHej\nHo", "Hej\nHo\nHej\nHo\n"),
    ("[Refren x3]\nHej", "Hej\nHej\nHej\n"),
    ("Hej\nHo\n(x2)", "Hej\nHo\nHej\nHo\n"),                                       # osobna linia
    ("Hej\nHo\n\n(x2)\n\nDalej", "Hej\nHo\nHej\nHo\n\nDalej\n"),                   # osobna zwrotka
    ("Hej\nHo\n2 razy", "Hej\nHo\n2 razy\n"),                                      # słownie: bez zmian
    ("Ref.:\nHej\n\n2x Ref.", "Hej\n\nHej\nHej\n"),                                # krotność przed etykietą
    ("Ref. x2:\nHej\n\nZwrotka:\nA\n\nRef.", "Hej\nHej\n\nA\n\nHej\nHej\n"),        # samo Ref. bierze krotność refrenu
    ("Ref. x2:\nHej\n\nRef. x3", "Hej\nHej\n\nHej\nHej\nHej\n"),                   # własna krotność wygrywa
    ("Raz\nDwa x2\nTrzy", "Raz\nDwa\nRaz\nDwa\nTrzy\n"),                           # w środku: od początku zwrotki
])
def test_repeats_expand_correctly(text, expected):
    assert expand(clean(text)) == expected


@pytest.mark.parametrize("line", ["Zwrotka raz", "Refren gra w radiu", "Intro do życia", "Chorus of angels"])
def test_label_words_inside_normal_lines_are_kept(line):
    assert clean(f"{line}\nDalej\n") == f"{line}\nDalej\n"


def test_x_inside_words_is_not_repeat():
    assert clean("Max2 grał\nTaxi x\n") == "Max2 grał\nTaxi x\n"
