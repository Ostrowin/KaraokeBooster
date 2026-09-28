# CLAUDE.md

## Projekt
KaraokeBooster: korekcja wysokości własnego głosu na żywo do melodii konkretnej piosenki (pliki UltraStar), na pokaz na imprezie. Pełny projekt w `docs/design.md`, decyzje w `docs/decisions/`.

## Komunikacja
- Z użytkownikiem rozmawiaj po polsku.
- Użytkownik nie jest muzykiem. Tłumacz pojęcia muzyczne i audio (odsyłaj do `docs/glossary.md`) i dopytuj, gdy prośba jest niejasna.

## Zasady
- Nie zmieniaj przyjętych decyzji po cichu. Zmiana decyzji = nowy plik ADR w `docs/decisions/` (kolejny numer) i status "zastąpiona przez NNNN" w starym oraz wpis w `docs/decisions/README.md`.
- Obecny zakres to **etap 1** (decyzja 0009). Nie buduj silnika etapu 2 bez nowego `/plan-eng-review`.
- Czas nut liczy wyłącznie `karaokebooster/ultrastar.py` (decyzja 0012): sekundy = GAP/1000 + beat · 60 / (BPM · 4). Nie duplikuj tej logiki w narzędziach.
- MIDI zapisujemy ze stałym tempem 120 BPM i PPQ 960, pozycje z sekund (decyzja 0010).

## Środowisko
- Jeden venv: `.venv` na Pythonie 3.11 (decyzja 0011). System ma tylko 3.13, więc 3.11 instaluj przez `py -3.11`.
- Zależności w `pyproject.toml`, grupy `base`, `ml`, `dev`.

## Testing
- Framework: pytest (decyzja 0014).
- Komenda: `.venv\Scripts\python -m pytest`
- Fikstury: `tests/fixtures/` (małe pliki UltraStar, różne kodowania); audio testowe generowane w testach (tony o znanej wysokości), bez prawdziwych nagrań w repo.
- Plan testów: `docs/test-plan.md`.
