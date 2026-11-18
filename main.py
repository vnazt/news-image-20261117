#!/usr/bin/env python3
"""
One-picture world news front page for Tuesday 17 November 2026.

Renders entry.png (1024 x 1024) as a classic broadsheet front page:
a masthead, a red markets-and-records ticker, three illustrated hero
stories, twelve illustrated cards, a pinned world map and thirty
one-line briefs -- 45 stories in all.  Pure Pillow plus the standard
library, fully deterministic: no randomness, no clock, no network, so
two runs always produce the same bytes.
"""

import math
import os

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------- canvas

SIZE = 1024
SS = 3                       # supersampling factor for smooth small type
MARGIN = 24
CONTENT_W = SIZE - 2 * MARGIN

PAPER = (246, 241, 229)        # cream newsprint
PANEL_BG = (252, 249, 240)     # slightly lighter card stock
PANEL_EDGE = (198, 189, 160)
INK = (32, 36, 43)
NAVY = (22, 41, 77)
RED = (179, 52, 42)
FAINT = (112, 105, 88)         # footer grey-brown
TAN = (227, 211, 172)          # map land
SEA = (198, 214, 224)          # map sea
GOLD = (196, 152, 40)

REGION_RGB = {
    "Europe": (37, 99, 235),
    "Middle East": (217, 119, 6),
    "Asia": (124, 58, 237),
    "Africa": (220, 38, 38),
    "Americas": (5, 150, 105),
    "Oceania": (8, 145, 178),
    "Global": (107, 114, 128),
}

FONT_SERIF = "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"
FONT_SANS = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
FONT_SANS_B = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

_font_cache = {}


def font(path, size):
    """Cached TrueType loader; fractional sizes are allowed (the page is
    rendered on a supersampled canvas and scaled down at the end)."""
    size = max(6.0, round(float(size), 1))
    key = (path, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(path, int(round(size * SS)))
    return _font_cache[key]


def text_w(pen, s, fnt):
    return pen.text_w(s, fnt)


def fit_single(draw, s, path, start, floor, max_w):
    """Largest size <= start whose single line fits max_w (floor bound)."""
    size = start
    while size > floor and text_w(draw, s, font(path, size)) > max_w:
        size -= 0.5
    return font(path, size), size


def wrap_lines(draw, s, fnt, max_w):
    """Greedy word wrap; returns the list of line strings."""
    lines, cur = [], ""
    for word in s.split():
        trial = word if not cur else cur + " " + word
        if not cur or text_w(draw, trial, fnt) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def fit_wrapped(draw, s, path, start, floor, max_w, max_lines):
    """Largest size <= start that wraps into at most max_lines lines."""
    size = start
    while size > floor:
        lines = wrap_lines(draw, s, font(path, size), max_w)
        if len(lines) <= max_lines:
            return font(path, size), size, lines
        size -= 0.5
    fnt = font(path, floor)
    return fnt, floor, wrap_lines(draw, s, fnt, max_w)


def spaced_w(draw, s, fnt, tracking):
    if not s:
        return 0.0
    return sum(text_w(draw, ch, fnt) for ch in s) + tracking * (len(s) - 1)


def draw_spaced(pen, x, y, s, fnt, fill, tracking):
    cx = x
    for ch in s:
        pen.text(cx, y, ch, fnt, fill)
        cx += text_w(pen, ch, fnt) + tracking
    return cx - tracking


def number_chip(pen, cx, cy, radius, rgb, num):
    """Filled region-coloured disc carrying the story number in white."""
    pen.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                fill=rgb)
    label = str(num)
    fnt, _ = fit_single(pen, label, FONT_SANS_B, radius * 1.15,
                        6.0, radius * 1.55)
    w = text_w(pen, label, fnt)
    box = pen.textbbox(label, fnt)
    h = box[3] - box[1]
    pen.text(cx - w / 2, cy - h / 2 - box[1], label, fnt,
             (255, 255, 255))


def starburst(draw, cx, cy, r_out, r_in, fill):
    pts = []
    for i in range(16):
        ang = math.pi * i / 8.0
        r = r_out if i % 2 == 0 else r_in
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    draw.polygon(pts, fill=fill)


def jet_shape(cx, cy, length, fill, draw, tilt=0.0):
    """Flat side-profile jet silhouette centred on (cx, cy)."""
    rel = [(0.50, 0.00), (0.22, -0.07), (0.06, -0.07), (-0.04, -0.30),
           (-0.11, -0.30), (-0.09, -0.07), (-0.36, -0.07), (-0.47, -0.21),
           (-0.54, -0.21), (-0.50, -0.03), (-0.50, 0.05), (-0.36, 0.07),
           (-0.10, 0.07), (-0.13, 0.25), (-0.05, 0.25), (0.04, 0.07),
           (0.22, 0.07)]
    ca, sa = math.cos(tilt), math.sin(tilt)
    pts = []
    for rx, ry in rel:
        px, py = rx * length, ry * length
        pts.append((cx + px * ca - py * sa, cy + px * sa + py * ca))
    draw.polygon(pts, fill=fill)


def dotted_circle(draw, cx, cy, r, fill, dot=1.6, step_deg=14):
    a = 0
    while a < 360:
        rad = math.radians(a)
        x, y = cx + r * math.cos(rad), cy + r * math.sin(rad)
        draw.ellipse([x - dot, y - dot, x + dot, y + dot], fill=fill)
        a += step_deg


class Pen:
    """ImageDraw wrapper that takes page coordinates and scales them
    onto the supersampled canvas; text uses fonts loaded at SS scale."""

    def __init__(self, img):
        self.d = ImageDraw.Draw(img)

    def _p(self, pts):
        return [(x * SS, y * SS) for x, y in pts]

    def _b(self, box):
        return [v * SS for v in box]

    def polygon(self, pts, fill=None, outline=None, width=1):
        self.d.polygon(self._p(pts), fill=fill, outline=outline,
                       width=int(width * SS))

    def ellipse(self, box, fill=None, outline=None, width=1):
        self.d.ellipse(self._b(box), fill=fill, outline=outline,
                       width=int(width * SS))

    def rect(self, box, fill=None, outline=None, width=1):
        self.d.rectangle(self._b(box), fill=fill, outline=outline,
                         width=int(width * SS))

    def line(self, pts, fill, width=1):
        self.d.line(self._p(pts), fill=fill, width=max(1, int(width * SS)))

    def arc(self, box, start, end, fill, width=1):
        self.d.arc(self._b(box), start, end, fill=fill,
                   width=max(1, int(width * SS)))

    def text(self, x, y, s, fnt, fill):
        self.d.text((x * SS, y * SS), s, font=fnt, fill=fill)

    def text_w(self, s, fnt):
        return self.d.textlength(s, font=fnt) / SS

    def textbbox(self, s, fnt):
        b = self.d.textbbox((0, 0), s, font=fnt)
        return tuple(v / SS for v in b)


