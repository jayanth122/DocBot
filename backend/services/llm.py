import os
import requests


def call_llm(prompt, history=None):
    """Call OpenRouter LLM with the constructed prompt."""
    messages = []

    if history:
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": prompt})

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
            "Content-Type": "application/json",
        },
        json={
            "model": "nvidia/nemotron-3-super-120b-a12b:free",
            "messages": messages,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]
