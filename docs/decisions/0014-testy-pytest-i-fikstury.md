# 0014. Testy: pytest i syntetyczne fikstury

- Status: przyjęta
- Data: 2026-09-28
- Źródło: /plan-eng-review, D6

## Kontekst
Błędy rzędu 20-50 ms w czasie nut łatwo przeoczyć uchem, a szukanie ich ręcznie w REAPER zajmuje godziny.

## Decyzja
- `pytest` w `.venv`.
- `tests/fixtures/` z małymi plikami UltraStar: UTF-8, BOM, CP1250 z tagiem i bez, duet, błędna linia, #RELATIVE.
- Syntetyczne audio: tony o znanej wysokości, generowane w samych testach.
- Testy jednostkowe: parser, konwerter MIDI, metryki analizy.
- Jeden test E2E: .txt + syntetyczny wav → MIDI + kontrola wyrównania (bez Demucs).

Szczegóły w [test-plan.md](../test-plan.md).
