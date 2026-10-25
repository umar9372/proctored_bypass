"""
run.py - Proctoring Research Overlay
MTech Thesis Phase 1 - Self-contained single executable file.
Features:
- Screen-hidden overlay (WDA_EXCLUDEFROMCAPTURE - invisible to Zoom/Teams/OBS/Snipping Tool)
- Snip + OCR question capture
- Direct AI answers (Gemini, Claude, GPT, Ollama)
- Voice listening toggler (listens to interviewer speaking -> auto-sends to Gemini)
- Auto-clear chat input box upon response completion
- Click-through and minimize modes
- Global hotkeys
"""

import sys
import os
import io
import json
import ctypes
import platform
import threading
import tkinter as tk
from tkinter import font as tkfont

# Fix Windows console encoding
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Win32 Constants
GWL_EXSTYLE            = -20
WS_EX_TRANSPARENT      = 0x00000020
WS_EX_TOOLWINDOW       = 0x00000080
WS_EX_APPWINDOW        = 0x00040000
WDA_EXCLUDEFROMCAPTURE = 0x00000011

WINDOW_TITLE = "ResearchOverlay_MTech_2024"

BG        = "#0b0b16"
HEADER_BG = "#13132b"
PANEL     = "#111128"
INPUT_BG  = "#0f0f22"
ACCENT    = "#7c6ffa"
GREEN     = "#00e5a0"
TEXT      = "#dde0f0"
DIM       = "#666880"
RED       = "#ff5f5f"
YELLOW    = "#ffcc44"
SEP       = "#1e1e3a"


def load_config():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cfg_file = os.path.join(base_dir, "config.json")
    cfg = {
        "provider": "gemini",
        "openai_key": "",
        "openai_model": "gpt-4o-mini",
        "anthropic_key": "",
        "anthropic_model": "claude-3-5-haiku-20241022",
        "gemini_key": "",
        "gemini_model": "gemini-2.5-flash",
        "ollama_host": "http://localhost:11434",
        "ollama_model": "llama3.2",
        "system_prompt": "Answer concisely. MCQ: option first then 1 line explanation. Code: working code with brief comments."
    }
    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                d = json.load(f)
                if d.get("ai_provider"): cfg["provider"] = d["ai_provider"]
                if d.get("openai_api_key"): cfg["openai_key"] = d["openai_api_key"]
                if d.get("openai_model"): cfg["openai_model"] = d["openai_model"]
                if d.get("anthropic_api_key"): cfg["anthropic_key"] = d["anthropic_api_key"]
                if d.get("anthropic_model"): cfg["anthropic_model"] = d["anthropic_model"]
                if d.get("gemini_api_key"): cfg["gemini_key"] = d["gemini_api_key"]
                if d.get("gemini_model"):
                    m = d["gemini_model"]
                    cfg["gemini_model"] = "gemini-2.5-flash" if "1.5" in m else m
                if d.get("ollama_host"): cfg["ollama_host"] = d["ollama_host"]
                if d.get("ollama_model"): cfg["ollama_model"] = d["ollama_model"]
                if d.get("system_prompt"): cfg["system_prompt"] = d["system_prompt"]
        except Exception as e:
            print(f"Config load error: {e}")
    return cfg