# ---------------------------------------------------------------- stories
# (number, region, kicker, headline, deck)

HEROES = [
    (1, "Europe", "EUROPE · UKRAINE WAR",
     "Ukraine drops a Crimean Bridge road span into the sea",
     "A second day of strikes; two killed, Russian-installed officials "
     "say. Zelensky hails an 'unprecedented operation'."),
    (2, "Middle East", "MIDDLE EAST · IRAN WAR",
     "Iran fires drones at a US radar in Bahrain; US jets hit Qeshm",
     "Bahrain says all were shot down. Iran says tankers struck mines "
     "in Hormuz; a gas carrier burns."),
    (3, "Asia", "ASIA · DIPLOMACY",
     "Trump holds his first Quad summit, in Manila",
     "The US, India, Japan and Australia unveil critical-minerals "
     "deals. Next: Shenzhen on Thursday, with Xi and Putin."),
]

CARDS = [
    (4, "Africa", "AFRICA · HEALTH",
     "Ebola in DR Congo tops 11,000 cases",
     "WHO says cases have more than doubled in three months; about "
     "5,400 deaths and no licensed vaccine."),
    (5, "Americas", "US · BUSINESS",
     "Nvidia sales double to $115.8bn as stocks slide",
     "A record quarter, reported after the close. Earlier the Dow "
     "fell 849 points (−1.6%)."),
    (6, "Americas", "AMERICAS · HEALTH",
     "US, Mexico and Bolivia lose measles-free status",
     "PAHO cites a year of spread; the US counts 5,700+ cases in 2026."),
    (7, "Global", "GLOBAL · CLIMATE",
     "COP31 split over the draft fossil-fuel phase-out",
     "Nations weigh the first draft in Antalya; talks are due to end "
     "on Friday."),
    (8, "Asia", "ASIA · POLITICS",
     "Mongolia's president says he will resign",
     "Khurelsukh denies a $25m rail-project bribe claim; parliament "
     "must accept."),
    (9, "Asia", "ASIA · DEFENCE",
     "Japan scrambles jets over a Russian airspace breach",
     "Two suspected Russian aircraft off Okinoshima; Tokyo protests "
     "to Moscow."),
    (10, "Europe", "EUROPE · POLITICS",
     "Serbia's student-led majority takes its seats",
     "The Student List holds 140 of 250 seats; Vučić's party goes "
     "into opposition."),
    (11, "Asia", "ASIA · LABOUR",
     "Bangladesh police tear-gas garment workers",
     "They want Tk 30,000 a month, up from 12,500; 37 factories shut."),
    (12, "Middle East", "MIDDLE EAST · POLITICS",
     "Matan Kahana elected Knesset speaker, 66–52",
     "The Eisenkot ally wins after a six-hour filibuster in Jerusalem."),
    (13, "Europe", "EUROPE · AIR CRASH",
     "Russian An-12 crash in Siberia kills all 19",
     "The air force transport came down near Kemerovo; a fault is "
     "suspected."),
    (14, "Global", "SPACE",
     "Voyager 1 reaches one light-day from Earth",
     "The first spacecraft to do so; NASA invites people to shine "
     "lights after sunset."),
    (15, "Middle East", "MIDDLE EAST · GAZA",
     "Gaza faces winter with 1.4m in acute hunger",
     "A UN report to the Board of Peace; agencies say aid is still "
     "held up."),
]

# Briefs are trimmed to a single line each; every fact and figure from
# the full wire version is preserved.
BRIEFS = [
    "Kyiv: Russian missiles hit North & South Dnipro bridges",
    "Russia: record 1,441 Ukrainian drones downed overnight",
    "Moldova shuts airspace after a drone nears Chișinău",
    "Prague: two trains collide; 46 people injured",
    "France: 146,000 march in a public-sector pay strike",
    "Poland: Tusk's government survives a no-confidence vote",
    "Turkey: police seize opposition broadcaster Sözcü TV",
    "JPMorgan outage cuts off Zelle users for hours",
    "Mozambique: Mondlane on trial, denies 5 charges",
    "Sudan: UN verifies 2,230 civilian deaths this year",
    "Cyclone Akvan strengthens; Odisha evacuates the coast",
    "Cyclone Xavier reaches Category 4 near the Cook Islands",
    "M6.6 Banda Sea quake shakes Darwin; no tsunami threat",
    "Deutsche Bank shares fall 6% after a huge data leak",
    "Apple: Pay, iCloud, App Store outage — 'not a hack'",
    "Five EU states plan a migrant return hub in Rwanda",
    "Ukraine: Europeans join peace talks; IMF may lend $1.6bn more",
    "Kuwait: air defences engage drones overnight",
    "West Bank: settlers kill a woman, 72, near Jericho",
    "Vatican: Pope Leo XIV returns from his South America tour",
    "UK sanctions 8 settlement firms and Tzav 9",
    "China–Canada: more tariff cuts after Carney–Xi talks",
    "Yemen: Houthis push towards Aden as the army retreats",
    "South Africa: 17 killed in two mass shootings",
    "India: bus falls into an Uttarakhand gorge; 8 dead",
    "Pentagon fails its audit for the ninth year in a row",
    "Football: India beat Pakistan 2–1 in the SAFF final",
    "Football: Norway beat Denmark 3–2; Haaland scores twice",
    "Football: Brazil rout Singapore 7–0; Vinícius hat-trick",
    "Australia eases planned backpacker visa curbs",
]

# Map pins: story number -> (region, fx, fy) inside the map panel.
PINS = {
    1: ("Europe", 0.570, 0.215),
    2: ("Middle East", 0.630, 0.388),
    3: ("Asia", 0.795, 0.46),
    4: ("Africa", 0.525, 0.575),
    5: ("Americas", 0.065, 0.335),
    6: ("Americas", 0.115, 0.435),
    7: ("Asia", 0.540, 0.305),
    8: ("Asia", 0.735, 0.285),
    9: ("Asia", 0.835, 0.35),
    10: ("Europe", 0.487, 0.268),
    11: ("Asia", 0.70, 0.415),
    12: ("Middle East", 0.580, 0.356),
    13: ("Asia", 0.675, 0.225),
    15: ("Middle East", 0.520, 0.405),
}


