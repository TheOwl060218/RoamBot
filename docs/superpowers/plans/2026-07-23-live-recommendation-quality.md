# RoamBot Live Recommendation Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make live recommendations type-balanced, weather-aware by scene, rating-based, and useful even when LLM explanation generation degrades.

**Architecture:** Extend the existing immutable Pydantic domain models, keep scoring and candidate selection deterministic in the backend, and treat the LLM as an optional two-item-at-a-time copy editor over local factual reasons. Preserve existing request and score wire keys for stored-history compatibility while adding nullable AMap ratings and explicit travel-advice fields.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, pytest, React 19, TypeScript 6, Vitest, Playwright.

## Global Constraints

- Do not add dependencies or AMap/QWeather SDKs.
- Keep `RankingWeights.popularity` and `ScoreBreakdown.popularity` as compatibility wire keys; their new meaning is the location-rating dimension.
- Keep the user-facing heading `推荐理由`.
- AMap rating must come from the existing POI search response with `show_fields=business`; do not add detail requests.
- Hard limits per recommendation: geocode 3, POI search 6, distance 7, weather 7, LLM 4.
- Each LLM request contains at most 2 destinations, receives no precise origin text, and is never retried automatically.
- Automated tests and CI use Mock/demo providers only; live providers run only with explicit user approval.
- This pass makes only the minimal frontend changes needed for the new data. The saved two-column and multi-day visual redesign remains out of scope.

---

### Task 1: Domain Models, Scene-Aware Weather, and Rating Scoring

**Files:**
- Modify: `backend/src/roambot/domain/models.py`
- Modify: `backend/src/roambot/domain/scoring.py`
- Modify: `backend/src/roambot/domain/ranking.py`
- Test: `backend/tests/unit/test_models.py`
- Test: `backend/tests/unit/test_scoring.py`
- Test: `backend/tests/unit/test_ranking.py`

**Interfaces:**
- Produces: `SceneryExposure`, `TravelAdviceStatus`, `OverallAdviceStatus` enums.
- Produces: `Destination.rating: float | None`, constrained to `0..5`.
- Produces: `DailySuitability.status`, `DailySuitability.summary`, and `RecommendationItem.overall_advice`.
- Produces: `score_rating(rating: float) -> float` and rating-aware `final_score(..., popularity: float | None, ...)`.
- Preserves: existing `popularity` compatibility keys and `coverage_penalty`, which becomes `0` for list-level coverage.

- [ ] **Step 1: Add failing domain and scoring tests**

```python
def test_destination_accepts_optional_five_point_rating() -> None:
    assert destination(rating=4.7).rating == 4.7
    assert destination(rating=None).rating is None

def test_same_extreme_heat_penalizes_outdoor_more_than_indoor() -> None:
    outdoor = score_daily_weather(hot_day(), frozenset({SceneryType.LAKE}))
    indoor = score_daily_weather(hot_day(), frozenset({SceneryType.MUSEUM}))
    assert outdoor.score == 60
    assert indoor.score == 85
    assert outdoor.status == TravelAdviceStatus.CAUTION
    assert "最高温度预计达到36℃" in outdoor.summary

def test_rating_is_scaled_and_missing_rating_reallocates_weight() -> None:
    assert score_rating(4.7) == 94
    assert final_score(80, 70, 100, None, weights(), coverage_ratio=1) == 75.71
```

- [ ] **Step 2: Run the focused tests and confirm they fail**

Run: `./.venv/Scripts/python.exe -m pytest backend/tests/unit/test_models.py backend/tests/unit/test_scoring.py backend/tests/unit/test_ranking.py -q`

Expected: FAIL because rating and advice fields and `score_rating` do not exist.

- [ ] **Step 3: Add enums, fields, and exposure-aware weather calculation**

