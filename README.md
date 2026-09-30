# KaraokeBooster

Karaoke, w którym brzmisz, jakbyś umiał śpiewać. Twój własny głos jest na żywo ściągany do nut konkretnej piosenki (np. Krzysztofa Krawczyka) i upiększany (kompresja, EQ, pogłos). Zamiany barwy na cudzy głos nie ma.

## Status

**Etap 1: w toku.** Narzędzia gotowe i przetestowane: parser UltraStar, konwerter MIDI z kontrolą wyrównania, podgląd tekstu, analiza nagrań. Generator piosenek przez ultrasongs, z okienkiem **Song Studio** (mp3 + tekst → gotowa piosenka w REAPER). Dalej: pomiary opóźnienia i REAPER.

| Etap | Co | Status |
|---|---|---|
| 1 | Pokaz z gotowych klocków (REAPER + MotTune MIDI) + nasze skrypty + pomiary | planowany |
| 2 | Własna aplikacja: tryby Twardy / Łagodny / Ghost vocal | po bramce go/no-go |
| 3 | Generator piosenek z pliku lub linku | przez ultrasongs ([0015](docs/decisions/0015-generator-ultrasongs.md)); z linku: później |

## Jak to działa (etap 1)

```
plik UltraStar (.txt) ──> ultrastar2midi.py ──> nuty MIDI ──┐
audio piosenki ──> Demucs ──> podkład + wokal "ghost" ──────┤
mikrofon ──> REAPER: MotTune MIDI → kompresor → EQ → de-esser → pogłos ──> głośniki
                     └─ OSC ──> lyrics_viewer.py (tekst na ekranie)
```

## Wymagania

- Windows 11, Python 3.11 (`py -3.11`), ffmpeg
- REAPER, ASIO4ALL lub FlexASIO, MotTune MIDI (VST)
- Najlepiej interfejs audio USB + dynamiczny mikrofon XLR ([decyzja 0006](docs/decisions/0006-jedno-urzadzenie-audio-i-opoznienie.md))

## Instalacja (planowana)

```bash
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -e ".[ml,dev]"
.venv\Scripts\python -m pytest
```

## Struktura (planowana)

```
karaokebooster/ultrastar.py   wspólny parser plików UltraStar
tools/song_studio.py          okienko: nowa piosenka z mp3 + biblioteka (Śpiewaj)
karaokebooster/pipeline.py    potok Song Studio (ultrasongs → MIDI → projekt REAPER)
tools/ultrastar2midi.py       UltraStar → MIDI + kontrola wyrównania
tools/lyrics_viewer.py        tekst zsynchronizowany z REAPER (OSC)
tools/analyze_takes.py        analiza nagrań: jak daleko od nut
tests/                        pytest + fikstury
docs/                         projekt, decyzje, pomiary, instrukcje
```

## Dokumentacja

- [docs/design.md](docs/design.md): pełny projekt (zachowanie korekcji, etapy, kryteria sukcesu)
- [docs/decisions/](docs/decisions/README.md): rejestr decyzji (ADR)
- [docs/glossary.md](docs/glossary.md): słowniczek pojęć
- [docs/test-plan.md](docs/test-plan.md): plan testów
- [docs/latency.md](docs/latency.md): pomiary opóźnienia
- [docs/reaper-setup.md](docs/reaper-setup.md): ustawienie projektu REAPER
- [docs/ultrasongs-setup.md](docs/ultrasongs-setup.md): generator plików UltraStar z audio + tekstu
- [docs/song-studio.md](docs/song-studio.md): Song Studio, nowa piosenka z mp3 jednym kliknięciem
- [TODOS.md](TODOS.md): rzeczy na później