# ------------------------------------------------------------- drawing kit

def dashed_arc(pen, p0, p1, p2, fill, width=2.0):
    """Quadratic-bezier dashed curve with a small arrowhead at p2."""
    pts = []
    for i in range(61):
        t = i / 60.0
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        pts.append((x, y))
    dist, drawing = 0.0, True
    for i in range(1, len(pts)):
        seg = math.dist(pts[i - 1], pts[i])
        dist += seg
        if drawing:
            pen.line([pts[i - 1], pts[i]], fill=fill, width=width)
        if dist > (7 if drawing else 5):
            drawing, dist = not drawing, 0.0
    tip = pts[-1]
    ang = math.atan2(tip[1] - pts[-4][1], tip[0] - pts[-4][0])
    for da in (2.75, -2.75):
        pen.line([tip, (tip[0] + 8 * math.cos(ang + da),
                        tip[1] + 8 * math.sin(ang + da))],
                 fill=fill, width=width)


def ill_bridge(pen, b):
    x0, y0, x1, y1 = b
    w, h = x1 - x0, y1 - y0
    pen.rect(b, fill=(213, 228, 239))
    sea_y = y0 + h * 0.64
    pen.rect([x0, sea_y, x1, y1], fill=(168, 196, 214))
    deck = y0 + h * 0.44
    slate = (52, 58, 66)
    for fx in (0.08, 0.30, 0.52, 0.74, 0.92):
        px = x0 + fx * w
        pen.rect([px - 2, deck, px + 2, y1 - 2], fill=slate)
    pen.line([(x0, deck), (x0 + 0.52 * w, deck)], fill=slate, width=4)
    pen.line([(x0 + 0.74 * w, deck), (x1, deck)], fill=slate, width=4)
    pen.line([(x0 + 0.52 * w, deck), (x0 + 0.735 * w, deck + h * 0.30)],
             fill=slate, width=4)
    tx = x0 + 0.30 * w
    pen.line([(tx, y0 + 3), (tx, deck)], fill=slate, width=2.5)
    for fx in (0.10, 0.18, 0.42, 0.50):
        pen.line([(tx, y0 + 3), (x0 + fx * w, deck)],
                 fill=(110, 118, 128), width=1)
    bx, by = x0 + 0.545 * w, deck - 2
    starburst(pen, bx, by, 13, 6, (238, 128, 32))
    starburst(pen, bx, by, 7, 3.5, RED)
    for dx, dy, r, g in ((12, -13, 8, 168), (22, -9, 6, 182),
                         (6, -20, 6, 152), (18, -19, 5, 172)):
        pen.ellipse([bx + dx - r, by + dy - r * 0.7,
                     bx + dx + r, by + dy + r * 0.7], fill=(g, g, g - 2))
    jet_shape(x0 + 0.15 * w, y0 + h * 0.17, 30, (40, 45, 54), pen)
    jet_shape(x0 + 0.87 * w, y0 + h * 0.13, 24, (40, 45, 54), pen)


def ill_gulf(pen, b):
    x0, y0, x1, y1 = b
    w, h = x1 - x0, y1 - y0
    pen.rect(b, fill=(196, 218, 231))
    land = (224, 205, 160)
    pen.polygon([(x0 + 0.46 * w, y0), (x1, y0), (x1, y0 + 0.34 * h),
                 (x0 + 0.78 * w, y0 + 0.30 * h),
                 (x0 + 0.60 * w, y0 + 0.42 * h),
                 (x0 + 0.47 * w, y0 + 0.20 * h)], fill=land)
    pen.polygon([(x0, y0 + 0.30 * h), (x0 + 0.20 * w, y0 + 0.36 * h),
                 (x0 + 0.30 * w, y0 + 0.54 * h), (x0 + 0.34 * w, y1),
                 (x0, y1)], fill=land)
    pen.ellipse([x0 + 0.755 * w, y0 + 0.40 * h, x0 + 0.875 * w,
                 y0 + 0.52 * h], fill=land, outline=(178, 158, 110),
                width=1)
    pen.ellipse([x0 + 0.205 * w, y0 + 0.44 * h, x0 + 0.265 * w,
                 y0 + 0.515 * h], fill=land, outline=(178, 158, 110),
                width=1)
    bahrain = (x0 + 0.235 * w, y0 + 0.475 * h)
    qeshm = (x0 + 0.815 * w, y0 + 0.46 * h)
    dashed_arc(pen, bahrain, (x0 + 0.52 * w, y0 + 0.16 * h), qeshm,
               RED, 2.0)
    starburst(pen, bahrain[0], bahrain[1], 9, 4.5, (238, 128, 32))
    starburst(pen, qeshm[0], qeshm[1], 10, 5, (238, 128, 32))
    starburst(pen, qeshm[0], qeshm[1], 5.5, 2.8, RED)
    tx, ty = x0 + 0.845 * w, y0 + 0.82 * h
    pen.polygon([(tx - 17, ty), (tx + 15, ty), (tx + 10, ty + 6),
                 (tx - 12, ty + 6)], fill=(52, 58, 66))
    pen.rect([tx - 4, ty - 5, tx + 3, ty], fill=(52, 58, 66))
    for dx, r in ((-3, 5), (2, 6.5), (7, 4.5)):
        starburst(pen, tx + dx, ty - 9, r, r * 0.5, (238, 128, 32))
    fnt = font(FONT_SANS_B, 10)
    pen.text(x0 + 0.045 * w, y0 + 0.30 * h, "BAHRAIN", fnt, INK)
    pen.text(x0 + 0.735 * w, y0 + 0.245 * h, "QESHM", fnt, INK)
    pen.text(x0 + 0.545 * w, y0 + 0.845 * h, "HORMUZ", fnt, NAVY)


def _flag_frame(pen, x, y, w, h):
    pen.rect([x, y, x + w, y + h], outline=(150, 148, 140), width=1)


