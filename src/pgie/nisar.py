"""NISAR GOFF processing: crop → cull → bias-correct → common grid → multi-geometry velocity inversion.

Conventions (NISAR L2 GOFF product specification):
* ``alongTrackOffset``  — displacement along the flight direction (horizontal unit vector a = (ae, an)).
* ``slantRangeOffset``  — change in slant range; positive = surface moved away from the sensor.
* radarGrid ``losUnitVector{X,Y}`` — line of sight from target to sensor (its vertical part lu = +sqrt(1-le²-ln²)).

Velocity observation equations for one geometry (all in m/yr):
    v_at =  ae·ve + an·vn
    v_sr = -(le·ve + ln·vn + lu·vu)

* one geometry (ascending OR descending): 2 equations → solve (ve, vn) assuming vu = 0 (surface-parallel approx.)
* two or more geometries (ascending AND descending): ≥4 equations → least-squares (ve, vn, vu), no assumption.
"""
import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

import h5py
import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.transform import from_origin
from rasterio.warp import reproject, Resampling

from .common import AOI, aoi_bounds_in, nan_median_filter, read_tif, PROCESSED_DIR

G = "science/LSAR/GOFF/grids/frequencyA/pixelOffsets/"
RG = "science/LSAR/GOFF/metadata/radarGrid/"

NAME_RE = re.compile(
    r"NISAR_L2_(?P<prod>[A-Z]{2})_GOFF_(?P<cycle>\d{3})_(?P<track>\d{3})_(?P<pass_>[AD])_(?P<frame>\d{3})_"
    r"\d{3}_\d{4}_[A-Z]{2}_(?P<ref>\d{8}T\d{6})_\d{8}T\d{6}_(?P<sec>\d{8}T\d{6})_\d{8}T\d{6}_(?P<crid>[A-Z]\d{5})_"
)


def season_of(d: dt.datetime) -> str:
    """Glaciological season of the pair's mid-date: May–Oct = summer, Nov–Apr = winter."""
    return "summer" if 5 <= d.month <= 10 else "winter"


@dataclass
class Pair:
    path: Path
    track: int
    pass_: str
    frame: int
    ref: dt.datetime
    sec: dt.datetime
    crid: str
    prod: str

    @property
    def days(self):
        return (self.sec - self.ref).total_seconds() / 86400

    @property
    def mid(self):
        return self.ref + (self.sec - self.ref) / 2

    @property
    def season(self):
        return season_of(self.mid)

    @property
    def geometry(self):
        return f"{self.track:03d}{self.pass_}"

    @property
    def tag(self):
        return f"{self.track:03d}{self.pass_}{self.frame:03d}_{self.ref:%Y%m%d}_{self.sec:%Y%m%d}"


def find_pairs(nisar_dir) -> list:
    pairs = []
    for f in sorted(Path(nisar_dir).rglob("*.h5")):
        m = NAME_RE.search(f.name)
        if not m or "QA_STATS" in f.name:
            continue
        g = m.groupdict()
        pairs.append(Pair(f, int(g["track"]), g["pass_"], int(g["frame"]),
                          dt.datetime.strptime(g["ref"], "%Y%m%dT%H%M%S"),
                          dt.datetime.strptime(g["sec"], "%Y%m%dT%H%M%S"), g["crid"], g["prod"]))
    return sorted(pairs, key=lambda p: p.ref)


# ---------------------------------------------------------------- common analysis grid
@dataclass
class Grid:
    crs: CRS
    transform: object
    shape: tuple


def common_grid(epsg=32643, res=80.0, aoi=AOI) -> Grid:
    x0, y0, x1, y1 = aoi_bounds_in(f"EPSG:{epsg}", aoi)
    x0, y1 = np.floor(x0 / res) * res, np.ceil(y1 / res) * res
    w, h = int(np.ceil((x1 - x0) / res)), int(np.ceil((y1 - y0) / res))
    return Grid(CRS.from_epsg(epsg), from_origin(x0, y1, res, res), (h, w))


def to_grid(arr, src_transform, src_crs, grid: Grid, resampling=Resampling.nearest):
    out = np.full(grid.shape, np.nan, "float32")
    reproject(np.asarray(arr, "float32"), out, src_transform=src_transform, src_crs=src_crs,
              dst_transform=grid.transform, dst_crs=grid.crs, resampling=resampling,
              src_nodata=np.nan, dst_nodata=np.nan)
    return out.astype("float64")


