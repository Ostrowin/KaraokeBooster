# 0002. Korekcja do melodii konkretnej piosenki, nie do skali

- Status: przyjęta
- Data: 2026-09-28
- Źródło: /office-hours, założenie 2

## Kontekst
Klasyczny autotune ściąga głos do najbliższej nuty skali. U kogoś, kto śpiewa kilka półtonów obok, wychodzi czysto zaśpiewana, ale zła nuta.

## Decyzja
Cel korekcji w każdej chwili to nuta z melodii piosenki (z pliku UltraStar), z tolerancją oktawy:
- etap 1: stałe przesunięcie per piosenka (`--octave`);
- etap 2: oktawa wybierana na początku frazy i trzymana do jej końca.

## Konsekwencje
- Program musi znać melodię i oś czasu piosenki ([0003](0003-zrodlo-melodii-ultrastar.md), [0004](0004-program-trzyma-os-czasu.md)).
- Duże przesunięcia dają artefakty, stąd tryby z [0007](0007-trzy-tryby-korekcji.md).
