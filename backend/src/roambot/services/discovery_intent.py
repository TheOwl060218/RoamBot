"""Execute quoted temporal and logical intent, never parse a sample vocabulary."""

from datetime import timedelta
import json

from roambot.domain.discovery import ExperienceRequirement, RequirementGroup, RetrievalDirection
from roambot.services.assistant_interpretation import combine_date_fragments


def compile_intent(plan, original=None):
    """Compile already quoted list intent; don't ask the model to repeat it."""
    if plan.intent != "search":
        return plan
    plan = plan.model_copy(deep=True)
    if original is not None:
        def quoted(value):
            if value and value not in original:
                try:
                    decoded = json.loads(value)
                    if isinstance(decoded, str) and decoded in original:
                        return decoded
                except ValueError:
                    pass
            return value

        plan.collection_quote = quoted(plan.collection_quote)
        for intent in (plan.temporal, plan.activity_relation, plan.collection_intent):
            if intent:
                intent.quote = quoted(intent.quote)
        if plan.activity_relation:
            for option in plan.activity_relation.options:
                option.quote = quoted(option.quote)
        for requirement in plan.requirements:
            requirement.quote = quoted(requirement.quote)
    context_mode_quote = getattr(plan.context, "travel_mode_quote", None)
    if context_mode_quote:
        if plan.travel_mode_quote and plan.travel_mode_quote != context_mode_quote:
            raise ValueError("出行方式的原文引用不一致。")
        plan.travel_mode_quote = context_mode_quote
    if plan.activity_relation:
        relation = plan.activity_relation
        if original is not None and relation.quote not in original:
            raise ValueError("活动关系须逐字引用用户原文。")
        members = []
        if relation.options:
            quotes = [option.quote for option in relation.options]
            if len(quotes) != len(set(quotes)) or any(quote not in relation.quote for quote in quotes):
                raise ValueError("各活动分支须绑定互不重复的真实活动原话，不能添加替代目标。")
            for option in relation.options:
                matches = [i for i, r in enumerate(plan.requirements, 1)
                           if r.role == "goal" and r.scope == "place" and r.quote == option.quote]
                if len(matches) > 1:
                    raise ValueError("活动分支重复出现在条件中。")
                if matches:
                    members.append(matches[0])
                else:
                    plan.requirements.append(ExperienceRequirement(
                        text=option.quote, quote=option.quote, role="goal",
                        importance=relation.importance))
                    members.append(len(plan.requirements))
            if any(r.role == "goal" and r.scope == "place" and i not in members
                   and sum(quote in r.quote for quote in quotes) > 1
                   for i, r in enumerate(plan.requirements, 1)):
                raise ValueError("已提供独立活动分支，不能另添必须兼有全部选项的复合目标。")
        else:
            members = [i for i, r in enumerate(plan.requirements, 1)
                       if r.role == "goal" and r.scope == "place" and r.importance != "accepted"
                       and r.quote in relation.quote]
        if len(members) < 2:
            raise ValueError("核心活动关系须绑定至少两个独立活动原话，不能遗漏或合并成一个新活动。")
        for index in members:
            plan.requirements[index - 1].importance = relation.importance
        matched = [g for g in plan.requirement_groups if set(g.requirements) == set(members)]
        if any(g.operator != relation.operator for g in matched):
            raise ValueError("核心活动关系与额外组合不一致。")
        if relation.importance == "preferred" and matched:
            raise ValueError("可取舍的活动倾向不能同时列为必要组合。")
        if relation.importance == "required" and not matched:
            plan.requirement_groups.append(RequirementGroup(
                quote=relation.quote, operator=relation.operator, requirements=members))
        if relation.options:
            branches = [RetrievalDirection.model_validate(option.model_dump(exclude={"quote"}))
                        for option in relation.options]
            if relation.operator == "any":
                outside = any(i not in members and r.role == "goal" and r.scope == "place"
                              and r.importance == "required"
                              for i, r in enumerate(plan.requirements, 1))
                directions = (plan.directions + branches if relation.importance == "preferred"
                              else branches + plan.directions if outside else branches)
                by_query = {}
                for direction in directions:
                    by_query.setdefault(direction.map_query, direction)
                plan.directions = list(by_query.values())
                plan.map_queries, plan.web_queries = [], []
            elif not plan.directions:
                plan.directions = branches
    if plan.collection_intent:
        intent = plan.collection_intent
        plan.collection_quote = intent.quote
        matching = [r for r in plan.requirements if r.scope == "collection"
                    and (r.quote in intent.quote or intent.quote in r.quote)]
        for requirement in matching:
            requirement.importance = intent.importance
        if matching:
            matching[0].text = matching[0].quote = intent.quote
    if (plan.collection_quote
            and not any(r.scope == "collection" and (
                r.quote in plan.collection_quote or plan.collection_quote in r.quote)
                for r in plan.requirements)):
        plan.requirements.append(ExperienceRequirement(
            text=plan.collection_quote, quote=plan.collection_quote,
            role="goal", scope="collection",
            importance=plan.collection_intent.importance if plan.collection_intent else "required"))
    return type(plan).model_validate(plan.model_dump())


def temporal_updates(intent, previous, original, today):
    if intent.quote not in original:
        raise ValueError("时间意图需要逐字引用用户原文。")
    request = combine_date_fragments(intent.request, None, today)
    start = request.start_date or previous.start_date
    if start is None:
        raise ValueError("所给时间片段缺少可确定的出游起点，不能忽略或编造日期。")
    duration = request.duration_days
    if duration is None:
        duration = ((previous.end_date - previous.start_date).days + 1
                    if previous.start_date and previous.end_date else 1)
    end = request.end_date or start + timedelta(days=duration - 1)
    if request.end_date and request.duration_days and (end - start).days + 1 != duration:
        raise ValueError("日期区间与持续天数不一致。")
    if end < start:
        raise ValueError("结束日期早于开始日期。")
    return {"start_date": start, "end_date": end, "date_quote": intent.quote}


def requirement_groups(criteria, values, original=None):
    by_index = {r["index"]: r for r in criteria}
    groups = []
    for value in values:
        group = RequirementGroup.model_validate(value)
        indices = group.requirements
        if (len(indices) != len(set(indices)) or not set(indices) <= by_index.keys()
                or any(by_index[i].get("scope", "place") != "place"
                       or by_index[i].get("importance", "required") != "required" for i in indices)):
            raise ValueError("选择组须引用真实、互不重复的逐地点必要项目，不能弱化其他条件。")
        if original is not None and group.quote not in original:
            raise ValueError("选择关系须逐字引用用户原文。")
        groups.append(group)
    return groups


def unmet_requirements(required, groups, supported):
    grouped = {i for group in groups for i in group.requirements}
    missing = set(required) - grouped - supported
    for group in groups:
        indices = set(group.requirements)
        satisfied = bool(indices & supported) if group.operator == "any" else indices <= supported
        if not satisfied:
            missing.update(indices - supported)
    return sorted(missing)
