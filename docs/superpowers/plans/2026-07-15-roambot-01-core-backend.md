# RoamBot Core Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable, provider-independent FastAPI vertical slice for recommendation and specified-place evaluation using deterministic mock providers.

**Architecture:** Domain models and scoring functions are pure and provider-independent. Provider protocols isolate geocoding, POI search, distance, weather, and explanation. `RecommendationService` orchestrates those protocols, while `/api/v1/recommendations` and `/api/v1/place-evaluations` expose stable JSON contracts.

**Tech Stack:** Python 3.13, FastAPI 0.139+, Pydantic v2, httpx, pytest, Ruff.

## Global Constraints

- Read `docs/plans/2026-07-15-roambot-design.md` and `docs/superpowers/plans/2026-07-15-roambot-roadmap.md` before editing.
- Use mock providers only; this milestone must work without real API credentials or network access.
- Keep all scores in 0-100 and use `mean(daily) * 0.70 + min(daily) * 0.30` for the multi-day weather score.
- Single-person defaults are weather 40, distance 30, popularity 30; multi-person defaults are weather 40, fairness 40, popularity 20, distance 0.
- Scenery match and primary-origin maximum distance are hard filters.
- Do not implement persistence, accounts, real providers, maps, routes, navigation, or frontend files in this plan.
- Every task follows red-green-refactor and ends with a focused commit.

---

## File Map

- `backend/pyproject.toml`: Python package metadata, runtime/dev dependencies, pytest and Ruff configuration.
- `backend/src/roambot/main.py`: FastAPI application factory.
- `backend/src/roambot/api/errors.py`: stable error envelope and exception handlers.
- `backend/src/roambot/api/dependencies.py`: request-scoped `RecommendationService` dependency.
- `backend/src/roambot/api/routes/health.py`: health endpoint.
- `backend/src/roambot/api/routes/recommendations.py`: public core endpoints.
- `backend/src/roambot/domain/models.py`: all provider-independent request/result types.
- `backend/src/roambot/domain/scenery.py`: deterministic POI-to-scenery mapping.
- `backend/src/roambot/domain/scoring.py`: daily weather, aggregate weather, distance, fairness, popularity functions.
- `backend/src/roambot/domain/ranking.py`: hard filters, coverage penalty, weight normalization, final ordering.
- `backend/src/roambot/providers/protocols.py`: provider interfaces and provider errors.
- `backend/src/roambot/providers/mock.py`: deterministic Suzhou fixtures.
- `backend/src/roambot/services/recommendations.py`: orchestration and template explanation fallback.
- `backend/tests/unit/`: pure domain/service tests.
- `backend/tests/api/`: FastAPI contract tests.

### Task 1: Python Package and Health Endpoint

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/src/roambot/__init__.py`
- Create: `backend/src/roambot/main.py`
- Create: `backend/src/roambot/api/__init__.py`
- Create: `backend/src/roambot/api/routes/__init__.py`
- Create: `backend/src/roambot/api/routes/health.py`
- Test: `backend/tests/api/test_health.py`

**Interfaces:**
- Produces: `roambot.main.create_app() -> FastAPI` and `GET /api/v1/health`.

- [ ] **Step 1: Verify the required interpreter**

Run:

```powershell
python --version
```

Expected: `Python 3.13.x`. If `python` is missing, stop and ask the user to approve installing Python 3.13; do not substitute the Microsoft Store alias.

- [ ] **Step 2: Create package metadata**

Create `backend/pyproject.toml`:

```toml
[build-system]
requires = ["hatchling>=1.27,<2"]
build-backend = "hatchling.build"

[project]
name = "roambot"
version = "0.1.0"
requires-python = ">=3.13,<3.15"
dependencies = [
  "fastapi>=0.139,<1",
  "httpx>=0.28,<1",
  "pydantic>=2.11,<3",
  "uvicorn>=0.35,<1",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.4,<9",
  "pytest-cov>=6.2,<7",
  "ruff>=0.12,<1",
]

[tool.hatch.build.targets.wheel]
packages = ["src/roambot"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--strict-markers --strict-config"

[tool.ruff]
target-version = "py313"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM"]
```

Create `backend/src/roambot/__init__.py` as an empty file before installing so the hatch wheel target exists. Then install the editable package:

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install --upgrade pip
./.venv/Scripts/python.exe -m pip install -e "./backend[dev]"
```

Expected: all commands exit 0.

- [ ] **Step 3: Write the failing health test**

Create `backend/tests/api/test_health.py`:

```python
from fastapi.testclient import TestClient

from roambot.main import create_app


def test_health_returns_ready() -> None:
    response = TestClient(create_app()).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
```

- [ ] **Step 4: Run the test and observe failure**

Run:

```powershell
./.venv/Scripts/python.exe -m pytest backend/tests/api/test_health.py -q
```

Expected: FAIL during import because `roambot.main` does not exist.

- [ ] **Step 5: Implement the application factory**

Create empty `__init__.py` files in `backend/src/roambot/`, `backend/src/roambot/api/`, and `backend/src/roambot/api/routes/`.

Create `backend/src/roambot/api/routes/health.py`:

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ready"}
```

Create `backend/src/roambot/main.py`:

```python
from fastapi import FastAPI

from roambot.api.routes.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="RoamBot API", version="0.1.0")
    app.include_router(health_router, prefix="/api/v1")
    return app