def ill_quad(pen, b):
    x0, y0, x1, y1 = b
    w, h = x1 - x0, y1 - y0
    pen.rect(b, fill=(236, 238, 240))
    gap, fh = 6, h * 0.58
    fw = (w - 3 * gap) / 4.0
    fy = y0 + 2
    # United States
    fx = x0
    pen.rect([fx, fy, fx + fw, fy + fh], fill=(250, 250, 250))
    for i in range(7):
        sy = fy + i * fh / 6.5
        pen.rect([fx, sy, fx + fw, sy + fh / 13], fill=(178, 34, 52))
    pen.rect([fx, fy, fx + fw * 0.42, fy + fh * 0.54], fill=(30, 40, 100))
    for r in range(3):
        for c in range(4):
            dx, dy = fx + 5 + c * fw * 0.10, fy + 4 + r * fh * 0.16
            pen.ellipse([dx - 1.2, dy - 1.2, dx + 1.2, dy + 1.2],
                        fill=(255, 255, 255))
    _flag_frame(pen, fx, fy, fw, fh)
    # India
    fx = x0 + (fw + gap)
    pen.rect([fx, fy, fx + fw, fy + fh / 3], fill=(244, 152, 53))
    pen.rect([fx, fy + fh / 3, fx + fw, fy + 2 * fh / 3],
             fill=(250, 250, 250))
    pen.rect([fx, fy + 2 * fh / 3, fx + fw, fy + fh], fill=(22, 128, 57))
    cx, cy, r = fx + fw / 2, fy + fh / 2, fh * 0.13
    pen.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(0, 0, 128),
                width=1.4)
    for a in (0, 45, 90, 135):
        rad = math.radians(a)
        pen.line([(cx - r * math.cos(rad), cy - r * math.sin(rad)),
                  (cx + r * math.cos(rad), cy + r * math.sin(rad))],
                 fill=(0, 0, 128), width=0.8)
    _flag_frame(pen, fx, fy, fw, fh)
    # Japan
    fx = x0 + 2 * (fw + gap)
    pen.rect([fx, fy, fx + fw, fy + fh], fill=(250, 250, 250))
    r = fh * 0.26
    pen.ellipse([fx + fw / 2 - r, fy + fh / 2 - r, fx + fw / 2 + r,
                 fy + fh / 2 + r], fill=(188, 0, 45))
    _flag_frame(pen, fx, fy, fw, fh)
    # Australia
    fx = x0 + 3 * (fw + gap)
    pen.rect([fx, fy, fx + fw, fy + fh], fill=(8, 28, 92))
    cw2, ch2 = fw * 0.5, fh * 0.5
    pen.line([(fx, fy), (fx + cw2, fy + ch2)], fill=(255, 255, 255),
             width=2)
    pen.line([(fx + cw2, fy), (fx, fy + ch2)], fill=(255, 255, 255),
             width=2)
    pen.rect([fx + cw2 / 2 - 2.2, fy, fx + cw2 / 2 + 2.2, fy + ch2],
             fill=(255, 255, 255))
    pen.rect([fx, fy + ch2 / 2 - 2.2, fx + cw2, fy + ch2 / 2 + 2.2],
             fill=(255, 255, 255))
    pen.rect([fx + cw2 / 2 - 1.2, fy, fx + cw2 / 2 + 1.2, fy + ch2],
             fill=(200, 30, 44))
    pen.rect([fx, fy + ch2 / 2 - 1.2, fx + cw2, fy + ch2 / 2 + 1.2],
             fill=(200, 30, 44))
    for dx, dy, r in ((0.25, 0.78, 2.4), (0.68, 0.22, 1.7),
                      (0.78, 0.45, 1.7), (0.62, 0.62, 1.5),
                      (0.82, 0.72, 1.5), (0.72, 0.85, 1.3)):
        sx, sy = fx + dx * fw, fy + dy * fh
        pen.ellipse([sx - r, sy - r, sx + r, sy + r],
                    fill=(255, 255, 255))
    _flag_frame(pen, fx, fy, fw, fh)
    # caption band, then the table the flags stand on
    cap_y = fy + fh + 4
    pen.rect([x0, cap_y, x1, cap_y + 15], fill=NAVY)
    label = "NEW CRITICAL-MINERALS DEALS"
    fnt, _ = fit_single(pen, label, FONT_SANS_B, 11.5, 8, w - 12)
    pen.text(x0 + (w - text_w(pen, label, fnt)) / 2, cap_y + 2.5,
             label, fnt, (255, 255, 255))
    pen.rect([x0, cap_y + 19, x1, y1], fill=(122, 84, 52))
    pen.line([(x0, cap_y + 19), (x1, cap_y + 19)], fill=(92, 62, 36),
             width=2)


def _mini_flag_us(pen, x, y, w, h):
    pen.rect([x, y, x + w, y + h], fill=(250, 250, 250))
    for i in range(4):
        sy = y + i * h / 3.5
        pen.rect([x, sy, x + w, sy + h / 7], fill=(178, 34, 52))
    pen.rect([x, y, x + w * 0.42, y + h * 0.55], fill=(30, 40, 100))
    pen.rect([x, y, x + w, y + h], outline=(150, 148, 140), width=1)


def _mini_flag_mx(pen, x, y, w, h):
    pen.rect([x, y, x + w / 3, y + h], fill=(0, 104, 71))
    pen.rect([x + w / 3, y, x + 2 * w / 3, y + h], fill=(250, 250, 250))
    pen.rect([x + 2 * w / 3, y, x + w, y + h], fill=(206, 17, 38))
    pen.ellipse([x + w / 2 - 1.8, y + h / 2 - 1.8, x + w / 2 + 1.8,
                 y + h / 2 + 1.8], fill=(140, 100, 40))
    pen.rect([x, y, x + w, y + h], outline=(150, 148, 140), width=1)


def _mini_flag_bo(pen, x, y, w, h):
    pen.rect([x, y, x + w, y + h / 3], fill=(213, 0, 50))
    pen.rect([x, y + h / 3, x + w, y + 2 * h / 3], fill=(249, 227, 0))
    pen.rect([x, y + 2 * h / 3, x + w, y + h], fill=(0, 121, 52))
    pen.rect([x, y, x + w, y + h], outline=(150, 148, 140), width=1)


