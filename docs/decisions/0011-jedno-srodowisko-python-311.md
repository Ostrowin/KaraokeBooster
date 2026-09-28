# 0011. Jedno środowisko .venv na Pythonie 3.11

- Status: przyjęta
- Data: 2026-09-28
- Źródło: /plan-eng-review, D3

## Kontekst
Na laptopie jest tylko Python 3.13 (`py -0`). Wsparcie Demucs i torchcrepe dla 3.13 jest niepotwierdzone.

## Decyzja
Jeden venv projektu (`.venv`, Python 3.11) dla wszystkich narzędzi, testów i AI. Zależności w `pyproject.toml` z grupami `base`, `ml` i `dev`.

## Konsekwencje
- Trzeba doinstalować Python 3.11 (uruchamiany przez `py -3.11`).
- Instalacja ciągnie PyTorch (kilka GB), także wtedy, gdy potrzebny jest tylko konwerter.
