import tkinter as tk
from tkinter import filedialog, messagebox
import numpy as np
import code


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

        self.shell_button = tk.Button(self.root, text="Open Shell Interactive", command=self.open_shell)
        self.shell_button.pack(pady=10)

        self.data = None
        self.extracted_vars = {}

    def load_npz_file(self):
        npz_path = filedialog.askopenfilename(title="Select .npz data file", filetypes=[("NPZ Files", "*.npz")])
        if not npz_path:
            return

        try:
            self.data = np.load(npz_path, allow_pickle=True)
            self.extracted_vars = {}  # reset extracted variables

            for widget in self.tree_frame.winfo_children():
                widget.destroy()

            # Headers
            tk.Label(self.tree_frame, text="Variable Name", width=20, anchor='w').grid(row=0, column=0)
            tk.Label(self.tree_frame, text="Type", width=15, anchor='w').grid(row=0, column=1)
            tk.Label(self.tree_frame, text="Dimensions", width=20, anchor='w').grid(row=0, column=2)

            # Variable entries
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

            self.label.config(text=f"Loaded: {npz_path}\nSelect a variable to view")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load .npz: {e}")

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


if __name__ == '__main__':
    root = tk.Tk()
    app = NPZViewerApp(root)
    root.mainloop()
