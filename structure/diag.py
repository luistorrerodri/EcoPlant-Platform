import numpy as np, sys, geo
from design import PIEZAS
name = sys.argv[1]
fn = dict(PIEZAS)[name]
f, bbox, h = fn()
v, t = geo.mesh(f, bbox, h)
e = np.sort(np.concatenate([t[:, [0,1]], t[:, [1,2]], t[:, [2,0]]]), axis=1)
u, c = np.unique(e, axis=0, return_counts=True)
bad = u[c != 2]
if len(bad) == 0:
    print('sin aristas malas'); sys.exit()
mid = (v[bad[:,0]] + v[bad[:,1]]) / 2
r = np.hypot(mid[:,0], mid[:,1])
# agrupar por proximidad
used = np.zeros(len(mid), bool)
groups = []
for i in range(len(mid)):
    if used[i]: continue
    d = np.linalg.norm(mid - mid[i], axis=1)
    m = (d < 6) & (~used)
    used |= m
    groups.append((int(m.sum()), mid[m].mean(0)))
groups.sort(key=lambda g: -g[0])
print(name, 'aristas malas:', len(bad), 'grupos:', len(groups))
for n, p in groups[:14]:
    print('  n=%-4d x=%7.1f y=%7.1f z=%7.1f   r=%6.1f' % (n, p[0], p[1], p[2], np.hypot(p[0],p[1])))
