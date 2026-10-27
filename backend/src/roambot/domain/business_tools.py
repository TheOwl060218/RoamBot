"""Task-oriented contracts. Models propose; the executor binds and authorizes."""

from dataclasses import dataclass
from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from roambot.domain.assistant import AssistantMessage, AssistantTurnRequest


class Parameters(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


Reference = str | Annotated[int, Field(ge=1, strict=True)]


class PlaceTarget(Parameters):
    place: Reference | None = None


class ResourceTarget(Parameters):
    target: Reference | None = None


class PlanScope(Parameters):
    plan: Reference | None = None


class PlanPlaceTarget(PlaceTarget, PlanScope):
    pass


class Selection(Parameters):
    places: list[Reference] = Field(max_length=3)


class ComparePlaces(Parameters):
    places: list[Reference] | None = Field(default=None, min_length=2, max_length=3)


class CreatePlanArgs(Parameters):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    expected_count: int | None = Field(default=None, ge=1, le=100)
    places: list[Reference] | None = Field(default=None, min_length=2, max_length=3)
    start_date: date | None = None
    end_date: date | None = None
    date_quote: str | None = Field(default=None, max_length=200)


class UpdatePlanArgs(ResourceTarget):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    expected_count: int | None = Field(default=None, ge=1, le=100)


class VoteArgs(PlanScope):
    preferred: Reference | None = None
    acceptable: list[Reference] | None = Field(default=None, max_length=3)


class DateViewArgs(Parameters):
    date: str = Field(pattern="^(all|[0-9]{4}-[0-9]{2}-[0-9]{2})$")


class JoinArgs(Parameters):
    nickname: str = Field(min_length=1, max_length=32)


class NavigateArgs(Parameters):
    page: Literal["home", "explore", "recommend", "favorites", "history", "plans", "itineraries"]


class ItineraryScope(Parameters):
    itinerary: Reference | None = None


class CreateItineraryArgs(Parameters):
    name: str = Field(min_length=1, max_length=100)


class AddItineraryStopArgs(ItineraryScope, PlaceTarget):
    pass


class EditItineraryArgs(ItineraryScope):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    start_date: date | None = None
    end_date: date | None = None
    date_quote: str | None = Field(default=None, max_length=200)
    travel_mode: Literal["walking", "bicycling", "driving"] | None = None


class MoveItineraryStopArgs(ItineraryScope, PlaceTarget):
    day: date | None = None
    date_quote: str | None = Field(default=None, max_length=200)
    position: int = Field(ge=1, le=60)


class GenerateItineraryArgs(ItineraryScope):
    optimize: bool = False


class ItineraryMapArgs(ItineraryScope):
    day: date | None = None
    day_number: int | None = Field(default=None, ge=1, le=30)


class EditArgs(Parameters):
    field: Literal[
        "mainOrigin", "companions", "dates", "sceneryTypes", "range", "targetPlace", "weights"
    ]


class ScrollArgs(Parameters):
    direction: Literal["up", "down", "left", "right", "top", "bottom"]


class MapViewArgs(Parameters):
    action: Literal["zoom_in", "zoom_out", "left", "right", "up", "down", "reset", "retry"]


class AccountArgs(Parameters):
    mode: Literal["login", "register"] = "login"


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: type[Parameters] = Parameters
    kind: str = "backend"
    destructive: bool = False

    def native_tool(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters.model_json_schema(),
            },
        }


def _tool(name, description, parameters=Parameters, *, kind="backend", destructive=False):
    return ToolDefinition(name, description, parameters, kind, destructive)


