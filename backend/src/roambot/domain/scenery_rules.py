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
