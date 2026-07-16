# RoamBot Providers and Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the mock-only runtime with bounded real AMap, QWeather, and OpenAI-compatible adapters while preserving the approved business contracts, then deliver a tested single-image Docker application and GitLab CI pipeline.

**Architecture:** Provider adapters remain behind the synchronous protocols introduced in milestone 1. A provider factory selects `mock` or `live` mode, unlocks the encrypted vault only in live mode, wraps external reads with the milestone 2 persistent cache, and applies explicit degradation rules. FastAPI serves the built React files in production, while tests and CI force mock mode and deny real network access.

**Tech Stack:** Python 3.13, FastAPI, Pydantic Settings, httpx, pytest, React/Vite, Playwright, SQLite, Docker multi-stage builds, GitLab CI.

## Global Constraints

- Complete and verify plans 01, 02, and 03 before beginning this plan.
- Do not change the approved scoring formula, scenery classifier, API response schema, account scope, or WebUI product scope.
- Do not add maps, routes, navigation, itineraries, phone, SMS, CAPTCHA, email, OAuth, or password recovery.
- Use mock providers for every automated test and CI job. A real provider request is allowed only from the explicit manual smoke command in Task 7.
- Never put a provider key or master password in source, `.env`, Git, logs, exception text, request URLs captured by logs, Docker layers, CI variables, screenshots, test reports, or chat.
- Use the existing encrypted vault for `amap_api_key`, `qweather_api_key`, and `llm_api_key`. Keep QWeather API Host, LLM base URL, and model as non-secret settings.
- QWeather V1 authenticates with `X-QW-Api-Key` and the account-specific API Host. Do not send its key in a query string.
- AMap requires its key as a request parameter; build requests with `httpx` parameters, disable URL-level request logging, and translate errors before logging so the key is never emitted.
- Bound each recommendation to at most 6 POI searches, 3 geocodes, 5 weather forecasts, 5 distance batches, and 1 LLM request. Reject or degrade before exceeding those limits.
- Use explicit `provider_mode=mock|live`. Demo Suzhou data is available only in mock mode and must be labelled as demo data.
- Every task follows red-green-refactor and ends with a focused commit.

---

## File Map

- `backend/src/roambot/config.py`: validated non-secret runtime settings.
- `backend/src/roambot/providers/factory.py`: mock/live provider assembly and vault boundary.
- `backend/src/roambot/providers/http.py`: shared sanitized HTTP client and error translation.
- `backend/src/roambot/providers/amap.py`: geocoding, POI search/resolve, and distance adapter.
- `backend/src/roambot/providers/qweather.py`: seven-day forecast adapter.
- `backend/src/roambot/providers/openai_compatible.py`: one-call structured explanation adapter.
- `backend/src/roambot/providers/cached.py`: typed fresh-cache decorators.
- `backend/src/roambot/providers/budget.py`: per-request provider-call counters.
- `backend/src/roambot/services/recommendations.py`: budget-aware orchestration and source notices.
- `backend/src/roambot/cli.py`: live-provider smoke command.
- `backend/src/roambot/main.py`: production static files and SPA fallback.
- `backend/src/roambot/entrypoint.py`: vault password file/TTY startup boundary.
- `Dockerfile`, `.dockerignore`: reproducible production image.
- `ci/Dockerfile`: Python, Node, and Chromium test image.
- `.gitlab-ci.yml`: zero-real-call test and delivery pipeline.
- `README.md`, `REFLECTION.md`: operation, evidence, limits, and assignment reflection.

### Task 1: Validated Runtime Configuration and Provider Factory

**Files:**
- Create: `backend/src/roambot/config.py`
- Create: `backend/src/roambot/providers/factory.py`
- Modify: `backend/src/roambot/api/dependencies.py`
- Modify: `backend/src/roambot/main.py`
- Test: `backend/tests/unit/test_config.py`
- Test: `backend/tests/unit/test_provider_factory.py`

**Interfaces:**
- Produces: `Settings`, `ProviderMode`, `ProviderBundle`, `ProviderRuntime`, and `build_provider_runtime(settings,vault_values,cache_repository)`; `ProviderRuntime.new_request_bundle()` is request scoped.
- Consumes: `MockProviderBundle.default()` and all milestone 1 provider protocols.

- [ ] **Step 1: Verify the settings dependency from milestone 2**

Confirm `pydantic-settings>=2.10,<3` remains in backend runtime dependencies, reinstall the editable package, and do not add `python-dotenv` or automatic `.env` loading.

- [ ] **Step 2: Write failing settings tests**

Assert these exact behaviors:

- Defaults are `provider_mode="mock"`, `demo_mode=True`, `data_dir=Path("data")`, HTTP timeout 5 seconds, and the locked call budgets.
- `provider_mode="live"` rejects `demo_mode=True`.
- Live mode rejects a missing or non-HTTPS `qweather_api_host`.
- Live mode rejects a missing or non-HTTPS `llm_base_url` and a blank `llm_model`.
- Host settings reject a query string, fragment, embedded username/password, and a trailing API path.
- Settings representation contains no credential fields.

