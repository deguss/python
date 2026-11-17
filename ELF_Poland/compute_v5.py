#!/usr/bin/env python3
"""
Daily spectra, time series and polarization for ELA11C data.

Expected layout:
    DATA_ROOT/YYYYMMDD/YYYYMMDDHHmm.dat      (5-minute files, name = start time)

Outputs (in OUTPUT_DIR, one subfolder per figure type):
    spectra/YYYYMMDD_spectra.png            Bx, By and total horizontal PSD: dynamic spectrum
                                            + day spectrum with peak markers
    timeseries/YYYYMMDD_timeseries.png      Bx and By: decimated (min/max envelope) time series
    polarization/YYYYMMDD_polarization.png  per spectral peak: source bearing vs time, band
                                            amplitude vs time, rose diagram
    schumann_heading/schumann_modeN_<f>Hz_heading.png
                                            source bearing + band ASD of Schumann mode N, all days
                                            overlaid, bold mean over the whole recording
    schumann_trace/YYYYMMDD_trace.png       peak frequency of modes 1-3 vs time of day, per day
    schumann_trace/period_overlay.png       peak frequency of modes 1-3, all days overlaid
    schumann_trace/period_trace.png         peak frequency of modes 1-3 over the entire registration

Processing is done file by file, so memory use stays small (one 5-min file at a time).

Polarization conventions
    Bx = north-south component (positive north), By = east-west component (positive east,
    see POL_BY_POSITIVE). For a distant source the horizontal B field is perpendicular to
    the propagation direction, so  bearing = (B-field axis angle) + 90 deg.
    With magnetic sensors only, the bearing is ambiguous by 180 deg (theta and theta+180
    cannot be told apart), therefore the rose diagram is symmetric by construction.
"""
import os
import re
import sys
import io
import contextlib
import warnings
from datetime import datetime, timedelta

import numpy as np
import matplotlib
matplotlib.use('Agg')                      # no GUI needed, just save PNGs
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.lines import Line2D
from matplotlib.colors import LogNorm
from matplotlib.gridspec import GridSpec
from numpy.lib.stride_tricks import sliding_window_view
from scipy import signal
from scipy.signal import find_peaks
from scipy.optimize import curve_fit

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from ELA11C_ADCread import ela11c_adc_read
from Calibrate_HYL import calibrate_hyl

# =============================================================================
#                              CONFIGURATION
# =============================================================================

# ---- Input / output ---------------------------------------------------------
DATA_ROOT   = 'egzotakert'   # folder containing the YYYYMMDD directories
OUTPUT_DIR  = DATA_ROOT         # base output folder (relative paths are taken relative
                                # to the folder of this script)
SUBDIR_SPECTRA      = 'spectra'
SUBDIR_TIMESERIES   = 'timeseries'
SUBDIR_POLARIZATION = 'polarization'
DAYS        = None              # None = all days found, or e.g. ['20261024', '20261025']
SKIP_EXISTING = False           # True: skip a day if all its PNGs already exist

FS            = 3000.0          # sampling frequency [Hz]
FILE_LEN_SEC  = 300.0           # nominal file length [s] (used for gap detection)
MIN_FILE_SEC  = 10.0            # files shorter than this are ignored

# ---- Pre-processing ---------------------------------------------------------
REMOVE_DC     = True            # the calibrated ADC data has a large offset (mid-scale);
                                # offset = mean of the first valid file of the day

# ---- Filtering (applied to spectra, time series and polarization) -----------
# Filter state is carried over between consecutive files (no edge transients
# at the 5-minute boundaries); it is reset after a gap in the data.
# NOTE: both channels get the identical filter, so the phase/angle relation is kept.
HP_ENABLE        = False        # high-pass (removes drift / residual DC)
HP_CUTOFF_HZ     = 0.5          # [Hz]
HP_ORDER         = 2            # Butterworth order

LP_ENABLE        = True         # low-pass
LP_CUTOFF_HZ     = 25.0         # -3 dB corner [Hz]
LP_ORDER         = 8            # Butterworth order (higher = steeper)

NOTCH_ENABLE     = False        # mains hum removal
NOTCH_FREQ_HZ    = 50.0         # fundamental of the mains hum [Hz]
NOTCH_N_HARMONICS = 3           # 3 -> 50, 100, 150 Hz
NOTCH_BW_HZ      = 1.0          # -3 dB width of each notch [Hz]

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
SPEC_CLIM     = None            # None = auto, COMMON to Bx, By and total (percentiles below),
                                # or (vmin, vmax) in pT/sqrt(Hz), e.g. (1e-1, 1e1)
SPEC_CLIM_PCT = (5, 99.5)       # percentiles used for the auto color range
SPEC_WIDTH_RATIOS = (4, 1.4)    # width of dynamic spectrum : day-spectrum panel
SPEC_FIGSIZE  = (16, 12)
SPEC_DPI      = 120

# ---- Day-spectrum (right-hand ASD panel) ------------------------------------
ASD_STAT      = 'mean'          # 'mean'   = sqrt(mean PSD), dominated by strong bursts
                                # 'median' = median of the 1-min ASDs, robust background
ASD_XLIM      = None            # None = auto, identical for all panels; or (lo, hi) in pT/sqrt(Hz)

# ---- Peak markers on the day spectrum ---------------------------------------
PEAK_ENABLE       = True
PEAK_N            = 3           # number of peaks marked per panel
PEAK_FMIN         = 5.0         # search range for peaks [Hz]
PEAK_FMAX         = 25.0
PEAK_MIN_SEP_HZ   = 3.0         # minimum distance between two marked peaks [Hz]
PEAK_MIN_WIDTH_HZ = 0.0         # 0 = any peak; ~1.0 ignores narrow interference lines
                                # and favours broad resonances (Schumann modes)
PEAK_RANK         = 'prominence'  # 'prominence' or 'height'
PEAK_LABEL        = 'legend'    # 'legend', 'text' (next to marker) or 'both'
PEAK_COLORS       = ('red', 'orange', 'magenta')
PEAK_MARK_SPEC    = True        # also draw small triangles at the left edge of the
                                # dynamic spectra at the peak frequencies

# ---- Polarization / direction figure ----------------------------------------
POL_ENABLE    = True
POL_FREQS     = None            # None = use the peaks of the TOTAL HORIZONTAL day spectrum,
                                # or a list of centre frequencies, e.g. [7.8, 14.1, 20.3]
