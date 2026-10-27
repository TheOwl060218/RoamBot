"""Bounded local live acceptance. No vault access, cookies or provider credentials."""

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic, sleep
from urllib.parse import urlsplit

import httpx


def cases(today):
    day = lambda offset: (today + timedelta(days=offset)).isoformat()
    complete = {
        "main_origin": "苏州",
        "start_date": day(1),
        "end_date": day(4),
        "max_distance_km": 100,
        "scenery_types": ["lake"],
    }
    return [
        {
            "name": "explicit_destination_direction",
            "draft": {},
            "turns": [
                {
                    "message": "我想去苏州",
                    "expected": {"destination_regions": ["320500"]},
                    "absent": ["main_origin", "target_place"],
                },
                {
                    "message": "从常州过去",
                    "expected": {
                        "main_origin": "常州",
                        "destination_regions": ["320500"],
                    },
                },
            ],
        },
        {
            "name": "destination_direction_generalization",
            "draft": {},
            "turns": [
                {
                    "message": "目的地选宁波好了",
                    "expected": {"destination_regions": ["330200"]},
                    "absent": ["main_origin", "target_place"],
                },
                {
                    "message": "我住绍兴，从这里动身",
                    "expected": {
                        "main_origin": "绍兴",
                        "destination_regions": ["330200"],
                    },
                },
                {
                    "message": "改去嘉兴，不去宁波了",
                    "expected": {
                        "main_origin": "绍兴",
                        "destination_regions": ["330400"],
                    },
                },
            ],
        },
        {
            "name": "unseen_city_and_calendar",
            "draft": {},
            "turns": [
                {
                    "message": "无锡",
                    "expected": {},
                    "question": True,
                    "absent": ["main_origin", "destination_regions", "target_place"],
                },
                {"message": "我是说从那边走", "expected": {"main_origin": "无锡"}},
                {
                    "message": f"{(today + timedelta(days=2)).day}号启程，{(today + timedelta(days=4)).day}号回",
                    "expected": {
                        "main_origin": "无锡",
                        "start_date": day(2),
                        "end_date": day(4),
                    },
                },
            ],
        },
        {
            "name": "duration_before_anchor",
            "draft": {},
            "turns": [
                {
                    "message": "待三天吧",
                    "expected": {},
                    "question": True,
                    "absent": ["main_origin", "start_date", "end_date"],
                },
                {
                    "message": "后天走",
                    "expected": {"start_date": day(2), "end_date": day(4)},
                    "absent": ["main_origin"],
                },
            ],
        },
        {
            "name": "companions_and_exclusion",
            "draft": complete,
            "turns": [
                {
                    "message": "朋友从南京出发，另外一位从上海出发，我还是苏州",
                    "expected": {
                        "main_origin": "苏州",
                        "companion_origins": ["南京", "上海"],
                    },
                },
                {
                    "message": "上海那位不去了，只留下南京",
                    "expected": {"main_origin": "苏州", "companion_origins": ["南京"]},
                },
                {
                    "message": "想要水边但不去博物馆",
                    "expected": {"main_origin": "苏州"},
                    "excluded_types": ["museum"],
                },
                {
                    "message": "今天先聊到这，别改旅行时间",
                    "expected": {
                        "main_origin": "苏州",
                        "start_date": day(1),
                        "end_date": day(4),
                    },
                },
            ],
        },
        {
            "name": "origin_then_dates",
            "draft": {},
            "turns": [
                {
                    "message": "苏州",
                    "expected": {"target_place": None},
                    "question": True,
                    "absent": ["main_origin", "destination_regions"],
                },
                {
                    "message": "出发地",
                    "expected": {"main_origin": "苏州"},
                    "absent": ["destination_regions", "target_place"],
                    "question_contains": ["哪天", "日期", "出发时间"],
                },
                {
                    "message": "明天出发，玩4天",
                    "absent": ["destination_regions", "target_place"],
                    "question_contains": ["风景", "地方", "目的地范围"],
                    "expected": {
                        "main_origin": "苏州",
                        "start_date": day(1),
                        "end_date": day(4),
                    },
                },
            ],
        },
        {
            "name": "correction_and_duration",
            "draft": complete,
            "turns": [
                {
                    "message": "不是明天出发玩四天，是后天动身，待两天",
                    "expected": {
                        "main_origin": "苏州",
                        "start_date": day(2),
                        "end_date": day(3),
                    },
                },
                {
                    "message": "两天太久，只留一天，其他不变",
                    "expected": {
                        "start_date": day(2),
                        "end_date": day(2),
                        "main_origin": "苏州",
                    },
                },
                {
                    "message": "明天再说吧",
                    "expected": {
                        "start_date": day(2),
                        "end_date": day(2),
                        "main_origin": "苏州",
                    },
                },
            ],
        },
        {
            "name": "negated_duration",
            "draft": complete,
            "turns": [
                {
                    "message": "明天出发，不玩四天，只玩一天",
                    "expected": {
                        "main_origin": "苏州",
                        "start_date": day(1),
                        "end_date": day(1),
                    },
                },
                {
                    "message": "距离改成80公里以内，日期不动",
                    "expected": {
                        "max_distance_km": 80,
                        "start_date": day(1),
                        "end_date": day(1),
                    },
                },
            ],
        },
        {
            "name": "region_remove_and_roles",
            "draft": complete,
            "turns": [
                {
                    "message": "目的地上海杭州都可以",
                    "expected": {
                        "destination_regions": ["310000", "330100"],
                        "main_origin": "苏州",
                    },
                },
                {
                    "message": "上海先不去了，只留杭州",
                    "expected": {
                        "destination_regions": ["330100"],
                        "main_origin": "苏州",
                    },
                },
                {
                    "message": "苏州改成目的地，我从无锡出发",
                    "expected": {
                        "destination_regions": ["320500"],
                        "main_origin": "无锡",
                    },
                },
            ],
        },
        {
            "name": "mixed_clarification",
            "draft": complete,
            "turns": [
                {
                    "message": "80公里内，南京这一项先加上，出发还是去那里我还没定",
                    "expected": {"max_distance_km": 80, "main_origin": "苏州"},
                    "question": True,
                    "allowed_changes": ["max_distance_km"],
                    "absent": [
                        "destination_regions",
                        "target_place",
                        "companion_origins",
                    ],
                },
            ],
        },
        {
            "name": "range_and_unsupported",
            "draft": complete,
            "turns": [
                {
                    "message": "范围80公里，大后天起住五天",
                    "expected": {
                        "max_distance_km": 80,
                        "start_date": day(1),
                        "end_date": day(4),
                    },
                    "question": True,
                },
                {
                    "message": "能查实时人流吗？",
                    "expected": {"main_origin": "苏州", "start_date": day(1)},
                    "unsupported": True,
                },
            ],
        },
        {
            "name": "free_preference_and_clear",
            "draft": complete,
            "turns": [
                {
                    "message": "不想爬山，改成在室内看展，别太吵",
                    "expected": {"main_origin": "苏州"},
                    "required_types": ["museum"],
                    "excluded_types": ["mountain"],
                },
                {
                    "message": "同行地点暂时清掉，日期也取消，之后再定",
                    "expected": {
                        "main_origin": "苏州",
                        "start_date": None,
                        "end_date": None,
                    },
                },
            ],
        },
    ]