def its_median_on_grid(grid: Grid):
    """ITS_LIVE 2017–2022 median speed (produced by notebook 02) resampled onto `grid`."""
    a, t, c = read_tif(PROCESSED_DIR / "its_live_siachen" / "siachen_v_median_2017_2022.tif")
    return to_grid(a, t, c, grid, Resampling.bilinear)


# ---------------------------------------------------------------- single pair
@dataclass
class PairResult:
    pair: Pair
    layer: str
    v_at: np.ndarray            # along-track velocity (m/yr), common grid
    v_sr: np.ndarray            # slant-range velocity (m/yr), common grid
    geom: dict                  # ae, an, le, ln, lu on common grid
    stats: dict = field(default_factory=dict)


def _radargrid_level(f, name, level, transform, shape, crs):
    X = f[RG + "xCoordinates"][()]; Y = f[RG + "yCoordinates"][()]
    dx, dy = X[1] - X[0], Y[1] - Y[0]
    src_t = from_origin(X[0] - dx / 2, Y[0] - dy / 2, dx, -dy)
    out = np.full(shape, np.nan, "float32")
    reproject(f[RG + name][level].astype("float32"), out, src_transform=src_t, src_crs=crs,
              dst_transform=transform, dst_crs=crs, resampling=Resampling.bilinear,
              src_nodata=np.nan, dst_nodata=np.nan)
    return out.astype("float64")


