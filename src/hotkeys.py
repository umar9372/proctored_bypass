"""
hotkeys.py — Global hotkey manager (works even when overlay is click-through)
MTech Thesis: Proctoring Vulnerability Research — Phase 1
"""

import threading


class HotkeyManager:
    def __init__(self):
        self._bindings: dict = {}
        self._active   = False

    def register(self, hotkey: str, callback):
        """Register a global hotkey (e.g. 'ctrl+alt+s')."""
        self._bindings[hotkey] = callback

    def start(self):
        """Start listening in a background daemon thread."""
        self._active = True
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def stop(self):
        self._active = False
        try:
            import keyboard
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────────

    def _run(self):
        try:
            import keyboard
            for hk, cb in self._bindings.items():
                keyboard.add_hotkey(hk, cb, suppress=False)
            # Block forever — the thread is a daemon, so it dies with main
            keyboard.wait()
        except ImportError:
            print(
                "[HotkeyManager] 'keyboard' library not found.\n"
                "  Run:  pip install keyboard\n"
                "  Note: may need to run as Administrator on Windows."
            )
        except Exception as e:
            print(f"[HotkeyManager] Error: {e}")
