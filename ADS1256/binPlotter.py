import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import struct
import os
import numpy as np
import matplotlib.pyplot as plt
plt.rcParams['agg.path.chunksize'] = 10000  # Increase the chunksize to 10,000
import matplotlib.dates as mdates
from matplotlib.dates import AutoDateLocator, DateFormatter
from matplotlib.widgets import SpanSelector
from matplotlib.dates import num2date
from datetime import timedelta, datetime, timezone
import code # for interactive shell
import traceback

FIXED_FORMAT_STR = '<HHIBBH'
HEADER_SIZE = struct.calcsize(FIXED_FORMAT_STR)

class BinPlotterApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Binary Data Plotter")
        self.abort_flag = False
        self.filename = ""
        self.meta = {}
        self.times = None
        self.values = None

        # Text widget for displaying log or header info
        self.info_text = tk.Text(master, height=10, width=80, wrap=tk.WORD)
        self.info_text.pack(pady=5)
        self.info_text.insert(tk.END, "Select a file to begin.\n")
        self.info_text.config(state='disabled')

        # Progress bar
        self.progress = ttk.Progressbar(master, orient="horizontal", length=400, mode="determinate")
        self.progress.pack(pady=5)

        # Label for progress updates
        self.status_label = tk.Label(master, text="")
        self.status_label.pack(pady=2)

        # Buttons
        self.button_frame = tk.Frame(master)
        self.button_frame.pack(pady=10)

        self.load_button = tk.Button(self.button_frame, text="Load .bin File", command=self.load_bin_file)
        self.load_button.grid(row=0, column=0, padx=5)

        self.load_npz_button = tk.Button(self.button_frame, text="Load .npz File", command=self.load_npz_file)
        self.load_npz_button.grid(row=0, column=1, padx=5)

        self.abort_button = tk.Button(self.button_frame, text="Abort", command=self.abort, state='disabled')
        self.abort_button.grid(row=0, column=2, padx=5)

        self.plot_button = tk.Button(self.button_frame, text="Plot", command=self.plot_data, state='disabled')
        self.plot_button.grid(row=0, column=3, padx=5)

        self.inspect_button = tk.Button(self.button_frame, text="Inspect Variables", command=self.inspect_variables)
        self.inspect_button.grid(row=0, column=4, padx=5)

        self.save_button = tk.Button(self.button_frame, text="Save Workspace", command=self.save_workspace)
        self.save_button.grid(row=0, column=5, padx=5)
        

    def set_info_text(self, content):
        self.info_text.config(state='normal')
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(tk.END, content + "\n")
        self.info_text.config(state='disabled')

    def append_info_text(self, content):
        self.info_text.config(state='normal')
        self.info_text.insert(tk.END, "==================== \n" + content + "\n")
        self.info_text.config(state='disabled')
        

    def abort(self):
        self.abort_flag = True
        self.status_label.config(text="Abort requested...")

    def load_bin_file(self):
        self.filename = filedialog.askopenfilename(title="Select binary data file", filetypes=[("Binary Files", "*.bin")])
        if not self.filename:
            return

        self.abort_flag = False
        self.abort_button.config(state='normal')
        self.plot_button.config(state='disabled')
        self.times = self.values = None

        # Try reading log file
        txt_file = os.path.splitext(self.filename)[0] + ".txt"
        self.meta = self.read_log_file(txt_file) if os.path.exists(txt_file) else {}

        # Read file size and preview first header
        try:
            filesize = os.path.getsize(self.filename)
            with open(self.filename, 'rb') as f:
                header = f.read(HEADER_SIZE)
                if len(header) != HEADER_SIZE:
                    raise ValueError("File too short or corrupted")
                length, sps, epochtime, gain, channel, res16 = struct.unpack(FIXED_FORMAT_STR, header)

                block_size = HEADER_SIZE + (length * 4)  # int32 is 4 bytes
                estimated_blocks = filesize // block_size

                # Estimate the file duration (in seconds)
                total_samples = length * estimated_blocks
                total_duration_seconds = total_samples / sps
                total_duration = timedelta(seconds=total_duration_seconds)

                # Format the estimated end date and time
                start_time = datetime.fromtimestamp(epochtime, tz=timezone.utc)  # Apply 27 seconds adjustment
                start_time_str = start_time.strftime('%Y-%m-%d %H:%M')
                end_time = start_time + total_duration
                estimated_end_str = end_time.strftime('%Y-%m-%d %H:%M')

                log_summary = "\n".join([f"{k}: {v}" for k, v in self.meta.items()]) if self.meta else "No .txt log info"
                header_info = (
                    f"Header:\n  length={length}, sps={sps}, time={epochtime}, gain={gain}, channel={channel}, res16={res16}\n"
                    f"blocks: {estimated_blocks}, File size: {filesize // (1024 * 1024)} MB\n"
                    f"start date & time:  {start_time_str}\n"
                    f"Estimated end time: {estimated_end_str}\n"
                    f"Estimated file duration: {total_duration}\n"   
                )

                # Create or meta dictionary with first header info
                self.meta = {
                    'start': start_time_str,
                    'end': estimated_end_str,
                    'duration': total_duration,
                    'b_length': length,
                    'sps': sps,
                    'epochtime': epochtime,
                    'gain': gain,
                    'channel': channel,
                    'res16': res16
                }
                self.set_info_text(f"{header_info}\n{log_summary}")
                self.status_label.config(text="Ready to load file blocks...")
        except Exception as e:
            self.status_label.config(text=f"Failed to read file header: {e}")
            return

        # Start threaded loading
        threading.Thread(target=self.read_blocks_thread).start()

    def write_memmap_array(self, path, array, dtype=None):
        """Write data to disk using memory-mapped file using np.memmap, with error tracing."""
        try:
            if dtype is None:
                raise ValueError("dtype must be specified")

            m = np.memmap(path, dtype=dtype, mode='w+', shape=array.shape)
            m[:] = array[:]
            m.flush()
            del m  # Ensure file handle is released

        except Exception as e:
            print(f"Error while writing memmap array to {path}: {e}")
            import pdb; pdb.set_trace()
            raise  # Re-raise the exception after debugging     

    def read_log_file(self, log_filename):
        log_info = {}
        try:
            with open(log_filename, 'r') as file:
                for line in file:
                    if '=' in line:
                        key, value = line.strip().split('=')
                        log_info[key] = value
        except Exception as e:
            print(f"Could not read log file: {e}")
        return log_info

    def epoch_to_datetime(self, epochtime):
        #Convert epoch time (seconds since 1970-01-01 00:00:00 UTC) to datetime object.
        start_date = datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)  # Base start date
        return start_date + timedelta(seconds = epochtime - 27 ) #leap seconds until 2025 (see encoding for MCU)

    def inspect_variables(self):
        # Check and display the actual variables and their names
        if hasattr(self, 'times') and self.times is not None:
            print(f"app.times: shape={self.times.shape}, dtype={self.times.dtype}")
        else:
            print("times: None")

        if hasattr(self, 'values') and self.values is not None:
            print(f"app.values: shape={self.values.shape}, dtype={self.values.dtype}")
        else:
            print("values: None")

        if hasattr(self, 'meta') and isinstance(self.meta, dict):
            print("app.meta keys:", list(self.meta.keys()))
        else:
            print("meta: None or invalid")

        print("ctrl+D to exit")

        # Once variables are printed, give control back to the user in an interactive shell
        # code.interact(local=locals())
        threading.Thread(target=lambda: code.interact(local=globals())).start()

    
    def save_workspace(self):
        if self.times is None or self.values is None:
            messagebox.showinfo("Save Error", "No data to save.")
            return

        save_path = filedialog.asksaveasfilename(defaultextension=".npz", filetypes=[("NPZ files", "*.npz")])
        if not save_path:
            return

        try:
            np.savez_compressed(save_path, times=self.times, values=self.values, meta=self.meta)
            messagebox.showinfo("Saved", f"Workspace saved to:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save file:\n{e}")

    def summarize_drift(self, drift_log, total_duration_sec):
        if not drift_log:
            self.append_info_text("No drift detected.")
            return

        # Unpack
        drift_sizes = [entry['drift'] for entry in drift_log]
        drift_times = [entry['time'] for entry in drift_log]  # seconds since start

        # Calculate stats
        drift_intervals = np.diff(drift_times)
        drift_avg = np.mean(drift_sizes)
        drift_min = np.min(drift_sizes)
        drift_max = np.max(drift_sizes)
        interval_min = np.min(drift_intervals) / 60
        interval_max = np.max(drift_intervals) / 60
        interval_avg = np.mean(drift_intervals) / 60
        total_drift = np.sum(drift_sizes)
        duration_hours = total_duration_sec / 3600
        drift_per_hour = total_drift / duration_hours
        ppm_error = (drift_per_hour / 3600) * 1e6  # error per second in ppm

        # Format nicely
        self.append_info_text(
            "Drift Summary:\n"
            f"- Detected drift events: {len(drift_sizes)}\n"
            f"- Drift size: ~{drift_avg:.2f}s (min: {drift_min:.2f}s, max: {drift_max:.2f}s)\n"
            f"- Occurs approximately every {interval_min:.0f}–{interval_max:.0f} minutes (avg: {interval_avg:.1f} min)\n"
            f"- Total accumulated drift: ~{total_drift:.2f} seconds over ~{duration_hours:.2f} hours\n"
            f"- Approximate clock error: {drift_per_hour:.2f} seconds/hour ≈ {100 * drift_per_hour / 3600:.3f}% ({ppm_error:.0f} ppm)"
        )

    def prompt_decimation(self, sps):
        from tkinter.simpledialog import askstring
        from tkinter import simpledialog

        # Nyquist values (sps / 2 / 2^n)
        max_power = 10  # 2^10 = 1024
        options = []
        for n in range(max_power + 1):  # 0 to 10
            factor = 2 ** n
            f_nyquist = (sps / 2) / factor
            options.append((factor, f"{f_nyquist:.2f} Hz"))

        # Create a simple option list for user selection
        choice = simpledialog.askstring(
            "Choose Nyquist Frequency",
            "Select desired Nyquist frequency:\n\n" +
            "\n".join([f"{i+1}: {label}" for i, (_, label) in enumerate(options)]),
            parent=self.master
        )

        if choice is None:
            return None

        try:
            idx = int(choice.strip()) - 1
            return options[idx][0]  # Return decimation factor
        except Exception:
            messagebox.showerror("Invalid Input", "Please enter a valid option number.")
            return None

    def read_blocks_thread(self):
        import time
        filesize = os.path.getsize(self.filename)
        read_bytes = 0
        block_counter = 0
        total_drift = 0
        total_duration = 0
        location_last_drift = 0
        times = []  # Stores time points for each block (epoch seconds)
        values = []  # Stores the sensor data values
        drift_log = []  # Logs detected drifts
        gaps = []  # Logs gaps (time offsets)

        self.status_label.config(text="Reading file...")
        self.progress.config(maximum=filesize)
        last_update_time = time.time()

        try:
            with open(self.filename, 'rb') as f:
                # Calculate block duration and time step only once before the loop
                block_duration = self.meta['b_length'] / self.meta['sps']
                time_step = 1.0 / self.meta['sps']
                blk_time = np.arange(self.meta['b_length']) * time_step
                
                while not self.abort_flag:
                    header = f.read(HEADER_SIZE)
                    if len(header) != HEADER_SIZE:
                        break
                    try:
                        length, sps, epochtime, gain, channel, res16 = struct.unpack(FIXED_FORMAT_STR, header)
                    except struct.error:
                        break

                    read_bytes += HEADER_SIZE
                    data = np.fromfile(f, dtype=np.int32, count=length)
                    read_bytes += data.nbytes

                    if len(data) != length:
                        break

                    block_counter += 1
                    if block_counter > 1:  # dismiss first block
                        # Append block data (convert to float to avoid NaN issues later)
                        values.append(data.astype(np.float32))

                        # Check for time consistency and drift after every block
                        total_duration += block_duration

                        expected_time = self.meta['epochtime'] + total_duration + total_drift
                        blk_times = expected_time + blk_time
                        times.append(blk_times)
                        
                        drift = epochtime - expected_time  # +ve: data late; -ve: data early

                        if 2 < abs(drift) < 60:
                            td = datetime.fromtimestamp(expected_time, tz=timezone.utc)
                            self.append_info_text(f"Drift of {drift:.2f}s detected at block {block_counter:8d} at {td.strftime('%H:%M:%S')}\n"
                                f"after {total_duration:.2f}s absolute or {(total_duration-location_last_drift):.2f}s relative to previous, "\
                                f"total_drift: {(total_drift):.2f}s\n"
                                f"length={length}, sps={sps}, date(epochtime)={datetime.fromtimestamp(epochtime, tz=timezone.utc).strftime('%H:%M:%S')}")
                            location_last_drift = total_duration
                            drift_log.append({'block': block_counter, 'drift': drift,'time': total_duration})

                            if drift > 0:
                                # Log the gap, no padding inserted here
                                gap_duration = drift
                                gaps.append({'block': block_counter, 'gap_duration': gap_duration})
                                total_drift += drift  # Increment the drift

                        elif drift < 0:
                            # Negative drift = lagging timestamp; accept it, realign time base
                            total_duration = epochtime - self.meta['epochtime']  # Realign expected time
                            total_drift += drift  # Increment the drift
                            
                        if abs(drift) >= 60:
                            td = datetime.fromtimestamp(expected_time, tz=timezone.utc)
                            self.append_info_text(f"Excessive drift ({drift:.2f} sec) at block {block_counter} (at {td.strftime('%H:%M:%S')} after {total_duration:.2f}s). Aborting.")
                            self.abort_flag = True
                            break

                        # Update progress bar periodically
                        if block_counter % 10 == 0 or read_bytes >= filesize:
                            now = time.time()
                            if now - last_update_time > 1 or read_bytes % (1024 * 1024) < HEADER_SIZE:
                                self.progress["value"] = read_bytes
                                self.master.update_idletasks()
                                self.status_label.config(text=f"Loaded {read_bytes // 1024} KB")
                                last_update_time = now

            if self.abort_flag:
                self.status_label.config(text="Loading aborted due to time drift.")
                self.abort_button.config(state='disabled')
                return

            # Update status label
            self.status_label.config(text=f"Done. Loaded {block_counter} blocks. Wait for saving!")
            self.abort_button.config(state='disabled')

            # Concatenate all times and values for the complete data (without any NaNs)
            self.times = np.concatenate(times).astype(np.float64)  # Array of epoch seconds
            self.values = np.concatenate(values).astype(np.float32)  # Array of sensor values (float)

            # Store metadata information
            self.meta.update({
                'num_samples': int(self.values.size),
                'blocks_loaded': block_counter,
                'final_drift_sec': round(total_drift, 3),
                'gaps': gaps  # Store gap data
            })

            self.summarize_drift(drift_log, total_duration) 

            self.progress.config(maximum=100)
            self.progress["value"] = 0
            self.master.update_idletasks()

            # Estimate the total number of chunks (for the progress bar)
            total_chunks = 2  # Times + Values
            chunk_size_times = self.times.nbytes
            chunk_size_values = self.values.nbytes
            total_size = chunk_size_times + chunk_size_values

            # Update progress bar as we write the chunks
            self.status_label.config(text="Saving data...")

            # Write times array
            base_path = os.path.splitext(self.filename)[0]
            times_path = f"{base_path}_times.dat"
            values_path = f"{base_path}_values.dat"
            meta_path = f"{base_path}.npz"
            
            self.write_memmap_array(times_path, self.times, np.float64)
            self.progress["value"] += (chunk_size_times / total_size) * 100
            self.master.update_idletasks()

            # Write values array
            self.write_memmap_array(values_path, self.values, np.float32)
            self.progress["value"] += (chunk_size_values / total_size) * 100
            self.master.update_idletasks()

            # Save metadata
            np.savez(meta_path, meta=self.meta)
            self.progress["value"] = 100  # Final progress update
            self.master.update_idletasks()

            self.status_label.config(text=f"Saved memory-mapped files.\nMeta: {meta_path}")
            print(f"Saved memory-mapped files: {times_path}, {values_path}, {meta_path}")

            self.plot_button.config(state='normal')
            self.progress["value"] = 100
            self.master.update_idletasks()

        except Exception as e:
            tb = traceback.format_exc()
            messagebox.showerror("Reading Block Error", f"Error: {e}\n\n{tb}")
            self.abort_button.config(state='disabled')



    def load_npz_file(self):
        meta_path = filedialog.askopenfilename(title="Select meta .npz file", filetypes=[("NPZ Files", "*.npz")])
        if not meta_path:
            return
        try:
            base = os.path.splitext(meta_path)[0]
            times_path = f"{base}_times.dat"
            values_path = f"{base}_values.dat"

            if not os.path.exists(times_path) or not os.path.exists(values_path):
                raise FileNotFoundError("Associated .dat files for times or values not found.")

            self.meta = np.load(meta_path, allow_pickle=True)['meta'].item()

            self.times = np.memmap(times_path, dtype=np.float64, mode='r')
            self.values = np.memmap(values_path, dtype=np.int32, mode='r')

            info = f"Loaded memory-mapped files:\n{meta_path}\n{times_path}\n{values_path}\n\n"
            info += "\n".join(f"{k}: {v}" for k, v in self.meta.items())
            self.set_info_text(info)

            self.plot_button.config(state='normal')

        except Exception as e:
            self.set_info_text(f"Failed to load memory-mapped files: {e}")
            self.plot_button.config(state='disabled')



    def read_log_file(self, log_filename):
        log_info = {}
        try:
            with open(log_filename, 'r') as file:
                for line in file:
                    if '=' in line:
                        key, value = line.strip().split('=')
                        log_info[key] = value
        except Exception as e:
            print(f"Could not read log file: {e}")
        return log_info
 

    def plot_data(self):
        from scipy.signal import decimate
        if self.times is None or self.values is None:
            messagebox.showinfo("Info", "No data loaded.")
            return

        try:   # Downsampling
            MAX_POINTS = 10000
            times = self.times
            values = self.values

            if len(times) != len(values):
                raise ValueError("Mismatch between times and values length")

            if len(times) > MAX_POINTS:
                step = len(times) // MAX_POINTS

                # Estimate downsampling factor and ensure it's a power of 2 for decimate
                factor = 2 ** int(np.log2(step))  # round down to nearest power of 2

                # Handle NaNs before filtering (decimate cannot handle NaNs)
                nan_mask = np.isnan(values)
                if np.any(nan_mask):
                    # Temporarily interpolate NaNs (can be skipped or improved)
                    x = np.arange(len(values))
                    valid = ~nan_mask
                    values_filled = np.interp(x, x[valid], values[valid])
                else:
                    values_filled = values

                # Apply decimation (filter + downsample)
                values_to_plot = decimate(values_filled, factor, ftype='fir', zero_phase=True)
                times_to_plot = times[::factor]
                values_to_plot = values_to_plot[:len(times_to_plot)]  # match lengths
            else:
                times_to_plot = times
                values_to_plot = values
                
            epoch_base = float(self.meta['epochtime'])

            start_dt = self.epoch_to_datetime(times_to_plot[0])
            end_dt = self.epoch_to_datetime(times_to_plot[-1])
            title_str = f"Start: {start_dt.strftime('%Y-%m-%d %H:%M:%S')} — End: {end_dt.strftime('%H:%M:%S')}"
            print(title_str)

            # Plotting
            fig, ax = plt.subplots(figsize=(12, 6))
            time_datetimes = [datetime.fromtimestamp(epoch, timezone.utc) for epoch in times_to_plot]  # convert from raw epoch seconds to datetime objects
            ax.plot(time_datetimes, values_to_plot, linewidth=0.8)

            # Optional: Set limits if needed (you can use start_dt and end_dt here)
            ax.set_xlim([start_dt, end_dt])

            ax.set_title(title_str)
            ax.set_xlabel("Time (UTC)")
            ax.set_ylabel("ADC Value")

            locator = AutoDateLocator()
            formatter = DateFormatter('%H:%M')
            ax.xaxis.set_major_locator(locator)
            ax.xaxis.set_major_formatter(formatter)
            ax.grid(which='major', linestyle='-', linewidth=0.7)
            ax.grid(which='minor', linestyle=':', linewidth=0.5)
            ax.minorticks_on()

            # Maximize plot window
            figManager = plt.get_current_fig_manager()
            try:
                figManager.window.state('zoomed')
            except AttributeError:
                try:
                    figManager.full_screen_toggle()
                except AttributeError:
                    pass

            # Handle selection
            def onselect(xmin, xmax):
                # Convert to datetime for better understanding
                t0 = num2date(xmin).astimezone(timezone.utc)
                t1 = num2date(xmax).astimezone(timezone.utc)
                delta = (t1 - t0).total_seconds()
                print(f"Selected range: {delta:.0f}s")

                # Convert datetime back to epoch time for comparison with times_to_plot
                t0_epoch = t0.timestamp()
                t1_epoch = t1.timestamp()

                # Mask data within selected range
                mask = (times_to_plot >= t0_epoch) & (times_to_plot <= t1_epoch)
                selected_values = np.array(values_to_plot)[mask]

                if len(selected_values) == 0:
                    return

                # Prompt for decimation (Nyquist frequency) from the user
                decimation_factor = self.prompt_decimation(self.meta['sps'])
                if decimation_factor is None:
                    return  # User cancelled or invalid input

                # Calculate Nyquist frequency based on decimation factor
                nyquist_frequency = self.meta['sps'] / 2 / decimation_factor
                print(f"Nyquist frequency: {nyquist_frequency:.2f} Hz")

                resampled_values = decimate(selected_values, decimation_factor, ftype='fir', zero_phase=True)

                # Perform FFT on resampled data
                N = len(resampled_values)
                T = 1 / self.meta['sps']  # Use the actual sample rate (sps)
                yf = np.fft.rfft(resampled_values)
                xf = np.fft.rfftfreq(N, T * decimation_factor)  # Adjust the frequency bins accordingly


                # Show spectrum in a new figure
                fig_spec = plt.figure(figsize=(12, 6))
                ax_spec = fig_spec.add_subplot(111)
                ax_spec.plot(xf, 20 * np.log10(np.abs(yf) + 1e-12))
                ax_spec.set_title("Spectrum of Selected Region")
                ax_spec.set_xlabel("Frequency (Hz)")
                ax_spec.set_ylabel("Magnitude (dB)")
                ax_spec.grid(True)
                plt.tight_layout()
                plt.show()

            # Create SpanSelector for horizontal selection
            span = SpanSelector(ax, onselect, 'horizontal', useblit=True,
                                props=dict(alpha=0.5, facecolor='red'), interactive=True)

            plt.tight_layout()
            plt.show()

        except Exception as e:
            tb = traceback.format_exc()
            messagebox.showerror("Plotting Error", f"Error: {e}\n\n{tb}")


if __name__ == "__main__":
    root = tk.Tk()
    app = BinPlotterApp(root)
    root.mainloop()
