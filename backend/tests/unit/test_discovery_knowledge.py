import json

from test_discovery import Maps

from roambot.persistence.discovery_knowledge import DiscoveryKnowledge
from roambot.services.discovery_grounding import passage_view
from roambot.domain.discovery_text import venue_paragraphs


def test_public_index_searches_chinese_without_scenery_categories_and_expires(tmp_path):
    now = [100]
    index = DiscoveryKnowledge(tmp_path / "public.sqlite3", clock=lambda: now[0])
    place = Maps().search("", "苏州", None, None)[1]
    index.remember(
        place,
        [
            {
                "url": "https://example.org/lake",
                "title": "湖边绿地介绍",
                "excerpt": "湖边绿地拥有草坪和湖畔休憩空间。",
                "kind": "web_page",
            }
        ],
    )
    results = index.find("草坪 湖畔休憩", region="苏州市")
    assert len(results) == 1 and results[0]["place"]["id"] == place["id"]
    assert index.find("草坪", region="杭州") == []
    now[0] += 86401
    assert index.find("草坪", region="苏州") == []


def test_identity_enrichment_reuses_only_fresh_sources_for_current_map_ids(tmp_path):
    now = [100]
    index = DiscoveryKnowledge(tmp_path / 'identity.sqlite3', clock=lambda: now[0])
    place = Maps().search('', '苏州', None, None)[0]
    index.remember(place, [{'kind': 'web_page', 'url': 'https://example.org/book',
        'title': place['name'], 'excerpt': place['name'] + '提供公开阅读空间。'}])
    assert index.sources_for([place])[place['id']]
    assert index.sources_for([place | {'id': 'another-real-map-id'}]) == {}
    assert index.sources_for([place | {'name': '已经更名的另一个场地'}])[place['id']] == []
    now[0] += 86401
    assert index.sources_for([place]) == {}


def test_public_index_stores_only_actual_place_and_public_source_fields(tmp_path):
    index = DiscoveryKnowledge(tmp_path / "public.sqlite3")
    place = Maps().search("", "苏州", None, None)[0] | {"user_message": "不应保存的私聊"}
    source = {
        "url": "https://example.org/book",
        "title": "独立书店介绍",
        "excerpt": "独立书店的公开资料正文。",
        "kind": "web_page",
        "conversation": "不应保存的对话",
        "actor": "private-identity",
    }
    index.remember(place, [source])
    result = index.find("独立书店", region="苏州")
    raw = json.dumps(result, ensure_ascii=False)
    assert result
    assert "不应保存" not in raw and "private-identity" not in raw
    # Non-public endpoints and unrelated entities never become shared evidence.
    index.remember(place, [source | {"url": "https://127.0.0.1/secret"}])
    assert len(index.find("独立书店")[0]["sources"]) == 1


def test_shared_index_does_not_accept_uncorroborated_model_fact_strings(tmp_path):
    index = DiscoveryKnowledge(tmp_path / "public.sqlite3")
    place = Maps().search("", "苏州", None, None)[0]
    index.remember(
        place,
        [
            {
                "url": "https://example.org/other",
                "title": "别的地方",
                "excerpt": "这里有许多书籍",
                "kind": "web_page",
            }
        ],
    )
    assert index.find("书籍") == []


def test_city_name_alone_is_not_evidence_for_an_uncovered_activity(tmp_path):
    index = DiscoveryKnowledge(tmp_path / 'public.sqlite3')
    place = Maps().search('', '苏州', None, None)[0]
    index.remember(place, [{'url': 'https://example.org/book', 'kind': 'web_page',
        'title': '苏州独立书店介绍', 'excerpt': '苏州的独立书店有休息和阅读空间。'}])
    assert index.find('苏州独立书店', region='苏州')
    assert index.find('苏州滑雪', region='苏州') == []
    assert index.find('苏州', region='苏州') == []


def test_long_flat_article_keeps_named_local_sentences_instead_of_other_venues():
    place = {'name': '湖边绿地'}
    source = {'title': '城市空间合集', 'excerpt':
        ('其他场所的介绍与不同设施，不属于本地点。' * 50)
        + '湖边绿地有临水步道。这里可以散步休息。'
        + ('另外一个场所介绍的是室内展厅。' * 50)}
    parts = venue_paragraphs(place, source)
    assert parts == ['湖边绿地有临水步道。', '这里可以散步休息。']
    assert '室内展厅' not in ''.join(parts)


def test_passages_do_not_borrow_facilities_from_another_venue_section():
    source = {
        "id": "e8",
        "kind": "web_page",
        "title": "当地书店介绍",
        "url": "https://example.org/shops",
        "excerpt": "01独立书店\n\n独立书店经营旧书和画册。\n\n"
        "02另一家书店\n\n另一家书店设有摄影集专柜和免费沙发座位。",
    }
    passages = passage_view({"id": "amap:1", "name": "独立书店"}, source, [])
    assert passages and all("摄影集" not in p["excerpt"] for p in passages)
    assert all(p["id"].startswith("e8.p") for p in passages)
    assert all(p["place_id"] == "amap:1" for p in passages)


def test_index_does_not_assign_another_venue_section_to_current_place(tmp_path):
    index = DiscoveryKnowledge(tmp_path / "public.sqlite3")
    place = Maps().search("", "苏州", None, None)[0]
    index.remember(
        place,
        [
            {
                "url": "https://example.org/list",
                "title": "休闲场所介绍",
                "kind": "web_page",
                "excerpt": "01独立书店\n\n独立书店经营旧书。\n\n"
                "02湖边绿地\n\n湖边绿地有草坪、湖畔野餐空间。",
            }
        ],
    )
    assert index.find("独立书店", region="苏州")
    assert index.find("草坪 野餐", region="苏州") == []


def test_index_reusing_a_record_does_not_refresh_its_verified_time(tmp_path):
    now = [100]
    index = DiscoveryKnowledge(tmp_path / "public.sqlite3", clock=lambda: now[0])
    place = Maps().search("", "苏州", None, None)[0]
    source = {
        "url": "https://example.org/book",
        "title": "独立书店介绍",
        "kind": "web_page",
        "excerpt": "独立书店的资料。",
    }
    index.remember(place, [source])
    now[0] += 80000
    existing = index.find("独立书店")[0]
    index.remember(existing["place"], existing["sources"])
    now[0] += 6500
    assert index.find("独立书店") == []
