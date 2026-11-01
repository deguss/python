#!/usr/bin/env python3
"""
Daily spectra + time series for ELA11C data.

Expected layout:
    DATA_ROOT/YYYYMMDD/YYYYMMDDHHmm.dat      (5-minute files, name = start time)

Outputs (in OUTPUT_DIR, default: the folder of this script):
    YYYYMMDD_spectra.png      Bx and By: dynamic spectrum + day-averaged spectrum
    YYYYMMDD_timeseries.png   Bx and By: decimated (min/max envelope) time series

Processing is done file by file, so memory use stays small (one 5-min file at a time).
"""
import os
import re
import sys
import io
import contextlib

import numpy as np
import matplotlib
matplotlib.use('Agg')                      # no GUI needed, just save PNGs
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.gridspec import GridSpec
from scipy import signal

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from ELA11C_ADCread import ela11c_adc_read
from Calibrate_HYL import calibrate_hyl

# =============================================================================
#                              CONFIGURATION
# =============================================================================

# ---- Input / output ---------------------------------------------------------
DATA_ROOT   = 'test_backyard'   # folder containing the YYYYMMDD directories
OUTPUT_DIR  = DATA_ROOT        # where the PNGs are saved
DAYS        = None              # None = all days found, or e.g. ['20261024', '20261025']
SKIP_EXISTING = False           # True: skip a day if both PNGs already exist

FS            = 3000.0          # sampling frequency [Hz]
FILE_LEN_SEC  = 300.0           # nominal file length [s] (used for gap detection)
MIN_FILE_SEC  = 10.0            # files shorter than this are ignored

# ---- Pre-processing ---------------------------------------------------------
REMOVE_DC     = True            # the calibrated ADC data has a large offset (mid-scale);
                                # offset = mean of the first valid file of the day

# ---- Filtering (applied to BOTH spectra and time series) --------------------
# Filter state is carried over between consecutive files (no edge transients
# at the 5-minute boundaries); it is reset after a gap in the data.
HP_ENABLE        = False         # high-pass (removes drift / residual DC)
#HP_CUTOFF_HZ     = 0.5          # [Hz]
#HP_ORDER         = 2            # Butterworth order

LP_ENABLE        = True         # low-pass
LP_CUTOFF_HZ     = 25.0         # -3 dB corner [Hz]
LP_ORDER         = 8            # Butterworth order (higher = steeper)

NOTCH_ENABLE     = False         # mains hum removal
#NOTCH_FREQ_HZ    = 50.0         # fundamental of the mains hum [Hz]
#NOTCH_N_HARMONICS = 3           # 3 -> 50, 100, 150 Hz
#NOTCH_BW_HZ      = 1.0          # -3 dB width of each notch [Hz] (narrower = less
                                # damage to nearby signal, but needs stable mains frequency)

# ---- Spectral estimation ----------------------------------------------------
NFFT          = 2**14           # FFT size [samples]  -> df = FS/NFFT = 0.183 Hz
OVERLAP       = 0.5             # segment overlap, 0 ... <1
WINDOW        = 'hann'          # any scipy.signal window name
DETREND       = 'constant'      # 'constant', 'linear' or False
FMIN          = 1.0             # plotted frequency range [Hz]
FMAX          = 25.0
SPEC_AVG_SEC  = 60.0            # time resolution of the dynamic spectrum [s]
                                # (PSD segments are averaged within these bins)

# ---- Spectra figure ---------------------------------------------------------
SPEC_FREQ_LOG = False           # log frequency axis for the dynamic spectrum
SPEC_CMAP     = 'viridis'
SPEC_CLIM     = None            # None = auto (percentiles below) or (vmin, vmax)
                                # in pT/sqrt(Hz), e.g. (1e-3, 1e0)
SPEC_CLIM_PCT = (5, 99.5)       # percentiles used for the auto color range
SPEC_FIGSIZE  = (16, 9)
SPEC_DPI      = 120

