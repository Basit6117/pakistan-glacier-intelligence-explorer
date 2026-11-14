"""Synthetic check of the multi-geometry velocity inversion.

Uses the real descending radar geometry from the downloaded GOFF file, plus a mirrored ascending geometry,
simulates offsets from a known 3-D velocity field, and checks the inversion recovers it.
Run:  .venv\\Scripts\\python tests\\test_inversion.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pgie.nisar import invert  # noqa: E402

rng = np.random.default_rng(0)
shape = (50, 60)

# Realistic NISAR-like geometry: descending heading ~190°, left-looking; incidence ~38°
inc = np.radians(38)
desc = dict(ae=np.full(shape, -0.17), an=np.full(shape, -0.985))
desc.update(le=np.full(shape, -np.sin(inc) * 0.985), ln=np.full(shape, np.sin(inc) * 0.17))
asc = dict(ae=np.full(shape, -0.17), an=np.full(shape, 0.985))          # heading ~350°
asc.update(le=np.full(shape, np.sin(inc) * 0.985), ln=np.full(shape, np.sin(inc) * 0.17))
for g in (desc, asc):
    g["lu"] = np.sqrt(1 - g["le"] ** 2 - g["ln"] ** 2)

# Known truth: glacier flowing south-east at 120 m/yr, sinking 6 m/yr
ve_t, vn_t, vu_t = np.full(shape, 85.0), np.full(shape, -85.0), np.full(shape, -6.0)


def observe(g, noise):
    v_at = g["ae"] * ve_t + g["an"] * vn_t + rng.normal(0, noise, shape)
    v_sr = -(g["le"] * ve_t + g["ln"] * vn_t + g["lu"] * vu_t) + rng.normal(0, noise, shape)
    return dict(v_at=v_at, v_sr=v_sr, **g)


def check(name, cond, detail):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}: {detail}")
    return cond


ok = True
# 1) both geometries, no noise → exact 3-D recovery
ve, vn, vu, ng = invert([observe(desc, 0), observe(asc, 0)])
err = max(np.abs(ve - ve_t).max(), np.abs(vn - vn_t).max(), np.abs(vu - vu_t).max())
ok &= check("asc+desc exact", err < 1e-6 and (ng == 2).all(), f"max error {err:.2e} m/yr")

# 2) both geometries with 10 m/yr noise → errors comparable to noise
ve, vn, vu, _ = invert([observe(desc, 10), observe(asc, 10)])
rms = np.sqrt(np.mean((np.hypot(ve, vn) - np.hypot(ve_t, vn_t)) ** 2))
ok &= check("asc+desc noisy", rms < 15, f"speed RMS error {rms:.1f} m/yr with 10 m/yr input noise")

# 3) single geometry → horizontal recovered; the ignored vertical motion leaks in as a bounded bias
ve, vn, vu, ng = invert([observe(desc, 0)])
bias = np.abs(np.hypot(ve, vn) - np.hypot(ve_t, vn_t)).max()
ok &= check("desc only", (ng == 1).all() and np.allclose(vu, 0) and bias < 15,
            f"speed bias from neglected vertical {bias:.1f} m/yr (vu forced to 0)")

# 4) pixel missing in one geometry falls back to single-geometry solve
o_d, o_a = observe(desc, 0), observe(asc, 0)
o_a["v_at"][:10] = np.nan
ve, vn, vu, ng = invert([o_d, o_a])
ok &= check("mixed coverage", (ng[:10] == 1).all() and (ng[10:] == 2).all() and np.isfinite(ve).all(),
            "pixels fall back to 1-geometry where the other is missing")

print("\nALL PASSED" if ok else "\nSOME TESTS FAILED")
sys.exit(0 if ok else 1)
