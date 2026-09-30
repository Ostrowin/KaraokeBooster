# 0017. Song Studio: okienko z kolejką i biblioteką już w etapie 1

- Status: przyjęta
- Data: 2026-09-30
- Źródło: /office-hours (D1-D6) i /plan-eng-review (D8-D15), [projekt](../designs/song-studio.md)

## Kontekst
Przygotowanie nowej piosenki wymagało ok. 6 ręcznych kroków w terminalu (tekst, ultrasongs, `ultrastar2midi.py`, kopiowanie plików, projekt REAPER, podgląd tekstu). Autor chce dodawać piosenki, zanim przyjdzie sprzęt, i na imprezie wybierać je z listy. [0008](0008-budowa-etapami.md) planował bibliotekę piosenek dopiero w etapie 2, a [0009](0009-przeglad-techniczny-tylko-etap-1.md) ogranicza zakres do etapu 1.

## Decyzja
W etapie 1 powstaje **Song Studio** (`tools/song_studio.py`, tkinter):
- zakładka "Dodaj piosenkę": mp3, wykonawca/tytuł z nazwy pliku, tekst wklejony albo pobrany z tekstowo.pl, jakość (szybka 3/3, dokładna 7/5), kolejka;
- zakładka "Biblioteka": status piosenek, "Śpiewaj" (REAPER + tekst na pełnym ekranie), poprawki nut, regeneracja, "Odśwież projekty z szablonu".

Potok (`karaokebooster/pipeline.py`) zapisuje stan w `songs/<slug>/song.json` i wznawia tylko brakujące kroki. Projekt REAPER powstaje z szablonu `songs/_szablon.rpp` (`karaokebooster/rpp.py`), więc ustawienia wtyczek z bloków E-G trafiają do piosenek przez szablon, a nie przez kod.

Ograniczenia:
- **REAPER zostaje odtwarzaczem i korektorem.** To nie jest silnik etapu 2.
- **Jeden proces**: bez wersji z terminala (D8, wpis w TODOS.md). Okienko pilnuje, żeby działało tylko jedno naraz.
- Źródłowe mp3 jest kopiowane do folderu piosenki (D10).

## Konsekwencje
- Nowa piosenka: wybór pliku, sprawdzenie tekstu, klik. Generowanie trwa dziesiątki minut na GTX 1050 (kolejka w tle).
- `expand()` i sklejanie MIDI przeniesione do pakietu; `tools/expand_lyrics.py` i `tools/ultrastar2midi.py` działają bez zmian (D12).
- Pobieranie z tekstowo.pl zależy od układu strony; przy zmianie zostaje wklejanie ręczne.
- ultrasongs pisze do krótkiego folderu w `%TEMP%`, bo powtarza "Wykonawca - Tytuł" w nazwie folderu i pliku, a Windows ogranicza ścieżki do 260 znaków.
- Biblioteka z etapu 2 może przejąć `song.json` i potok.
