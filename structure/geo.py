"""
geo.py - motor de geometria minimo para generar STL imprimibles.

No requiere CAD: solo numpy.
Las piezas se describen con funciones de distancia con signo (SDF) y booleanas
(union / diferencia / interseccion). Despues se mallan con "surface nets",
que produce una malla cerrada (watertight) y se exporta a STL binario.
"""
import numpy as np
import struct


# ----------------------------------------------------------------- primitivas

def cyl(cx, cy, r, z0, z1):
    """Cilindro vertical macizo."""
    def f(X, Y, Z):
        dr = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2) - r
        dz = np.abs(Z - 0.5 * (z0 + z1)) - 0.5 * (z1 - z0)
        out = np.sqrt(np.maximum(dr, 0.0) ** 2 + np.maximum(dz, 0.0) ** 2)
        ins = np.minimum(np.maximum(dr, dz), 0.0)
        return out + ins
    return f


def cyl_x(cy, cz, r, x0, x1):
    """Cilindro horizontal a lo largo de X."""
    def f(X, Y, Z):
        dr = np.sqrt((Y - cy) ** 2 + (Z - cz) ** 2) - r
        dx = np.abs(X - 0.5 * (x0 + x1)) - 0.5 * (x1 - x0)
        out = np.sqrt(np.maximum(dr, 0.0) ** 2 + np.maximum(dx, 0.0) ** 2)
        ins = np.minimum(np.maximum(dr, dx), 0.0)
        return out + ins
    return f


def cyl_y(cx, cz, r, y0, y1):
    """Cilindro horizontal a lo largo de Y."""
    def f(X, Y, Z):
        dr = np.sqrt((X - cx) ** 2 + (Z - cz) ** 2) - r
        dy = np.abs(Y - 0.5 * (y0 + y1)) - 0.5 * (y1 - y0)
        out = np.sqrt(np.maximum(dr, 0.0) ** 2 + np.maximum(dy, 0.0) ** 2)
        ins = np.minimum(np.maximum(dr, dy), 0.0)
        return out + ins
    return f


def cone(cx, cy, r0, r1, z0, z1):
    """Tronco de cono vertical (r0 en z0, r1 en z1)."""
    def f(X, Y, Z):
        t = np.clip((Z - z0) / (z1 - z0), 0.0, 1.0)
        r = r0 + (r1 - r0) * t
        dr = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2) - r
        dz = np.abs(Z - 0.5 * (z0 + z1)) - 0.5 * (z1 - z0)
        out = np.sqrt(np.maximum(dr, 0.0) ** 2 + np.maximum(dz, 0.0) ** 2)
        ins = np.minimum(np.maximum(dr, dz), 0.0)
        return out + ins
    return f


def box(x0, x1, y0, y1, z0, z1):
    """Caja alineada con los ejes."""
    def f(X, Y, Z):
        dx = np.abs(X - 0.5 * (x0 + x1)) - 0.5 * (x1 - x0)
        dy = np.abs(Y - 0.5 * (y0 + y1)) - 0.5 * (y1 - y0)
        dz = np.abs(Z - 0.5 * (z0 + z1)) - 0.5 * (z1 - z0)
        out = np.sqrt(np.maximum(dx, 0.0) ** 2 + np.maximum(dy, 0.0) ** 2
                      + np.maximum(dz, 0.0) ** 2)
        ins = np.minimum(np.maximum(np.maximum(dx, dy), dz), 0.0)
        return out + ins
    return f


def slab_y(y0, y1):
    """Losa infinita en X y Z, acotada en Y."""
    def f(X, Y, Z):
        return np.abs(Y - 0.5 * (y0 + y1)) - 0.5 * (y1 - y0)
    return f


def tube(cx, cy, r_in, r_out, z0, z1):
    """Corona cilindrica (anillo) vertical."""
    return diff(cyl(cx, cy, r_out, z0, z1), cyl(cx, cy, r_in, z0 - 50, z1 + 50))


# ------------------------------------------------------------------ booleanas

def union(*fs):
    def f(X, Y, Z):
        r = fs[0](X, Y, Z)
        for g in fs[1:]:
            r = np.minimum(r, g(X, Y, Z))
        return r
    return f