```python
class TravelAdviceStatus(StrEnum):
    SUITABLE = "suitable"
    CAUTION = "caution"
    NOT_RECOMMENDED = "not_recommended"

class OverallAdviceStatus(StrEnum):
    SUITABLE = "suitable"
    SOME_DATES_CAUTION = "some_dates_caution"
    SOME_DATES_NOT_RECOMMENDED = "some_dates_not_recommended"

class Destination(DomainModel):
    # existing fields remain unchanged
    rating: float | None = Field(default=None, ge=0, le=5)

class DailySuitability(DomainModel):
    date: date
    score: float = Field(ge=0, le=100)
    status: TravelAdviceStatus
    summary: str = Field(min_length=1)
    reasons: list[str] = Field(min_length=1)
```

Implement an internal exposure classifier: museum-only is indoor, outdoor tags are outdoor, mixed tags or missing tags are mixed. Apply the exact penalty matrix and `75/50` status thresholds from the approved design. Build `summary` from the actual date and weather values without exposing numeric deductions.

- [ ] **Step 4: Replace rank scoring with rating scaling and missing-value normalization**

```python
def score_rating(rating: float) -> float:
    if not 0 <= rating <= 5:
        raise ValueError("rating must be between zero and five")
    return clamp(rating * 20)

def final_score(weather, distance, fairness, popularity, weights, coverage_ratio):
    base_values = {"weather": weather, "distance": distance, "popularity": popularity}
    available = {name: value for name, value in base_values.items() if value is not None}
    total_weight = sum(weights.model_dump().values())
    fairness_fraction = weights.fairness / total_weight
    base_fraction = 1 - fairness_fraction
    available_weight = sum(getattr(weights, name) for name in available)
    weighted_base = sum(
        available[name] * getattr(weights, name) / available_weight
        for name in available
    )
    return clamp(weighted_base * base_fraction + fairness * fairness_fraction)
```

For multi-origin requests, keep fairness at its fixed 20%; when rating is absent, renormalize only the weather/distance share inside the remaining 80% and then add fairness.

- [ ] **Step 5: Run focused tests and commit**

Run: `./.venv/Scripts/python.exe -m pytest backend/tests/unit/test_models.py backend/tests/unit/test_scoring.py backend/tests/unit/test_ranking.py -q`

Expected: PASS.

Commit: `git commit -am "feat: add scene-aware advice and rating scoring"`

---

### Task 2: AMap and Mock Rating Data

**Files:**
- Modify: `backend/src/roambot/providers/amap.py`
- Modify: `backend/src/roambot/providers/mock.py`
- Modify: `backend/tests/fixtures/amap/poi_around_success.json`
- Modify: `backend/tests/fixtures/amap/poi_text_success.json`
- Test: `backend/tests/unit/test_amap_provider.py`
- Test: `backend/tests/unit/test_mock_providers.py`

**Interfaces:**
- Consumes: `Destination.rating` from Task 1.
- Produces: `_optional_rating(raw: object) -> float | None` for AMap `business.rating` parsing.
- Preserves: `popularity_rank` as a type-local fallback tie-breaker only.

- [ ] **Step 1: Add failing provider tests**

```python
def test_search_parses_business_rating_without_extra_request() -> None:
    results = provider.search(center, "苏州", (SceneryType.LAKE,), 20)
    assert [item.rating for item in results] == [4.8, 4.5]
    assert len(requests) == 1

@pytest.mark.parametrize("raw", [None, "", "[]", "bad", "6.0", -1])
def test_invalid_or_missing_business_rating_becomes_none(raw) -> None:
    assert parsed_destination_with_rating(raw).rating is None
```

- [ ] **Step 2: Run provider tests and confirm failure**

Run: `./.venv/Scripts/python.exe -m pytest backend/tests/unit/test_amap_provider.py backend/tests/unit/test_mock_providers.py -q`

Expected: FAIL because parsed destinations do not expose ratings.

- [ ] **Step 3: Parse ratings and remove cross-type rank bias**

```python
def _optional_rating(raw: object) -> float | None:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if isfinite(value) and 0 <= value <= 5 else None

business = raw.get("business")
rating = _optional_rating(business.get("rating")) if isinstance(business, dict) else None
```

Assign `popularity_rank` from each individual type query's result order before merging and deduplicating. Do not enumerate the merged cross-type list. Add deterministic ratings plus one missing-rating sample to the built-in Suzhou destinations.

