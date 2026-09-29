"""test.py - verificacion numerica del modelo."""
import numpy as np
from design import (cubeta_base, tapa_superior, maceta, cesta, tapon,
                    tapa_bahia, rejilla)
from params import *

def val(f, p):
    a = np.array([[p[0]]], np.float32)
    return float(f(a, np.array([[p[1]]], np.float32), np.array([[p[2]]], np.float32))[0, 0])

base = cubeta_base()[0]; plate = tapa_superior()[0]; pot = maceta()[0]
bask = cesta()[0]; cap = tapon()[0]; lid = tapa_bahia()[0]; grid = rejilla()[0]

CASOS = [
    ("base: deposito vacio",            base, (0, -60, 30), 'void'),
    ("base: bahia vacia",               base, (0, 60, 30), 'void'),
    ("base: tabique divisorio",         base, (0, 31.5, 30), 'solid'),
    ("base: anillo tecnico seco",       base, (113.5, 0, 30), 'void'),
    ("base: pared exterior",            base, (118.5, 0, 30), 'solid'),
    ("base: pared del deposito",        base, (108.5, 0, 30), 'solid'),
    ("base: pilar de tornillo",         base, (0, 104, 10), 'solid'),
    ("base: taladro guia M3",           base, (0, 101, 10), 'void'),
    ("base: boca de servicio",          base, (0, 70, 1.5), 'void'),
    ("base: suelo fuera de la boca",    base, (0, 30, 2), 'solid'),
    ("base: repisa de la tapa",         base, (115, 0, 62.5), 'solid'),
    ("base: alojamiento de la tapa",    base, (115, 0, 66), 'void'),
    ("base: ventana USB-C",             base, (0, 118, 23), 'void'),
    ("base: chaveta antigiro",          base, (0, -115, 67), 'solid'),
    ("base: ventana bahia-anillo",      base, (0, 108.5, 60), 'void'),
    ("tapa: cuerpo",                    plate, (60, 0, 66), 'solid'),
    ("tapa: collar de centrado",        plate, (102, 0, 72), 'solid'),
    ("tapa: paso de la torre",          plate, (0, -92, 66), 'void'),
    ("tapa: paso del nervio",           plate, (0, 92, 66), 'void'),
    ("tapa: canal de cable LED",        plate, (0, -60, 65), 'void'),
    ("tapa: techo sobre el canal",      plate, (0, -60, 69), 'solid'),
    ("tapa: canal cable bomba",         plate, (26, 35, 65), 'void'),
    ("maceta: espacio de tierra",       pot, (0, 0, 150), 'void'),
    ("maceta: pared",                   pot, (98.75, 0, 150), 'solid'),
    ("maceta: boca de llenado libre",   pot, (0, -92, 150), 'void'),
    ("maceta: pared de la torre",       pot, (0, -78.5, 150), 'solid'),
    ("maceta: tabique del conducto",    pot, (5.2, -92, 150), 'solid'),
    ("maceta: conducto de cable",       pot, (9.5, -92, 150), 'void'),
    ("maceta: paso del nervio",         pot, (0, 92, 150), 'void'),
    ("maceta: pared del nervio",        pot, (0, 83, 150), 'solid'),
    ("maceta: suelo",                   pot, (0, 0, 71.5), 'solid'),
    ("maceta: teton de apoyo",          pot, (30, -52, 75), 'solid'),
    ("cesta: camara de aireacion",      bask, (0, 0, 88), 'void'),
    ("cesta: fondo",                    bask, (0, 0, 78), 'solid'),
    ("cesta: repisa de la rejilla",     bask, (90, 0, 98), 'solid'),
    ("cesta: bajo la repisa",           bask, (85, 0, 98), 'void'),
    ("cesta: pared",                    bask, (93, 0, 150), 'solid'),
    ("tapon: vastago",                  cap, (0, 0, -5), 'solid'),
    ("tapon: garganta junta torica",    cap, (11, 0, -5.5), 'void'),
    ("rejilla: material",               grid, (60, 12, 1.2), 'solid'),
    ("rejilla: ranura",                 grid, (60, 0, 1.2), 'void'),
]

fallos = 0
for nombre, f, p, esperado in CASOS:
    d = val(f, p)
    ok = (d < 0) if esperado == 'solid' else (d > 0)
    if not ok:
        fallos += 1
        print("FALLO  %-34s %-6s d=%+7.2f  en %s" % (nombre, esperado, d, p))
print("puntos comprobados: %d   fallos: %d" % (len(CASOS), fallos))

# ---- interferencias entre piezas (rejilla 1.2 mm)
def desplaza(f, dx, dy, dz):
    return lambda X, Y, Z: f(X - dx, Y - dy, Z - dz)

PIEZAS_POS = {
    'cubeta': base, 'tapa': plate, 'maceta': pot, 'cesta': bask,
    'tapon': desplaza(cap, 0, -FEAT_R, TOWER_TOP),
    'tapa_bahia': desplaza(lid, 0, HATCH_CY, 0),
    'rejilla': desplaza(grid, 0, 0, Z_DRAIN1),
}
step = 1.2
xs = np.arange(-122, 122, step, dtype=np.float32)
ys = np.arange(-122, 122, step, dtype=np.float32)
zs = np.arange(-2, 230, step, dtype=np.float32)
X, Y = np.meshgrid(xs, ys, indexing='ij')
dentro = {k: [] for k in PIEZAS_POS}
vox = {k: 0 for k in PIEZAS_POS}
choques = {}
for z in zs:
    m = {k: (f(X, Y, np.float32(z)) < -0.15) for k, f in PIEZAS_POS.items()}
    for k in m:
        vox[k] += int(m[k].sum())
    ks = list(m)
    for i in range(len(ks)):
        for j in range(i + 1, len(ks)):
            n = int((m[ks[i]] & m[ks[j]]).sum())
            if n:
                key = ks[i] + ' / ' + ks[j]
                choques[key] = choques.get(key, 0) + n
print("\ninterferencias (voxeles de 1.2 mm, margen 0.15 mm):")
if not choques:
    print("  ninguna")
for k, n in sorted(choques.items(), key=lambda x: -x[1]):
    print("  %-26s %6d vox = %6.1f cm3" % (k, n, n * step ** 3 / 1000))

# ---- volumenes utiles
v = step ** 3 / 1000.0
agua = 0.0
tierra = 0.0
for z in zs:
    if T_FLOOR < z < WATER_MAX:
        m = (base(X, Y, np.float32(z)) > 0.2) & (Y < CHORD_Y) & (X ** 2 + Y ** 2 < R_TANK_I ** 2)
        agua += int(m.sum()) * v
    if Z_SOIL < z < Z_BASK_T - 15:
        m = (bask(X, Y, np.float32(z)) > 0.2) & (pot(X, Y, np.float32(z)) > 0.2) \
            & (X ** 2 + Y ** 2 < (R_BASK - T_BASK) ** 2)
        tierra += int(m.sum()) * v
print("\ndeposito util hasta el nivel maximo : %.2f L" % (agua / 1000))
print("tierra (hasta 15 mm bajo el borde)  : %.2f L" % (tierra / 1000))
print("volumen de material por pieza (cm3):")
for k in vox:
    print("  %-12s %6.0f" % (k, vox[k] * v))