app = create_app()
```

- [ ] **Step 6: Verify test and lint**

Run:

```powershell
./.venv/Scripts/python.exe -m pytest backend/tests/api/test_health.py -q
./.venv/Scripts/python.exe -m ruff check backend
```

Expected: `1 passed`; Ruff exits 0.

- [ ] **Step 7: Commit**

```powershell
git add backend/pyproject.toml backend/src backend/tests/api/test_health.py
git commit -m "build: initialize FastAPI backend"
```

### Task 2: Domain Contracts and Validation

**Files:**
- Create: `backend/src/roambot/domain/__init__.py`
- Create: `backend/src/roambot/domain/models.py`
- Test: `backend/tests/unit/test_models.py`

**Interfaces:**
- Produces: `RecommendationRequest`, `PlaceEvaluationRequest`, `Destination`, `DailyWeather`, `RankingWeights`, `RecommendationResponse`, and `PlaceEvaluationResponse`.
- Consumed by: every later backend and frontend contract task.

- [ ] **Step 1: Write request-validation tests**

Create `backend/tests/unit/test_models.py`:

```python
from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from roambot.domain.models import (
    PlaceEvaluationRequest,
    RecommendationRequest,
    SceneryMatchMode,
    SceneryType,
)


def valid_dates() -> tuple[date, date]:
    start = datetime.now(timezone(timedelta(hours=8))).date() + timedelta(days=1)
    return start, start + timedelta(days=2)


def test_recommendation_accepts_three_origins_and_scenery() -> None:
    start, end = valid_dates()
    request = RecommendationRequest(
        city="苏州",
        main_origin="苏州站",
        companion_origins=["苏州园区站", "苏州新区站"],
        max_distance_km=80,
        start_date=start,
        end_date=end,
        scenery_types=[SceneryType.LAKE, SceneryType.PARK],
        scenery_match_mode=SceneryMatchMode.ANY,
    )

    assert request.origin_count == 3


@pytest.mark.parametrize(
    "changes",
    [
        {"main_origin": " "},
        {"companion_origins": ["a", "b", "c"]},
        {"max_distance_km": 0},
        {"scenery_types": []},
    ],
)
def test_recommendation_rejects_invalid_inputs(changes: dict[str, object]) -> None:
    start, end = valid_dates()
    values: dict[str, object] = {
        "city": "苏州",
        "main_origin": "苏州站",
        "companion_origins": [],
        "max_distance_km": 80,
        "start_date": start,
        "end_date": end,
        "scenery_types": [SceneryType.LAKE],
        "scenery_match_mode": SceneryMatchMode.ANY,
    }
    values.update(changes)

    with pytest.raises(ValidationError):
        RecommendationRequest.model_validate(values)


def test_place_evaluation_has_target_and_no_scenery_input() -> None:
    start, end = valid_dates()
    request = PlaceEvaluationRequest(
        city="苏州",
        main_origin="苏州站",
        target_place="金鸡湖",
        max_distance_km=80,
        start_date=start,
        end_date=end,
    )

    assert request.target_place == "金鸡湖"
    assert "scenery_types" not in type(request).model_fields


def test_date_window_is_today_through_six_days_later() -> None:
    today = datetime.now(timezone(timedelta(hours=8))).date()
    valid = {
        "city": "苏州",
        "main_origin": "苏州站",
        "max_distance_km": 80,
        "start_date": today,
        "end_date": today + timedelta(days=6),
        "scenery_types": [SceneryType.LAKE],
    }

    RecommendationRequest.model_validate(valid)
    with pytest.raises(ValidationError):
        RecommendationRequest.model_validate(
            {**valid, "end_date": today + timedelta(days=7)}
        )
```

- [ ] **Step 2: Run tests and observe failure**

Run:

```powershell
./.venv/Scripts/python.exe -m pytest backend/tests/unit/test_models.py -q
```

Expected: FAIL because `roambot.domain.models` does not exist.

- [ ] **Step 3: Implement the complete domain contracts**

Create `backend/src/roambot/domain/__init__.py` and `backend/src/roambot/domain/models.py` with these exact public types:

```python
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class SceneryType(StrEnum):
    LAKE = "lake"
    SEA = "sea"
    OLD_TOWN = "old_town"
    MUSEUM = "museum"
    PARK = "park"
    MOUNTAIN = "mountain"


class SceneryMatchMode(StrEnum):
    ANY = "any"
    COVER_ALL = "cover_all"


class SourceKind(StrEnum):
    LIVE = "live"
    CACHE = "cache"
    DEMO = "demo"
    DEGRADED = "degraded"


