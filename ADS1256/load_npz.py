import tkinter as tk
from tkinter import filedialog, messagebox
import numpy as np


class NPZViewerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NPZ Viewer")

        # Create a label for instructions
        self.label = tk.Label(self.root, text="Select a .npz file to view its variables", font=("Arial", 14))
        self.label.pack(pady=10)

        # Button to load .npz file
        self.load_button = tk.Button(self.root, text="Load .npz File", command=self.load_npz_file)
        self.load_button.pack(pady=10)

        # Table-like structure to display variables
        self.tree_frame = tk.Frame(self.root)
        self.tree_frame.pack(pady=10)

        # Textbox to display the content of the selected variable
        self.textbox = tk.Text(self.root, width=50, height=10, wrap=tk.WORD)
        self.textbox.pack(pady=10)

        # To store loaded data
        self.data = None

    def load_npz_file(self):
        npz_path = filedialog.askopenfilename(title="Select .npz data file", filetypes=[("NPZ Files", "*.npz")])
        if not npz_path:
            return

        try:
            # Load the .npz file
            self.data = np.load(npz_path, allow_pickle=True)

            # Clear the tree frame
            for widget in self.tree_frame.winfo_children():
                widget.destroy()

            # Add table headers
            tk.Label(self.tree_frame, text="Variable Name", width=20, anchor='w').grid(row=0, column=0)
            tk.Label(self.tree_frame, text="Type", width=15, anchor='w').grid(row=0, column=1)
            tk.Label(self.tree_frame, text="Dimensions", width=20, anchor='w').grid(row=0, column=2)

            # Add variable names, types, and dimensions in the table-like structure
            for idx, key in enumerate(self.data.files):
                var = self.data[key]
                var_type = type(var).__name__

                # Check for special handling of ndarray containing a dictionary (e.g., 'meta')
                if isinstance(var, np.ndarray) and var.dtype.kind in 'O':  # dtype.kind 'O' means object
                    var_shape = "N/A"  # Do not show dimensions for object arrays
                else:
                    var_shape = str(var.shape) if isinstance(var, np.ndarray) else "N/A"

                # Create clickable labels for each variable name
                var_name_label = tk.Label(self.tree_frame, text=key, anchor='w', fg="blue", cursor="hand2")
                var_name_label.grid(row=idx + 1, column=0)
                var_name_label.bind(
                    "<Button-1>", lambda e, key=key: self.show_variable_content(key)
                )

                # Show the type and dimensions next to the name
                tk.Label(self.tree_frame, text=var_type, anchor='w').grid(row=idx + 1, column=1)
                tk.Label(self.tree_frame, text=var_shape, anchor='w').grid(row=idx + 1, column=2)

            self.label.config(text=f"Loaded: {npz_path}\nSelect a variable to view")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load .npz: {e}")

    def show_variable_content(self, key):
        variable_content = self.data[key]

        # Handle special case for object arrays (like 'meta')
        if isinstance(variable_content, np.ndarray) and variable_content.dtype.kind in 'O':
            # If it's an object array, assume it's a dictionary or other structured object
            preview = variable_content.item()  # Extract the object (e.g., a dict)
            if isinstance(preview, dict):
                preview = "\n".join([f"{k}: {v}" for k, v in preview.items()])  # Display keys and values
        else:
            # Truncate arrays to 10 elements for preview
            if isinstance(variable_content, np.ndarray):
                preview = variable_content.tolist()[:10]
            else:
                preview = variable_content

        # Display the content in the textbox
        self.textbox.delete(1.0, tk.END)
        self.textbox.insert(tk.END, f"Content of '{key}':\n{preview}\n\nType: {type(variable_content).__name__}\nShape: {getattr(variable_content, 'shape', 'N/A')}")

        # Print variable content to shell for interaction
        print(f"Content of {key}: {preview}")


if __name__ == '__main__':
    # Create the Tkinter root window
    root = tk.Tk()
    app = NPZViewerApp(root)

    # Start the Tkinter event loop
    root.mainloop()
