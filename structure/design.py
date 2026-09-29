"""
design.py - las 7 piezas imprimibles del macetero de riego.
Cada funcion devuelve (sdf, bbox, paso_de_malla_mm).

Ejes:  -Y = FRENTE (torre de servicio)   +Y = DORSO (bahia + nervio)
"""
import numpy as np
from geo import (cyl, cyl_x, cone, box, tube, union, inter, diff,
                 rot_z, polar_array)
from params import *

NADA = box(0, 0, 0, 0, 0, 0)


def screw_positions():
    """Los 3 tornillos M3 de la tapa de servicio, en coordenadas del plato."""
    out = []
    for a in (90.0, 210.0, 330.0):
        r = np.radians(a)
        out.append((SCREW_R * np.cos(r), HATCH_CY + SCREW_R * np.sin(r)))
    return out


# ------------------------------------------------------------- 1. cubeta base
def cubeta_base():
    """Deposito + bahia electronica + anillo tecnico seco + pared exterior."""
    hueco = union(
        cyl(0, 0, R_RING_O, T_FLOOR, Z_RAMP0),                    # cavidad
        cone(0, 0, R_RING_O, R_LEDGE, Z_RAMP0, Z_LEDGE),          # rampa 45
        cyl(0, 0, R_LEDGE, Z_LEDGE, Z_WALL_TOP),
        cyl(0, 0, R_RING_O - 0.5, Z_WALL_TOP, H_BASE + 1),        # alojamiento
    )
    s = diff(cyl(0, 0, R_BASE, 0, H_BASE), hueco)

    s = union(
        s,
        tube(0, 0, R_TANK_I, R_TANK_O, T_FLOOR, Z_WALL_TOP),      # pared deposito
        box(-103, 103, CHORD_Y, CHORD_Y + T_DIV, T_FLOOR, Z_WALL_TOP),
        box(-5, 5, 98, 111, T_FLOOR, BOSS_TOP),                   # nervio del pilar
        box(-KEY_W / 2, KEY_W / 2, -116.8, -113.5,
            Z_WALL_TOP, H_BASE + 0.5),                            # chaveta antigiro
        *[cyl(px, py, BOSS_R, T_FLOOR, BOSS_TOP) for px, py in screw_positions()]
    )

    cortes = [
        cyl(0, HATCH_CY, HATCH_R, -2, T_FLOOR + 1),               # boca de servicio
        cyl(0, HATCH_CY, REBATE_R, -2, REBATE_D),                 # rebaje de la tapa
        box(-USB_W / 2, USB_W / 2, 100, R_BASE + 2, USB_Z, USB_Z + USB_H),
        box(-8, 8, R_TANK_I - 3, R_TANK_O + 4.2, 56.5, Z_WALL_TOP + 1),
    ]
    cortes += [cyl(px, py, PILOT_R, REBATE_D - 0.5, BOSS_TOP + 1)
               for px, py in screw_positions()]
    s = diff(s, *cortes)
    return s, (-R_BASE, R_BASE, -R_BASE, R_BASE, 0, H_BASE), 0.75


# ----------------------------------------------------------- 2. tapa superior
def tapa_superior():
    """Cierra el deposito por encima del nivel de agua y centra la maceta."""
    s = union(
        cyl(0, 0, R_PLATE, Z_WALL_TOP, H_BASE),
        tube(0, 0, R_POT + 0.8, R_POT + 3.8, H_BASE, H_BASE + COLLAR_H),
    )
    s = diff(
        s,
        cyl(0, -FEAT_R, TOWER_RI + 0.5, Z_WALL_TOP - 2, H_BASE + COLLAR_H + 2),
        cyl(0, FEAT_R, NERVE_RI + 0.5, Z_WALL_TOP - 2, H_BASE + COLLAR_H + 2),
        cyl(0, -FEAT_R, TOWER_RO + 5.0, H_BASE - 1, H_BASE + COLLAR_H + 2),
        cyl(0, FEAT_R, NERVE_RO + 4.0, H_BASE - 1, H_BASE + COLLAR_H + 2),
        box(-6, 6, -100, 45, Z_WALL_TOP - 1, Z_WALL_TOP + 4),     # cable LED
        box(20, 32, 20, 50, Z_WALL_TOP - 1, Z_WALL_TOP + 4),      # tubo aspiracion
        box(-KEY_W / 2 - 0.5, KEY_W / 2 + 0.5, -118, -112.8,
            Z_WALL_TOP - 1, H_BASE + 1),                          # chavetero
        tube(0, 0, R_TANK_I + 0.5, R_TANK_O - 0.5,
             Z_WALL_TOP - 1, Z_WALL_TOP + 1.2),                   # junta de 2 mm
    )
    return s, (-R_PLATE - 1, R_PLATE + 1, -R_PLATE - 1, R_PLATE + 1,
               Z_WALL_TOP, H_BASE + COLLAR_H), 0.55


