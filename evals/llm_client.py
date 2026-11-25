"""Minimal OpenRouter client (no extra packages needed).

OpenRouter gives one API for many model providers (Anthropic, OpenAI, Google,
DeepSeek, Qwen, Moonshot, ...). Swapping models = changing the model name.
The API key is read from the OPENROUTER_API_KEY environment variable or a .env
file in the project folder. It is passed to curl on stdin, never on the command
line, so it doesn't show up in process lists.
"""
import json
import os
import re
import subprocess
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://openrouter.ai/api/v1/chat/completions"


def api_key():
    key = os.environ.get("OPENROUTER_API_KEY")
    env_file = os.path.join(HERE, ".env")
    if not key and os.path.exists(env_file):
        for line in open(env_file):
            if line.strip().startswith("OPENROUTER_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        raise SystemExit("No OPENROUTER_API_KEY found. Copy .env.example to .env and paste your key there.")
    return key


MIN_GAP_SECONDS = 3.2  # stay under 20 requests/minute (OpenRouter's limit for new accounts)
_last_call = [0.0]


def chat(model, system, user, temperature=0.0, timeout=120, max_tokens=2000, retries=5):
    """Send one request, retrying on rate limits. Returns (text, seconds, cost_usd)."""
    for attempt in range(1, retries + 1):
        wait = MIN_GAP_SECONDS - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()
        try:
            return _chat_once(model, system, user, temperature, timeout, max_tokens)
        except RuntimeError as e:
            retryable = any(s in str(e).lower() for s in ("rate limit", "in-flight", "in_flight", "429", "timeout", "overloaded"))
            if not retryable or attempt == retries:
                raise
            time.sleep(15 * attempt)


def _chat_once(model, system, user, temperature, timeout, max_tokens):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": temperature,
        "max_tokens": max_tokens,  # the answer is a short JSON; also keeps cost reservations small
        "usage": {"include": True},  # ask OpenRouter to report the cost of this call
    })
    config = (f'header = "Authorization: Bearer {api_key()}"\n'
              'header = "Content-Type: application/json"\n')
    start = time.time()
    proc = subprocess.run(["curl", "-sS", "-m", str(timeout), "-K", "-", "-d", "@" + _tmp(body), URL],
                          input=config, capture_output=True, text=True)
    seconds = time.time() - start
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        raise RuntimeError(f"Bad response from OpenRouter: {proc.stdout[:300]} {proc.stderr[:300]}")
    if "error" in data:
        raise RuntimeError(f"OpenRouter error: {data['error']}")
    text = data["choices"][0]["message"]["content"] or ""
    cost = (data.get("usage") or {}).get("cost")
    return text, seconds, cost


def _tmp(body):
    path = os.path.join(HERE, "results", ".request.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(body)
    return path


def parse_json(text):
    """Pull the first JSON object out of a model reply (handles ```json fences)."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start:end + 1])
    except ValueError:
        return None