Run the tests and observe the import failure for `roambot.config`.

- [ ] **Step 3: Implement settings with exact fields**

Use a string enum with `MOCK="mock"` and `LIVE="live"`. Define:

```python
class Settings(BaseSettings):
    provider_mode: ProviderMode = ProviderMode.MOCK
    demo_mode: bool = True
    data_dir: Path = Path("data")
    amap_base_url: AnyHttpUrl = AnyHttpUrl("https://restapi.amap.com")
    qweather_api_host: AnyHttpUrl | None = None
    llm_base_url: AnyHttpUrl | None = None
    llm_model: str | None = None
    provider_timeout_seconds: float = 5.0
    max_geocode_calls: int = 3
    max_poi_search_calls: int = 6
    max_weather_calls: int = 5
    max_distance_calls: int = 5
    max_llm_calls: int = 1
```

Use `env_prefix="ROAMBOT_"`, `extra="forbid"`, and a model validator for the live-mode rules. Normalize hosts by stripping only a final slash. Do not include secrets in this model.

- [ ] **Step 4: Write failing provider-factory tests**

Assert:

- Mock mode runtime returns a new deterministic mock request bundle without touching the vault or cache.
- Live mode with any missing credential raises `ConfigurationError` naming only the missing provider, never any supplied value.
- Live mode request bundles return objects satisfying all five provider protocols and never share a `ProviderTrace`.
- `create_app(Settings(provider_mode="mock"))` remains testable without filesystem credentials.

- [ ] **Step 5: Implement the factory boundary**

Create one immutable `ProviderBundle` dataclass with fields `geocoder`, `places`, `distance`, `weather`, `explanations`, and request-scoped `trace`. `ProviderRuntime` owns the shared client, raw adapters, settings, and cache repository; `new_request_bundle()` creates a fresh trace and cheap wrappers. In mock/demo mode it adapts `MockProviderBundle.default()` and marks demo on that trace. In live mode, accept already-unlocked `Mapping[str, str]`; validate the three expected nonblank entries, create one sanitized shared `httpx.Client`, and construct real adapters once.

Update application lifespan to build/close only the runtime. The request dependency calls `new_request_bundle()` once per API request; tests may override that bundle directly. Never keep trace/events on the runtime or raw adapter, and do not unlock the vault inside route handlers.

- [ ] **Step 6: Verify and commit**

Run config/factory tests, all backend tests, and Ruff. Expected: all pass with no network access. Commit `feat: configure mock and live provider modes`.

### Task 2: Sanitized HTTP Boundary and Provider Budgets

**Files:**
- Create: `backend/src/roambot/providers/http.py`
- Create: `backend/src/roambot/providers/budget.py`
- Test: `backend/tests/unit/test_provider_http.py`
- Test: `backend/tests/unit/test_provider_budget.py`

**Interfaces:**
- Produces: `ProviderHttpClient.get_json()`, `ProviderBudget.consume()`, and `ProviderBudgetExceeded`.
- Consumed by: all real adapters and `RecommendationService`.

- [ ] **Step 1: Write failing redaction tests**

Use `httpx.MockTransport` and fake values `amap-secret-123`, `weather-secret-456`, and `llm-secret-789`. Cover successful JSON, HTTP 429, HTTP 500, timeout, invalid JSON, and a provider error body. Capture logs and exception strings; assert none contains any fake value, `key=`, `X-QW-Api-Key`, or `Authorization` header content.

- [ ] **Step 2: Implement the sanitized client**

`ProviderHttpClient` accepts a prebuilt `httpx.Client`, provider name, base URL, timeout, and a tuple of secret values to redact. It builds paths and `params` separately, calls `client.request`, parses JSON, and raises stable `ProviderError` codes: `rate_limited`, `timeout`, `bad_response`, `unavailable`, or provider-specific codes supplied by an adapter.

The only request log fields are provider name, operation name, HTTP status, elapsed milliseconds, and a generated request ID. Set `httpx` and `httpcore` loggers to warning in the application logging configuration. Never log `request.url`, headers, params, body, or raw provider response.

- [ ] **Step 3: Write failing budget tests**

Assert each operation can consume exactly its configured maximum, the next call raises `ProviderBudgetExceeded`, counters are independent, and a new budget starts at zero. Assert exception text names only operation and limit.

- [ ] **Step 4: Implement request-local budgets**

Use an enum for `GEOCODE`, `POI_SEARCH`, `WEATHER`, `DISTANCE`, and `LLM`. `ProviderBudget` owns integer limits and counters and is created inside each recommend/evaluate service call. Consume immediately before an adapter call. Convert overflow into an explicit degraded notice; never silently issue an extra call.

- [ ] **Step 5: Verify and commit**

Run both focused test files, full backend tests, and Ruff. Commit `feat: bound and sanitize provider calls`.

### Task 3: AMap Geocoding, POI, and Distance Adapter

