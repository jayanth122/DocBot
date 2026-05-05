import os
import time
import requests


class LLMServiceError(Exception):
    """Raised when the upstream LLM provider returns an error."""

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def _extract_error_detail(response):
    try:
        payload = response.json()
    except ValueError:
        return response.text[:200]

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            return error.get("message", "")
        if isinstance(error, str):
            return error
    return ""


def _post_openrouter(messages, model, api_key):
    return requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
        },
        timeout=60,
    )


def call_llm(prompt, history=None):
    """Call OpenRouter LLM with the constructed prompt."""
    messages = []

    if history:
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": prompt})

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise LLMServiceError("OPENROUTER_API_KEY is not configured.")

    primary_model = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")
    fallback_models_raw = os.getenv("OPENROUTER_FALLBACK_MODELS", "")
    fallback_models = [m.strip() for m in fallback_models_raw.split(",") if m.strip()]
    model_candidates = [primary_model] + [m for m in fallback_models if m != primary_model]

    max_retries = int(os.getenv("OPENROUTER_MAX_RETRIES", "2"))
    base_backoff = float(os.getenv("OPENROUTER_RETRY_BASE_SECONDS", "1.0"))

    last_error = None

    for model in model_candidates:
        for attempt in range(max_retries + 1):
            try:
                response = _post_openrouter(messages, model, api_key)
            except requests.exceptions.RequestException as err:
                last_error = err
                if attempt < max_retries:
                    time.sleep(base_backoff * (2 ** attempt))
                    continue
                break

            if response.status_code == 429:
                last_error = response
                if attempt < max_retries:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        wait_seconds = max(float(retry_after), 0.5)
                    else:
                        wait_seconds = base_backoff * (2 ** attempt)
                    time.sleep(wait_seconds)
                    continue
                break

            if response.status_code >= 400:
                detail = _extract_error_detail(response)
                raise LLMServiceError(
                    f"The AI provider request failed. {detail}".strip(),
                    status_code=response.status_code,
                )

            try:
                return response.json()["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError, ValueError) as err:
                raise LLMServiceError("The AI provider returned an unexpected response format.") from err

    if isinstance(last_error, requests.Response) and last_error.status_code == 429:
        raise LLMServiceError(
            "DocBot is a little tired right now from too many requests. Please try again in a moment.",
            status_code=429,
        )

    raise LLMServiceError("Could not reach the AI provider. Check your network and try again.")
