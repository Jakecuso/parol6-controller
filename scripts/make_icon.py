"""Generate a robot arm app icon at 1024x1024."""
from PIL import Image, ImageDraw, ImageFilter
import math, sys, os

SIZE = 1024

def draw_link(draw, x1, y1, x2, y2, width, color):
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length < 1:
        return
    px, py = -dy / length * width / 2, dx / length * width / 2
    points = [(x1+px,y1+py),(x2+px,y2+py),(x2-px,y2-py),(x1-px,y1-py)]
    draw.polygon(points, fill=color)

def draw_joint(draw, x, y, r, fill, rim=None):
    rim = rim or tuple(max(0, c - 40) for c in fill)
    draw.ellipse([x-r, y-r, x+r, y+r], fill=rim)
    inner = int(r * 0.72)
    draw.ellipse([x-inner, y-inner, x+inner, y+inner], fill=fill)
    # highlight
    hl = int(r * 0.38)
    hx, hy = int(x - r * 0.22), int(y - r * 0.22)
    draw.ellipse([hx-hl, hy-hl, hx+hl, hy+hl],
                 fill=tuple(min(255, c + 80) for c in fill))

img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))

# ── Background (rounded square, dark gradient) ──────────────────────────────
bg = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
bd = ImageDraw.Draw(bg)
R = 220
bd.rounded_rectangle([0, 0, SIZE-1, SIZE-1], radius=R, fill=(10, 12, 28, 255))
# Subtle blue-to-dark radial feel — paint a lighter circle in centre
for i in range(60, 0, -1):
    alpha = int(i * 0.6)
    r_i = int(SIZE * 0.55 * i / 60)
    bd.ellipse([SIZE//2 - r_i, SIZE//2 - r_i, SIZE//2 + r_i, SIZE//2 + r_i],
               fill=(20, 30, 70, alpha))
img = Image.alpha_composite(img, bg)

draw = ImageDraw.Draw(img)

# ── Colour palette ───────────────────────────────────────────────────────────
SILVER      = (185, 200, 218)
SILVER_DIM  = (120, 135, 152)
ORANGE      = (255, 107, 53)
ORANGE_RIM  = (180,  65,  20)
BLUE_GLOW   = (30, 144, 255)
BASE_COL    = (40,  55,  80)
BASE_LT     = (60,  80, 115)

# ── Arm joint positions (side view) ─────────────────────────────────────────
BX, BY = 512, 870   # base plate centre
J0 = (512, 770)     # base rotation axis
J1 = (410, 565)     # shoulder (upper arm top)
J2 = (575, 355)     # elbow
J3 = (730, 305)     # wrist
TOOL_TIP   = (790, 270)
FINGER_A   = (845, 235)
FINGER_B   = (845, 305)

# ── Glow under base ──────────────────────────────────────────────────────────
glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
gd   = ImageDraw.Draw(glow)
for step in range(30, 0, -1):
    a = int(step * 2.5)
    rr = step * 8
    gd.ellipse([BX-rr, BY+10-rr//5, BX+rr, BY+10+rr//5], fill=(*BLUE_GLOW, a))
glow = glow.filter(ImageFilter.GaussianBlur(12))
img  = Image.alpha_composite(img, glow)
draw = ImageDraw.Draw(img)

# ── Base platform ────────────────────────────────────────────────────────────
draw.rounded_rectangle([BX-175, BY-18, BX+175, BY+50], radius=22, fill=BASE_COL)
draw.rounded_rectangle([BX-110, BY-55, BX+110, BY- 5], radius=16, fill=BASE_LT)

# ── Column (base to J0) ──────────────────────────────────────────────────────
draw_link(draw, BX, BY-55, J0[0], J0[1], 90, SILVER_DIM)
draw_link(draw, BX, BY-55, J0[0], J0[1], 68, SILVER)

# ── J0 shoulder joint ────────────────────────────────────────────────────────
draw_joint(draw, J0[0], J0[1], 58, ORANGE, ORANGE_RIM)

# ── Upper arm (J0→J1) ────────────────────────────────────────────────────────
draw_link(draw, J0[0], J0[1], J1[0], J1[1], 78, SILVER_DIM)
draw_link(draw, J0[0], J0[1], J1[0], J1[1], 58, SILVER)

# ── Elbow joint ──────────────────────────────────────────────────────────────
draw_joint(draw, J1[0], J1[1], 50, ORANGE, ORANGE_RIM)

# ── Forearm (J1→J2) ──────────────────────────────────────────────────────────
draw_link(draw, J1[0], J1[1], J2[0], J2[1], 64, SILVER_DIM)
draw_link(draw, J1[0], J1[1], J2[0], J2[1], 46, SILVER)

# ── Wrist joint ──────────────────────────────────────────────────────────────
draw_joint(draw, J2[0], J2[1], 40, ORANGE, ORANGE_RIM)

# ── Wrist link (J2→J3) ───────────────────────────────────────────────────────
draw_link(draw, J2[0], J2[1], J3[0], J3[1], 50, SILVER_DIM)
draw_link(draw, J2[0], J2[1], J3[0], J3[1], 36, SILVER)

# ── Tool flange ──────────────────────────────────────────────────────────────
draw_joint(draw, J3[0], J3[1], 32, (255, 140, 60), (180, 90, 20))

# ── Tool shaft ───────────────────────────────────────────────────────────────
draw_link(draw, J3[0], J3[1], TOOL_TIP[0], TOOL_TIP[1], 28, SILVER_DIM)
draw_link(draw, J3[0], J3[1], TOOL_TIP[0], TOOL_TIP[1], 18, SILVER)

# ── Gripper fingers ───────────────────────────────────────────────────────────
draw_link(draw, TOOL_TIP[0], TOOL_TIP[1], FINGER_A[0], FINGER_A[1], 16, SILVER_DIM)
draw_link(draw, TOOL_TIP[0], TOOL_TIP[1], FINGER_A[0], FINGER_A[1], 10, SILVER)
draw_link(draw, TOOL_TIP[0], TOOL_TIP[1], FINGER_B[0], FINGER_B[1], 16, SILVER_DIM)
draw_link(draw, TOOL_TIP[0], TOOL_TIP[1], FINGER_B[0], FINGER_B[1], 10, SILVER)

# Fingertip dots
for fp in (FINGER_A, FINGER_B):
    draw.ellipse([fp[0]-9, fp[1]-9, fp[0]+9, fp[1]+9], fill=ORANGE)

# ── Blue accent line along arm (highlight on SILVER) ─────────────────────────
for seg in [(J0, J1), (J1, J2), (J2, J3)]:
    a, b = seg
    mx = (a[0] + b[0]) // 2
    my = (a[1] + b[1]) // 2
    draw_link(draw, a[0], a[1], mx, my, 6, (80, 160, 255, 160))

# ── Slight vignette ──────────────────────────────────────────────────────────
vign = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
vd   = ImageDraw.Draw(vign)
vd.rounded_rectangle([0, 0, SIZE-1, SIZE-1], radius=R, fill=(0, 0, 0, 0))
for i in range(1, 60):
    alpha = int(i * 1.8)
    pad   = i * 4
    vd.rounded_rectangle([pad, pad, SIZE-1-pad, SIZE-1-pad], radius=R,
                          outline=(0, 0, 0, alpha), width=1)
img = Image.alpha_composite(img, vign)

out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/parol6_icon_1024.png"
img.save(out)
print(f"saved {out}")