def process_pair(pair: Pair, grid: Grid, rock_mask=None, snr_min=5.0, max_abs=30.0, med_tol=2.0,
                 ref_height=5000.0) -> PairResult:
    """Crop, cull, bias-correct and resample one GOFF pair onto the common grid."""
    with h5py.File(pair.path, "r") as f:
        crs = CRS.from_epsg(int(f[G + "projection"][()]))
        X = f[G + "xCoordinates"][()]; Y = f[G + "yCoordinates"][()]
        res = X[1] - X[0]
        x0, y0, x1, y1 = aoi_bounds_in(crs)
        pad = 10 * res
        c0, c1 = np.searchsorted(X, x0 - pad), np.searchsorted(X, x1 + pad)
        r0, r1 = np.searchsorted(-Y, -(y1 + pad)), np.searchsorted(-Y, -(y0 - pad))
        if c1 <= c0 or r1 <= r0:
            raise ValueError(f"{pair.path.name} does not overlap the AOI")
        sl = np.s_[r0:r1, c0:c1]
        native_t = from_origin(X[c0] - res / 2, Y[r0] + abs(Y[1] - Y[0]) / 2, res, abs(Y[1] - Y[0]))
        shape = (r1 - r0, c1 - c0)

        best = None
        for L in [l.decode() for l in f["science/LSAR/GOFF/grids/frequencyA/listOfLayers"][()]]:
            pol = [p.decode() for p in f["science/LSAR/GOFF/grids/frequencyA/listOfPolarizations"][()]][0]
            at = f[G + f"{pol}/{L}/alongTrackOffset"][sl].astype("f8")
            sr = f[G + f"{pol}/{L}/slantRangeOffset"][sl].astype("f8")
            snr = f[G + f"{pol}/{L}/snr"][sl].astype("f8")
            score = np.mean(np.isfinite(at) & (np.abs(at) < max_abs) & (np.abs(sr) < max_abs) & (snr >= snr_min))
            if best is None or score > best[0]:
                best = (score, L, at, sr, snr)
        _, layer, at, sr, snr = best
        mask = f[G + "mask"][sl]
        h = f[RG + "heightAboveEllipsoid"][()]
        lev = int(np.argmin(np.abs(h - ref_height)))
        geom_native = {k: _radargrid_level(f, n, lev, native_t, shape, crs) for k, n in
                       [("ae", "alongTrackUnitVectorX"), ("an", "alongTrackUnitVectorY"),
                        ("le", "losUnitVectorX"), ("ln", "losUnitVectorY")]}

    # cull: product mask (255 = invalid, first digit 1 = water), SNR, magnitude, neighbourhood consistency
    keep = (mask != 255) & ((mask // 100) != 1) & np.isfinite(at) & np.isfinite(sr) & (snr >= snr_min) \
        & (np.abs(at) < max_abs) & (np.abs(sr) < max_abs)
    at = np.where(keep, at, np.nan); sr = np.where(keep, sr, np.nan)
    cons = (np.abs(at - nan_median_filter(at)) <= med_tol) & (np.abs(sr - nan_median_filter(sr)) <= med_tol)
    at = np.where(cons, at, np.nan); sr = np.where(cons, sr, np.nan)

    # onto the common grid (nearest keeps culled pixels culled; geometry is smooth → bilinear)
    at_g = to_grid(at, native_t, crs, grid)
    sr_g = to_grid(sr, native_t, crs, grid)
    geom = {k: to_grid(v, native_t, crs, grid, Resampling.bilinear) for k, v in geom_native.items()}
    geom["lu"] = np.sqrt(np.clip(1 - geom["le"] ** 2 - geom["ln"] ** 2, 0, 1))

    # stable-ground bias: rock should not move
    rock = np.isfinite(at_g) & (rock_mask if rock_mask is not None else True)
    bias_at, bias_sr = np.nanmedian(at_g[rock]), np.nanmedian(sr_g[rock])
    at_g -= bias_at; sr_g -= bias_sr
    noise = float(np.nanstd(np.hypot(at_g[rock], sr_g[rock])))

    scale = 365.25 / pair.days
    return PairResult(pair, layer, at_g * scale, sr_g * scale, geom, dict(
        layer=layer, bias_at_m=float(bias_at), bias_sr_m=float(bias_sr), rock_px=int(np.sum(rock)),
        rock_noise_m=noise, rock_noise_m_yr=noise * scale,
        valid_pct=float(100 * np.mean(np.isfinite(at_g)))))


# ---------------------------------------------------------------- multi-geometry inversion
def invert(observations, vertical_prior_weight=1.0):
    """Per-pixel least squares for (ve, vn, vu).

    observations: list of dicts with keys v_at, v_sr (m/yr) and ae, an, le, ln, lu (unit vectors) on one grid.
    Pixels seen by only one geometry get an extra equation vu = 0 (surface-parallel assumption), so every
    pixel is solvable; pixels seen by ≥2 geometries are solved freely for the vertical component.
    Returns ve, vn, vu, n_geom.
    """
    shape = observations[0]["v_at"].shape
    rows_A, rows_b, n_geom = [], [], np.zeros(shape, int)
    for o in observations:
        ok = np.isfinite(o["v_at"]) & np.isfinite(o["v_sr"]) & np.isfinite(o["le"])
        n_geom += ok
        z = np.zeros(shape)
        rows_A.append(np.stack([np.where(ok, o["ae"], 0), np.where(ok, o["an"], 0), z], -1))
        rows_b.append(np.where(ok, o["v_at"], 0))
        rows_A.append(np.stack([np.where(ok, -o["le"], 0), np.where(ok, -o["ln"], 0), np.where(ok, -o["lu"], 0)], -1))
        rows_b.append(np.where(ok, o["v_sr"], 0))
    one = n_geom == 1
    rows_A.append(np.stack([np.zeros(shape), np.zeros(shape), np.where(one, vertical_prior_weight, 0)], -1))
    rows_b.append(np.zeros(shape))
    A = np.stack(rows_A, -2)                       # (..., R, 3)
    b = np.stack(rows_b, -1)                       # (..., R)
    AtA = np.einsum("...ri,...rj->...ij", A, A)
    Atb = np.einsum("...ri,...r->...i", A, b)
    solvable = n_geom >= 1
    AtA[~solvable] = np.eye(3)
    x = np.linalg.solve(AtA, Atb[..., None])[..., 0]
    x[~solvable] = np.nan
    return x[..., 0], x[..., 1], x[..., 2], n_geom


def combine(results, group_by="season"):
    """Median-stack pairs per (group, geometry), then invert each group. Returns {group: dict of maps}."""
    groups = {}
    for r in results:
        key = getattr(r.pair, group_by) if group_by else "all"
        groups.setdefault(key, {}).setdefault(r.pair.geometry, []).append(r)
    out = {}
    for key, geoms in groups.items():
        obs, n_pairs = [], 0
        for gname, rs in geoms.items():
            n_pairs += len(rs)
            o = {"v_at": np.nanmedian(np.stack([r.v_at for r in rs]), 0) if len(rs) > 1 else rs[0].v_at,
                 "v_sr": np.nanmedian(np.stack([r.v_sr for r in rs]), 0) if len(rs) > 1 else rs[0].v_sr}
            o.update(rs[0].geom)
            obs.append(o)
        ve, vn, vu, ng = invert(obs)
        out[key] = dict(ve=ve, vn=vn, vu=vu, speed=np.hypot(ve, vn), n_geom=ng,
                        geometries=sorted(geoms), n_pairs=n_pairs)
    return out