def ask_ai(question, cfg, on_chunk, on_done, on_error):
    def worker():
        try:
            p = cfg.get("provider", "gemini")
            sy = cfg.get("system_prompt", "Answer concisely. MCQ: option first then 1 line explanation. Code: working code with comments.")
            if p == "gemini":
                import google.generativeai as genai
                k = cfg.get("gemini_key", "").strip()
                if not k:
                    on_error("Gemini API key is empty. Click Config to set it.")
                    return
                genai.configure(api_key=k)
                model_name = cfg.get("gemini_model", "gemini-2.5-flash")
                try:
                    m = genai.GenerativeModel(model_name, system_instruction=sy)
                    full = ""
                    for chunk in m.generate_content(question, stream=True):
                        t = getattr(chunk, "text", "") or ""
                        if t:
                            full += t
                            on_chunk(t)
                    on_done(full)
                except Exception as ex:
                    # fallback to gemini-flash-latest or gemini-2.5-pro if specific model name fails
                    if "not found" in str(ex).lower():
                        m = genai.GenerativeModel("gemini-flash-latest", system_instruction=sy)
                        full = ""
                        for chunk in m.generate_content(question, stream=True):
                            t = getattr(chunk, "text", "") or ""
                            if t:
                                full += t
                                on_chunk(t)
                        on_done(full)
                    else:
                        raise ex
            elif p == "openai":
                import openai
                c = openai.OpenAI(api_key=cfg["openai_key"])
                s = c.chat.completions.create(
                    model=cfg.get("openai_model", "gpt-4o-mini"),
                    messages=[{"role": "system", "content": sy}, {"role": "user", "content": question}],
                    stream=True
                )
                full = ""
                for chunk in s:
                    t = chunk.choices[0].delta.content or ""
                    if t:
                        full += t
                        on_chunk(t)
                on_done(full)
            elif p == "anthropic":
                import anthropic
                c = anthropic.Anthropic(api_key=cfg["anthropic_key"])
                full = ""
                with c.messages.stream(
                    model=cfg.get("anthropic_model", "claude-3-5-haiku-20241022"),
                    max_tokens=1024,
                    system=sy,
                    messages=[{"role": "user", "content": question}]
                ) as s:
                    for t in s.text_stream:
                        full += t
                        on_chunk(t)
                on_done(full)
            elif p == "ollama":
                import requests
                r = requests.post(
                    f"{cfg.get('ollama_host', 'http://localhost:11434')}/api/chat",
                    json={
                        "model": cfg.get("ollama_model", "llama3.2"),
                        "stream": True,
                        "messages": [{"role": "system", "content": sy}, {"role": "user", "content": question}]
                    },
                    stream=True,
                    timeout=60
                )
                r.raise_for_status()
                full = ""
                for line in r.iter_lines():
                    if not line:
                        continue
                    d = json.loads(line)
                    t = d.get("message", {}).get("content", "")
                    if t:
                        full += t
                        on_chunk(t)
                    if d.get("done"):
                        break
                on_done(full)
            else:
                on_error(f"Unknown provider: {p}")
        except ImportError as e:
            on_error(f"Missing dependency: {e}\nRun: pip install {str(e).split()[-1]}")
        except Exception as e:
            on_error(str(e))
    threading.Thread(target=worker, daemon=True).start()


def capture_region(x, y, w, h):
    import mss
    from PIL import Image
    with mss.mss() as sct:
        raw = sct.grab({"left": x, "top": y, "width": w, "height": h})
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


def ocr_image(img):
    try:
        import pytesseract
        return pytesseract.image_to_string(img, config="--oem 3 --psm 6").strip()
    except Exception:
        pass
    try:
        import easyocr
        import numpy as np
        r = easyocr.Reader(["en"], gpu=False, verbose=False)
        return "\n".join(r.readtext(np.array(img), detail=0, paragraph=True)).strip()
    except Exception:
        return "[OCR unavailable - pytesseract or easyocr error]"


