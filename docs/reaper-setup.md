# Etap 1 w REAPER: lista kroków

Odhaczaj po kolei. Każdy blok kończy się punktem "sprawdź". Jeśli coś nie wyjdzie, zapisz, co się stało, i wróć do rozmowy z Claude.
Pojęcia (bufor, PDC, sidechain, CC) wyjaśnia [glossary.md](glossary.md).

**Pliki potrzebne na start** (dla "Za tobą pójdę jak na bal"):
- `C:\Projects\Private\ultrasongs\output\Krzysztof Krawczyk - Za tobą pójdę jak na bal\`
  - `…_accompaniment.mp3`: podkład (bez wokalu),
  - `…_vocals.mp3`: wokal Krawczyka (do trybu ghost),
  - `….txt`: plik UltraStar (dla podglądu tekstu);
- `C:\Projects\Private\KaraokeBooster\songs\za-toba.mid`: nuty dla korektora (z `ultrastar2midi.py`).

---

## Blok A: instalacje (ok. 20 min)

- [ ] **REAPER** z https://www.reaper.fm (wersja 64-bit, 60 dni za darmo, potem licencja domowa ok. 60 USD).
- [ ] **ASIO4ALL** z https://asio4all.org: sterownik niskiego opóźnienia dla wbudowanej karty Realtek. Niepotrzebny, jeśli masz interfejs audio USB z własnym sterownikiem ASIO.
- [ ] **MotTune MIDI**: darmowa wtyczka. Źródło: ogłoszenia z 2026-09-05 (bedroomproducersblog.com, rekkerd.org) prowadzą do strony autora. Pobieraj tylko stamtąd. Zainstaluj wersję **VST3 64-bit**.
- [ ] W REAPER: Options → Preferences → Plug-ins → VST → **Re-scan**.
- [ ] **Sprawdź:** nowa ścieżka (Ctrl+T) → przycisk **FX** → w polu wyszukiwania wpisz "MotTune" → jest **VST3: MotTune MIDI (MotTune)**. To efekt, więc **nie ma go** w Insert → Virtual instrument (tam są tylko instrumenty).
  Wtyczka instaluje się do `C:\Program Files\Common Files\VST3\MotTune MIDI.vst3`.
  Jeśli nie ma wersji Windows albo VST3, **stop**: zapisz to i przejdź do rozmowy (plan B w [design.md](design.md), krok 2).

## Blok B: urządzenie audio (ok. 10 min)

- [ ] Options → Preferences → Audio → Device:
  - Audio system: **ASIO**;
  - ASIO driver: sterownik interfejsu albo **ASIO4ALL v2**;
  - w ASIO4ALL włącz **to samo urządzenie** dla wejścia i wyjścia (Realtek), a inne wyłącz ([decyzja 0006](decisions/0006-jedno-urzadzenie-audio-i-opoznienie.md): jeden zegar);
  - Sample rate **48000**, Block size **128**.
- [ ] **Sprawdź:** na dole tego okna REAPER pokazuje opóźnienie wejścia i wyjścia w ms. Zapisz obie liczby w [latency.md](latency.md) w kolumnie "Uwagi" (to wartości deklarowane przez sterownik, nie pomiar).

## Blok C: pomiar opóźnienia (ok. 20 min)

Potrzebny kabel mini-jack ↔ mini-jack (3,5 mm): z wyjścia słuchawkowego do wejścia mikrofonowego laptopa. **Ścisz wyjście do ok. 30%**, żeby nie przesterować wejścia.

- [ ] Options → Preferences → Audio → Recording → **wyłącz** "Use audio driver reported latency" (mierzymy surowe opóźnienie).
- [ ] Ścieżka 1: Insert → **Click source** (krótki impuls metronomu), 2-3 sekundy.
- [ ] Ścieżka 2: wejście = wejście mikrofonowe, **Record arm**, monitoring wyłączony.
- [ ] Nagraj kilka sekund (Ctrl+R, potem Stop).
- [ ] Powiększ oś czasu na pierwszy impuls na obu ścieżkach. Zaznacz odcinek od impulsu na ścieżce 1 do impulsu na ścieżce 2. Długość zaznaczenia (na dole, w ms) to **pełna pętla**.
- [ ] Powtórz dla Block size **64** i **256**.
- [ ] Wpisz wyniki do [latency.md](latency.md).
- [ ] Na koniec **włącz z powrotem** "Use audio driver reported latency".
- [ ] **Sprawdź:** wg [decyzji 0006](decisions/0006-jedno-urzadzenie-audio-i-opoznienie.md):
  - ≤ 25 ms: świetnie;
  - 25-40 ms: dalej, oceniając komfort śpiewania;
  - \> 40 ms przy każdym buforze: stop, potrzebny interfejs audio.

Bez kabla: klaśnij przy mikrofonie w słuchawkach, nagraj i porównaj z metronomem. Wynik jest mniej dokładny (plus/minus kilka ms), ale na pierwszą ocenę wystarczy.

## Blok D: projekt piosenki (ok. 15 min)

- [ ] Options → Preferences → Media → **wyłącz** "Automatically adjust media to project tempo" (albo odpowiadaj "No" przy imporcie).
- [ ] Nowy projekt, tempo **120 BPM**. Zapisz go w `songs\za-toba\za-toba.rpp` (folder jest w `.gitignore`).
- [ ] Przeciągnij na oś czasu w pozycję **0:00**:
  - `…_accompaniment.mp3` na ścieżkę **Podkład**;
  - `…_vocals.mp3` na ścieżkę **Ghost** (na razie wyciszoną, M);
  - `za-toba.mid` na ścieżkę **Wokal**. Przy pytaniu o tempo: **nie importuj** mapy tempa ([decyzja 0010](decisions/0010-midi-w-sekundach-i-kontrola-wyrownania.md)).
- [ ] Na ścieżkach Podkład i Ghost: prawy klik na ścieżce → Track timebase → **Time**.
- [ ] **Sprawdź:** Play. Pierwsze nuty MIDI (kreski na ścieżce Wokal) zaczynają się tam, gdzie Krawczyk zaczyna śpiewać (ok. 32 s).

## Blok E: korektor na ścieżce Wokal (ok. 20 min)

Na ścieżce Wokal są naraz nuty MIDI i Twój mikrofon. Nuty sterują wtyczką, a mikrofon przez nią przechodzi.

- [ ] Wejście ścieżki: mikrofon (Mono), **Record arm** + **monitoring włączony** (ikonka głośnika), a do tego ustaw "Record: disable (input monitoring only)", żeby nie nagrywać przy próbach.
- [ ] FX ścieżki (przycisk FX albo klawisz **F** na zaznaczonej ścieżce): dodaj **MotTune MIDI** (v1.2.0) i ustaw:
  - przełącznik u góry: **Real Time** (nie Studio; Studio ma bufor wyprzedzenia);
  - **MIDI Input**: zaznaczone (Key/Scale robią się wtedy szare, a nuty idą z MIDI);
  - **Pitch Lock**: 100 (pełne przyciągnięcie do nuty = tryb twardy);
  - **Retune Speed**: 100 na start. Kierunek skali jest niepotwierdzony, więc porównaj uchem z 20 i zapisz, która wartość daje szybsze "przeskoki";
  - **Formant A / Formant B**: 0,0 (bez zmiany barwy);
  - **Balance A-B**: sprawdź, przy której skrajnej wartości słychać Twój poprawiony głos, a przy której wokoder; ustaw na głos;
  - sekcja **VOCODER SOUND**: nieużywana, **Volume** = 0,0.
- [ ] Opóźnienie wtyczki: pasek na dole okna FX pokazuje "…/… spls". **0/0 spls = 0 próbek** (zmierzone 2026-09-29, Real Time).
- [ ] Załóż słuchawki (w tym bloku bez głośników, żeby nie było sprzężenia). Play i śpiewaj z Krawczykiem.
- [ ] **Sprawdź i zapisz** (to weryfikacja z kroku 2 [design.md](design.md)):
  - [ ] głos jest ściągany do nut z pliku (śpiewaj celowo obok);
  - [ ] PDC wtyczki: FX → prawy klik na MotTune → wartość "PDC" w ms (wpisz do [latency.md](latency.md));
  - [ ] co się dzieje **w przerwach między frazami**: głos czysty, trzyma ostatnią nutę czy ściąga do skali;
  - [ ] jak brzmi, gdy śpiewasz 3-5 półtonów obok (akceptowalne czy "robot/wiewiórka");
  - [ ] czy słyszysz opóźnienie ("echo" własnego głosu).

**Bypass w przerwach** (tylko jeśli w przerwach MotTune trzyma nutę albo skalę): plik MIDI wysyła CC 85 (127 = wyłącz korekcję, 0 = włącz).
- [ ] W oknie FX: Param → FX parameter list → **Parameter modulation/MIDI link** → parametr **Bypass** → Link from MIDI → **CC 85**.
- [ ] **Sprawdź:** w przerwach słychać Twój naturalny głos.

## Blok F: upiększacze (ok. 15 min)

Za MotTune, na tej samej ścieżce Wokal, w tej kolejności:
- [ ] **ReaComp**: ratio 3:1, threshold tak, żeby wskazanie redukcji skakało o 3-6 dB przy śpiewie.
- [ ] **ReaEQ**: lekkie obcięcie basu (high-pass ok. 100 Hz), lekkie podbicie ok. 3 kHz (+2 dB) dla wyrazistości.
- [ ] **De-esser**: ReaXcomp z jednym pasmem 5-8 kHz albo darmowy de-esser VST (ściszanie syczących "s", "sz", "ć").
- [ ] **ReaVerbate**: pogłos Wet ok. −15 dB (niewielki; więcej zwiększa ryzyko sprzężenia na głośnikach).
- [ ] **Sprawdź:** porównaj z wyłączonym łańcuchem (przycisk bypass FX). Głos ma brzmieć pełniej, ale naturalnie.

## Blok G: ghost vocal (ok. 15 min)

Ghost to cichy oryginalny wokal, który przycicha, gdy śpiewasz ([decyzja 0007](decisions/0007-trzy-tryby-korekcji.md)).
- [ ] Ścieżka Ghost: odcisz (zdejmij M) i ustaw poziom ok. **−12 dB** względem podkładu.
- [ ] Ścieżka Ghost → Routing → liczba kanałów ścieżki: **4**.
- [ ] Ścieżka Wokal → Routing → Add send → Ghost, ustaw na kanały **3/4** (to "sidechain": Twój głos steruje ściszaniem ghosta).
- [ ] Na ścieżce Ghost dodaj **ReaComp**: Detector input = **Auxiliary input L+R**, threshold nisko (ok. −40 dB), ratio wysoki (ok. 10:1), release ok. 400 ms.
- [ ] **Sprawdź:** gdy śpiewasz, Krawczyk w tle cichnie. Gdy milkniesz w trakcie frazy, wraca.

## Blok H: tekst na ekranie (ok. 10 min)

- [ ] REAPER: Options → Preferences → Control/OSC/web → **Add** → Control surface mode: **OSC**. Pattern config: **Default**. Mode: Configure device IP + local port. Device IP: **127.0.0.1**, Device port: **9000**. Zaznacz wysyłanie.
- [ ] W terminalu:
  ```bash
  cd C:\Projects\Private\KaraokeBooster
  .venv\Scripts\python tools\lyrics_viewer.py "C:\Projects\Private\ultrasongs\output\Krzysztof Krawczyk - Za tobą pójdę jak na bal\Krzysztof Krawczyk - Za tobą pójdę jak na bal.txt" --port 9000
  ```
- [ ] **Sprawdź:** Play w REAPER. Tekst przewija się razem z muzyką, pauza go zatrzymuje, przewinięcie przeskakuje.
  Jeśli tekst wyprzedza dźwięk, uruchom podgląd z `--offset-ms` równym opóźnieniu wyjścia z bloku B.

## Blok I: nagrania do analizy (ok. 20 min)

To dane do strojenia etapu 2 ([design.md](design.md), kroki 8-9).
- [ ] **Wyłącz** MotTune (bypass). Nagrywamy Twój naturalny śpiew.
- [ ] Ustaw "Record: input (audio)", nagraj **3 razy** całą piosenkę albo co najmniej dwa refreny.
- [ ] Każde nagranie: File → Render → wybrana ścieżka Wokal, od 0:00, WAV → `songs\za-toba\take1.wav` itd.
- [ ] Ręczne znaczniki sylab: w REAPER klawisz **M** na początku każdej sylaby, dla fragmentu ok. 30 s na nagranie. Potem View → Region/Marker Manager → Export (CSV) do `songs\za-toba\take1_markers.csv`.
- [ ] W terminalu:
  ```bash
  .venv\Scripts\python tools\analyze_takes.py "…\Krzysztof Krawczyk - Za tobą pójdę jak na bal.txt" songs\za-toba\take1.wav songs\za-toba\take2.wav songs\za-toba\take3.wav --markers songs\za-toba\take1_markers.csv songs\za-toba\take2_markers.csv songs\za-toba\take3_markers.csv --octave -5 --json songs\za-toba\wyniki.json
  ```
  (`--octave -5`, bo plik z ultrasongs ma o 3 oktawy za wysokie nuty, a `ultrastar2midi.py` dobrał dla niego −5.)

## Blok J: próba na głośnikach (na koniec)

- [ ] Głośniki **przed** Tobą, mikrofon trzymany przy ustach.
- [ ] Zacznij cicho i zwiększaj głośność. Przy piszczeniu ścisz, zmniejsz pogłos, obróć mikrofon tyłem do głośników.
- [ ] **Sprawdź:** brak sprzężenia przy głośności imprezowej (ok. 85 dB w 1 m, np. aplikacja miernika w telefonie), ghost nie "trzyma się" sam przez głośniki, a śpiewa się wygodnie.

---

**Co przynieść z powrotem do rozmowy:**
- wypełniony [latency.md](latency.md);
- odpowiedzi z bloku E (przerwy, 3-5 półtonów, echo);
- `wyniki.json` z bloku I;
- wrażenia z bloku J.