def ill_ebola(pen, b):
    x0, y0, x1, y1 = b
    cx, base = (x0 + x1) / 2, y1 - 3
    pen.line([(cx - 78, base), (cx + 78, base)], fill=(150, 148, 140),
             width=1)
    for i, bh in enumerate((10, 17, 25)):
        bx = cx - 72 + i * 20
        pen.rect([bx, base - bh, bx + 13, base], fill=(220, 38, 38))
    ccx, ccy, r = cx + 48, (y0 + y1) / 2, 11
    pen.ellipse([ccx - r, ccy - r, ccx + r, ccy + r], fill=(200, 30, 30))
    pen.rect([ccx - 6.5, ccy - 2, ccx + 6.5, ccy + 2],
             fill=(255, 255, 255))
    pen.rect([ccx - 2, ccy - 6.5, ccx + 2, ccy + 6.5],
             fill=(255, 255, 255))


def ill_nvidia(pen, b):
    x0, y0, x1, y1 = b
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    green, dark = (118, 185, 20), (70, 128, 12)
    gx, gy, gs = cx - 62, cy - 13, 26
    for i in range(3):
        px = gx - 5 + i * 0  # left pins
        pen.line([(gx - 5, gy + 4 + i * 9), (gx, gy + 4 + i * 9)],
                 fill=dark, width=2)
        pen.line([(gx + gs, gy + 4 + i * 9), (gx + gs + 5, gy + 4 + i * 9)],
                 fill=dark, width=2)
        pen.line([(gx + 4 + i * 9, gy - 5), (gx + 4 + i * 9, gy)],
                 fill=dark, width=2)
        pen.line([(gx + 4 + i * 9, gy + gs), (gx + 4 + i * 9, gy + gs + 5)],
                 fill=dark, width=2)
    pen.rect([gx, gy, gx + gs, gy + gs], fill=green)
    pen.rect([gx + 6, gy + 6, gx + gs - 6, gy + gs - 6], outline=dark,
             width=2)
    base = y1 - 3
    for i, bh in enumerate((9, 15, 22)):
        bx = cx + 6 + i * 19
        pen.rect([bx, base - bh, bx + 12, base], fill=dark)


def ill_measles(pen, b):
    x0, y0, x1, y1 = b
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    fw, fh, gap = 27, 18, 5
    fx = cx - (3 * fw + 2 * gap) / 2 - 14
    fy = cy - fh / 2
    _mini_flag_us(pen, fx, fy, fw, fh)
    _mini_flag_mx(pen, fx + fw + gap, fy, fw, fh)
    _mini_flag_bo(pen, fx + 2 * (fw + gap), fy, fw, fh)
    vx, vy, r = cx + 78, cy, 10
    for i in range(8):
        a = math.radians(i * 45)
        ex, ey = vx + (r + 5) * math.cos(a), vy + (r + 5) * math.sin(a)
        pen.line([(vx + r * 0.7 * math.cos(a), vy + r * 0.7 * math.sin(a)),
                  (ex, ey)], fill=(200, 40, 40), width=1.6)
        pen.ellipse([ex - 1.8, ey - 1.8, ex + 1.8, ey + 1.8],
                    fill=(200, 40, 40))
    pen.ellipse([vx - r, vy - r, vx + r, vy + r], fill=(200, 40, 40))
    for dx, dy in ((-3.5, -2.5), (3, 3), (0.5, -4.5)):
        pen.ellipse([vx + dx - 1.3, vy + dy - 1.3, vx + dx + 1.3,
                     vy + dy + 1.3], fill=(255, 255, 255))


def ill_cop31(pen, b):
    x0, y0, x1, y1 = b
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    dx, dy, dw, dh = cx - 58, cy - 14, 24, 28
    pen.rect([dx, dy, dx + dw, dy + dh], fill=(252, 252, 250),
             outline=(140, 138, 130), width=1)
    label = "DRAFT"
    fnt, _ = fit_single(pen, label, FONT_SANS_B, 8, 5, dw - 3)
    pen.text(dx + (dw - text_w(pen, label, fnt)) / 2, dy + 2.5, label,
             fnt, RED)
    for i in range(3):
        ly = dy + 13 + i * 5
        pen.line([(dx + 4, ly), (dx + dw - 4, ly)], fill=(170, 168, 160),
                 width=1.2)
    tx = cx + 34
    pen.rect([tx - 3, cy - 15, tx + 3, cy + 8], outline=(90, 90, 96),
             width=1.6)
    pen.rect([tx - 1.6, cy - 3, tx + 1.6, cy + 8], fill=RED)
    pen.ellipse([tx - 5.5, cy + 5, tx + 5.5, cy + 16], fill=RED)


def ill_mongolia(pen, b):
    x0, y0, x1, y1 = b
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    fx, fy, fw, fh = cx - 66, cy - 12, 36, 24
    pen.rect([fx, fy, fx + fw / 3, fy + fh], fill=(218, 32, 45))
    pen.rect([fx + fw / 3, fy, fx + 2 * fw / 3, fy + fh],
             fill=(0, 97, 168))
    pen.rect([fx + 2 * fw / 3, fy, fx + fw, fy + fh], fill=(218, 32, 45))
    pen.rect([fx + 4.5, fy + 3.5, fx + 7.5, fy + 6.5], fill=(250, 205, 0))
    pen.polygon([(fx + 4, fy + 8), (fx + 8, fy + 8), (fx + 6, fy + 11.5)],
                fill=(250, 205, 0))
    pen.rect([fx + 4.5, fy + 13.5, fx + 7.5, fy + 15], fill=(250, 205, 0))
    pen.rect([fx + 4.5, fy + 17, fx + 7.5, fy + 18.5], fill=(250, 205, 0))
    pen.rect([fx, fy, fx + fw, fy + fh], outline=(150, 148, 140), width=1)
    dx, dy, dw, dh = cx + 26, cy - 14, 17, 28
    pen.rect([dx, dy, dx + dw, dy + dh], fill=(120, 82, 50))
    pen.rect([dx + 2.5, dy + 2.5, dx + dw - 2.5, dy + dh],
             fill=(66, 46, 30))
    hx, hy = dx + dw / 2, dy + 11
    pen.ellipse([hx - 2.6, hy - 2.6, hx + 2.6, hy + 2.6],
                fill=(240, 220, 190))
    pen.line([(hx, hy + 2.6), (hx, dy + dh - 1)], fill=(240, 220, 190),
             width=2.4)
    ay = cy + 1
    pen.line([(dx + dw + 4, ay), (dx + dw + 16, ay)], fill=INK, width=2)
    pen.polygon([(dx + dw + 16, ay - 3.4), (dx + dw + 21.5, ay),
                 (dx + dw + 16, ay + 3.4)], fill=INK)


