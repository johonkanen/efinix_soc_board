"""2D quasi-static finite-difference field solver for trace impedance (single-ended and odd-mode differential).
Layers are listed bottom-up as (thickness_mm, er). Planes are Dirichlet 0 boundaries at given y. Energy method:
C = 2W/V^2 (single line); odd mode with +-1 V: W = C11 - |C12| = C_odd. Z = 1/(c*sqrt(C*C0))."""
import numpy as np, scipy.sparse as sp, scipy.sparse.linalg as spl
E0 = 8.854e-12; C = 299792458.0

def solve(stack, planes, traces, top_open, width=3.0, h=0.0025, er_air=1.0):
    """stack: list of (y0, y1, er) dielectric slabs (mm). planes: list of y (mm) of plane surfaces: the domain runs
    from planes[0] (bottom) to planes[-1] (top) or to y_top + air if top_open. traces: list of (x0, x1, y0, y1, V)."""
    ytop = max(s[1] for s in stack)
    y_max = ytop + (0.6 if top_open else 0.0)
    y_min = min(planes)
    ny = int(round((y_max - y_min) / h)) + 1; nx = int(round(width / h)) + 1
    ys = y_min + np.arange(ny) * h; xs = -width / 2 + np.arange(nx) * h
    # er at cell centres (ny-1, nx-1)
    yc = (ys[:-1] + ys[1:]) / 2
    er_c = np.full((ny - 1, nx - 1), er_air)
    xc = (xs[:-1] + xs[1:]) / 2
    for sl in stack:
        y0, y1, er = sl[:3]; x0, x1 = (sl[3], sl[4]) if len(sl) > 3 else (-1e9, 1e9)
        m = ((yc >= y0) & (yc < y1))[:, None] & ((xc >= x0) & (xc < x1))[None, :]; er_c[m] = er
    res = {}
    for label, use_er in (("diel", True), ("air", False)):
        e = er_c if use_er else np.ones_like(er_c)
        fixed = np.zeros((ny, nx), bool); val = np.zeros((ny, nx))
        for yp in planes:
            j = int(round((yp - y_min) / h)); fixed[j, :] = True
        if not top_open:
            fixed[-1, :] = True
        fixed[:, 0] = fixed[:, -1] = True   # side walls far away
        for x0, x1, y0, y1, V in traces:
            jm = (ys >= y0 - 1e-9) & (ys <= y1 + 1e-9); im = (xs >= x0 - 1e-9) & (xs <= x1 + 1e-9)
            fixed[np.ix_(jm, im)] = True; val[np.ix_(jm, im)] = V
        # node equation: sum over the 4 links of eps_link*(V_nb - V) = 0; eps_link = mean of the two adjacent cells
        def cell(j, i):
            j = min(max(j, 0), ny - 2); i = min(max(i, 0), nx - 2); return e[j, i]
        idx = -np.ones((ny, nx), int); free = ~fixed; idx[free] = np.arange(free.sum())
        rows, cols, data = [], [], []; b = np.zeros(free.sum())
        J, I = np.nonzero(free)
        for j, i in zip(J, I):
            k = idx[j, i]; diag = 0.0
            for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                jj, ii = j + dj, i + di
                if jj < 0 or jj >= ny:          # open top (Neumann): skip
                    continue
                if di:   # horizontal link between (j,i) and (j,i+di): cells (j-1, i') and (j, i'), i' = min(i, i+di)
                    ic = min(i, ii); w = (cell(j - 1, ic) + cell(j, ic)) / 2
                else:
                    jc = min(j, jj); w = (cell(jc, i - 1) + cell(jc, i)) / 2
                diag += w
                if fixed[jj, ii]:
                    b[k] += w * val[jj, ii]
                else:
                    rows.append(k); cols.append(idx[jj, ii]); data.append(-w)
            rows.append(k); cols.append(k); data.append(diag)
        A = sp.csr_matrix((data, (rows, cols)), shape=(free.sum(),) * 2)
        V = val.copy(); V[free] = spl.spsolve(A, b)
        # energy per unit length: 0.5*eps0*sum er |grad V|^2 over cells (V in volts, lengths in mm -> unitless ratio)
        gx = (V[:-1, 1:] - V[:-1, :-1] + V[1:, 1:] - V[1:, :-1]) / 2 / h
        gy = (V[1:, :-1] - V[:-1, :-1] + V[1:, 1:] - V[:-1, 1:]) / 2 / h
        W = 0.5 * E0 * np.sum(e * (gx ** 2 + gy ** 2)) * h * h   # J/m (mm units cancel: grad 1/mm^2 * area mm^2)
        res[label] = W
    return res

def z_se(**kw):
    r = solve(**kw); Cd, Ca = 2 * r["diel"], 2 * r["air"]
    return 1 / (C * np.sqrt(Cd * Ca)), Cd / Ca

def z_diff(**kw):
    r = solve(**kw); Cd, Ca = r["diel"], r["air"]
    return 2 / (C * np.sqrt(Cd * Ca)), Cd / Ca
