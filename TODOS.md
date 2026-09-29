# TODOS

## Planning

### Przegląd techniczny etapu 2 (własna apka) po bramce go/no-go

**What:** Uruchomić `/plan-eng-review` dla etapu 2 (własny silnik korekcji, tryby Twardy/Łagodny/Ghost, UI) z wynikami pomiarów z etapu 1.

**Why:** Architektura etapu 2 (Python + numba kontra Rust/C++, PSOLA, budżet opóźnienia, parametry D i W) zależy od zmierzonych liczb. Bez nich decyzje byłyby zgadywaniem (decyzja D1 przeglądu z 2026-09-28).

**Context:** Dokument projektu: `~/.gstack/projects/KaraokeBooster/lucci-unknown-design-20260928-180248.md` (sekcje "Zachowanie korekcji", "Bramka po etapie 1", "Etap 2"). Wejście do przeglądu: `docs/latency.md` (pełna pętla + PDC na wybranej topologii), liczby (a), (b), (c) i skuteczność detektora z `tools/analyze_takes.py`, wynik testu przed/po. Uruchamiać tylko, jeśli bramka wskazała "idziemy w etap 2".
Pros: plan etapu 2 oparty na danych. Cons: wymaga ukończenia etapu 1c.

**Effort:** S
**Priority:** P3
**Depends on:** Etap 1 ukończony (1a-1c) i bramka go/no-go rozstrzygnięta na "etap 2"

## Completed

### Generator plików UltraStar z samego audio
Zrobione przez użycie gotowego ultrasongs zamiast własnego kodu ([decyzja 0015](docs/decisions/0015-generator-ultrasongs.md), [instrukcja](docs/ultrasongs-setup.md)). Dodano `ultrastar2midi.py --octave auto` na konwencję oktaw ultrasongs. **Zamknięte:** 2026-09-29.
