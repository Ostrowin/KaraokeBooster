# KaraokeBooster

Karaoke, w którym brzmisz, jakbyś umiał śpiewać. Twój własny głos jest na żywo ściągany do nut konkretnej piosenki (np. Krzysztofa Krawczyka) i upiększany (kompresja, EQ, pogłos). Zamiany barwy na cudzy głos nie ma.

## Status

**Etap 1: przygotowanie.** Projekt i przegląd techniczny są zatwierdzone. Kodu jeszcze nie ma.

| Etap | Co | Status |
|---|---|---|
| 1 | Pokaz z gotowych klocków (REAPER + MotTune MIDI) + nasze skrypty + pomiary | planowany |
| 2 | Własna aplikacja: tryby Twardy / Łagodny / Ghost vocal | po bramce go/no-go |
| 3 | Generator piosenek z pliku lub linku | aspiracyjny |

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
- [TODOS.md](TODOS.md): rzeczy na później