def ill_jets(pen, b):
    x0, y0, x1, y1 = b
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    jet_shape(cx - 42, cy + 3, 58, (92, 100, 110), pen)
    jx, jy = cx + 52, cy - 4
    jet_shape(jx, jy, 46, (105, 112, 122), pen)
    jet_shape(jx, jy, 41, (243, 243, 240), pen)
    pen.ellipse([jx - 4, jy - 4, jx + 4, jy + 4], fill=(200, 30, 44))


def ill_serbia(pen, b):
    x0, y0, x1, y1 = b
    cx, base = (x0 + x1) / 2, y1 - 4
    pen.rect([cx - 36, base - 5, cx + 36, base], fill=(122, 84, 52))
    pen.rect([cx - 6, base - 10, cx + 6, base - 5], fill=(100, 68, 42))
    cols = [(37, 99, 235), (220, 38, 38)]
    for ring, r in enumerate((25, 18)):
        n = 9 - ring * 2
        for i in range(n):
            a = math.radians(180 - i * (180 / (n - 1)))
            dx = cx + r * math.cos(a)
            dy = base - 6 - r * 0.72 * math.sin(a)
            pen.ellipse([dx - 2.6, dy - 2.6, dx + 2.6, dy + 2.6],
                        fill=cols[(i + ring) % 2])


def ill_bangladesh(pen, b):
    x0, y0, x1, y1 = b
    cx, base = (x0 + x1) / 2, y1 - 3
    dark = (58, 58, 66)
    fx = cx - 76
    pen.rect([fx, base - 15, fx + 46, base], fill=dark)
    for i in range(3):
        tx = fx + 3 + i * 15
        pen.polygon([(tx, base - 15), (tx + 7, base - 21),
                     (tx + 14, base - 15)], fill=dark)
    for chx in (fx + 34, fx + 42):
        pen.rect([chx, base - 27, chx + 5, base - 15], fill=dark)
        pen.ellipse([chx - 1, base - 31, chx + 6, base - 27],
                    fill=(168, 168, 166))
    for i in range(7):
        hx = cx + 6 + (i % 4) * 13
        hy = base - 12 + (i // 4) * 11
        pen.ellipse([hx - 3, hy - 3, hx + 3, hy + 3], fill=(70, 70, 78))
        pen.rect([hx - 3.6, hy + 3, hx + 3.6, hy + 6.4], fill=(70, 70, 78))


def ill_knesset(pen, b):
    x0, y0, x1, y1 = b
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    fnt = font(FONT_SANS_B, 10.5)
    rows = (("66", 104, (37, 99, 235), cy - 11), ("52", 82, (178, 90, 60),
                                                  cy + 3))
    for label, blen, col, ry in rows:
        pen.text(cx - 74, ry - 1, label, fnt, INK)
        pen.rect([cx - 52, ry, cx - 52 + blen, ry + 9], fill=col)
    gx, gy = cx + 66, cy - 8
    pen.rect([gx - 7, gy - 3, gx + 7, gy + 3], fill=(120, 82, 50))
    pen.line([(gx + 5, gy + 2), (gx + 14, gy + 12)], fill=(120, 82, 50),
             width=2.6)
    pen.rect([gx - 9, gy + 13, gx + 9, gy + 16], fill=(100, 68, 42))


def ill_an12(pen, b):
    x0, y0, x1, y1 = b
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    for i, (dx, dy, r) in enumerate(((-44, -13, 4.5), (-34, -9, 6),
                                     (-23, -5, 7.5))):
        g = 176 - i * 12
        pen.ellipse([cx + dx - r, cy + dy - r * 0.7, cx + dx + r,
                     cy + dy + r * 0.7], fill=(g, g, g - 2))
    jet_shape(cx + 8, cy + 3, 66, (108, 114, 122), pen, tilt=0.30)


def ill_voyager(pen, b):
    x0, y0, x1, y1 = b
    pen.rect(b, fill=(15, 23, 52))
    stars = [(0.06, 0.25, 1.4), (0.13, 0.7, 1.1), (0.22, 0.35, 1.5),
             (0.30, 0.8, 1.0), (0.38, 0.2, 1.2), (0.60, 0.75, 1.3),
             (0.66, 0.25, 1.0), (0.74, 0.65, 1.5), (0.82, 0.3, 1.1),
             (0.90, 0.75, 1.4), (0.95, 0.2, 1.2), (0.5, 0.88, 1.0),
             (0.17, 0.5, 0.9), (0.87, 0.52, 0.9)]
    w, h = x1 - x0, y1 - y0
    for fx, fy, r in stars:
        col = (255, 255, 255) if r > 1.05 else (210, 200, 160)
        pen.ellipse([x0 + fx * w - r, y0 + fy * h - r, x0 + fx * w + r,
                     y0 + fy * h + r], fill=col)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    dotted_circle(pen, cx, cy, 17, (140, 165, 215), dot=1.1, step_deg=18)
    pen.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], outline=(245, 245, 245),
                width=1.6)
    pen.ellipse([cx - 1.6, cy - 1.6, cx + 1.6, cy + 1.6],
                fill=(245, 245, 245))
    pen.rect([cx + 8, cy - 2.5, cx + 14, cy + 2.5], fill=GOLD)
    pen.line([(cx + 13, cy - 2), (cx + 21, cy - 10)], fill=(220, 220, 220),
             width=1.4)
    pen.rect([cx + 20, cy - 13, cx + 24, cy - 9], fill=(220, 220, 220))
    pen.line([(cx + 9, cy + 2), (cx + 16, cy + 10)], fill=(220, 220, 220),
             width=1.4)


