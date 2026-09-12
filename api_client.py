"""OpenRouter API client — provisioning key discovery + per-key usage polling."""

import json
import urllib.request
import urllib.error

BASE = "https://openrouter.ai/api/v1"


def _get(path, key, timeout=10):
    """GET an OpenRouter endpoint. Returns parsed JSON or raises."""
    url = f"{BASE}{path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            err = json.loads(body)
            msg = err.get("error", {}).get("message", body)
        except Exception:
            msg = body
        raise RuntimeError(f"HTTP {e.code}: {msg}") from None
    except Exception as e:
        raise RuntimeError(str(e)) from e


def list_keys(provisioning_key):
    """List all API keys on the account using a provisioning key.

    Returns a list of dicts, each with: name, label, limit, limit_remaining,
    limit_reset, usage, usage_daily, usage_weekly, usage_monthly, disabled, etc.

    The actual key values (sk-or-v1-...) are NOT returned — only metadata + usage.
    One call gets everything needed for the per-key display.
    """
    data = _get("/keys", provisioning_key)
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return data if isinstance(data, list) else []


def get_key_info(api_key):
    """Get usage/limit info for a single key.

    Returns dict with: label, limit, limit_remaining, limit_reset,
    usage, usage_daily, usage_weekly, usage_monthly, is_free_tier, etc.
    """
    data = _get("/key", api_key)
    return data.get("data", {})


def get_credits(api_key):
    """Get account-wide credit balance. Same regardless of which key is used.

    Returns {total_credits, total_usage, remaining}
    """
    data = _get("/credits", api_key)
    inner = data.get("data", {})
    total = inner.get("total_credits", 0)
    used = inner.get("total_usage", 0)
    return {
        "total_credits": total,
        "total_usage": used,
        "remaining": total - used,
    }
