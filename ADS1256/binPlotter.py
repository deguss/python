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
        self.blocks = []
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
        """Convert epoch time (seconds since 1970-01-01 00:00:00 UTC) to datetime object."""
        start_date = datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)  # Base start date
        return start_date + timedelta(seconds = epochtime - 27 ) #leap seconds until 2025 (see encoding for MCU)

    def inspect_variables(self):
        # Check and display the actual variables and their names
        if hasattr(self, 'times') and self.times is not None:
            print(f"times: shape={self.times.shape}, dtype={self.times.dtype}")
        else:
            print("times: None")

        if hasattr(self, 'values') and self.values is not None:
            print(f"values: shape={self.values.shape}, dtype={self.values.dtype}")
        else:
            print("values: None")

        if hasattr(self, 'meta') and isinstance(self.meta, dict):
            print("meta keys:", list(self.meta.keys()))
        else:
            print("meta: None or invalid")

        if hasattr(self, 'sps') and self.sps is not None:
            print(f"sps: {self.sps}")
        else:
            print("sps: None")

        if hasattr(self, 'gain') and self.gain is not None:
            print(f"gain: {self.gain}")
        else:
            print("gain: None")
        
        # Add any other relevant variables you need to display
        if hasattr(self, 'start_day') and self.start_day is not None:
            print(f"start_day: {self.start_day}")
        if hasattr(self, 'start_time') and self.start_time is not None:
            print(f"start_time: {self.start_time}")

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



    def read_blocks_thread(self):
        self.blocks = []
        filesize = os.path.getsize(self.filename)
        read_bytes = 0
        block_counter = 0
        expected_end_epoch = None
        start_time = None

        self.status_label.config(text="Reading file...")
        self.progress.config(maximum=filesize)

        try:
            with open(self.filename, 'rb') as f:

                total_duration = 0  # Track total duration

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
                        self.blocks.append({
                            'length': length,
                            'sps': sps,
                            'epochtime': epochtime,
                            'gain': gain,
                            'channel': channel,
                            'res16': res16,
                            'data': data
                        })

                        # Check for time consistency and drift after every block
                        # Calculate expected time for this block based on previous
                        elapsed_time = length / sps  # Time duration of this block
                        total_duration += elapsed_time

                        # Check if current epochtime is close to the expected one
                        drift = abs(epochtime - (self.meta['epochtime'] + total_duration))

                        if drift > 2:  # 2 seconds threshold for drift
                            self.status_label.config(text=f"Time drift detected in block {block_counter}")
                            self.append_info_text(f"Drift detected at block {block_counter}:\n"
                                                  f"Expected epochtime: {self.meta['epochtime'] + total_duration:.2f}\n"
                                                  f"Actual epochtime: {epochtime}\n"
                                                  f"Drift: {drift:.2f} seconds")
                            self.abort_flag = True
                            self.abort_button.config(state='normal')
                            break

                        if block_counter % 10 == 0 or read_bytes >= filesize:
                            self.progress["value"] = read_bytes
                            self.master.update_idletasks()
                            self.status_label.config(text=f"Loaded {read_bytes // 1024} KB")

                if self.abort_flag:
                    self.status_label.config(text="Loading aborted due to time drift.")
                    self.abort_button.config(state='disabled')
                    return

                self.status_label.config(text=f"Done. Loaded {block_counter} blocks.")
                self.abort_button.config(state='disabled')

                # Now calculate the final time duration and compare with the last block's epochtime
                if self.blocks:
                    # Expected total duration (in seconds)
                    calculated_total_seconds = total_duration

                    # Get the expected end epochtime from the last block
                    last_block = self.blocks[-1]
                    last_block_epoch = last_block['epochtime']

                    # Display difference between expected and actual end times
                    calculated_end_time = self.meta['epochtime'] + calculated_total_seconds
                    drift = last_block_epoch - calculated_end_time

                    self.append_info_text(f"Total blocks: {block_counter}\n"
                                          f"Start: {self.meta['epochtime']}\n"
                                          f"Calculated total duration: {calculated_total_seconds:.2f} seconds\n"
                                          f"Last block epoch: {last_block_epoch}\n"
                                          f"Calculated end time: {calculated_end_time}\n"
                                          f"Time drift from last block: {drift:.2f} seconds")
                
                    if abs(drift) > 2:  # If drift exceeds 2 seconds, warn user
                        self.status_label.config(text=f"Warning: Time drift detected: {drift:.2f} seconds")
                    else:
                        self.status_label.config(text=f"No significant time drift detected.")

                # Convert blocks to arrays for plotting [times] and [values]
                times = []
                values = []

                # Start time of the first block (in epoch time)
                #start_epoch_time = self.blocks[0]['epochtime']  # Get the epochtime of the first block

                # Correct the start time by converting the epochtime to a proper datetime
                #start_time = datetime.fromtimestamp(start_epoch_time, tz=timezone.utc)  # Convert epoch to UTC datetime (timezone-aware)
                #self.start_day = start_time.strftime('%Y-%m-%d')
                #self.start_time = start_time.strftime('%H:%M')            

                # Variable to keep track of the running total time
                current_time = self.meta['epochtime']
                block_duration = self.meta['b_length'] / self.meta['sps']
                time_step = 1.0 / self.meta['sps']
                blk_time = np.arange(self.meta['b_length']) * time_step  # Generate an array of time steps in seconds
                for blk in self.blocks:                    
                    times.append(current_time + blk_time)
                    current_time = current_time + block_duration
                    values.append(blk['data'])


                # Concatenate all times and values for the complete data
                self.times = np.concatenate(times)      #will be an array of raw epoch seconds
                self.values = np.concatenate(values)    #will be an array of AD values

                # Later, update it like this:
                self.meta.update({
                    'num_samples': int(self.values.size),
                    'blocks_loaded': block_counter,
                    'estimated_end_epoch': round(calculated_end_time, 3),
                    'final_drift_sec': round(drift, 3)                    
                })
                
                # Save to npz
                base = os.path.splitext(os.path.basename(self.filename))[0]
                npz_path = os.path.join(os.path.dirname(self.filename), f"{base}.npz")
                np.savez_compressed(npz_path, times=self.times, values=self.values, meta=self.meta)
                self.status_label.config(text=f"Saved to {npz_path}")
                print(f"Saved to {npz_path}")

                self.plot_button.config(state='normal')

        except Exception as e:
            tb = traceback.format_exc()
            messagebox.showerror("Reading Block Error", f"Error: {e}\n\n{tb}")
            self.abort_button.config(state='disabled')



    def load_npz_file(self):
        npz_path = filedialog.askopenfilename(title="Select .npz data file", filetypes=[("NPZ Files", "*.npz")])
        if not npz_path:
            return
        try:
            data = np.load(npz_path, allow_pickle=True)
            self.times = data['times']
            self.values = data['values']

            # Properly handle meta stored as 0-d ndarray
            meta_raw = data['meta']
            self.meta = meta_raw.item() if isinstance(meta_raw, np.ndarray) else dict(meta_raw)

            # Parse the start datetime string from meta
            start_str = self.meta.get("start", "Unknown")
            info = f"Loaded: {npz_path}\n"
            if self.meta:
                info += "\n" + "\n".join([f"{k}: {v}" for k, v in self.meta.items()])

            self.set_info_text(info)
            self.plot_button.config(state='normal')

        except Exception as e:
            self.set_info_text(f"Failed to load .npz: {e}")
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
        if self.times is None or self.values is None:
            messagebox.showinfo("Info", "No data loaded.")
            return

        try:
            # Downsampling
            MAX_POINTS = 10000
            times = self.times
            values = self.values

            if len(times) != len(values):
                raise ValueError("Mismatch between times and values length")

            if len(times) > MAX_POINTS:
                step = len(times) // MAX_POINTS
                times_to_plot = times[::step]
                values_to_plot = values[::step]
            else:
                times_to_plot = times
                values_to_plot = values

            # Fallback for epoch_base
            if self.blocks:
                epoch_base = self.blocks[0]['epochtime']
            elif 'epochtime' in self.meta:
                epoch_base = float(self.meta['epochtime'])
            else:
                raise ValueError("Missing 'epochtime' in metadata and no block info available")

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

                print(f"Selected range (datetime): {t0} to {t1}")
                print(f"Selected range in seconds: {delta:.3f} seconds")

                # Convert datetime back to epoch time for comparison with times_to_plot
                t0_epoch = t0.timestamp()
                t1_epoch = t1.timestamp()

                # Mask data within selected range
                mask = (times_to_plot >= t0_epoch) & (times_to_plot <= t1_epoch)
                selected_values = np.array(values_to_plot)[mask]

                if len(selected_values) == 0:
                    return

                # Perform FFT on selected range
                N = len(selected_values)
                T = 1.0 / 2000  # Replace with actual sample rate if needed
                yf = np.fft.rfft(selected_values)
                xf = np.fft.rfftfreq(N, T)

                # Show spectrum in a new figure
                fig_spec = plt.figure(figsize=(10, 4))
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