_TOOLS = [
    _tool(
        "create_itinerary",
        "创建独立的旅行行程，不是同行投票计划；不必在收集地点时填写日期。",
        CreateItineraryArgs,
    ),
    _tool("open_itinerary", "打开当前或具名的旅行行程。", ItineraryScope),
    _tool(
        "show_itinerary_map",
        "查看旅行行程某天的地图及路线；day是具体日期，day_number是第几天，从1开始。不重新查询路线。",
        ItineraryMapArgs,
    ),
    _tool(
        "add_to_itinerary",
        "把当前推荐或收藏中的一个真实地点加入最近创建的行程，或指定行程；不等同于收藏。",
        AddItineraryStopArgs,
    ),
    _tool(
        "edit_itinerary",
        "修改旅行行程名称、完整起止日期或交通方式，不影响同行投票计划。日期修改要date_quote原文。",
        EditItineraryArgs,
    ),
    _tool(
        "move_itinerary_stop",
        "把行程内真实地点移到指定日期及从1开始的位置；只保存顺序，不查询路线。day为空表示待安排；日期要原文quote。",
        MoveItineraryStopArgs,
    ),
    _tool(
        "remove_itinerary_stop",
        "把行程中的地点移出，不取消收藏、不删除历史。",
        AddItineraryStopArgs,
    ),
    _tool(
        "generate_itinerary",
        "用户明确要生成/更新路线才调用。optimize=true自动分天和重排；false严格保留用户手动顺序更新路线。需要已确定日期，会请求路线天气。",
        GenerateItineraryArgs,
    ),
    _tool(
        "update_search_conditions",
        "无入参，arguments必须为{}。程序按本轮原文修改条件，保留未提及条件。",
    ),
    _tool(
        "explain_result",
        "回答当前真实推荐结果的地点、天气、路程或差异问题，不修改条件、不重新查询。新推荐没有匹配指数。",
    ),
    _tool("run_recommendation", "按已确认条件查询推荐或指定地点评估；条件缺失则先补充。"),
    _tool("favorite_place", "收藏当前真实结果中的地点；未指明时用当前详情。", PlaceTarget),
    _tool("evaluate_favorite", "把当前收藏地点放入指定地点评估条件。", ResourceTarget),
    _tool("remove_favorite", "取消收藏，目标须唯一匹配当前用户收藏。", ResourceTarget),
    _tool("list_favorites", "查看当前用户的收藏。"),
    _tool("list_history", "查看当前用户查询历史。"),
    _tool("open_history", "打开一条实际查询历史。", ResourceTarget),
    _tool("rerun_history", "使用当前用户历史条件重新查询，过期日期需修改。", ResourceTarget),
    _tool("delete_history", "删除明确指定的一条历史。", ResourceTarget, destructive=True),
    _tool("clear_history", "清空当前用户全部历史。", destructive=True),
    _tool("create_share", "创建当前历史的匿名只读结果分享。", ResourceTarget),
    _tool("revoke_share", "撤销当前历史分享。", ResourceTarget, destructive=True),
    _tool("list_plans", "查看当前用户的同行计划。"),
    _tool("open_plan", "打开当前用户的一项计划。", ResourceTarget),
    _tool(
        "create_plan_from_selection",
        "用当前2–3个已选地点创建计划。新推荐可另外提供出行日期，date_quote须摘录用户日期原话；缺日期先问，不补默认。",
        CreatePlanArgs,
    ),
    _tool("update_plan", "修改当前计划的名称或预计人数，保留未提及字段。", UpdatePlanArgs),
    _tool("delete_plan", "删除明确指定的当前用户计划。", ResourceTarget, destructive=True),
    _tool(
        "remove_participant", "移除当前计划中明确指定的同行者。", ResourceTarget, destructive=True
    ),
    _tool(
        "rotate_invite", "生成或换新当前或具名计划邀请，旧邀请失效。", PlanScope, destructive=True
    ),
    _tool("revoke_invite", "撤销当前或具名计划的邀请。", PlanScope, destructive=True),
    _tool("submit_vote", "提交自己的首选和可接受地点；不能代他人投票。", VoteArgs),
    _tool("close_voting", "结束当前或具名计划投票，进入待定案状态。", PlanScope, destructive=True),
    _tool(
        "decide_plan", "把当前或具名计划中的一个候选定为目的地。", PlanPlaceTarget, destructive=True
    ),
    _tool("reopen_voting", "重新开放当前或具名计划投票。", PlanScope, destructive=True),
    _tool("check_plan_weather", "检查当前或具名计划剩余日期天气，遵守复查冷却。", PlanScope),
    _tool("join_plan", "通过当前邀请以给定昵称加入，不更换登录身份。", JoinArgs),
    _tool(
        "navigate",
        "打开指定站内页面：explore是新推荐，recommend是原推荐。",
        NavigateArgs,
        kind="ui",
    ),
    _tool("open_detail", "打开当前结果中的地点详情。", PlaceTarget, kind="ui"),
    _tool("open_map", "查看当前地点位置。", PlaceTarget, kind="ui"),
    _tool("close_layer", "只关闭当前最上层浮层。", kind="ui"),
    _tool(
        "select_candidates",
        "只设置比较或同行清单，不打开对比。给出完整0–3个当前候选；要查看对比须接show_comparison。空列表清空。",
        Selection,
        kind="ui",
    ),
    _tool(
        "show_comparison",
        "打开已选择候选的对比；尚未选够时先select_candidates，再调用本工具。",
        kind="ui",
    ),
    _tool(
        "compare_places",
        "比较2–3个当前地点：一次绑定候选、选入并打开对比；places省略时用已选清单。优先用于直接比较任务。",
        ComparePlaces,
        kind="ui",
    ),
    _tool("show_vote_panel", "打开当前计划的本人投票面板。", kind="ui"),
    _tool("show_plan_management", "打开当前计划的管理区。", kind="ui"),
    _tool("edit_plan", "打开当前计划的名称和人数编辑表单。", kind="ui"),
    _tool("set_weather_view", "选择计划天气比较日期，或显示全部日期。", DateViewArgs, kind="ui"),
    _tool("show_day_explanation", "查看计划中某候选的当前日期天气解读。", PlaceTarget, kind="ui"),
    _tool("show_candidates", "打开当前结果的候选地点列表。", kind="ui"),
    _tool("go_back", "返回上一页面或最上层浮层。", kind="ui"),
    _tool("edit_condition", "打开指定条件的手动编辑器。", EditArgs, kind="ui"),
    _tool("start_new_query", "开始新查询，保留可撤销状态。", kind="ui"),
    _tool("undo_new_query", "撤销刚开始的新查询。", kind="ui"),
    _tool("clear_conversation", "清除当前聊天记录，不清除查询条件。", kind="ui"),
    _tool("open_account", "打开登录或注册表单；不要通过对话索取密码。", AccountArgs, kind="ui"),
    _tool("logout", "退出当前登录账户。"),
    _tool("copy_link", "复制最近生成的邀请或分享链接。", kind="ui"),
    _tool("open_external_map", "在高德中打开当前真实地点。", PlaceTarget, kind="ui"),
    _tool("show_tools", "打开推荐页面更多功能。", kind="ui"),
    _tool("show_preferences", "打开推荐页面其他偏好。", kind="ui"),
    _tool("choose_favorite", "在推荐页面打开收藏选地点。", kind="ui"),
    _tool("start_team_pick", "进入同行挑选模式，尚未选满时不立即创建计划。", kind="ui"),
    _tool("scroll_view", "滚动当前内容或横向候选清单，上下左右或到顶到底。", ScrollArgs, kind="ui"),
    _tool("refresh_page", "刷新当前页面的实际资源与状态。", kind="ui"),
    _tool("open_generated_link", "在本页打开刚生成的真实邀请或分享链接。", kind="ui"),
    _tool("describe_capabilities", "询问当前可执行功能和操作方式；返回真实工具清单。"),
    _tool("end_team_pick", "结束同行挑选模式，保留现有条件和结果。", kind="ui"),
    _tool(
        "control_map", "缩放、平移、重置或重试当前地图，不需要鼠标拖拽。", MapViewArgs, kind="ui"
    ),
    _tool("scroll_chat", "查看更早或更近的聊天记录，可到顶到底。", ScrollArgs, kind="ui"),
]
TOOL_CATALOG = {tool.name: tool for tool in _TOOLS}
# The intake planner may propose these local-result tasks in its existing call.
# Everything else still uses the complete planner and authorization boundary.
INTAKE_TOOLS = frozenset(
    {
        "explain_result",
        "favorite_place",
        "create_plan_from_selection",
        "open_detail",
        "open_map",
        "close_layer",
        "select_candidates",
        "show_comparison",
        "compare_places",
        "show_candidates",
        "scroll_view",
        "go_back",
        "navigate",
    }
)