# ---- Time series figure -----------------------------------------------------
TS_MAX_POINTS = 20000           # max. plotted points per channel and day
                                # (min/max envelope per time bin, so peaks are preserved)
TS_FIGSIZE    = (16, 6)
TS_DPI        = 120

# =============================================================================
#                              IMPLEMENTATION
# =============================================================================
DAY_SEC = 86400.0
FILE_RE = re.compile(r'^(\d{8})(\d{2})(\d{2})\.dat$', re.IGNORECASE)
DAY_RE = re.compile(r'^\d{8}$')
CHANNELS = ('Bx', 'By')


def design_filter():
    """Cascade of second-order sections: optional high-pass + notches."""
    sections = []
    if HP_ENABLE:
        sections.append(signal.butter(HP_ORDER, HP_CUTOFF_HZ, btype='highpass',
                                      fs=FS, output='sos'))
    if LP_ENABLE:
        sections.append(signal.butter(LP_ORDER, LP_CUTOFF_HZ, btype='lowpass',
                                      fs=FS, output='sos'))        
    if NOTCH_ENABLE:
        for k in range(1, NOTCH_N_HARMONICS + 1):
            f0 = NOTCH_FREQ_HZ * k
            if f0 >= FS / 2:
                break
            q = f0 / NOTCH_BW_HZ                      # constant bandwidth for all notches
            b, a = signal.iirnotch(f0, q, fs=FS)
            sections.append(signal.tf2sos(b, a))
    return np.vstack(sections) if sections else None


def apply_filter(sos, x, zi):
    if sos is None:
        return x, None
    if zi is None:
        zi = signal.sosfilt_zi(sos) * x[0]
    y, zf = signal.sosfilt(sos, x, zi=zi)
    return y, zf


def list_days(root):
    days = sorted(d for d in os.listdir(root)
                  if DAY_RE.match(d) and os.path.isdir(os.path.join(root, d)))
    if DAYS is not None:
        days = [d for d in days if d in set(DAYS)]
    return days


def list_files(day_dir):
    """Return [(start_second_of_day, path), ...] sorted by time."""
    out = []
    for name in os.listdir(day_dir):
        m = FILE_RE.match(name)
        if m:
            sec = int(m.group(2)) * 3600 + int(m.group(3)) * 60
            out.append((sec, os.path.join(day_dir, name)))
    return sorted(out)


def read_file(path):
    """Read + calibrate one file -> (Bx, By) in pT as float64 arrays, or None."""
    try:
        with contextlib.redirect_stdout(io.StringIO()):     # silence the reader's print
            bx, by, nr, _ = ela11c_adc_read(path)
            bx, by = calibrate_hyl(bx, by)
    except Exception as exc:
        print(f'    ! cannot read {os.path.basename(path)}: {exc}')
        return None
    if nr < MIN_FILE_SEC * FS:
        print(f'    ! {os.path.basename(path)} too short ({nr} samples), skipped')
        return None
    return np.asarray(bx, dtype=np.float64), np.asarray(by, dtype=np.float64)


