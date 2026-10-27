"""Interactive, loopback-only preview with real providers and the production build."""

from __future__ import annotations

import getpass
import logging
import re
import sys
from pathlib import Path
from time import perf_counter

import httpx
import uvicorn
from pydantic import SecretStr, ValidationError
from roambot.config import ProviderMode, Settings
from roambot.entrypoint import configure_runtime_logging
from roambot.main import create_app
from roambot.security.vault import CredentialVault, VaultAuthenticationError

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "frontend" / "dist"


class ModelConfigurationError(Exception):
    pass


class MapConfigurationError(Exception):
    pass


def map_credentials(
    vault: CredentialVault,
    password: str,
    values: dict[str, str | None],
    *,
    force: bool = False,
) -> dict[str, str]:
    prompts = {
        "amap_js_key": "AMap JavaScript API key (not Web Service key): ",
        "amap_js_security_code": "AMap JavaScript security code: ",
    }
    selected: dict[str, str] = {}
    changed = False
    for name, prompt in prompts.items():
        value = (values.get(name) or "").strip()
        if force or not value:
            value = getpass.getpass(prompt).strip()
            changed = True
        if not value:
            raise MapConfigurationError(
                "Both map settings are required; vault unchanged."
            )
        selected[name] = value
    if changed:
        try:
            vault.update_many(password, selected)
        except OSError:
            raise MapConfigurationError(
                "Unable to save encrypted map settings."
            ) from None
        print("Map settings saved in the encrypted local vault.")
    return selected


def _available_model_ids(base_url: str, key: str) -> list[str]:
    try:
        with httpx.Client(timeout=15) as client:
            response = client.get(
                f"{base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {key}"},
            )
    except httpx.HTTPError:
        raise ModelConfigurationError(
            "Unable to reach the model gateway; check the network and base URL."
        ) from None
    if response.status_code in (401, 403):
        raise ModelConfigurationError(
            f"Model gateway rejected the key (HTTP {response.status_code}); "
            "check the LLM key and its model access group."
        )
    if response.status_code != 200:
        raise ModelConfigurationError(
            f"Model list HTTP {response.status_code}; check the gateway and model key."
        )
    try:
        payload = response.json()
    except ValueError:
        raise ModelConfigurationError("Model gateway returned invalid JSON.") from None
    entries = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(entries, list):
        raise ModelConfigurationError(
            "Model gateway returned an unexpected catalog shape."
        )
    return [
        item["id"]
        for item in entries
        if isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and re.fullmatch(r"[\w./:-]{1,120}", item["id"])
    ]


def gateway_model(base_url: str, key: str, requested: str) -> str:
    available = _available_model_ids(base_url, key)
    if requested in available:
        return requested
    matches = [name for name in available if name.casefold() == requested.casefold()]
    if len(matches) == 1:
        print(f"Using the gateway's exact model ID: {matches[0]}")
        return matches[0]
    if not available:
        raise ModelConfigurationError(
            "This key exposes no models; confirm the gateway channel before retrying."
        )
    candidates = [
        name
        for name in available
        if "deepseek" in name.lower() or "flash" in name.lower()
    ]
    print("Configured model is not in this key's available model list.")
    print("Available IDs: " + ", ".join((candidates or available)[:20]))
    selected = input("Choose an available model ID, or press Enter to cancel: ").strip()
    if selected not in available:
        raise ModelConfigurationError("No verified model selected; startup cancelled.")
    return selected


def comparison_models(base_url: str, key: str, baseline: str) -> tuple[str, str]:
    from roambot.providers.assistant_model_comparison import thinking_options

    available = _available_model_ids(base_url, key)
    baselines = [name for name in available if name.casefold() == baseline.casefold()]
    if len(baselines) != 1:
        raise ModelConfigurationError(
            "Comparison needs one exact configured baseline in this key's catalog."
        )
    candidates = []
    for name in available:
        try:
            thinking_options(name)
        except ValueError:
            continue
        candidates.append(name)
    if not candidates:
        raise ModelConfigurationError(
            "No candidate with a known non-thinking control; comparison cancelled."
        )
    preferred = (
        "qwen-plus",
        "qwen3.8-flash",
        "qwen3.7-plus",
        "qwen3.8-max",
        "deepseek-v4-flash",
    )
    candidates.sort(
        key=lambda name: (
            preferred.index(name.casefold())
            if name.casefold() in preferred
            else len(preferred)
        )
    )
    default = candidates[0]
    print("Temporary experiment only; website model and vault will not change.")
    print("Available non-thinking candidates: " + ", ".join(candidates[:20]))
    print(
        f"Suggested first candidate: {default}; actual accuracy/latency still require measurement."
    )
    selected = (
        input("Enter exact candidate ID, Enter for suggested, or 'cancel': ").strip()
        or default
    )
    if selected not in candidates:
        raise ModelConfigurationError(
            "No verified experiment candidate selected; comparison cancelled."
        )
    return baselines[0], selected


