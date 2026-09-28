# Słowniczek

## Muzyka i głos
- **Wysokość (pitch):** czy trafiasz w nutę. Poprawia ją autotune.
- **Barwa (timbre):** jak brzmi głos (chrapliwy, ciepły). Tego nie zmieniamy.
- **Półton:** najmniejszy krok między nutami (sąsiedni klawisz pianina). 12 półtonów = oktawa.
- **Oktawa:** ta sama nuta wyżej lub niżej (np. męski głos śpiewający piosenkę kobiety).
- **Fraza:** fragment melodii między oddechami (linia tekstu w karaoke).
- **Wibrato:** lekkie falowanie wysokości na długiej nucie.
- **Formanty:** rezonanse gardła i ust, które sprawiają, że głos brzmi jak Twój. Przy dużym przesunięciu wysokości bez ich zachowania głos brzmi jak "wiewiórka" albo "Darth Vader".

## Korekcja głosu
- **Autotune / korekcja wysokości:** przesuwa śpiewaną nutę do nuty docelowej.
- **Tryb twardy ("T-Pain"):** natychmiastowe, pełne ściągnięcie do nuty. Słychać efekt "robota".
- **Tryb łagodny:** korekcja tym delikatniejsza, im dalej jesteś od nuty. Brzmi naturalniej.
- **Ghost vocal:** cichy oryginalny wokal, który wchodzi, gdy się zgubisz.
- **Retune speed:** jak szybko korekcja dochodzi do nuty.
- **PSOLA:** algorytm zmiany wysokości głosu z małym opóźnieniem (używany w autotune).

## Pliki i formaty
- **MIDI:** cyfrowy zapis nut: jaka nuta, kiedy i jak długo. Bez dźwięku.
- **UltraStar (.txt):** format karaoke (gra UltraStar Deluxe, klon SingStara). Zawiera nuty, sylaby i czas.
- **BPM:** tempo (uderzenia na minutę). W UltraStar beat trwa 60 / (BPM · 4) s.
- **GAP:** w UltraStar czas w ms od początku pliku audio do beatu 0.
- **Kodowanie znaków (UTF-8, CP1250):** sposób zapisu liter takich jak "ą, ę, ł" w pliku.

## Audio i sprzęt
- **Opóźnienie (latency):** czas od dźwięku w mikrofonie do dźwięku z głośnika.
- **Bufor:** porcja próbek przetwarzana naraz. Mniejszy bufor to mniejsze opóźnienie, ale większe ryzyko trzasków.
- **ASIO / WASAPI Exclusive:** tryby sterownika dźwięku w Windows z niskim opóźnieniem.
- **Interfejs audio:** zewnętrzna karta dźwiękowa USB z wejściem na mikrofon (XLR).
- **Mikrofon dynamiczny, kardioidalny:** mikrofon sceniczny, który zbiera głównie dźwięk tuż przy ustach.
- **Sprzężenie:** pisk, gdy mikrofon zbiera dźwięk z głośników i wzmacnia go w pętli.
- **Przesłuch (bleed):** muzyka z głośników słyszalna w mikrofonie.
- **Bramka szumów (noise gate):** wycisza sygnał poniżej progu głośności.
- **dB SPL:** głośność w pomieszczeniu (85 dB SPL to głośna impreza).
- **LUFS:** miara odczuwalnej głośności nagrania (do wyrównania wersji w teście przed/po).

## Narzędzia
- **REAPER:** program do nagrywania i miksowania muzyki (DAW).
- **VST:** wtyczka z efektem dźwiękowym (np. MotTune MIDI).
- **PDC:** opóźnienie wnoszone przez wtyczkę, które REAPER kompensuje.
- **OSC:** protokół, którym REAPER wysyła pozycję odtwarzania do innych programów.
- **Demucs:** AI rozdzielające piosenkę na wokal i podkład.
- **torchcrepe / RMVPE:** AI odczytujące wysokość głosu z nagrania.
- **ADR:** krótki plik z zapisem jednej decyzji projektowej (`docs/decisions/`).
