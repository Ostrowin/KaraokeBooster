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

## Sprzęt

### Wybór wyjścia audio na imprezę (głośnik)

**What:** Zdecydować, jak podłączać głośniki na imprezie, i ewentualnie zmienić [decyzję 0005](docs/decisions/0005-scena-impreza-glosniki.md) nowym ADR.

**Why:** Dostępny głośnik JBL Charge 5 ma tylko Bluetooth (brak AUX). Bluetooth dodaje 150-250 ms opóźnienia i jest drugim urządzeniem audio obok UMC22, czyli ma drugi zegar ([decyzja 0006](docs/decisions/0006-jedno-urzadzenie-audio-i-opoznienie.md)). Setup głośników będzie inny na każdej imprezie.

**Context:** Opcje:
1. głośnik lub wieża z AUX, podłączona kablem do wyjścia UMC22 (6,3 mm → 3,5 mm albo RCA);
2. śpiewający w słuchawkach z UMC22, a publiczność słucha z głośnika BT (spójne dla publiczności, ale technicznie są dwa urządzenia wyjściowe);
3. sam BT: odradzane.

Sprzęt kupiony na start: Behringer XM8500 + UMC22 + kable XLR-XLR, jack-jack 6,3 mm, XLR-jack.

**Effort:** S
**Priority:** P2
**Depends on:** przed blokiem J z [docs/reaper-setup.md](docs/reaper-setup.md)

## Completed

### Generator plików UltraStar z samego audio
Zrobione przez użycie gotowego ultrasongs zamiast własnego kodu ([decyzja 0015](docs/decisions/0015-generator-ultrasongs.md), [instrukcja](docs/ultrasongs-setup.md)). Dodano `ultrastar2midi.py --octave auto` na konwencję oktaw ultrasongs. **Zamknięte:** 2026-09-29.
