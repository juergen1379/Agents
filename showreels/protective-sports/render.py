#!/usr/bin/env python3
"""
PROTECTIVE — 30s Motion-Graphics Showreel
Procedural 1080p renderer (numpy + Pillow) piped into ffmpeg.

Usage:
  python3 render.py                 # full render -> out/protective_showreel.mp4
  python3 render.py --preview 4.2 9 # write PNG stills for the given seconds
  FPS=30 python3 render.py          # faster draft render

Optional real photography: drop JPGs into ./photos/ named
  dawn.jpg  road.jpg  nordic.jpg  textile.jpg  logo.jpg
and they replace the procedural backgrounds of the matching scene
(with Ken-Burns move + colour grade). Everything else stays identical.
"""
import math
import os
import subprocess
import sys
from functools import lru_cache
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import audio

W, H = 1920, 1080
FPS = int(os.environ.get("FPS", 60))
DUR = 30.0
ROOT = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(ROOT, "fonts")
PHOTO_DIR = os.path.join(ROOT, "photos")
OUT_DIR = os.path.join(ROOT, "out")

WHITE = (0.97, 0.96, 0.94)
EMBER = (1.0, 0.36, 0.12)
ICE = (0.62, 0.85, 1.0)

# scene boundaries (seconds) — synced to the 120 BPM soundtrack
T_DAWN, T_ROAD, T_NORDIC, T_VALUES, T_CRAFT, T_LOGO = 3.0, 8.0, 13.0, 17.5, 22.5, 26.0
IMPACTS = [T_ROAD, T_NORDIC, T_LOGO]


# ----------------------------------------------------------------- helpers
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def prog(t, a, b):
    return clamp((t - a) / (b - a))


def eo_expo(x):
    return 1.0 if x >= 1 else 1 - 2 ** (-10 * x)


def ei_expo(x):
    return 0.0 if x <= 0 else 2 ** (10 * x - 10)


def eo_cubic(x):
    return 1 - (1 - x) ** 3


def eio_cubic(x):
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def eio_sine(x):
    return -(math.cos(math.pi * x) - 1) / 2


def lerp(a, b, x):
    return a + (b - a) * x


def to_u8(img):
    return (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)


def from_u8(a):
    return a.astype(np.float32) * (1.0 / 255)


def gradient(stops, n):
    ys = np.linspace(0, 1, n)
    out = np.zeros((n, 3), np.float32)
    ps = [s[0] for s in stops]
    for c in range(3):
        out[:, c] = np.interp(ys, ps, [s[1][c] for s in stops])
    return out


def vgrad_img(stops, w=W, h=H):
    g = gradient(stops, h)
    return np.repeat(g[:, None, :], w, axis=1)


def paste(img, L, x, y, a=1.0, add=False, clip=None):
    """Alpha-composite float RGBA layer L onto float RGB img at (x, y)."""
    if a <= 0.002:
        return
    h, w = L.shape[:2]
    x, y = int(round(x)), int(round(y))
    cx0, cy0, cx1, cy1 = clip if clip else (0, 0, W, H)
    cx0, cy0 = max(cx0, 0), max(cy0, 0)
    cx1, cy1 = min(cx1, img.shape[1]), min(cy1, img.shape[0])
    x0, y0 = max(x, cx0), max(y, cy0)
    x1, y1 = min(x + w, cx1), min(y + h, cy1)
    if x0 >= x1 or y0 >= y1:
        return
    sub = L[y0 - y:y1 - y, x0 - x:x1 - x]
    if sub.dtype == np.uint8:
        sub = from_u8(sub)
    al = sub[..., 3:4] * a
    if add:
        img[y0:y1, x0:x1] += sub[..., :3] * al
    else:
        dst = img[y0:y1, x0:x1]
        dst *= 1 - al
        dst += sub[..., :3] * al


def glow_field(cx, cy, sigma, w=W, h=H, scale=4):
    """Gaussian glow computed at low res and upsampled (fast soft light)."""
    sw, sh = w // scale, h // scale
    xs = (np.arange(sw) * scale - cx) / sigma
    ys = (np.arange(sh) * scale - cy) / sigma
    g = np.exp(-0.5 * (ys[:, None] ** 2 + xs[None, :] ** 2)).astype(np.float32)
    im = Image.fromarray(g, mode="F").resize((w, h), Image.BILINEAR)
    return np.asarray(im)


def camera(img, zoom=1.0, dx=0.0, dy=0.0):
    """Push-in / shake by cropping and resampling."""
    if abs(zoom - 1) < 1e-4 and abs(dx) < 0.5 and abs(dy) < 0.5:
        return img
    cw, ch = W / zoom, H / zoom
    x0 = (W - cw) / 2 + dx
    y0 = (H - ch) / 2 + dy
    pil = Image.fromarray(to_u8(img))
    pil = pil.transform((W, H), Image.EXTENT, (x0, y0, x0 + cw, y0 + ch), Image.BICUBIC)
    return from_u8(np.asarray(pil))


def hsmear(img, amount):
    """Horizontal motion blur for whip pans."""
    if amount < 1.5:
        return img
    pil = Image.fromarray(to_u8(img))
    small = pil.resize((max(8, int(W / amount)), H), Image.BILINEAR)
    return from_u8(np.asarray(small.resize((W, H), Image.BILINEAR)))


# ------------------------------------------------------------------- fonts
@lru_cache(None)
def font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


BEBAS = "BebasNeue.woff"
INTER3 = "Inter-300.woff"
INTER4 = "Inter-400.woff"
INTER7 = "Inter-700.woff"


@lru_cache(None)
def text_layer(text, fname, size, color=WHITE, tracking=0, stroke=0, outline=False, grad=None):
    """Tightly cropped float RGBA text image."""
    f = font(fname, size)
    asc, desc = f.getmetrics()
    adv = [f.getlength(ch) + tracking for ch in text]
    pad = 20 + stroke * 2
    w = int(sum(adv) - tracking + pad * 2)
    h = asc + desc + pad * 2
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rgb = tuple(int(c * 255) for c in color)
    if tracking == 0:
        if outline:
            d.text((pad, pad), text, font=f, fill=(0, 0, 0, 0), stroke_width=stroke, stroke_fill=rgb + (255,))
        else:
            d.text((pad, pad), text, font=f, fill=rgb + (255,))
    else:
        x = pad
        for ch, a in zip(text, adv):
            if outline:
                d.text((x, pad), ch, font=f, fill=(0, 0, 0, 0), stroke_width=stroke, stroke_fill=rgb + (255,))
            else:
                d.text((x, pad), ch, font=f, fill=rgb + (255,))
            x += a
    arr = from_u8(np.asarray(im))
    ys, xs = np.nonzero(arr[..., 3] > 0.01)
    arr = arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1].copy()
    if grad is not None:  # vertical colour gradient fill
        g = gradient(grad, arr.shape[0])
        arr[..., :3] = g[:, None, :]
    return arr


