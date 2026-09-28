# 0008. Budowa etapami z bramką go/no-go

- Status: przyjęta
- Data: 2026-09-28
- Źródło: /office-hours, D9

## Kontekst
Darmowa korekcja sterowana MIDI (MotTune MIDI) i REAPER pozwalają złożyć pokaz bez własnego DSP. Własny silnik zbudowany bez pomiarów byłby zgadywaniem.

## Decyzja
1. Etap 1: REAPER + MotTune MIDI + nasze skrypty, pomiary i test przed/po.
2. Etap 2: własna aplikacja z trybami z [0007](0007-trzy-tryby-korekcji.md).
3. Etap 3: generator piosenek.

Między etapem 1 a 2 jest bramka go/no-go ([design.md](../design.md), "Bramka po etapie 1").

## Konsekwencje
- Projekt może skończyć się sukcesem już na etapie 1.
- Jeśli powstanie etap 2, część pracy w REAPER zostanie wyrzucona.