**Files:**
- Create: `backend/src/roambot/providers/amap.py`
- Create: `backend/tests/fixtures/amap/geocode_success.json`
- Create: `backend/tests/fixtures/amap/poi_around_success.json`
- Create: `backend/tests/fixtures/amap/poi_text_success.json`
- Create: `backend/tests/fixtures/amap/distance_success.json`
- Test: `backend/tests/unit/test_amap_provider.py`

**Interfaces:**
- Implements: `Geocoder`, `PlaceProvider`, and `DistanceProvider`.
- Calls only `https://restapi.amap.com/v3/geocode/geo`, `/v5/place/around`, `/v5/place/text`, and `/v3/distance` with GCJ-02 coordinates.

- [ ] **Step 1: Create minimal provider fixtures**

Store only synthetic values shaped like official AMap responses. Include `status`, `info`, `infocode`, `count`, coordinates, POI `id/name/type/typecode/address/business.rating`, and distance `distance/duration`. Do not copy real API keys, full production payloads, or personal addresses.

- [ ] **Step 2: Write failing geocode and resolve tests**

Using `httpx.MockTransport`, assert:

- `geocode("Suzhou Railway Station", "Suzhou")` sends `/v3/geocode/geo` with exactly `key,address,city,output=json` and maps `location="120.617,31.335"` to `Coordinate(120.617, 31.335)`.
- Empty geocodes raise `ProviderError("not_found", "未找到出发地")`.
- `resolve(name, city)` calls `/v5/place/text` with exactly `key,keywords,region,city_limit=true,show_fields=business,page_size=25,page_num=1,output=json`, and chooses exact normalized name before provider order.
- Only top-level `status == "1"` and `infocode == "10000"` is success. A valid empty list is `not_found`; top-level provider errors, malformed coordinates, and missing required response structure produce sanitized errors.

Run and observe the import failure for `roambot.providers.amap`.

- [ ] **Step 3: Implement response validation and geocode/resolve**

Use small Pydantic response models with `extra="ignore"`. Split AMap coordinates on one comma and validate longitude/latitude ranges. Keep the coordinate-system assumption documented as GCJ-02 in code and README. `name`, `location`, `type`, and `typecode` are required for a usable POI; `address` may be empty and missing `cityname` falls back to the requested city. Optional `business.rating` is parsed only when numeric and is never used as a cross-category popularity score.

Never stringify a response model containing a key. The adapter maps `status`, `info`, and `infocode` into a stable code while exposing only a short provider-safe message.

- [ ] **Step 4: Write failing POI search tests**

Define exact keyword sets:

```python
SEARCH_TERMS = {
    SceneryType.LAKE: "湖泊景区",
    SceneryType.SEA: "海滩",
    SceneryType.OLD_TOWN: "古镇",
    SceneryType.MUSEUM: "博物馆",
    SceneryType.PARK: "公园",
    SceneryType.MOUNTAIN: "山岳景区",
}
```

Keep these Chinese API search terms and enum keys stable. Tests assert:

- Up to one search is made for each distinct selected scenery type, never more than six.
- Radius at or below 50 km uses `/v5/place/around` with exactly `key,keywords,location,radius,sortrule=weight,region,city_limit=true,show_fields=business,page_size=25,page_num=1,output=json`; `radius` is rounded meters clamped to 1-50000.
- Radius above 50 km uses `/v5/place/text` with exactly `key,keywords,region,city_limit=true,show_fields=business,page_size=25,page_num=1,output=json`, then applies a local haversine coarse filter before the AMap distance hard filter.
- Merge order is selected scenery order, then provider order. Duplicate POIs use nonblank POI ID first. A no-ID valid entry uses normalized name plus coordinates rounded to six decimals and receives `amap:synthetic:` plus the first 16 SHA-256 hex characters of that key.
- Skip an individual POI missing `name/location/type/typecode` or having invalid coordinates. A declared `count>0` response whose entries are all malformed raises `bad_response`; a valid empty `pois` list returns no candidates.
- Returned `Destination` values retain AMap `type` and `typecode`, run through the deterministic scenery classifier, and receive `popularity_rank` from the merged provider order. Optional AMap ratings are not treated as a stable cross-category score.
- No selected type returns an empty list without an HTTP call.

- [ ] **Step 5: Implement bounded POI search**

Use the approved scenery classifier from milestone 1 for final tags; search keywords only gather candidates. Fetch page 1 only. Preserve merged order as a one-based `provider_rank`. Cap the merged candidate pool at 25 before distance and weather calls. Do not hardcode AMap numeric classification codes as the sole classifier because their table can change.

- [ ] **Step 6: Write failing distance tests**

Assert one `/v3/distance` request contains exactly `key,origins,destination,type=1,output=json`, up to 100 pipe-separated origins, and one destination. Verify meters become kilometers, seconds become minutes, output order matches origin order, partial result count or a result-level error raises `bad_response`, and more than 100 origins is rejected locally. RoamBot accepts at most three origins, but the adapter still enforces the provider boundary.

