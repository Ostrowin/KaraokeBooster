# 0013. Automatyczne wykrywanie kodowania plików UltraStar

- Status: przyjęta
- Data: 2026-09-28
- Źródło: /plan-eng-review, D5

## Kontekst
Nowe pliki UltraStar są w UTF-8, ale starsze polskie bywają w CP1250. Bez obsługi tego przypadku polskie litery zamieniają się w krzaki.

## Decyzja
Kolejność rozpoznawania kodowania:
1. UTF-8 (z BOM i bez).
2. Jeśli plik ma tag `#ENCODING`, parser używa podanego kodowania.
3. Jeśli UTF-8 się nie dekoduje, parser przechodzi na CP1250 i wypisuje ostrzeżenie.

Wszystkie cztery warianty mają testy.

## Konsekwencje
- Starsze polskie pliki działają bez ręcznej konwersji.
- Dla pliku bez tagu w innym języku zgadnięcie CP1250 może być błędne (rzadkie).
