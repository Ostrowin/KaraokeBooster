"""Odczyt wysokości głosu z nagrania.

Dwa silniki, ten sam wynik: (czasy_s, f0_hz, pewność 0..1), krok 10 ms.
- "crepe": torchcrepe (grupa zależności `ml`), dokładny, GPU jeśli dostępne.
- "yin":   prosty YIN na numpy, bez PyTorcha (testy i zapas).
f0 = 0 oznacza ramkę bez głosu.
"""

from __future__ import annotations

import numpy as np

HOP_S = 0.010
FMIN, FMAX = 65.0, 1000.0


def hz_to_midi(f0: np.ndarray) -> np.ndarray:
    out = np.full(f0.shape, np.nan)
    voiced = f0 > 0
    out[voiced] = 69 + 12 * np.log2(f0[voiced] / 440.0)
    return out


def _mono(samples: np.ndarray) -> np.ndarray:
    s = np.asarray(samples, dtype=np.float64)
    return s.mean(axis=1) if s.ndim > 1 else s


def yin(samples: np.ndarray, sr: int, threshold: float = 0.15,
        silence_db: float = -45.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x = _mono(samples)
    hop = int(sr * HOP_S)
    tau_min, tau_max = int(sr / FMAX), int(sr / FMIN)
    W = tau_max + 2                     # okno porównania
    frame = W + tau_max + 2             # ramka mieści okno przesunięte o tau_max + 1
    n_frames = max(0, (len(x) - frame) // hop + 1)
    times = np.arange(n_frames) * HOP_S + frame / 2 / sr
    f0 = np.zeros(n_frames)
    conf = np.zeros(n_frames)
    peak = np.max(np.abs(x)) if len(x) else 0.0
    if peak <= 0:
        return times, f0, conf
    nfft = 1 << (2 * frame - 1).bit_length()
    taus = np.arange(tau_max + 2)
    for i in range(n_frames):
        w = x[i * hop: i * hop + frame]
        if 20 * np.log10(np.sqrt(np.mean(w ** 2)) / peak + 1e-12) < silence_db:
            continue
        # d(tau) = sum_{j<W} (w[j] - w[j+tau])^2 = e0 + e(tau) - 2 * cross(tau)
        cross = np.fft.irfft(np.fft.rfft(w, nfft) * np.conj(np.fft.rfft(w[:W], nfft)), nfft)[taus]
        c = np.concatenate(([0.0], np.cumsum(w ** 2)))
        d = c[W] + (c[taus + W] - c[taus]) - 2 * cross
        d[0] = 0
        cmnd = np.ones_like(d)
        cmnd[1:] = d[1:] * np.arange(1, len(d)) / np.maximum(np.cumsum(d[1:]), 1e-12)
        cand = np.where(cmnd[tau_min:tau_max] < threshold)[0]
        if len(cand) == 0:
            continue
        t = cand[0] + tau_min
        while t + 1 < tau_max and cmnd[t + 1] < cmnd[t]:
            t += 1
        a, b, c = cmnd[t - 1], cmnd[t], cmnd[t + 1]
        denom = a - 2 * b + c
        shift = 0.5 * (a - c) / denom if abs(denom) > 1e-12 else 0.0
        f0[i] = sr / (t + shift)
        conf[i] = float(np.clip(1 - b, 0, 1))
    return times, f0, conf


def crepe(samples: np.ndarray, sr: int, model: str = "full",
          device: str | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    import torch
    import torchaudio.functional as AF
    import torchcrepe

    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    audio = torch.tensor(_mono(samples), dtype=torch.float32)[None]
    if sr != 16000:
        audio = AF.resample(audio, sr, 16000)
    f0, periodicity = torchcrepe.predict(
        audio, 16000, hop_length=160, fmin=FMIN, fmax=FMAX, model=model,
        return_periodicity=True, batch_size=512, device=device)
    f0 = f0[0].cpu().numpy().astype(np.float64)
    conf = periodicity[0].cpu().numpy().astype(np.float64)
    times = np.arange(len(f0)) * HOP_S
    f0[conf < 0.1] = 0.0
    return times, f0, conf


def track(samples: np.ndarray, sr: int, engine: str = "crepe"):
    if engine == "yin":
        return yin(samples, sr)
    if engine == "crepe":
        return crepe(samples, sr)
    raise ValueError(f"Nieznany silnik wysokości: {engine}")
