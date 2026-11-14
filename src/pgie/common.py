"""Shared paths, area of interest and raster helpers for the Pakistan Glacier Intelligence Explorer."""
from pathlib import Path

import numpy as np
import rasterio
from numpy.lib.stride_tricks import sliding_window_view
from pyproj import Transformer

PROJECT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_DIR / "data"
ITS_LIVE_DIR = DATA_DIR / "its_live"
NISAR_DIR = DATA_DIR / "nisar"
PROCESSED_DIR = PROJECT_DIR / "processed"
RESULTS_DIR = PROJECT_DIR / "results"
FIGURES_DIR = RESULTS_DIR / "figures"

# Siachen Glacier area of interest (WGS84 lon/lat): main trunk + major tributaries.
AOI = dict(lon_min=76.75, lon_max=77.30, lat_min=35.15, lat_max=35.70)


def aoi_bounds_in(crs, aoi=AOI, n=25):
    """AOI bounding box (xmin, ymin, xmax, ymax) expressed in `crs`, densified so curved edges are enclosed."""
    t = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    lo, la = np.meshgrid(np.linspace(aoi["lon_min"], aoi["lon_max"], n),
                         np.linspace(aoi["lat_min"], aoi["lat_max"], n))
    x, y = t.transform(lo.ravel(), la.ravel())
    return float(np.min(x)), float(np.min(y)), float(np.max(x)), float(np.max(y))


def save_tif(path, arr, transform, crs, nodata=np.nan):
    arr = np.asarray(arr, dtype="float32")
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
                       dtype="float32", crs=crs, transform=transform, nodata=nodata,
                       compress="deflate") as dst:
        dst.write(arr, 1)


def read_tif(path):
    with rasterio.open(path) as src:
        a = src.read(1).astype("float64")
        if src.nodata is not None and not np.isnan(src.nodata):
            a[a == src.nodata] = np.nan
        return a, src.transform, src.crs


def nan_median_filter(a, size=5):
    pad = size // 2
    p = np.pad(a, pad, mode="constant", constant_values=np.nan)
    return np.nanmedian(sliding_window_view(p, (size, size)), axis=(-1, -2))
