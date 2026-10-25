"""
ai_engine.py — Multi-provider AI engine with streaming support
MTech Thesis: Proctoring Vulnerability Research — Phase 1

Supported providers: OpenAI | Google Gemini | Ollama (local)
"""

import threading
from typing import Callable


class AIEngine:
    def __init__(self, config):
        self.config = config

    # ──────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────

    def ask(
        self,
        question: str,
        on_chunk: Callable[[str], None],
        on_done: Callable[[str], None],
        on_error: Callable[[str], None],
    ):
        """Ask a question asynchronously. Streams tokens via on_chunk()."""
        thread = threading.Thread(
            target=self._worker,
            args=(question, on_chunk, on_done, on_error),
            daemon=True,
        )
        thread.start()

    # ──────────────────────────────────────────────────────────────────
    # Internal
    # ──────────────────────────────────────────────────────────────────

    def _worker(self, question, on_chunk, on_done, on_error):
        try:
            provider = self.config.get("ai_provider", "ollama")
            system  = self.config.get("system_prompt", "You are a helpful assistant.")

            dispatch = {
                "openai":  self._openai,
                "gemini":  self._gemini,
                "ollama":  self._ollama,
            }

            fn = dispatch.get(provider)
            if fn is None:
                on_error(f"Unknown AI provider: '{provider}'. Check config.json.")
                return
            fn(question, system, on_chunk, on_done)

        except ImportError as e:
            on_error(f"Missing library: {e}. Run: pip install {str(e).split()[-1]}")
        except Exception as e:
            on_error(str(e))

    # ── OpenAI ────────────────────────────────────────────────────────
    def _openai(self, question, system, on_chunk, on_done):
        # pyrefly: ignore[missing-import]
        import openai
        
        client = openai.OpenAI(api_key=self.config.get("openai_api_key"))
        model  = self.config.get("openai_model", "gpt-4o-mini")

        stream = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system",  "content": system},
                {"role": "user",    "content": question},
            ],
            stream=True,
        )
        full = ""
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                full += delta
                on_chunk(delta)
        on_done(full)


    # ── Google Gemini ─────────────────────────────────────────────────
    def _gemini(self, question, system, on_chunk, on_done):
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.config.get("gemini_api_key"))
            primary = self.config.get("gemini_model", "gemini-2.5-flash")
            candidates = [primary, "gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-pro"]
            candidates = list(dict.fromkeys(candidates))

            last_error = None
            for model_name in candidates:
                try:
                    m = genai.GenerativeModel(model_name, system_instruction=system)
                    full = ""
                    for chunk in m.generate_content(question, stream=True):
                        text = getattr(chunk, "text", "") or ""
                        if text:
                            full += text
                            on_chunk(text)
                    on_done(full)
                    return
                except Exception as e:
                    last_error = e
                    continue
            if last_error:
                raise last_error
        except Exception as e:
            raise e

    # ── Ollama (local) ────────────────────────────────────────────────
    def _ollama(self, question, system, on_chunk, on_done):
        import requests, json
        host  = self.config.get("ollama_host",  "http://localhost:11434")
        model = self.config.get("ollama_model", "llama3.2")

        resp = requests.post(
            f"{host}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user",   "content": question},
                ],
                "stream": True,
            },
            stream=True,
            timeout=60,
        )
        resp.raise_for_status()

        full = ""
        for line in resp.iter_lines():
            if not line:
                continue
            data = json.loads(line)
            text = data.get("message", {}).get("content", "")
            if text:
                full += text
                on_chunk(text)
            if data.get("done"):
                break
        on_done(full)
