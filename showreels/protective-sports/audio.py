"""Synthesised cinematic soundtrack (120 BPM, A minor) cut to the showreel's scene changes."""
import wave

import numpy as np

SR = 48000
BPM = 120
BEAT = 60 / BPM
RNG = np.random.default_rng(1991)

# Am – F – C – G, one chord per bar (2 s)
CHORDS = [[57, 60, 64, 69], [53, 57, 60, 65], [48, 55, 60, 64], [55, 59, 62, 67]]
ROOTS = [45, 41, 36, 43]


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def env_adsr(n, a, d, s, r, sr=SR):
    a, d, r = int(a * sr), int(d * sr), int(r * sr)
    e = np.full(n, s, np.float32)
    e[:a] = np.linspace(0, 1, a, endpoint=False) if a else e[:a]
    e[a:a + d] = np.linspace(1, s, len(e[a:a + d]))
    if r:
        e[-r:] *= np.linspace(1, 0, len(e[-r:]))
    return e


def add(buf, sig, t0, gain=1.0, pan=0.0):
    i = int(t0 * SR)
    if i >= buf.shape[1]:
        return
    sig = sig[: buf.shape[1] - i]
    l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    buf[0, i:i + len(sig)] += sig * gain * l * 1.414
    buf[1, i:i + len(sig)] += sig * gain * r * 1.414


def lowpass(x, cutoff):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / np.sqrt(1 + (f / cutoff) ** 4)
    return np.fft.irfft(X, len(x)).astype(np.float32)


def bandnoise(n, lo, hi):
    X = np.fft.rfft(RNG.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / SR)
    X *= (f > lo) & (f < hi)
    y = np.fft.irfft(X, n)
    return (y / (np.abs(y).max() + 1e-9)).astype(np.float32)


def pad_note(freq, dur, bright=0.35):
    t = np.arange(int(dur * SR)) / SR
    y = np.zeros_like(t)
    for det in (-0.12, 0.0, 0.11):
        f = freq * 2 ** (det / 12)
        for h in range(1, 14):
            amp = (1 / h) * np.exp(-h * (1 - bright) * 0.55)
            y += amp * np.sin(2 * np.pi * f * h * t + RNG.uniform(0, 6.28))
    return (y / 6).astype(np.float32)


def pluck(freq, dur=1.2, bright=0.6):
    t = np.arange(int(dur * SR)) / SR
    y = np.zeros_like(t)
    for h in range(1, 9):
        y += (1 / h ** 1.3) * np.sin(2 * np.pi * freq * h * t) * np.exp(-t * (2.5 + h * 1.6 * (1.2 - bright)))
    return (y * np.minimum(1, t / 0.003)).astype(np.float32)


def bell(freq, dur=2.5):
    t = np.arange(int(dur * SR)) / SR
    y = np.zeros_like(t)
    for ratio, amp, dec in [(1, 1, 1.4), (2.0, 0.5, 2.2), (2.76, 0.35, 3.0), (5.4, 0.2, 5.0)]:
        y += amp * np.sin(2 * np.pi * freq * ratio * t) * np.exp(-t * dec)
    return (y * np.minimum(1, t / 0.002) * 0.5).astype(np.float32)


def kick(dur=0.5, punch=1.0):
    t = np.arange(int(dur * SR)) / SR
    f = 42 + 140 * np.exp(-t * 32)
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = np.sin(ph) * np.exp(-t * 7.5) * punch
    y += 0.25 * bandnoise(len(t), 1500, 6000) * np.exp(-t * 120)
    return np.tanh(y * 1.6).astype(np.float32)


def hat(dur=0.08, open_=False):
    n = int((0.25 if open_ else dur) * SR)
    t = np.arange(n) / SR
    return (bandnoise(n, 7000, 16000) * np.exp(-t * (14 if open_ else 60)) * 0.5).astype(np.float32)


def clap():
    n = int(0.4 * SR)
    t = np.arange(n) / SR
    e = np.exp(-t * 18)
    for k in (0.0, 0.011, 0.022):
        e += np.exp(-np.maximum(t - k, 0) * 140) * (t >= k)
    return (bandnoise(n, 900, 5000) * e * 0.35).astype(np.float32)


