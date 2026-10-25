"""
overlay.py — The transparent, screen-capture-invisible overlay window
MTech Thesis: Proctoring Vulnerability Research — Phase 1

──────────────────────────────────────────────────────────────────────
KEY SECURITY RESEARCH CONCEPTS DEMONSTRATED:
──────────────────────────────────────────────────────────────────────
1. SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)
   → Window is rendered to physical monitor via DWM (Desktop Window Manager)
   → But completely OMITTED from any capture surface/framebuffer exposed
     to other apps — invisible to Zoom, Teams, OBS, Snipping Tool,
     BitBlt, DXGI Desktop Duplication, and Windows Graphics Capture APIs.
   → Requires Windows 10 build 19041 (2004) or later.

2. WS_EX_TOOLWINDOW
   → Hides overlay from Alt+Tab switcher and Taskbar.
   → Proctoring software that enumerates visible windows won't find it.

3. WS_EX_TRANSPARENT (click-through mode)
   → Mouse events pass THROUGH the overlay to the application below.
   → Candidate can interact normally with the exam while viewing answers.

4. overrideredirect(True)
   → Removes all OS window decorations (title bar, border).
   → No process name appears in window title bar.
──────────────────────────────────────────────────────────────────────
"""

import ctypes
import ctypes.wintypes
import platform
import queue
import threading
import tkinter as tk
from tkinter import font as tkfont

from .ai_engine       import AIEngine
from .config          import Config
from .hotkeys         import HotkeyManager
from .region_selector import RegionSelector
from .screen_reader   import ScreenReader

# ── Win32 Constants ───────────────────────────────────────────────────
GWL_EXSTYLE           = -20
WS_EX_LAYERED         = 0x00080000
WS_EX_TRANSPARENT     = 0x00000020   # Click-through
WS_EX_TOOLWINDOW      = 0x00000080   # Hide from Alt+Tab / Taskbar
WS_EX_APPWINDOW       = 0x00040000
WDA_EXCLUDEFROMCAPTURE = 0x00000011  # THE KEY FLAG — invisible to screen capture

# Unique internal title used to locate the HWND via FindWindowW
_WINDOW_TITLE = "ProctoringResearch_PoC_Phase1_v1"