def inter(*fs):
    def f(X, Y, Z):
        r = fs[0](X, Y, Z)
        for g in fs[1:]:
            r = np.maximum(r, g(X, Y, Z))
        return r
    return f


def diff(a, *bs):
    def f(X, Y, Z):
        r = a(X, Y, Z)
        for b in bs:
            r = np.maximum(r, -b(X, Y, Z))
        return r
    return f


def rot_z(f, deg):
    """Gira una SDF alrededor del eje Z."""
    a = np.radians(deg)
    ca, sa = np.cos(a), np.sin(a)

    def g(X, Y, Z):
        return f(ca * X + sa * Y, -sa * X + ca * Y, Z)
    return g


def polar_array(f, n, start=0.0):
    """Repite una SDF n veces alrededor del eje Z."""
    return union(*[rot_z(f, start + i * 360.0 / n) for i in range(n)])


# -------------------------------------------------------------------- mallado

def mesh(f, bbox, h, slab=24):
    """Surface nets. Devuelve (verts, tris) de una malla cerrada."""
    (x0, x1, y0, y1, z0, z1) = bbox
    pad = 3.0 * h
    xs = np.arange(x0 - pad, x1 + pad + h, h, dtype=np.float32)
    ys = np.arange(y0 - pad, y1 + pad + h, h, dtype=np.float32)
    zs = np.arange(z0 - pad, z1 + pad + h, h, dtype=np.float32)
    nx, ny, nz = len(xs), len(ys), len(zs)

    F = np.empty((nx, ny, nz), dtype=np.float32)
    X2, Y2 = np.meshgrid(xs, ys, indexing='ij')
    for k0 in range(0, nz, slab):
        k1 = min(k0 + slab, nz)
        for k in range(k0, k1):
            F[:, :, k] = f(X2, Y2, np.float32(zs[k]))

    # la pieza no puede tocar el borde de la rejilla
    for sl in (F[0], F[-1], F[:, 0], F[:, -1], F[:, :, 0], F[:, :, -1]):
        assert (sl > 0).all(), "la pieza toca el borde de la rejilla"

    ins = F < 0

    # ---- vertice por celda activa (media de los cortes en sus 12 aristas)
    acc = np.zeros((nx - 1, ny - 1, nz - 1, 3), dtype=np.float32)
    cnt = np.zeros((nx - 1, ny - 1, nz - 1), dtype=np.float32)
    P = [xs, ys, zs]

    for axis in range(3):
        sa = [slice(0, n - 1) for n in (nx, ny, nz)]
        sb = list(sa)
        sa[axis] = slice(0, [nx, ny, nz][axis])
        sb[axis] = slice(1, [nx, ny, nz][axis] + 1)
        # aristas a lo largo de "axis", indexadas por el punto inicial
        oth = [i for i in range(3) if i != axis]
        # recorremos las 4 posiciones de la arista dentro de la celda
        for o0 in (0, 1):
            for o1 in (0, 1):
                idx_a = [None, None, None]
                idx_b = [None, None, None]
                idx_a[axis] = slice(0, [nx, ny, nz][axis] - 1)
                idx_b[axis] = slice(1, [nx, ny, nz][axis])
                idx_a[oth[0]] = slice(o0, [nx, ny, nz][oth[0]] - 1 + o0)
                idx_b[oth[0]] = idx_a[oth[0]]
                idx_a[oth[1]] = slice(o1, [nx, ny, nz][oth[1]] - 1 + o1)
                idx_b[oth[1]] = idx_a[oth[1]]
                Fa = F[tuple(idx_a)]
                Fb = F[tuple(idx_b)]
                cross = (Fa < 0) != (Fb < 0)
                if not cross.any():
                    continue
                t = np.where(cross, Fa / (Fa - Fb + 1e-30), 0.0).astype(np.float32)
                # coordenada a lo largo de axis
                pa = P[axis][:-1].astype(np.float32)
                shape = [1, 1, 1]
                shape[axis] = -1
                pos_axis = pa.reshape(shape) + t * np.float32(h)
                # coordenadas fijas en los otros dos ejes
                comp = [None, None, None]
                comp[axis] = pos_axis
                for oi, oo in zip(oth, (o0, o1)):
                    p = P[oi][oo:oo + [nx, ny, nz][oi] - 1].astype(np.float32)
                    sh = [1, 1, 1]
                    sh[oi] = -1
                    comp[oi] = np.broadcast_to(p.reshape(sh), cross.shape)
                w = cross.astype(np.float32)
                cnt += w
                for c in range(3):
                    acc[:, :, :, c] += w * comp[c]

    active = cnt > 0
    verts = np.zeros((int(active.sum()), 3), dtype=np.float32)
    vid = np.full((nx - 1, ny - 1, nz - 1), -1, dtype=np.int64)
    vid[active] = np.arange(verts.shape[0])
    for c in range(3):
        verts[:, c] = acc[:, :, :, c][active] / cnt[active]

    # ---- quads: una arista de rejilla con cambio de signo -> 4 celdas vecinas
    quads = []
    dims = (nx, ny, nz)
    for axis in range(3):
        o1, o2 = (axis + 1) % 3, (axis + 2) % 3
        sa = [slice(None)] * 3
        sb = [slice(None)] * 3
        sa[axis] = slice(0, dims[axis] - 1)
        sb[axis] = slice(1, dims[axis])
        sa[o1] = sb[o1] = slice(1, dims[o1] - 1)
        sa[o2] = sb[o2] = slice(1, dims[o2] - 1)
        ia = ins[tuple(sa)]
        ib = ins[tuple(sb)]
        chg = ia != ib
        if not chg.any():
            continue
        idx = np.argwhere(chg)
        e = np.zeros((idx.shape[0], 3), dtype=np.int64)
        e[:, axis] = idx[:, axis]
        e[:, o1] = idx[:, o1] + 1
        e[:, o2] = idx[:, o2] + 1
        # celdas: (o1-1,o2-1) (o1,o2-1) (o1,o2) (o1-1,o2)
        corners = [(-1, -1), (0, -1), (0, 0), (-1, 0)]
        vs = []
        for (d1, d2) in corners:
            c = e.copy()
            c[:, o1] += d1
            c[:, o2] += d2
            vs.append(vid[c[:, 0], c[:, 1], c[:, 2]])
        vs = np.stack(vs, axis=1)
        assert (vs >= 0).all(), "celda inactiva en un quad"
        flip = ib[tuple(np.array(idx).T)]  # dentro en el lado +axis -> invertir
        vs[flip] = vs[flip][:, ::-1]
        quads.append(vs)

    quads = np.concatenate(quads, axis=0)
    tris = np.concatenate([quads[:, [0, 1, 2]], quads[:, [0, 2, 3]]], axis=0)

    if signed_volume(verts, tris) < 0:
        tris = tris[:, ::-1].copy()
    return verts, tris