def holdout_cases(today):
    """Independent paraphrases and scope invariants; never sent as prompt examples."""

    def day(offset):
        return (today + timedelta(days=offset)).isoformat()

    complete = {
        "main_origin": "广州",
        "companion_origins": ["佛山"],
        "start_date": day(1),
        "end_date": day(2),
        "max_distance_km": 120,
        "scenery_types": ["park"],
        "scenery_query": "绿地",
        "scenery_keywords": ["公园"],
        "destination_regions": ["350200"],
    }
    return [
        {
            "name": "holdout_pending_no_history",
            "draft": {},
            "history_limit": 0,
            "turns": [
                {
                    "message": "还没定哪天，反正总共待两天",
                    "expected": {},
                    "pending_duration": 2,
                    "allowed_changes": [],
                    "question": True,
                },
                {
                    "message": "出发点在扬州",
                    "expected": {"main_origin": "扬州"},
                    "allowed_changes": ["main_origin"],
                    "pending_duration": 2,
                },
                {
                    "message": "路程上限六十公里",
                    "expected": {"max_distance_km": 60},
                    "allowed_changes": ["max_distance_km"],
                    "pending_duration": 2,
                },
                {
                    "message": "明儿动身",
                    "expected": {"start_date": day(1), "end_date": day(2)},
                    "allowed_changes": ["start_date", "end_date"],
                },
            ],
        },
        {
            "name": "holdout_return_before_departure",
            "draft": {},
            "history_limit": 0,
            "turns": [
                {
                    "message": f"{(today + timedelta(days=3)).month}月{(today + timedelta(days=3)).day}日回来，出发那天还没决定",
                    "expected": {},
                    "expected_pending": {"end_date": day(3)},
                    "allowed_changes": [],
                    "question": True,
                },
                {
                    "message": "那就明天出门吧",
                    "expected": {"start_date": day(1), "end_date": day(3)},
                    "allowed_changes": ["start_date", "end_date"],
                },
            ],
        },
        {
            "name": "holdout_destination_scope",
            "draft": complete,
            "turns": [
                {
                    "message": "厦门先撤了，目的地换成泉州，其他照旧",
                    "expected": {"destination_regions": ["350500"]},
                    "allowed_changes": ["destination_regions"],
                },
                {
                    "message": "目的地城市的限制也先取消",
                    "expected": {"destination_regions": []},
                    "allowed_changes": ["destination_regions"],
                },
            ],
        },
        {
            "name": "holdout_conversation_time",
            "draft": complete,
            "turns": [
                {
                    "message": "我明天再联系你，出游时间先按原来的",
                    "expected": {},
                    "allowed_changes": [],
                }
            ],
        },
        {
            "name": "holdout_ambiguous_scope",
            "draft": complete,
            "turns": [
                {
                    "message": "距离再缩到六十公里；扬州是从那儿走还是到那儿玩，我还没拿准",
                    "expected": {"max_distance_km": 60},
                    "allowed_changes": ["max_distance_km"],
                    "question": True,
                }
            ],
        },
        {
            "name": "holdout_capability",
            "draft": complete,
            "turns": [
                {
                    "message": "你能告诉我景点此刻要排队多少分钟吗",
                    "expected": {},
                    "allowed_changes": [],
                    "unsupported": True,
                }
            ],
        },
        {
            "name": "holdout_preference_clear",
            "draft": complete,
            "turns": [
                {
                    "message": "别推荐登山，我更想在室内逛展",
                    "expected": {},
                    "required_types": ["museum"],
                    "excluded_types": ["mountain"],
                    "required_patch_fields": [
                        "scenery_types",
                        "scenery_query",
                        "scenery_keywords",
                    ],
                    "forbidden_values": {
                        "scenery_query": ["绿地"],
                        "scenery_keywords": ["公园"],
                    },
                    "allowed_changes": [
                        "scenery_types",
                        "scenery_query",
                        "scenery_keywords",
                    ],
                },
                {
                    "message": "先不管风景了，这项偏好取消",
                    "expected": {},
                    "absent": ["scenery_types", "scenery_query", "scenery_keywords"],
                    "allowed_changes": [
                        "scenery_types",
                        "scenery_query",
                        "scenery_keywords",
                    ],
                },
            ],
        },
        {
            "name": "holdout_duration_correction",
            "draft": complete,
            "turns": [
                {
                    "message": "我只能玩一天，不是两天",
                    "expected": {"start_date": day(1), "end_date": day(1)},
                    "allowed_changes": ["start_date", "end_date"],
                },
                {
                    "message": "改成后天启程，天数不动",
                    "expected": {"start_date": day(2), "end_date": day(2)},
                    "allowed_changes": ["start_date", "end_date"],
                },
            ],
        },
    ]