class Coordinate(DomainModel):
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    system: str = "gcj02"


class RankingWeights(DomainModel):
    weather: float = Field(ge=0, le=100)
    distance: float = Field(ge=0, le=100)
    fairness: float = Field(ge=0, le=100)
    popularity: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def require_positive_total(self) -> RankingWeights:
        if self.weather + self.distance + self.fairness + self.popularity <= 0:
            raise ValueError("at least one ranking weight must be positive")
        return self


class TravelRequestBase(DomainModel):
    city: str = "苏州"
    main_origin: str = Field(min_length=1, max_length=200)
    companion_origins: list[str] = Field(default_factory=list, max_length=2)
    max_distance_km: float = Field(gt=0, le=500)
    start_date: date
    end_date: date
    weights: RankingWeights | None = None

    @field_validator("city")
    @classmethod
    def default_blank_city(cls, value: str) -> str:
        return value.strip() or "苏州"

    @field_validator("main_origin")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value

    @field_validator("companion_origins")
    @classmethod
    def strip_companions(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("companion origin must not be blank")
        return cleaned

    @model_validator(mode="after")
    def validate_dates(self) -> TravelRequestBase:
        china_time = timezone(timedelta(hours=8))
        today = datetime.now(china_time).date()
        if self.start_date < today or self.end_date < self.start_date:
            raise ValueError("date range must start today or later")
        if (self.end_date - today).days > 6:
            raise ValueError("date range must stay within the next 7 days")
        if self.weights is not None and self.origin_count == 1 and self.weights.fairness != 0:
            raise ValueError("single-origin fairness weight must be zero")
        return self

    @computed_field
    @property
    def origin_count(self) -> int:
        return 1 + len(self.companion_origins)


class RecommendationRequest(TravelRequestBase):
    scenery_types: list[SceneryType] = Field(min_length=1)
    scenery_match_mode: SceneryMatchMode = SceneryMatchMode.ANY


class PlaceEvaluationRequest(TravelRequestBase):
    target_place: str = Field(min_length=1, max_length=200)

    @field_validator("target_place")
    @classmethod
    def strip_target(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("target place must not be blank")
        return value


class Origin(DomainModel):
    label: str
    address: str
    coordinate: Coordinate


class Destination(DomainModel):
    provider_id: str
    name: str
    address: str
    city: str
    coordinate: Coordinate
    type_name: str
    type_code: str
    scenery_tags: frozenset[SceneryType] = frozenset()
    popularity_rank: int = Field(ge=1)


class DailyWeather(DomainModel):
    date: date
    condition: str
    temp_min_c: float
    temp_max_c: float
    precipitation_mm: float = Field(ge=0)
    wind_speed_kmh: float = Field(ge=0)
    humidity_percent: float = Field(ge=0, le=100)
    visibility_km: float = Field(ge=0)
    uv_index: float = Field(ge=0)


class DailySuitability(DomainModel):
    date: date
    score: float = Field(ge=0, le=100)
    reasons: list[str] = Field(min_length=1)


class DistanceEstimate(DomainModel):
    origin_label: str
    distance_km: float = Field(ge=0)
    duration_minutes: float | None = Field(default=None, ge=0)
    estimated: bool = False


class GroupAccessibilityScore(DomainModel):
    average_distance_km: float = Field(ge=0)
    max_distance_km: float = Field(ge=0)
    distance_variance: float = Field(ge=0)
    distance_stddev: float = Field(ge=0)
    fairness_score: float = Field(ge=0, le=100)


class ScoreBreakdown(DomainModel):
    weather: float = Field(ge=0, le=100)
    distance: float = Field(ge=0, le=100)
    fairness: float = Field(ge=0, le=100)
    popularity: float = Field(ge=0, le=100)
    coverage_penalty: float = Field(ge=0, le=100)
    total: float = Field(ge=0, le=100)


class SourceState(DomainModel):
    kind: SourceKind
    notices: list[str] = Field(default_factory=list)


class RecommendationItem(DomainModel):
    destination: Destination
    distances: list[DistanceEstimate]
    group_accessibility: GroupAccessibilityScore
    weather: list[DailyWeather]
    daily_suitability: list[DailySuitability]
    score: ScoreBreakdown
    explanation: str


class RecommendationResponse(DomainModel):
    items: list[RecommendationItem]
    source_state: SourceState
    generated_at: str


class PlaceEvaluationResponse(DomainModel):
    item: RecommendationItem
    source_state: SourceState
    generated_at: str
```

- [ ] **Step 4: Run tests**

Run:

```powershell
./.venv/Scripts/python.exe -m pytest backend/tests/unit/test_models.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/src/roambot/domain backend/tests/unit/test_models.py
git commit -m "feat: define travel domain contracts"
```

### Task 3: Deterministic Scenery Classification

**Files:**
- Create: `backend/src/roambot/domain/scenery.py`
- Create: `backend/src/roambot/domain/scenery_rules.py`
- Test: `backend/tests/unit/test_scenery.py`

**Interfaces:**
- Consumes: `SceneryType`.
- Produces: `classify_scenery(name, type_name, type_code, overrides) -> frozenset[SceneryType]`.

- [ ] **Step 1: Write classification tests**

```python
from roambot.domain.models import SceneryType
from roambot.domain.scenery import classify_scenery


def test_type_and_name_can_produce_multiple_tags() -> None:
    tags = classify_scenery(
        name="金鸡湖景区",
        type_name="风景名胜;公园广场;公园",
        type_code="110101",
        overrides={},
    )

    assert tags == frozenset({SceneryType.LAKE, SceneryType.PARK})


def test_override_replaces_ambiguous_rules() -> None:
    tags = classify_scenery(
        name="测试地点",
        type_name="风景名胜",
        type_code="110000",
        overrides={"测试地点": frozenset({SceneryType.MUSEUM})},
    )

    assert tags == frozenset({SceneryType.MUSEUM})


def test_unknown_place_is_not_guessed() -> None:
    assert classify_scenery("甲乙丙", "地名地址信息", "190000", {}) == frozenset()
```

- [ ] **Step 2: Run and observe failure**

Run `./.venv/Scripts/python.exe -m pytest backend/tests/unit/test_scenery.py -q`.

Expected: import failure for `roambot.domain.scenery`.

- [ ] **Step 3: Add explicit rule configuration**

Create `backend/src/roambot/domain/scenery_rules.py`:

```python
from roambot.domain.models import SceneryType

TYPE_TERMS: dict[SceneryType, list[str]] = {
    SceneryType.LAKE: ["湖泊", "水库", "湿地"],
    SceneryType.SEA: ["海滩", "海湾", "海滨"],
    SceneryType.OLD_TOWN: ["古镇", "历史建筑", "历史街区"],
    SceneryType.MUSEUM: ["博物馆", "纪念馆", "展览馆"],
    SceneryType.PARK: ["公园", "湿地", "植物园", "森林公园"],
    SceneryType.MOUNTAIN: ["山岳", "登山", "徒步", "森林公园"],
}

NAME_TERMS: dict[SceneryType, list[str]] = {
    SceneryType.LAKE: ["湖", "湿地", "水库"],
    SceneryType.SEA: ["海滩", "海湾", "海滨", "沙滩"],
    SceneryType.OLD_TOWN: ["古镇", "古城", "古街", "历史街区"],
    SceneryType.MUSEUM: ["博物馆", "纪念馆", "美术馆", "科技馆"],
    SceneryType.PARK: ["公园", "湿地", "植物园", "绿地"],
    SceneryType.MOUNTAIN: ["山", "峰", "岭", "步道", "徒步"],
}
```

Create `backend/src/roambot/domain/scenery.py`:

```python
from collections.abc import Mapping

from roambot.domain.models import SceneryType
from roambot.domain.scenery_rules import NAME_TERMS, TYPE_TERMS


def classify_scenery(
    name: str,
    type_name: str,
    type_code: str,
    overrides: Mapping[str, frozenset[SceneryType]],
) -> frozenset[SceneryType]:
    if name in overrides:
        return overrides[name]

    tags: set[SceneryType] = set()
    for tag, terms in TYPE_TERMS.items():
        if any(term in type_name for term in terms):
            tags.add(tag)
    for tag, terms in NAME_TERMS.items():
        if any(term in name for term in terms):
            tags.add(tag)
    return frozenset(tags)
```

- [ ] **Step 4: Verify tests and lint**

Run:

```powershell
./.venv/Scripts/python.exe -m pytest backend/tests/unit/test_scenery.py -q
./.venv/Scripts/python.exe -m ruff check backend
```

Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/src/roambot/domain/scenery.py backend/src/roambot/domain/scenery_rules.py backend/tests/unit/test_scenery.py
git commit -m "feat: classify destination scenery deterministically"
```

### Task 4: Scoring and Ranking

**Files:**
- Create: `backend/src/roambot/domain/scoring.py`
- Create: `backend/src/roambot/domain/ranking.py`
- Test: `backend/tests/unit/test_scoring.py`
- Test: `backend/tests/unit/test_ranking.py`

**Interfaces:**
- Produces: `score_daily_weather`, `aggregate_weather`, `score_distance`, `score_fairness`, `score_popularity`, `normalize_weights`, and `final_score`.

- [ ] **Step 1: Write exact scoring tests**

Create tests asserting these public examples:

```python
from datetime import date

import pytest

from roambot.domain.models import DailyWeather, RankingWeights, SceneryType
from roambot.domain.scoring import (
    aggregate_weather,
    score_daily_weather,
    score_distance,
    score_fairness,
    score_popularity,
)


def weather(**changes: object) -> DailyWeather:
    values: dict[str, object] = {
        "date": date(2026, 7, 20),
        "condition": "多云",
        "temp_min_c": 20,
        "temp_max_c": 27,
        "precipitation_mm": 0,
        "wind_speed_kmh": 10,
        "humidity_percent": 60,
        "visibility_km": 20,
        "uv_index": 5,
    }
    values.update(changes)
    return DailyWeather.model_validate(values)


def test_outdoor_rain_is_worse_than_museum_rain() -> None:
    rainy = weather(condition="中雨", precipitation_mm=8)
    outdoor = score_daily_weather(rainy, frozenset({SceneryType.MOUNTAIN}))
    indoor = score_daily_weather(rainy, frozenset({SceneryType.MUSEUM}))
    assert outdoor.score < indoor.score


def test_multi_day_formula_is_seventy_thirty() -> None:
    assert aggregate_weather([90, 85, 30]) == pytest.approx(56.833333, rel=1e-5)


def test_distance_and_fairness_are_bounded() -> None:
    assert score_distance(20, 100) == 80
    assert score_distance(100, 100) == 0
    assert score_fairness([30, 32, 29], 100) > score_fairness([10, 30, 90], 100)


def test_popularity_converts_rank() -> None:
    assert score_popularity(rank=1) == 100
    assert score_popularity(rank=25) == 4
```

- [ ] **Step 2: Run and observe failure**

Run `./.venv/Scripts/python.exe -m pytest backend/tests/unit/test_scoring.py -q`.

Expected: import failure.

- [ ] **Step 3: Implement deterministic scoring**

Implement `backend/src/roambot/domain/scoring.py` with the following exact policy:

```python
from math import sqrt
from statistics import fmean, pvariance

from roambot.domain.models import DailySuitability, DailyWeather, SceneryType

OUTDOOR = frozenset(
    {
        SceneryType.LAKE,
        SceneryType.SEA,
        SceneryType.OLD_TOWN,
        SceneryType.PARK,
        SceneryType.MOUNTAIN,
    }
)


def clamp(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def score_daily_weather(
    weather: DailyWeather, scenery_tags: frozenset[SceneryType]
) -> DailySuitability:
    score = 100.0
    reasons: list[str] = []
    outdoor = not scenery_tags or bool(scenery_tags & OUTDOOR)

    if weather.precipitation_mm > 10:
        penalty = 60 if outdoor else 35
        score -= penalty
        reasons.append(f"强降水 -{penalty}")
    elif weather.precipitation_mm > 1:
        penalty = 35 if outdoor else 15
        score -= penalty
        reasons.append(f"降雨 -{penalty}")
    elif weather.precipitation_mm > 0:
        penalty = 10 if outdoor else 5
        score -= penalty
        reasons.append(f"微量降水 -{penalty}")

    hottest = weather.temp_max_c
    coldest = weather.temp_min_c
    if hottest > 35 or coldest < 0:
        score -= 40
        reasons.append("极端温度 -40")
    elif hottest > 32 or coldest < 10:
        score -= 25
        reasons.append("温度不舒适 -25")
    elif hottest > 28 or coldest < 18:
        score -= 10
        reasons.append("温度稍有偏离 -10")

    if weather.wind_speed_kmh > 40:
        score -= 40 if outdoor else 20
        reasons.append("大风")
    elif weather.wind_speed_kmh > 30:
        score -= 25 if outdoor else 10
        reasons.append("风力较强")
    elif weather.wind_speed_kmh > 20 and outdoor:
        score -= 10
        reasons.append("户外风力影响")

    if weather.visibility_km < 2:
        score -= 30
        reasons.append("能见度很低")
    elif weather.visibility_km < 5:
        score -= 15
        reasons.append("能见度较低")
    elif weather.visibility_km < 10:
        score -= 5
        reasons.append("能见度一般")

    if weather.uv_index > 8 and outdoor:
        score -= 10
        reasons.append("紫外线强")

    if not reasons:
        reasons.append("天气条件总体舒适")
    return DailySuitability(date=weather.date, score=clamp(score), reasons=reasons)


def aggregate_weather(scores: list[float]) -> float:
    if not scores:
        raise ValueError("daily weather scores must not be empty")
    return clamp(fmean(scores) * 0.70 + min(scores) * 0.30)


def score_distance(distance_km: float, max_distance_km: float) -> float:
    if max_distance_km <= 0:
        raise ValueError("max distance must be positive")
    return clamp(100 * (1 - distance_km / max_distance_km))


def score_fairness(distances_km: list[float], max_distance_km: float) -> float:
    if not distances_km:
        raise ValueError("distances must not be empty")
    if len(distances_km) == 1:
        return 100.0
    stddev = sqrt(pvariance(distances_km))
    return clamp(100 * (1 - stddev / max_distance_km))


def score_popularity(rank: int, local_bonus: float = 0) -> float:
    if rank < 1:
        raise ValueError("invalid popularity rank")
    if not -20 <= local_bonus <= 20:
        raise ValueError("popularity bonus must be between -20 and 20")
    return clamp(100 - 4 * (rank - 1) + local_bonus)
```

- [ ] **Step 4: Write ranking tests**

Create `backend/tests/unit/test_ranking.py`:

```python
import pytest

from roambot.domain.models import RankingWeights
from roambot.domain.ranking import final_score, normalize_weights


def test_weights_are_normalized() -> None:
    normalized = normalize_weights(RankingWeights(weather=4, distance=3, fairness=0, popularity=3))
    assert normalized == {"weather": 0.4, "distance": 0.3, "fairness": 0.0, "popularity": 0.3}


def test_coverage_penalty_reduces_total() -> None:
    weights = RankingWeights(weather=40, distance=30, fairness=0, popularity=30)
    full = final_score(80, 80, 100, 80, weights, coverage_ratio=1)
    partial = final_score(80, 80, 100, 80, weights, coverage_ratio=0.5)
    assert full == pytest.approx(80)
    assert partial == pytest.approx(70)
```

- [ ] **Step 5: Implement ranking functions**

Create `backend/src/roambot/domain/ranking.py`:

```python
from roambot.domain.models import RankingWeights
from roambot.domain.scoring import clamp


def normalize_weights(weights: RankingWeights) -> dict[str, float]:
    values = weights.model_dump()
    total = sum(values.values())
    return {name: value / total for name, value in values.items()}


def final_score(
    weather: float,
    distance: float,
    fairness: float,
    popularity: float,
    weights: RankingWeights,
    coverage_ratio: float,
) -> float:
    normalized = normalize_weights(weights)
    weighted = (
        weather * normalized["weather"]
        + distance * normalized["distance"]
        + fairness * normalized["fairness"]
        + popularity * normalized["popularity"]
    )
    coverage_penalty = 20 * (1 - max(0.0, min(1.0, coverage_ratio)))
    return clamp(weighted - coverage_penalty)
```

- [ ] **Step 6: Verify all domain tests**

Run:

```powershell
./.venv/Scripts/python.exe -m pytest backend/tests/unit/test_scoring.py backend/tests/unit/test_ranking.py -q
./.venv/Scripts/python.exe -m ruff check backend
```

Expected: all pass.

- [ ] **Step 7: Commit**

```powershell
git add backend/src/roambot/domain/scoring.py backend/src/roambot/domain/ranking.py backend/tests/unit/test_scoring.py backend/tests/unit/test_ranking.py
git commit -m "feat: score and rank travel destinations"
```

### Task 5: Provider Protocols and Deterministic Mocks

**Files:**
- Create: `backend/src/roambot/providers/__init__.py`
- Create: `backend/src/roambot/providers/protocols.py`
- Create: `backend/src/roambot/providers/mock.py`
- Test: `backend/tests/unit/test_mock_providers.py`

**Interfaces:**
- Produces: `Geocoder`, `PlaceProvider`, `DistanceProvider`, `WeatherProvider`, `ExplanationProvider`, and deterministic mock implementations.

- [ ] **Step 1: Write a provider contract test**

```python
from datetime import date

from roambot.domain.models import Coordinate, SceneryType
from roambot.providers.mock import MockProviderBundle


def test_mock_bundle_returns_suzhou_vertical_slice() -> None:
    providers = MockProviderBundle.default()
    origin = providers.geocoder.geocode("苏州站", "苏州")
    places = providers.places.search(
        center=origin.coordinate,
        city="苏州",
        scenery_types=(SceneryType.LAKE,),
        radius_km=80,
    )
    weather = providers.weather.daily(places[0].coordinate, date(2026, 7, 20), date(2026, 7, 22))

    assert origin.coordinate == Coordinate(longitude=120.617, latitude=31.335)
    assert places[0].name == "金鸡湖景区"
    assert len(weather) == 3
```

- [ ] **Step 2: Run and observe failure**

Run `./.venv/Scripts/python.exe -m pytest backend/tests/unit/test_mock_providers.py -q`.

Expected: import failure.

- [ ] **Step 3: Define synchronous provider protocols**

Create `backend/src/roambot/providers/protocols.py` with `Protocol` methods:

```python
from datetime import date
from typing import Protocol

from roambot.domain.models import (
    Coordinate,
    DailyWeather,
    Destination,
    DistanceEstimate,
    Origin,
    RecommendationItem,
    SceneryType,
)


class ProviderError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class Geocoder(Protocol):
    def geocode(self, address: str, city: str) -> Origin:
        raise NotImplementedError


class PlaceProvider(Protocol):
    def search(
        self,
        center: Coordinate,
        city: str,
        scenery_types: tuple[SceneryType, ...],
        radius_km: float,
    ) -> list[Destination]:
        raise NotImplementedError

    def resolve(self, name: str, city: str) -> Destination:
        raise NotImplementedError


class DistanceProvider(Protocol):
    def measure(self, origins: list[Origin], destination: Destination) -> list[DistanceEstimate]:
        raise NotImplementedError


class WeatherProvider(Protocol):
    def daily(self, coordinate: Coordinate, start: date, end: date) -> list[DailyWeather]:
        raise NotImplementedError


class ExplanationProvider(Protocol):
    def explain(self, items: list[RecommendationItem]) -> list[str]:
        raise NotImplementedError
```

- [ ] **Step 4: Implement fixed Suzhou mocks**

Create `backend/src/roambot/providers/mock.py`. It must expose:

```python
@dataclass(frozen=True)
class MockProviderBundle:
    geocoder: MockGeocoder
    places: MockPlaceProvider
    distance: MockDistanceProvider
    weather: MockWeatherProvider
    explanations: MockExplanationProvider

    @classmethod
    def default(cls) -> "MockProviderBundle":
        return cls(
            geocoder=MockGeocoder(),
            places=MockPlaceProvider(),
            distance=MockDistanceProvider(),
            weather=MockWeatherProvider(),
            explanations=MockExplanationProvider(),
        )
```

Use fixed coordinates for 苏州站 `(120.617, 31.335)`, 苏州园区站 `(120.706, 31.374)`, 苏州新区站 `(120.543, 31.328)`, 金鸡湖景区 `(120.704, 31.315)`, 同里古镇 `(120.717, 31.159)`, 苏州博物馆 `(120.627, 31.324)`, and 穹窿山 `(120.407, 31.199)`. Return deterministic three-day weather and template explanations. Unknown addresses must raise `ProviderError("not_found", "未找到出发地")`; unknown places must raise `ProviderError("not_found", "未找到指定地点")`.

- [ ] **Step 5: Verify provider tests**

Run:

```powershell
./.venv/Scripts/python.exe -m pytest backend/tests/unit/test_mock_providers.py -q
./.venv/Scripts/python.exe -m ruff check backend
```

Expected: all pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/src/roambot/providers backend/tests/unit/test_mock_providers.py
git commit -m "feat: add provider protocols and deterministic mocks"
```

### Task 6: Recommendation Orchestration

**Files:**
- Create: `backend/src/roambot/services/__init__.py`
- Create: `backend/src/roambot/services/recommendations.py`
- Test: `backend/tests/unit/test_recommendation_service.py`

**Interfaces:**
- Consumes: all domain scoring functions and provider protocols.
- Produces: `RecommendationService.recommend()` and `.evaluate()`.

- [ ] **Step 1: Write service behavior tests**

Cover these exact cases in separately named tests:

- `test_recommend_filters_primary_origin_distance_and_sorts`: a candidate beyond the primary-origin maximum is absent and ties sort by primary distance then destination name.
- `test_multi_origin_uses_default_fairness_weight`: two origins use weights `(40, 0, 40, 20)` and the larger distance spread produces the lower fairness score.
- `test_cover_all_applies_coverage_penalty`: matching one of two requested types applies the documented 10-point coverage penalty while `ANY` applies none.
- `test_evaluate_returns_only_requested_destination`: evaluation returns the resolved target even when another mock destination would rank higher.
- `test_explanation_failure_uses_template_without_changing_score`: forced `ProviderError` changes only explanation text/source notice, not score or rank.
- `test_no_candidates_returns_empty_items_with_notice`: hard filters can produce an empty list with a stable `no_candidates` notice.

Use `MockProviderBundle.default()` and fixed dates with a `clock: Callable[[], datetime]` injected into the service. Assert result ordering, exact source kind `demo`, and absence of any external calls.

- [ ] **Step 2: Run and observe failure**

Run `./.venv/Scripts/python.exe -m pytest backend/tests/unit/test_recommendation_service.py -q`.

Expected: import failure.

- [ ] **Step 3: Implement the service**

Create `RecommendationService` with constructor parameters:

```python
def __init__(
    self,
    geocoder: Geocoder,
    places: PlaceProvider,
    distance: DistanceProvider,
    weather: WeatherProvider,
    explanations: ExplanationProvider,
    source_kind: SourceKind,
    clock: Callable[[], datetime],
) -> None:
    self.geocoder = geocoder
    self.places = places
    self.distance = distance
    self.weather = weather
    self.explanations = explanations
    self.source_kind = source_kind
    self.clock = clock
```

Implementation requirements:

- Use single defaults `(40, 30, 0, 30)` for one origin and multi defaults `(40, 0, 40, 20)` for two or three origins unless request weights are supplied.
- Hard-filter using distance from the primary origin only.
- Use average distance for the optional multi-person distance score.
- Use all origin distances for fairness.
- For `ANY`, require at least one requested scenery tag and use coverage ratio 1.
- For `COVER_ALL`, require at least one requested tag and compute `matched/requested` coverage ratio for the 20-point penalty.
- Aggregate weather with the fixed 70/30 formula.
- Convert provider rank to the RoamBot popularity estimate.
- Sort descending by total then ascending by primary distance then by destination name.
- Return at most five items.
- Ask the explanation provider once with the final item list. If it raises `ProviderError`, retain scores and add deterministic template explanations plus a degraded notice.

- [ ] **Step 4: Verify service tests**

Run:

```powershell
./.venv/Scripts/python.exe -m pytest backend/tests/unit/test_recommendation_service.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/src/roambot/services backend/tests/unit/test_recommendation_service.py
git commit -m "feat: orchestrate travel recommendations"
```

### Task 7: Public Core API and Error Envelope

**Files:**
- Create: `backend/src/roambot/api/errors.py`
- Create: `backend/src/roambot/api/dependencies.py`
- Create: `backend/src/roambot/api/routes/recommendations.py`
- Modify: `backend/src/roambot/main.py`
- Test: `backend/tests/api/test_recommendations.py`

**Interfaces:**
- Produces: `POST /api/v1/recommendations`, `POST /api/v1/place-evaluations`, and error shape `{"error":{"code","message","fields"}}`.

- [ ] **Step 1: Write API contract tests**

```python
from datetime import date, timedelta

from fastapi.testclient import TestClient

from roambot.main import create_app


def payload() -> dict[str, object]:
    start = date.today() + timedelta(days=1)
    return {
        "city": "苏州",
        "main_origin": "苏州站",
        "companion_origins": [],
        "max_distance_km": 80,
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=2)).isoformat(),
        "scenery_types": ["lake", "park"],
        "scenery_match_mode": "any",
    }


