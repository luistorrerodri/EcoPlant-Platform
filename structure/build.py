import sys, time, json
import numpy as np
import geo
from design import PIEZAS

only = sys.argv[1:] if len(sys.argv) > 1 else None
report = {}
for name, fn in PIEZAS:
    if only and not any(o in name for o in only):
        continue
    t0 = time.time()
    f, bbox, h = fn()
    v, t = geo.mesh(f, bbox, h)
    bad = geo.check_closed(t)
    vol = geo.signed_volume(v, t)
    geo.write_stl('stl/%s.stl' % name, v, t)
    report[name] = dict(tris=int(t.shape[0]), verts=int(v.shape[0]),
                        aristas_mal=bad, volumen_cm3=round(vol / 1000.0, 1),
                        bbox_min=[round(x, 1) for x in v.min(0).tolist()],
                        bbox_max=[round(x, 1) for x in v.max(0).tolist()],
                        malla_mm=h, seg=round(time.time() - t0, 1))
    print(name, json.dumps(report[name]), flush=True)
json.dump(report, open('reporte.json', 'w'), indent=1, ensure_ascii=False)