def native_smoke_cases(today):
    """Six key turns before expanding evaluation; no prompt examples."""

    def day(offset):
        return (today + timedelta(days=offset)).isoformat()

    return [
        {
            "name": "native_role_smoke",
            "draft": {},
            "turns": [
                {
                    "message": "这次想去苏州转转",
                    "expected": {"destination_regions": ["320500"]},
                    "allowed_changes": ["destination_regions"],
                },
                {
                    "message": "我从常州过去",
                    "expected": {"main_origin": "常州"},
                    "allowed_changes": ["main_origin"],
                },
            ],
        },
        {
            "name": "native_date_smoke",
            "draft": {"main_origin": "扬州"},
            "history_limit": 0,
            "turns": [
                {
                    "message": "总共待四天，哪天走还没定",
                    "expected": {},
                    "allowed_changes": [],
                    "pending_duration": 4,
                    "question": True,
                },
                {
                    "message": "明天动身",
                    "expected": {"start_date": day(1), "end_date": day(4)},
                    "allowed_changes": ["start_date", "end_date"],
                },
            ],
        },
        {
            "name": "native_preference_smoke",
            "draft": {
                "main_origin": "广州",
                "start_date": day(1),
                "end_date": day(2),
                "max_distance_km": 100,
                "scenery_types": ["park"],
                "scenery_query": "绿地",
                "scenery_keywords": ["公园"],
            },
            "turns": [
                {
                    "message": "不爬山了，想在室内逛展",
                    "expected": {},
                    "required_types": ["museum"],
                    "excluded_types": ["mountain"],
                    "allowed_changes": [
                        "scenery_types",
                        "scenery_query",
                        "scenery_keywords",
                    ],
                },
                {
                    "message": "风景偏好先全部取消",
                    "expected": {},
                    "absent": ["scenery_types", "scenery_query", "scenery_keywords"],
                    "allowed_changes": [
                        "scenery_types",
                        "scenery_query",
                        "scenery_keywords",
                    ],
                },
            ],
        },
    ]


