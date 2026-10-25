"""
config.py — Configuration manager
MTech Thesis: Proctoring Vulnerability Research — Phase 1
"""

import json
import os

DEFAULT_CONFIG = {
    # ── AI Provider ──────────────────────────────────────────────────
    # Supported: "openai" | "gemini" | "ollama"
    "ai_provider": "gemini",

    "openai_api_key": "",
    "openai_model": "gpt-4o-mini",

    "gemini_api_key": "AIzaSyC3gKpIkfeyAOiprQRtxO0t_omo-KCJiT0",
    "gemini_model": "gemini-2.5-flash",

    # Ollama — local & free. Run: ollama pull llama3.2
    "ollama_host": "http://localhost:11434",
    "ollama_model": "llama3.2",

    # ── Overlay UI ───────────────────────────────────────────────────
    "overlay_opacity": 0.90,
    "overlay_width": 540,
    "overlay_height": 500,
    "overlay_capture_hidden": False,

    # ── AI Behaviour ─────────────────────────────────────────────────
    "system_prompt": (
        "You are a precise academic assistant. Answer questions concisely and correctly. "
        "For MCQ questions, state the correct option first, then a 1-2 line explanation. "
        "For coding questions, give working code with brief comments. "
        "For math/theory, be direct and show key steps only."
    ),
}


class Config:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.data = DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.data.update(json.load(f))
            except Exception:
                pass

    def save(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except IOError as e:
            print(f"[Config] Save error: {e}")

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value):
        self.data[key] = value
        self.save()
