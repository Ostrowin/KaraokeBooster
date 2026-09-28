# 0003. Źródło melodii: pliki UltraStar, AI jako zapas

- Status: przyjęta
- Data: 2026-09-28
- Źródło: /office-hours, D3

## Kontekst
Program potrzebuje nut piosenki wraz z czasem. Społeczność UltraStar ma tysiące plików .txt. Każda nuta ma numer MIDI − 60, pozycję w beatach i sylabę, a nagłówek podaje BPM i GAP.

Dla piosenek bez pliku melodię można wyciągnąć z nagrania: Demucs + RMVPE/torchcrepe (wzór: github.com/Beherith/ultrasongs).

## Decyzja
Podstawowym źródłem są pliki UltraStar. Generowanie plików UltraStar z mp3 (później także z linku) to etap 3.

## Konsekwencje
- Etap 1 działa tylko dla piosenek z plikiem UltraStar i pasującym do niego plikiem audio.
- Brak pliku dla wybranej piosenki Krawczyka podnosi priorytet etapu 3.