- [ ] **Step 7: Implement distance measurement**

Format coordinates with at most six decimal places and no locale-dependent commas. Return `estimated=False`. The application uses this route for distance display and scoring only; it does not request route geometry or navigation steps.

- [ ] **Step 8: Verify and commit**

Run `backend/tests/unit/test_amap_provider.py`, full backend tests, and Ruff. Assert mock transport recorded only the expected endpoints and secrets did not appear in captured output. Commit `feat: integrate bounded AMap data adapters`.

### Task 4: QWeather Seven-Day Forecast Adapter

**Files:**
- Create: `backend/src/roambot/providers/qweather.py`
- Create: `backend/tests/fixtures/qweather/weather_7d_success.json`
- Test: `backend/tests/unit/test_qweather_provider.py`

**Interfaces:**
- Produces: `QWeatherProvider(http: ProviderHttpClient, api_key: str, today: Callable[[], date])`.
- Implements: `WeatherProvider.daily(coordinate: Coordinate, start: date, end: date) -> list[DailyWeather]`.
- Calls: `{account_api_host}/v7/weather/7d`.

- [ ] **Step 1: Write failing request-shape tests**

Use a fake account host and `httpx.MockTransport`. Assert the request:

- Uses exactly `/v7/weather/7d`.
- Sends exactly `location=120.70,31.32`, `lang=zh`, and `unit=m`; longitude precedes latitude and trailing zeros remain.
- Sends the fake key only in `X-QW-Api-Key`.
- Does not contain `key`, `token`, or credential text in the URL/query.
- Requests only dates within the returned seven-day range.
- Uses the supplied GCJ-02 coordinate without conversion; the live smoke later verifies Suzhou plausibility.

- [ ] **Step 2: Write failing response tests**

The synthetic fixture must cover `fxDate`, `tempMin`, `tempMax`, `textDay`, `textNight`, `windScaleDay`, `windSpeedDay`, `windScaleNight`, `windSpeedNight`, `humidity`, `precip`, `uvIndex`, and `vis`. Assert inclusive date filtering, finite numeric conversion, max(day/night) wind speed, identical text retained once, differing text joined with `转`, and stable ordering by date.

Also assert `forecast_unavailable` for a missing requested date or a date range outside `today..today+6`; `unavailable` for provider `code != "200"`; and `bad_response` for duplicate dates, missing required requested-day fields, malformed/nonfinite/range-invalid values, or `tempMin>tempMax`. Invalid JSON and timeout remain sanitized HTTP-boundary errors. Entries outside the requested interval need only a parseable `fxDate`; their other fields are ignored. No error or log may contain the fake key, full URL, or raw response.

- [ ] **Step 3: Implement the adapter**

Validate the configured base URL as HTTPS, no credentials/port/path/query/fragment, and host suffix `.qweatherapi.com`; reject legacy public hosts. Use the account-specific API Host from settings and API KEY header authentication. Fetch once per destination, index valid `fxDate` values, then strictly parse and select the requested inclusive range. Do not make one call per day.

Reject unsupported date ranges before HTTP with `ProviderError("forecast_unavailable", "所选日期超出七日天气预报范围")`. Preserve enough daily fields for the milestone 1 deterministic weather scorer; unknown optional fields are `None`, not zero.

- [ ] **Step 4: Verify and commit**

Run the focused test, full backend tests, and Ruff. Commit `feat: integrate QWeather daily forecasts`.

### Task 5: Cached Providers and Explicit Degradation

**Files:**
- Create: `backend/src/roambot/providers/cached.py`
- Create: `backend/src/roambot/providers/trace.py`
- Modify: `backend/src/roambot/providers/factory.py`
- Modify: `backend/src/roambot/services/recommendations.py`
- Test: `backend/tests/unit/test_cached_providers.py`
- Test: `backend/tests/unit/test_degradation_policy.py`
- Modify Test: `backend/tests/unit/test_provider_factory.py`
- Modify Test: `backend/tests/unit/test_recommendation_service.py`

**Interfaces:**
- Consumes: `CacheRepository` from milestone 2.
- Produces: `make_cache_key(provider:str,operation:str,params:Mapping[str,JsonValue])->str`, `CACHE_TTLS`, `CachedGeocoder`, `CachedPlaceProvider`, `CachedDistanceProvider`, `CachedWeatherProvider`, `ProviderEvent`, and request-scoped `ProviderTrace`.
- All cached constructors are `(inner,cache:CacheRepository,provider:str,clock:Callable[[],datetime],trace:ProviderTrace)`. Methods exactly preserve M1 protocols: `geocode(address,city)->Origin`; `search(center,city,scenery_types:tuple[SceneryType,...],radius_km)->list[Destination]`; `resolve(name,city)->Destination`; `measure(origins,destination)->list[DistanceEstimate]`; `daily(coordinate,start,end)->list[DailyWeather]`.
- `ProviderEvent(StrEnum)` has `CACHE,DEMO,WEATHER_EXCLUDED,STRAIGHT_LINE,TEMPLATE_EXPLANATION,INSUFFICIENT_CANDIDATES`; `ProviderTrace.mark(event)->None` and `.to_source_state(final_item_count:int)->SourceState`; `ProviderRuntime.new_request_bundle()->ProviderBundle`, whose fields are five providers plus `trace`.

