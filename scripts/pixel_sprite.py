"""Re-pixeliza um sprite gerado por IA: acha a grade, 1 cor por célula, tira o fundo e fecha o contorno.

uv run --with pillow python scripts/pixel_sprite.py entrada.png saida.png 120 220  # faixa da célula em décimos de px
"""
import sys
from collections import Counter
from PIL import Image

src, out = sys.argv[1], sys.argv[2]
im = Image.open(src).convert("RGBA")
W, H = im.size
px = im.load()

def q(c):  # quantiza p/ achar a cor dominante da célula
    return tuple(v // 12 * 12 for v in c[:3])

best = None
for s10 in range(int(sys.argv[3]), int(sys.argv[4])):  # tamanho da célula em décimos de px
    s = s10 / 10
    for off in range(0, int(s), 1):
        err = 0; n = 0
        for gy in range(int((H - off) / s)):
            for gx in range(0, int((W - off) / s), 3):
                cx, cy = int(off + (gx + 0.5) * s), int(off + (gy + 0.5) * s)
                a, b = px[cx, cy], px[min(int(off + (gx + 0.85) * s), W - 1), cy]
                err += sum(abs(x - y) for x, y in zip(a[:3], b[:3])); n += 1
        score = err / n
        if best is None or score < best[0]:
            best = (score, s, off)
_, s, off = best
gw, gh = int((W - off) / s), int((H - off) / s)
print("célula", s, "offset", off, "grade", gw, gh)

g = Image.new("RGBA", (gw, gh))
gp = g.load()
for gy in range(gh):
    for gx in range(gw):
        cells = [px[min(int(off + (gx + fx) * s), W - 1), min(int(off + (gy + fy) * s), H - 1)]
                 for fx in (0.3, 0.5, 0.7) for fy in (0.3, 0.5, 0.7)]
        alpha = sum(c[3] for c in cells) / len(cells)
        if alpha < 128:
            gp[gx, gy] = (0, 0, 0, 0); continue
        mode = Counter(q(c) for c in cells if c[3] > 128).most_common(1)[0][0]
        pick = min((c for c in cells if c[3] > 128), key=lambda c: sum(abs(a - b) for a, b in zip(q(c), mode)))
        gp[gx, gy] = (*pick[:3], 255)

# fundo: branco/claro ligado à borda some
def light(c): return c[3] and min(c[:3]) > 200 and max(c[:3]) - min(c[:3]) < 30
stack = [(x, y) for x in range(gw) for y in (0, gh - 1)] + [(x, y) for y in range(gh) for x in (0, gw - 1)]
seen = set()
while stack:
    x, y = stack.pop()
    if (x, y) in seen or not (0 <= x < gw and 0 <= y < gh): continue
    seen.add((x, y))
    c = gp[x, y]
    if c[3] == 0 or light(c):
        gp[x, y] = (0, 0, 0, 0)
        stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]

# fiapos: pixel opaco com <=1 vizinho opaco
for _ in range(2):
    for y in range(gh):
        for x in range(gw):
            if gp[x, y][3]:
                nb = sum(1 for dx, dy in ((1,0),(-1,0),(0,1),(0,-1))
                         if 0 <= x+dx < gw and 0 <= y+dy < gh and gp[x+dx, y+dy][3])
                if nb <= 1: gp[x, y] = (0, 0, 0, 0)

# contorno escuro de 1px em volta de toda a silhueta
OUT = (38, 20, 30, 255)
edge = [(x, y) for y in range(gh) for x in range(gw) if not gp[x, y][3] and any(
    0 <= x+dx < gw and 0 <= y+dy < gh and gp[x+dx, y+dy][3] and gp[x+dx, y+dy] != OUT
    for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)))]
for x, y in edge: gp[x, y] = OUT

g = g.crop(g.getbbox())
pad = Image.new("RGBA", (g.width + 2, g.height + 2)); pad.paste(g, (1, 1))
pad.save(out)
print("final", pad.size)
