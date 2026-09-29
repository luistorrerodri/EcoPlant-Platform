"""render.py - vistas previas PNG (rasterizador propio, solo numpy)."""
import numpy as np, zlib, struct, sys
import geo
from design import PIEZAS
from params import *

W = H = 1000


def png(path, rgb):
    h, w, _ = rgb.shape
    raw = b''.join(b'\x00' + rgb[y].tobytes() for y in range(h))
    def chunk(t, d):
        c = struct.pack('>I', len(d)) + t + d
        return c + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    out = b'\x89PNG\r\n\x1a\n'
    out += chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
    out += chunk(b'IDAT', zlib.compress(raw, 6))
    out += chunk(b'IEND', b'')
    open(path, 'wb').write(out)


def normals(v, t):
    a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    fn = np.cross(b - a, c - a)
    fn /= np.linalg.norm(fn, axis=1, keepdims=True) + 1e-12
    vn = np.zeros_like(v)
    for i in range(3):
        np.add.at(vn, t[:, i], fn)
    vn /= np.linalg.norm(vn, axis=1, keepdims=True) + 1e-12
    return vn


def render(parts, path, eye=(0.62, 0.92, -0.52), cut=None, splat=2):
    """parts = lista de (verts, tris, color). cut='x' corta la mitad x>0."""
    V, N, C = [], [], []
    for v, t, col in parts:
        vn = normals(v, t)
        keep = np.ones(len(v), bool)
        if cut == 'x':
            keep = v[:, 0] >= -0.6
        elif cut == 'y':
            keep = v[:, 1] >= -0.6
        V.append(v[keep]); N.append(vn[keep])
        C.append(np.tile(np.array(col, np.float32), (keep.sum(), 1)))
    V = np.concatenate(V); N = np.concatenate(N); C = np.concatenate(C)

    ctr = np.array([0.0, 0.0, 110.0], np.float32)
    f = np.array(eye, np.float32); f /= np.linalg.norm(f)
    right = np.cross(np.array([0, 0, 1.0], np.float32), f)
    right /= np.linalg.norm(right)
    up = np.cross(f, right)

    d = V - ctr
    u = d @ right; w = d @ up; dep = d @ f
    ext = max(np.abs(u).max(), np.abs(w).max()) * 1.06
    sc = (min(W, H) / 2.0) / ext
    px = (W / 2 + u * sc).astype(np.int32)
    py = (H / 2 - w * sc).astype(np.int32)

    light = np.array([0.45, 0.35, 0.82], np.float32); light /= np.linalg.norm(light)
    lam = np.clip(N @ light, 0, 1)
    shade = (0.30 + 0.70 * lam)[:, None] * C
    rim = 0.12 * np.clip(-(N @ f), 0, 1)[:, None]
    shade = np.clip(shade + rim, 0, 1)

    off = [(i, j) for i in range(-splat, splat + 1) for j in range(-splat, splat + 1)]
    PX = np.concatenate([px + o[0] for o in off])
    PY = np.concatenate([py + o[1] for o in off])
    DP = np.tile(dep, len(off))
    IX = np.tile(np.arange(len(V)), len(off))
    ok = (PX >= 0) & (PX < W) & (PY >= 0) & (PY < H)
    PX, PY, DP, IX = PX[ok], PY[ok], DP[ok], IX[ok]
    order = np.argsort(-DP, kind='stable')
    flat = (PY[order].astype(np.int64) * W + PX[order])
    buf = np.full(W * H, -1, np.int64)
    buf[flat] = IX[order]
    buf = buf.reshape(H, W)

    img = np.full((H, W, 3), 250, np.uint8)
    m = buf >= 0
    img[m] = (shade[buf[m]] * 255).astype(np.uint8)
    png(path, img)
    print('->', path)


CACHE = {}
def load(name):
    if name not in CACHE:
        d = np.load('/tmp/cache_%s.npy' % name)
        n = len(d)
        # v = 3*nv floats, t = 3*nt floats ; guardamos nv en build
        CACHE[name] = None
    return CACHE[name]


def build_part(name, fn):
    f, bbox, h = fn()
    return geo.mesh(f, bbox, h)


def shift(v, dx, dy, dz):
    o = v.copy(); o[:, 0] += dx; o[:, 1] += dy; o[:, 2] += dz
    return o


COL = dict(base=(0.72, 0.70, 0.66), tapa=(0.62, 0.60, 0.57),
           pot=(0.80, 0.55, 0.42), cesta=(0.45, 0.52, 0.58),
           tapon=(0.30, 0.55, 0.75), lid=(0.55, 0.55, 0.55),
           grid=(0.40, 0.60, 0.50))

if __name__ == '__main__':
    P = dict(PIEZAS)
    m = {k: build_part(k, P[k]) for k in P}

    single = [('01_cubeta_base', 'base', None), ('01_cubeta_base', 'base', 'x'),
              ('02_tapa_superior', 'tapa', None), ('03_maceta', 'pot', None),
              ('03_maceta', 'pot', 'x'), ('04_cesta', 'cesta', 'x'),
              ('05_tapon_llenado', 'tapon', None), ('06_tapa_bahia', 'lid', None),
              ('07_rejilla_drenaje', 'grid', None)]
    for name, col, cut in single:
        v, t = m[name]
        render([(v, t, COL[col])],
               'preview/%s%s.png' % (name, '_corte' if cut else ''),
               cut=cut, splat=2)

    conj = [
        (m['01_cubeta_base'][0], m['01_cubeta_base'][1], COL['base']),
        (m['02_tapa_superior'][0], m['02_tapa_superior'][1], COL['tapa']),
        (m['03_maceta'][0], m['03_maceta'][1], COL['pot']),
        (m['04_cesta'][0], m['04_cesta'][1], COL['cesta']),
        (shift(m['05_tapon_llenado'][0], 0, -FEAT_R, TOWER_TOP), m['05_tapon_llenado'][1], COL['tapon']),
        (shift(m['06_tapa_bahia'][0], 0, HATCH_CY, 0), m['06_tapa_bahia'][1], COL['lid']),
        (shift(m['07_rejilla_drenaje'][0], 0, 0, Z_DRAIN1), m['07_rejilla_drenaje'][1], COL['grid']),
    ]
    render(conj, 'preview/00_conjunto.png', splat=2)
    render(conj, 'preview/00_conjunto_corte.png', cut='x', splat=2)
    render(conj, 'preview/00_conjunto_dorso.png', eye=(-0.62, -0.92, -0.52), splat=2)
    render(conj, 'preview/00_conjunto_frontal.png', eye=(0.02, 1.0, -0.12), splat=2)
    render(conj, 'preview/00_conjunto_cenital.png', eye=(0.02, 0.05, -1.0), splat=2)
