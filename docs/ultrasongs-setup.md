# Generator piosenek: ultrasongs

Tworzy plik UltraStar z audio i tekstu piosenki ([decyzja 0015](decisions/0015-generator-ultrasongs.md)).
Projekt: https://github.com/Beherith/ultrasongs (licencja MIT).

## Instalacja (Windows, GTX 1050)

Ultrasongs żyje **poza naszym repo**, we własnym środowisku. Wymaga innego PyTorcha (2.8) niż nasz `.venv` (2.14).

1. ffmpeg (jednorazowo, w systemie):
   ```bash
   winget install Gyan.FFmpeg
   ```
   Po instalacji zrestartuj terminal.

2. Kod i środowisko:
   ```bash
   cd C:\Projects\Private
   git clone https://github.com/Beherith/ultrasongs.git
   cd ultrasongs
   py -3.11 -m venv .venv
   .venv\Scripts\python -m pip install --upgrade pip
   ```

3. Obejście 1: `antlr4-python3-runtime 4.9.3` (zależność whisperx) nie buduje się z nowym setuptools:
   ```bash
   .venv\Scripts\python -m pip install "setuptools<70" wheel
   .venv\Scripts\python -m pip install --no-build-isolation antlr4-python3-runtime==4.9.3
   ```

4. Zależności. Z `cli/requirements.txt` usuń linię `--extra-index-url` (cu128) oraz, jeśli nie potrzebujesz interfejsu WWW, `dash` i `flask`. Potem:
   ```bash
   .venv\Scripts\python -m pip install -r requirements-bez-cu128.txt -e cli/
   ```

5. Obejście 2: whisperx wymusza PyTorch 2.8 i pip instaluje wersję **tylko na CPU**. Podmień ją na wersję z CUDA 12.6 (obsługuje GTX 1050). Pobiera ok. 2,9 GB:
   ```bash
   .venv\Scripts\python -m pip install --force-reinstall --no-deps torch==2.8.0 torchaudio==2.8.0 torchvision==0.23.0 --index-url https://download.pytorch.org/whl/cu126
   ```

6. Sprawdzenie:
   ```bash
   .venv\Scripts\python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
   ```
   Oczekiwane: `2.8.0+cu126 True`.

Przy pierwszym uruchomieniu dociągną się modele (Demucs, Whisper medium, wav2vec2 dla danego języka): kilkaset MB.

## Użycie dla polskiej piosenki

```bash
cd C:\Projects\Private\ultrasongs
.venv\Scripts\python -m cli -o whisper_language=pl,transcribe_runs=3,whisperx_align_runs=3 process --mp3 "piosenka.mp3" --lyrics "tekst.txt" --title "Tytuł" --artist "Wykonawca"
```

- `--lyrics`: zwykły tekst piosenki, linia po linii (UTF-8). Program dopasowuje go w czasie, więc tekst nie pochodzi z rozpoznawania mowy.
- `transcribe_runs` / `whisperx_align_runs`: liczba przebiegów (domyślnie 7 i 5). Więcej przebiegów to lepsza zgodność, ale dłuższy czas. Na GTX 1050 domyślne ustawienia dla 35 s próbki zajęły ok. 20 min (bez pobierania modeli).
- Wynik trafia do `output\<Wykonawca> - <Tytuł>\`:
  - `.txt`: UltraStar;
  - `_vocals.mp3`, `_accompaniment.mp3`: wokal i podkład;
  - `_editor.html`: edytor nut do ręcznej korekty.

## Dalej w KaraokeBooster

```bash
.venv\Scripts\python tools\ultrastar2midi.py "…\piosenka.txt" -o song.mid --vocals "…\piosenka_vocals.mp3"
```

**Oktawa.** Ultrasongs zapisuje wysokości o 3 oktawy za wysoko względem standardu UltraStar. `ultrastar2midi.py` domyślnie (`--octave auto`) przenosi melodię w zakres głosu (środek G3, zmiana przez `--voice-center`).

## Jakość (próbka z repo ultrasongs, porównanie z plikiem wzorcowym)

| Metryka | Wynik |
|---|---|
| Słowa zgodne ze wzorcem | 80 / 83 |
| Czas startu słowa | mediana 0 ms, p50 43 ms, p80 83 ms, max 264 ms |
| Nuta (bez oktawy) | 82% ta sama, 98% w ±1 półtonie |