def same_condition(field, actual, expected):
    if (
        field
        in {
            "companion_origins",
            "destination_regions",
            "scenery_types",
            "scenery_keywords",
        }
        and not actual
        and not expected
    ):
        return True
    if field == "main_origin" and isinstance(actual, str) and isinstance(expected, str):
        return actual.removesuffix("市") == expected.removesuffix("市")
    if (
        field == "companion_origins"
        and isinstance(actual, list)
        and isinstance(expected, list)
    ):
        return len(actual) == len(expected) and all(
            same_condition("main_origin", a, b)
            for a, b in zip(actual, expected, strict=True)
        )
    return actual == expected


def date_role_cases(today):
    """Four independent role controls, not examples for production prompts."""
    scenarios = []
    wordings = (
        "先确定返程：{calendar}号回；哪天走还没想好",
        "结束日期记{calendar}号，出发的日期暂时空着",
        "{calendar}号不出发，那是我回来的日子",
    )
    for index, wording in enumerate(wordings, start=3):
        day = today + timedelta(days=index)
        scenarios.append(
            {
                "name": f"return_role_control_{index}",
                "draft": {},
                "history_limit": 0,
                "turns": [
                    {
                        "message": wording.format(calendar=f"{day.month}月{day.day}"),
                        "expected": {},
                        "allowed_changes": [],
                        "question": True,
                        "expected_pending": {"end_date": day.isoformat()},
                    }
                ],
            }
        )
    day = today + timedelta(days=3)
    scenarios.append(
        {
            "name": "departure_role_control",
            "draft": {},
            "history_limit": 0,
            "turns": [
                {
                    "message": f"{day.month}月{day.day}日出发，当天返回",
                    "expected": {
                        "start_date": day.isoformat(),
                        "end_date": day.isoformat(),
                    },
                    "allowed_changes": ["start_date", "end_date"],
                    "expected_pending": None,
                }
            ],
        }
    )
    return scenarios


