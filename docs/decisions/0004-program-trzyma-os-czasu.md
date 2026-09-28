# 0004. Program sam odtwarza podkład; YouTube tylko jako źródło

- Status: przyjęta
- Data: 2026-09-28
- Źródło: /office-hours, D6 (założenie 4)

## Kontekst
Żeby wiedzieć, do której nuty ściągać głos, program musi znać dokładną pozycję w piosence. Karaoke z YouTube w przeglądarce nie ma wokalu ani dostępnej osi czasu.

## Decyzja
- Podkład odtwarza nasz tor (w etapie 1 REAPER).
- Podkład i wokal "ghost" powstają przez Demucs z dokładnie tego pliku audio, do którego odwołuje się UltraStar (#AUDIO/#MP3).
- YouTube wraca w etapie 3 jako źródło dla generatora piosenek, tylko dla treści, do których użytkownik ma prawo.

## Konsekwencje
- Zewnętrzne podkłady są poza zakresem etapu 1 (wymagałyby ręcznego przesunięcia GAP).
