# Pomiary opóźnienia

Reguła z [decyzji 0006](decisions/0006-jedno-urzadzenie-audio-i-opoznienie.md):

**Opóźnienie mikrofon → głośnik = pełna pętla zwrotna + PDC wtyczek.** Nie dzielimy pętli na pół.

| Wynik | Ocena |
|---|---|
| ≤ 25 ms | zalicza |
| 25-40 ms | zalicza tylko przy komforcie śpiewania |
| > 40 ms | zmiana sprzętu |

## Metoda

1. W REAPER: kabel z wyjścia do wejścia (pętla) albo test klaśnięcia.
2. Nagraj impuls i odczytaj przesunięcie w ms (pełna pętla, bez dzielenia).
3. Odczytaj PDC łańcucha wtyczek (MotTune + efekty) w REAPER.
4. Suma = opóźnienie mikrofon → głośnik.

## Wyniki

Częstotliwość próbkowania: 48 kHz.

| Data | Topologia | Sterownik | Bufor | Pętla [ms] | PDC [ms] | Suma [ms] | Trzaski? | Komfort śpiewu | Uwagi |
|---|---|---|---|---|---|---|---|---|---|
| | 3: Realtek | ASIO4ALL | 64 | | | | | | |
| | 3: Realtek | ASIO4ALL | 128 | | | | | | |
| | 3: Realtek | ASIO4ALL | 256 | | | | | | |
| | 3: Realtek | WASAPI Excl. | 128 | | | | | | |
| | 1: interfejs USB | ASIO producenta | 128 | | | | | | |
| | 2 urządzenia (kontrola) | ASIO4ALL | 128 | | | | | | oczekiwany dryf |

## Wniosek

_(Uzupełnić po pomiarach: wybrana topologia i bufor.)_
