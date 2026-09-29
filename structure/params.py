"""
params.py - todas las cotas del macetero, en milimetros.

Para escalar el producto cambia solo D_BASE (240 -> 200, 280...).
Los radios y alturas se derivan de ahi. Lo que NO escala son los huecos
que alojan componentes comerciales (bahia electronica, tapa de servicio,
boca de llenado): esos son absolutos a proposito.

Ejes:  -Y = FRENTE (torre de servicio)   +Y = DORSO (bahia + nervio)
       z = 0 en la base apoyada en la mesa
"""

# ---------------------------------------------------------------- escala
D_BASE   = 240.0                 # diametro exterior del plato
R_BASE   = D_BASE / 2.0          # 120

T_OUT    = 3.0                   # pared exterior
RING_W   = 7.0                   # anillo tecnico seco
T_TANK   = 3.0                   # pared del deposito

R_RING_O = R_BASE - T_OUT        # 117  cara interna de la pared exterior
R_TANK_O = R_RING_O - RING_W     # 110  cara externa del deposito
R_TANK_I = R_TANK_O - T_TANK     # 107  cara interna del deposito

# ---------------------------------------------------------------- alturas
T_FLOOR    = 3.5                 # suelo del plato
H_BASE     = 70.0                # altura total del plato
Z_WALL_TOP = 64.0                # coronacion del deposito (asiento de tapa)
Z_RAMP0    = 58.0                # inicio de la rampa a 45 grados
Z_LEDGE    = 61.0                # repisa donde apoya la tapa
R_LEDGE    = 113.0
WATER_MAX  = 55.0                # nivel maximo de agua

# ---------------------------------------------------------------- deposito
CHORD_Y = 30.0                   # plano divisorio; bahia electronica en y > 33
T_DIV   = 3.0

# ---------------------------------------------------------------- tapa superior
T_PLATE   = 6.0                  # z 64..70
R_PLATE   = R_RING_O - 1.0       # 116.0, holgura de 0.5 en el alojamiento
COLLAR_H  = 6.0                  # collar de centrado de la maceta
KEY_W     = 8.0                  # chaveta antigiro (1 sola)

# ---------------------------------------------------------------- maceta
R_POT   = 100.0
T_POT   = 2.5
H_POT   = 150.0
Z_POT   = H_BASE                 # 70
Z_POT_T = Z_POT + H_POT          # 220

# ---------------------------------------------------------------- torre y nervio
FEAT_R    = 92.0                 # radio al eje de torre y nervio
TOWER_RO  = 15.0                 # exterior de la torre
TOWER_RI  = 12.0                 # taladro (boca de llenado Ø24)
TOWER_TOP = 224.0
COND_X0   = 4.0                  # tabique interior: conducto de cable en x > 6.5
COND_X1   = 6.5
TOWER_COL_R = 20.0               # brida superior (asiento del tapon)
TOWER_COL_Z = 214.0
LED_X     = 16.0                 # LED difuso de 5 mm, brilla hacia arriba
LED_R     = 2.85

NERVE_RO  = 11.0
NERVE_RI  = 7.0
NERVE_TOP = 212.0

# ---------------------------------------------------------------- cesta
R_BASK    = 94.0
T_BASK    = 2.0
Z_BASK    = 77.0                 # apoya en 3 tetones del fondo de la maceta
Z_BASK_T  = 210.0
Z_DRAIN0  = 79.0                 # techo del fondo de la cesta
Z_DRAIN1  = 99.0                 # camara de aireacion de 20 mm
T_GRID    = 2.5                  # rejilla suelta (pieza 07)
R_GRID    = R_BASK - T_BASK - 3.8   # 88.2, apoya en la repisa (0.4 de holgura)
Z_SOIL    = Z_DRAIN1 + T_GRID    # 101.5
Z_OVER    = 94.0                 # rebosadero

# ---------------------------------------------------------------- bahia y tapa
HATCH_CY  = 70.0                 # centro de la tapa de servicio
HATCH_R   = 28.0                 # hueco Ø56
REBATE_R  = 36.0                 # rebaje para que la tapa quede enrasada
REBATE_D  = 2.0
LID_R     = 34.5
LID_T     = 2.0
SCREW_R   = 31.0                 # 3 tornillos M3 a 120 grados
BOSS_R    = 5.0
BOSS_TOP  = 16.0
PILOT_R   = 1.35                 # M3 autorroscante

USB_W     = 10.0                 # ventana para placa USB-C
USB_H     = 6.0
USB_Z     = 20.0

# ---------------------------------------------------------------- tapon
CAP_R     = 13.8
CAP_T     = 4.0
CAP_SKIRT = 8.0
CAP_PLUG  = 11.5                 # 0.5 de holgura en TOWER_RI
ORING_R0  = 10.0                 # garganta para junta torica de 2 mm
ORING_R1  = 12.2
