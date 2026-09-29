# 0015. Generator piosenek: ultrasongs zamiast własnego kodu

- Status: przyjęta
- Data: 2026-09-29
- Źródło: rozmowa z użytkownikiem ("nie będziemy wynajdywać koła na nowo"), test na próbce

## Kontekst
Brak plików UltraStar dla polskich piosenek blokuje etap 1. Plan zakładał własny generator w etapie 3 ([0008](0008-budowa-etapami.md)). Istnieją dwa gotowe projekty (MIT):
- **ultrasongs**: przyjmuje własny tekst piosenki, ma edytor do korekty, Python 3.10+.
- **UltraSinger**: popularniejszy, ale tylko Python 3.12 i bez własnego tekstu.

## Decyzja
Pliki UltraStar generujemy **ultrasongs**, zainstalowanym poza repo we własnym venv ([instrukcja](../ultrasongs-setup.md)). Nie piszemy własnego generatora. KaraokeBooster przyjmuje jego wynik:
- parser wczytuje plik;
- `ultrastar2midi.py --octave auto` naprawia konwencję oktaw;
- `alignment.py` sprawdza wyrównanie.

Generowanie jest dostępne od razu, a nie dopiero w etapie 3.

## Konsekwencje
- Po stronie użytkownika zostaje: audio + tekst piosenki (+ ewentualna korekta w edytorze).
- Na próbce: 80/83 słowa zgodne, czas słów p80 83 ms, nuty 98% w ±1 półtonie (bez oktawy).
- Długi czas przetwarzania na GTX 1050. Liczba przebiegów jest parametrem.
- Zależymy od cudzego projektu (fork, mniej aktywny). Instalacja wymaga dwóch obejść (antlr4, PyTorch cu126).
- Zmienia kolejność z [0008](0008-budowa-etapami.md) tylko dla generatora. Reszta etapów bez zmian.