def probe_completion(base_url: str, key: str, model: str) -> int:
    try:
        available = _available_model_ids(base_url, key)
        print("Available IDs: " + (", ".join(available[:40]) or "(none)"))
    except ModelConfigurationError as error:
        print(str(error))
    started = perf_counter()
    try:
        with httpx.Client(timeout=45) as client:
            response = client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": model,
                    "temperature": 0,
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "ping"}],
                },
            )
    except httpx.HTTPError:
        print("Probe failed: unable to reach the gateway.")
        return 1
    elapsed_ms = round((perf_counter() - started) * 1000)
    print(
        f"Probe POST /chat/completions model={model} -> "
        f"HTTP {response.status_code} elapsed_ms={elapsed_ms}"
    )
    if response.status_code != 200:
        excerpt = response.text.replace(key, "[redacted]")[:300]
        print("Upstream error excerpt: " + excerpt)
    else:
        print("Completion channel responded 200; the model is callable.")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if args not in (
        [],
        ["--check"],
        ["--probe"],
        ["--configure-map"],
        ["--compare-models"],
        ["--compare-models", "--holdout"],
        ["--compare-models", "--holdout-focus"],
        ["--diagnose-assistant"],
        ["--diagnose-assistant", "--audit"],
        ["--diagnose-assistant", "--parameters"],
        ["--diagnose-assistant", "--date-roles"],
    ) and not (len(args) == 2 and args[0] == "--probe"):
        print(
            "Usage: local_live.py [--check | --probe [model-id] | --configure-map | "
            "--diagnose-assistant | --compare-models [--holdout]]"
        )
        return 1
    try:
        settings = Settings(
            provider_mode=ProviderMode.LIVE,
            demo_mode=False,
            secure_cookies=False,
            data_dir=ROOT / "data" / "local-live",
            qweather_api_host="https://np2yw2kakp.re.qweatherapi.com",
            llm_base_url="https://njusehub.info/v1",
            llm_model="qwen3.7-plus",
            llm_enable_thinking=False,
            assistant_timeout_seconds=8,
            provider_timeout_seconds=15,
        )
    except ValidationError:
        print("Local live configuration is invalid; no provider requests made.")
        return 1
    vault = CredentialVault(settings.data_dir / "credentials.vault")
    if not vault.path.is_file() or (
        args
        not in (
            ["--configure-map"],
            ["--compare-models"],
            ["--compare-models", "--holdout"],
            ["--compare-models", "--holdout-focus"],
            ["--diagnose-assistant"],
            ["--diagnose-assistant", "--audit"],
            ["--diagnose-assistant", "--parameters"],
            ["--diagnose-assistant", "--date-roles"],
        )
        and not (DIST / "index.html").is_file()
    ):
        print("Local credential vault or frontend build is missing.")
        return 1
    if sys.argv[1:] == ["--check"]:
        print("Live configuration, vault file and production frontend are present.")
        print("No secrets unlocked and no API requests made.")
        return 0
    if not sys.stdin.isatty():
        print("Run this script in your own interactive terminal for hidden input.")
        return 1
    credentials: dict[str, str] = {}
    values: dict[str, str | None] = {}
    password = None
    try:
        password = getpass.getpass("Local vault master password: ")
        values = vault.unlock(password)
        if args and args[0] == "--compare-models":
            from roambot.providers.assistant_model_comparison import (
                run_model_comparison,
            )

            key = (values.get("llm_api_key") or "").strip()
            if not key:
                raise ModelConfigurationError("The local vault has no LLM key.")
            baseline, candidate = comparison_models(
                str(settings.llm_base_url), key, "qwen-turbo"
            )
            if "--holdout" in args or "--holdout-focus" in args:
                from roambot.providers.assistant_candidate_holdout import (
                    run_candidate_holdout,
                )

                if "--holdout-focus" in args:
                    print(
                        "Focus only: 2 synthetic turns, at most 4 completion calls; "
                        "website and credentials unchanged."
                    )
                    return run_candidate_holdout(
                        str(settings.llm_base_url),
                        key,
                        candidate,
                        ROOT / "test-results/assistant-candidate-focus.json",
                        focus=True,
                    )
                print(
                    "Candidate only: 15 synthetic turns, at most 30 completion calls; "
                    "website and credentials unchanged."
                )
                return run_candidate_holdout(
                    str(settings.llm_base_url),
                    key,
                    candidate,
                    ROOT / "test-results/assistant-candidate-holdout.json",
                )
            return run_model_comparison(
                str(settings.llm_base_url),
                key,
                baseline,
                candidate,
                ROOT / "test-results/assistant-model-latency-comparison.json",
            )
        if args == ["--configure-map"]:
            map_credentials(vault, password, values, force=True)
            return 0
        if args and args[0] == "--diagnose-assistant":
            from roambot.providers.assistant_diagnostics import run_assistant_diagnostic

            key = (values.get("llm_api_key") or "").strip()
            if not key:
                print("The local vault has no LLM key.")
                return 1
            # Fixed audits/probes target the configured model directly: no extra
            # catalog request, no model chooser and no silent switch.
            if (
                "--parameters" not in args
                and "--audit" not in args
                and "--date-roles" not in args
                and settings.llm_model
                not in _available_model_ids(str(settings.llm_base_url), key)
            ):
                raise ModelConfigurationError(
                    "Configured model is absent; diagnostic cancelled."
                )
            diagnostic_options = (
                {"parameters": True}
                if "--parameters" in args
                else {"date_roles": True}
                if "--date-roles" in args
                else {"audit": True}
                if "--audit" in args
                else {}
            )
            return run_assistant_diagnostic(
                str(settings.llm_base_url),
                key,
                settings.llm_model,
                ROOT
                / "test-results"
                / (
                    "assistant-parameter-probe.json"
                    if "--parameters" in args
                    else "assistant-date-role-comparison.json"
                    if "--date-roles" in args
                    else "assistant-semantic-audit.json"
                    if diagnostic_options
                    else "assistant-protocol-comparison.json"
                ),
                **diagnostic_options,
            )
        for name in ("amap_api_key", "qweather_api_key", "llm_api_key"):
            value = values.get(name)
            if not value or not value.strip():
                print("One or more service keys are missing from the local vault.")
                return 1
            credentials[name] = value.strip()
        if sys.argv[1:2] == ["--probe"]:
            requested = (
                sys.argv[2]
                if len(sys.argv) > 2
                else gateway_model(
                    str(settings.llm_base_url),
                    credentials["llm_api_key"],
                    settings.llm_model,
                )
            )
            return probe_completion(
                str(settings.llm_base_url), credentials["llm_api_key"], requested
            )
        settings.llm_model = gateway_model(
            str(settings.llm_base_url), credentials["llm_api_key"], settings.llm_model
        )
        maps = map_credentials(vault, password, values)
        settings.amap_js_key = SecretStr(maps["amap_js_key"])
        settings.amap_js_security_code = SecretStr(maps["amap_js_security_code"])
        maps.clear()
        configure_runtime_logging()
        diagnostic_dir = ROOT / "test-results"
        diagnostic_dir.mkdir(parents=True, exist_ok=True)
        diagnostic_logger = logging.getLogger("roambot.providers.assistant")
        diagnostic_handler = logging.FileHandler(
            diagnostic_dir / "assistant-model-errors.log", encoding="utf-8"
        )
        diagnostic_handler.setLevel(logging.WARNING)
        diagnostic_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        diagnostic_logger.addHandler(diagnostic_handler)
        application = create_app(
            settings=settings, frontend_dist=DIST, provider_credentials=credentials
        )
    except VaultAuthenticationError:
        print("Unable to unlock the local vault. Check your local master password.")
        return 1
    except (ModelConfigurationError, MapConfigurationError) as error:
        print(str(error))
        return 1
    finally:
        password = None
        values.clear()
        credentials.clear()
    print("Local LIVE preview: http://127.0.0.1:8026/recommend")
    print(f"Model: {settings.llm_model}. Real requests consume provider quotas.")
    print("Map settings loaded from the encrypted local vault. Press Ctrl+C to stop.")
    try:
        uvicorn.run(application, host="127.0.0.1", port=8026, access_log=False)
    finally:
        diagnostic_logger.removeHandler(diagnostic_handler)
        diagnostic_handler.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        print("Local live startup cancelled.")