def demo_cases(today):
    """Bounded deadline rehearsal, not a replacement for general semantic acceptance."""

    def day(offset):
        return (today + timedelta(days=offset)).isoformat()

    return [
        {
            "name": "demo_explicit_input",
            "draft": {},
            "turns": [
                {
                    "message": "从苏州站出发，明天想去湖边，100公里以内",
                    "expected": {
                        "main_origin": "苏州站",
                        "start_date": day(1),
                        "end_date": day(1),
                        "max_distance_km": 100,
                    },
                    "required_types": ["lake"],
                    "absent": ["destination_regions", "target_place"],
                    "allowed_changes": [
                        "main_origin",
                        "start_date",
                        "end_date",
                        "max_distance_km",
                        "scenery_types",
                        "scenery_query",
                        "scenery_keywords",
                    ],
                },
                {
                    "message": "改成后天出发，玩两天，其他不变",
                    "expected": {"start_date": day(2), "end_date": day(3)},
                    "allowed_changes": ["start_date", "end_date"],
                },
                {
                    "message": "朋友从南京南站出发，跟我一起去",
                    "expected": {"companion_origins": ["南京南站"]},
                    "allowed_changes": ["companion_origins"],
                },
                {
                    "message": "南京那位不去了，还是我一个人",
                    "expected": {"companion_origins": []},
                    "allowed_changes": ["companion_origins"],
                },
            ],
        }
    ]


def release_cases(today):
    """Frozen post-selection inputs, never imported by production code."""

    def day(offset):
        return (today + timedelta(days=offset)).isoformat()

    complete = {
        "main_origin": "绍兴",
        "start_date": day(1),
        "end_date": day(3),
        "max_distance_km": 90,
        "destination_regions": ["330500"],
        "scenery_types": ["museum"],
        "scenery_query": "展览",
        "scenery_keywords": ["展馆"],
    }
    return [
        {
            "name": "release_bare_city_role",
            "draft": {},
            "turns": [
                {
                    "message": "金华",
                    "expected": {},
                    "question": True,
                    "allowed_changes": [],
                },
                {
                    "message": "要去那儿逛逛。我从台州出发",
                    "expected": {
                        "main_origin": "台州",
                        "destination_regions": ["330700"],
                    },
                    "allowed_changes": ["main_origin", "destination_regions"],
                },
                {
                    "message": "明天过去，住两晚，第三天回",
                    "expected": {"start_date": day(1), "end_date": day(3)},
                    "allowed_changes": ["start_date", "end_date"],
                },
            ],
        },
        {
            "name": "release_station_companions",
            "draft": complete,
            "turns": [
                {
                    "message": "我从绍兴北站走，同行一个南京南站，另一个杭州东站",
                    "expected": {
                        "main_origin": "绍兴北站",
                        "companion_origins": ["南京南站", "杭州东站"],
                    },
                    "allowed_changes": ["main_origin", "companion_origins"],
                },
                {
                    "message": "杭州东站那位这次不跟了，南京的朋友照旧",
                    "expected": {
                        "main_origin": "绍兴北站",
                        "companion_origins": ["南京南站"],
                    },
                    "allowed_changes": ["companion_origins"],
                },
                {
                    "message": "最后一位也不去了，只有我自己",
                    "expected": {"main_origin": "绍兴北站", "companion_origins": []},
                    "allowed_changes": ["companion_origins"],
                },
            ],
        },
        {
            "name": "release_pending_return",
            "draft": {},
            "history_limit": 0,
            "turns": [
                {
                    "message": f"返程定{(today + timedelta(days=4)).month}月{(today + timedelta(days=4)).day}号，去的日期还没定",
                    "expected": {},
                    "expected_pending": {"end_date": day(4)},
                    "allowed_changes": [],
                    "question": True,
                },
                {
                    "message": "从宁波站出发",
                    "expected": {"main_origin": "宁波站"},
                    "expected_pending": {"end_date": day(4)},
                    "allowed_changes": ["main_origin"],
                },
                {
                    "message": "去的日子就选明天",
                    "expected": {"start_date": day(1), "end_date": day(4)},
                    "expected_pending": None,
                    "allowed_changes": ["start_date", "end_date"],
                },
            ],
        },
        {
            "name": "release_reverse_cancellation",
            "draft": complete,
            "turns": [
                {
                    "message": "目的地只选衢州，半径仍90公里",
                    "expected": {
                        "destination_regions": ["330800"],
                        "max_distance_km": 90,
                    },
                    "allowed_changes": ["destination_regions"],
                },
                {
                    "message": "只撤销路程上限，选的城市还保留",
                    "expected": {
                        "max_distance_km": None,
                        "destination_regions": ["330800"],
                    },
                    "allowed_changes": ["max_distance_km"],
                },
            ],
        },
        {
            "name": "release_chat_time_no_edit",
            "draft": complete,
            "turns": [
                {
                    "message": "我后天再把照片发给你，出游日期先别动",
                    "expected": {},
                    "allowed_changes": [],
                    "expected_pending": None,
                },
            ],
        },
    ]