class Action(Parameters):
    tool: str = Field(min_length=1, max_length=80)
    arguments: dict[str, Any] = Field(default_factory=dict)

    def validated_arguments(self) -> Parameters:
        if self.tool not in TOOL_CATALOG:
            raise ValueError("unknown business tool")
        return TOOL_CATALOG[self.tool].parameters.model_validate(self.arguments)


class VisiblePlace(Parameters):
    id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)


class VisibleResources(Parameters):
    kind: Literal["history", "plans", "favorites"]
    ids: list[str] = Field(max_length=100)


class CommandContext(Parameters):
    itinerary_id: str | None = Field(default=None, max_length=100)
    itinerary_version: int | None = Field(default=None, ge=1)
    page_loading: bool = False
    page: str = Field(default="/recommend", max_length=300)
    history_id: str | None = Field(default=None, max_length=100)
    discovery_job_id: str | None = Field(default=None, max_length=64)
    plan_id: str | None = Field(default=None, max_length=100)
    share_id: str | None = Field(default=None, max_length=100)
    invite_token: str | None = Field(default=None, max_length=200)
    selected_ids: list[str] = Field(default_factory=list, max_length=3)
    visible_places: list[VisiblePlace] = Field(default_factory=list, max_length=24)
    visible_resources: VisibleResources | None = None
    focused_id: str | None = Field(default=None, max_length=200)
    result_version: int | None = Field(default=None, ge=0)
    dirty: bool = False
    layer: str | None = Field(default=None, max_length=40)
    resource_version: str | None = Field(default=None, max_length=100)
    weather_date: str | None = Field(default=None, max_length=10)
    all_dates: bool = False
    assistant_turn: AssistantTurnRequest | None = None
    conversation: list[AssistantMessage] = Field(default_factory=list, max_length=6)


