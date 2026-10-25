"""
region_selector.py — Interactive click-drag screen region selector
MTech Thesis: Proctoring Vulnerability Research — Phase 1

Opens a translucent fullscreen canvas. The user clicks and drags to
select a rectangular region. Returns (x, y, width, height) or None.
"""

import tkinter as tk


class RegionSelector:
    """Fullscreen semi-transparent region picker."""

    def select(self):
        """
        Block until the user selects a region (or presses ESC).
        Returns (x, y, w, h) in screen coordinates, or None if cancelled.
        """
        self._result   = None
        self._start_x  = 0
        self._start_y  = 0
        self._dragging = False
        self._rect_id  = None

        # ── Build fullscreen overlay window ──────────────────────────
        self.win = tk.Toplevel()
        self.win.attributes("-fullscreen", True)
        self.win.attributes("-topmost",    True)
        self.win.attributes("-alpha",      0.35)
        self.win.configure(bg="black")
        self.win.config(cursor="crosshair")

        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()

        self.canvas = tk.Canvas(
            self.win,
            width=sw, height=sh,
            bg="black",
            highlightthickness=0,
            cursor="crosshair",
        )
        self.canvas.pack(fill="both", expand=True)

        # Instructions
        self.canvas.create_text(
            sw // 2, 28,
            text="✦  Drag to select the exam question region  ·  ESC to cancel",
            fill="white",
            font=("Segoe UI", 13, "bold"),
            anchor="center",
        )

        # Bind events
        self.canvas.bind("<ButtonPress-1>",   self._on_press)
        self.canvas.bind("<B1-Motion>",       self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.win.bind("<Escape>",             self._on_escape)

        # Wait until closed
        self.win.grab_set()
        self.win.wait_window()
        return self._result

    # ──────────────────────────────────────────────────────────────────

    def _on_press(self, event):
        self._start_x  = event.x_root
        self._start_y  = event.y_root
        self._dragging = True

    def _on_drag(self, event):
        if not self._dragging:
            return
        if self._rect_id:
            self.canvas.delete(self._rect_id)

        x1 = min(self._start_x, event.x_root)
        y1 = min(self._start_y, event.y_root)
        x2 = max(self._start_x, event.x_root)
        y2 = max(self._start_y, event.y_root)

        # Glowing selection rectangle
        self.canvas.create_rectangle(
            x1, y1, x2, y2,
            outline="#00e5a0", width=1,
            fill="", tags="_shadow",
        )
        self._rect_id = self.canvas.create_rectangle(
            x1, y1, x2, y2,
            outline="#00ffc3", width=2,
            fill="",
        )
        # Dimensions label
        self.canvas.delete("_dim_label")
        self.canvas.create_text(
            x1 + 4, y1 - 14,
            text=f"{abs(x2-x1)} × {abs(y2-y1)} px",
            fill="#00ffc3",
            font=("Segoe UI", 9, "bold"),
            anchor="w",
            tags="_dim_label",
        )

    def _on_release(self, event):
        if not self._dragging:
            return
        self._dragging = False
        x = min(self._start_x, event.x_root)
        y = min(self._start_y, event.y_root)
        w = abs(event.x_root - self._start_x)
        h = abs(event.y_root - self._start_y)

        if w > 10 and h > 10:
            self._result = (x, y, w, h)

        self.win.destroy()

    def _on_escape(self, event):
        self._result = None
        self.win.destroy()