def ill_gaza(pen, b):
    x0, y0, x1, y1 = b
    cx, base = (x0 + x1) / 2, y1 - 3
    pen.line([(x0 + 6, base), (x1 - 6, base)], fill=(150, 148, 140),
             width=1)
    tents = [(cx - 78, 36, 21, (198, 178, 128)), (cx - 38, 29, 16,
                                                  (150, 148, 138)),
             (cx - 12, 32, 18, (138, 138, 108))]
    for tx, tw, th, col in tents:
        pen.polygon([(tx, base), (tx + tw / 2, base - th),
                     (tx + tw, base)], fill=col)
        pen.polygon([(tx + tw / 2 - 4, base), (tx + tw / 2, base - th * 0.5),
                     (tx + tw / 2 + 4, base)], fill=(90, 84, 70))
    tx = cx + 34
    pen.rect([tx, base - 17, tx + 30, base - 4], fill=(250, 250, 250),
             outline=(140, 138, 130), width=1)
    pen.rect([tx + 12.5, base - 14, tx + 17.5, base - 9], fill=RED)
    pen.rect([tx + 13.8, base - 15.5, tx + 16.2, base - 7.5], fill=RED)
    pen.rect([tx + 30, base - 13, tx + 39, base - 4], fill=(96, 110, 124))
    pen.polygon([(tx + 30, base - 13), (tx + 36, base - 13),
                 (tx + 39, base - 8), (tx + 39, base - 13)],
                fill=(120, 140, 160))
    for wx in (tx + 7, tx + 32):
        pen.ellipse([wx - 3.4, base - 6, wx + 3.4, base + 0.8],
                    fill=(40, 40, 44))


CARD_ART = {
    4: ill_ebola, 5: ill_nvidia, 6: ill_measles, 7: ill_cop31,
    8: ill_mongolia, 9: ill_jets, 10: ill_serbia, 11: ill_bangladesh,
    12: ill_knesset, 13: ill_an12, 14: ill_voyager, 15: ill_gaza,
}


# ------------------------------------------------------------------- map

LAND = [
    [(0.01, 0.30), (0.04, 0.16), (0.12, 0.08), (0.22, 0.09), (0.26, 0.16),
     (0.23, 0.24), (0.19, 0.28), (0.17, 0.36), (0.13, 0.40), (0.10, 0.33),
     (0.04, 0.34)],                                            # N America
    [(0.14, 0.46), (0.20, 0.44), (0.23, 0.52), (0.20, 0.66),
     (0.165, 0.78), (0.145, 0.64), (0.125, 0.52)],             # S America
    [(0.435, 0.20), (0.46, 0.10), (0.52, 0.07), (0.565, 0.12),
     (0.56, 0.22), (0.545, 0.26), (0.50, 0.285), (0.46, 0.26),
     (0.44, 0.235)],                                           # Europe
    [(0.45, 0.33), (0.52, 0.30), (0.585, 0.34), (0.60, 0.44),
     (0.575, 0.58), (0.545, 0.72), (0.51, 0.74), (0.475, 0.62),
     (0.45, 0.48), (0.44, 0.38)],                              # Africa
    [(0.56, 0.18), (0.60, 0.09), (0.72, 0.05), (0.88, 0.05),
     (0.95, 0.10), (0.96, 0.18), (0.90, 0.27), (0.86, 0.34),
     (0.82, 0.41), (0.78, 0.45), (0.74, 0.40), (0.71, 0.47),
     (0.68, 0.42), (0.64, 0.35), (0.605, 0.375), (0.575, 0.33),
     (0.565, 0.25)],                                           # Asia
    [(0.655, 0.35), (0.705, 0.35), (0.68, 0.465)],             # India
    [(0.745, 0.42), (0.775, 0.44), (0.762, 0.545), (0.743, 0.52)],
    [(0.815, 0.64), (0.87, 0.60), (0.94, 0.62), (0.95, 0.70),
     (0.90, 0.78), (0.84, 0.76), (0.815, 0.70)],               # Australia
]

ISLANDS = [  # (fx, fy, rx, ry)
    (0.432, 0.155, 0.012, 0.020),   # Britain
    (0.125, 0.440, 0.016, 0.012),   # Central America
    (0.800, 0.460, 0.010, 0.016),   # Philippines
    (0.840, 0.335, 0.011, 0.014),   # Japan, south
    (0.858, 0.268, 0.010, 0.016),   # Japan, north
    (0.795, 0.565, 0.016, 0.008),   # Indonesia
    (0.835, 0.575, 0.014, 0.008),
    (0.870, 0.565, 0.012, 0.008),
    (0.575, 0.660, 0.010, 0.020),   # Madagascar
    (0.958, 0.800, 0.010, 0.014),   # New Zealand
]


def draw_map(pen, panel):
    x0, y0, x1, y1 = panel
    pen.rect(panel, fill=PANEL_BG, outline=PANEL_EDGE, width=1)
    draw_spaced(pen, x0 + 10, y0 + 6, "WHERE IT HAPPENED",
                font(FONT_SANS_B, 12), NAVY, 1.2)
    mx0, my0, mx1, my1 = x0 + 8, y0 + 24, x1 - 8, y0 + 176
    mw, mh = mx1 - mx0, my1 - my0
    pen.rect([mx0, my0, mx1, my1], fill=SEA, outline=PANEL_EDGE, width=1)
    coast = (186, 164, 116)
    for poly in LAND:
        pen.polygon([(mx0 + fx * mw, my0 + fy * mh) for fx, fy in poly],
                    fill=TAN, outline=coast, width=0.8)
    for fx, fy, rx, ry in ISLANDS:
        pen.ellipse([mx0 + (fx - rx) * mw, my0 + (fy - ry) * mh,
                     mx0 + (fx + rx) * mw, my0 + (fy + ry) * mh],
                    fill=TAN, outline=coast, width=0.8)
    for num, (region, fx, fy) in PINS.items():
        cx, cy = mx0 + fx * mw, my0 + fy * mh
        pen.ellipse([cx - 8.4, cy - 8.4, cx + 8.4, cy + 8.4],
                    fill=(255, 255, 255))
        number_chip(pen, cx, cy, 7, REGION_RGB[region], num)
    vx, vy = mx0 + 0.965 * mw, my0 + 0.07 * mh
    dotted_circle(pen, vx, vy, 11, (88, 108, 138), dot=1.2, step_deg=16)
    starburst(pen, vx, vy, 6, 2.6, GOLD)
    lx = x0 + 10
    ly = y0 + 190
    fnt = font(FONT_SANS, 9)
    for name in ("Europe", "Middle East", "Asia", "Africa", "Americas",
                 "Oceania", "Global"):
        pen.ellipse([lx, ly + 1.5, lx + 5.2, ly + 6.7],
                    fill=REGION_RGB[name])
        pen.text(lx + 8, ly - 1.5, name, fnt, INK)
        lx += 8 + text_w(pen, name, fnt) + 9


# ---------------------------------------------------------------- panels

