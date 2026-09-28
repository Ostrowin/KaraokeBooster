# 0007. Trzy tryby korekcji jako przełączniki

- Status: przyjęta
- Data: 2026-09-28
- Źródło: /office-hours, D8 (po drugiej opinii)

## Kontekst
Nieśpiewający bywa 3-7 półtonów obok i 100-300 ms spóźniony. Twarde ściąganie wg zegara daje artefakty formantów i przeskoki w środku sylab.

## Decyzja
Wszystkie trzy tryby, przełączane w aplikacji:
- **Twardy ("T-Pain")**: pełne, szybkie ściągnięcie do nuty.
- **Łagodny**: siła korekcji zależna od odległości od nuty, zachowanie formantów, zmiana nuty od początku sylaby śpiewaka.
- **Ghost vocal**: cichy oryginalny wokal, gdy śpiewak się gubi.

Parametry i warunki opisuje [design.md](../design.md), sekcja "Zachowanie korekcji".

## Konsekwencje
- Etap 1 ma tylko tryb twardy (MotTune) i ghost wyciszany poziomem mikrofonu.
- Tryb łagodny i ghost wyzwalany błędem wysokości powstają w etapie 2.