def bass(freq, dur):
    t = np.arange(int(dur * SR)) / SR
    y = np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * freq * 2 * t) + 0.12 * np.sin(2 * np.pi * freq * 3 * t)
    return (np.tanh(y * 1.4) * env_adsr(len(t), 0.004, 0.08, 0.6, 0.05)).astype(np.float32)


def impact(size=1.0, dur=4.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 30 + 110 * np.exp(-t * 9)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.6)
    hit = bandnoise(n, 60, 9000) * np.exp(-t * 9) * 0.55
    sub = np.sin(2 * np.pi * 36 * t) * np.exp(-t * 1.0) * 0.5
    return (np.tanh((boom + hit + sub) * 1.3) * size).astype(np.float32)


def riser(dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    p = t / dur
    out = np.zeros(n, np.float32)
    hop = 2048
    win = np.hanning(hop * 2).astype(np.float32)
    for s in range(0, n - hop * 2, hop):
        c = 300 + 9000 * (p[s] ** 2.2)
        seg = bandnoise(hop * 2, c * 0.5, c * 1.6) * win
        out[s:s + hop * 2] += seg
    tone = np.sin(2 * np.pi * np.cumsum(220 + 660 * p ** 2) / SR) * 0.25
    return ((out * 0.6 + tone) * p ** 2.5).astype(np.float32)


def whoosh(dur=0.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    e = np.sin(np.pi * t / dur) ** 2
    return (bandnoise(n, 400, 6000) * e * 0.8).astype(np.float32)


def reverb(x, seconds=2.8, mix=0.3):
    n = int(seconds * SR)
    t = np.arange(n) / SR
    out = np.empty_like(x)
    for c in range(2):
        ir = RNG.standard_normal(n).astype(np.float32) * np.exp(-t * 6.9 / seconds)
        ir = lowpass(ir, 5000)
        ir /= np.sqrt((ir ** 2).sum())
        L = x.shape[1] + n
        N = 1 << int(np.ceil(np.log2(L)))
        wet = np.fft.irfft(np.fft.rfft(x[c], N) * np.fft.rfft(ir, N), N)[: x.shape[1]]
        out[c] = x[c] * (1 - mix) + wet * mix * 2.2
    return out


def render(path, dur=30.0):
    n = int((dur + 0.5) * SR)
    dry = np.zeros((2, n), np.float32)   # drums / bass (little reverb)
    wet = np.zeros((2, n), np.float32)   # pads / tonal (lush reverb)
    tt = np.arange(n) / SR

    # sub drone + pads
    drone = np.sin(2 * np.pi * 55 * tt) * 0.18 + np.sin(2 * np.pi * 82.4 * tt) * 0.06
    drone *= np.clip(tt / 2.5, 0, 1) * (1 - np.clip((tt - 26.0) / 3.5, 0, 1) * 0.3)
    wet += drone.astype(np.float32)
    for bar in range(int(dur / 2) + 1):
        t0 = bar * 2.0
        ch = CHORDS[bar % 4]
        bright = 0.25 if t0 < 8 else 0.45 if t0 < 22 else 0.35
        g = 0.07 if t0 < 3 else 0.11
        for k, m in enumerate(ch):
            sig = pad_note(mtof(m), 2.6, bright) * env_adsr(int(2.6 * SR), 0.6, 0.4, 0.8, 0.9)
            add(wet, sig, t0 - 0.2 if t0 > 0 else 0, g, pan=(k - 1.5) * 0.35)

    # intro heartbeat
    for b in (0.5, 1.5, 2.4):
        add(dry, kick(0.5, 0.6), b, 0.45)
        add(dry, kick(0.5, 0.45), b + 0.22, 0.32)
    add(wet, whoosh(1.2), 2.2, 0.35)
    add(wet, impact(0.5), 3.0, 0.5)

    # dawn: sparse piano-ish arpeggio
    arp = [0, 2, 3, 1, 2, 3, 1, 3]
    for s in range(int((8 - 3) / (BEAT / 2))):
        t0 = 3 + s * BEAT / 2
        ch = CHORDS[int(t0 / 2) % 4]
        add(wet, pluck(mtof(ch[arp[s % 8]] + 12), 1.4, 0.5), t0, 0.16, pan=0.4 * np.sin(s))
    add(wet, riser(1.5), 6.5, 0.45)

    # drop — road
    add(dry, impact(1.0), 8.0, 0.9)
    for s in range(int((22.5 - 8) / BEAT)):
        t0 = 8 + s * BEAT
        nordic = 13 <= t0 < 17.5
        if not nordic or s % 2 == 0:
            add(dry, kick(0.45, 1.0), t0, 0.75 if not nordic else 0.55)
        if not nordic:
            add(dry, hat(), t0 + BEAT / 2, 0.22, pan=0.3)
            add(dry, hat(0.05), t0 + BEAT / 4, 0.08, pan=-0.3)
            add(dry, hat(0.05), t0 + 3 * BEAT / 4, 0.08, pan=-0.3)
        if t0 >= 17.5 and s % 2 == 1:
            add(dry, clap(), t0, 0.5)
        root = ROOTS[int(t0 / 2) % 4]
        if not nordic:
            for e in (0, 0.5):
                add(dry, bass(mtof(root), BEAT / 2 * 0.9), t0 + e * BEAT, 0.3)
        else:
            add(dry, bass(mtof(root), BEAT * 1.8), t0, 0.22) if s % 2 == 0 else None
    add(dry, hat(open_=True), 12.5, 0.25)

    # whoosh into nordic + ice bells
    add(wet, whoosh(0.6), 12.65, 0.6)
    for s in range(int(4.5 / (BEAT / 2))):
        t0 = 13 + s * BEAT / 2
        ch = CHORDS[int(t0 / 2) % 4]
        add(wet, bell(mtof(ch[(s * 3) % 4] + 24)), t0, 0.07, pan=np.sin(s * 1.7) * 0.7)

    # values
    add(wet, impact(0.6), 17.5, 0.55)
    for s in range(10):
        t0 = 17.5 + s * BEAT
        ch = CHORDS[int(t0 / 2) % 4]
        add(wet, pluck(mtof(ch[s % 4] + 12), 1.0, 0.7), t0 + BEAT / 2, 0.1, pan=-0.4)

    # craft — breakdown with ticking counter
    add(wet, impact(0.4), 22.5, 0.4)
    for s in range(int(3.5 / (BEAT / 4))):
        t0 = 22.5 + s * BEAT / 4
        if t0 > 25.8:
            break
        add(dry, hat(0.02), t0, 0.12 if s % 4 else 0.2, pan=0.2 * (-1) ** s)
    add(wet, riser(2.0), 24.0, 0.55)

    # logo — the big hit and a long resolving chord
    add(dry, impact(1.1, 4.5), 26.0, 1.0)
    for k, m in enumerate([45, 57, 64, 69, 71, 76]):
        sig = pad_note(mtof(m), 4.4, 0.4) * env_adsr(int(4.4 * SR), 0.05, 1.0, 0.7, 2.6)
        add(wet, sig, 26.0, 0.11, pan=(k - 2.5) * 0.25)
    for k, m in enumerate([81, 76, 72, 69]):
        add(wet, bell(mtof(m), 3.0), 26.4 + k * 0.25, 0.08, pan=(k - 1.5) * 0.4)

    mix = reverb(wet, 3.2, 0.42) + reverb(dry, 1.2, 0.12)
    mix = mix[:, : int(dur * SR)]
    fade = np.clip((dur - np.arange(mix.shape[1]) / SR) / 0.8, 0, 1)
    mix *= fade
    mix = np.tanh(mix * 1.1)
    mix /= np.abs(mix).max() / 0.89
    pcm = (mix.T * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return path


if __name__ == "__main__":
    import sys
    render(sys.argv[1] if len(sys.argv) > 1 else "soundtrack.wav")