POL_BAND_HZ   = 1.0             # width of the analysis band around each frequency [Hz]
POL_AVG_SEC   = 300.0           # averaging time of one direction estimate [s]
                                # (rounded to a multiple of SPEC_AVG_SEC)
POL_MIN_DOP   = 0.2             # use only estimates with degree of polarization >= this (0...1)
POL_WEIGHT    = 'none'          # rose weighting: 'none' (each estimate counts once) or 'power'
POL_ROSE_BINS = 36              # bins on the full 360 deg rose (36 -> 10 deg)
POL_BY_POSITIVE = 'east'        # 'east' or 'west': which way By is positive (check your coil!)
POL_AZIMUTH_OFFSET_DEG = 0.0    # added to the bearing, e.g. magnetic declination if the coils
                                # were aligned to magnetic north, or a known coil rotation
POL_FIGSIZE   = (16, 11)
POL_DPI       = 120

# ---- Schumann resonance analysis (heading + peak tracking) ------------------
SR_ENABLE        = True
SR_MODES_HZ      = (7.8, 14.1, 20.3)     # nominal frequencies of the first 3 Schumann modes
SR_SEARCH_HZ     = ((6.3, 9.3), (12.3, 15.8), (18.3, 22.3))   # peak search / fit window per mode
SR_BAND_HZ       = 2.0                   # width of the band around each nominal frequency used
                                         # for bearing and band ASD [Hz]
SR_LINE_MASK     = ((16.67, 0.4),)   # (centre, half-width) [Hz] of man-made lines that
                                         # are cut out of ALL Schumann analyses; () = none.
                                         # half-width >= 0.4 Hz is needed because of the
                                         # leakage of the Hann window (+-2 bins = +-0.37 Hz)
SR_CORRECT_FILTER = True                 # divide PSD by the filter's |H(f)|^2 (compensates the
                                         # low-pass slope near 20 Hz)
SR_AVG_SEC       = 300.0                 # one bearing / band-ASD estimate every ... [s]
SR_MIN_DOP       = 0.2                   # bearing estimates need a degree of polarization >= this
SR_MEAN_BIN_SEC  = 1800.0                # time resolution of the multi-day mean curves [s]
SR_MEAN_STAT     = 'mean'                # band-ASD average over days: 'mean' or 'median'
SR_TRACK_SEC     = 3600.0                # one peak-frequency estimate every ... [s]
SR_TRACK_STAT    = 'median'              # spectrum used for the fit: 'median' (robust against
                                         # lightning bursts) or 'mean' of the 1-min PSDs
SR_TRACK_MIN_BINS = 10                   # minimum number of 1-min PSDs for one estimate
SR_PEAK_METHOD   = 'lorentz'             # 'lorentz' (Lorentzian + linear background) or 'max'
SUBDIR_SR_HEADING = 'schumann_heading'
SUBDIR_SR_TRACE   = 'schumann_trace'
SUBDIR_SR_CACHE   = 'schumann_cache'     # small .npz per day, used for the multi-day plots
SR_HEADING_FIGSIZE = (15, 9)
SR_TRACE_FIGSIZE   = (18, 5.5)
SR_DPI             = 120

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
ROWS = ('Bx', 'By', 'H')                       # rows of the spectra figure
ROW_TITLES = {'Bx': 'Bx (N–S)', 'By': 'By (E–W)',
              'H': 'Total horizontal  √(Sxx + Syy)'}


def design_filter():
    """Cascade of second-order sections: optional high-pass + low-pass + notches."""
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


