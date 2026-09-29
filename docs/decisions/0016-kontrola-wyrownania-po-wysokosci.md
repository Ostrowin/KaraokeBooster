# 0016. Kontrola wyrównania po wysokości głosu zamiast po początkach sylab

- Status: przyjęta
- Data: 2026-09-29
- Źródło: test na "Za tobą pójdę jak na bal" (wynik ultrasongs), rozmowa z użytkownikiem
- Zastępuje: mechanizm kontroli z [0010](0010-midi-w-sekundach-i-kontrola-wyrownania.md) (reszta 0010 bez zmian)

## Kontekst
Kontrola z 0010 szukała początków śpiewu po chwili ciszy (energia RMS) i porównywała je z pierwszymi 8 nutami. Na prawdziwej piosence ta metoda zawiodła:
- Śpiew płynny (legato) prawie nie ma przerw. Na 4 minutach wokalu wykryto tylko 57 początków.
- 8 pierwszych nut mieściło się w 1,3 s, więc wynik "2/8 dopasowań" był fałszywym alarmem.

Ręczne sprawdzenie po wysokości tej samej piosenki pokazało przesunięcie +10 ms i 87% zgodności ramek.

## Decyzja
Kontrola wyrównania porównuje **wysokość wokalu** (crepe albo yin) z nutami z pliku, przesuwając nuty w oknie ±300 ms co 10 ms:
- Zgodność = ramki, w których śpiew (pewność ≥ 0,5) jest w ±1 półtonie od nuty (bez oktawy), podzielone przez ramki, w których jest nuta albo śpiew. Cisza w trakcie nuty i śpiew poza nutą obniżają wynik.
- Wynik to przesunięcie z najwyższą zgodnością. Dodatnie oznacza, że wokal jest później niż nuty. Podpowiedź: popraw #GAP o tę wartość.
- Pewność: najlepsza zgodność musi być co najmniej 2× wyższa od mediany zgodności w oknie ±1 s. Bezwzględny procent zależy od silnika (na tej samej piosence crepe 55%, yin 33%), więc nie jest progiem. Kalibracja: właściwa melodia 4,4×, podmieniona melodia 1,4×.
- Pewność, warunek 2: przy najlepszym przesunięciu co najmniej 50% ramek, w których jest jednocześnie śpiew i nuta, trafia w ±1 półton. Sam rytm daje szczyt kontrastu także dla złej melodii (losowa melodia w tym rytmie: 2,5×), a ten warunek to rozróżnia: właściwa melodia 84-87% (yin/crepe), losowa 14%.
- Wyrównanie jest OK, gdy dopasowanie jest pewne (oba warunki) i |przesunięcie| ≤ 30 ms (przy co najmniej 200 porównanych ramkach). Inaczej ostrzeżenie z powodem.
- Silnik domyślny to `crepe` (GPU). Bez PyTorcha skrypt przełącza się na `yin` (wolniejszy, tylko numpy).

Wykrywacz początków (`detect_onsets`) zostaje, ale tylko do analizy nagrań (skuteczność detektora, [design.md](../design.md) krok 9).

## Konsekwencje
- Działa przy płynnym śpiewie i daje od razu wartość korekty #GAP.
- Wymaga odczytu wysokości całego wokalu: kilkadziesiąt sekund (yin) albo kilkanaście (crepe na GPU).
- Nie wykryje przesunięcia większego niż ±300 ms. Takie przypadki wyjdą jako niska zgodność ze stosownym komunikatem.