def process_day(day, day_dir):
    files = list_files(day_dir)
    if not files:
        print(f'  no data files in {day_dir}')
        return None

    sos = design_filter()
    nperseg = int(NFFT)
    noverlap = int(round(NFFT * OVERLAP))
    f_all = np.fft.rfftfreq(nperseg, 1.0 / FS)
    fmask = (f_all >= FMIN) & (f_all <= FMAX)
    f_sel = f_all[fmask]
    n_tbins = int(np.ceil(DAY_SEC / SPEC_AVG_SEC))

    # time series bin size (min/max envelope)
    ts_bin_sec = DAY_SEC / max(TS_MAX_POINTS // 2, 1)
    ts_nb = max(int(round(ts_bin_sec * FS)), 1)

    acc = {ch: dict(S=np.zeros((n_tbins, f_sel.size)), n=np.zeros(n_tbins),
                    zi=None, offset=None, tc=[], mn=[], mx=[]) for ch in CHANNELS}
    prev_t0 = None
    n_ok = 0

    for t0, path in files:
        data = read_file(path)
        if data is None:
            prev_t0 = None
            continue
        contiguous = prev_t0 is not None and abs((t0 - prev_t0) - FILE_LEN_SEC) < 2.0
        prev_t0 = t0
        n_ok += 1

        for ch, x in zip(CHANNELS, data):
            a = acc[ch]
            if REMOVE_DC:
                if a['offset'] is None:
                    a['offset'] = float(np.mean(x))
                x = x - a['offset']
            if not contiguous:
                a['zi'] = None                     # reset filter state after a gap
                if a['tc']:                        # break the line in the time series plot
                    a['tc'].append(np.array([np.nan]))
                    a['mn'].append(np.array([np.nan]))
                    a['mx'].append(np.array([np.nan]))
            x, a['zi'] = apply_filter(sos, x, a['zi'])

            # ---- spectrogram of this file, accumulated into time bins ----
            if x.size >= nperseg:
                _, t, S = signal.spectrogram(
                    x, fs=FS, window=WINDOW, nperseg=nperseg, noverlap=noverlap,
                    nfft=nperseg, detrend=DETREND, scaling='density', mode='psd')
                S = S[fmask, :]
                idx = np.clip(((t0 + t) // SPEC_AVG_SEC).astype(int), 0, n_tbins - 1)
                np.add.at(a['S'], idx, S.T)
                np.add.at(a['n'], idx, 1.0)

            # ---- min/max envelope for the time series ----
            nbins = x.size // ts_nb
            if nbins > 0:
                seg = x[:nbins * ts_nb].reshape(nbins, ts_nb)
                a['mn'].append(seg.min(axis=1))
                a['mx'].append(seg.max(axis=1))
                a['tc'].append((t0 + (np.arange(nbins) + 0.5) * ts_nb / FS) / 3600.0)

    if n_ok == 0:
        return None
    print(f'  {n_ok}/{len(files)} files processed')
    return f_sel, acc


# ---------------------------------------------------------------------------
#                                 plotting
# ---------------------------------------------------------------------------
def plot_spectra(day, f_sel, acc, outpath):
    fig = plt.figure(figsize=SPEC_FIGSIZE)
    gs = GridSpec(2, 2, width_ratios=[5, 1], wspace=0.04, hspace=0.25, figure=fig)
    t_centers = (np.arange(acc['Bx']['n'].size) + 0.5) * SPEC_AVG_SEC / 3600.0

    for row, ch in enumerate(CHANNELS):
        a = acc[ch]
        with np.errstate(invalid='ignore', divide='ignore'):
            asd = np.sqrt(a['S'] / a['n'][:, None])               # [pT/sqrt(Hz)], NaN where no data
            mean_asd = np.sqrt(a['S'].sum(axis=0) / a['n'].sum()) if a['n'].sum() else np.full(f_sel.size, np.nan)
        asd = np.ma.masked_invalid(asd)

        if SPEC_CLIM is not None:
            vmin, vmax = SPEC_CLIM
        else:
            vals = asd.compressed()
            vals = vals[vals > 0]
            if vals.size:
                vmin, vmax = np.percentile(vals, SPEC_CLIM_PCT)
            else:
                vmin, vmax = 1e-3, 1.0

        ax = fig.add_subplot(gs[row, 0])
        pm = ax.pcolormesh(t_centers, f_sel, asd.T, shading='auto', cmap=SPEC_CMAP,
                           norm=LogNorm(vmin=vmin, vmax=vmax), rasterized=True)
        ax.set_xlim(0, 24)
        ax.set_xticks(range(0, 25, 2))
        ax.set_ylim(FMIN, FMAX)
        if SPEC_FREQ_LOG:
            ax.set_yscale('log')
        ax.set_ylabel('Frequency (Hz)')
        ax.set_title(f'{ch}', loc='left', fontsize=11)
        if row == 1:
            ax.set_xlabel('Time (UTC hours)')
        else:
            ax.tick_params(labelbottom=False)
        cb = fig.colorbar(pm, ax=ax, pad=0.01, fraction=0.04)
        cb.set_label('ASD (pT/√Hz)')

        axm = fig.add_subplot(gs[row, 1], sharey=ax)
        axm.plot(mean_asd, f_sel, color='k', lw=0.8)
        axm.set_xscale('log')
        axm.grid(True, which='both', alpha=0.3)
        axm.tick_params(labelleft=False)
        axm.set_title('day mean', fontsize=9)
        if row == 1:
            axm.set_xlabel('ASD (pT/√Hz)')

    notch = (f'notch {NOTCH_FREQ_HZ:g} Hz x{NOTCH_N_HARMONICS} (BW {NOTCH_BW_HZ:g} Hz)'
             if NOTCH_ENABLE else 'no notch')
    hp = f'HP {HP_CUTOFF_HZ:g} Hz' if HP_ENABLE else 'no HP'
    fig.suptitle(f'{day[:4]}-{day[4:6]}-{day[6:]}   NFFT={NFFT} (df={FS / NFFT:.3f} Hz), '
                 f'overlap={OVERLAP:g}, {WINDOW}, {SPEC_AVG_SEC:g} s bins, {hp}, {notch}',
                 fontsize=10)
    fig.savefig(outpath, dpi=SPEC_DPI, bbox_inches='tight')
    plt.close(fig)


def plot_timeseries(day, acc, outpath):
    fig, axes = plt.subplots(2, 1, figsize=TS_FIGSIZE, sharex=True)
    colors = {'Bx': 'navy', 'By': 'darkred'}
    for ax, ch in zip(axes, CHANNELS):
        a = acc[ch]
        if a['tc']:
            tc = np.concatenate(a['tc'])
            mn = np.concatenate(a['mn'])
            mx = np.concatenate(a['mx'])
            ax.fill_between(tc, mn, mx, color=colors[ch], alpha=0.35, linewidth=0)
            ax.plot(tc, mn, color=colors[ch], lw=0.4)
            ax.plot(tc, mx, color=colors[ch], lw=0.4)
        ax.set_ylabel(f'{ch} (pT)')
        ax.grid(True, alpha=0.3)
    axes[-1].set_xlim(0, 24)
    axes[-1].set_xticks(range(0, 25, 2))
    axes[-1].set_xlabel('Time (UTC hours)')
    axes[0].set_title(f'{day[:4]}-{day[4:6]}-{day[6:]}  filtered time series '
                      f'(min/max envelope, ≤{TS_MAX_POINTS} points/channel)')
    fig.tight_layout()
    fig.savefig(outpath, dpi=TS_DPI)
    plt.close(fig)


# ---------------------------------------------------------------------------
def main():
    root = DATA_ROOT if os.path.isabs(DATA_ROOT) else os.path.join(SCRIPT_DIR, DATA_ROOT)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    days = list_days(root)
    if not days:
        print(f'No YYYYMMDD directories found in {root}')
        return

    for day in days:
        spec_png = os.path.join(OUTPUT_DIR, f'{day}_spectra.png')
        ts_png = os.path.join(OUTPUT_DIR, f'{day}_timeseries.png')
        if SKIP_EXISTING and os.path.exists(spec_png) and os.path.exists(ts_png):
            print(f'{day}: already done, skipped')
            continue
        print(f'{day}:')
        res = process_day(day, os.path.join(root, day))
        if res is None:
            continue
        f_sel, acc = res
        plot_spectra(day, f_sel, acc, spec_png)
        plot_timeseries(day, acc, ts_png)
        print(f'  saved {os.path.basename(spec_png)}, {os.path.basename(ts_png)}')


if __name__ == '__main__':
    main()
