# 0001. Zostaje własny głos, korygujemy tylko wysokość

- Status: przyjęta
- Data: 2026-09-28
- Źródło: /office-hours, D2

## Kontekst
Cel: słyszeć na imprezie swój głos, ale tak, jakbym umiał śpiewać (np. Krawczyk). Są dwie różne technologie:
- korekcja wysokości (autotune): opóźnienie 10-30 ms;
- zamiana barwy przez AI (RVC): 150-300 ms, wymaga mocnego GPU, szara strefa prawna.

Laptop ma GTX 1050 4 GB.

## Decyzja
Korygujemy wysokość (pitch) i dodajemy upiększacze (kompresja, EQ, de-esser, pogłos). Barwa zostaje moja. Bez konwersji głosu AI.

## Konsekwencje
- Da się to zrobić z niskim opóźnieniem na obecnym sprzęcie.
- Nie brzmi jak Krawczyk, tylko jak ja dobrze zaśpiewany.
- RVC trafia do "Odłożone / poza zakresem" w [design.md](../design.md).
