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
# Sharp pixels for every letter: the MK1's 255x64 screens turned anti-aliased edges into grey smears, and with the
# heavy weight the small logo's E became a lump with notches (Dennis, 2026-10-27).
ImageDraw.ImageDraw.fontmode = "1"
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


SCENE_SECS = {"rufus": 8.0, "lab": 6.0}


def cat(d, cx, base, pose, glow):
    """Rufus, side view. pose 0 = lying dead (X eyes), 1 = arched back, fur up, eyes glowing"""
    w = g(31)
    if pose == 0:
        d.ellipse([cx - 26, base - 12, cx + 18, base], fill=w)                 # body flat on the table
        d.ellipse([cx + 12, base - 14, cx + 30, base - 1], fill=w)              # head
        d.polygon([(cx + 15, base - 12), (cx + 18, base - 20), (cx + 21, base - 12)], fill=w)
        d.polygon([(cx + 22, base - 12), (cx + 26, base - 19), (cx + 28, base - 11)], fill=w)
        for ex in (cx + 20, cx + 25):                                           # X eyes
            d.line([ex - 2, base - 10, ex + 1, base - 7], fill=0); d.line([ex - 2, base - 7, ex + 1, base - 10], fill=0)
        d.line([cx - 26, base - 4, cx - 44, base - 2], fill=w, width=2)         # limp tail
        for lx in (cx - 14, cx - 4, cx + 4):
            d.line([lx, base - 2, lx + 6, base + 2], fill=w, width=2)           # legs out sideways
    else:
        d.chord([cx - 26, base - 34, cx + 16, base + 6], 180, 360, fill=w)      # arched back
        d.rectangle([cx - 22, base - 14, cx + 12, base - 8], fill=w)
        for lx in (cx - 20, cx - 13, cx + 2, cx + 9):
            d.line([lx, base - 9, lx, base], fill=w, width=3)                   # stiff legs
        for i in range(9):                                                      # fur on end
            x = cx - 22 + i * 4; y = base - 30 + abs(i - 4) * 2
            d.line([x, y, x - 1, y - 4], fill=w)
        d.ellipse([cx + 10, base - 30, cx + 30, base - 12], fill=w)             # head, up
        d.polygon([(cx + 12, base - 27), (cx + 14, base - 37), (cx + 19, base - 29)], fill=w)
        d.polygon([(cx + 22, base - 29), (cx + 27, base - 37), (cx + 29, base - 26)], fill=w)
        for ex in (cx + 17, cx + 24):                                           # glowing eyes
            d.ellipse([ex - 2, base - 25, ex + 2, base - 21], fill=0)
            d.point([ex, base - 23], fill=g(31) if glow else g(10))
        d.line([cx + 18, base - 16, cx + 24, base - 16], fill=0)                # bared teeth
        for k in range(4): d.line([cx + 18 + k * 2, base - 16, cx + 19 + k * 2, base - 14], fill=0)
        pts = [(cx - 26, base - 12)]                                            # tail up, bristling
        for k in range(1, 7): pts.append((cx - 26 - k * 3 + (k % 2) * 2, base - 12 - k * 5))
        d.line(pts, fill=w, width=3)


def scene_rufus(c, t):
    """the cat on the lab table: dead, the syringe, a jolt, alive and furious"""
    d = ImageDraw.Draw(c)
    d.rectangle([20, 54, 230, 57], fill=g(20)); d.line([30, 57, 30, 64], fill=g(20)); d.line([220, 57, 220, 64], fill=g(20))
    alive = t > 4.2
    if not alive:
        cat(d, 120, 54, 0, False)
        d.text((10, 4), "RUFUS", font=SMALL, fill=g(18))
    if 1.0 < t < 4.2:                                                            # the syringe on the right screen
        u = (t - 1.0) / 3.2
        sx = W + 20 + int(30 * min(1, u * 2))
        syr = Image.new("L", (W, H), 0)
        syringe(ImageDraw.Draw(syr), 10 + int(30 * min(1, u * 2)), 30, 1 - max(0, u - 0.4) / 0.6, max(0, u - 0.4) / 0.6)
        c.paste(syr.transpose(Image.FLIP_LEFT_RIGHT), (W, 0))                    # needle pointing at the cat
        if u > 0.4:                                                              # the reagent sprays from the needle
            x0 = 10 + int(30 * min(1, u * 2))
            tip = (W + (W - 1 - (x0 + 132)), 30)                                 # the needle's tip, after the flip
            target = (150, 42)                                                   # the cat's head on the left screen
            push = (u - 0.4) / 0.6
            rnd = random.Random(11)
            for n in range(26):                                                  # droplets along an arc, each with its own start
                ph = (push * 2.2 + rnd.random()) % 1
                x = tip[0] + (target[0] - tip[0]) * ph + rnd.uniform(-3, 3)
                y = tip[1] + (target[1] - tip[1]) * ph - 10 * math.sin(ph * math.pi) + rnd.uniform(-2, 2) + 6 * ph * ph
                r = 1 if n % 3 else 0
                d.ellipse([x - r, y - r, x + r, y + r], fill=g(31) if n % 2 else g(22))
            jet = int(30 * min(1, push * 3))                                     # and a short jet right at the tip
            d.line([tip[0], tip[1], tip[0] - jet, tip[1] + 1], fill=g(31))
    if 4.0 < t < 4.4:                                                            # the jolt
        return "flash"
    if alive:
        jump = max(0, int(14 * math.sin(min(1, (t - 4.2) / 0.6) * math.pi))) if t < 4.8 else 0
        shake = int(2 * math.sin(t * 40)) if t < 5.5 else 0
        cat(d, 120 + shake, 54 - jump, 1, int(t * 6) % 2 == 0)
        ImageDraw.Draw(c).text((W + 40, 18), "HISSS!", font=BIG2, fill=g(31))
    return None