def signed_volume(verts, tris):
    a = verts[tris[:, 0]].astype(np.float64)
    b = verts[tris[:, 1]].astype(np.float64)
    c = verts[tris[:, 2]].astype(np.float64)
    return float(np.einsum('ij,ij->i', a, np.cross(b, c)).sum() / 6.0)


def check_closed(tris):
    """Toda arista debe aparecer exactamente en 2 triangulos."""
    e = np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]])
    e = np.sort(e, axis=1)
    _, counts = np.unique(e, axis=0, return_counts=True)
    return int((counts != 2).sum())


def write_stl(path, verts, tris):
    v = verts[tris].astype(np.float32)
    n = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    n = np.divide(n, ln, out=np.zeros_like(n), where=ln > 0)
    with open(path, 'wb') as fh:
        fh.write(b'\0' * 80)
        fh.write(struct.pack('<I', tris.shape[0]))
        rec = np.zeros((tris.shape[0], 12), dtype=np.float32)
        rec[:, 0:3] = n
        rec[:, 3:6] = v[:, 0]
        rec[:, 6:9] = v[:, 1]
        rec[:, 9:12] = v[:, 2]
        buf = np.zeros((tris.shape[0], 50), dtype=np.uint8)
        buf[:, :48] = rec.view(np.uint8).reshape(-1, 48)
        fh.write(buf.tobytes())
