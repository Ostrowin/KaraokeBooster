# 0010. MIDI w sekundach przy stałym tempie i kontrola wyrównania

- Status: przyjęta; mechanizm kontroli wyrównania zastąpiony przez [0016](0016-kontrola-wyrownania-po-wysokosci.md)
- Data: 2026-09-28
- Źródło: /plan-eng-review, D2

## Kontekst
REAPER przy imporcie MIDI pyta o mapę tempa. Jeśli nuty i podkład trzymają się różnych osi czasu, korekcja ściąga do przesuniętych nut.

## Decyzja
- `ultrastar2midi.py` zapisuje MIDI ze stałym tempem 120 BPM i PPQ 960. Pozycje nut liczy z sekund: sekundy = GAP/1000 + beat · 60 / (BPM · 4).
- W REAPER import idzie bez mapy tempa, a ścieżki audio mają podstawę czasu "Time" ([reaper-setup.md](../reaper-setup.md)).
- Automatyczna kontrola porównuje pierwsze nuty z początkami śpiewu w `vocals.wav` i ostrzega przy przesunięciu > 30 ms.

## Konsekwencje
- Siatka taktów w REAPER nie odpowiada muzyce. Przeszkadza to tylko przy ręcznej edycji nut.