- [ ] **Step 4: Run tests and commit**

Run: `./.venv/Scripts/python.exe -m pytest backend/tests/unit/test_amap_provider.py backend/tests/unit/test_mock_providers.py -q`

Expected: PASS with one HTTP request per selected type and no POI detail request.

Commit: `git commit -am "feat: ingest AMap place ratings"`

---

### Task 3: Dynamic Candidate Selection and List-Level Coverage

**Files:**
- Modify: `backend/src/roambot/services/recommendations.py`
- Modify: `backend/src/roambot/providers/trace.py`
- Test: `backend/tests/unit/test_recommendation_service.py`
- Test: `backend/tests/unit/test_provider_budget.py`
- Test: `backend/tests/unit/test_degradation_policy.py`

**Interfaces:**
- Consumes: rating and travel-advice models from Tasks 1-2.
- Produces: `_target_count(request) -> int`, returning 5 for ANY and `clamp(types + 1, 5, 7)` for COVER_ALL.
- Produces: `_preselect_candidates(...) -> list[Destination]`, capped at 7.
- Produces: response-level `uncovered_scenery_types: list[SceneryType]`.

- [ ] **Step 1: Add failing recommendation-selection tests**

```python
def test_cover_all_selects_representative_per_requested_type() -> None:
    response = service(destinations=museums_then_lake_and_park()).recommend(cover_all_request())
    covered = set().union(*(item.destination.scenery_tags for item in response.items))
    assert set(cover_all_request().scenery_types) <= covered

def test_cover_all_target_is_selected_type_count_plus_one_capped_at_seven() -> None:
    assert len(service_with_many_candidates().recommend(request_with_six_types()).items) == 7

def test_bad_weather_keeps_outdoor_representative_with_not_recommended_status() -> None:
    item = find_lake(service(...).recommend(cover_all_request()).items)
    assert item.overall_advice == OverallAdviceStatus.SOME_DATES_NOT_RECOMMENDED

def test_provider_limits_allow_seven_distance_weather_and_four_llm_calls() -> None:
    assert DEFAULT_PROVIDER_LIMITS[ProviderOperation.DISTANCE] == 7
    assert DEFAULT_PROVIDER_LIMITS[ProviderOperation.WEATHER] == 7
    assert DEFAULT_PROVIDER_LIMITS[ProviderOperation.LLM] == 4
```

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `./.venv/Scripts/python.exe -m pytest backend/tests/unit/test_recommendation_service.py backend/tests/unit/test_provider_budget.py backend/tests/unit/test_degradation_policy.py -q`

Expected: FAIL because recommendation still stops at five merged candidates and uses per-item coverage penalties.

- [ ] **Step 3: Implement deterministic preselection and coverage notices**

```python
def _target_count(self, request: RecommendationRequest) -> int:
    if request.scenery_match_mode is SceneryMatchMode.ANY:
        return 5
    return max(5, min(7, len(set(request.scenery_types)) + 1))

def _preview_key(self, destination, center):
    rating_missing = destination.rating is None
    return (rating_missing, -(destination.rating or 0),
            self._haversine_km(center, destination.coordinate),
            destination.popularity_rank, destination.provider_id)
```

Filter by tag and rough radius, then in COVER_ALL mode greedily take the best candidate that covers each still-uncovered requested type. Fill remaining slots from the same deterministic preview order. Run exact distance and weather only for the selected maximum of seven candidates. Keep poor-weather candidates; continue the existing provider-unavailable exclusion behavior only when weather data itself is missing.

- [ ] **Step 4: Build daily and overall advice into scored items**

```python
def _overall_advice(days: list[DailySuitability]) -> OverallAdviceStatus:
    statuses = {day.status for day in days}
    if TravelAdviceStatus.NOT_RECOMMENDED in statuses:
        return OverallAdviceStatus.SOME_DATES_NOT_RECOMMENDED
    if TravelAdviceStatus.CAUTION in statuses:
        return OverallAdviceStatus.SOME_DATES_CAUTION
    return OverallAdviceStatus.SUITABLE
```