class RegionSelector:
    def select(self):
        self._result = None
        self._sx = self._sy = 0
        self._dragging = False
        self._rid = None
        self.win = tk.Toplevel()
        self.win.attributes("-fullscreen", True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.35)
        self.win.configure(bg="black")
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.cv = tk.Canvas(self.win, bg="black", highlightthickness=0, cursor="crosshair")
        self.cv.pack(fill="both", expand=True)

        # Top banner with instruction and cancel button
        banner = tk.Frame(self.win, bg="#111124", padx=16, pady=8, highlightthickness=1, highlightbackground="#3a3a60")
        banner.place(relx=0.5, y=40, anchor="center")
        tk.Label(
            banner, text="✦ Drag mouse to select exam question  ·  ESC / Right-click to cancel",
            fg="#dde0f0", bg="#111124", font=("Segoe UI", 11, "bold")
        ).pack(side="left", padx=(0, 16))
        tk.Button(
            banner, text="✕ Cancel Snip (ESC)", command=self._cancel,
            bg="#ff4757", fg="white", relief="flat", bd=0,
            font=("Segoe UI", 9, "bold"), padx=14, pady=4, cursor="hand2",
            activebackground="#ff6b81", activeforeground="white"
        ).pack(side="left")

        self.cv.bind("<ButtonPress-1>", self._press)
        self.cv.bind("<B1-Motion>", self._drag)
        self.cv.bind("<ButtonRelease-1>", self._release)

        # Bind Escape and Right-Click to cancel
        self.win.bind_all("<Escape>", lambda _: self._cancel())
        self.cv.bind_all("<Escape>", lambda _: self._cancel())
        self.cv.bind("<ButtonPress-3>", lambda _: self._cancel())
        self.win.bind("<ButtonPress-3>", lambda _: self._cancel())
        self.win.focus_force()

        try:
            self.win.grab_set()
        except:
            pass
        self.win.wait_window()
        return self._result

    def _press(self, e):
        self._sx, self._sy, self._dragging = e.x_root, e.y_root, True

    def _drag(self, e):
        if not self._dragging:
            return
        if self._rid:
            self.cv.delete(self._rid)
        x1, y1 = min(self._sx, e.x_root), min(self._sy, e.y_root)
        x2, y2 = max(self._sx, e.x_root), max(self._sy, e.y_root)
        self.cv.delete("_l")
        self.cv.create_text(
            x1 + 4, y1 - 14,
            text=f"{x2-x1}x{y2-y1}px", fill="#00ffc3",
            font=("Segoe UI", 9, "bold"), anchor="w", tags="_l"
        )
        self._rid = self.cv.create_rectangle(x1, y1, x2, y2, outline="#00ffc3", width=2, fill="")

    def _release(self, e):
        if not self._dragging:
            return
        self._dragging = False
        x, y = min(self._sx, e.x_root), min(self._sy, e.y_root)
        w, h = abs(e.x_root - self._sx), abs(e.y_root - self._sy)
        if w > 10 and h > 10:
            self._result = (x, y, w, h)
        self._cancel()

    def _cancel(self):
        try:
            self.win.grab_release()
        except:
            pass
        try:
            self.win.destroy()
        except:
            pass