def test_guest_recommendation_returns_ranked_items() -> None:
    response = TestClient(create_app()).post("/api/v1/recommendations", json=payload())
    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["destination"]["name"] == "金鸡湖景区"
    assert body["source_state"]["kind"] == "demo"


def test_invalid_request_returns_stable_error() -> None:
    invalid = payload()
    invalid["max_distance_km"] = 0
    response = TestClient(create_app()).post("/api/v1/recommendations", json=invalid)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert "traceback" not in response.text.lower()
```

Add a similar success test for `/api/v1/place-evaluations` and a not-found provider error test.

- [ ] **Step 2: Run and observe 404/failure**

Run `./.venv/Scripts/python.exe -m pytest backend/tests/api/test_recommendations.py -q`.

Expected: endpoints return 404.

- [ ] **Step 3: Implement dependency and routes**

- `get_recommendation_service()` returns a service using `MockProviderBundle.default()` and `SourceKind.DEMO`.
- Route functions use `response_model=RecommendationResponse` and `response_model=PlaceEvaluationResponse`.
- Geocoder `not_found` maps to HTTP 422 `origin_not_found`; target-place resolution `not_found` maps to HTTP 404 `place_not_found`; other provider failures map to HTTP 503 `provider_unavailable`.
- Override FastAPI request validation handling so all validation responses use the stable envelope and field paths.
- Do not include exception strings from unknown errors in responses.

Include the recommendation router in `create_app()` under `/api/v1`.

- [ ] **Step 4: Verify API and complete backend suite**

Run:

```powershell
./.venv/Scripts/python.exe -m pytest backend/tests -q
./.venv/Scripts/python.exe -m ruff check backend
```

Expected: all tests pass and Ruff exits 0.

- [ ] **Step 5: Run the server and inspect OpenAPI**

Run:

```powershell
./.venv/Scripts/python.exe -m uvicorn roambot.main:app --app-dir backend/src --port 8000
```

In a second terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
Invoke-RestMethod http://127.0.0.1:8000/openapi.json | Select-Object -ExpandProperty paths
```