Set rating score to `score_rating(destination.rating)` or `None`, set `coverage_penalty=0`, and return uncovered types in a structured response field. Update limits to `3/6/7/7/4`.

- [ ] **Step 5: Run tests and commit**

Run: `./.venv/Scripts/python.exe -m pytest backend/tests/unit/test_recommendation_service.py backend/tests/unit/test_provider_budget.py backend/tests/unit/test_degradation_policy.py -q`

Expected: PASS, including maximum-call assertions and bad-weather outdoor retention.

Commit: `git commit -am "feat: balance recommendation types and advice"`

---

### Task 4: Factual Local Reasons and Batched LLM Polishing

**Files:**
- Modify: `backend/src/roambot/domain/models.py`
- Modify: `backend/src/roambot/providers/protocols.py`
- Modify: `backend/src/roambot/providers/openai_compatible.py`
- Modify: `backend/src/roambot/providers/mock.py`
- Modify: `backend/src/roambot/services/recommendations.py`
- Test: `backend/tests/unit/test_explanation_provider.py`
- Test: `backend/tests/unit/test_recommendation_service.py`
- Test: `backend/tests/unit/test_degradation_policy.py`

**Interfaces:**
- Produces: immutable `ExplanationContext` with requested types, match mode, and display weights.
- Changes: `ExplanationProvider.explain(items, context) -> list[str]`.
- Produces: `_local_explanation(item, context, coverage_kept) -> str`.

- [ ] **Step 1: Add failing local-fallback, privacy, and grouping tests**

```python
def test_seven_results_are_polished_in_groups_of_two_without_retry() -> None:
    response = service_with_group_two_failure().recommend(request_with_six_types())
    assert [len(call.items) for call in explainer.calls] == [2, 2, 2, 1]
    assert response.items[2].explanation.startswith("该地点符合")
    assert response.items[0].explanation.startswith("polished:")

def test_local_reason_contains_tradeoffs_and_no_internal_scores() -> None:
    reason = service(explanations_fail=True).recommend(request()).items[0].explanation
    assert "湖景" in reason and "公里" in reason and "推荐" in reason
    assert "scored" not in reason and "-40" not in reason

def test_llm_payload_excludes_precise_origin_and_internal_score_dump() -> None:
    assert PRIVATE_ORIGIN not in serialized_request
    assert '"score"' not in serialized_request
```

- [ ] **Step 2: Run explanation tests and confirm failure**

Run: `./.venv/Scripts/python.exe -m pytest backend/tests/unit/test_explanation_provider.py backend/tests/unit/test_recommendation_service.py backend/tests/unit/test_degradation_policy.py -q`

Expected: FAIL because the service makes one LLM call and falls back to an English score sentence.

- [ ] **Step 3: Generate local factual reasons before LLM calls**

```python
def _local_explanation(self, item, context, coverage_kept=False) -> str:
    matched = "、".join(localized_tag(tag) for tag in matched_requested_tags(item, context))
    distance = item.group_accessibility.average_distance_km
    advice = localized_overall_advice(item.overall_advice)
    rating = (
        f"高德评分 {item.destination.rating:.1f} / 5"
        if item.destination.rating is not None
        else "暂无高德评分"
    )
    coverage = "，同时补足了本次类型覆盖" if coverage_kept else ""
    return f"该地点符合你选择的{matched}{coverage}，平均路程约{distance:.2f}公里；{advice}。{rating}。"
```

Attach these local reasons to every item first. They must remain useful if every LLM call fails.

- [ ] **Step 4: Polish in independent two-item groups**

```python
for start in range(0, len(items), 2):
    group = items[start:start + 2]
    try:
        budget.consume(ProviderOperation.LLM)
        polished = self.explanations.explain(group, context)
    except (ProviderError, ProviderBudgetExceeded):
        degraded = True
        continue
    items[start:start + 2] = [
        item.model_copy(update={"explanation": text})
        for item, text in zip(group, polished, strict=True)
    ]
```