class OverlayApp:
    def __init__(self):
        self.cfg = load_config()
        self._ct = False
        self._min = False
        self._dx = self._dy = 0
        self._hwnd = None
        self._busy = False
        self._voice_on = False
        self._opacity = float(self.cfg.get("overlay_opacity", 0.85))

        self.root = tk.Tk()
        self._init()
        self._build()
        self._w32()
        self._hkeys()

    def _init(self):
        self.root.title(WINDOW_TITLE)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", self._opacity)
        self.root.overrideredirect(True)
        self.root.configure(bg=BG)
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w, h = 640, 580
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.minsize(360, 220)

    def _w32(self):
        if platform.system() != "Windows":
            return
        self.root.update()
        hwnd = ctypes.windll.user32.FindWindowW(None, WINDOW_TITLE)
        if not hwnd:
            hwnd = ctypes.windll.user32.GetAncestor(self.root.winfo_id(), 2)
        self._hwnd = hwnd
        ex = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ex = (ex | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)
        ok = bool(ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE))
        if ok:
            self._badge.config(text=" SCREEN-HIDDEN ", bg="#003d2b", fg=GREEN)
            self._log("SUCCESS: Window is invisible to Zoom / Teams / OBS / Proctoring.\n", "ok")
        else:
            self._badge.config(text=" NOT HIDDEN ", bg="#3d0000", fg=RED)
            self._log(f"Display affinity failed (err {ctypes.GetLastError()}) - Needs Win10 19041+\n", "warn")
        self._log(f"Active Provider: {self.cfg.get('provider').upper()} ({self.cfg.get('gemini_model' if self.cfg.get('provider')=='gemini' else 'ollama_model')})\n", "ok")
        self._log("-" * 52 + "\n", "sep")

    def _build(self):
        # Header
        hdr = tk.Frame(self.root, bg=HEADER_BG, height=44)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        self._dot = tk.Label(hdr, text="*", fg=GREEN, bg=HEADER_BG, font=("Segoe UI", 12, "bold"))
        self._dot.pack(side="left", padx=(10, 4), pady=8)

        tk.Label(
            hdr, text="Proctoring Research Overlay | MTech Thesis",
            fg=TEXT, bg=HEADER_BG, font=("Segoe UI", 9, "bold")
        ).pack(side="left")

        self._badge = tk.Label(hdr, text=" INIT... ", bg=YELLOW, fg="#000", font=("Segoe UI", 7, "bold"))
        self._badge.pack(side="left", padx=8)

        # Header window controls
        for txt, fg_, cmd in [("[X]", RED, self._quit), ("[-]", DIM, self._tmin), ("[T]", DIM, self._tct)]:
            b = tk.Button(
                hdr, text=txt, fg=fg_, bg=HEADER_BG, relief="flat", bd=0,
                font=("Segoe UI", 9, "bold"), cursor="hand2", padx=6, pady=4,
                activebackground=PANEL, activeforeground=fg_, command=cmd
            )
            b.pack(side="right", padx=2)
            if txt == "[T]":
                self._ctb = b

        # Opacity controller in header
        opac_frame = tk.Frame(hdr, bg=HEADER_BG)
        opac_frame.pack(side="right", padx=(2, 10))
        tk.Label(opac_frame, text="Opacity:", fg=DIM, bg=HEADER_BG, font=("Segoe UI", 8)).pack(side="left", padx=(0, 2))
        tk.Button(opac_frame, text="–", fg=TEXT, bg=PANEL, relief="flat", bd=0,
                  font=("Segoe UI", 8, "bold"), cursor="hand2", padx=5, pady=0,
                  command=lambda: self._adjust_opacity(-0.10)).pack(side="left")
        self._opac_lbl = tk.Label(opac_frame, text=f"{int(self._opacity * 100)}%",
                                  fg=GREEN, bg=PANEL, font=("Segoe UI", 8, "bold"),
                                  padx=4, pady=1, cursor="hand2")
        self._opac_lbl.pack(side="left", padx=1)
        self._opac_lbl.bind("<Button-1>", lambda e: self._cycle_opacity())
        tk.Button(opac_frame, text="+", fg=TEXT, bg=PANEL, relief="flat", bd=0,
                  font=("Segoe UI", 8, "bold"), cursor="hand2", padx=5, pady=0,
                  command=lambda: self._adjust_opacity(0.10)).pack(side="left")

        for w in [hdr] + list(hdr.winfo_children()):
            w.bind("<ButtonPress-1>", self._ds)
            w.bind("<B1-Motion>", self._dm)

        # Body
        self._body = tk.Frame(self.root, bg=BG)
        self._body.pack(fill="both", expand=True)

        # Action Buttons Toolbar
        row = tk.Frame(self._body, bg=BG)
        row.pack(fill="x", padx=10, pady=(8, 4))
        ab = dict(
            bg=PANEL, fg=TEXT, relief="flat", bd=0, font=("Segoe UI", 8, "bold"),
            cursor="hand2", padx=10, pady=6, activebackground=SEP, activeforeground=TEXT
        )

        tk.Button(row, text="Snip + OCR", command=self._snip, **ab).pack(side="left", padx=(0, 4))
        tk.Button(row, text="Ask AI", command=self._ask, **ab).pack(side="left", padx=4)

        # Voice Listening Toggle Button
        self._voice_btn = tk.Button(
            row, text="Voice: OFF", command=self._toggle_voice,
            bg=PANEL, fg=DIM, relief="flat", bd=0, font=("Segoe UI", 8, "bold"),
            cursor="hand2", padx=10, pady=6, activebackground=SEP, activeforeground=TEXT
        )
        self._voice_btn.pack(side="left", padx=4)

        tk.Button(row, text="Clear", command=self._clr, **ab).pack(side="left", padx=4)
        tk.Button(row, text="Config", command=self._cfg_dlg, **ab).pack(side="right")

        # Response Area
        mono = next((f for f in ["Cascadia Code", "JetBrains Mono", "Consolas", "Courier New"]
                     if f in tkfont.families()), "Courier New")
        self._resp = tk.Text(
            self._body, bg=INPUT_BG, fg=TEXT, font=(mono, 9),
            relief="flat", bd=0, padx=10, pady=8, wrap="word", state="disabled",
            selectbackground=ACCENT, insertbackground=TEXT, spacing1=2, spacing3=3
        )
        self._resp.pack(fill="both", expand=True, padx=10, pady=(0, 4))

        for tag, fg_, fnt in [
            ("ok", GREEN, (mono, 8)),
            ("warn", YELLOW, (mono, 8)),
            ("sep", SEP, (mono, 8)),
            ("q", ACCENT, ("Segoe UI", 9, "bold")),
            ("ai", TEXT, None),
            ("err", RED, (mono, 8))
        ]:
            kw = {"foreground": fg_}
            if fnt:
                kw["font"] = fnt
            self._resp.tag_config(tag, **kw)

        # Input Area (Chatbox)
        inf = tk.Frame(self._body, bg=PANEL)
        inf.pack(fill="x", padx=10, pady=(0, 4))
        self._inp = tk.Text(
            inf, bg=INPUT_BG, fg=TEXT, font=("Segoe UI", 9), relief="flat", bd=0,
            padx=8, pady=8, height=3, wrap="word", insertbackground=TEXT
        )
        self._inp.pack(fill="x")
        self._inp.insert("1.0", "Type question or toggle Voice / Snip...")
        self._inp.bind("<FocusIn>", self._if)
        self._inp.bind("<Control-Return>", lambda _: self._ask())

        # Status Bar and Corner Resize Grip
        self._sb_frame = tk.Frame(self.root, bg="#08080f")
        self._sb_frame.pack(fill="x", side="bottom")

        self._sb = tk.Label(
            self._sb_frame,
            text="  Snip: Ctrl+Alt+S | Ask: Ctrl+Alt+A | Voice: Ctrl+Alt+V | Opacity: Ctrl+Alt+[/] | ESC to cancel snip",
            fg=DIM, bg="#08080f", font=("Segoe UI", 7), anchor="w", padx=8
        )
        self._sb.pack(side="left", fill="x", expand=True)

        self._grip = tk.Label(
            self._sb_frame, text="◢", fg=ACCENT, bg="#08080f",
            font=("Segoe UI", 10, "bold"), cursor="size_nw_se", padx=4
        )
        self._grip.pack(side="right")
        self._grip.bind("<ButtonPress-1>", self._on_resize_start)
        self._grip.bind("<B1-Motion>", self._on_resize_drag)

        # Right and bottom edge resize handles
        self._r_edge = tk.Frame(self.root, bg="#1a1a36", width=4, cursor="size_we")
        self._r_edge.place(relx=1.0, rely=0, relheight=1.0, anchor="ne")
        self._r_edge.bind("<ButtonPress-1>", self._on_resize_x_start)
        self._r_edge.bind("<B1-Motion>", self._on_resize_x_drag)

        self._b_edge = tk.Frame(self.root, bg="#1a1a36", height=4, cursor="size_ns")
        self._b_edge.place(relx=0, rely=1.0, relwidth=1.0, anchor="sw")
        self._b_edge.bind("<ButtonPress-1>", self._on_resize_y_start)
        self._b_edge.bind("<B1-Motion>", self._on_resize_y_drag)

    # Voice Toggle & Listener
    def _toggle_voice(self):
        self._voice_on = not self._voice_on
        if self._voice_on:
            self._voice_btn.config(text="Voice: ON (Listening)", fg=GREEN, bg="#0d2b1a")
            self._st("Voice ON - Listening to interviewer. Speak question...")
            threading.Thread(target=self._voice_loop, daemon=True).start()
        else:
            self._voice_on = False
            self._voice_btn.config(text="Voice: OFF", fg=DIM, bg=PANEL)
            self._st("Voice listener stopped.")

    def _stop_voice(self):
        self._voice_on = False
        self._voice_btn.config(text="Voice: OFF", fg=DIM, bg=PANEL)

    def _voice_loop(self):
        try:
            import speech_recognition as sr
        except Exception as e:
            self.root.after(0, lambda: self._st(f"Voice err: {e}"))
            self.root.after(0, self._stop_voice)
            return

        r = sr.Recognizer()
        r.dynamic_energy_threshold = True
        r.pause_threshold = 1.0

        try:
            mic = sr.Microphone()
        except Exception as e:
            self.root.after(0, lambda: self._st(f"Mic err: {e}"))
            self.root.after(0, self._stop_voice)
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
                        self.root.after(0, lambda: self._st("Voice: Listening for speech..."))
                        audio = r.listen(source, timeout=3, phrase_time_limit=25)
                        if not self._voice_on:
                            break
                        self.root.after(0, lambda: self._st("Voice: Transcribing speech..."))
                        text = r.recognize_google(audio)
                        text = text.strip() if text else ""
                        if text and len(text) >= 3 and self._voice_on and not self._busy:
                            self.root.after(0, lambda t=text: self._on_voice_heard(t))
                    except sr.WaitTimeoutError:
                        continue
                    except sr.UnknownValueError:
                        continue
                    except Exception as e:
                        if self._voice_on:
                            self.root.after(0, lambda err=str(e): self._st(f"Voice info: {err[:35]}"))
                        import time
                        time.sleep(0.5)
        except Exception as e:
            self.root.after(0, lambda: self._st(f"Mic error: {e}"))
            self.root.after(0, self._stop_voice)

    def _on_voice_heard(self, text):
        if not text or self._busy:
            return
        self._si(text)
        self._st(f"Heard: {text[:45]}...")
        self._ask()

    # Question actions
    def _snip(self):
        self._st("Select region with mouse drag...")
        def do():
            try:
                r = RegionSelector().select()
                if r:
                    img = capture_region(*r)
                    t = ocr_image(img)
                    if t:
                        self.root.after(0, lambda: self._si(t))
                        self.root.after(0, lambda: self._st(f"OCR extracted {len(t)} chars."))
                    else:
                        self.root.after(0, lambda: self._st("No text found in selected region."))
                else:
                    self.root.after(0, lambda: self._st("Region selection cancelled."))
            except Exception as e:
                self.root.after(0, lambda: self._st(f"Error: {e}"))
        threading.Thread(target=do, daemon=True).start()

    def _ask(self):
        q = self._inp.get("1.0", "end").strip()
        if not q or q.startswith("Type question"):
            self._st("Input box is empty! Type question or use Voice / Snip.")
            return
        # Clear input box immediately so user can type next question right away
        self._inp.delete("1.0", "end")
        self._busy = True
        self._st("AI generating answer...")
        self._dot.config(fg=YELLOW)
        self._log(f"\nQ: {q}\n", "q")
        self._log("-" * 52 + "\n", "sep")

        def oc(t):
            self.root.after(0, lambda: self._log(t, "ai"))

        def od(_):
            self.root.after(0, self._ad)

        def oe(e):
            self.root.after(0, lambda: self._oe(e))

        ask_ai(q, self.cfg, oc, od, oe)

    def _ad(self):
        self._busy = False
        self._log("\n" + "-" * 52 + "\n", "sep")
        self._st("Answer complete!")
        self._dot.config(fg=GREEN)
        # Requirement 1: Clear the chatbox when response comes from Gemini!
        self._inp.delete("1.0", "end")

    def _oe(self, e):
        self._busy = False
        self._log(f"\nERROR: {e}\n", "err")
        self._dot.config(fg=RED)
        self._st(f"Error: {e[:40]}")

    def _clr(self):
        self._resp.config(state="normal")
        self._resp.delete("1.0", "end")
        self._resp.config(state="disabled")
        self._inp.delete("1.0", "end")
        self._st("Cleared.")

    def _cfg_dlg(self):
        w = tk.Toplevel(self.root)
        w.title("Config")
        w.geometry("440x490")
        w.configure(bg=BG)
        w.attributes("-topmost", True)
        tk.Label(w, text="AI Provider Settings", fg=TEXT, bg=BG, font=("Segoe UI", 12, "bold")).pack(pady=12)

        fields = [
            ("Provider", "provider", ["gemini", "openai", "anthropic", "ollama"]),
            ("Gemini Key", "gemini_key", None),
            ("Gemini Model", "gemini_model", None),
            ("OpenAI Key", "openai_key", None),
            ("Anthropic Key", "anthropic_key", None),
            ("Ollama Host", "ollama_host", None),
            ("Ollama Model", "ollama_model", None)
        ]
        entries = {}
        for lbl, key, opts in fields:
            r = tk.Frame(w, bg=BG)
            r.pack(fill="x", padx=20, pady=3)
            tk.Label(r, text=lbl, fg=DIM, bg=BG, font=("Segoe UI", 8), width=14, anchor="w").pack(side="left")
            if opts:
                var = tk.StringVar(value=self.cfg.get(key, opts[0]))
                om = tk.OptionMenu(r, var, *opts)
                om.config(bg=PANEL, fg=TEXT, relief="flat")
                om["menu"].config(bg=PANEL, fg=TEXT)
                om.pack(side="left", fill="x", expand=True)
            else:
                var = tk.StringVar(value=self.cfg.get(key, ""))
                tk.Entry(
                    r, textvariable=var, bg=PANEL, fg=TEXT, insertbackground=TEXT,
                    relief="flat", bd=0, font=("Segoe UI", 8)
                ).pack(side="left", fill="x", expand=True, ipady=5)
            entries[key] = var

        def save():
            for k, v in entries.items():
                self.cfg[k] = v.get().strip()
            # Save to config.json
            base_dir = os.path.dirname(os.path.abspath(__file__))
            cfg_file = os.path.join(base_dir, "config.json")
            try:
                save_data = {
                    "ai_provider": self.cfg.get("provider", "gemini"),
                    "gemini_api_key": self.cfg.get("gemini_key", ""),
                    "gemini_model": self.cfg.get("gemini_model", "gemini-2.5-flash"),
                    "openai_api_key": self.cfg.get("openai_key", ""),
                    "openai_model": self.cfg.get("openai_model", "gpt-4o-mini"),
                    "anthropic_api_key": self.cfg.get("anthropic_key", ""),
                    "anthropic_model": self.cfg.get("anthropic_model", "claude-3-5-haiku-20241022"),
                    "ollama_host": self.cfg.get("ollama_host", "http://localhost:11434"),
                    "ollama_model": self.cfg.get("ollama_model", "llama3.2"),
                    "system_prompt": self.cfg.get("system_prompt", "")
                }
                with open(cfg_file, "w", encoding="utf-8") as f:
                    json.dump(save_data, f, indent=4)
            except Exception as e:
                print(f"Failed to write config.json: {e}")
            w.destroy()
            self._st("Config saved!")

        tk.Button(
            w, text="Save Settings", command=save, bg=ACCENT, fg="white", relief="flat", bd=0,
            font=("Segoe UI", 10, "bold"), padx=20, pady=8, cursor="hand2"
        ).pack(pady=16)

    def _tct(self):
        if not self._hwnd:
            return
        self._ct = not self._ct
        ex = ctypes.windll.user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE)
        if self._ct:
            ex |= WS_EX_TRANSPARENT
            self._ctb.config(fg=ACCENT)
            self._st("Click-through ON")
        else:
            ex &= ~WS_EX_TRANSPARENT
            self._ctb.config(fg=DIM)
            self._st("Click-through OFF")
        ctypes.windll.user32.SetWindowLongW(self._hwnd, GWL_EXSTYLE, ex)

    def _tmin(self):
        if self._min:
            self._body.pack(fill="both", expand=True)
            self._sb.pack(fill="x", side="bottom")
            self.root.geometry("640x580")
        else:
            self._body.pack_forget()
            self._sb.pack_forget()
            self.root.geometry("640x44")
        self._min = not self._min

    def _tv(self):
        a = self.root.attributes("-alpha")
        self.root.attributes("-alpha", 0 if a > 0 else 1.0)

    def _ds(self, e):
        self._dx = e.x_root - self.root.winfo_x()
        self._dy = e.y_root - self.root.winfo_y()

    def _dm(self, e):
        self.root.geometry(f"+{e.x_root-self._dx}+{e.y_root-self._dy}")

    def _st(self, m):
        self._sb.config(text=f"  {m}")

    def _si(self, t):
        self._inp.delete("1.0", "end")
        self._inp.insert("1.0", t)

    def _if(self, _):
        val = self._inp.get("1.0", "end").strip()
        if val.startswith("Type question"):
            self._inp.delete("1.0", "end")

    def _log(self, t, tag="ai"):
        self._resp.config(state="normal")
        self._resp.insert("end", t, tag)
        self._resp.see("end")
        self._resp.config(state="disabled")

    def _set_opacity(self, val):
        self._opacity = round(max(0.15, min(1.0, val)), 2)
        self.root.attributes("-alpha", self._opacity)
        if hasattr(self, "_opac_lbl"):
            self._opac_lbl.config(text=f"{int(self._opacity * 100)}%")
        self._st(f"Opacity set to {int(self._opacity * 100)}%")

    def _adjust_opacity(self, delta):
        self._set_opacity(self._opacity + delta)

    def _cycle_opacity(self):
        presets = [1.0, 0.80, 0.60, 0.40, 0.20]
        cur = round(self._opacity, 2)
        next_val = presets[0]
        for p in presets:
            if p < cur - 0.05:
                next_val = p
                break
        self._set_opacity(next_val)

    def _on_resize_start(self, event):
        self._rs_x = event.x_root
        self._rs_y = event.y_root
        self._rs_w = self.root.winfo_width()
        self._rs_h = self.root.winfo_height()

    def _on_resize_drag(self, event):
        dw = event.x_root - self._rs_x
        dh = event.y_root - self._rs_y
        nw = max(340, self._rs_w + dw)
        nh = max(220, self._rs_h + dh)
        cur_x = self.root.winfo_x()
        cur_y = self.root.winfo_y()
        self.root.geometry(f"{nw}x{nh}+{cur_x}+{cur_y}")

    def _on_resize_x_start(self, event):
        self._rs_x = event.x_root
        self._rs_w = self.root.winfo_width()

    def _on_resize_x_drag(self, event):
        dw = event.x_root - self._rs_x
        nw = max(340, self._rs_w + dw)
        cur_h = self.root.winfo_height()
        cur_x = self.root.winfo_x()
        cur_y = self.root.winfo_y()
        self.root.geometry(f"{nw}x{cur_h}+{cur_x}+{cur_y}")

    def _on_resize_y_start(self, event):
        self._rs_y = event.y_root
        self._rs_h = self.root.winfo_height()

    def _on_resize_y_drag(self, event):
        dh = event.y_root - self._rs_y
        nh = max(220, self._rs_h + dh)
        cur_w = self.root.winfo_width()
        cur_x = self.root.winfo_x()
        cur_y = self.root.winfo_y()
        self.root.geometry(f"{cur_w}x{nh}+{cur_x}+{cur_y}")

    def _hkeys(self):
        def run():
            try:
                import keyboard
                keyboard.add_hotkey("ctrl+alt+s", self._snip)
                keyboard.add_hotkey("ctrl+alt+a", self._ask)
                keyboard.add_hotkey("ctrl+alt+v", self._toggle_voice)
                keyboard.add_hotkey("ctrl+alt+[", lambda: self._adjust_opacity(-0.10))
                keyboard.add_hotkey("ctrl+alt+]", lambda: self._adjust_opacity(0.10))
                keyboard.add_hotkey("ctrl+alt+o", self._cycle_opacity)
                keyboard.add_hotkey("ctrl+alt+h", self._tv)
                keyboard.add_hotkey("ctrl+alt+t", self._tct)
                keyboard.add_hotkey("ctrl+alt+q", self._quit)
                keyboard.wait()
            except Exception as e:
                print(f"Hotkeys: {e}")
        threading.Thread(target=run, daemon=True).start()

    def _quit(self):
        try:
            import keyboard
            keyboard.unhook_all_hotkeys()
        except:
            pass
        self._voice_on = False
        self.root.quit()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    print("Starting Proctoring Research Overlay...")
    OverlayApp().run()
