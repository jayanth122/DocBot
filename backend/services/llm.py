import os
import time
import requests


class LLMServiceError(Exception):
    """Raised when the upstream LLM provider returns an error."""

    def __init__(self, message, status_code=None, provider=None):
        super().__init__(message)
        self.status_code = status_code
        self.provider = provider


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


def _build_messages(prompt, history=None):
    messages = []

    if history:
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": prompt})
    return messages


def _split_csv_env(name):
    return [item.strip() for item in os.getenv(name, "").split(",") if item.strip()]


def _get_provider_order():
    configured = _split_csv_env("LLM_PROVIDER_ORDER")
    return configured or ["openrouter", "groq", "gemini"]


def _get_models(primary_env, fallback_env, default_model):
    primary_model = os.getenv(primary_env, default_model).strip()
    fallback_models = _split_csv_env(fallback_env)
    return [primary_model] + [model for model in fallback_models if model != primary_model]


def _post_openai_compatible(url, messages, model, api_key):
    return requests.post(
        url,
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


def _post_gemini(messages, model, api_key):
    contents = []
    for message in messages:
        role = "model" if message["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": message["content"]}]})

    return requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
        headers={"Content-Type": "application/json"},
        json={"contents": contents},
        timeout=60,
    )


def _parse_openai_compatible(response, provider):
    try:
        return response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as err:
        raise LLMServiceError(
            f"{provider} returned an unexpected response format.",
            provider=provider,
        ) from err


def _parse_gemini(response):
    try:
        candidates = response.json()["candidates"]
        parts = candidates[0]["content"]["parts"]
        return "".join(part.get("text", "") for part in parts).strip()
    except (KeyError, IndexError, TypeError, ValueError) as err:
        raise LLMServiceError(
            "gemini returned an unexpected response format.",
            provider="gemini",
        ) from err


def _provider_configs():
    return {
        "openrouter": {
            "api_key": os.getenv("OPENROUTER_API_KEY"),
            "models": _get_models(
                "OPENROUTER_MODEL",
                "OPENROUTER_FALLBACK_MODELS",
                "nvidia/nemotron-3-super-120b-a12b:free",
            ),
            "request": lambda messages, model, api_key: _post_openai_compatible(
                "https://openrouter.ai/api/v1/chat/completions",
                messages,
                model,
                api_key,
            ),
            "parse": lambda response: _parse_openai_compatible(response, "openrouter"),
        },
        "groq": {
            "api_key": os.getenv("GROQ_API_KEY"),
            "models": _get_models(
                "GROQ_MODEL",
                "GROQ_FALLBACK_MODELS",
                "llama-3.1-8b-instant",
            ),
            "request": lambda messages, model, api_key: _post_openai_compatible(
                "https://api.groq.com/openai/v1/chat/completions",
                messages,
                model,
                api_key,
            ),
            "parse": lambda response: _parse_openai_compatible(response, "groq"),
        },
        "gemini": {
            "api_key": os.getenv("GEMINI_API_KEY"),
            "models": _get_models(
                "GEMINI_MODEL",
                "GEMINI_FALLBACK_MODELS",
                "gemini-1.5-flash",
            ),
            "request": _post_gemini,
            "parse": _parse_gemini,
        },
    }


def _call_provider(provider_name, config, messages, max_retries, base_backoff):
    api_key = config.get("api_key")
    if not api_key:
        raise LLMServiceError(
            f"{provider_name} API key is not configured.",
            provider=provider_name,
        )

    last_error = None
    for model in config["models"]:
        for attempt in range(max_retries + 1):
            try:
                response = config["request"](messages, model, api_key)
            except requests.exceptions.RequestException as err:
                last_error = LLMServiceError(
                    f"{provider_name} could not be reached.",
                    provider=provider_name,
                )
                if attempt < max_retries:
                    time.sleep(base_backoff * (2 ** attempt))
                    continue
                break

            if response.status_code == 429:
                last_error = LLMServiceError(
                    f"{provider_name} is rate-limiting requests.",
                    status_code=429,
                    provider=provider_name,
                )
                if attempt < max_retries:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        wait_seconds = max(float(retry_after), 0.5)
                    else:
                        wait_seconds = base_backoff * (2 ** attempt)
                    time.sleep(wait_seconds)
                    continue
                break

            if response.status_code >= 500:
                last_error = LLMServiceError(
                    f"{provider_name} is temporarily unavailable.",
                    status_code=response.status_code,
                    provider=provider_name,
                )
                if attempt < max_retries:
                    time.sleep(base_backoff * (2 ** attempt))
                    continue
                break

            if response.status_code >= 400:
                detail = _extract_error_detail(response)
                last_error = LLMServiceError(
                    f"{provider_name} request failed. {detail}".strip(),
                    status_code=response.status_code,
                    provider=provider_name,
                )
                break

            return config["parse"](response)

    if last_error:
        raise last_error

    raise LLMServiceError(
        f"{provider_name} failed without a usable response.",
        provider=provider_name,
    )


def call_llm(prompt, history=None):
    """Call the configured LLM providers with automatic failover."""
    messages = _build_messages(prompt, history)
    max_retries = int(os.getenv("LLM_MAX_RETRIES", os.getenv("OPENROUTER_MAX_RETRIES", "2")))
    base_backoff = float(
        os.getenv("LLM_RETRY_BASE_SECONDS", os.getenv("OPENROUTER_RETRY_BASE_SECONDS", "1.0"))
    )

    provider_errors = []
    configs = _provider_configs()
    for provider_name in _get_provider_order():
        config = configs.get(provider_name)
        if not config:
            continue

        try:
            return _call_provider(provider_name, config, messages, max_retries, base_backoff)
        except LLMServiceError as err:
            provider_errors.append(err)

    if any(error.status_code == 429 for error in provider_errors):
        raise LLMServiceError(
            "DocBot is a little tired right now from too many requests across its backup brains. Please try again in a moment.",
            status_code=429,
        )

    if provider_errors:
        raise LLMServiceError(
            "DocBot couldn't reach any of its AI providers right now. Please try again shortly.",
            status_code=provider_errors[-1].status_code,
        )

    raise LLMServiceError("No LLM providers are configured.")