def scene_lab(c, t):
    """flasks bubbling on the left; a brain in a jar with electrodes and sparks on the right"""
    d = ImageDraw.Draw(c)
    flask(d, 50, 60, t, 0); flask(d, 125, 60, t, 1); flask(d, 200, 60, t, 2)
    jx = W + 128
    d.rectangle([jx - 30, 10, jx + 30, 62], outline=g(31))                     # the jar
    d.rectangle([jx - 34, 6, jx + 34, 10], fill=g(20))                          # the lid
    d.ellipse([jx - 24, 18, jx + 24, 50], fill=g(20))                          # the brain
    d.ellipse([jx - 6, 44, jx + 8, 56], fill=g(16))                            # brain stem
    d.line([jx, 19, jx, 49], fill=g(8))                                         # the two halves
    for k in range(5):                                                          # folds
        y0 = 22 + k * 6
        pts = [(jx - 22 + i * 4, y0 + int(2 * math.sin(i * 1.7 + k))) for i in range(12)]
        d.line(pts, fill=g(8))
    for b in range(3):                                                          # bubbles in the fluid
        by = 60 - int(((t * 0.7 + b * 0.33) % 1) * 48)
        d.point([jx - 20 + b * 18, by], fill=g(26))
    pulse = 0.5 + 0.5 * math.sin(t * 6)
    d.line([jx - 22, 50, jx + 22, 50], fill=g(int(14 + 12 * pulse)))
    for side in (-1, 1):                                                        # electrodes and wires
        ex = jx + side * 46
        d.line([jx + side * 20, 28, ex, 18], fill=g(24)); d.rectangle([ex - 3, 14, ex + 3, 22], fill=g(31))
    if int(t * 5) % 4 == 0:                                                     # a spark, now and then
        zx = jx - 40; pts = [(zx, 18)]
        for k in range(1, 7): pts.append((zx + k * 13, 18 + (8 if k % 2 else -4)))
        d.line(pts, fill=g(31), width=1)
    return None


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
SMALL = small
TINY = ImageFont.truetype(FONT, 8, index=8)
BIG2 = ImageFont.truetype(FONT, 26, index=8)
mid = ImageFont.truetype(FONT, 24, index=0)   # Bold, not Heavy: at this size Heavy closed the E's gaps
total = 9.0 + 4.4 + sum(SCENE_SECS.values())   # the intro, the living logos, then the scenes
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
            # From exactly where the big logo stands to exactly where each small one will drip, so nothing jumps
            # when the drips start (it used to land 10 px lower, as a shrunk picture, then be redrawn: the E
            # looked broken at the swap). The last 30 % of the way it is the small font's own letters.
            def glyphs(font):
                img = Image.new("L", (400, 60), 0)
                ImageDraw.Draw(img).text((0, 0), "RE-ANIMATOR", font=font, fill=g(31))
                bb = img.getbbox()
                return img.crop(bb), bb
            big_word, big_bb = glyphs(big)
            small_word, small_bb = glyphs(mid)
            small_w = ImageDraw.Draw(Image.new("L", (1, 1))).textlength("RE-ANIMATOR", font=mid)
            start = (int((2 * W - big_w) / 2) + big_bb[0], 6 + big_bb[1], big_word.width, big_word.height)
            from PIL import ImageChops
            for cx in (W / 2, W * 1.5):
                end = (int(cx - small_w / 2) + small_bb[0], 6 + small_bb[1], small_word.width, small_word.height)
                x, y, ww, wh = (int(round(a0 + (b0 - a0) * k)) for a0, b0 in zip(start, end))
                piece = (small_word if k >= 0.7 else big_word).resize((max(1, ww), max(1, wh)), Image.LANCZOS)
                layer = Image.new("L", canvas.size, 0)
                layer.paste(piece, (x, y))
                canvas = ImageChops.lighter(canvas, layer)   # two copies, light on light: one logo that comes apart
            dc = ImageDraw.Draw(canvas)
            random.seed(3)                        # the big logo's drops, falling away
            for n in range(14):
                x = random.randint(int((2 * W - big_w) / 2) + 4, int((2 * W + big_w) / 2) - 4)
                L = random.randint(4, 18)
                fy = 44 + L + int(120 * (u - 1.8) ** 2)
                if fy < H: dc.ellipse([x - 2, fy - 2, x + 2, fy + 2], fill=g(31))
        elif t >= 9.0 + LOOP_SECS:                # the scenes after the living logos, then the bridge starts over
            v = t - 9.0 - LOOP_SECS
            canvas = Image.new("L", (2 * W, H), 0)
            fx = None
            for name in ("rufus", "lab"):
                if v < SCENE_SECS[name]:
                    fx = {"rufus": scene_rufus, "lab": scene_lab}[name](canvas, v)
                    break
                v -= SCENE_SECS[name]
            if fx == "flash":
                canvas = Image.new("L", (2 * W, H), g(31))
            dc = ImageDraw.Draw(canvas)
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
LOOP_START = int(9.0 * FPS)   # (the bridge plays the whole file in a loop now; see main.c)


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
