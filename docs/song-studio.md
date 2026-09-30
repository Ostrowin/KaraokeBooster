# Song Studio: nowa piosenka z mp3

Okienko, które z pliku mp3 i tekstu robi gotową piosenkę do śpiewania w REAPER ([decyzja 0017](decisions/0017-song-studio-okienko-i-biblioteka.md), [projekt](designs/song-studio.md)).

## Uruchomienie

```bash
.venv\Scripts\pythonw.exe tools\song_studio.py
```

`pythonw` uruchamia okienko bez czarnego okna konsoli. Wygodnie jest zrobić skrót na pulpicie z tym poleceniem (folder startowy: `C:\Projects\Private\KaraokeBooster`).

Wymagania: ultrasongs zainstalowany wg [ultrasongs-setup.md](ultrasongs-setup.md), REAPER, szablon projektu (niżej).

## Dodanie piosenki

1. **Wybierz…** plik audio. Nazwa w formacie `Wykonawca - Tytuł.mp3` sama wypełnia pola.
2. **Pobierz z tekstowo.pl** albo wklej tekst. Sprawdź go:
   - `/x2` na końcu linii powtarza zwrotkę do tego miejsca;
   - `!!! WKLEJ REFREN !!!` oznacza, że strona miała tylko "Ref." bez tekstu refrenu. Wklej refren w to miejsce, inaczej dodanie jest zablokowane.
3. **Jakość**: szybka (ok. 30-40 min) albo dokładna (ok. 1-2 h). Czasy to szacunek dla GTX 1050.
4. **Dodaj do kolejki**. Piosenki generują się po kolei; można dodać kilka i zostawić komputer.

Zamknięcie okienka w trakcie przerywa generowanie. Po ponownym uruchomieniu piosenka ma status "przerwana" i przycisk **Wznów** (robi tylko brakujące kroki).

## Biblioteka

| Status | Co zrobić |
|---|---|
| gotowa | **Śpiewaj** |
| do sprawdzenia | nuty mogą być przesunięte; w Uwagach jest podpowiedź korekty `#GAP`. Popraw w **Edytor nut**, zapisz plik `.txt`, **Importuj .txt**. Albo **Akceptuj mimo to** |
| błąd | **Log** pokazuje przyczynę, **Wznów** ponawia krok z błędem |
| przerwana | **Wznów** |

- **Śpiewaj** otwiera projekt w REAPER i tekst na pełnym ekranie (Esc zamyka tekst). Start odtwarzania: spacja w REAPER. Wymaga ustawionego OSC (blok H w [reaper-setup.md](reaper-setup.md)).
- **Przelicz** buduje od nowa MIDI i projekt (np. po ręcznej zmianie `.txt` w folderze piosenki).
- **Generuj ponownie** puszcza ultrasongs jeszcze raz, np. w jakości dokładnej. Twoje poprawki `.txt` trafiają do kopii `.bak`.

Przed Przelicz / Generuj / Odśwież **zamknij projekt piosenki w REAPER**, bo projekt jest przebudowywany.

## Szablon projektu REAPER

Projekt każdej piosenki powstaje z `songs\_szablon.rpp`: ścieżki **Podklad**, **ghost**, **wokal** z ich wtyczkami i poziomami. Pierwszy szablon zrobiony jest z projektu "Za tobą pójdę jak na bal".

Gdy po blokach E-G ([reaper-setup.md](reaper-setup.md)) ustawisz MotTune, upiększacze i ghost:
1. zapisz ten projekt w REAPER;
2. w Bibliotece: **Ustaw szablon z projektu…** i wskaż go;
3. **Odśwież projekty z szablonu**: wszystkie piosenki dostają nowe ustawienia.

Ustawienia zmieniane w projekcie jednej piosenki giną przy przebudowie (kopia trafia do `.rpp.<data>.bak`). Wszystko, co ma zostać na stałe, ustawiaj w szablonie.

## Folder piosenki

`songs\<nazwa>\` (poza gitem): `source.mp3` (kopia), `lyrics.txt`, plik UltraStar `.txt`, `_vocals.mp3`, `_accompaniment.mp3`, edytor nut, `.mid`, `.rpp`, `song.json` (stan), `log.txt`.

## Konfiguracja (opcjonalna)

Plik `karaokebooster.local.toml` w katalogu projektu (poza gitem). Domyślne wartości:

```toml
ultrasongs_dir = "C:/Projects/Private/ultrasongs"
reaper_exe = "C:/Program Files/REAPER (x64)/reaper.exe"
songs_dir = "C:/Projects/Private/KaraokeBooster/songs"
osc_port = 9000
offset_ms = 0        # opóźnienie tekstu, np. opóźnienie wyjścia audio z bloku B
language = "pl"
align_engine = "crepe"
```
