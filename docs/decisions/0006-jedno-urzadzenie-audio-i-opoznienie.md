# 0006. Jedno urządzenie audio (jeden zegar) i reguła opóźnienia

- Status: przyjęta
- Data: 2026-09-28
- Źródło: /office-hours, recenzja dokumentu (R1-1, R2-1, R2-2)

## Kontekst
- Mikrofon USB z wyjściem przez wbudowanego Realteka to dwa zegary audio. Przy łączeniu przez ASIO4ALL/FlexASIO pojawia się dryf i trzaski.
- Opóźnienie liczone jako połowa pętli pomiarowej byłoby zaniżone o 5-10 ms.

## Decyzja
- Wejście i wyjście na jednym urządzeniu. Kolejność preferencji:
  1. interfejs USB z wejściem XLR + dynamiczny mikrofon XLR;
  2. mikrofon USB z własnym wyjściem;
  3. sam Realtek.
- Opóźnienie mikrofon → głośnik = pełna pętla zwrotna + PDC wtyczek.
- Reguła:
  - ≤ 25 ms: zalicza;
  - 25-40 ms: zalicza tylko przy komforcie śpiewania;
  - \> 40 ms: zmiana sprzętu, nie kodu.

## Konsekwencje
- Pomiary zapisujemy w [latency.md](../latency.md).
- Kroki 8-10 etapu 1 czekają na docelowy sprzęt.