Send only public place facts, rounded distance/duration, weather/advice facts, selected types, coverage mode, and display weights. Do not send origin labels, addresses, raw score objects, credentials, or user/account identifiers. Validate exact destination IDs and reject malformed group output without retrying.

- [ ] **Step 5: Run tests and commit**

Run: `./.venv/Scripts/python.exe -m pytest backend/tests/unit/test_explanation_provider.py backend/tests/unit/test_recommendation_service.py backend/tests/unit/test_degradation_policy.py -q`

Expected: PASS with call sizes `[2, 2, 2, 1]` for seven items.

Commit: `git commit -am "feat: add factual batched recommendation reasons"`

---

### Task 5: API, History, and Public-Share Compatibility

**Files:**
- Modify: `backend/src/roambot/services/personal_data.py`
- Modify: `backend/src/roambot/api/routes/shares.py`
- Test: `backend/tests/api/test_recommendations.py`
- Test: `backend/tests/api/test_history.py`
- Test: `backend/tests/api/test_shares.py`

**Interfaces:**
- Consumes: rating, daily status/summary, overall advice, and uncovered-type fields from Tasks 1-4.
- Produces: public snapshots with only safe rating/advice fields.
- Preserves: old history snapshots by supplying `rating=None` and deriving missing display advice from saved weather/suitability data.

- [ ] **Step 1: Add failing API and compatibility tests**

```python
def test_recommendation_response_contains_rating_advice_and_coverage() -> None:
    payload = response.json()
    assert payload["items"][0]["destination"]["rating"] == 4.8
    assert payload["items"][0]["daily_suitability"][0]["status"] == "suitable"
    assert "overall_advice" in payload["items"][0]
    assert payload["uncovered_scenery_types"] == []

def test_old_snapshot_without_new_fields_still_opens_and_shares() -> None:
    public = share_old_snapshot_without_rating_or_advice()
    assert public["items"][0]["destination"]["rating"] is None
    assert public["items"][0]["daily_suitability"][0]["status"] in {
        "suitable", "caution", "not_recommended"
    }
```

- [ ] **Step 2: Run API tests and confirm failure**

Run: `./.venv/Scripts/python.exe -m pytest backend/tests/api/test_recommendations.py backend/tests/api/test_history.py backend/tests/api/test_shares.py -q`

Expected: FAIL because public allowlists and response models do not include the new fields.

- [ ] **Step 3: Extend safe projections with explicit legacy defaults**

```python
def _optional_field(value: dict[str, object], field: str, default: object) -> object:
    return value[field] if field in value else default

public_destination["rating"] = _optional_field(destination, "rating", None)
public_item["overall_advice"] = _optional_field(
    item, "overall_advice", _derive_legacy_overall_advice(suitability)
)
```

Add `status` and `summary` to the suitability safe projection, deriving them from the old saved score/reasons when absent. Do not expose distances, origin labels, precise origins, prompts, credentials, or cookies. Keep private history data immutable.

- [ ] **Step 4: Run API tests and commit**

Run: `./.venv/Scripts/python.exe -m pytest backend/tests/api/test_recommendations.py backend/tests/api/test_history.py backend/tests/api/test_shares.py -q`

Expected: PASS for both new and old snapshot shapes.

Commit: `git commit -am "feat: expose safe rating and advice snapshots"`

---