# ----------------------------------------------------------------- 3. maceta
def maceta():
    """Ø200 con torre de servicio delante y nervio de cables detras."""
    cuerpo = cyl(0, 0, R_POT, Z_POT, Z_POT_T)
    torre = union(cyl(0, -FEAT_R, TOWER_RO, Z_POT, TOWER_COL_Z),
                  cone(0, -FEAT_R, TOWER_RO, TOWER_COL_R,
                       TOWER_COL_Z - 5, TOWER_COL_Z),
                  cyl(0, -FEAT_R, TOWER_COL_R, TOWER_COL_Z, TOWER_TOP))
    nervio = cyl(0, FEAT_R, NERVE_RO, Z_POT, NERVE_TOP)
    # cordones de refuerzo en las 4 lineas de union torre/nervio con la pared:
    # evitan aristas en cuchillo y concentracion de tensiones
    refuerzo = union(
        cyl(12.5, -97.8, 5.0, Z_POT, TOWER_COL_Z),
        cyl(-12.5, -97.8, 5.0, Z_POT, TOWER_COL_Z),
        cyl(8.8, 98.4, 3.6, Z_POT, NERVE_TOP),
        cyl(-8.8, 98.4, 3.6, Z_POT, NERVE_TOP),
    )
    macizo = union(cuerpo, torre, nervio, refuerzo)
    cavidad = diff(cyl(0, 0, R_POT - T_POT, Z_POT + 3, Z_POT_T + 1),
                   torre, nervio, refuerzo)

    s = diff(
        macizo, cavidad,
        cyl(0, -FEAT_R, TOWER_RI, Z_POT - 2, TOWER_TOP + 2),      # boca de llenado
        cyl(0, FEAT_R, NERVE_RI, Z_POT - 2, NERVE_TOP + 2),       # paso de cables
        cyl(LED_X, -FEAT_R, LED_R, TOWER_COL_Z - 1, TOWER_TOP + 2),
        box(6.0, 17.0, -FEAT_R - 3.2, -FEAT_R + 3.2,
            TOWER_COL_Z, TOWER_COL_Z + 4),                        # paso al LED
        box(-6, 6, 78, FEAT_R + 1, NERVE_TOP - 10, NERVE_TOP + 1),
        cyl_x(0, Z_POT + 6, 2.5, R_POT - 8, R_POT + 5),           # rebosaderos
        cyl_x(0, Z_POT + 6, 2.5, -R_POT - 5, -R_POT + 8),
    )
    tabique = inter(cyl(0, -FEAT_R, TOWER_RI, Z_POT, TOWER_TOP - 2),
                    box(COND_X0, COND_X1, -110, -74, Z_POT, TOWER_TOP - 2))
    tetones = polar_array(cyl(0, -60, 6, Z_POT + 3, Z_BASK), 3, 30.0)
    s = union(s, tabique, tetones)
    return s, (-R_POT, R_POT, -FEAT_R - TOWER_COL_R, FEAT_R + NERVE_RO,
               Z_POT, TOWER_TOP), 0.75


