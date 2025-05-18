import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import struct
import os
import numpy as np
import matplotlib.pyplot as plt

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

        txt_file = os.path.splitext(self.filename)[0] + ".txt"
        self.meta = self.read_log_file(txt_file) if os.path.exists(txt_file) else {}

        if self.meta:
            log_summary = "\n".join([f"{k}: {v}" for k, v in self.meta.items()])
            self.set_info_text(f"Log file found:\n{log_summary}")
        else:
            # If no log, read the first block header to show info
            try:
                filesize = os.path.getsize(self.filename)
                with open(self.filename, 'rb') as f:
                    header = f.read(HEADER_SIZE)
                    if len(header) != HEADER_SIZE:
                        raise ValueError("File too short or corrupted")
                    length, sps, epochtime, gain, channel, res16 = struct.unpack(FIXED_FORMAT_STR, header)

                    block_size = HEADER_SIZE + (length * 4)
                    estimated_blocks = filesize // block_size

                    header_info = (
                        f"Header:\n"
                        f"  length = {length}, sps = {sps}, epochtime = {epochtime}\n"
                        f"  gain = {gain}, channel = {channel}, res16 = {res16}\n"
                        f"Estimated blocks = {estimated_blocks}, File size = {filesize // (1024 * 1024)} MB"
                    )
                    self.set_info_text(header_info)
            except Exception as e:
                self.set_info_text(f"Failed to read file header: {e}")
                return

        threading.Thread(target=self.read_blocks_thread).start()

    def read_blocks_thread(self):
        self.blocks = []
        filesize = os.path.getsize(self.filename)
        read_bytes = 0
        block_counter = 0

        self.status_label.config(text="Reading file...")
        self.progress.config(maximum=filesize)

        txt_file = os.path.splitext(self.filename)[0] + ".txt"
        self.meta = self.read_log_file(txt_file) if os.path.exists(txt_file) else {}
        self.start_day = self.meta.get("start_day", "Unknown Date")
        self.start_time = self.meta.get("start_time", "Unknown Time")

        try:
            with open(self.filename, 'rb') as f:
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

                    self.blocks.append({
                        'length': length,
                        'sps': sps,
                        'epochtime': epochtime,
                        'gain': gain,
                        'channel': channel,
                        'res16': res16,
                        'data': data
                    })

                    block_counter += 1
                    if block_counter % 10 == 0 or read_bytes >= filesize:
                        self.progress["value"] = read_bytes
                        self.master.update_idletasks()
                        self.status_label.config(text=f"Loaded {read_bytes // 1024} KB")

            if self.abort_flag:
                self.status_label.config(text="Loading aborted.")
                self.abort_button.config(state='disabled')
                return

            self.status_label.config(text=f"Done. Loaded {block_counter} blocks.")
            self.plot_button.config(state='normal')
            self.abort_button.config(state='disabled')

            # Save to .npz
            hhmm = os.path.splitext(os.path.basename(self.filename))[0][-4:]
            npz_path = os.path.join(os.path.dirname(self.filename), f"{hhmm}.npz")
            times = []
            values = []
            for blk in self.blocks:
                time_step = 1.0 / blk['sps']
                blk_time = np.arange(blk['length']) * time_step + blk['epochtime']
                times.append(blk_time)
                values.append(blk['data'])
            self.times = np.concatenate(times)
            self.values = np.concatenate(values)
            np.savez_compressed(npz_path, times=self.times, values=self.values, meta=self.meta)
            print(f"Saved to {npz_path}")

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

        plt.figure()
        plt.plot(self.times, self.values)
        plt.xlabel("Time (s)")
        plt.ylabel("ADC Value")
        plt.title(f"Start={self.start_day} {self.start_time}")
        plt.grid(True)
        plt.tight_layout()
        plt.show()

if __name__ == "__main__":
    root = tk.Tk()
    app = BinPlotterApp(root)
    root.mainloop()