- [ ] **Step 1: Write failing cache policy tests**

Use a fixed UTC clock and assert exact fresh TTLs from the approved design:

| Operation | Fresh TTL |
| --- | ---: |
| Geocode | 30 days |
| POI search/resolve | 7 days |
| Distance | 1 day |
| Weather | 60 minutes |
| LLM explanation | no cache |

Assert the five exact params scenarios and versioned payload envelopes from SPEC: geocode, POI search/DestinationList, POI resolve/Destination, distance, and weather. Include ordered scenery tuple/list, NFC/folded whitespace, ISO dates, six-place map coordinates and two-place weather coordinates. The digest includes schema version, provider and operation but never a credential or header. For every operation, `expires_at-1 microsecond` is fresh and skips the inner adapter; exactly at expiry it is a miss and calls the adapter. Provider errors never create cache rows, and expired rows are never stale fallbacks.

- [ ] **Step 2: Implement typed cache wrappers**

Implement the exact constructors/methods above. Use an injected `Callable[[],datetime]` that must return aware UTC, exact key/payload rules from SPEC, and TTLs `geocode=30d`, `poi_search=7d`, `distance=1d`, `weather=1h`. A fresh hit marks `ProviderEvent.CACHE`; a cache parse/model/version failure calls `cache.delete(key)`, then acts as a miss without logging raw payload. Cache only successful complete responses; do not use pickle.

- [ ] **Step 3: Write failing degradation matrix tests**

Cover these outcomes:

- Geocode/POI/distance/weather live success: `source_kind="live"` with no degradation notice.
- Any fresh cache hit: add fixed notice `使用未过期缓存结果`; do not expose raw cache keys or parameters.
- AMap POI failure without cache while the separate demo flag is explicitly enabled: Suzhou demo data may be used and must say demo; other cities return service unavailable.
- AMap POI failure without cache in live mode: never silently use Suzhou demo data.
- Weather failure for some candidates without cache: exclude those candidates from complete recommendation scoring and add a partial-weather notice.
- Weather failure for every remaining candidate without cache: fail the request, write no history record, and do not renormalize weights.
- Weather failure during specified-place evaluation without cache: fail the request because a complete evaluation cannot be produced.
- Distance failure without cache: compute each origin's haversine distance rounded to two decimals, set `duration_minutes=None,estimated=True`, enforce the maximum-distance filter against the primary-origin estimate, and add fixed notice `部分路程使用直线距离估算`.
- LLM failure: keep all scores and use deterministic templates.
- Geocode `not_found`: return a correctable address field error; provider outage without a fresh cache returns `503`. Never guess a coordinate.

- [ ] **Step 4: Implement bounded candidate selection and degradation in one orchestration boundary**

Before exact provider calls, coarse-filter merged POIs by primary-origin haversine distance while preserving the existing merge order (selected scenery-type order, then provider order), then take the first five. Do not resort or backfill after the exact-distance hard filter; returning fewer than five results is valid. This guarantees at most five distance and weather calls.

For each of those candidates, call exact distance first (or create straight-line estimates on distance provider failure), then apply the primary-origin maximum-distance hard filter. Only candidates that pass may call weather. “All weather failed” means every candidate that reached this weather step failed; candidates removed by distance do not enter that denominator. If none pass distance, return the normal 200 empty result and make zero weather calls.

Add exactly the fixed Chinese notices and order from SPEC without changing numeric scores after ranking. Represent the overall state with existing `SourceState.kind` using precedence `degraded > demo > cache > live`; partial weather, straight-line distance, or template explanation is degraded. If every remaining candidate lacks complete weather, raise `ProviderError("unavailable","全部候选天气数据暂时不可用")`, which the API maps to 503 `provider_unavailable`; do not write history. The frontend already renders this metadata from milestone 3.

`ProviderTrace` is mutable only inside one request bundle. It stores a set of `ProviderEvent` values and maps them to notices at response construction. Count every event that occurred in a successful request, including events from a candidate later excluded by precise distance or weather; failed responses have no `SourceState`. Mark insufficient candidates only after final items are known. Never use module globals, context variables, runtime fields, or raw-adapter fields for request events.

Do not catch validation bugs or programming exceptions as provider degradation. Only stable provider/cache errors enter this matrix.

- [ ] **Step 5: Verify and commit**

Run `./.venv/Scripts/python.exe -m pytest backend/tests/unit/test_cached_providers.py backend/tests/unit/test_degradation_policy.py backend/tests/unit/test_provider_factory.py backend/tests/unit/test_recommendation_service.py -q`, all backend tests, Ruff, `npm --prefix frontend test -- SearchWorkspace.test.tsx ResultCard.test.tsx`, and the mock Playwright guest journey. Commit `feat: apply provider cache and degradation policy`.