# ------------------------------------------------------------------ 4. cesta
def cesta():
    """Cesta de plantacion con camara de aireacion y rebosadero."""
    ri = R_BASK - T_BASK
    cuerpo = diff(cyl(0, 0, R_BASK, Z_BASK, Z_BASK_T),
                  cyl(0, 0, ri, Z_DRAIN0, Z_BASK_T + 1))
    # repisa escalonada: dos voladizos de 1.7 mm, imprimible sin soportes
    repisa = union(
        tube(0, 0, ri - 1.7, ri, Z_DRAIN1 - 5.0, Z_DRAIN1 - 2.5),
        tube(0, 0, ri - 3.4, ri, Z_DRAIN1 - 2.5, Z_DRAIN1),
    )
    s = diff(
        union(cuerpo, repisa),
        cyl(0, -FEAT_R, TOWER_RO + 1.5, Z_BASK - 2, Z_BASK_T + 2),
        cyl(0, FEAT_R, NERVE_RO + 1.5, Z_BASK - 2, Z_BASK_T + 2),
        cyl_x(0, Z_OVER, 2.5, R_BASK - 8, R_BASK + 5),            # rebosaderos
        cyl_x(0, Z_OVER, 2.5, -R_BASK - 5, -R_BASK + 8),
        cyl_x(0, Z_BASK_T + 2, 9, R_BASK - 14, R_BASK + 5),       # asas
        cyl_x(0, Z_BASK_T + 2, 9, -R_BASK - 5, -R_BASK + 14),
    )
    return s, (-R_BASK, R_BASK, -FEAT_R - NERVE_RO, FEAT_R + NERVE_RO,
               Z_BASK, Z_BASK_T), 0.75


# ------------------------------------------------------------------ 5. tapon
def tapon():
    """Tapon a presion de la boca de llenado. Vastago en D: libra el tabique."""
    vastago = diff(
        union(cone(0, 0, CAP_PLUG - 1.2, CAP_PLUG, -CAP_SKIRT, -CAP_SKIRT + 1.5),
              cyl(0, 0, CAP_PLUG, -CAP_SKIRT + 1.5, 0.5)),
        box(COND_X0 - 0.4, 30, -30, 30, -CAP_SKIRT - 1, 1))
    s = union(cyl(0, 0, CAP_R, 0, CAP_T),
              vastago,
              box(-9, 9, -2.5, 2.5, CAP_T - 0.5, CAP_T + 3))      # lengueta
    return s, (-CAP_R, CAP_R, -CAP_R, CAP_R, -CAP_SKIRT, CAP_T + 3), 0.25


# ------------------------------------------------------------- 6. tapa bahia
def tapa_bahia():
    """Tapa de servicio de la bahia electronica, 3 tornillos M3."""
    s = diff(
        cyl(0, 0, LID_R, 0, LID_T),
        cyl(0, 0, 8, -0.5, 1.0),                                  # hueco de agarre
        *[cyl(px, py - HATCH_CY, 1.7, -1, LID_T + 1)
          for px, py in screw_positions()]
    )
    return s, (-LID_R, LID_R, -LID_R, LID_R, 0, LID_T), 0.35


# ---------------------------------------------------------------- 7. rejilla
def rejilla():
    """Rejilla suelta que separa la tierra de la camara de aireacion."""
    s = diff(
        cyl(0, 0, R_GRID, 0, T_GRID),
        polar_array(box(-1.75, 1.75, 24, R_GRID + 1, -1, T_GRID + 1), 12, 0.0),
        polar_array(box(-1.5, 1.5, 10, 21, -1, T_GRID + 1), 8, 22.5),
        cyl(0, -FEAT_R, TOWER_RO + 2.0, -1, T_GRID + 1),
        cyl(0, FEAT_R, NERVE_RO + 2.0, -1, T_GRID + 1),
        cyl(30, 0, 5, -1, T_GRID + 1),                            # agarres
        cyl(-30, 0, 5, -1, T_GRID + 1),
    )
    return s, (-R_GRID, R_GRID, -R_GRID, R_GRID, 0, T_GRID), 0.4


PIEZAS = [
    ("01_cubeta_base", cubeta_base),
    ("02_tapa_superior", tapa_superior),
    ("03_maceta", maceta),
    ("04_cesta", cesta),
    ("05_tapon_llenado", tapon),
    ("06_tapa_bahia", tapa_bahia),
    ("07_rejilla_drenaje", rejilla),
]
