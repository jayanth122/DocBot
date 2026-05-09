const DEFAULT_TIMEOUT_MS = 90000;
const DEFAULT_RETRIES = 1;

export class ApiError extends Error {
  status: number;
  retryable: boolean;
  details?: string;

  constructor(message: string, status = 500, retryable = false, details?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.retryable = retryable;
    this.details = details;
  }
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isRetriableStatus(status: number) {
  return status === 408 || status === 429 || status >= 500;
}

function getMessageFromPayload(payload: unknown) {
  if (!payload || typeof payload !== "object") {
    return "";
  }

  const record = payload as Record<string, unknown>;
  const candidates = [record.message, record.error, record.response];
  for (const value of candidates) {
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }
  return "";
}

export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  if (!path.startsWith("/")) {
    throw new Error("apiFetch expects a path that starts with '/'.");
  }

  const retries = DEFAULT_RETRIES;

  for (let attempt = 0; attempt <= retries; attempt += 1) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);

    try {
      const response = await fetch(`/api/proxy${path}`, {
        ...init,
        signal: controller.signal,
      });

      if (response.ok) {
        return response;
      }

      let payload: unknown = null;
      try {
        payload = await response.clone().json();
      } catch {
        payload = null;
      }

      const details = getMessageFromPayload(payload);
      const message = details || "The service could not process this request.";
      const retryable = isRetriableStatus(response.status);

      if (retryable && attempt < retries) {
        await sleep(300 * (attempt + 1));
        continue;
      }

      throw new ApiError(message, response.status, retryable, details || undefined);
    } catch (err) {
      const isAbort = err instanceof DOMException && err.name === "AbortError";
      const isNetwork = err instanceof TypeError;
      const retryable = isAbort || isNetwork;

      if (retryable && attempt < retries) {
        await sleep(300 * (attempt + 1));
        continue;
      }

      if (err instanceof ApiError) {
        throw err;
      }

      throw new ApiError(
        "I had trouble connecting to the service. Please try again.",
        503,
        true
      );
    } finally {
      clearTimeout(timeout);
    }
  }

  throw new ApiError("Request failed unexpectedly.");
}

export function toUserFacingError(err: unknown) {
  if (err instanceof ApiError) {
    if (err.status === 503 || err.status === 504) {
      return "I\u2019m having trouble reaching the chat service right now. Please try again in a few seconds.";
    }
    if (err.status === 429) {
      return "I\u2019m getting rate-limited at the moment. Please retry in a short while.";
    }
    return err.message || "Something went wrong while processing your request.";
  }

  return "Something went wrong while processing your request.";
}