def story_panel(pen, box, story, art, hero):
    num, region, kicker, head, deck = story
    x0, y0, x1, y1 = box
    pen.rect(box, fill=PANEL_BG, outline=PANEL_EDGE, width=1)
    pad = 9 if hero else 8
    ix0, ix1 = x0 + pad, x1 - pad
    iw = ix1 - ix0
    art_top = y0 + (8 if hero else 5)
    art_h = 78 if hero else 34
    art(pen, [ix0, art_top, ix1, art_top + art_h])
    col = REGION_RGB[region]
    r = 8 if hero else 7
    ky = art_top + art_h + (4 if hero else 3)
    number_chip(pen, ix0 + r, ky + r, r, col, num)
    k_start = 12.5 if hero else 11
    kfnt, ksize = fit_single(pen, kicker, FONT_SANS_B, k_start, 8,
                             iw - 2 * r - 5)
    pen.text(ix0 + 2 * r + 5, ky + r - ksize * 0.62, kicker, kfnt, col)
    hy = ky + 2 * r + (5 if hero else 3)
    hfnt, hsize, hlines = fit_wrapped(pen, head, FONT_SERIF,
                                      23 if hero else 17, 12.5, iw, 2)
    lh = hsize * 1.14
    for i, ln in enumerate(hlines):
        pen.text(ix0, hy + i * lh, ln, hfnt, INK)
    dy = hy + len(hlines) * lh + 3
    dfnt, dsize, dlines = fit_wrapped(pen, deck, FONT_SANS,
                                      13 if hero else 11, 9, iw, 2)
    dlh = dsize * 1.2
    for i, ln in enumerate(dlines):
        pen.text(ix0, dy + i * dlh, ln, dfnt, (58, 60, 64))


def render():
    img = Image.new("RGB", (SIZE * SS, SIZE * SS), PAPER)
    pen = Pen(img)

    # 1 -- top strip
    left = "THE WORLD'S NEWS IN ONE PICTURE"
    draw_spaced(pen, MARGIN, 9, left, font(FONT_SANS_B, 12.5), RED, 1.6)
    right = "45 STORIES · 6 CONTINENTS · ALL FROM TUESDAY"
    rfnt = font(FONT_SANS_B, 12.5)
    pen.text(SIZE - MARGIN - text_w(pen, right, rfnt), 9, right, rfnt,
             NAVY)

    # 2 -- masthead with a double rule
    title = "Tuesday 17 November 2026"
    mfnt, _ = fit_single(pen, title, FONT_SERIF, 88, 40, CONTENT_W)
    pen.text((SIZE - text_w(pen, title, mfnt)) / 2, 30, title, mfnt,
             (24, 28, 38))
    pen.line([(MARGIN, 124), (SIZE - MARGIN, 124)], fill=INK, width=2.2)
    pen.line([(MARGIN, 127.5), (SIZE - MARGIN, 127.5)], fill=INK,
             width=0.9)

    # 3 -- red ticker
    tick = ("DOW −849 · NVIDIA $115.8BN RECORD · EBOLA PASSES 11,000 · "
            "VOYAGER 1 AT ONE LIGHT-DAY · 1,441 DRONES DOWNED")
    pen.rect([MARGIN, 134, SIZE - MARGIN, 161], fill=RED)
    tfnt, tsize = fit_single(pen, tick, FONT_SANS_B, 15, 10,
                             CONTENT_W - 20)
    pen.text((SIZE - text_w(pen, tick, tfnt)) / 2, 134 + (27 - tsize) / 2,
             tick, tfnt, (255, 255, 255))

    # 4 -- hero row
    hero_art = {1: ill_bridge, 2: ill_gulf, 3: ill_quad}
    for i, story in enumerate(HEROES):
        hx = MARGIN + i * 329
        story_panel(pen, [hx, 168, hx + 318, 364], story,
                    hero_art[story[0]], hero=True)

    # 5 -- card grid, 4 x 3
    for i, story in enumerate(CARDS):
        cx = MARGIN + (i % 4) * 246
        cy = 372 + (i // 4) * 132
        story_panel(pen, [cx, cy, cx + 238, cy + 126], story,
                    CARD_ART[story[0]], hero=False)

    # 6 -- bottom row: map + briefs
    draw_map(pen, [MARGIN, 770, MARGIN + 380, 982])
    bx = MARGIN + 392
    pen.text(bx, 774, "ALSO ON TUESDAY 17 NOVEMBER",
             font(FONT_SERIF, 16), NAVY)
    pen.line([(bx, 796), (SIZE - MARGIN, 796)], fill=PANEL_EDGE, width=1)
    col_w, col_gap = 279, 14
    for j, brief in enumerate(BRIEFS):
        num = 16 + j
        colx = bx + 6 + (j // 15) * (col_w + col_gap)
        rowy = 802 + (j % 15) * 11.7
        tag = "%d." % num
        size = 11.5
        while size > 9:
            bf, rf = font(FONT_SANS_B, size), font(FONT_SANS, size)
            if text_w(pen, tag, bf) + 3 + text_w(pen, brief, rf) <= col_w:
                break
            size -= 0.5
        pen.text(colx, rowy, tag, font(FONT_SANS_B, size), NAVY)
        pen.text(colx + text_w(pen, tag, font(FONT_SANS_B, size)) + 3,
                 rowy, brief, font(FONT_SANS, size), INK)

    # 7 -- footer
    pen.line([(MARGIN, 986), (SIZE - MARGIN, 986)], fill=PANEL_EDGE,
             width=1)
    line1 = ("DATE CHECK — Not counted: Thursday's Trump–Xi–Putin summit "
             "in Shenzhen (19 Nov) is previewed in story 3 only. Every "
             "numbered story happened or was first reported on Tuesday "
             "17 November 2026.")
    line2 = ("Disputed claims are attributed to whoever made them. "
             "Sources: Reuters · AP · AFP · BBC · Al Jazeera · WHO · "
             "PAHO · UN News. Original drawings.")
    for k, ln in enumerate((line1, line2)):
        lfnt, _ = fit_single(pen, ln, FONT_SANS, 11, 8.5, CONTENT_W)
        pen.text(MARGIN, 990 + k * 14, ln, lfnt, FAINT)

    return img.resize((SIZE, SIZE), Image.LANCZOS)


def main():
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "entry.png")
    render().save(out, format="PNG")
    print("wrote", out)


if __name__ == "__main__":
    main()
