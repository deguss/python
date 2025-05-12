import matplotlib.pyplot as plt
import numpy as np
import struct
import os
import tkinter as tk
from tkinter import filedialog

FIXED_FORMAT_STR = '<HHIBBH'  # Binary header format
HEADER_SIZE = struct.calcsize(FIXED_FORMAT_STR)

def read_log_file(log_filename):
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

def load_all_blocks(filename):
    data_blocks = []
    with open(filename, 'rb') as f:
        while True:
            header = f.read(HEADER_SIZE)
            if len(header) != HEADER_SIZE:
                break
            length, sps, epochtime, gain, channel, res16 = struct.unpack(FIXED_FORMAT_STR, header)
            data = np.fromfile(f, dtype=np.int32, count=length)
            if len(data) != length:
                print("Warning: Incomplete data block detected, skipping.")
                break
            block = {
                'length': length,
                'sps': sps,
                'epochtime': epochtime,
                'gain': gain,
                'channel': channel,
                'res16': res16,
                'data': data
            }
            data_blocks.append(block)
    return data_blocks

def plot_blocks(blocks, start_day, start_time):
    if not blocks:
        print("No valid data blocks to plot.")
        return

    times = []
    values = []

    ref_sps = blocks[0]['sps']
    ref_ch = blocks[0]['channel']
    current_time = blocks[0]['epochtime']

    for i, blk in enumerate(blocks):
        time_step = 1.0 / blk['sps']
        blk_time = np.arange(blk['length']) * time_step + blk['epochtime']
        
        if blk['sps'] != ref_sps or blk['channel'] != ref_ch:
            print(f"Inconsistent block at index {i}, skipping or separating not yet implemented.")
            continue

        if i > 0:
            expected_next_time = blocks[i - 1]['epochtime'] + blocks[i - 1]['length'] / ref_sps
            time_gap = blk['epochtime'] - expected_next_time
            if time_gap > 2:
                print(f"Gap of {time_gap:.2f}s detected between blocks {i-1} and {i}, inserting NaNs.")
                gap_samples = int(time_gap * ref_sps)
                times.append(np.arange(gap_samples) * time_step + current_time)
                values.append(np.full(gap_samples, np.nan))
                current_time += time_gap

        times.append(blk_time)
        values.append(blk['data'])
        current_time = blk_time[-1] + time_step

        expected_duration = blk['length'] / blk['sps']
        print(f"Block {i}: time={blk['epochtime']}, samples={blk['length']}, "
              f"duration={expected_duration:.2f}s, sps={blk['sps']}")

    full_time = np.concatenate(times)
    full_data = np.concatenate(values)

    fig = plt.figure()
    manager = plt.get_current_fig_manager()
    try:
        manager.full_screen_toggle()
    except AttributeError:
        manager.window.state('zoomed')
    plt.plot(full_time, full_data)
    plt.xlabel("Time (seconds since epoch)")
    plt.ylabel("ADC Value")
    plt.title(f"CH={ref_ch}, SPS={ref_sps}, Start={start_day} {start_time}")
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def main():
    root = tk.Tk()
    root.withdraw()

    bin_file = filedialog.askopenfilename(title="Select binary data file", filetypes=[("Binary Files", "*.bin")])
    if not bin_file:
        print("No binary file selected.")
        return

    txt_file = os.path.splitext(bin_file)[0] + ".txt"
    log_info = read_log_file(txt_file) if os.path.exists(txt_file) else {}

    start_day = log_info.get("start_day", "Unknown Date")
    start_time = log_info.get("start_time", "Unknown Time")

    blocks = load_all_blocks(bin_file)
    plot_blocks(blocks, start_day, start_time)

if __name__ == "__main__":
    main()
