# RE-ANIMATOR's MK1 screen animation, drawn here and played by the bridge (bridge/mk1-bridge/main.c, reanimator_anim).
#   python3 make_anim.py OUT.anim [--gif PREVIEW.gif]
# Two 255x64 grey screens at 20 fps: a flatline, a syringe of glowing reagent, a heartbeat, one big RE-ANIMATOR logo
# over both screens that splits into one logo per screen. Then a 4.4 s loop (living logos, a small heartbeat) until
# Maschine takes the screens; the bridge replays the whole intro every 30 s while it waits. Our own drawing, inspired by the film, nothing copied from it.
import struct, sys
import math, random
from PIL import Image, ImageDraw, ImageFont
W, H, FPS = 255, 64, 20
random.seed(7)
FONT = "/System/Library/Fonts/Avenir Next.ttc"
def g(v):  # MK1 grey: 5-bit level 0..31 -> 0..255
    return int(v * 255 / 31)

def ecg(x, beat_x):
    """an ECG trace: flat, with a P-QRS-T shape centred on beat_x"""
    d = x - beat_x
    if -26 < d < -18: return -3 * math.sin((d + 26) / 8 * math.pi)       # P
    if -6 < d < -3:   return 4                                          # Q
    if -3 <= d < 0:   return -22 * (d + 3) / 3                          # R up
    if 0 <= d < 3:    return -22 + 30 * d / 3                           # R down to S
    if 3 <= d < 6:    return 8 - 8 * (d - 3) / 3                        # back
    if 14 < d < 30:   return -5 * math.sin((d - 14) / 16 * math.pi)     # T
    return 0

def screens():
    a = Image.new("L", (W, H), 0); b = Image.new("L", (W, H), 0)
    return a, b, ImageDraw.Draw(a), ImageDraw.Draw(b)

def syringe(d, x, y, fill, push):
    """a syringe pointing right: barrel at x..x+90, needle to x+130, reagent level `fill` 0..1, plunger `push`"""
    d.rectangle([x, y - 9, x + 90, y + 9], outline=g(31))                   # barrel
    for t in range(1, 6): d.line([x + t * 15, y + 9, x + t * 15, y + 5], fill=g(20))   # scale marks
    lvl = int(88 * fill)
    if lvl > 0:
        d.rectangle([x + 90 - lvl, y - 7, x + 89, y + 7], fill=g(26))       # glowing reagent
        for i in range(0, lvl, 6): d.point([x + 90 - i, y - 3], fill=g(31))
    px = x - 18 + int(push * 88)
    d.rectangle([px, y - 3, x + max(1, int(push * 88)), y + 3], fill=g(18))  # plunger rod
    d.rectangle([px - 4, y - 11, px, y + 11], fill=g(31))                   # thumb rest
    d.polygon([(x + 90, y - 5), (x + 100, y - 2), (x + 100, y + 2), (x + 90, y + 5)], fill=g(31))
    d.line([x + 100, y, x + 132, y], fill=g(31), width=1)                   # needle

def title(d, x0, txt, drip_t, font):
    """our own dripping title lettering"""
    d.text((x0, 6), txt, font=font, fill=g(31))
    random.seed(3)
    bbox = d.textbbox((x0, 6), txt, font=font)
    for i in range(14):
        x = random.randint(bbox[0] + 4, bbox[2] - 4); L = random.randint(4, 18)
        n = int(L * min(1, drip_t * random.uniform(0.8, 1.6)))
        if n > 0:
            d.line([x, bbox[3] - 1, x, bbox[3] - 1 + n], fill=g(31), width=2 if i % 3 == 0 else 1)
            if n == L: d.ellipse([x - 2, bbox[3] + n - 1, x + 2, bbox[3] + n + 3], fill=g(31))

LOOP_SECS = 4.4          # the loop's length: every moving part repeats exactly in it, so it joins up seamlessly


def living_logo(d, x0, txt, font, t, bright):
    """the logo while it waits: each drip grows, lets a drop fall, and grows back, each at its own phase"""
    d.text((x0, 6), txt, font=font, fill=g(bright))
    random.seed(3)
    bbox = d.textbbox((x0, 6), txt, font=font)
    for i in range(14):
        x = random.randint(bbox[0] + 4, bbox[2] - 4)
        L = random.randint(4, 14)
        off = random.random()
        ph = (t / LOOP_SECS * (1 + i % 2) + off) % 1          # one or two drips per loop, never out of step
        top = bbox[3] - 1
        if ph < 0.6:                                          # growing
            n = int(L * ph / 0.6)
            if n: d.line([x, top, x, top + n], fill=g(bright), width=2 if i % 3 == 0 else 1)
        elif ph < 0.72:                                       # full, a drop swelling at the end
            d.line([x, top, x, top + L], fill=g(bright), width=2 if i % 3 == 0 else 1)
            d.ellipse([x - 2, top + L - 1, x + 2, top + L + 3], fill=g(bright))
        else:                                                 # the drop falls, the drip pulls back
            f = (ph - 0.72) / 0.28
            n = int(L * (1 - f))
            if n: d.line([x, top, x, top + n], fill=g(bright))
            fy = top + L + int(30 * f * f)
            if fy < 56: d.ellipse([x - 1, fy - 1, x + 1, fy + 1], fill=g(bright))


