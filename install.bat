@echo off
echo ============================================================
echo  Proctoring Research PoC -- Install Dependencies
echo ============================================================
echo.

echo [1/3] Installing Python packages...
pip install mss Pillow keyboard requests pytesseract openai anthropic google-generativeai

echo.
echo [2/3] Done! Optional: for local AI without API keys, install Ollama:
echo        https://ollama.com  then run:  ollama pull llama3.2
echo.
echo [3/3] To run the overlay:
echo        python main.py
echo.
echo NOTE: Run as Administrator for global hotkeys to work properly.
pause
