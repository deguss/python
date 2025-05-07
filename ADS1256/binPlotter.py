import matplotlib.pyplot as plt
import numpy as np
from tkinter import filedialog
import tkinter as tk
import os

# Function to read the log file and extract information
def read_log_file(log_filename):
    log_info = {}
    
    # Read the log file line by line
    with open(log_filename, 'r') as file:
        for line in file:
            if line.startswith("start="):
                log_info["start"] = line.strip().split("=")[1]
            elif line.startswith("SPS="):
                log_info["SPS"] = int(line.strip().split("=")[1])
            elif line.startswith("CH="):
                log_info["CH"] = int(line.strip().split("=")[1])
    
    return log_info

# Function to open and load binary data file
def load_bin_file(filename):
    # Read binary file (assume the data is 32-bit integers)
    data = np.fromfile(filename, dtype=np.int32)
    return data

# Function to plot the data
def plot_data(data, sps, ch, start_time):
    # Create the x-axis (time in seconds)
    time = np.arange(len(data)) / sps  # Time in seconds

    # Create the plot
    plt.plot(time, data)
    plt.xlabel('Time (seconds)')
    plt.ylabel('Data Value')
    plt.title(f"CH={ch}, SPS={sps}Hz, Start={start_time}")
    plt.grid(True)
    plt.show()

# Function to get the log file and bin file, and then plot the data
def main():
    # Create a tkinter root window (to be hidden)
    root = tk.Tk()
    root.withdraw()

    # Open a file dialog to select the log file
    log_file = filedialog.askopenfilename(title="Select log file", filetypes=[("Text Files", "*.txt")])
    if not log_file:
        print("No log file selected!")
        return

    # Open a file dialog to select the bin file
    bin_file = filedialog.askopenfilename(title="Select binary data file", filetypes=[("Binary Files", "*.bin")])
    if not bin_file:
        print("No binary data file selected!")
        return

    # Read the log file
    log_info = read_log_file(log_file)
    if "SPS" not in log_info or "CH" not in log_info or "start" not in log_info:
        print("Log file is missing necessary keys (SPS, CH, start)")
        return

    # Extract information from log
    sps = log_info["SPS"]
    ch = log_info["CH"]
    start_time = log_info["start"]

    # Load the binary data file
    data = load_bin_file(bin_file)

    # Plot the data
    plot_data(data, sps, ch, start_time)

if __name__ == "__main__":
    main()
