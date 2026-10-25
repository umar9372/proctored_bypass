"""
main.py - Entry point for the Proctoring Vulnerability Research PoC
MTech Thesis: Phase 1 - Attack Surface Demonstration

Hotkeys:
    Ctrl+Alt+S   Snip screen region and OCR the question
    Ctrl+Alt+A   Send question to AI and stream the answer
    Ctrl+Alt+H   Toggle overlay visibility (hide/show)
    Ctrl+Alt+T   Toggle click-through mode
    Ctrl+Alt+Q   Quit
"""

import sys
import os
import io

# Fix Windows console Unicode encoding (cp1252 -> utf-8)
if sys.stdout and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Ensure src/ is importable regardless of working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.overlay import TransparentOverlay

BANNER = """
+==============================================================+
|      PROCTORING VULNERABILITY RESEARCH  --  Phase 1         |
|      MTech Thesis  |  Attack Surface Demonstration          |
+==============================================================+
|                                                              |
|  DEMONSTRATES:                                               |
|  [+] Transparent overlay invisible to ALL screen capture     |
|  [+] Win32 WDA_EXCLUDEFROMCAPTURE exploit                    |
|  [+] OCR-based automatic question extraction                 |
|  [+] Real-time AI streaming (GPT/Claude/Gemini/Ollama)       |
|  [+] Click-through mode  (WS_EX_TRANSPARENT)                 |
|  [+] Hidden from Alt-Tab & Taskbar (WS_EX_TOOLWINDOW)        |
|                                                              |
|  HOTKEYS:                                                    |
|  Ctrl+Alt+S  ->  Snip screen region for OCR                  |
|  Ctrl+Alt+A  ->  Ask AI with current question                |
|  Ctrl+Alt+H  ->  Hide / Show overlay                         |
|  Ctrl+Alt+T  ->  Toggle click-through mode                   |
|  Ctrl+Alt+Q  ->  Quit                                        |
|                                                              |
|  [!]  FOR ACADEMIC RESEARCH ONLY  [!]                        |
+==============================================================+
"""


def main():
    print(BANNER)
    print("  Starting overlay ...\n")

    try:
        app = TransparentOverlay()
        app.run()
    except KeyboardInterrupt:
        print("\n  Exited.")
    except Exception as e:
        print(f"\n  Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