Expected: health is ready and both core paths are listed. Stop Uvicorn cleanly before continuing.

- [ ] **Step 6: Commit**

```powershell
git add backend/src/roambot/api backend/src/roambot/main.py backend/tests/api/test_recommendations.py
git commit -m "feat: expose public recommendation API"
```

### Task 8: Milestone Verification and Run Documentation

**Files:**
- Create: `backend/README.md`
- Modify: `AGENT_LOG.md`

**Interfaces:**
- Produces: reproducible backend setup/run/test instructions for the next milestone.

- [ ] **Step 1: Document exact commands**

Create `backend/README.md` with PowerShell commands for creating `.venv`, installing `./backend[dev]`, running pytest/Ruff, and launching Uvicorn. State prominently that this milestone uses mock providers and needs no real credentials.

- [ ] **Step 2: Run fresh verification**

```powershell
./.venv/Scripts/python.exe -m pytest backend/tests/unit backend/tests/api/test_recommendations.py -q
./.venv/Scripts/python.exe -m ruff check backend
git diff --check
```

Expected: zero test failures, zero lint errors, and `git diff --check` exits 0.

- [ ] **Step 3: Record evidence**

Append the exact test count, commands, and any human intervention to `AGENT_LOG.md`. Do not claim real provider connectivity.

- [ ] **Step 4: Commit**

```powershell
git add backend/README.md AGENT_LOG.md
git commit -m "docs: record core backend verification"
```

## Milestone Exit Criteria

- Both core endpoints work for guests with mock providers.
- Domain behavior is deterministic and covered by unit tests.
- No database, account, real provider, or frontend dependency has leaked into core domain code.
- No test performs network I/O.
- `python -m pytest backend/tests/unit backend/tests/api/test_recommendations.py -q` and Ruff both pass from a fresh process.
