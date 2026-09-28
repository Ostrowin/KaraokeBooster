# 0012. Wspólny parser UltraStar

- Status: przyjęta
- Data: 2026-09-28
- Źródło: /plan-eng-review, D4

## Kontekst
Trzy narzędzia (konwerter MIDI, podgląd tekstu, analiza nagrań) muszą z pliku UltraStar wyliczyć te same nuty w tych samych sekundach.

## Decyzja
Moduł `karaokebooster/ultrastar.py` udostępnia `load(path)` i typy `Song`/`Note` (typ, start_s, dur_s, pitch_midi, sylaba, fraza). Używają go `ultrastar2midi.py`, `lyrics_viewer.py` i `analyze_takes.py`.

Zakres formatu:
- Obsługiwane: v1.0.0 i starsze pliki bez #VERSION; #TITLE, #ARTIST, #BPM, #GAP, #MP3/#AUDIO (#AUDIO ma pierwszeństwo), #RELATIVE, #START, #END.
- Ignorowane z ostrzeżeniem: #VIDEO, #VIDEOGAP i nieznane tagi.
- Błąd: duety P1/P2 i niepoprawne linie (z numerem linii).

## Konsekwencje
- Jedno źródło prawdy o czasie nut.
- Awaria parsera psuje trzy narzędzia naraz, więc testy kontraktu są obowiązkowe.