def evaluate(client, base_url, scenarios, checkpoint=None):
    results = []
    for scenario in scenarios:
        draft = dict(scenario["draft"])
        history = []
        conversation_state = {"pending_date_request": None}
        for index, case in enumerate(scenario["turns"]):
            limit = scenario.get("history_limit", 6)
            body = {
                "message": case["message"],
                "revision": index,
                "draft": draft,
                "history": history[-limit:] if limit else [],
                "conversation_state": conversation_state,
            }
            started = monotonic()
            response = client.post(base_url + "/api/v1/assistant/turns", json=body)
            if response.status_code == 429:
                print("Local rate limit; waiting 60 seconds once.", flush=True)
                sleep(60)
                response = client.post(base_url + "/api/v1/assistant/turns", json=body)
            data = response.json()
            errors = []
            if response.status_code != 200:
                errors.append("http_status")
            elif data.get("source") != "live":
                errors.append("not_live")
            else:
                before = dict(draft)
                draft.update(data.get("patch", {}))
                conversation_state = data.get("conversation_state", conversation_state)
                if "allowed_changes" in case:
                    for field in set(before) | set(draft):
                        if field not in case["allowed_changes"] and not same_condition(
                            field, draft.get(field), before.get(field)
                        ):
                            errors.append("unrequested_" + field)
                for field, expected in case["expected"].items():
                    if not same_condition(field, draft.get(field), expected):
                        errors.append(field)
                for field in case.get("absent", []):
                    if draft.get(field):
                        errors.append("unexpected_" + field)
                if case.get("question") and not data.get("question"):
                    errors.append("missing_clarification")
                if case.get("question_contains") and not any(
                    word in (data.get("question") or "")
                    for word in case["question_contains"]
                ):
                    errors.append("wrong_clarification_topic")
                if case.get("unsupported") and not data.get("unsupported_preferences"):
                    errors.append("missing_capability_boundary")
                if "pending_duration" in case and (
                    (conversation_state.get("pending_date_request") or {}).get(
                        "duration_days"
                    )
                    != case["pending_duration"]
                ):
                    errors.append("pending_duration")
                if (
                    "expected_pending" in case
                    and conversation_state.get("pending_date_request")
                    != case["expected_pending"]
                ):
                    errors.append("pending_date_request")
                for kind in case.get("required_types", []):
                    if kind not in (draft.get("scenery_types") or []):
                        errors.append("missing_type_" + kind)
                for field in case.get("required_patch_fields", []):
                    if field not in (data.get("patch") or {}):
                        errors.append("missing_patch_" + field)
                for field, forbidden in case.get("forbidden_values", {}).items():
                    current = draft.get(field)
                    values = current if isinstance(current, list) else [current]
                    if any(value in forbidden for value in values):
                        errors.append("stale_" + field)
                for kind in case.get("excluded_types", []):
                    if kind in (draft.get("scenery_types") or []):
                        errors.append("excluded_type_" + kind)
            results.append(
                {
                    "scenario": scenario["name"],
                    "turn": index,
                    "message": case["message"],
                    "status": response.status_code,
                    "source": data.get("source"),
                    "patch": data.get("patch"),
                    "question": data.get("question"),
                    "unsupported_preferences": data.get("unsupported_preferences"),
                    "conversation_state": data.get("conversation_state"),
                    "errors": errors,
                    "elapsed_seconds": round(monotonic() - started, 2),
                }
            )
            print(json.dumps(results[-1], ensure_ascii=False), flush=True)
            if checkpoint:
                checkpoint(results)
            history.extend(
                [
                    {"role": "user", "content": case["message"]},
                    {
                        "role": "assistant",
                        "content": (
                            data.get("reply", "") + "\n" + (data.get("question") or "")
                        ).strip()[:1000]
                        or "请求失败",
                    },
                ]
            )
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8026")
    parser.add_argument("--scenario", help="Run only one named scenario")
    parser.add_argument(
        "--holdout", action="store_true", help="Independent paraphrase and scope checks"
    )
    parser.add_argument(
        "--native-smoke", action="store_true", help="Only six native-protocol key turns"
    )
    parser.add_argument(
        "--date-roles",
        action="store_true",
        help="Only four independent date-role controls",
    )
    parser.add_argument(
        "--release-holdout",
        action="store_true",
        help="Twelve frozen post-selection scope and memory turns",
    )
    parser.add_argument(
        "--report", default="test-results/assistant-live-acceptance.json"
    )
    parser.add_argument(
        "--demo-rehearsal",
        action="store_true",
        help="Four explicit-input deadline rehearsal turns; not general acceptance",
    )
    args = parser.parse_args()
    url = urlsplit(args.base_url)
    if (
        url.hostname not in {"127.0.0.1", "localhost"}
        or url.scheme != "http"
        or url.username
    ):
        parser.error("Only a local HTTP server is allowed.")
    # Backend uses China time even when the host timezone differs.
    today = (datetime.now(UTC) + timedelta(hours=8)).date()
    if (
        sum(
            (
                args.holdout,
                args.native_smoke,
                args.date_roles,
                args.release_holdout,
                args.demo_rehearsal,
            )
        )
        > 1
    ):
        parser.error("Choose one evaluation suite")
    selected = (
        demo_cases(today)
        if args.demo_rehearsal
        else release_cases(today)
        if args.release_holdout
        else date_role_cases(today)
        if args.date_roles
        else native_smoke_cases(today)
        if args.native_smoke
        else holdout_cases(today)
        if args.holdout
        else cases(today)
    )
    scenarios = [
        case for case in selected if not args.scenario or case["name"] == args.scenario
    ]
    if not scenarios:
        parser.error("Unknown scenario")
    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)

    def checkpoint(results):
        report.write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    with httpx.Client(timeout=100, trust_env=False) as client:
        results = evaluate(
            client, args.base_url.rstrip("/"), scenarios, checkpoint=checkpoint
        )
    failures = sum(bool(result["errors"]) for result in results)
    print(f"Live acceptance: {len(results) - failures}/{len(results)} passed.")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
