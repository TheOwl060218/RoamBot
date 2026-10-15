"""Task-oriented contracts. Models propose; the executor binds and authorizes."""

from dataclasses import dataclass
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


class Selection(Parameters):
    places: list[Reference] = Field(max_length=3)


class CreatePlanArgs(Parameters):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    expected_count: int | None = Field(default=None, ge=1, le=100)
    places: list[Reference] | None = Field(default=None, min_length=2, max_length=3)


class UpdatePlanArgs(ResourceTarget):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    expected_count: int | None = Field(default=None, ge=1, le=100)


class VoteArgs(Parameters):
    preferred: Reference | None = None
    acceptable: list[Reference] | None = Field(default=None, max_length=3)


class DateViewArgs(Parameters):
    date: str = Field(pattern="^(all|[0-9]{4}-[0-9]{2}-[0-9]{2})$")


class JoinArgs(Parameters):
    nickname: str = Field(min_length=1, max_length=32)


class NavigateArgs(Parameters):
    page: Literal["home", "recommend", "favorites", "history", "plans"]


class EditArgs(Parameters):
    field: Literal[
        "mainOrigin", "companions", "dates", "sceneryTypes", "range", "targetPlace", "weights"
    ]


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
        "update_search_conditions",
        "无入参，arguments必须为{}。程序按本轮原文修改条件，保留未提及条件。",
    ),
    _tool("explain_result", "解读当前真实结果的天气、路程、评分或差异，不修改条件。"),
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
    _tool("create_plan_from_selection", "用当前历史的2–3个已选地点创建计划。", CreatePlanArgs),
    _tool("update_plan", "修改当前计划的名称或预计人数，保留未提及字段。", UpdatePlanArgs),
    _tool("delete_plan", "删除明确指定的当前用户计划。", ResourceTarget, destructive=True),
    _tool(
        "remove_participant", "移除当前计划中明确指定的同行者。", ResourceTarget, destructive=True
    ),
    _tool("rotate_invite", "生成或换新当前计划邀请，旧邀请失效。", destructive=True),
    _tool("revoke_invite", "撤销当前计划的邀请。", destructive=True),
    _tool("submit_vote", "提交自己的首选和可接受地点；不能代他人投票。", VoteArgs),
    _tool("close_voting", "结束当前计划投票，进入待定案状态。", destructive=True),
    _tool("decide_plan", "把当前计划中的一个候选定为目的地。", PlaceTarget, destructive=True),
    _tool("reopen_voting", "重新开放当前计划投票。", destructive=True),
    _tool("check_plan_weather", "检查当前计划剩余出行日期天气，遵守复查冷却。"),
    _tool("join_plan", "通过当前邀请以给定昵称加入，不更换登录身份。", JoinArgs),
    _tool("navigate", "打开指定站内页面。", NavigateArgs, kind="ui"),
    _tool("open_detail", "打开当前结果中的地点详情。", PlaceTarget, kind="ui"),
    _tool("open_map", "查看当前地点位置。", PlaceTarget, kind="ui"),
    _tool("close_layer", "只关闭当前最上层浮层。", kind="ui"),
    _tool(
        "select_candidates",
        "设置比较或同行清单，给出完整0–3个当前候选，空列表清空。",
        Selection,
        kind="ui",
    ),
    _tool("show_comparison", "显示已选择的候选对比。", kind="ui"),
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
    _tool("open_account", "打开登录或注册表单；不要通过对话索取密码。", kind="ui"),
    _tool("logout", "退出当前登录账户。"),
    _tool("copy_link", "复制最近生成的邀请或分享链接。", kind="ui"),
    _tool("open_external_map", "在高德中打开当前真实地点。", PlaceTarget, kind="ui"),
]
TOOL_CATALOG = {tool.name: tool for tool in _TOOLS}


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
    page: str = Field(default="/recommend", max_length=300)
    history_id: str | None = Field(default=None, max_length=100)
    plan_id: str | None = Field(default=None, max_length=100)
    share_id: str | None = Field(default=None, max_length=100)
    invite_token: str | None = Field(default=None, max_length=200)
    selected_ids: list[str] = Field(default_factory=list, max_length=3)
    visible_places: list[VisiblePlace] = Field(default_factory=list, max_length=7)
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