class TransparentOverlay:

    # ── Colour palette ────────────────────────────────────────────────
    C = {
        "bg":          "#0b0b16",
        "header":      "#13132b",
        "panel":       "#111128",
        "input_bg":    "#0f0f22",
        "accent":      "#7c6ffa",
        "accent2":     "#00e5a0",
        "text":        "#dde0f0",
        "dim":         "#666880",
        "danger":      "#ff5f5f",
        "warning":     "#ffcc44",
        "separator":   "#1e1e3a",
    }

    def __init__(self):
        self.config         = Config()
        self.screen_reader  = ScreenReader()
        self.ai_engine      = AIEngine(self.config)
        self.hotkey_manager = HotkeyManager()

        self._msg_queue        = queue.Queue()
        self._is_click_through = False
        self._is_minimised     = False
        self._drag_ox          = 0
        self._drag_oy          = 0
        self._hwnd             = None
        self._capture_excluded = False
        self._voice_on         = False
        self._busy             = False

        self.root = tk.Tk()
        self._setup_window()
        self._build_ui()
        self._apply_win32_magic()
        self._setup_hotkeys()
        self._poll_queue()

    # ══════════════════════════════════════════════════════════════════
    # Window setup
    # ══════════════════════════════════════════════════════════════════

    def _setup_window(self):
        C = self.C
        self.root.title(_WINDOW_TITLE)
        self.root.attributes("-topmost",  True)
        self.root.attributes("-alpha",    self.config.get("overlay_opacity", 0.90))
        self.root.overrideredirect(True)    # No title bar / border
        self.root.configure(bg=C["bg"])

        sw = self.root.winfo_screenwidth()
        w  = self.config.get("overlay_width",  540)
        h  = self.config.get("overlay_height", 500)
        x  = sw - w - 18
        y  = 40
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.minsize(320, 220)
        self.root.lift()
        self.root.focus_force()

    # ══════════════════════════════════════════════════════════════════
    # Win32 API — The core vulnerability demonstration
    # ══════════════════════════════════════════════════════════════════

    def _apply_win32_magic(self):
        """
        RESEARCH NOTE:
        This method applies the Win32 API calls that make this window
        completely invisible to screen-capture software while remaining
        fully visible on the physical monitor.

        The capture-hiding behavior is intentionally off by default so the
        overlay remains visible while you are developing/debugging the app.
        Set overlay_capture_hidden to True in config.json to enable the
        research effect.
        """
        if platform.system() != "Windows":
            self._append("⚠ Win32 API unavailable on this OS.\n", "warn")
            return

        self.root.update()  # Ensure the OS window is actually created

        # ── Step 1: Locate the HWND ───────────────────────────────────
        hwnd = ctypes.windll.user32.FindWindowW(None, _WINDOW_TITLE)
        if not hwnd:
            # Fallback: use tkinter's winfo_id()
            hwnd = ctypes.windll.user32.GetAncestor(self.root.winfo_id(), 2)
        self._hwnd = hwnd

        # ── Step 2: Modify extended window style ──────────────────────
        user32   = ctypes.windll.user32
        ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)

        # Always make the window interactive by default. The click-through
        # feature is an opt-in troubleshooting mode used only when the user
        # explicitly toggles it. This avoids the overlay swallowing mouse/keyboard
        # input as soon as the app starts.
        ex_style &= ~WS_EX_TRANSPARENT
        ex_style |= WS_EX_TOOLWINDOW
        ex_style &= ~WS_EX_APPWINDOW
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)

        if not self.config.get("overlay_capture_hidden", False):
            self._capture_excluded = False
            self._is_click_through = False
            self._ct_btn.config(fg=self.C["dim"])
            self._badge.config(text="◉ VISIBLE MODE", fg=self.C["warning"])
            self._append(
                "✔  Overlay is visible on screen.\n"
                "   Capture-hiding mode is OFF by default for debugging purposes.\n"
                "   Set overlay_capture_hidden to true in config.json to enable WDA_EXCLUDEFROMCAPTURE.\n"
                "   Click-through is disabled by default so the UI accepts mouse and keyboard input.\n",
                "sys_ok",
            )
            self._append("─" * 56 + "\n", "sep")
            return

        # ── Step 3: EXCLUDE FROM SCREEN CAPTURE ──────────────────────
        # WDA_EXCLUDEFROMCAPTURE = 0x00000011
        # DWM renders this window normally on the physical display,
        # but reports a BLACK rectangle (or omits entirely) to any
        # application that tries to capture/record the screen.
        # Blocked APIs: BitBlt, PrintWindow, DXGI, WGC, OBS, Zoom,
        #               Teams, Meet, Snipping Tool, Print Screen
        ok = bool(user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE))
        self._capture_excluded = ok

        # Update UI badge
        if ok:
            self._badge.config(text="◉ SCREEN-HIDDEN", fg=self.C["accent2"])
            self._append(
                "✔  SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE) — SUCCESS\n"
                "   This window is NOW invisible to:\n"
                "   • Zoom / Teams / Meet / Discord screen share\n"
                "   • OBS Studio, Bandicam, any recorder\n"
                "   • Windows Snipping Tool & Print Screen\n"
                "   • All BitBlt / DXGI / WGC capture APIs\n"
                "   • Proctoring software (ProctorU, ExamSoft, etc.)\n",
                "sys_ok",
            )
        else:
            err = ctypes.GetLastError()
            self._badge.config(text="⚠ CAPTURE NOT HIDDEN", fg=self.C["danger"])
            self._append(
                f"✘  SetWindowDisplayAffinity FAILED (error {err})\n"
                "   Requires Windows 10 build 19041 (version 2004) or later.\n",
                "warn",
            )

        self._append("─" * 56 + "\n", "sep")

    # ══════════════════════════════════════════════════════════════════
    # UI Construction
    # ══════════════════════════════════════════════════════════════════

    def _build_ui(self):
        C = self.C

        # ── Header ────────────────────────────────────────────────────
        hdr = tk.Frame(self.root, bg=C["header"], height=38)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)

        # Status dot
        self._dot = tk.Label(hdr, text="●", fg=C["accent2"], bg=C["header"],
                             font=("Segoe UI", 10))
        self._dot.pack(side="left", padx=(10, 3), pady=9)

        tk.Label(hdr, text="Overlay Research PoC — MTech Thesis",
                 fg=C["text"], bg=C["header"],
                 font=("Segoe UI", 9, "bold")).pack(side="left")

        # Capture-exclusion badge
        self._badge = tk.Label(hdr, text="◉ INITIALISING...",
                               fg=C["warning"], bg=C["header"],
                               font=("Segoe UI", 7, "bold"))
        self._badge.pack(side="left", padx=8)

        # Right-side controls
        btn = dict(bg=C["header"], relief="flat", bd=0,
                   font=("Segoe UI", 12), cursor="hand2", padx=6, pady=3)
        tk.Button(hdr, text="✕", fg=C["danger"],
                  command=self._on_close,          **btn).pack(side="right", padx=4)
        tk.Button(hdr, text="–", fg=C["dim"],
                  command=self._toggle_minimise,   **btn).pack(side="right")
        self._ct_btn = tk.Button(hdr, text="⊙", fg=C["dim"],
                                 command=self._toggle_click_through, **btn)
        self._ct_btn.pack(side="right")

        # Make header draggable
        for w in [hdr] + hdr.winfo_children():
            w.bind("<ButtonPress-1>",  self._drag_start)
            w.bind("<B1-Motion>",      self._drag_move)

        # Status bar at bottom
        self._status = tk.Label(
            self.root,
            text=" Ready  |  Ctrl+Alt+S: Snip  |  Ctrl+Alt+A: Ask AI  |  Ctrl+Alt+H: Hide/Show",
            fg=C["dim"], bg="#09090f",
            font=("Segoe UI", 7), anchor="w", padx=8,
        )
        self._status.pack(fill="x", side="bottom")

        # ── Body ──────────────────────────────────────────────────────
        self._body = tk.Frame(self.root, bg=C["bg"])
        self._body.pack(fill="both", expand=True)

        # Action buttons row
        row = tk.Frame(self._body, bg=C["bg"])
        row.pack(fill="x", side="top", padx=10, pady=(8, 4))

        ab = dict(bg=C["panel"], fg=C["text"], relief="flat", bd=0,
                  font=("Segoe UI", 8, "bold"), cursor="hand2",
                  padx=12, pady=6,
                  activebackground="#1e1e3a", activeforeground=C["text"])
        tk.Button(row, text="📷  Snip + OCR", command=self._snip, **ab).pack(side="left", padx=(0, 4))
        tk.Button(row, text="🤖  Ask AI",     command=self._ask,  **ab).pack(side="left", padx=4)
        self._voice_btn = tk.Button(row, text="🎤 Voice: OFF", command=self._toggle_voice, **ab)
        self._voice_btn.pack(side="left", padx=4)
        tk.Button(row, text="🗑  Clear",      command=self._clear, **ab).pack(side="left", padx=4)
        tk.Button(row, text="⚙  Config",     command=self._config_dialog,
                  **ab).pack(side="right")

        # ── Input box (pinned at the bottom of the body) ──────────────
        in_frame = tk.Frame(self._body, bg=C["bg"])
        in_frame.pack(fill="x", side="bottom", padx=10, pady=(4, 8))

        inp_header = tk.Frame(in_frame, bg=C["bg"])
        inp_header.pack(fill="x", pady=(0, 3))
        tk.Label(
            inp_header,
            text="INPUT / QUESTION",
            fg=C["accent"],
            bg=C["bg"],
            font=("Segoe UI", 8, "bold"),
        ).pack(side="left")
        tk.Label(
            inp_header,
            text="Ctrl+Enter to send",
            fg=C["dim"],
            bg=C["bg"],
            font=("Segoe UI", 7),
        ).pack(side="right")

        self._inp = tk.Text(
            in_frame,
            bg="#141b36", fg="#eaf0ff",
            font=("Segoe UI", 10), relief="flat", bd=1,
            padx=10, pady=8, height=3, wrap="word",
            insertbackground="#ffffff",
            highlightthickness=1,
            highlightbackground="#3a4474",
            highlightcolor="#7c6ffa",
        )
        self._inp.pack(fill="x")
        self._inp.bind("<Control-Return>", lambda _e: self._ask())
        self.root.after(150, self._inp.focus_set)

        # ── Response text area (expands in remaining space) ───────────
        mono = next(
            (f for f in ["Cascadia Code", "JetBrains Mono", "Consolas", "Courier New"]
             if f in tkfont.families()),
            "Courier New",
        )
        self._resp = tk.Text(
            self._body,
            bg=C["input_bg"], fg=C["text"],
            font=(mono, 9),
            relief="flat", bd=1, padx=10, pady=8,
            wrap="word", state="disabled",
            selectbackground=C["accent"],
            insertbackground=C["text"],
            highlightthickness=1,
            highlightbackground="#2a3258",
            highlightcolor="#7c6ffa",
            spacing1=2, spacing3=3,
        )
        self._resp.pack(fill="both", expand=True, side="top", padx=10, pady=(0, 4))

        # Text colour tags
        self._resp.tag_config("ai",     foreground=C["text"])
        self._resp.tag_config("sys_ok", foreground=C["accent2"],  font=(mono, 8))
        self._resp.tag_config("warn",   foreground=C["warning"],   font=(mono, 8))
        self._resp.tag_config("error",  foreground=C["danger"],    font=(mono, 8))
        self._resp.tag_config("q",      foreground=C["accent"],    font=("Segoe UI", 9, "bold"))
        self._resp.tag_config("sep",    foreground=C["separator"], font=(mono, 8))

    # ══════════════════════════════════════════════════════════════════
    # Actions
    # ══════════════════════════════════════════════════════════════════

    def _ui_call(self, fn, *args, **kwargs):
        """Thread-safe UI dispatcher: schedules execution on Tkinter's main thread."""
        self._msg_queue.put(lambda: fn(*args, **kwargs))

    def _poll_queue(self):
        try:
            while True:
                task = self._msg_queue.get_nowait()
                task()
        except queue.Empty:
            pass
        self.root.after(30, self._poll_queue)

    def _snip(self):
        """Open region selector → OCR → populate input box."""
        self._set_status("⌛ Select screen region …")

        def do():
            try:
                sel = RegionSelector()
                region = sel.select()
                if region:
                    x, y, w, h = region
                    img  = self.screen_reader.capture_region(x, y, w, h)
                    text = self.screen_reader.extract_text(img)
                    if text:
                        self._ui_call(self._set_input, text)
                        self._ui_call(self._set_status, f"✔ OCR complete — {len(text)} chars extracted")
                    else:
                        self._ui_call(self._set_status, "⚠ No text detected in region")
                else:
                    self._ui_call(self._set_status, "Cancelled")
            except Exception as e:
                self._ui_call(self._set_status, f"Error: {e}")

        threading.Thread(target=do, daemon=True).start()

    def _toggle_voice(self):
        self._voice_on = not self._voice_on
        if self._voice_on:
            self._voice_btn.config(text="🎤 Voice: ON (Listening)", fg=self.C["accent2"], bg="#0d2b1a")
            self._set_status("🎤 Voice ON - Listening to interviewer. Speak question...")
            threading.Thread(target=self._voice_loop, daemon=True).start()
        else:
            self._voice_on = False
            self._voice_btn.config(text="🎤 Voice: OFF", fg=self.C["text"], bg=self.C["panel"])
            self._set_status("🎤 Voice listener stopped.")

    def _stop_voice(self):
        self._voice_on = False
        self._voice_btn.config(text="🎤 Voice: OFF", fg=self.C["text"], bg=self.C["panel"])

    def _voice_loop(self):
        try:
            import speech_recognition as sr
        except Exception as e:
            self._ui_call(self._set_status, f"Voice error: {e}")
            self._ui_call(self._stop_voice)
            return

        r = sr.Recognizer()
        r.dynamic_energy_threshold = True
        r.pause_threshold = 1.0

        try:
            mic = sr.Microphone()
        except Exception as e:
            self._ui_call(self._set_status, f"Mic error: {e}")
            self._ui_call(self._stop_voice)
            return

        try:
            with mic as source:
                r.adjust_for_ambient_noise(source, duration=0.6)
                while self._voice_on:
                    if self._busy:
                        import time
                        time.sleep(0.4)
                        continue
                    try:
                        self._ui_call(self._set_status, "🎤 Voice: Listening for speech...")
                        audio = r.listen(source, timeout=3, phrase_time_limit=25)
                        if not self._voice_on:
                            break
                        self._ui_call(self._set_status, "🎤 Voice: Transcribing speech...")
                        text = r.recognize_google(audio)
                        text = text.strip() if text else ""
                        if text and len(text) >= 3 and self._voice_on and not self._busy:
                            self._ui_call(self._on_voice_heard, text)
                    except sr.WaitTimeoutError:
                        continue
                    except sr.UnknownValueError:
                        continue
                    except Exception as e:
                        if self._voice_on:
                            self._ui_call(self._set_status, f"Voice: {str(e)[:35]}")
                        import time
                        time.sleep(0.5)
        except Exception as e:
            self._ui_call(self._set_status, f"Mic error: {e}")
            self._ui_call(self._stop_voice)

    def _on_voice_heard(self, text):
        if not text or self._busy:
            return
        self._set_input(text)
        self._set_status(f"🎤 Heard: {text[:45]}...")
        self._ask()

    def _ask(self):
        """Send current input to AI engine and stream the response."""
        q = self._inp.get("1.0", "end").strip()
        if not q:
            self._set_status("⚠ Enter a question first")
            return

        # CLEAR IMMEDIATELY ON CLICKING ASK AI:
        self._inp.delete("1.0", "end")
        self._busy = True

        self._set_status("🤖 AI thinking …")
        self._dot.config(fg=self.C["warning"])
        self._append(f"\n❓  {q}\n", "q")
        self._append("─" * 48 + "\n", "sep")

        def on_chunk(tok):
            self._ui_call(self._append, tok, "ai")

        def on_done(_full):
            self._busy = False
            self._ui_call(self._ai_done)

        def on_error(msg):
            self._busy = False
            def handle_err():
                self._append(f"\n⚠ {msg}\n", "error")
                self._dot.config(fg=self.C["danger"])
                self._set_status(f"Error: {msg}")
            self._ui_call(handle_err)

        self.ai_engine.ask(q, on_chunk, on_done, on_error)

    def _ai_done(self):
        self._busy = False
        self._append("\n" + "─" * 48 + "\n", "sep")
        self._set_status("✔ Response complete")
        self._dot.config(fg=self.C["accent2"])
        # Clear input box on response completion
        self._inp.delete("1.0", "end")

    def _clear(self):
        self._resp.config(state="normal")
        self._resp.delete("1.0", "end")
        self._resp.config(state="disabled")
        self._inp.delete("1.0", "end")

    # ══════════════════════════════════════════════════════════════════
    # Window behaviour
    # ══════════════════════════════════════════════════════════════════

    def _toggle_click_through(self):
        """
        RESEARCH NOTE: WS_EX_TRANSPARENT
        When enabled, all mouse events (clicks, scroll, hover) pass
        THROUGH the overlay to whatever window is underneath.
        The candidate can interact normally with their exam.
        """
        if not self._hwnd:
            return
        self._is_click_through = not self._is_click_through
        ex = ctypes.windll.user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE)
        if self._is_click_through:
            ex |= WS_EX_TRANSPARENT
            self._ct_btn.config(fg=self.C["accent"])
            self._set_status("Click-through ON — mouse passes through overlay")
        else:
            ex &= ~WS_EX_TRANSPARENT
            self._ct_btn.config(fg=self.C["dim"])
            self._set_status("Click-through OFF — overlay is interactive")
        ctypes.windll.user32.SetWindowLongW(self._hwnd, GWL_EXSTYLE, ex)

    def _toggle_minimise(self):
        if self._is_minimised:
            self._status.pack(fill="x", side="bottom")
            self._body.pack(fill="both", expand=True)
            w = self.config.get("overlay_width",  540)
            h = self.config.get("overlay_height", 500)
            self.root.geometry(f"{w}x{h}")
        else:
            self._body.pack_forget()
            self._status.pack_forget()
            self.root.geometry(f"{self.config.get('overlay_width', 540)}x38")
        self._is_minimised = not self._is_minimised

    def _toggle_visibility(self):
        cur = self.root.attributes("-alpha")
        self.root.attributes("-alpha", 0 if cur > 0 else self.config.get("overlay_opacity", 0.90))

    def _drag_start(self, ev):
        self._drag_ox = ev.x_root - self.root.winfo_x()
        self._drag_oy = ev.y_root - self.root.winfo_y()

    def _drag_move(self, ev):
        self.root.geometry(f"+{ev.x_root - self._drag_ox}+{ev.y_root - self._drag_oy}")

    # ══════════════════════════════════════════════════════════════════
    # Config dialog
    # ══════════════════════════════════════════════════════════════════

    def _config_dialog(self):
        C = self.C
        win = tk.Toplevel(self.root)
        win.title("Configuration — Proctoring Research PoC")
        win.geometry("430x540")
        win.configure(bg=C["bg"])
        win.attributes("-topmost", True)

        tk.Label(win, text="⚙  Configuration",
                 fg=C["text"], bg=C["bg"],
                 font=("Segoe UI", 13, "bold")).pack(pady=(18, 6))
        tk.Label(win, text="Set your AI provider & API key, then save.",
                 fg=C["dim"], bg=C["bg"],
                 font=("Segoe UI", 9)).pack(pady=(0, 14))

        # Provider dropdown
        provider_var = tk.StringVar(value=self.config.get("ai_provider", "ollama"))
        fields_data = [
            ("AI Provider",      "ai_provider",      None,
             ["openai", "anthropic", "gemini", "ollama"]),
            ("OpenAI API Key",   "openai_api_key",   None, None),
            ("OpenAI Model",     "openai_model",     None, None),
            ("Anthropic Key",    "anthropic_api_key", None, None),
            ("Anthropic Model",  "anthropic_model",  None, None),
            ("Gemini API Key",   "gemini_api_key",   None, None),
            ("Gemini Model",     "gemini_model",     None, None),
            ("Ollama Host",      "ollama_host",      None, None),
            ("Ollama Model",     "ollama_model",     None, None),
        ]

        lf = tk.Frame(win, bg=C["bg"])
        lf.pack(fill="x", padx=20)
        entries = {}

        for label, key, _, opts in fields_data:
            row = tk.Frame(lf, bg=C["bg"])
            row.pack(fill="x", pady=3)
            tk.Label(row, text=label, fg=C["dim"], bg=C["bg"],
                     font=("Segoe UI", 8), width=16, anchor="w").pack(side="left")
            if opts:
                var = tk.StringVar(value=self.config.get(key, opts[0]))
                om  = tk.OptionMenu(row, var, *opts)
                om.config(bg=C["panel"], fg=C["text"], relief="flat",
                          activebackground=C["separator"],
                          font=("Segoe UI", 8))
                om["menu"].config(bg=C["panel"], fg=C["text"],
                                  activebackground=C["accent"])
                om.pack(side="left", fill="x", expand=True)
            else:
                var = tk.StringVar(value=self.config.get(key, ""))
                e   = tk.Entry(row, textvariable=var,
                               bg=C["panel"], fg=C["text"],
                               insertbackground=C["text"],
                               relief="flat", bd=0, font=("Segoe UI", 8))
                e.pack(side="left", fill="x", expand=True, ipady=4)
            entries[key] = var

        def save_cfg():
            for k, v in entries.items():
                self.config.set(k, v.get())
            win.destroy()
            self._set_status("✔ Configuration saved")

        tk.Button(win, text="  Save  ", command=save_cfg,
                  bg=C["accent"], fg="white", relief="flat", bd=0,
                  font=("Segoe UI", 10, "bold"),
                  padx=24, pady=10, cursor="hand2",
                  activebackground="#5a4fcc").pack(pady=20)

    # ══════════════════════════════════════════════════════════════════
    # Hotkeys
    # ══════════════════════════════════════════════════════════════════

    def _setup_hotkeys(self):
        hm = self.hotkey_manager
        hm.register("ctrl+alt+s", self._snip)
        hm.register("ctrl+alt+a", self._ask)
        hm.register("ctrl+alt+v", self._toggle_voice)
        hm.register("ctrl+alt+h", self._toggle_visibility)
        hm.register("ctrl+alt+t", self._toggle_click_through)
        hm.register("ctrl+alt+q", self._on_close)
        hm.start()

    # ══════════════════════════════════════════════════════════════════
    # Utility
    # ══════════════════════════════════════════════════════════════════

    def _append(self, text: str, tag: str = "ai"):
        self._resp.config(state="normal")
        self._resp.insert("end", text, tag)
        self._resp.see("end")
        self._resp.config(state="disabled")

    def _set_status(self, msg: str):
        self._status.config(text=f"  {msg}")

    def _set_input(self, text: str):
        self._inp.delete("1.0", "end")
        self._inp.insert("1.0", text)

    def _inp_focus(self, _ev):
        cur = self._inp.get("1.0", "end").strip()
        if cur.startswith("Type your question"):
            self._inp.delete("1.0", "end")

    def _on_close(self):
        self.hotkey_manager.stop()
        self.root.quit()
        self.root.destroy()

    # ══════════════════════════════════════════════════════════════════
    # Run
    # ══════════════════════════════════════════════════════════════════

    def run(self):
        self.root.mainloop()