### Task 6: OpenAI-Compatible Explanation Adapter

**Files:**
- Create: `backend/src/roambot/providers/openai_compatible.py`
- Test: `backend/tests/unit/test_explanation_provider.py`

**Interfaces:**
- Implements: `ExplanationProvider.explain(items)`.
- Calls: `{llm_base_url}/chat/completions` once for zero to five final items.

- [ ] **Step 1: Write failing request tests**

Use `httpx.MockTransport`. Assert an empty list returns empty explanations with no call. For one to five items, assert one POST uses `Authorization: Bearer <fake>`, configured model, `temperature=0.2`, and a JSON response-format request when supported by the configured OpenAI-compatible endpoint.

The prompt contains only destination name, scenery labels, score breakdown, distance summaries, weather summary, and source limitations. It must not contain username, session, exact origin addresses, history ID, favorite state, share token, provider keys, or master password.

- [ ] **Step 2: Write failing response and privacy tests**

Require this parsed shape:

```json
{
  "explanations": [
    {"destination_id": "poi-1", "reason": "Short factual reason"}
  ]
}
```

Assert output is reordered to the input item order, every item appears exactly once, each reason is 20 to 180 Unicode characters after trimming, unknown IDs are rejected, markdown/code fences are rejected, and malformed/partial responses raise `ProviderError("bad_response", "AI 解释格式无效")`. Assert captured logs contain neither bearer token nor prompt content.

- [ ] **Step 3: Implement one-call structured explanation**

Build a short Chinese system instruction that forbids invented facts and asks only for recommendation reasons derived from supplied fields. Post to `/chat/completions`; parse `choices[0].message.content` as JSON with a strict Pydantic model. Do not let LLM output alter rank, score, scenery tags, weather, distance, or popularity.

If the endpoint rejects JSON response format, do not automatically make a second request because the one-call budget is locked. Raise a provider error and let the existing deterministic template fallback run.

- [ ] **Step 4: Verify and commit**

Run explanation tests, all backend tests, and Ruff. Commit `feat: add bounded AI recommendation explanations`.

### Task 7: Manual Live Smoke Command and Credential Handoff

**Files:**
- Modify: `backend/src/roambot/cli.py`
- Create: `backend/tests/integration/test_provider_smoke_cli.py`
- Modify: `backend/README.md`

**Interfaces:**
- Produces: `roambot providers smoke`.
- This is the first and only task that asks the user to obtain and enter real credentials.

- [ ] **Step 1: Write a zero-network CLI test**

Inject mock adapters and a fixed clock. Assert the command executes one bounded Suzhou request, prints provider names, redacted success/failure status, call counts, cache state, candidate count, and generated timestamp. It must never print keys, master password, raw headers, full request URLs, exact account origin addresses, or LLM prompt.

- [ ] **Step 2: Implement the smoke command**

The command requires `ROAMBOT_PROVIDER_MODE=live`, unlocks the vault using a hidden prompt, and runs this fixed low-cost sequence:

1. Geocode one public landmark in Suzhou.
2. Resolve one named Suzhou destination.
3. Measure one distance.
4. Fetch one seven-day forecast and select the next valid day.
5. Request one explanation for one synthetic scored result.

Add `--skip-llm` and provider-specific `--only amap|qweather|llm` options so credentials can be verified independently. A failure exits nonzero after a sanitized message. Do not retry automatically.

- [ ] **Step 3: Pause for credential handoff**

Only now ask the user to create the AMap Web Service key, QWeather API key plus account-specific API Host, and school OpenAI-compatible key/base URL/model. Instruct the user to run local hidden CLI prompts; never ask them to paste values into chat.

Run `roambot credentials status` and report only configured booleans. If a provider is not configured, run the smoke test for configured providers and record the skipped one; do not block mock-mode delivery.

- [ ] **Step 4: Run the manual smoke with explicit approval**

Before a real call, state the exact five-call maximum and ask for approval because it may consume provider quota. Then run the local command once. Record only sanitized status and call counts in `AGENT_LOG.md`; do not record returned personal/location payloads or credentials.

- [ ] **Step 5: Verify and commit**

Run CLI tests and full backend tests in mock mode. Commit `feat: add explicit live-provider smoke checks`.

### Task 8: Production Static Serving and Single Docker Image

**Files:**
- Modify: `backend/src/roambot/main.py`
- Create: `backend/src/roambot/entrypoint.py`
- Create: `backend/tests/api/test_static_serving.py`
- Create: `backend/tests/unit/test_entrypoint.py`
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `docker-compose.yml`

**Interfaces:**
- Produces: `create_app(frontend_dist: Path | None = None)`, `resolve_master_password(...)`, `entrypoint.main() -> int`, and one image serving `/api/v1` plus the React SPA on port 8000 with persistent `/data`.

- [ ] **Step 1: Write failing static-serving tests**