def heart_line(d, t, y=59):
    """a small heartbeat under the logo: a beat every 85 px, scrolling so that one loop moves it exactly 4 beats"""
    shift = (t / LOOP_SECS) * 340
    pts = []
    for x in range(W):
        yy = y
        for k in range(-1, 5):
            yy += 0.3 * ecg(x, k * 85 + 85 - (shift % 85))
        pts.append((x, yy))
    d.line(pts, fill=g(16))


def flask(d, cx, base, t, k):
    """a round lab flask with bubbling liquid"""
    d.ellipse([cx - 18, base - 34, cx + 18, base + 2], outline=g(31))
    d.rectangle([cx - 5, base - 50, cx + 5, base - 32], outline=g(31), fill=0)
    d.line([cx - 4, base - 33, cx + 4, base - 33], fill=0)
    d.chord([cx - 17, base - 33, cx + 17, base + 1], 20, 160, fill=g(14 + k * 4))
    for i in range(4):
        ph = (t * (0.9 + 0.3 * i) + i * 0.27 + k * 0.5) % 1
        bx = cx - 9 + i * 6 + int(2 * math.sin(t * 6 + i)); by = int(base - 6 - ph * 44)
        r = 1 + (i % 2)
        if by > base - 30: d.ellipse([bx - r, by - r, bx + r, by + r], outline=g(31))
        elif ph < 0.97: d.point([bx, by], fill=g(24))

