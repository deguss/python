import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import struct
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.dates import AutoDateLocator, DateFormatter
from matplotlib.widgets import SpanSelector
from datetime import timedelta, datetime, timezone

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

    def set_info_text(self, content):
        self.info_text.config(state='normal')
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(tk.END, content + "\n")
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
                estimated_end_day = end_time.strftime('%Y-%m-%d')
                estimated_end_time = end_time.strftime('%H:%M')

                log_summary = "\n".join([f"{k}: {v}" for k, v in self.meta.items()]) if self.meta else "No .txt log info"
                header_info = (
                    f"Header:\n  length={length}, sps={sps}, time={epochtime}, gain={gain}, channel={channel}, res16={res16}\n"
                    f"blocks: {estimated_blocks}, File size: {filesize // (1024 * 1024)} MB\n"
                    f"start date & time:  {start_time_str}\n"
                    f"Estimated end time: {estimated_end_day} {estimated_end_time}\n"
                    f"Estimated file duration: {total_duration}\n"   
                )

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
        """Convert epoch time (seconds since 1981-08-26 00:00:27 UTC) to datetime object."""
        #start_date = datetime(1981, 8, 26, 0, 0, 27, tzinfo=timezone.utc)  # Base start date
        start_date = datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)  # Base start date
        return start_date + timedelta(seconds=epochtime)


    def read_blocks_thread(self):
        self.blocks = []
        filesize = os.path.getsize(self.filename)
        read_bytes = 0
        block_counter = 0

        self.status_label.config(text="Reading file...")
        self.progress.config(maximum=filesize)

        try:
            with open(self.filename, 'rb') as f:
                # Read first header for metadata
                header = f.read(HEADER_SIZE)
                if len(header) != HEADER_SIZE:
                    raise ValueError("File too short or corrupted")
                length, sps, epochtime, gain, channel, res16 = struct.unpack(FIXED_FORMAT_STR, header)
                self.meta = {
                    'length': length,
                    'sps': sps,
                    'gain': gain,
                    'channel': channel,
                    'res16': res16
                }

                # Compute and store start time
                corrected_epoch = epochtime - length / sps
                dt_start = self.epoch_to_datetime(corrected_epoch)
                self.start_day = dt_start.strftime('%Y-%m-%d')
                self.start_time = dt_start.strftime('%H:%M')
                self.meta['start_day'] = self.start_day
                self.meta['start_time'] = self.start_time

                f.seek(0)  # Go back to start for full read

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
                    if (block_counter > 1): #dismiss first block (as they are from an earlier time
                        
                        self.blocks.append({
                            'length': length,
                            'sps': sps,
                            'epochtime': epochtime,
                            'gain': gain,
                            'channel': channel,
                            'res16': res16,
                            'data': data
                        })


                        if block_counter % 10 == 0 or read_bytes >= filesize:
                            self.progress["value"] = read_bytes
                            self.master.update_idletasks()
                            self.status_label.config(text=f"Loaded {read_bytes // 1024} KB")

            if self.abort_flag:
                self.status_label.config(text="Loading aborted.")
                self.abort_button.config(state='disabled')
                return

            self.status_label.config(text=f"Done. Loaded {block_counter} blocks.")
            self.abort_button.config(state='disabled')

            # Convert blocks to arrays
            times = []
            values = []
            for blk in self.blocks:
                time_step = 1.0 / blk['sps']
                start_time = blk['epochtime']
                blk_time = np.arange(blk['length']) * time_step
                times.append(blk_time)
                values.append(blk['data'])
            self.times = np.concatenate(times)
            self.values = np.concatenate(values)

            # Save to npz
            base = os.path.splitext(os.path.basename(self.filename))[0]
            npz_path = os.path.join(os.path.dirname(self.filename), f"{base}.npz")
            np.savez_compressed(npz_path, times=self.times, values=self.values, meta=self.meta)
            self.status_label.config(text=f"Saved to {npz_path}")
            print(f"Saved to {npz_path}")

            self.plot_button.config(state='normal')

        except Exception as e:
            self.status_label.config(text=f"Error: {e}")
            self.abort_button.config(state='disabled')

    def load_npz_file(self):
        npz_path = filedialog.askopenfilename(title="Select .npz data file", filetypes=[("NPZ Files", "*.npz")])
        if not npz_path:
            return
        try:
            data = np.load(npz_path, allow_pickle=True)
            self.times = data['times']
            self.values = data['values']
            self.meta = data['meta'].item() if isinstance(data['meta'], np.ndarray) else data['meta']
            self.start_day = self.meta.get("start_day", "Unknown Date")
            self.start_time = self.meta.get("start_time", "Unknown Time")
            info = f"Loaded: {npz_path}\nStart: {self.start_day} {self.start_time}"
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

        # Convert epochtime (seconds since 1981-08-26 00:00:27 UTC) to datetime objects
        try:
            # Convert relative time to absolute epoch using the base epoch from first block
            epoch_base = self.blocks[0]['epochtime']
            times_dt = [self.epoch_to_datetime(epoch_base + t) for t in times_to_plot]

            start_dt = times_dt[0]
            end_dt = times_dt[-1]            
            title_str = f"Start: {start_dt.strftime('%Y-%m-%d %H:%M:%S')} — End: {end_dt.strftime('%H:%M:%S')}"
            print(title_str)

            MAX_POINTS = 100000  # Plotting more than this isn't useful for humans
            if len(self.times) > MAX_POINTS:
                step = len(self.times) // MAX_POINTS
                times_to_plot = self.times[::step]
                values_to_plot = self.values[::step]
            else:
                times_to_plot = self.times
                values_to_plot = self.values

            times_dt = [self.epoch_to_datetime(t) for t in times_to_plot]

            # Plotting
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.plot(times_dt, values_to_plot)
            ax.set_title(title_str)
            ax.set_xlabel("Time (UTC)")
            ax.set_ylabel("ADC Value")

            locator = AutoDateLocator()
            formatter = DateFormatter('%H:%M')
            ax.xaxis.set_major_locator(locator)
            ax.xaxis.set_major_formatter(formatter)
            ax.tick_params(axis='x', rotation=45)

            ax.grid(which='major', linestyle='-', linewidth=0.7)
            ax.grid(which='minor', linestyle=':', linewidth=0.5)
            ax.minorticks_on()

            # Maximize window
            figManager = plt.get_current_fig_manager()
            try:
                figManager.window.state('zoomed')
            except AttributeError:
                try:
                    figManager.full_screen_toggle()
                except AttributeError:
                    pass

            def onselect(xmin, xmax):
                # Convert time back to epoch seconds
                t0 = mdates.date2num(xmin)
                t1 = mdates.date2num(xmax)
                mask = (mdates.date2num(times_dt) >= t0) & (mdates.date2num(times_dt) <= t1)

                selected_values = values_to_plot[mask]
                if len(selected_values) == 0:
                    return

                # Compute and plot FFT
                N = len(selected_values)
                T = 1.0 / 2000  # default sample rate; could be dynamic from block
                yf = np.fft.rfft(selected_values)
                xf = np.fft.rfftfreq(N, T)

                plt.figure(figsize=(10, 4))
                plt.plot(xf, 20 * np.log10(np.abs(yf) + 1e-12))  # dB scale
                plt.title("Spectrum of Selected Region")
                plt.xlabel("Frequency (Hz)")
                plt.ylabel("Magnitude (dB)")
                plt.grid(True, which='both')
                plt.tight_layout()
                plt.show()

            span = SpanSelector(ax, onselect, 'horizontal', useblit=True,
                                props=dict(alpha=0.5, facecolor='red'), interactive=True)

            plt.tight_layout()
            plt.show()

        except Exception as e:
            messagebox.showerror("Plotting Error", f"Error during plotting: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = BinPlotterApp(root)
    root.mainloop()
