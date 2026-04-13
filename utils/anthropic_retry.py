"""
anthropic_retry.py
Wrapper universal para llamadas a la Anthropic API con retry automático.
Aplica en TODOS los API routes del ecosistema Orlando 360™.

Errores cubiertos:
  - 529: Overloaded
  - 429: Rate limit (respeta Retry-After header)
  - 503: Service unavailable
  - 500: Internal server error (transiente)
  - Errores de conexión / red
"""

import time
import random
import anthropic

RETRY_STATUS_CODES = {429, 500, 503, 529}
MAX_RETRIES = 3
BASE_DELAY  = 1.0  # 1s → 2s → 4s (+ jitter)


def _jittered_delay(attempt: int) -> float:
    """Exponential backoff with +0–50% jitter."""
    base = BASE_DELAY * (2 ** (attempt - 1))   # 1s, 2s, 4s
    return base + random.random() * base * 0.5


def call_anthropic_with_retry(client: anthropic.Anthropic, **kwargs):
    """
    Drop-in replacement for client.messages.create(**kwargs).
    Retries up to MAX_RETRIES times on retriable errors with
    jittered exponential backoff.  Respects Retry-After on 429s.

    Usage:
        msg = call_anthropic_with_retry(client,
                  model="claude-sonnet-4-20250514",
                  max_tokens=5000,
                  messages=[...])
    """
    last_exc = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return client.messages.create(**kwargs)

        except anthropic.APIStatusError as exc:
            status = exc.status_code
            if status not in RETRY_STATUS_CODES or attempt == MAX_RETRIES:
                raise

            last_exc = exc

            # Respect Retry-After header for 429s
            retry_after = None
            if hasattr(exc, "response") and exc.response is not None:
                ra = exc.response.headers.get("retry-after")
                if ra:
                    try:
                        retry_after = float(ra)
                    except ValueError:
                        pass

            delay = retry_after if retry_after is not None else _jittered_delay(attempt)
            print(
                f"[AnthropicRetry] Attempt {attempt}/{MAX_RETRIES} failed "
                f"(HTTP {status}). Retrying in {delay:.1f}s...",
                flush=True,
            )
            time.sleep(delay)

        except (anthropic.APIConnectionError, anthropic.APITimeoutError) as exc:
            if attempt == MAX_RETRIES:
                raise

            last_exc = exc
            delay = _jittered_delay(attempt)
            print(
                f"[AnthropicRetry] Connection error on attempt {attempt}/{MAX_RETRIES}. "
                f"Retrying in {delay:.1f}s...",
                flush=True,
            )
            time.sleep(delay)

    # Should not be reached, but satisfy type checkers
    raise last_exc or RuntimeError("Unknown error in call_anthropic_with_retry")