With a temporary frontend directory containing only `index.html` and `assets/app.js`, assert `/` and `/history` return `index.html`, the real asset returns its content type, `/api/v1/health` is never captured, `/api/v1/missing` is JSON 404, and missing asset or other suffixed paths return 404 rather than HTML. `create_app(None)` keeps API routes working without static routes, matching Vite development.

- [ ] **Step 2: Implement production SPA serving**

Mount `/assets` with `StaticFiles` and add a final GET fallback only for paths without a file suffix and outside `/api`. Inject `frontend_dist` into `create_app`; production entrypoint uses `/app/frontend/dist` and exits 78 if index is absent. Keep API exception envelopes JSON.

- [ ] **Step 3: Write failing entrypoint tests**

Assert mock mode starts without a vault; live mode reads the master password from `/run/secrets/roambot_master_password` or non-secret path override `ROAMBOT_MASTER_PASSWORD_FILE`, rejects group/world-readable secret-file permissions where POSIX modes are exposed, removes trailing CR/LF only, and can prompt with `getpass` only when stdin is a TTY. Non-interactive live mode without the file returns exit code 78 with `RoamBot live mode requires a readable master-password file` and no attempted Uvicorn start.

- [ ] **Step 4: Implement startup credential boundary**

`entrypoint.py` unlocks the vault once, validates `/app/frontend/dist/index.html`, passes plaintext values only in memory to `create_app`, zeroes mutable byte buffers where practical, and never places the master password in environment variables or process arguments. It starts Uvicorn on fixed `0.0.0.0:8000`.

- [ ] **Step 5: Create the production Dockerfile**

Use three pinned-major stages:

1. `node:24-alpine` installs with `npm ci` and builds `frontend/dist`.
2. `python:3.13-slim` builds a backend wheel.
3. `python:3.13-slim` installs the wheel, copies static output, creates a non-root `roambot` user, exposes 8000, declares `/data`, and starts `python -m roambot.entrypoint`.

Set `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`, and non-secret `ROAMBOT_DATA_DIR=/data`. Do not copy `.git`, `.env`, `data`, vault files, test artifacts, screenshots, `node_modules`, or real credentials. Add an HTTP health check against `/api/v1/health`.

- [ ] **Step 6: Add local Compose without embedding secrets**

Compose service name is `roambot`; it builds the image, publishes `8000:8000`, mounts named volume `roambot-data:/data`, defaults to mock/demo mode, and uses the fixed secret-file mechanism only under an explicit live profile. It must not contain a key or master password literal.

- [ ] **Step 7: Build and inspect**

Run:

```powershell
docker build -t roambot:local .
docker history --no-trunc roambot:local
docker run --rm -d --name roambot-check -p 8000:8000 -v roambot-check-data:/data -e ROAMBOT_PROVIDER_MODE=mock -e ROAMBOT_DEMO_MODE=true roambot:local
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
Invoke-WebRequest http://127.0.0.1:8000/
Invoke-WebRequest http://127.0.0.1:8000/history
docker stop roambot-check
```

Verify health, `/`, one SPA route, and one mock recommendation. Inspect history/output for known fake-secret patterns. Stop and remove only `roambot-check`; keep the named volume unless the user explicitly approves deleting it.

- [ ] **Step 8: Verify and commit**

Run static/entrypoint tests, full test script, and a fresh Docker build. Commit `build: package RoamBot as one Docker image`.

### Task 9: GitLab CI with Zero Real Provider Calls

**Files:**
- Create: `ci/Dockerfile`
- Create: `.gitlab-ci.yml`
- Create: `backend/tests/integration/test_network_guard.py`
- Modify: `scripts/test.sh`

**Interfaces:**
- Produces: required `unit-test` job plus production image build/push jobs.

- [ ] **Step 1: Write a network-denial test**

Patch socket connection creation in the backend test session and fail any outbound connection except loopback ports used by Playwright. Assert every provider test uses `MockTransport` or mock providers. Add a frontend test that fails if production code contains hardcoded AMap, QWeather, bearer-token, or master-password patterns.

- [ ] **Step 2: Build one reproducible CI test image**

Create `ci/Dockerfile` from `python:3.13-slim-bookworm`, copy Node runtime from `node:24-bookworm-slim`, install only Playwright Chromium system dependencies through `npx playwright install --with-deps chromium`, install backend dev dependencies with the lock/metadata files, run `npm ci`, and copy the repository last. The default command is `./scripts/test.sh`.

- [ ] **Step 3: Add exact GitLab jobs**

Use `docker:29-cli` plus `docker:29-dind` and these stages:

```yaml
stages:
  - test
  - build
```

The `unit-test` job builds `ci/Dockerfile` and runs it with:

```text
ROAMBOT_PROVIDER_MODE=mock
ROAMBOT_DEMO_MODE=true
NO_PROXY=127.0.0.1,localhost
```

Do not define provider credentials in CI. The `docker-build` job runs only after `unit-test`, builds the production Dockerfile, starts the image in mock mode, waits for the health check, performs one API smoke request, then pushes `$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA`. Push `latest` only from the default branch. Use GitLab predefined registry credentials, not project source files.