def filter_description():
    parts = []
    if HP_ENABLE:
        parts.append(f'HP {HP_CUTOFF_HZ:g} Hz (n={HP_ORDER})')
    if LP_ENABLE:
        parts.append(f'LP {LP_CUTOFF_HZ:g} Hz (n={LP_ORDER})')
    if NOTCH_ENABLE:
        parts.append(f'notch {NOTCH_FREQ_HZ:g} Hz x{NOTCH_N_HARMONICS} (BW {NOTCH_BW_HZ:g} Hz)')
    return ', '.join(parts) if parts else 'no filter'


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
    hop = max(nperseg - int(round(NFFT * OVERLAP)), 1)
    win = signal.get_window(WINDOW, nperseg)
    f_all = np.fft.rfftfreq(nperseg, 1.0 / FS)
    fmask = (f_all >= FMIN) & (f_all <= FMAX)
    f_sel = f_all[fmask]
    n_tbins = int(np.ceil(DAY_SEC / SPEC_AVG_SEC))

    # PSD scaling (density, one-sided) -- same normalisation as scipy.signal.spectrogram
    onesided = np.full(f_all.size, 2.0)
    onesided[0] = 1.0
    if nperseg % 2 == 0:
        onesided[-1] = 1.0
    fac = (onesided / (FS * np.sum(win ** 2)))[fmask]

    # |H(f)|^2 of the pre-filter (used to compensate its slope in the Schumann analysis)
    if sos is not None:
        _, h = signal.sosfreqz(sos, worN=f_sel, fs=FS)
        resp2 = np.abs(h) ** 2
    else:
        resp2 = np.ones(f_sel.size)

    def seg_fft(x):
        """Detrended + windowed segment FFTs (only the selected bins) and segment times."""
        v = sliding_window_view(x, nperseg)[::hop]
        if DETREND in ('constant', 'linear'):
            v = signal.detrend(v, type=DETREND, axis=1)
        Z = np.fft.rfft(v * win, axis=1)[:, fmask]
        t = (np.arange(v.shape[0]) * hop + nperseg / 2) / FS
        return Z, t

    # time series bin size (min/max envelope)
    ts_bin_sec = DAY_SEC / max(TS_MAX_POINTS // 2, 1)
    ts_nb = max(int(round(ts_bin_sec * FS)), 1)

    acc = {ch: dict(S=np.zeros((n_tbins, f_sel.size)), n=np.zeros(n_tbins),
                    zi=None, offset=None, tc=[], mn=[], mx=[]) for ch in CHANNELS}
    acc['Sxy'] = np.zeros((n_tbins, f_sel.size), dtype=complex)    # cross-spectrum sum
    acc['resp2'] = resp2
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

        xs = {}
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
            xs[ch] = x

            # ---- min/max envelope for the time series ----
            nbins = x.size // ts_nb
            if nbins > 0:
                seg = x[:nbins * ts_nb].reshape(nbins, ts_nb)
                a['mn'].append(seg.min(axis=1))
                a['mx'].append(seg.max(axis=1))
                a['tc'].append((t0 + (np.arange(nbins) + 0.5) * ts_nb / FS) / 3600.0)

        # ---- segment FFTs of both channels -> PSDs and cross-spectrum, binned in time ----
        nmin = min(xs['Bx'].size, xs['By'].size)
        if nmin >= nperseg:
            Zx, tseg = seg_fft(xs['Bx'][:nmin])
            Zy, _ = seg_fft(xs['By'][:nmin])
            idx = np.clip(((t0 + tseg) // SPEC_AVG_SEC).astype(int), 0, n_tbins - 1)
            np.add.at(acc['Bx']['S'], idx, fac * np.abs(Zx) ** 2)
            np.add.at(acc['By']['S'], idx, fac * np.abs(Zy) ** 2)
            np.add.at(acc['Sxy'], idx, fac * np.conj(Zx) * Zy)
            np.add.at(acc['Bx']['n'], idx, 1.0)
            np.add.at(acc['By']['n'], idx, 1.0)

    if n_ok == 0:
        return None
    print(f'  {n_ok}/{len(files)} files processed')
    return f_sel, acc


# ---------------------------------------------------------------------------
#                    day spectra and peak detection
# ---------------------------------------------------------------------------
def find_asd_peaks(f, asd):
    """Top PEAK_N peaks of a spectrum within [PEAK_FMIN, PEAK_FMAX].
    Returns [(f_peak, amplitude), ...] sorted by frequency. The peak frequency is
    refined by parabolic interpolation of the log-spectrum (sub-bin accuracy)."""
    if not PEAK_ENABLE or f.size < 5 or not np.any(np.isfinite(asd)):
        return []
    a = np.nan_to_num(np.asarray(asd, dtype=float), nan=0.0)
    df = f[1] - f[0]
    idx = np.where((f >= PEAK_FMIN) & (f <= PEAK_FMAX))[0]
    if idx.size < 3:
        return []
    sub = a[idx]
    kw = dict(distance=max(int(round(PEAK_MIN_SEP_HZ / df)), 1), prominence=0)
    if PEAK_MIN_WIDTH_HZ > 0:
        kw['width'] = PEAK_MIN_WIDTH_HZ / df
    pk, props = find_peaks(sub, **kw)
    if pk.size == 0:
        return []
    key = props['prominences'] if PEAK_RANK == 'prominence' else sub[pk]
    pk = np.sort(pk[np.argsort(key)[::-1][:PEAK_N]])
    out = []
    for j in pk:
        i = idx[j]
        la, lb, lc = np.log(np.maximum(a[[i - 1, i, i + 1]], 1e-30))
        denom = la - 2 * lb + lc
        off = float(np.clip(0.5 * (la - lc) / denom, -0.5, 0.5)) if denom < 0 else 0.0
        out.append((f[i] + off * df, float(np.exp(lb - 0.25 * (la - lc) * off))))
    return out


def compute_spectra(f_sel, acc):
    """ASD(t, f), day spectrum and peaks for Bx, By and total horizontal 'H'."""
    S = {'Bx': acc['Bx']['S'], 'By': acc['By']['S']}
    S['H'] = S['Bx'] + S['By']
    n = acc['Bx']['n']
    sp = dict(asd={}, day={}, peaks={})
    for key in ROWS:
        with np.errstate(invalid='ignore', divide='ignore'), warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)
            raw = np.sqrt(S[key] / n[:, None])                # [pT/sqrt(Hz)], NaN where no data
            if ASD_STAT == 'median':
                day = np.nanmedian(raw, axis=0)
            elif n.sum() > 0:
                day = np.sqrt(S[key].sum(axis=0) / n.sum())
            else:
                day = np.full(f_sel.size, np.nan)
        sp['asd'][key] = np.ma.masked_invalid(raw)
        sp['day'][key] = day
        sp['peaks'][key] = find_asd_peaks(f_sel, day)
    return sp


# ---------------------------------------------------------------------------
#                                 plotting
# ---------------------------------------------------------------------------
def plot_spectra(day, f_sel, acc, sp, outpath):
    t_centers = (np.arange(acc['Bx']['n'].size) + 0.5) * SPEC_AVG_SEC / 3600.0

    # common colour range for all dynamic spectra
    if SPEC_CLIM is not None:
        vmin, vmax = SPEC_CLIM
    else:
        vals = np.concatenate([sp['asd'][k].compressed() for k in ROWS])
        vals = vals[vals > 0]
        vmin, vmax = np.percentile(vals, SPEC_CLIM_PCT) if vals.size else (1e-3, 1.0)

    # common x-range for all day-spectrum panels
    if ASD_XLIM is not None:
        xlim = ASD_XLIM
    else:
        v = np.concatenate([sp['day'][k][np.isfinite(sp['day'][k]) & (sp['day'][k] > 0)]
                            for k in ROWS])
        xlim = (v.min() / 1.5, v.max() * 1.5) if v.size else (1e-2, 1e2)

    fig = plt.figure(figsize=SPEC_FIGSIZE)
    nrow = len(ROWS)
    gs = GridSpec(nrow, 2, width_ratios=list(SPEC_WIDTH_RATIOS), wspace=0.16, hspace=0.25,
                  figure=fig)
    axm_first = None

    for row, key in enumerate(ROWS):
        ax = fig.add_subplot(gs[row, 0])
        pm = ax.pcolormesh(t_centers, f_sel, sp['asd'][key].T, shading='auto',
                           cmap=SPEC_CMAP, norm=LogNorm(vmin=vmin, vmax=vmax),
                           rasterized=True)
        ax.set_xlim(0, 24)
        ax.set_xticks(range(0, 25, 2))
        ax.set_ylim(FMIN, FMAX)
        if SPEC_FREQ_LOG:
            ax.set_yscale('log')
        ax.set_ylabel('Frequency (Hz)')
        ax.set_title(ROW_TITLES[key], loc='left', fontsize=11)
        if row == nrow - 1:
            ax.set_xlabel('Time (UTC hours)')
        else:
            ax.tick_params(labelbottom=False)
        cb = fig.colorbar(pm, ax=ax, pad=0.01, fraction=0.04)
        cb.set_label('ASD (pT/√Hz)')

        axm = fig.add_subplot(gs[row, 1], sharey=ax, sharex=axm_first)
        if axm_first is None:
            axm_first = axm
        axm.plot(sp['day'][key], f_sel, color='k', lw=0.8, zorder=2)
        axm.set_xscale('log')
        axm.set_xlim(xlim)
        # heavy grid on the decades (1, 10, 100, ...), light grid on the minor ticks
        axm.grid(True, which='major', axis='x', color='k', lw=1.3, alpha=0.75, zorder=0)
        axm.grid(True, which='minor', axis='x', color='gray', lw=0.4, alpha=0.4, zorder=0)
        axm.grid(True, which='major', axis='y', color='gray', lw=0.5, alpha=0.4, zorder=0)
        axm.tick_params(labelleft=False)
        axm.set_title(f'day {ASD_STAT}', fontsize=9)
        if row == nrow - 1:
            axm.set_xlabel('ASD (pT/√Hz)')

        # peak markers
        for k, (fp, ap) in enumerate(sp['peaks'][key]):
            col = PEAK_COLORS[k % len(PEAK_COLORS)]
            axm.plot(ap, fp, marker='o', ms=7, ls='none', color=col, mec='k', zorder=5,
                     label=f'{fp:.2f} Hz')
            if PEAK_LABEL in ('text', 'both'):
                axm.annotate(f'{fp:.2f} Hz', (ap, fp), xytext=(7, 0),
                             textcoords='offset points', va='center', fontsize=8,
                             color='k', zorder=6)
            if PEAK_MARK_SPEC:
                ax.plot(0.004, fp, marker='>', ms=8, color=col, mec='k', ls='none',
                        transform=ax.get_yaxis_transform(), clip_on=False, zorder=6)
        if sp['peaks'][key] and PEAK_LABEL in ('legend', 'both'):
            axm.legend(loc='upper right', fontsize=8, framealpha=0.9, title='peaks',
                       title_fontsize=8, handletextpad=0.3, borderpad=0.4)

    fig.suptitle(f'{day[:4]}-{day[4:6]}-{day[6:]}   NFFT={NFFT} (df={FS / NFFT:.3f} Hz), '
                 f'overlap={OVERLAP:g}, {WINDOW}, {SPEC_AVG_SEC:g} s bins, {filter_description()}',
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
    axes[0].set_title(f'{day[:4]}-{day[4:6]}-{day[6:]}  filtered time series, {filter_description()} '
                      f'(min/max envelope, ≤{TS_MAX_POINTS} points/channel)')
    fig.tight_layout()
    fig.savefig(outpath, dpi=TS_DPI)
    plt.close(fig)


# ---------------------------------------------------------------------------
#                           polarization / direction
# ---------------------------------------------------------------------------
def group_sum(v, k):
    """Sum consecutive groups of k rows (zero-padded at the end)."""
    ng = int(np.ceil(v.shape[0] / k))
    pad = ng * k - v.shape[0]
    if pad:
        v = np.concatenate([v, np.zeros((pad,) + v.shape[1:], dtype=v.dtype)])
    return v.reshape((ng, k) + v.shape[1:]).sum(axis=1)


def band_series(acc, bmask, avg_sec, resp2=None):
    """Bearing [deg, 0..180), degree of polarization, band ASD [pT/sqrt(Hz), total horizontal]
    in the frequency bins `bmask`, one estimate per avg_sec. If resp2 (|H|^2 of the pre-filter)
    is given, the band ASD is corrected for it."""
    if not bmask.any():
        return None
    sxx = acc['Bx']['S'][:, bmask]
    syy = acc['By']['S'][:, bmask]
    sxy = acc['Sxy'][:, bmask]
    w = 1.0 if resp2 is None else 1.0 / np.maximum(resp2[bmask], 1e-6)
    ic = ((sxx + syy) * w).sum(axis=1)                 # (filter-corrected) total power per 1-min bin
    sxx, syy, sxy = sxx.sum(axis=1), syy.sum(axis=1), sxy.sum(axis=1)
    if POL_BY_POSITIVE == 'west':
        sxy = -sxy
    k = max(int(round(avg_sec / SPEC_AVG_SEC)), 1)
    sxx, syy, sxy, ic, cnt = (group_sum(v, k) for v in (sxx, syy, sxy, ic, acc['Bx']['n']))
    I = sxx + syy
    ok = (cnt > 0) & (I > 0)
    with np.errstate(invalid='ignore', divide='ignore'):
        Q = sxx - syy                      # Stokes-like parameters of the 2x2 coherency matrix
        U = 2 * sxy.real
        V = 2 * sxy.imag
        dop = np.sqrt(Q ** 2 + U ** 2 + V ** 2) / I
        psi = 0.5 * np.arctan2(U, Q)       # B-field axis, from north towards east
        bearing = (np.degrees(psi) + 90.0 + POL_AZIMUTH_OFFSET_DEG) % 180.0
        amp = np.sqrt(ic / cnt / bmask.sum())
        power = I / cnt
    return dict(t=(np.arange(I.size) + 0.5) * k * SPEC_AVG_SEC / 3600.0, bearing=bearing,
                dop=dop, amp=amp, ok=ok, power=power)


def band_polarization(f_sel, acc, f0):
    """Polarization estimates in the band f0 +- POL_BAND_HZ/2, one per POL_AVG_SEC."""
    return band_series(acc, np.abs(f_sel - f0) <= POL_BAND_HZ / 2, POL_AVG_SEC)


def plot_polarization(day, f_sel, acc, freqs, outpath):
    res = [(f0, band_polarization(f_sel, acc, f0)) for f0 in freqs]
    res = [(f0, r) for f0, r in res if r is not None]
    if not res:
        return False
    nc = len(res)
    fig = plt.figure(figsize=POL_FIGSIZE)
    gs = GridSpec(3, nc, height_ratios=[2, 1.4, 2.6], hspace=0.7, wspace=0.3, figure=fig)
    top_axes, sc = [], None

    for c, (f0, r) in enumerate(res):
        col = PEAK_COLORS[c % len(PEAK_COLORS)]
        sel = r['ok'] & (r['dop'] >= POL_MIN_DOP)

        # --- row 0: bearing vs time, colour = degree of polarization ---
        ax1 = fig.add_subplot(gs[0, c])
        top_axes.append(ax1)
        if sel.any():
            sc = ax1.scatter(r['t'][sel], r['bearing'][sel], c=r['dop'][sel], s=18,
                             cmap='plasma', vmin=0, vmax=1, edgecolors='none')
        else:
            ax1.text(0.5, 0.5, 'no estimate above DOP threshold', transform=ax1.transAxes,
                     ha='center', va='center', fontsize=9)
        ax1.set_ylim(0, 180)
        ax1.set_yticks([0, 45, 90, 135, 180])
        ax1.set_yticklabels(['0 (N–S)', '45', '90 (E–W)', '135', '180 (N–S)'])
        ax1.set_xlim(0, 24)
        ax1.set_xticks(range(0, 25, 4))
        ax1.grid(True, alpha=0.3)
        ax1.tick_params(labelbottom=False)
        ax1.set_title(f'{f0:.2f} Hz  (±{POL_BAND_HZ / 2:g} Hz band)', color=col,
                      fontsize=11, fontweight='bold')
        if c == 0:
            ax1.set_ylabel('Source bearing (° from N, mod 180)')

        # --- row 1: band amplitude vs time ---
        ax2 = fig.add_subplot(gs[1, c], sharex=ax1)
        if r['ok'].any():
            ax2.semilogy(r['t'][r['ok']], r['amp'][r['ok']], '.-', color=col, lw=0.8, ms=4)
        ax2.grid(True, which='both', alpha=0.3)
        ax2.set_xlabel('Time (UTC hours)')
        if c == 0:
            ax2.set_ylabel('Band ASD, total H (pT/√Hz)')

        # --- row 2: rose diagram (180° ambiguity -> symmetric) ---
        ax3 = fig.add_subplot(gs[2, c], projection='polar')
        n_sel = int(sel.sum())
        if n_sel:
            b = r['bearing'][sel]
            w = r['power'][sel] if POL_WEIGHT == 'power' else np.ones(n_sel)
            th = np.concatenate([b, b + 180.0]) % 360.0
            ww = np.concatenate([w, w])
            hist, edges = np.histogram(np.radians(th), bins=POL_ROSE_BINS,
                                       range=(0, 2 * np.pi), weights=ww)
            ctr = 0.5 * (edges[1:] + edges[:-1])
            ax3.bar(ctr, hist, width=2 * np.pi / POL_ROSE_BINS, color=col, alpha=0.8,
                    edgecolor='k', lw=0.4)
            z = np.sum(w * np.exp(2j * np.radians(b)))          # axial (mod 180) statistics
            mean_b = (np.degrees(np.angle(z)) / 2.0) % 180.0
            R = np.abs(z) / np.sum(w)
            ax3.set_title(f'N = {n_sel}   axis {mean_b:.0f}° / {(mean_b + 180) % 360:.0f}°   '
                          f'R = {R:.2f}', fontsize=9, pad=14)
        else:
            ax3.set_title('no data', fontsize=9, pad=14)
        ax3.set_theta_zero_location('N')
        ax3.set_theta_direction(-1)
        ax3.set_thetagrids(range(0, 360, 45), labels=['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'])
        ax3.tick_params(axis='y', labelsize=7)

    if sc is not None:
        cb = fig.colorbar(sc, ax=top_axes, pad=0.01, fraction=0.025)
        cb.set_label('degree of polarization')
    weight = 'power-weighted' if POL_WEIGHT == 'power' else 'unweighted'
    fig.suptitle(f'{day[:4]}-{day[4:6]}-{day[6:]}   polarization, {POL_AVG_SEC:g} s estimates, '
                 f'DOP ≥ {POL_MIN_DOP:g}, {weight} rose, By positive {POL_BY_POSITIVE}, '
                 f'offset {POL_AZIMUTH_OFFSET_DEG:+g}°, {filter_description()}', fontsize=10)
    fig.savefig(outpath, dpi=POL_DPI, bbox_inches='tight')
    plt.close(fig)
    return True


# ---------------------------------------------------------------------------
#                       Schumann resonance analysis
# ---------------------------------------------------------------------------
def line_mask(f):
    """True for frequency bins belonging to the man-made lines in SR_LINE_MASK."""
    m = np.zeros(f.size, dtype=bool)
    for fl, hw in SR_LINE_MASK:
        m |= np.abs(f - fl) <= hw
    return m


def fit_peak(f, p, lo, hi, bad):
    """Peak frequency of a broad resonance in the window [lo, hi] of the PSD p(f).
    Bins flagged in `bad` (masked lines) are left out. Returns (f_peak, error) in Hz,
    NaN if no sensible peak was found."""
    sel = (f >= lo) & (f <= hi) & ~bad & np.isfinite(p) & (p > 0)
    if sel.sum() < 8:
        return np.nan, np.nan
    x, y = f[sel], p[sel]
    y = y / y.max()
    ys = np.convolve(y, np.ones(3) / 3.0, mode='same')
    ys[0], ys[-1] = y[0], y[-1]
    i0 = int(np.argmax(ys[1:-1])) + 1

    if SR_PEAK_METHOD == 'max':                          # parabolic interpolation of the maximum
        la, lb, lc = np.log(np.maximum(ys[i0 - 1:i0 + 2], 1e-30))
        den = la - 2 * lb + lc
        off = float(np.clip(0.5 * (la - lc) / den, -0.5, 0.5)) if den < 0 else 0.0
        return float(x[i0] + off * np.median(np.diff(x))), np.nan

    fc = 0.5 * (lo + hi)

    def model(ff, a, f0, g, b, c):                       # Lorentzian + linear background
        return a / (1.0 + ((ff - f0) / g) ** 2) + b + c * (ff - fc)

    p0 = [max(ys[i0] - ys.min(), 0.05), float(np.clip(x[i0], lo + 1e-3, hi - 1e-3)), 1.0,
          float(ys.min()), 0.0]
    try:
        popt, pcov = curve_fit(model, x, y, p0=p0, sigma=np.maximum(y, 0.05),
                               bounds=([0.0, lo, 0.3, -1.0, -5.0], [10.0, hi, 4.0, 5.0, 5.0]),
                               max_nfev=2000)
    except (RuntimeError, ValueError):
        return np.nan, np.nan
    f0 = float(popt[1])
    if f0 <= lo + 0.02 or f0 >= hi - 0.02:               # stuck at the window edge -> no peak
        return np.nan, np.nan
    err = float(np.sqrt(pcov[1, 1])) if np.isfinite(pcov[1, 1]) else np.nan
    return f0, err


def sr_compute_day(day, f_sel, acc):
    """Bearing / band ASD per SR_AVG_SEC and peak frequency per SR_TRACK_SEC for the
    first Schumann modes of one day. Returns a dict of arrays (saved as .npz)."""
    resp2 = acc['resp2'] if SR_CORRECT_FILTER else None
    bad = line_mask(f_sel)
    nm = len(SR_MODES_HZ)

    # ---- bearing and band ASD ----
    k = max(int(round(SR_AVG_SEC / SPEC_AVG_SEC)), 1)
    nt = int(np.ceil(acc['Bx']['n'].size / k))
    bearing, dop, amp = (np.full((nm, nt), np.nan) for _ in range(3))
    ok = np.zeros((nm, nt), dtype=bool)
    for m, f0 in enumerate(SR_MODES_HZ):
        bmask = (np.abs(f_sel - f0) <= SR_BAND_HZ / 2) & ~bad
        s = band_series(acc, bmask, SR_AVG_SEC, resp2)
        if s is not None:
            bearing[m], dop[m], amp[m], ok[m] = s['bearing'], s['dop'], s['amp'], s['ok']

    # ---- peak frequency tracking on the total horizontal PSD ----
    kt = max(int(round(SR_TRACK_SEC / SPEC_AVG_SEC)), 1)
    n = acc['Bx']['n']
    S = acc['Bx']['S'] + acc['By']['S']
    if SR_CORRECT_FILTER:
        S = S / np.maximum(acc['resp2'], 1e-6)[None, :]
    with np.errstate(invalid='ignore', divide='ignore'):
        P = S / n[:, None]                                # mean PSD of each 1-min bin (NaN if empty)

    def stat(rows):
        rows = rows[np.all(np.isfinite(rows), axis=1)]
        if rows.shape[0] < SR_TRACK_MIN_BINS:
            return None
        return np.median(rows, axis=0) if SR_TRACK_STAT == 'median' else np.mean(rows, axis=0)

    nb = int(np.ceil(n.size / kt))
    f0 = np.full((nm, nb), np.nan)
    f0e = np.full((nm, nb), np.nan)
    for b in range(nb):
        p = stat(P[b * kt:(b + 1) * kt])
        if p is None:
            continue
        for m, (lo, hi) in enumerate(SR_SEARCH_HZ):
            f0[m, b], f0e[m, b] = fit_peak(f_sel, p, lo, hi, bad)
    day_f0 = np.full(nm, np.nan)
    day_err = np.full(nm, np.nan)
    pday = stat(P)
    if pday is not None:
        for m, (lo, hi) in enumerate(SR_SEARCH_HZ):
            day_f0[m], day_err[m] = fit_peak(f_sel, pday, lo, hi, bad)

    return dict(day=np.array(day), modes=np.array(SR_MODES_HZ),
                hd_t=(np.arange(nt) + 0.5) * k * SPEC_AVG_SEC / 3600.0,
                bearing=bearing, dop=dop, amp=amp, ok=ok,
                tr_t=(np.arange(nb) + 0.5) * kt * SPEC_AVG_SEC / 3600.0,
                f0=f0, f0err=f0e, day_f0=day_f0, day_err=day_err)


def day_label(d):
    d = str(d)
    return f'{d[:4]}-{d[4:6]}-{d[6:]}'


def day_colors(n):
    if n <= 10:
        return [plt.cm.tab10(i) for i in range(n)]
    return [plt.cm.turbo(i / max(n - 1, 1)) for i in range(n)]


def mask_text():
    return ', '.join(f'{c:g}±{h:g} Hz' for c, h in SR_LINE_MASK) if SR_LINE_MASK else 'none'


def pooled_mean(results, m):
    """Mean over all days in bins of SR_MEAN_BIN_SEC: axial-mean bearing and band ASD."""
    step = SR_MEAN_BIN_SEC / 3600.0
    edges = np.arange(0.0, 24.0 + 1e-9, step)
    nb = len(edges) - 1
    t = np.concatenate([r['hd_t'] for r in results])
    b = np.concatenate([r['bearing'][m] for r in results])
    a = np.concatenate([r['amp'][m] for r in results])
    ok = np.concatenate([r['ok'][m] for r in results])
    dop = np.concatenate([r['dop'][m] for r in results])
    okb = ok & (dop >= SR_MIN_DOP) & np.isfinite(b)
    oka = ok & np.isfinite(a)
    idx = np.clip(np.digitize(t, edges) - 1, 0, nb - 1)
    tc = 0.5 * (edges[:-1] + edges[1:])
    mb = np.full(nb, np.nan)
    ma = np.full(nb, np.nan)
    for j in range(nb):
        sa = (idx == j) & oka
        if sa.sum() >= 2:
            ma[j] = np.median(a[sa]) if SR_MEAN_STAT == 'median' else np.mean(a[sa])
        sb = (idx == j) & okb
        if sb.sum() >= 3:
            z = np.mean(np.exp(2j * np.radians(b[sb])))
            mb[j] = (np.degrees(np.angle(z)) / 2.0) % 180.0
    if okb.any():
        z = np.mean(np.exp(2j * np.radians(b[okb])))
        axis, R = (np.degrees(np.angle(z)) / 2.0) % 180.0, float(np.abs(z))
    else:
        axis, R = np.nan, np.nan
    return tc, mb, ma, axis, R


def plot_sr_heading(results, out_dir):
    """One figure per Schumann mode: all days overlaid, bold mean over the recording."""
    nd = len(results)
    cols = day_colors(nd)
    days = [str(r['day']) for r in results]
    paths = []
    for m, fnom in enumerate(SR_MODES_HZ):
        tc, mb, ma, axis, R = pooled_mean(results, m)
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=SR_HEADING_FIGSIZE, sharex=True,
                                       gridspec_kw=dict(height_ratios=[1.3, 1], hspace=0.08))
        for r, c in zip(results, cols):
            good = r['ok'][m] & (r['dop'][m] >= SR_MIN_DOP) & np.isfinite(r['bearing'][m])
            ax1.scatter(r['hd_t'][good], r['bearing'][m][good], s=7, color=c, alpha=0.55,
                        edgecolors='none')
            g2 = r['ok'][m] & np.isfinite(r['amp'][m])
            ax2.semilogy(r['hd_t'][g2], r['amp'][m][g2], '-', color=c, lw=0.7, alpha=0.6)

        # bold mean curves (bearing line is broken where it wraps around 0/180 deg)
        xs, ys = [], []
        for i in range(len(tc)):
            if i and np.isfinite(mb[i]) and np.isfinite(mb[i - 1]) and abs(mb[i] - mb[i - 1]) > 90:
                xs.append(np.nan)
                ys.append(np.nan)
            xs.append(tc[i])
            ys.append(mb[i])
        ax1.plot(xs, ys, '-', color='w', lw=5.5, zorder=5)
        h1, = ax1.plot(xs, ys, 'o-', color='k', lw=2.5, ms=5, zorder=6,
                       label=f'MEAN of {nd} days: axis {axis:.0f}°, R = {R:.2f}')
        ax2.plot(tc, ma, '-', color='w', lw=5.5, zorder=5)
        h2, = ax2.plot(tc, ma, 'o-', color='k', lw=2.5, ms=5, zorder=6,
                       label=f'MEAN of {nd} days ({SR_MEAN_STAT}, {SR_MEAN_BIN_SEC / 60:g} min bins)')
        ax2.set_yscale('log')

        ax1.set_ylim(0, 180)
        ax1.set_yticks([0, 45, 90, 135, 180])
        ax1.set_yticklabels(['0 (N–S)', '45', '90 (E–W)', '135', '180 (N–S)'])
        ax1.set_ylabel('Source bearing (° from N, mod 180)')
        ax1.grid(True, alpha=0.3)
        ax1.legend(handles=[h1], loc='lower left', fontsize=10, framealpha=0.95)
        ax2.set_ylabel('Band ASD, total H (pT/√Hz)')
        ax2.set_xlabel('Time (UTC hours)')
        ax2.set_xlim(0, 24)
        ax2.set_xticks(range(0, 25, 2))
        ax2.grid(True, which='both', alpha=0.3)
        ax2.legend(handles=[h2], loc='upper right', fontsize=10, framealpha=0.95)
        ax1.set_title(f'Schumann mode {m + 1} (nominal {fnom:g} Hz, band ±{SR_BAND_HZ / 2:g} Hz)   '
                      f'{nd} days: {day_label(days[0])} – {day_label(days[-1])}\n'
                      f'bearing from estimates with DOP ≥ {SR_MIN_DOP:g}, {SR_AVG_SEC:g} s averages; '
                      f'masked lines: {mask_text()}; {filter_description()}', fontsize=10)
        handles = [Line2D([0], [0], color=c, lw=2, label=day_label(d)) for c, d in zip(cols, days)]
        fig.legend(handles=handles, loc='center right', fontsize=9, title='days',
                   bbox_to_anchor=(0.995, 0.5))
        fig.subplots_adjust(left=0.07, right=0.87, top=0.91, bottom=0.07)
        p = os.path.join(out_dir, f'schumann_mode{m + 1}_{fnom:g}Hz_heading.png')
        fig.savefig(p, dpi=SR_DPI)
        plt.close(fig)
        paths.append(os.path.basename(p))
    return paths


def plot_sr_trace_day(r, outpath):
    """Peak frequency of the Schumann modes vs time of day for one day (3 modes side by side)."""
    nm = len(SR_MODES_HZ)
    fig, axes = plt.subplots(1, nm, figsize=SR_TRACE_FIGSIZE, sharex=True)
    for m, ax in enumerate(axes):
        col = PEAK_COLORS[m % len(PEAK_COLORS)]
        good = np.isfinite(r['f0'][m])
        err = np.where(np.isfinite(r['f0err'][m]), r['f0err'][m], 0.0)
        if good.any():
            ax.errorbar(r['tr_t'][good], r['f0'][m][good], yerr=err[good], fmt='o-', ms=4,
                        lw=0.8, capsize=2, color=col)
        if np.isfinite(r['day_f0'][m]):
            e = r['day_err'][m]
            lab = f'day fit {r["day_f0"][m]:.2f}' + (f' ± {e:.2f} Hz' if np.isfinite(e) else ' Hz')
            ax.axhline(r['day_f0'][m], color='k', ls='--', lw=1, label=lab)
            ax.legend(loc='best', fontsize=9)
        ax.set_title(f'mode {m + 1} (nominal {SR_MODES_HZ[m]:g} Hz)', color=col, fontweight='bold')
        ax.set_xlim(0, 24)
        ax.set_xticks(range(0, 25, 4))
        ax.set_xlabel('Time (UTC hours)')
        ax.grid(True, alpha=0.3)
        if m == 0:
            ax.set_ylabel('Peak frequency (Hz)')
    d = str(r['day'])
    fig.suptitle(f'{day_label(d)}   Schumann peak frequency, {SR_TRACK_SEC / 3600:g} h estimates '
                 f'({SR_TRACK_STAT} PSD, {SR_PEAK_METHOD} fit); masked lines: {mask_text()}',
                 fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(outpath, dpi=SR_DPI)
    plt.close(fig)


def plot_sr_trace_period(results, out_dir):
    """(1) all days overlaid vs time of day, (2) entire registration on a date axis."""
    nm = len(SR_MODES_HZ)
    nd = len(results)
    cols = day_colors(nd)
    days = [str(r['day']) for r in results]

    # ---- (1) overlay ----
    fig, axes = plt.subplots(1, nm, figsize=SR_TRACE_FIGSIZE, sharex=True)
    for m, ax in enumerate(axes):
        for r, c, d in zip(results, cols, days):
            good = np.isfinite(r['f0'][m])
            ax.plot(r['tr_t'][good], r['f0'][m][good], 'o-', ms=3.5, lw=0.9, color=c,
                    label=day_label(d))
        ax.set_title(f'mode {m + 1} (nominal {SR_MODES_HZ[m]:g} Hz) — {nd} days overlaid',
                     fontsize=11)
        ax.set_xlim(0, 24)
        ax.set_xticks(range(0, 25, 4))
        ax.set_xlabel('Time (UTC hours)')
        ax.grid(True, alpha=0.3)
        if m == 0:
            ax.set_ylabel('Peak frequency (Hz)')
    axes[-1].legend(loc='center left', bbox_to_anchor=(1.01, 0.5), fontsize=9, title='days')
    fig.suptitle(f'Schumann peak frequency vs time of day, {SR_TRACK_SEC / 3600:g} h estimates '
                 f'({SR_TRACK_STAT} PSD, {SR_PEAK_METHOD} fit); masked lines: {mask_text()}',
                 fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    p1 = os.path.join(out_dir, 'period_overlay.png')
    fig.savefig(p1, dpi=SR_DPI, bbox_inches='tight')
    plt.close(fig)

    # ---- (2) entire registration ----
    fig, axes = plt.subplots(1, nm, figsize=SR_TRACE_FIGSIZE)
    bases = [datetime.strptime(d, '%Y%m%d') for d in days]
    for m, ax in enumerate(axes):
        col = PEAK_COLORS[m % len(PEAK_COLORS)]
        tx, fy = [], []
        for i, (r, b0) in enumerate(zip(results, bases)):
            if i and (b0 - bases[i - 1]).days > 1:            # missing day(s): break the line
                tx.append(np.nan)
                fy.append(np.nan)
            tx.extend(mdates.date2num(b0) + r['tr_t'] / 24.0)
            fy.extend(r['f0'][m])
        ax.plot(tx, fy, 'o-', ms=3, lw=0.7, color=col, label=f'{SR_TRACK_SEC / 3600:g} h estimates')
        dd = np.array([r['day_f0'][m] for r in results])
        de = np.array([r['day_err'][m] for r in results])
        gd = np.isfinite(dd)
        if gd.any():
            xd = np.array([mdates.date2num(b0) + 0.5 for b0 in bases])
            ax.errorbar(xd[gd], dd[gd], yerr=np.where(np.isfinite(de[gd]), de[gd], 0), fmt='D',
                        color='k', ms=6, capsize=3, zorder=5,
                        label=f'daily fit: mean {np.mean(dd[gd]):.2f} Hz, σ {np.std(dd[gd]):.2f} Hz')
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
        ax.set_title(f'mode {m + 1} (nominal {SR_MODES_HZ[m]:g} Hz) — {nd} days', fontsize=11)
        ax.grid(True, alpha=0.3)
        ax.legend(loc='best', fontsize=8)
        if m == 0:
            ax.set_ylabel('Peak frequency (Hz)')
    fig.suptitle(f'Schumann peak frequency over the entire registration: {nd} days '
                 f'({day_label(days[0])} – {day_label(days[-1])}); masked lines: {mask_text()}',
                 fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    p2 = os.path.join(out_dir, 'period_trace.png')
    fig.savefig(p2, dpi=SR_DPI)
    plt.close(fig)
    return [os.path.basename(p1), os.path.basename(p2)]


# ---------------------------------------------------------------------------
def load_sr(path):
    z = np.load(path, allow_pickle=False)
    return {k: z[k] for k in z.files}


def main():
    root = DATA_ROOT if os.path.isabs(DATA_ROOT) else os.path.join(SCRIPT_DIR, DATA_ROOT)
    out_dir = OUTPUT_DIR if os.path.isabs(OUTPUT_DIR) else os.path.join(SCRIPT_DIR, OUTPUT_DIR)
    d_spec = os.path.join(out_dir, SUBDIR_SPECTRA)
    d_ts = os.path.join(out_dir, SUBDIR_TIMESERIES)
    d_pol = os.path.join(out_dir, SUBDIR_POLARIZATION)
    d_srh = os.path.join(out_dir, SUBDIR_SR_HEADING)
    d_srt = os.path.join(out_dir, SUBDIR_SR_TRACE)
    d_src = os.path.join(out_dir, SUBDIR_SR_CACHE)
    dirs = [d_spec, d_ts] + ([d_pol] if POL_ENABLE else []) + \
           ([d_srh, d_srt, d_src] if SR_ENABLE else [])
    for d in dirs:
        os.makedirs(d, exist_ok=True)

    days = list_days(root)
    if not days:
        print(f'No YYYYMMDD directories found in {root}')
        return

    for day in days:
        spec_png = os.path.join(d_spec, f'{day}_spectra.png')
        ts_png = os.path.join(d_ts, f'{day}_timeseries.png')
        pol_png = os.path.join(d_pol, f'{day}_polarization.png')
        sr_png = os.path.join(d_srt, f'{day}_trace.png')
        sr_cache = os.path.join(d_src, f'{day}.npz')
        needed = [spec_png, ts_png] + ([pol_png] if POL_ENABLE else []) + \
                 ([sr_png, sr_cache] if SR_ENABLE else [])
        if SKIP_EXISTING and all(os.path.exists(p) for p in needed):
            print(f'{day}: already done, skipped')
            continue
        print(f'{day}:')
        res = process_day(day, os.path.join(root, day))
        if res is None:
            continue
        f_sel, acc = res
        sp = compute_spectra(f_sel, acc)
        plot_spectra(day, f_sel, acc, sp, spec_png)
        plot_timeseries(day, acc, ts_png)
        saved = [os.path.join(SUBDIR_SPECTRA, os.path.basename(spec_png)),
                 os.path.join(SUBDIR_TIMESERIES, os.path.basename(ts_png))]
        if POL_ENABLE:
            freqs = POL_FREQS if POL_FREQS else [fp for fp, _ in sp['peaks']['H']]
            if plot_polarization(day, f_sel, acc, freqs, pol_png):
                saved.append(os.path.join(SUBDIR_POLARIZATION, os.path.basename(pol_png)))
            else:
                print('  polarization skipped (no peaks / frequencies to analyse)')
        if SR_ENABLE:
            r = sr_compute_day(day, f_sel, acc)
            np.savez(sr_cache, **r)
            plot_sr_trace_day(r, sr_png)
            saved.append(os.path.join(SUBDIR_SR_TRACE, os.path.basename(sr_png)))
        print('  saved ' + ', '.join(saved))

    # ---- multi-day Schumann plots (from the per-day cache) ----
    if SR_ENABLE:
        results = [load_sr(os.path.join(d_src, f'{d}.npz')) for d in days
                   if os.path.exists(os.path.join(d_src, f'{d}.npz'))]
        if results:
            ref = results[0]
            keep = [r for r in results
                    if r['hd_t'].shape == ref['hd_t'].shape and r['tr_t'].shape == ref['tr_t'].shape
                    and np.allclose(r['modes'], ref['modes'])]
            if len(keep) < len(results):
                print(f'  ! {len(results) - len(keep)} cached day(s) with different SR settings '
                      f'ignored (rerun them with SKIP_EXISTING = False)')
            results = keep
            print(f'Schumann multi-day plots from {len(results)} day(s):')
            h = plot_sr_heading(results, d_srh)
            t = plot_sr_trace_period(results, d_srt)
            print('  saved ' + ', '.join([os.path.join(SUBDIR_SR_HEADING, x) for x in h] +
                                         [os.path.join(SUBDIR_SR_TRACE, x) for x in t]))


if __name__ == '__main__':
    main()
