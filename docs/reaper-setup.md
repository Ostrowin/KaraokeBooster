# Ustawienie projektu REAPER (etap 1)

Wersja robocza. Uzupełnimy ją po weryfikacji MotTune MIDI (krok 2 w [design.md](design.md)).

## 1. Urządzenie audio
- Preferences → Audio → Device: ASIO (sterownik interfejsu, ASIO4ALL lub FlexASIO), 48 kHz, bufor zgodny z [latency.md](latency.md).
- Wejście i wyjście na tym samym urządzeniu ([decyzja 0006](decisions/0006-jedno-urzadzenie-audio-i-opoznienie.md)).

## 2. Import bez mapy tempa ([decyzja 0010](decisions/0010-midi-w-sekundach-i-kontrola-wyrownania.md))
- Preferences → Media → wyłącz "automatically adjust media to project tempo" (albo odpowiadaj "Nie" przy pytaniu o tempo).
- Tempo projektu: 120 BPM.
- Przy imporcie `song.mid`: **nie** importuj mapy tempa.
- Ścieżki audio (`instrumental.wav`, `vocals.wav`): Timebase = **Time**.
- Wszystkie pliki startują w pozycji 0:00.

## 3. Ścieżki
| Ścieżka | Zawartość | Wyjście |
|---|---|---|
| Podkład | `instrumental.wav` (Demucs) | główne |
| Nuty | `song.mid` (ultrastar2midi.py) | MIDI do ścieżki Wokal |
| Wokal | wejście mikrofonu, monitoring włączony | główne |
| Ghost | `vocals.wav` (Demucs), sidechain z Wokalu | główne |

## 4. Łańcuch efektów na ścieżce Wokal
MotTune MIDI (szybki retune = tryb twardy) → ReaComp → ReaEQ → de-esser (ReaXcomp, pasmo 5-8 kHz) → ReaVerbate (ograniczony poziom).

## 5. Ghost vocal (etap 1)
- ReaComp na ścieżce Ghost, sidechain z ścieżki Wokal: gdy śpiewasz, ghost cichnie.
- Poziom: domyślnie −12 dB względem podkładu, maksymalnie −6 dB.

## 6. OSC dla podglądu tekstu
- Preferences → Control/OSC/web → Add → OSC, wysyłanie na `127.0.0.1` i port `lyrics_viewer.py` (do ustalenia przy T4).

## 7. Kontrola przed śpiewaniem
- `ultrastar2midi.py` nie pokazuje ostrzeżenia o wyrównaniu (> 30 ms).
- Test sprzężenia przy docelowej głośności.