- [ ] **Step 4: Validate locally**

Run:

```powershell
docker build -f ci/Dockerfile -t roambot-ci:local .
docker run --rm -e ROAMBOT_PROVIDER_MODE=mock -e ROAMBOT_DEMO_MODE=true roambot-ci:local
```

Expected: backend tests, Ruff, Vitest, frontend lint/build, and Playwright all pass; network guard reports no real provider connections.

Validate `.gitlab-ci.yml` with GitLab CI Lint when repository access is configured. If it is unavailable, record that limitation rather than claiming remote CI success.

- [ ] **Step 5: Verify and commit**

Run `git diff --check`, scan tracked files for secret patterns, and commit `ci: test and package RoamBot without live credentials`.

### Task 10: Documentation, Assignment Evidence, and Final Verification

**Files:**
- Modify: `README.md`
- Modify: `backend/README.md`
- Create: `REFLECTION.md`
- Modify: `AGENT_LOG.md`
- Modify: `TASKS.md`
- Create: `docs/evidence/verification.md`

**Interfaces:**
- Produces: reproducible runbook and assignment evidence without secret or personal data.

- [ ] **Step 1: Write the top-level runbook**

Document prerequisites, mock quick start, separate frontend/backend development, one-image Docker start, SQLite volume backup, migrations, credential CLI, live non-secret settings, secret-file startup, smoke command cost boundary, tests, GitLab pipeline, cache TTLs, degradation behavior, and reset consequences.

State clearly:

- Forgetting the vault master password means the old encrypted API keys cannot be recovered; reset deletes only the vault file and requires re-entering keys.
- Anyone able to reset the vault already has local filesystem/process access; reset does not grant them the original keys, but they could configure their own keys, so OS account permissions and host access still matter.
- Automated tests cost zero provider quota because they force mock mode.
- The app does not provide maps, route planning, navigation, or itineraries.
- V1 does not provide phone/SMS/CAPTCHA/email/OAuth/password recovery.

- [ ] **Step 2: Complete reflection and traceability**

Update `REFLECTION.md` with design choices, tradeoffs, AI-assisted workflow, mock-versus-live testing, privacy controls, cost controls, known limits, and future mini-program possibility outside V1. Update `TASKS.md` only from fresh command evidence. Add the final decision/iteration summary to `AGENT_LOG.md` without reproducing chat or credentials.

- [ ] **Step 3: Create verification evidence**

`docs/evidence/verification.md` records date, environment versions, exact commands, exit status, test counts, Docker image ID/size, health result, responsive viewports checked, and whether real-provider smoke was run or skipped. Link selected Playwright screenshots only if they contain no account names, exact personal origins, keys, tokens, or cookies.

- [ ] **Step 4: Run the complete fresh verification**

From a clean process state, run:

```powershell
./scripts/test.ps1
git diff --check
git grep -n -I -E "(AIza|sk-[A-Za-z0-9]|Bearer [A-Za-z0-9]|X-QW-Api-Key:|amap_api_key[[:space:]]*=|qweather_api_key[[:space:]]*=|llm_api_key[[:space:]]*=)" -- . ":(exclude)docs/superpowers/plans/*"
docker build -t roambot:final .
```

The grep command must return no tracked credential values; documentation may mention field names but must not contain values. Start `roambot:final` in mock mode, wait for healthy state, then verify `/`, `/api/v1/health`, guest recommendation, registration/login, favorite, history, share, and public share revocation.

- [ ] **Step 5: Inspect final scope and worktree**

Run `git status --short` and review every changed path. Confirm there are no `.env` files, vaults, SQLite databases, `node_modules`, build outputs, Playwright traces, unapproved screenshots, route/map libraries, phone/SMS/CAPTCHA packages, or unrelated user-file edits staged for commit.

- [ ] **Step 6: Request final code review**

Use `superpowers:requesting-code-review` against the approved design and all four implementation plans. Address verified findings using `superpowers:receiving-code-review`, rerun affected tests, then rerun the complete verification before any completion claim.

- [ ] **Step 7: Commit final documentation**

After fresh evidence passes, commit `docs: finalize RoamBot delivery evidence`. Do not claim remote GitLab success or real-provider success unless those checks actually ran and passed.

## Milestone Exit Criteria

- Real adapters satisfy the milestone 1 protocols and are covered by mock-transport contract tests.
- Automated tests and CI make zero real provider calls and use zero provider quota.
- Provider keys remain in the encrypted vault and plaintext exists only in process memory after an approved unlock.
- Per-request budgets, fresh-cache TTLs, partial/all-weather failure handling, straight-line distance fallback, and template explanation fallback match this plan.
- Production serves the React SPA and `/api/v1` from one non-root Docker image with persistent SQLite data.
- The GitLab `unit-test` job and production build are reproducible, or any unavailable remote validation is explicitly recorded.
- README, reflection, task evidence, and final verification match the implemented application without extending V1 scope.
