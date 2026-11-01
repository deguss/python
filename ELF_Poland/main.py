import numpy as np
import matplotlib.pyplot as plt

# Függvények importálása a helyi modulokból
from ELA11C_ADCread import ela11c_adc_read
from Calibrate_HYL import calibrate_hyl

# 1. Bemeneti paraméterek beállítása
filename = 'test_backyard/20261024/202610240000.dat'
fs = 3000.0  # Mintavételezési frekvencia (Hz)[cite: 2]

# Megjelenítési időtartam beállítása másodpercben a mérés kezdetétől számítva
t_start_sec = 0.0       # Kezdő időpont másodpercben (0 = a fájl eleje)
t_duration_sec = 10.0  # Megjelenítendő időablak hossza másodpercben (300 s = 5 perc)

# 2. Nyers adatok beolvasása a bináris állományból
Bx_raw, By_raw, nr, tini = ela11c_adc_read(filename)

# 3. Kalibráció (DAC értékek konvertálása pT mértékegységre)
Bx_pT, By_pT = calibrate_hyl(Bx_raw, By_raw)

# 4. Időtengely előállítása másodpercben
dt = 1.0 / fs
time_vector = tini + np.arange(nr) * dt

# 5. Szeletelés az időparaméterek alapján
idx_start = int(t_start_sec * fs)
idx_end = int((t_start_sec + t_duration_sec) * fs)
idx_end = min(idx_end, nr)  # Védelem a tömb túlindexelése ellen

t_plot = time_vector[idx_start:idx_end]
bx_plot = Bx_pT[idx_start:idx_end]
by_plot = By_pT[idx_start:idx_end]

# 6. Idősorok kirajzolása
fig, axes = plt.subplots(2, 1, figsize=(14, 6), sharex=True)

axes[0].plot(t_plot, bx_plot, color='navy', linewidth=0.5)
axes[0].set_title(f'Bx komponens ({t_start_sec:.1f} s – {t_start_sec + t_duration_sec:.1f} s)')
axes[0].set_ylabel('Bx (pT)')
axes[0].grid(True)

axes[1].plot(t_plot, by_plot, color='darkred', linewidth=0.5)
axes[1].set_title(f'By komponens ({t_start_sec:.1f} s – {t_start_sec + t_duration_sec:.1f} s)')
axes[1].set_xlabel('Idő (s)')
axes[1].set_ylabel('By (pT)')
axes[1].grid(True)

plt.tight_layout()
plt.show()