### Task 6: Minimal Frontend Rendering

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/features/search/WeightSegments.tsx`
- Modify: `frontend/src/features/search/ResultCard.tsx`
- Modify: `frontend/src/features/search/ResultList.tsx`
- Modify: `frontend/src/features/search/DailyWeatherList.tsx`
- Modify: `frontend/src/features/shares/PublicSharePage.tsx`
- Modify: `frontend/src/styles/results.css`
- Test: `frontend/tests/WeightSegments.test.tsx`
- Test: `frontend/tests/ResultCard.test.tsx`
- Test: `frontend/tests/SearchWorkspace.test.tsx`
- Test: `frontend/tests/PersonalPages.test.tsx`

**Interfaces:**
- Consumes: new backend rating/advice fields and uncovered-type list.
- Preserves: internal TypeScript key `popularity` for request/score compatibility.
- Displays: `地点评分`, `X.X / 5` or `暂无数据`, Chinese dates, text travel advice, and one source/index notice per result area.

- [ ] **Step 1: Update fixtures and add failing component expectations**

```tsx
expect(screen.getByText('地点评分')).toBeInTheDocument()
expect(screen.getByText('4.8 / 5')).toBeInTheDocument()
expect(screen.getByText('7月25日')).toBeInTheDocument()
expect(screen.getByText('谨慎考虑')).toBeInTheDocument()
expect(screen.getByRole('heading', { name: '推荐理由' })).toBeInTheDocument()
expect(screen.queryByText(/极端温度\s*-40|适宜程度/)).not.toBeInTheDocument()
expect(screen.getAllByText(/地点评分数据来源：高德开放平台/)).toHaveLength(1)
```

- [ ] **Step 2: Run frontend tests and confirm failure**

Run: `npm --prefix frontend test -- WeightSegments.test.tsx ResultCard.test.tsx SearchWorkspace.test.tsx PersonalPages.test.tsx`

Expected: FAIL because current UI uses popularity labels, slash dates, and raw internal weather reasons.

- [ ] **Step 3: Add types and render explicit status text**

```ts
export type TravelAdviceStatus = 'suitable' | 'caution' | 'not_recommended'
export type OverallAdviceStatus =
  | 'suitable'
  | 'some_dates_caution'
  | 'some_dates_not_recommended'

export type DailySuitability = {
  date: string
  score: number
  status: TravelAdviceStatus
  summary: string
  reasons: string[]
}
```

Render `new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric', timeZone: 'UTC' })`, the localized status label, and `summary`. Do not render score or raw penalty reasons. Keep “推荐理由” unchanged.

- [ ] **Step 4: Rename visible popularity copy and centralize the source note**

```tsx
<div><span>地点评分</span><strong>{
  destination.rating === null ? '暂无数据' : `${destination.rating.toFixed(1)} / 5`
}</strong></div>
```

Change the segmented-weight legend to `地点评分` while retaining the `popularity` object key. Put the combined AMap source and candidate-comparison notice once in `ResultList` and once on the standalone public-share page, not in each card.

- [ ] **Step 5: Apply only minimal CSS for hierarchy and wrapping**

Add stable classes for advice status, rating, and daily summary. Do not redesign the two-column page or solve the saved 2-7-day layout backlog in this task.

- [ ] **Step 6: Run frontend checks and commit**

Run: `npm --prefix frontend test -- WeightSegments.test.tsx ResultCard.test.tsx SearchWorkspace.test.tsx PersonalPages.test.tsx`

Run: `npm --prefix frontend run build`

Expected: tests PASS and Vite production build succeeds.

Commit: `git commit -am "feat: present ratings and travel advice"`

---

### Task 7: Integrated Verification and Evidence

**Files:**
- Modify: `docs/evidence/verification.md`

**Interfaces:**
- Consumes: completed backend and frontend behavior from Tasks 1-6.
- Produces: reproducible verification evidence without live-provider charges.

- [ ] **Step 1: Run the complete backend quality gate**

Run: `./.venv/Scripts/python.exe -m pytest backend/tests -q`

Run: `./.venv/Scripts/python.exe -m ruff check backend`

Expected: all tests pass and Ruff reports no violations.

- [ ] **Step 2: Run the complete frontend quality gate**

Run: `npm --prefix frontend test`

Run: `npm --prefix frontend run lint`

Run: `npm --prefix frontend run build`

Expected: Vitest, ESLint, and the production build all pass.

- [ ] **Step 3: Run one consolidated Mock Playwright pass**

Run: `npm --prefix frontend run e2e`

Expected: recommendation, account/history, public share, and responsive smoke tests pass without live API calls.

- [ ] **Step 4: Record actual evidence and commit**

Append only actual command results, test counts, dates, and any intentionally deferred visual items to `docs/evidence/verification.md`.

Run: `git add docs/evidence/verification.md`

Commit: `git commit -m "docs: record recommendation quality verification"`
