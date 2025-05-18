import tkinter as tk
from tkinter import filedialog, messagebox
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, timezone
import code
import traceback


class NPZViewerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NPZ Viewer")

        # GUI layout
        self.label = tk.Label(self.root, text="Select a .npz file to view its variables", font=("Arial", 14))
        self.label.pack(pady=10)

        self.load_button = tk.Button(self.root, text="Load .npz File", command=self.load_npz_file)
        self.load_button.pack(pady=10)

        self.tree_frame = tk.Frame(self.root)
        self.tree_frame.pack(pady=10)

        self.textbox = tk.Text(self.root, width=50, height=10, wrap=tk.WORD)
        self.textbox.pack(pady=10)
        self.textbox.bind('<Control-c>', self.copy)

        self.shell_button = tk.Button(self.root, text="Open Shell Interactive", command=self.open_shell)
        self.shell_button.pack(pady=10)      

        self.data = None
        self.extracted_vars = {}
        self.meta = None  # Initialize meta variable

    def copy(self, event=None):
        self.root.clipboard_clear()
        text = self.textbox.get("sel.first", "sel.last")
        self.root.clipboard_append(text)
        return 'break'        

    def load_npz_file(self):
        npz_path = filedialog.askopenfilename(title="Select .npz data file", filetypes=[("NPZ Files", "*.npz")])
        if not npz_path:
            return

        try:
            self.data = np.load(npz_path, allow_pickle=True)
            self.extracted_vars = {}  # reset extracted variables
            self.meta = None  # Reset meta before loading

            # Check if 'meta' exists in the file
            if 'meta' in self.data:
                self.meta = self.data['meta'].item()  # Assuming 'meta' is a dictionary
                print(f"Meta loaded: {self.meta}")  # Debugging line to check the contents of 'meta'


            for widget in self.tree_frame.winfo_children():
                widget.destroy()

            # Headers
            tk.Label(self.tree_frame, text="Variable Name", width=20, anchor='w').grid(row=0, column=0)
            tk.Label(self.tree_frame, text="Type", width=15, anchor='w').grid(row=0, column=1)
            tk.Label(self.tree_frame, text="Dimensions", width=20, anchor='w').grid(row=0, column=2)

            # Variable entries
            flag_analyze = False
            for idx, key in enumerate(self.data.files):
                var = self.data[key]
                var_type = type(var).__name__
                var_shape = str(var.shape) if isinstance(var, np.ndarray) and var.dtype.kind != 'O' else "N/A"

                # Store for shell access
                if isinstance(var, np.ndarray) and var.dtype.kind == 'O':
                    self.extracted_vars[key] = var.item()
                else:
                    self.extracted_vars[key] = var

                lbl = tk.Label(self.tree_frame, text=key, anchor='w', fg="blue", cursor="hand2")
                lbl.grid(row=idx + 1, column=0)
                lbl.bind("<Button-1>", lambda e, key=key: self.show_variable_content(key))

                tk.Label(self.tree_frame, text=var_type, anchor='w').grid(row=idx + 1, column=1)
                tk.Label(self.tree_frame, text=var_shape, anchor='w').grid(row=idx + 1, column=2)

                if key == "values":
                    self.values = var
                    if min(self.values) == 1 and max(self.values) == 2:
                        print("test signal pattern detected!")
                        flag_analyze = True

            self.label.config(text=f"Loaded: {npz_path}\nSelect a variable to view")

            if flag_analyze:
                self.analyze_test_signal()

        except Exception as e:
            tb = traceback.format_exc()
            messagebox.showerror("Error", f"Failed to load .npz: {e}\n\n{tb}")

    def show_variable_content(self, key):
        variable_content = self.data[key]

        if isinstance(variable_content, np.ndarray) and variable_content.dtype.kind == 'O':
            preview = variable_content.item()
            if isinstance(preview, dict):
                preview = "\n".join([f"{k}: {v}" for k, v in preview.items()])
        elif isinstance(variable_content, np.ndarray):
            preview = variable_content.tolist()[:10]
        else:
            preview = variable_content

        self.textbox.delete(1.0, tk.END)
        self.textbox.insert(tk.END, f"Content of '{key}':\n{preview}\n\nType: {type(variable_content).__name__}\nShape: {getattr(variable_content, 'shape', 'N/A')}")
        print(f"Content of {key}: {preview}")

    def open_shell(self):
        if not self.extracted_vars:
            print("No data loaded to interact with.")
            return
        banner = "Interactive Shell\nAvailable variables:\n" + ", ".join(self.extracted_vars.keys())
        print(banner)
        code.interact(banner=banner, local=self.extracted_vars)

    def analyze_test_signal(self):
        # Access meta data like sps
        sps = self.meta.get('sps', None)
        b_length = self.meta.get('b_length', None)
        epochtime = self.meta.get('epochtime', None)
        if sps is None or b_length is None or epochtime is None:
            print("Warning: metadata not complete")
            return
            
        # Identify rising/falling edges
        edges = np.where(np.diff(self.values) != 0)[0]
        intervals = np.diff(edges)

        # Basic analysis
        mean_interval = np.mean(intervals)        
        std_interval = np.std(intervals)
        abnormal = np.where(np.abs(intervals - mean_interval) > 2 * std_interval)[0]
        abnormal_values = intervals[abnormal]

        # Display results
        print("Mean interval:", mean_interval)
        print("Abnormal intervals:", abnormal_values)
        print("        at blocks:", abnormal)

        # Optional: visualize intervals to spot anomalies
        plt.figure(figsize=(12, 4))
        plt.plot(intervals,'o')
        plt.title("Transition intervals")
        plt.xlabel("Transition index")
        plt.ylabel("Interval length")        
        plt.grid(True)
        plt.show()

        # Optional: visualize intervals to spot anomalies
        plt.figure(figsize=(12, 4))
        s1=(abnormal[0]-6)*b_length
        s2=(abnormal[0]+6)*b_length
        plt.plot(np.arange(s1, s2), self.values[s1:s2])
        plt.title("Signal at irregularity")
        plt.xlabel("signal")
        plt.ylabel("# of block")
        plt.grid(True)
        
        
        t_rel = (abnormal*b_length) / sps
        print(f"happens at seconds {t_rel}")
        print(f"         diff(t) = {np.diff(t_rel)}")
        # Convert to absolute datetimes
        absolute_times = [datetime.fromtimestamp(epochtime + t, tz=timezone.utc) for t in t_rel]
        # Format and print
        for abs_time in absolute_times:
            print(abs_time.strftime("%H:%M:%S"))
        
        plt.show()
        
        

        

if __name__ == '__main__':
    import numpy as np
    import matplotlib.pyplot as plt
    root = tk.Tk()
    app = NPZViewerApp(root)
    root.mainloop()