class CommandRequest(Parameters):
    request_id: str = Field(min_length=16, max_length=100)
    message: str = Field(min_length=1, max_length=2000)
    context: CommandContext = Field(default_factory=CommandContext)
    intake_id: str | None = Field(default=None, max_length=64)


class ExecutionRequest(Parameters):
    request_id: str = Field(min_length=16, max_length=100)
    proposal: str = Field(min_length=1, max_length=100)
    confirmed: bool = False


class BusinessPlan(Parameters):
    actions: list[Action] = Field(default_factory=list, max_length=6)
    question: str | None = Field(default=None, min_length=1, max_length=300)


def resolve_reference(reference, objects: list[dict], *, focused: str | None = None):
    """References can only resolve inside the supplied, authorized object set."""
    if reference is None:
        reference = focused
    if reference is None:
        raise ValueError("请明确选择要操作的对象。")
    ordinal = {
        "第一个": 1,
        "第二个": 2,
        "第三个": 3,
        "第一个地点": 1,
        "第二个地点": 2,
        "第三个地点": 3,
    }
    position = ordinal.get(reference) if isinstance(reference, str) else reference
    if isinstance(reference, str) and reference.isdecimal():
        position = int(reference)
    if type(position) is int:
        if 1 <= position <= len(objects):
            return objects[position - 1]
        raise ValueError("这个序号不在当前对象中。")
    matches = [o for o in objects if reference in (o.get("id"), o.get("name"))]
    if len(matches) != 1:
        raise ValueError("对象不存在或有重名，请明确选择。")
    return matches[0]