frames = []
raw = []
big = ImageFont.truetype(FONT, 34, index=8)
small = ImageFont.truetype(FONT, 11, index=8)
mid = ImageFont.truetype(FONT, 22, index=8)
total = 9.0 + 4.4     # intro until 9.0 s, then the 4.4 s loop
for f in range(int(total * FPS)):
    t = f / FPS
    a, b, da, db = screens()
    if t < 1.4:                                   # A: flatline, nothing alive
        y = 44
        for x in range(W): da.point([x, y], fill=g(31)); db.point([x, y], fill=g(31))
        if (f // 6) % 2: db.text((8, 6), "NO SIGNAL", font=small, fill=g(20))
    elif t < 3.0:                                 # B: the syringe injects
        u = (t - 1.4) / 1.6
        syringe(da, 20 + int(25 * min(1, u * 3)), 32, 1 - max(0, u - 0.3) / 0.7, max(0, u - 0.3) / 0.7)
        for x in range(W): db.point([x, 44], fill=g(31))
        if u > 0.35:                              # drops travel along the needle
            for k in range(3):
                dx = int(((t * 90) + k * 30) % 60)
                da.point([150 + dx, 32], fill=g(31)) if 150 + dx < W else None
    elif t < 4.6:                                 # C: the heart starts, a flash on each beat
        u = t - 3.0
        beat = 1 / 0.8
        off = (u * 140) % 140
        for x in range(1, W):
            for (dd, base_x) in ((db, None), (da, None)):
                pass
        for scr, dd, shift in ((a, da, 0), (b, db, 255)):
            pts = []
            for x in range(W):
                X = x + shift
                yy = 40
                for bx in range(-140, 2 * W + 140, 140):
                    yy += ecg(X, bx + 140 - off)
                pts.append((x, yy))
            dd.line(pts, fill=g(31))
        if (u % 0.8) < 0.08: a = Image.eval(a, lambda v: 255 - v); b = Image.eval(b, lambda v: 255 - v)
    else:                                         # D: one big logo over both screens, then it splits in two
        u = t - 4.6
        canvas = Image.new("L", (2 * W, H), 0); dc = ImageDraw.Draw(canvas)
        big_w = dc.textlength("RE-ANIMATOR", font=big)
        if u < 1.6:                               # the big logo drips in, spanning both screens
            title(dc, int((2 * W - big_w) / 2), "RE-ANIMATOR", u / 1.2, big)
        elif u < 1.8:                             # a jolt: it is about to divide
            title(dc, int((2 * W - big_w) / 2), "RE-ANIMATOR", 1, big)
            canvas = Image.eval(canvas, lambda v: 255 - v)
        elif u < 3.0:                             # it splits: two copies move apart and shrink, the drops fall off
            k = (u - 1.8) / 1.2
            k = k * k * (3 - 2 * k)               # ease in and out
            word = Image.new("L", (int(big_w) + 4, 50), 0)
            ImageDraw.Draw(word).text((2, 0), "RE-ANIMATOR", font=big, fill=g(31))
            word = word.crop(word.getbbox())
            small_w = ImageDraw.Draw(Image.new("L", (1, 1))).textlength("RE-ANIMATOR", font=mid)
            sc = 1 + (small_w / word.width - 1) * k
            ww, wh = max(1, int(word.width * sc)), max(1, int(word.height * sc))
            piece = word.resize((ww, wh), Image.LANCZOS)
            y0 = int(10 + (17 - 10) * k)
            from PIL import ImageChops
            for cx in (W + (W / 2 - W) * k, W + (W * 1.5 - W) * k):
                layer = Image.new("L", canvas.size, 0)
                layer.paste(piece, (int(cx - ww / 2), y0))
                canvas = ImageChops.lighter(canvas, layer)   # two copies, light on light: one logo that comes apart
            dc = ImageDraw.Draw(canvas)
            random.seed(3)                        # the big logo's drops, falling away
            for n in range(14):
                x = random.randint(int((2 * W - big_w) / 2) + 4, int((2 * W + big_w) / 2) - 4)
                L = random.randint(4, 18)
                fy = 44 + L + int(120 * (u - 1.8) ** 2)
                if fy < H: dc.ellipse([x - 2, fy - 2, x + 2, fy + 2], fill=g(31))
        elif t >= 9.0:                            # the loop: living logos, a heartbeat, a pulse on each beat
            v = t - 9.0
            small_w = dc.textlength("RE-ANIMATOR", font=mid)
            beat = ((v / LOOP_SECS) * 4) % 1 < 0.08              # four beats per loop, in step with the line
            for cx in (W / 2, W * 1.5):
                living_logo(dc, int(cx - small_w / 2), "RE-ANIMATOR", mid, v, 31 if beat else 26)
            from PIL import ImageChops
            for half in (0, 1):                   # the heartbeat, light over whatever is there (falling drops)
                layer = Image.new("L", canvas.size, 0)
                heart_line(ImageDraw.Draw(layer), v)
                if half: layer = ImageChops.offset(layer, W, 0)
                canvas = ImageChops.lighter(canvas, layer)
            dc = ImageDraw.Draw(canvas)
        else:                                     # one logo on each screen, dripping again, alive
            small_w = dc.textlength("RE-ANIMATOR", font=mid)
            for cx in (W / 2, W * 1.5):
                title(dc, int(cx - small_w / 2), "RE-ANIMATOR", (u - 3.0) / 1.2, mid)
        a, b = canvas.crop((0, 0, W, H)), canvas.crop((W, 0, 2 * W, H))
        if 4.6 < u < 4.4 and (u % 2.2) < 0.06:    # (the loop has its own pulse now)
            a = Image.eval(a, lambda v: 255 - v); b = Image.eval(b, lambda v: 255 - v)
    raw.append((a, b))
    # the MK1's two displays side by side, with a bezel
    out = Image.new("L", (2 * W + 30, H + 20), g(4))
    out.paste(a, (10, 10)); out.paste(b, (W + 20, 10))
    frames.append(out.resize((out.width * 3, out.height * 3), Image.NEAREST).convert("P"))
LOOP_START = int(9.0 * FPS)


def rle(img):
    """5-bit grey (the ST7529's 0..31), run-length coded as (count 1..255, value) pairs"""
    px = [v * 31 // 255 for v in img.tobytes()]
    out, i = bytearray(), 0
    while i < len(px):
        j = i
        while j < len(px) and j - i < 255 and px[j] == px[i]:
            j += 1
        out += bytes((j - i, px[i]))
        i = j
    return bytes(out)


out = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "reanimator.anim"
with open(out, "wb") as f:
    f.write(b"RANIM1\0\0" + struct.pack("<HHHHH", W, H, FPS, len(raw), LOOP_START))
    for a, b in raw:
        for scr in (a, b):
            data = rle(scr)
            f.write(struct.pack("<I", len(data)) + data)
print(f"{out}: {len(raw)} frames at {FPS} fps, loop from {LOOP_START}")
if "--gif" in sys.argv:
    p = sys.argv[sys.argv.index("--gif") + 1]
    frames[0].save(p, save_all=True, append_images=frames[1:], duration=int(1000 / FPS), loop=0, optimize=True)
    print(p)
