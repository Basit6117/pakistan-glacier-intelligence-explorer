"""Change analysis on the ITS_LIVE stack: trend significance, change hotspots, glacier centreline."""
import heapq
from collections import deque

import numpy as np


def trend_with_stderr(stack, years, min_years=4):
    """Per-pixel OLS slope (units/yr) and its standard error. stack: (n_years, rows, cols) with NaNs."""
    t = np.asarray(years, "float64")[:, None, None] * np.ones_like(stack)
    ok = np.isfinite(stack)
    n = ok.sum(0)
    tm = np.where(ok, t, 0).sum(0) / np.maximum(n, 1)
    vm = np.where(ok, stack, 0).sum(0) / np.maximum(n, 1)
    sxx = np.where(ok, (t - tm) ** 2, 0).sum(0)
    sxy = np.where(ok, (t - tm) * (stack - vm), 0).sum(0)
    with np.errstate(all="ignore"):
        slope = sxy / sxx
        resid = np.where(ok, stack - (vm + slope * (t - tm)), 0)
        se = np.sqrt((resid ** 2).sum(0) / np.maximum(n - 2, 1) / sxx)
    bad = n < min_years
    slope[bad] = np.nan; se[bad] = np.nan
    return slope, se, n


def significant_change(slope, se, dv, dv_err, t_min=2.0):
    """+1 significant speed-up, -1 significant slow-down, 0 no significant change, NaN where undefined.

    Significant = trend is ≥ t_min standard errors from zero AND the end-to-end change dv exceeds
    t_min × its measurement uncertainty (both tests must agree in sign)."""
    out = np.where(np.isfinite(slope), 0.0, np.nan)
    with np.errstate(all="ignore"):
        trend_sig = np.abs(slope) >= t_min * se
        dv_sig = np.abs(dv) >= t_min * dv_err
    up = trend_sig & dv_sig & (slope > 0) & (dv > 0)
    down = trend_sig & dv_sig & (slope < 0) & (dv < 0)
    out[up] = 1; out[down] = -1
    return out


def label_regions(mask):
    """8-connected component labelling (no SciPy needed). Returns label array (0 = background) and count."""
    labels = np.zeros(mask.shape, np.int32)
    H, W = mask.shape
    n = 0
    for r0, c0 in zip(*np.nonzero(mask)):
        if labels[r0, c0]:
            continue
        n += 1
        labels[r0, c0] = n
        q = deque([(r0, c0)])
        while q:
            r, c = q.popleft()
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < H and 0 <= cc < W and mask[rr, cc] and not labels[rr, cc]:
                        labels[rr, cc] = n
                        q.append((rr, cc))
    return labels, n


def least_cost_path(cost, start, end):
    """Dijkstra on an 8-connected grid. cost: per-pixel cost (inf = impassable). start/end: (row, col)."""
    H, W = cost.shape
    dist = np.full(cost.shape, np.inf)
    prev = np.full(cost.shape + (2,), -1, np.int32)
    dist[start] = 0
    heap = [(0.0, start)]
    steps = [(dr, dc, np.hypot(dr, dc)) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc]
    while heap:
        d, (r, c) = heapq.heappop(heap)
        if (r, c) == end:
            break
        if d > dist[r, c]:
            continue
        for dr, dc, w in steps:
            rr, cc = r + dr, c + dc
            if 0 <= rr < H and 0 <= cc < W and np.isfinite(cost[rr, cc]):
                nd = d + w * 0.5 * (cost[r, c] + cost[rr, cc])
                if nd < dist[rr, cc]:
                    dist[rr, cc] = nd
                    prev[rr, cc] = (r, c)
                    heapq.heappush(heap, (nd, (rr, cc)))
    path, node = [], end
    while node[0] >= 0:
        path.append(node)
        if node == start:
            break
        node = tuple(prev[node])
    return path[::-1] if path[-1] == start else []