def draw_text(img, text, fname, size, x, y, anchor="c", a=1.0, color=WHITE, tracking=0, add=False, **kw):
    L = text_layer(text, fname, size, color, tracking, **kw)
    h, w = L.shape[:2]
    if anchor == "c":
        x, y = x - w / 2, y - h / 2
    elif anchor == "l":
        y = y - h / 2
    elif anchor == "r":
        x, y = x - w, y - h / 2
    paste(img, L, x, y, a, add=add)
    return w, h


def reveal_text(img, text, fname, size, x, y, p, anchor="c", a=1.0, color=WHITE, tracking=0, **kw):
    """Text rising out of an invisible mask line (p: 0..1)."""
    L = text_layer(text, fname, size, color, tracking, **kw)
    h, w = L.shape[:2]
    if anchor == "c":
        x0, y0 = x - w / 2, y - h / 2
    elif anchor == "l":
        x0, y0 = x, y - h / 2
    else:
        x0, y0 = x - w, y - h / 2
    off = (1 - p) * h * 1.08
    clip = (int(x0) - 2, int(y0) - 2, int(x0 + w) + 2, int(y0 + h) + 4)
    paste(img, L, x0, y0 + off, a * clamp(p * 3), clip=clip)
    return w, h


@lru_cache(None)
def letter_layers(text, fname, size, color=WHITE, tracking=0):
    """Per-letter layers sharing one baseline: [(x, layer)], total_w, (top, bottom)."""
    f = font(fname, size)
    asc, desc = f.getmetrics()
    out, x = [], 0.0
    for ch in text:
        adv = f.getlength(ch)
        im = Image.new("RGBA", (int(adv) + 40, asc + desc + 20), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((20, 10), ch, font=f, fill=tuple(int(c * 255) for c in color) + (255,))
        out.append((x - 20, from_u8(np.asarray(im))))
        x += adv + tracking
    total = x - tracking
    bbox = font(fname, size).getbbox(text)
    return out, total, (bbox[1] + 10, bbox[3] + 10)


def rect(img, x0, y0, x1, y1, color, a=1.0, add=False):
    x0, y0 = max(int(x0), 0), max(int(y0), 0)
    x1, y1 = min(int(x1), W), min(int(y1), H)
    if x1 <= x0 or y1 <= y0 or a <= 0:
        return
    c = np.array(color, np.float32)
    if add:
        img[y0:y1, x0:x1] += c * a
    else:
        img[y0:y1, x0:x1] = img[y0:y1, x0:x1] * (1 - a) + c * a


# ------------------------------------------------------------ procedural
def fbm1d(n, seed, base=3.0, octaves=8, gain=0.5, lac=2.07):
    rng = np.random.default_rng(seed)
    x = np.linspace(0, 1, n)
    y = np.zeros(n)
    amp, freq = 1.0, base
    for _ in range(octaves):
        pts = rng.uniform(-1, 1, int(freq) + 3)
        xi = x * freq
        i = np.floor(xi).astype(int)
        f = xi - i
        f = f * f * (3 - 2 * f)
        y += amp * (pts[i] * (1 - f) + pts[i + 1] * f)
        amp *= gain
        freq *= lac
    return y


def noise2d(w, h, cell, seed):
    rng = np.random.default_rng(seed)
    small = rng.random((max(2, h // cell + 2), max(2, w // cell + 2))).astype(np.float32)
    im = Image.fromarray(small, mode="F").resize((w + 2 * cell, h + 2 * cell), Image.BICUBIC)
    return np.asarray(im)[cell:cell + h, cell:cell + w]


def ridge_layer(LW, seed, base_y, amp, lit, shade, rim_col, rim_k, fog_col, fog_k,
                peaks=3.0, light=1.0, snow=False, sharp=0.5, rock=None):
    n1 = fbm1d(LW, seed, base=peaks)
    n2 = fbm1d(LW, seed + 7, base=peaks * 1.7)
    prof = (1 - sharp) * n1 + sharp * (1 - np.abs(n2)) * 1.2
    prof = (prof - prof.min()) / (prof.max() - prof.min())
    ytop = base_y - amp * prof
    top = int(max(0, ytop.min() - 3))
    hh = H - top
    yy = (np.arange(hh) + top)[:, None].astype(np.float32)
    d = yy - ytop[None, :]
    alpha = np.clip(d + 0.5, 0, 1)
    slope = np.gradient(ytop)
    k = np.hanning(61)
    slope = np.convolve(slope, k / k.sum(), mode="same")
    dd = np.maximum(d, 0)
    # organic 2D terrain for facet shading (avoids column streaks)
    terr = sum(noise2d(LW, hh, c, seed + c) * w_ for c, w_ in ((140, 1.0), (60, 0.5), (28, 0.18)))
    gx = np.gradient(terr, axis=1) * 60
    near = np.exp(-dd / 70)
    s = np.clip(light * (slope[None, :] * 1.4 * near + gx * (1 - near * 0.5)), -1, 1)
    depth = np.exp(-dd / (amp * 1.2 + 1))
    m = (s + 1) / 2 * (0.35 + 0.65 * depth) + 0.1 * (1 - depth)
    if snow:
        m = np.clip((m - 0.5) * 1.6 + 0.5, 0, 1)
    lit = np.array(lit, np.float32)
    shade = np.array(shade, np.float32)
    col = shade[None, None, :] * (1 - m[..., None]) + lit[None, None, :] * m[..., None]
    if snow and rock is not None:
        rmask = np.clip((np.abs(gx) - 0.7) * 1.2, 0, 1) * np.clip(dd / 30, 0, 1) * 0.55
        col = col * (1 - rmask[..., None]) + np.array(rock, np.float32) * rmask[..., None]
    rim = rim_k * np.exp(-np.maximum(d, 0) / 5.0)
    col = col + np.array(rim_col, np.float32)[None, None, :] * rim[..., None]
    fog = fog_k * np.clip(d / (H - base_y + amp + 1), 0, 1) ** 0.8
    col = col * (1 - fog[..., None]) + np.array(fog_col, np.float32) * fog[..., None]
    rgba = np.concatenate([np.clip(col, 0, 1), alpha[..., None]], axis=2)
    return top, to_u8(rgba)


def photo(name):
    p = os.path.join(PHOTO_DIR, name + ".jpg")
    return p if os.path.exists(p) else None


@lru_cache(None)
def photo_src(path):
    im = Image.open(path).convert("RGB")
    s = max(W * 1.25 / im.width, H * 1.25 / im.height)
    return im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)


def photo_bg(name, t, dur, tint=(1, 1, 1), lift=0.0):
    path = photo(name)
    if not path:
        return None
    im = photo_src(path)
    p = eio_sine(clamp(t / dur))
    z = lerp(1.0, 1.12, p)
    cw, ch = im.width / 1.25 / z * 1.0, im.height / 1.25 / z
    x0 = (im.width - cw) / 2 + lerp(-30, 30, p)
    y0 = (im.height - ch) / 2
    fr = im.transform((W, H), Image.EXTENT, (x0, y0, x0 + cw, y0 + ch), Image.BICUBIC)
    a = from_u8(np.asarray(fr))
    a = a * np.array(tint, np.float32) + lift
    return a


class Assets:
    def __init__(self):
        LW = int(W * 1.45)
        self.LW = LW
        # dawn — warm backlit alpine ridges (Munich: where the Alps begin)
        self.dawn_sky = vgrad_img([(0, (0.012, 0.016, 0.05)), (0.28, (0.06, 0.05, 0.14)),
                                   (0.47, (0.32, 0.14, 0.24)), (0.6, (0.92, 0.46, 0.27)),
                                   (0.68, (1.0, 0.70, 0.44)), (1, (1.0, 0.72, 0.5))])
        fogc = (0.88, 0.52, 0.42)
        spec = [  # base_y, amp, lit, shade, rim_k, fog_k, peaks, parallax
            (0.60, 0.20, (0.66, 0.40, 0.42), (0.56, 0.32, 0.38), 0.25, 0.55, 5.0, 0.08),
            (0.67, 0.21, (0.48, 0.26, 0.33), (0.38, 0.19, 0.28), 0.32, 0.45, 4.0, 0.22),
            (0.76, 0.20, (0.30, 0.15, 0.22), (0.22, 0.10, 0.17), 0.38, 0.35, 3.4, 0.42),
            (0.86, 0.18, (0.15, 0.075, 0.12), (0.10, 0.05, 0.085), 0.45, 0.22, 2.6, 0.68),
            (0.98, 0.16, (0.05, 0.028, 0.05), (0.03, 0.018, 0.035), 0.55, 0.10, 2.0, 1.0),
        ]
        self.dawn_layers = []
        for i, (by, am, lit, sh, rk, fk, pk, par) in enumerate(spec):
            top, L = ridge_layer(LW, 11 + i * 13, by * H, am * H, lit, sh, (1.0, 0.62, 0.32), rk,
                                 fogc, fk, peaks=pk, light=1.0, sharp=0.55)
            self.dawn_layers.append((top, L, par))

        # nordic — blue hour, snow covered peaks
        self.nordic_sky = vgrad_img([(0, (0.008, 0.02, 0.06)), (0.32, (0.03, 0.08, 0.18)),
                                     (0.55, (0.18, 0.32, 0.5)), (0.66, (0.52, 0.66, 0.8)),
                                     (1, (0.62, 0.74, 0.86))])
        nspec = [
            (0.66, 0.20, (0.62, 0.72, 0.86), (0.42, 0.53, 0.70), 0.10, 0.55, 5.0, 0.1),
            (0.75, 0.22, (0.78, 0.86, 0.96), (0.34, 0.45, 0.62), 0.12, 0.38, 3.8, 0.28),
            (0.86, 0.22, (0.88, 0.93, 0.99), (0.26, 0.35, 0.52), 0.15, 0.22, 3.0, 0.55),
            (0.99, 0.22, (0.93, 0.96, 1.0), (0.18, 0.26, 0.42), 0.18, 0.08, 2.2, 1.0),
        ]
        self.nordic_layers = []
        for i, (by, am, lit, sh, rk, fk, pk, par) in enumerate(nspec):
            top, L = ridge_layer(LW, 101 + i * 17, by * H, am * H, lit, sh, (0.85, 0.95, 1.0), rk,
                                 (0.55, 0.68, 0.82), fk, peaks=pk, light=-1.0, snow=True,
                                 sharp=0.7, rock=(0.12, 0.15, 0.22))
            self.nordic_layers.append((top, L, par))

        # road — sunset horizon
        self.road_sky = vgrad_img([(0, (0.02, 0.012, 0.04)), (0.25, (0.07, 0.03, 0.09)),
                                   (0.42, (0.45, 0.13, 0.12)), (0.5, (1.0, 0.45, 0.16)),
                                   (0.52, (0.12, 0.05, 0.06)), (1, (0.015, 0.012, 0.02))])
        top, L = ridge_layer(LW, 401, 0.502 * H, 0.07 * H, (0.16, 0.06, 0.09), (0.12, 0.04, 0.07),
                             (1.0, 0.5, 0.2), 0.6, (0.6, 0.22, 0.14), 0.25, peaks=4.0, sharp=0.4)
        self.road_ridge = (top, L)

        # textile — macro knit/weave
        TW, TH = W + 240, H + 160
        yy, xx = np.mgrid[0:TH, 0:TW].astype(np.float32)
        ang = math.radians(-24)
        u = (xx * math.cos(ang) - yy * math.sin(ang)) / 24.0
        v = (xx * math.sin(ang) + yy * math.cos(ang)) / 24.0
        fu, fv = u - np.floor(u), v - np.floor(v)
        par = (np.floor(u) + np.floor(v)) % 2
        pw = np.sin(np.pi * fu) ** 0.6
        pf = np.sin(np.pi * fv) ** 0.6
        topw = np.where(par == 0, pw, pf)
        under = np.where(par == 0, pf, pw)
        # thread fibre micro-texture
        fib = 0.85 + 0.15 * np.sin((np.where(par == 0, v, u)) * 40 + np.where(par == 0, fu, fv) * 9)
        h_ = np.maximum(topw, under * 0.55) * fib
        accent = (np.floor(u) % 17 == 0).astype(np.float32)
        base = np.array((0.07, 0.075, 0.09), np.float32)
        red = np.array((0.75, 0.16, 0.06), np.float32)
        col = base[None, None] * (1 - accent[..., None]) + red[None, None] * accent[..., None]
        self.tex_base = (col * (0.25 + 0.95 * h_[..., None])).astype(np.float32)
        self.tex_spec = (np.clip(h_, 0, 1) ** 6).astype(np.float32)
        self.tex_coord = (xx + yy * 0.35).astype(np.float32)

        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
        self.vignette = (1 - 0.42 * np.clip(r / 1.25, 0, 1) ** 2.4)[..., None].astype(np.float32)
        rng = np.random.default_rng(5)
        self.grain = [rng.standard_normal((H + 64, W + 64)).astype(np.float32) for _ in range(3)]

        tilt = np.abs(np.arange(H) - H * 0.52) / (H * 0.5)
        self.tilt_mask = np.clip(tilt * 1.4 - 0.25, 0, 1)[:, None, None].astype(np.float32)


A = None


def assets():
    global A
    if A is None:
        A = Assets()
    return A


# ----------------------------------------------------------------- scenes
def mountains(img, layers, camx, camy=0.0, sun=None):
    a = assets()
    margin = (a.LW - W) / 2
    for i, (top, L, par) in enumerate(layers):
        if sun is not None and i == 1:
            sun(img)
        paste(img, L, -margin - par * camx, top + par * camy)


def scene_dawn(t, dur=5.0):
    a = assets()
    ph = photo_bg("dawn", t, dur)
    p = clamp(t / dur)
    sx, sy = 0.73 * W, lerp(0.66 * H, 0.50 * H, eo_cubic(p))
    if ph is not None:
        img = ph
    else:
        img = a.dawn_sky.copy()
        g = glow_field(sx, sy, 150) * 0.9 + glow_field(sx, sy, 520) * 0.35
        img += g[..., None] * np.array((1.0, 0.62, 0.34), np.float32)

        def sun(im):
            core = glow_field(sx, sy, 26, scale=2)
            im += np.clip(core * 2.4, 0, 1.6)[..., None] * np.array((1.0, 0.93, 0.8), np.float32)

        mountains(img, a.dawn_layers, camx=lerp(-60, 60, eio_sine(p)), camy=lerp(10, -6, p), sun=sun)
        bloom = glow_field(sx, sy, 330) * 0.28
        img += bloom[..., None] * np.array((1.0, 0.55, 0.3), np.float32)
        # anamorphic streak
        ys = np.exp(-0.5 * ((np.arange(H) - sy) / 2.2) ** 2)[:, None]
        xs = np.exp(-np.abs(np.arange(W) - sx) / 520)[None, :]
        img += (ys * xs * 0.55)[..., None] * np.array((0.55, 0.7, 1.0), np.float32)
        # floating dust in the light
        rng = np.random.default_rng(3)
        n = 90
        px = rng.uniform(0, W, n)
        py = rng.uniform(0, H, n)
        sp = rng.uniform(6, 22, n)
        ov = Image.new("L", (W // 2, H // 2), 0)
        d = ImageDraw.Draw(ov)
        for k in range(n):
            x = (px[k] + sp[k] * t * 1.5) % W
            y = (py[k] - sp[k] * t * 0.6) % H
            near = math.exp(-((x - sx) ** 2 + (y - sy) ** 2) / (2 * 500 ** 2))
            r = 1.2 + (k % 3)
            d.ellipse((x / 2 - r, y / 2 - r, x / 2 + r, y / 2 + r), fill=int(255 * near))
        ov = ov.filter(ImageFilter.GaussianBlur(1.2)).resize((W, H), Image.BILINEAR)
        img += from_u8(np.asarray(ov))[..., None] * np.array((1.0, 0.8, 0.6), np.float32) * 0.6
    return camera(img, zoom=lerp(1.0, 1.07, eio_sine(p)))


def scene_road(t, dur=5.0):
    a = assets()
    ph = photo_bg("road", t, dur)
    vx, hz = W / 2, 0.5 * H
    if ph is not None:
        img = ph
    else:
        img = a.road_sky.copy()
        img += (glow_field(vx, hz, 140) * 1.0 + glow_field(vx, hz, 600) * 0.4)[..., None] * \
            np.array((1.0, 0.5, 0.2), np.float32)
        top, L = a.road_ridge
        paste(img, L, -(a.LW - W) / 2 - t * 8, top)
        ov = Image.new("RGB", (W, H), (0, 0, 0))
        d = ImageDraw.Draw(ov)
        # road surface
        d.polygon([(vx - 4, hz), (vx + 4, hz), (vx + 1.25 * W, H), (vx - 1.25 * W, H)], fill=(20, 15, 18))
        speed = 26.0
        f = 260.0
        for side in (-1, 1):  # edge lines
            d.polygon([(vx + side * 3, hz), (vx + side * 3.6, hz), (vx + side * 1.05 * W, H),
                       (vx + side * 1.0 * W, H)], fill=(200, 150, 120))
        for k in range(40):  # centre dashes
            z0 = ((k * 2.6 - t * speed) % 104) + 1.0
            z1 = z0 + 1.2
            y0, y1 = hz + f / z0 * 2.1, hz + f / z1 * 2.1
            if y0 > H * 1.6:
                continue
            w0, w1 = 1300 / z0 * 0.055, 1300 / z1 * 0.055
            br = int(185 * clamp(1.3 - z0 / 80) * clamp(z0 / 3.0))
            d.polygon([(vx - w0, y0), (vx + w0, y0), (vx + w1, y1), (vx - w1, y1)], fill=(br, int(br * .92), int(br * .85)))
        road = from_u8(np.asarray(ov))
        mask = (road.sum(axis=2, keepdims=True) > 0).astype(np.float32)
        img = img * (1 - mask) + road * mask
        # wet-asphalt sun reflection
        yy = np.arange(H)[:, None].astype(np.float32)
        xx = np.arange(W)[None, :].astype(np.float32)
        dy = np.maximum(yy - hz, 0)
        refl = np.exp(-np.abs(xx - vx) / (8 + dy * 0.5)) * np.exp(-dy / 380) * (yy > hz)
        img += (refl * 0.9)[..., None] * np.array((1.0, 0.5, 0.22), np.float32)
        # speed streaks radiating from the vanishing point
        sv = Image.new("RGB", (W, H), (0, 0, 0))
        d = ImageDraw.Draw(sv)
        rng = np.random.default_rng(9)
        n = 170
        ang = rng.uniform(0, 2 * np.pi, n)
        ph0 = rng.uniform(0, 1, n)
        spd = rng.uniform(0.7, 1.4, n)
        for k in range(n):
            z = 1 - ((ph0[k] + t * 0.55 * spd[k]) % 1.0)
            z = 0.04 + z * 0.96
            r0 = 90 / z
            r1 = 90 / min(1.0, z + 0.05 + 0.08 * (1 - z))
            if r0 > 2200:
                continue
            ca, sa = math.cos(ang[k]), math.sin(ang[k]) * 0.62
            x0, y0 = vx + ca * r0, hz + sa * r0
            x1, y1 = vx + ca * r1, hz + sa * r1
            b = int(clamp((1 - z) * 1.3) * 210)
            d.line((x1, y1, x0, y0), fill=(b, int(b * 0.8), int(b * 0.65)), width=max(1, int(3 * (1 - z) + 1)))
        img += from_u8(np.asarray(sv)) * 0.75
    shake = 3.0 * math.sin(t * 37) + 2.0 * math.sin(t * 23.3)
    punch = 1 + 0.16 * (1 - eo_expo(prog(t, 0, 0.6)))
    return camera(img, zoom=punch * lerp(1.0, 1.05, t / dur), dx=shake, dy=shake * 0.6)


def scene_nordic(t, dur=4.5):
    a = assets()
    ph = photo_bg("nordic", t, dur)
    p = clamp(t / dur)
    if ph is not None:
        img = ph
    else:
        img = a.nordic_sky.copy()
        mx, my = 0.22 * W, 0.2 * H
        img += (glow_field(mx, my, 90) * 0.45 + glow_field(mx, my, 500) * 0.22)[..., None] * \
            np.array((0.7, 0.85, 1.0), np.float32)
        # stars
        rng = np.random.default_rng(21)
        sx, sy = rng.uniform(0, W, 260).astype(int), (rng.uniform(0, 0.5, 260) ** 1.4 * H).astype(int)
        tw = 0.5 + 0.5 * np.sin(t * 3 + np.arange(260))
        img[sy, sx] += (tw * rng.uniform(0.2, 0.8, 260))[:, None] * np.array((0.8, 0.9, 1.0), np.float32)
        mountains(img, a.nordic_layers, camx=lerp(70, -70, eio_sine(p)), camy=lerp(-8, 8, p))
        # snowfall — three depths
        for layer, (n, rmin, rmax, blur, spd, alpha) in enumerate(
                [(260, 1.0, 1.8, 0.6, 60, 0.65), (110, 2.0, 3.4, 1.6, 120, 0.7), (26, 6, 11, 5, 260, 0.45)]):
            rng = np.random.default_rng(300 + layer)
            px, py = rng.uniform(0, W, n), rng.uniform(0, H, n)
            ph_ = rng.uniform(0, 6.28, n)
            ov = Image.new("L", (W, H), 0)
            d = ImageDraw.Draw(ov)
            for k in range(n):
                x = (px[k] + 40 * t + 25 * math.sin(t * 0.9 + ph_[k])) % (W + 40) - 20
                y = (py[k] + spd * t) % (H + 40) - 20
                r = rmin + (rmax - rmin) * ((k * 37) % 10) / 10
                d.ellipse((x - r, y - r, x + r, y + r), fill=255)
            ov = ov.filter(ImageFilter.GaussianBlur(blur))
            img += from_u8(np.asarray(ov))[..., None] * alpha * np.array((0.9, 0.95, 1.0), np.float32)
    whip_in = 1 - eo_expo(prog(t, 0, 0.5))
    return camera(img, zoom=lerp(1.06, 1.0, eo_cubic(p)), dx=whip_in * -140)


def scene_textile(t, dur=3.5):
    a = assets()
    ph = photo_bg("textile", t, dur, tint=(0.75, 0.75, 0.75))
    if ph is not None:
        img = ph
    else:
        ox, oy = int(120 + 60 * math.sin(t * 0.4)), int(60 + t * 18)
        base = a.tex_base[oy:oy + H, ox:ox + W]
        spec = a.tex_spec[oy:oy + H, ox:ox + W]
        coord = a.tex_coord[oy:oy + H, ox:ox + W]
        sweep = -600 + t * 900
        band = np.exp(-0.5 * ((coord - sweep - ox - oy * 0.35) / 260) ** 2) * 1.1 + 0.18
        img = base * (0.55 + band[..., None] * 0.9) + (spec * band)[..., None] * np.array((1.0, 0.86, 0.75), np.float32) * 0.55
        small = Image.fromarray(to_u8(img)).resize((W // 8, H // 8), Image.BILINEAR)
        blur = from_u8(np.asarray(small.filter(ImageFilter.GaussianBlur(1.5)).resize((W, H), Image.BILINEAR)))
        img = img * (1 - a.tilt_mask) + blur * a.tilt_mask
    img *= 1 - 0.35 * glow_field(W / 2, H * 0.5, 380)[..., None]  # dark centre for type
    return camera(img, zoom=lerp(1.08, 1.0, eo_cubic(clamp(t / dur))))


def scene_logo(t, dur=4.0):
    a = assets()
    ph = photo_bg("logo", t, dur, tint=(0.35, 0.33, 0.33))
    if ph is not None:
        img = ph
    else:
        img = vgrad_img([(0, (0.01, 0.01, 0.015)), (0.6, (0.03, 0.022, 0.03)), (0.85, (0.16, 0.06, 0.05)),
                         (1, (0.10, 0.04, 0.04))])
        img += glow_field(W / 2, H * 1.05, 700)[..., None] * np.array((0.9, 0.3, 0.12), np.float32) * 0.5
        top, L, par = a.dawn_layers[3]
        paste(img, L, -(a.LW - W) / 2 - t * 12, top + 70, 0.55)
        top, L, par = a.dawn_layers[4]
        paste(img, L, -(a.LW - W) / 2 - t * 22, top + 60, 1.0)
        # embers
        rng = np.random.default_rng(77)
        n = 70
        px, ph_, sp = rng.uniform(0, W, n), rng.uniform(0, 1, n), rng.uniform(40, 110, n)
        ov = Image.new("L", (W // 2, H // 2), 0)
        d = ImageDraw.Draw(ov)
        for k in range(n):
            y = H - ((ph_[k] * H + sp[k] * (t + 3)) % H)
            x = px[k] + 30 * math.sin(t * 1.3 + k)
            life = clamp((H - y) / H)
            b = int(255 * (1 - life) * (0.4 + 0.6 * ((k * 13) % 7) / 7))
            r = 1.0 + (k % 3) * 0.7
            d.ellipse((x / 2 - r, y / 2 - r, x / 2 + r, y / 2 + r), fill=b)
        ov = ov.filter(ImageFilter.GaussianBlur(1.4)).resize((W, H), Image.BILINEAR)
        img += from_u8(np.asarray(ov))[..., None] * np.array((1.0, 0.45, 0.16), np.float32) * 1.4
    return camera(img, zoom=lerp(1.0, 1.04, clamp(t / dur)))


# ------------------------------------------------------------- typography
def hud(img, t, chapter):
    a = 0.55 * prog(t, 3.3, 3.9) * (1 - prog(t, 25.6, 26.0))
    if a <= 0:
        return
    m, L = 48, 34
    c = WHITE
    for (x, y, sx, sy) in [(m, m, 1, 1), (W - m, m, -1, 1), (m, H - m, 1, -1), (W - m, H - m, -1, -1)]:
        rect(img, min(x, x + sx * L), y if sy > 0 else y - 2, max(x, x + sx * L), (y + 2) if sy > 0 else y, c, a)
        rect(img, x if sx > 0 else x - 2, min(y, y + sy * L), (x + 2) if sx > 0 else x, max(y, y + sy * L), c, a)
    f = int(t * FPS) % FPS
    s = int(t)
    tc = f"00:00:{s:02d}:{f:02d}"
    draw_text(img, tc, INTER4, 17, W - 92, 70, anchor="r", a=a, tracking=2)
    draw_text(img, "PROTECTIVE  /  SHOWREEL", INTER4, 17, 92, 70, anchor="l", a=a, tracking=4)
    draw_text(img, chapter, INTER4, 17, 92, H - 70, anchor="l", a=a, tracking=4)
    # progress bar
    rect(img, W - 92 - 220, H - 71, W - 92, H - 70, c, a * 0.4)
    rect(img, W - 92 - 220, H - 72, W - 92 - 220 + 220 * clamp(t / DUR), H - 69, EMBER, a * 1.4)


def type_intro(img, t):
    cy = H / 2
    lp = eo_expo(prog(t, 0.15, 1.3))
    lw = 720 * lp
    out = prog(t, 2.45, 2.95)
    a_txt = 1 - out
    p1 = eo_expo(prog(t, 0.45, 1.25))
    p2 = eo_expo(prog(t, 1.15, 1.95))
    reveal_text(img, "JEDER MORGEN", INTER3, 52, W / 2, cy - 58 - out * 20, p1, a=a_txt, tracking=16)
    reveal_text(img, "IST EIN VERSPRECHEN.", INTER3, 52, W / 2, cy + 58 + out * 20, p2, a=a_txt, tracking=16)
    lw = lerp(lw, W + 40, eio_cubic(prog(t, 2.55, 3.0)))
    rect(img, W / 2 - lw / 2, cy - 1, W / 2 + lw / 2, cy + 1, EMBER, 1.0)
    img += (glow_field(W / 2, cy, 60 + 200 * lp) * 0.25 * lp)[..., None] * np.array(EMBER, np.float32)


def type_dawn(img, t):
    x = 150 + t * 6
    out = 1 - prog(t, 4.35, 4.85)
    reveal_text(img, "MÜNCHEN  ·  SEIT 1991", INTER4, 26, x + 4, 380, eo_expo(prog(t, 0.45, 1.2)), anchor="l",
                a=out, color=EMBER, tracking=10)
    layers, total, (bt, bb) = letter_layers("LEIDENSCHAFT", BEBAS, 210, WHITE, 6)
    for i, (lx, L) in enumerate(layers):
        p = eo_expo(prog(t, 0.75 + i * 0.035, 1.6 + i * 0.035))
        y0 = 425 - bt
        off = (1 - p) * (bb - bt) * 1.1
        paste(img, L, x + lx, y0 + off, out, clip=(0, 425 - 4, W, 425 + (bb - bt) + 6))
    reveal_text(img, "trifft Textilkompetenz.", INTER3, 44, x + 6, 700, eo_expo(prog(t, 1.5, 2.3)), anchor="l",
                a=out * 0.95, tracking=1)


def type_road(img, t):
    xo = lerp(0.62, 0.40, t / 5.0) * W
    big_a = eo_cubic(prog(t, 0.05, 0.4)) * (1 - prog(t, 4.6, 5.0))
    for k in range(3, 0, -1):  # echo trails
        draw_text(img, "CYCLING", BEBAS, 500, xo + k * 70, H * 0.47, a=big_a * 0.16 * (4 - k) / 3,
                  outline=True, stroke=2)
    fill = text_layer("CYCLING", BEBAS, 500, WHITE, 0, grad=((0, (1.0, 0.97, 0.92)), (1, (1.0, 0.42, 0.14))))
    h, w = fill.shape[:2]
    x0, y0 = xo - w / 2, H * 0.47 - h / 2
    wp = eo_expo(prog(t, 0.25, 1.0))
    paste(img, fill, x0, y0, big_a * 0.95, clip=(int(x0), 0, int(x0 + w * wp), H))
    draw_text(img, "CYCLING", BEBAS, 500, xo, H * 0.47, a=big_a, outline=True, stroke=2)
    words = [("TRIKOTS", 1.0), ("HOSEN", 1.5), ("JACKEN", 2.0), ("ACCESSOIRES", 2.5), ("FÜR SIE & IHN", 3.0)]
    for i, (wd, st) in enumerate(words):
        en = words[i + 1][1] if i + 1 < len(words) else 4.6
        if st - 0.02 <= t < en + 0.2:
            p = eo_expo(prog(t, st, st + 0.22))
            q = prog(t, en, en + 0.18)
            reveal_text(img, wd, INTER7, 46, 160, H - 220 - q * 30, p, anchor="l", a=1 - q, tracking=8)
    bar = eo_expo(prog(t, 0.9, 1.4)) * (1 - prog(t, 4.6, 4.9))
    rect(img, 160, H - 270, 160 + 70 * bar, H - 265, EMBER, 1)


def type_nordic(img, t):
    a = eo_cubic(prog(t, 0.35, 1.2)) * (1 - prog(t, 4.0, 4.5))
    tr = lerp(90, 28, eo_expo(prog(t, 0.3, 2.2)))
    draw_text(img, "NORDIC", BEBAS, 400, W / 2, H * 0.27, a=a, tracking=int(tr),
              grad=((0, (1.0, 1.0, 1.0)), (0.55, (0.86, 0.94, 1.0)), (1, ICE)))
    reveal_text(img, "Gemacht für den Winter.", INTER3, 44, W / 2, H * 0.27 + 175,
                eo_expo(prog(t, 1.0, 1.8)), a=1 - prog(t, 4.0, 4.5), tracking=2)


VALUES = [("VERANTWORTUNG", "Für Mensch und Umwelt."),
          ("QUALITÄT", "Bis in jede Naht."),
          ("INNOVATION", "Immer einen Schritt voraus.")]


@lru_cache(None)
def still(i):
    return [lambda: scene_dawn(3.2, 5.0), lambda: scene_road(2.4, 5.0), lambda: scene_nordic(3.5, 4.5)][i]()


def scene_values(img_under, t):
    """Three panels wipe over the previous scene, then exit to the next one."""
    img = img_under
    pw = W // 3
    for i in range(3):
        pin = eo_expo(prog(t, 0.0 + i * 0.1, 0.85 + i * 0.1))
        pout = ei_expo(prog(t, 4.45 + i * 0.07, 4.95 + i * 0.07))
        y = H * (1 - pin) - H * pout
        if y >= H or y <= -H:
            continue
        x0 = i * pw
        src = still(i)
        inner = -(1 - pin) * H * 0.35 + pout * H * 0.35 + t * 6
        panel = src[:, x0:x0 + pw].copy()
        sh = int(round(inner))
        panel = np.roll(panel, -sh, axis=0)
        panel *= 0.42
        g = np.linspace(0, 1, H)[:, None, None] ** 2.2
        panel = panel * (1 - 0.65 * g)
        hi = 1.0 + 0.35 * math.exp(-((t - (1.6 + i * 0.85)) / 0.35) ** 2)
        panel *= hi
        yi = int(round(y))
        ya, yb = max(0, yi), min(H, yi + H)
        if yb > ya:
            img[ya:yb, x0 + 1:x0 + pw - 1] = panel[ya - yi:yb - yi, 1:pw - 1]
        word, sub = VALUES[i]
        tp = eo_expo(prog(t, 0.55 + i * 0.18, 1.3 + i * 0.18))
        draw_text(img, f"0{i + 1}", INTER4, 24, x0 + 60, 130 + y, anchor="l", color=EMBER, tracking=4)
        rect(img, x0 + 60, 165 + y, x0 + 60 + 40 * tp, 167 + y, EMBER, 1)
        size = 92 if len(word) > 10 else 112
        L = text_layer(word, BEBAS, size, WHITE, 3)
        h, w = L.shape[:2]
        by = H - 300 + y
        paste(img, L, x0 + 60, by + (1 - tp) * h * 1.1, 1.0, clip=(x0, int(by) - 4, x0 + pw, int(by + h) + 6))
        reveal_text(img, sub, INTER3, 28, x0 + 62, H - 160 + y, eo_expo(prog(t, 0.85 + i * 0.18, 1.6 + i * 0.18)),
                    anchor="l", tracking=1)
    return img


def type_craft(img, t):
    p = eo_cubic(prog(t, 0.25, 2.0))
    year = 1991 + int(round(35 * p))
    a = eo_cubic(prog(t, 0.1, 0.5)) * (1 - prog(t, 3.25, 3.5))
    f = font(BEBAS, 300)
    cell = max(f.getlength(str(d)) for d in range(10)) + 6
    s = str(year)
    x0 = W / 2 - cell * 2
    for i, ch in enumerate(s):
        col = EMBER if (p >= 1 and i >= 2) else WHITE
        draw_text(img, ch, BEBAS, 300, x0 + cell * (i + 0.5), H * 0.42, a=a, color=col)
    reveal_text(img, "35 JAHRE LEIDENSCHAFT", INTER7, 40, W / 2, H * 0.42 + 190, eo_expo(prog(t, 1.9, 2.5)),
                a=a, color=WHITE, tracking=12)
    reveal_text(img, "Qualität, die man spürt.", INTER3, 36, W / 2, H * 0.42 + 255, eo_expo(prog(t, 2.2, 2.8)),
                a=a * 0.9, tracking=2)


def type_logo(img, t):
    out = 1.0
    layers, total, (bt, bb) = letter_layers("PROTECTIVE", BEBAS, 250, WHITE, 24)
    x0 = W / 2 - total / 2
    ytop = H / 2 - 80 - (bb - bt) / 2
    hgt = bb - bt
    sweep = lerp(-0.3, 1.3, eio_cubic(prog(t, 1.05, 2.1)))
    for i, (lx, L) in enumerate(layers):
        p = eo_expo(prog(t, 0.1 + i * 0.045, 0.95 + i * 0.045))
        off = (1 - p) * hgt * 1.15
        paste(img, L, x0 + lx, ytop - bt + off, out, clip=(0, int(ytop) - 4, W, int(ytop + hgt) + 6))
    # light sweep across the wordmark
    sx = x0 + sweep * total
    ys, ye = int(ytop) - 4, int(ytop + hgt) + 6
    region = img[ys:ye]
    xs = np.arange(W)[None, :]
    band = np.exp(-0.5 * ((xs - sx + (np.arange(ye - ys)[:, None] - hgt / 2) * 0.35) / 60) ** 2)
    lum = region.mean(axis=2)
    mask = np.clip((lum - 0.75) * 4, 0, 1)
    region += (band * mask * 0.9)[..., None] * np.array((1.0, 0.75, 0.55), np.float32)
    bw = total * eo_expo(prog(t, 0.85, 1.7))
    rect(img, W / 2 - bw / 2, ytop + hgt + 34, W / 2 + bw / 2, ytop + hgt + 39, EMBER, 1)
    img += (glow_field(W / 2, ytop + hgt + 36, 160) * 0.18 * eo_expo(prog(t, 0.9, 1.7)))[..., None] * \
        np.array(EMBER, np.float32)
    reveal_text(img, "CYCLING & NORDIC SPORTSWEAR", INTER4, 28, W / 2, ytop + hgt + 95,
                eo_expo(prog(t, 1.35, 2.0)), tracking=12)
    reveal_text(img, "MÜNCHEN  ·  SEIT 1991", INTER3, 24, W / 2, ytop + hgt + 145,
                eo_expo(prog(t, 1.6, 2.2)), color=(0.7, 0.68, 0.66), tracking=10)
    draw_text(img, "protective-sports.com", INTER4, 24, W / 2, H - 110, a=eo_cubic(prog(t, 2.1, 2.7)) * 0.85,
              tracking=4)


# ------------------------------------------------------------------ frame
def chapter(t):
    for st, name in [(T_LOGO, "06  /  PROTECTIVE"), (T_CRAFT, "05  /  CRAFT"), (T_VALUES, "04  /  VALUES"),
                     (T_NORDIC, "03  /  NORDIC"), (T_ROAD, "02  /  ROAD"), (0, "01  /  ORIGIN")]:
        if t >= st:
            return name


def render_frame(i):
    t = i / FPS
    a = assets()
    if t < T_DAWN - 0.15:
        img = np.zeros((H, W, 3), np.float32)
        type_intro(img, t)
    elif t < T_ROAD:
        lt = t - T_DAWN
        img = scene_dawn(max(lt, 0))
        if t < T_DAWN + 0.75:  # the line opens like an eye
            op = eio_cubic(prog(t, T_DAWN - 0.15, T_DAWN + 0.75))
            hh = op * H / 2
            black = np.zeros_like(img)
            type_intro(black, t)
            m = (np.abs(np.arange(H) - H / 2) < hh)[:, None, None]
            img = np.where(m, img, black)
            rect(img, 0, H / 2 - hh - 1, W, H / 2 - hh + 1, EMBER, 1 - op)
            rect(img, 0, H / 2 + hh - 1, W, H / 2 + hh + 1, EMBER, 1 - op)
        type_dawn(img, max(lt, 0))
    elif t < T_NORDIC:
        lt = t - T_ROAD
        if t > T_NORDIC - 0.3:
            img = hsmear(scene_road(lt), 1 + 60 * ei_expo(prog(t, T_NORDIC - 0.3, T_NORDIC)))
        else:
            img = scene_road(lt)
        type_road(img, lt)
    elif t < T_VALUES:
        lt = t - T_NORDIC
        img = scene_nordic(lt)
        if lt < 0.3:
            img = hsmear(img, 1 + 60 * (1 - eo_expo(prog(lt, 0, 0.3))))
        type_nordic(img, lt)
    elif t < T_CRAFT:
        lt = t - T_VALUES
        if lt < 1.2:
            under = scene_nordic(lt + 4.5)
            type_nordic(under, lt + 4.5)
        elif lt > 4.4:
            under = scene_textile(0.0)
        else:
            under = np.zeros((H, W, 3), np.float32)
        img = scene_values(under, lt)
    elif t < T_LOGO:
        lt = t - T_CRAFT
        img = scene_textile(lt)
        type_craft(img, lt)
    else:
        lt = t - T_LOGO
        img = scene_logo(lt)
        type_logo(img, lt)

    hud(img, t, chapter(t))

    # flashes & impacts
    for ti in IMPACTS:
        if ti - 0.05 <= t < ti + 0.6:
            k = math.exp(-max(t - ti, 0) / 0.09) if t >= ti else prog(t, ti - 0.05, ti)
            img += k * 0.85
            s = int(10 * math.exp(-max(t - ti, 0) / 0.15))
            if s > 0:
                img[..., 0] = np.roll(img[..., 0], -s, axis=1)
                img[..., 2] = np.roll(img[..., 2], s, axis=1)
    if T_LOGO - 0.35 <= t < T_LOGO:  # dip before logo
        img *= 1 - eo_cubic(prog(t, T_LOGO - 0.35, T_LOGO - 0.05))

    img *= a.vignette
    g = a.grain[i % 3]
    ox, oy = (i * 17) % 64, (i * 29) % 64
    img += g[oy:oy + H, ox:ox + W, None] * 0.018
    # final fade
    img *= 1 - prog(t, DUR - 0.55, DUR - 0.05)
    # gentle filmic tonemap
    img = img / (1 + np.maximum(img - 0.85, 0) * 1.2)
    return to_u8(img).tobytes()


def init_worker():
    assets()


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] == "--preview":
        for s in sys.argv[2:]:
            i = int(float(s) * FPS)
            buf = render_frame(i)
            Image.frombytes("RGB", (W, H), buf).save(os.path.join(OUT_DIR, f"preview_{float(s):05.2f}.png"))
            print("wrote", s)
        return
    wav = os.path.join(OUT_DIR, "soundtrack.wav")
    audio.render(wav, DUR)
    out = os.path.join(OUT_DIR, "protective_showreel.mp4")
    n = int(DUR * FPS)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "slow", "-crf", "16",
           "-tune", "film", "-pix_fmt", "yuv420p", "-profile:v", "high", "-c:a", "aac", "-b:a", "320k",
           "-movflags", "+faststart", "-shortest", out]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(os.cpu_count(), initializer=init_worker) as pool:
        for k, buf in enumerate(pool.imap(render_frame, range(n), chunksize=4)):
            ff.stdin.write(buf)
            if k % FPS == 0:
                print(f"\rframe {k}/{n}", end="", flush=True)
    ff.stdin.close()
    ff.wait()
    print("\nwrote", out)


if __name__ == "__main__":
    main()
