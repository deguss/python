"""
Terrain (2D hillshade + contours, 3D surface) and wind rose around the Lodi site.
Run locally (needs internet):
    pip install numpy requests pillow matplotlib
    python lodi_terrain_wind.py
Elevation: AWS "Terrarium" tiles (global DEM, ~50 m at this zoom).
Wind: Open-Meteo archive (ERA5-based, hourly 10 m wind) for the chosen period.
"""
import io, math
import numpy as np
import requests
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource

# ---- settings ---------------------------------------------------------
LAT, LON = 45 + 13/60 + 55.4/3600, 9 + 25/60 + 50.0/3600   # 45.2321 N, 9.4306 E
HALF_KM = 150            # half-width of the map; 15 -> 30 km across, set 30 for 60 km
ZOOM = 11               # 11 ~ 55 m/px here; 10 is coarser/faster
START, END = "2026-07-23", "2026-08-03"   # wind period
# -----------------------------------------------------------------------

def deg2tile(lat, lon, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y

def tile2deg(x, y, z):
    n = 2 ** z
    lon = x / n * 360 - 180
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lat, lon

dlat = HALF_KM / 111.32
dlon = HALF_KM / (111.32 * math.cos(math.radians(LAT)))
x0, y1 = deg2tile(LAT - dlat, LON - dlon, ZOOM)
x1, y0 = deg2tile(LAT + dlat, LON + dlon, ZOOM)
tx0, tx1, ty0, ty1 = int(x0), int(x1), int(y0), int(y1)

rows = []
for ty in range(ty0, ty1 + 1):
    row = []
    for tx in range(tx0, tx1 + 1):
        url = f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{ZOOM}/{tx}/{ty}.png"
        r = requests.get(url, timeout=30); r.raise_for_status()
        a = np.asarray(Image.open(io.BytesIO(r.content)).convert("RGB"), dtype=float)
        row.append(a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768)
    rows.append(np.hstack(row))
dem_full = np.vstack(rows)

# crop to requested box
px0 = int(round((x0 - tx0) * 256)); px1 = int(round((x1 - tx0) * 256))
py0 = int(round((y0 - ty0) * 256)); py1 = int(round((y1 - ty0) * 256))
dem = dem_full[py0:py1, px0:px1]
ny, nx = dem.shape
xs = np.linspace(-HALF_KM, HALF_KM, nx)          # km east of centre
ys = np.linspace(HALF_KM, -HALF_KM, ny)          # km north of centre
X, Y = np.meshgrid(xs, ys)

# ---- wind -------------------------------------------------------------
w = requests.get("https://archive-api.open-meteo.com/v1/archive", timeout=60, params=dict(
    latitude=LAT, longitude=LON, start_date=START, end_date=END,
    hourly="wind_speed_10m,wind_direction_10m,relative_humidity_2m",
    wind_speed_unit="kmh", timezone="UTC")).json()["hourly"]
spd = np.array(w["wind_speed_10m"], float)
dirn = np.array(w["wind_direction_10m"], float)      # direction wind comes FROM
ok = ~np.isnan(spd) & ~np.isnan(dirn)
spd, dirn = spd[ok], dirn[ok]
# vector-mean wind (direction it blows TOWARD, for the arrow)
u = -spd * np.sin(np.radians(dirn)); v = -spd * np.cos(np.radians(dirn))
um, vm = u.mean(), v.mean()
mean_from = (math.degrees(math.atan2(-um, -vm)) + 360) % 360

# ---- figure 1: 2D map + wind rose ------------------------------------
fig = plt.figure(figsize=(15, 7))
ax = fig.add_subplot(1, 2, 1)
ls = LightSource(azdeg=315, altdeg=40)
shade = ls.hillshade(dem, vert_exag=8, dx=55, dy=55)
ax.imshow(shade, cmap="gray", extent=[-HALF_KM, HALF_KM, -HALF_KM, HALF_KM])
im = ax.imshow(dem, cmap="terrain", alpha=0.55, extent=[-HALF_KM, HALF_KM, -HALF_KM, HALF_KM])
cs = ax.contour(X, Y, dem, levels=np.arange(0, 400, 10), colors="k", linewidths=0.3)
ax.plot(0, 0, "r*", ms=16, label="site")
scale = HALF_KM * 0.5 / max(np.hypot(um, vm), 1e-6)
ax.annotate("", xy=(um * scale, vm * scale), xytext=(0, 0),
            arrowprops=dict(arrowstyle="->", lw=3, color="blue"))
ax.set_title(f"Terrain (m), site marked; blue arrow = mean 10 m wind {START}..{END}\n"
             f"(mean from {mean_from:.0f} deg, vector-mean {np.hypot(um, vm):.1f} km/h)")
ax.set_xlabel("km east"); ax.set_ylabel("km north"); ax.legend(loc="upper right")
plt.colorbar(im, ax=ax, shrink=0.7, label="elevation m")

axr = fig.add_subplot(1, 2, 2, projection="polar")
axr.set_theta_zero_location("N"); axr.set_theta_direction(-1)
bins = np.arange(-11.25, 360, 22.5)
cnt, _ = np.histogram((dirn + 11.25) % 360 - 11.25, bins=bins)
axr.bar(np.radians(bins[:-1] + 11.25), cnt / cnt.sum() * 100, width=np.radians(20), color="steelblue")
axr.set_title(f"Wind rose (direction wind comes FROM, % of hours)\nmean speed {spd.mean():.1f} km/h, n={len(spd)} h", pad=20)
fig.tight_layout(); fig.savefig("lodi_2d_wind.png", dpi=150)

# ---- figure 2: 3D surface --------------------------------------------
step = max(1, nx // 150)
fig3 = plt.figure(figsize=(11, 8)); a3 = fig3.add_subplot(111, projection="3d")
a3.plot_surface(X[::step, ::step], Y[::step, ::step], dem[::step, ::step], cmap="terrain",
                linewidth=0, antialiased=True, rcount=150, ccount=150)
a3.set_box_aspect((1, 1, 0.15))                 # modest vertical exaggeration
a3.quiver(0, 0, dem.max() + 20, um * scale, vm * scale, 0, color="blue", linewidth=3)
a3.scatter([0], [0], [dem[ny // 2, nx // 2]], c="r", s=80)
a3.set_xlabel("km east"); a3.set_ylabel("km north"); a3.set_zlabel("m")
a3.set_title("3D terrain (vertical exaggeration applied), blue = mean wind")
fig3.savefig("lodi_3d.png", dpi=150)
print("saved lodi_2d_wind.png and lodi_3d.png; elevation range", dem.min(), dem.max())
