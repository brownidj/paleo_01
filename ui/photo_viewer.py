import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, UnidentifiedImageError
import os

class PhotoViewer(tk.Toplevel):
    """
    An integrated photo viewer window.
    """
    def __init__(self, parent, photo_path, caption=""):
        super().__init__(parent)
        self.title(f"Photo Viewer - {os.path.basename(photo_path)}")
        self.geometry("800x600")
        self.photo_path = photo_path
        
        # Main container
        self.container = ttk.Frame(self)
        self.container.pack(fill=tk.BOTH, expand=True)
        
        # Label for caption
        if caption:
            ttk.Label(self.container, text=caption, wraplength=700).pack(pady=5)
        
        # Canvas for the image to support resizing and potentially zooming later
        self.canvas = tk.Canvas(self.container, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.image = None
        self.tk_image = None
        
        # Load and display the image
        self.load_image()
        
        # Bind resize event
        self.bind("<Configure>", self.on_resize)
        
        # Add a close button at the bottom
        ttk.Button(self.container, text="Close", command=self.destroy).pack(pady=5)

    def load_image(self):
        try:
            self.image = Image.open(self.photo_path)
            self.display_image()
        except (FileNotFoundError, PermissionError, OSError, UnidentifiedImageError) as e:
            ttk.Label(self.canvas, text=f"Error loading image: {str(e)}", foreground="red").pack(expand=True)

    def display_image(self):
        if not self.image:
            return
            
        # Get canvas dimensions
        self.update_idletasks()
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width < 10 or canvas_height < 10:
            canvas_width = 800
            canvas_height = 500
            
        # Calculate scaling to fit the canvas while maintaining aspect ratio
        img_width, img_height = self.image.size
        ratio = min(canvas_width / img_width, canvas_height / img_height)
        
        new_width = int(img_width * ratio)
        new_height = int(img_height * ratio)
        
        if new_width > 0 and new_height > 0:
            resized_image = self.image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            self.tk_image = ImageTk.PhotoImage(resized_image)
            
            self.canvas.delete("all")
            self.canvas.create_image(canvas_width // 2, canvas_height // 2, anchor=tk.CENTER, image=self.tk_image)

    def on_resize(self, event):
        # Debounce or just resize
        if event.widget == self:
            self.display_image()
