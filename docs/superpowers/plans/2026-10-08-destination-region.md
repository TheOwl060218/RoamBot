# Destination Region Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking. Repository instructions prohibit subagents; execution and self-review stay in this session.

**Goal:** 让推荐查询支持可输入的多选省市，默认最大距离内不限省市，筛选真实生效且不撑高表单。

**Architecture:** 后端提供静态行政目录与编码校验；空间 POI 查询解除出发城市限制，地区硬过滤在候选配额之前执行。前端 RegionInput 使用浮层、固定高度框内胶囊和本地匹配，请求/草稿/历史/摘要贯通；不改变评估与同行计划权限。

**Tech Stack:** 既有 FastAPI/Pydantic、React/TypeScript、Lucide、pytest/Vitest/Playwright；不安装依赖。

**Spec:** `docs/superpowers/specs/2026-10-08-destination-region-design.md`（用户2026-10-08要求开始修改，视为正式设计确认）。

## Global Constraints

- 默认“最大距离内不限省市”；地区之间 OR，与主出发地最大距离及风景规则求交集。
- 只在推荐模式使用；评估请求不携带地区，切回保留草稿。
- 单一外框、文字“选择”、框内胶囊单行溢出 `+N`；浮层不推动后续控件。
- 保留既有 ScenerySelector、权重、同行出发地、主题、认证、CSRF、公开分享白名单。
- 每种风景类型最多一次 POI 网络查询、每次25条，最多6种；无逐地区倍增或空结果补查。
- 自动测试仅 Mock/HTTP fixture；不改用户8000/5173、data-competition-demo、密钥或远程部署。
- 数据库不迁移；旧请求/快照缺地区字段按兼容语义读取，搜索缓存算法版本升级。
- 沿用已获批准的当前实验分支；执行开始前核对工作区。逐任务通过后记录检查点，产品改动暂不commit/push，等待用户验收；计划文档不代表产品通过。

## Review Focus

1. 输入法确认字词的 Enter 不能意外添加地区或提交推荐（Task 4）。
2. 全省覆盖、直辖市与省直辖城市的编码不能靠字符串猜父级（Task 1/2）。
3. 地区未知的 POI 在受限结果中不能靠出发 city 兜底冒充匹配（Task 2）。
4. 编辑草稿或用户切换账号不能修改旧结果摘要、绕过可信重新推荐（Task 5/6）。
5. 右侧/底部空间不足与侧栏裁切时浮层仍可选择和关闭（Task 4/6）。

## 文件与责任

- 新增 `backend/src/roambot/domain/regions.py`：目录、规范化、行政归属、筛选谓词。
- 新增 `backend/src/roambot/domain/data/regions.json`：独立许可目录及县区显式父级索引、版本/来源记录。
- 新增 `backend/src/roambot/api/routes/regions.py`：匿名只读目录。
- 修改 domain/models.py、main.py：新增缺省字段、校验与路由挂载。
- 修改 providers/protocols.py、amap.py、mock.py、cached.py 与 services/recommendations.py：空间候选、归属筛选、缓存。
- 新增 `frontend/src/features/search/regions.ts`：目录加载、规范化、匹配与显示。
- 新增 `frontend/src/features/search/RegionInput.tsx`：受控多选输入与 Portal 浮层。
- 修改 api/types.ts、TravelForm.tsx、formState.ts、QuerySummary.tsx、SearchWorkspace.tsx、features/history/restoreHistorySearch.ts 和 styles/forms.css：接入及历史/摘要。
- 对应下列测试、SPEC.md/PLAN.md/交接与开发过程记录；不改计划详情布局。

### Task 1: 静态目录、模型与只读 API

**Files:** Create regions.py、data/regions.json、api/routes/regions.py；Modify domain/models.py、main.py；Test backend/tests/unit/test_regions.py、test_models.py、backend/tests/api/test_region_catalog_api.py。

**Interfaces:** `normalize_destination_regions(values: list[str]) -> list[str]`；`region_catalog() -> dict[str, object]` 返回 `{version, regions:[{adcode,name,level,province_adcode}]}`；RecommendationRequest.destination_regions 缺省 `[]`。Destination 新字段均为 `str | None = None`，字段名依设计。

- [x] **Step 1: 先补目录与模型 RED。**

```python
def test_normalizes_province_coverage():
    assert normalize_destination_regions(['320500', '320000', '330100', '320500']) == ['320000', '330100']

def test_rejects_unknown_region():
    with pytest.raises(ValueError):
        normalize_destination_regions(['000000'])
```

同时测试旧请求缺字段默认不限、重复/超目录规模拒绝或去重契约、直辖市及省直辖城市来自显式归属、输入列表不被修改。API测试匿名200、响应版本非空、只返回省市可选层级且没有 Provider 调用。
- [x] **Step 2: 运行 `.venv/Scripts/python.exe -m pytest backend/tests/unit/test_regions.py backend/tests/unit/test_models.py backend/tests/api/test_region_catalog_api.py -q`，记录新增契约失败。**
- [x] **Step 3: 采用用户批准的独立WTFPL目录固定提交并派生静态目录。** 记录来源、2023-06-30数据日期、读取日期、归一化源文本SHA256和许可证。原高德下载表步骤已撤销，不安装包。保留县区到地级/省级的显式索引供 POI 解析，普通县区不作候选，明确省直辖县级条目按真实省级父项提供。数据层用标准库结构，避免 models 与 regions 循环导入；过滤模块以 TYPE_CHECKING 引用 Destination。
- [x] **Step 4: 实现上述两个接口，request field validator 复用规范化；新建 get_regions 路由并挂 `/api/v1/regions`。** 名称只来自目录，错误沿用既有422处理。
- [x] **Step 5: 重跑 Step 2 至全通过，再运行 Ruff；记录目录来源/特殊地区覆盖，未有数据不得标记为全国已覆盖。**
- [x] **Step 6: 自审 API 无隐私/Provider依赖，记录检查点，不提交产品代码。**

### Task 2: 跨城市空间候选和地区过滤

**Files:** Modify providers/protocols.py、amap.py、mock.py、services/recommendations.py、domain/regions.py；Test unit/test_amap_provider.py、test_mock_providers.py、test_recommendation_service.py；HTTP响应fixture使用测试中的内联构造器。

**Interfaces:** `PlaceProvider.search(center: Coordinate, city: str, scenery_types: tuple[SceneryType,...], radius_km: float, destination_regions: tuple[str,...] = ()) -> list[Destination]`；`matches_destination_regions(destination: Destination, regions: tuple[str,...]) -> bool`；city仅为出发定位提示。

- [x] **Step 1: 写 RED，沿用测试中既有 origin/destination/HTTP fake 构造器。** 新测试名称与精确断言：`test_unrestricted_search_keeps_nearby_cross_city_poi`（苏州提示下跨市仍入候选）；`test_selected_regions_are_or_and_intersect_distance`（江苏或杭州可选，另一省和主出发地超距排除）；`test_unknown_region_does_not_use_origin_city_fallback`（无归属受限排除，不限可保留）；`test_large_radius_uses_polygon_without_city_limit`（大于50走v3 polygon，矩形覆盖圆、角落超距排除）；`test_each_scenery_type_makes_at_most_one_poi_request`（6类型调用≤6，1/3地区调用数相同，空查询不补查）。
- [x] **Step 2: 运行 `.venv/Scripts/python.exe -m pytest backend/tests/unit/test_amap_provider.py backend/tests/unit/test_mock_providers.py backend/tests/unit/test_recommendation_service.py -q` 并记录有效 RED。**
- [x] **Step 3: 按 Task 1 目录解析 pcode/adcode 到省市；v3从 biz_ext.rating 读取有效评分，v5沿用 business.rating；缺失/无效时为None。** 增加两类 fixture 缺失评分/行政字段断言，不用城市文本推测编码。
- [x] **Step 4: 更新搜索协议、AMap与Mock实现。** ≤50km周边不传出发城市硬限制；>50km用主坐标半径的球面包络矩形调用v3 polygon（经纬度最多6位，合法范围）；每类一次请求25条。先范围/球面距离/类型过滤再去重、原配额合并；不截断筛选后的有效候选。不新增网络重试。极端高纬/经度跨界无法构造合法单矩形时返回 ProviderError，不扩大到任意全国结果。
- [x] **Step 5: 推荐服务传入规范地区并再次硬过滤，随后保持原路线距离、天气、分数和解释逻辑。** 加 `region_metadata_missing` notice（缺归属候选实际被排除时），结果来源提示使用“部分地点缺少地区信息，未纳入本次范围”。Mock原演示数据补独立目录显式归属，新增明确为演示的跨市/跨省fixture；不要伪称真实天气/余票或覆盖全国景点。
- [x] **Step 6: 重跑 Step 2、预算测试及Ruff，更新已被明确修改的同城/补查旧契约，不放宽新过滤断言；记录检查点。**

### Task 3: 缓存、保存请求与旧数据兼容

**Files:** Modify providers/cached.py；Test unit/test_cached_providers.py、api/test_recommendations.py、api/test_history.py、api/test_shares.py、api/test_plans.py。

**Interfaces:** CachedPlaceProvider.search 同 Task 2 签名；cache params增加 `search_version='destination-regions-v1'`、目录版本、规范排序地区。历史请求继续由model_dump排除computed fields后保存，无数据库结构更改。

- [x] **Step 1: RED `test_region_search_cache_isolated_and_order_independent`：不同地区两次inner调用、同集合不同顺序一次；`test_old_destination_cache_is_not_reused_for_new_search`：旧key不命中；空结果不重用原错误同城缓存。**
- [x] **Step 2: 运行 `.venv/Scripts/python.exe -m pytest backend/tests/unit/test_cached_providers.py backend/tests/api/test_history.py -q`，确认失败后实现键与签名透传。**
- [x] **Step 3: 补历史 RED：capture保存编码、rerun保留编码、旧历史缺字段成功读取、非法新请求422且不写半条历史。** 复用既有登录/CSRF隔离测试助手；用户身份不可串用。
- [x] **Step 4: 运行 history/recommendations 测试，按最小需要修复历史模型读取，不迁移/批量重写原记录。** 新计划仍从原可信历史复制；公开share断言保留既有精确白名单，不顺带暴露行政请求/出发地址。
- [x] **Step 5: `.venv/Scripts/python.exe -m pytest backend/tests -q` 与 `.venv/Scripts/python.exe -m ruff check backend` 全通过；记录旧数据兼容与无迁移事实。**

### Task 4: 可输入的固定高度多选地区控件

**Files:** Create frontend/src/features/search/regions.ts、RegionInput.tsx、frontend/tests/RegionInput.test.tsx；Modify frontend/src/api/types.ts、styles/forms.css。

**Interfaces:** 类型 `DestinationRegion={adcode:string;name:string;level:'province'|'city';province_adcode:string}`、`RegionCatalog={version:string;regions:DestinationRegion[]}`；`loadRegionCatalog(): Promise<RegionCatalog>` 调用已有apiClient；`normalizeRegions(ids:string[],catalog:RegionCatalog):string[]`；匹配在RegionInput按目录名称过滤。

RegionInput props：`value:string[]; onChange:(ids:string[])=>void; query:string; onQueryChange:(query:string)=>void; 保留表单既有可编辑行为`。目录在控件中按需加载，请求失败清缓存Promise允许重试；前端不可发往高德。

- [x] **Step 1: 组件RED：`typing_hang_shows_hangzhou_without_selecting` 输入“杭”候选含“杭州市 · 浙江省”、onChange未调用；`enter_selects_highlighted_candidate` 点击/Enter返回330100；`composition_enter_does_not_select`；`province_selection_merges_children` 返回规范集合；`failed_catalog_can_retry` 显示失败重试而非自由文本；`overflow_can_open_all_selected_and_remove` 可看全部并移除。** 用Vitest apiClient mock，既有testing-library/user-event。
- [x] **Step 2: `node frontend/node_modules/vitest/vitest.mjs run frontend/tests/RegionInput.test.tsx`，确认导入/行为RED并分别记录。** 若root配置不发现测试，改在frontend目录执行 `node node_modules/vitest/vitest.mjs run tests/RegionInput.test.tsx`，以实际配置为准。
- [x] **Step 3: 实现目录工具与RegionInput。** 输入组合、键盘活动候选和选中编码分离；使用可访问combobox/listbox，单行胶囊；按可用宽度测量可显示胶囊，保留输入及“选择”按钮空间，剩余为+N。一次一个Portal候选面板，跟随锚点/滚动/ResizeObserver，关闭无布局变化；不添加“框中框”。点击覆盖城市不改变选择。
- [x] **Step 4: 添加现有主题CSS。** 框与最大距离同高；选择按钮touch有效区域至少44px；焦点在整栏可见。浮层与锚点左右在viewport内，长候选列表限高滚动，完整已选名称可访问；屏幕宽320也不能横向溢出。
- [x] **Step 5: 聚焦GREEN、ESLint、tsc通过，新增ResizeObserver mock仅在测试setup需要时用，不能篡改生产布局以满足jsdom；记录检查点。**

### Task 5: 表单、历史回填与实际请求摘要

**Files:** Modify TravelForm.tsx、formState.ts、QuerySummary.tsx、SearchWorkspace.tsx、features/history/restoreHistorySearch.ts、api/types.ts；Test TravelForm.test.tsx、SearchWorkspace.test.tsx、restoreHistorySearch.test.ts；Create QuerySummary.test.tsx。

**Interfaces:** 推荐类型新增 `destination_regions?:string[]`（缺省兼容旧fixture）；TravelFormDraft新增 `destinationRegions?:string[]`；`draftFromRequest(request: RecommendationRequest|PlaceEvaluationRequest): TravelFormDraft` 放formState.ts，仅映射已提交事实，用现有权重转换函数。QuerySummary新增 `request?: RecommendationRequest|PlaceEvaluationRequest` 并在有request时优先显示；无request走原恢复fallback但不假定新地区条件。

- [x] **Step 1: RED `recommendation_submits_selected_regions` 请求含编码；`evaluation_omits_regions_but_preserves_draft`；`unconfirmed_region_text_blocks_submit` 出现两秒原胶囊精确提示“请从候选中选择省市，或清空未选择的输入”，onSubmit不调用；旧草稿无字段仍可提交。**
- [x] **Step 2: 运行frontend聚焦TravelForm/restoreHistorySearch/QuerySummary，记录RED后接入RegionInput与持久化。** 未确认输入独立state，目录加载并不自动发起推荐；submission/目录状态错误遵循现有ValidationBubble，不改变原风景选项。
- [x] **Step 3: RED `summary_uses_submitted_request_not_edited_draft` 请求杭州，session草稿苏州，摘要仍杭州；`rerun_restores_region_selection`；`guest_result_stays_untrusted_after_account_switch`；`evaluation_summary_does_not_show_destination_filter`。**
- [x] **Step 4: 修改SearchWorkspace传result.query_request给摘要；历史回填把规范地区加入草稿。** RegionCatalog目录名用于摘要展示；目录加载失败或编码失效显示“地区信息待确认”，通过重新查询与选择控件处理，不替换成“不限”而扩大下一次请求。旧历史省市范围缺字段才按不限。
- [x] **Step 5: 聚焦GREEN后完整Vitest、ESLint、tsc、build；记录现有游客/登录流程不变。**

### Task 6: 桌面/手机浏览器与真实Mock流程验收

**Files:** Create frontend/e2e/destination-region.spec.ts；Modify guest-recommendation.spec.ts、account-personal-data.spec.ts（仅需要的新覆盖）；测试fixture跨市归属只放测试或明确标记的Mock演示。

**Interfaces:** 已有匿名regions与recommendations；使用现有Playwright两个project和helpers，隔离data目录，不调用真实高德。

- [x] **Step 1: 布局RED先写入Task 4实现前或由执行者在Task 4开始时提前建立。** `region_popup_does_not_shift_preferences_or_submit` 比较打开/选择前后矩形y差≤1px；`region_input_has_one_focus_frame` 输入outline/border无独立粗框，外框聚焦可见；`region_selector_fits_sidebar_and_small_viewport` 桌面侧栏/390/320，浮层和按钮在可用宽度内；选择按钮有效宽高均≥44px。执行步骤时不得把已实现后的补测伪称RED。
- [x] **Step 2: Mock业务用例：后端Mock验证默认距离200跨省可推荐；浏览器验证指定江苏+杭州排除另一省；结果都在主出发地最大距离内；编辑到不同地区未提交时摘要不变；注册后显式重查保留地区、历史rerun返回工作区保留选择。** 全省选中覆盖城市、输入法Enter、Escape、外部点击、+N删除、目录重试各有检查。
- [x] **Step 3: 启动前检查8010/5180是否空闲，设置以下隔离变量，在frontend目录运行专项。** 不复用用户服务；若占用，先调查归属，不杀未知进程。

```powershell
$env:ROAMBOT_E2E_BROWSER_CHANNEL='chrome'
$env:ROAMBOT_E2E_BACKEND_PORT='8010'
$env:ROAMBOT_E2E_FRONTEND_PORT='5180'
$env:ROAMBOT_E2E_RUN_ID='destination-regions-20261008'
node node_modules/@playwright/test/cli.js test e2e/destination-region.spec.ts --workers=1
```

- [x] **Step 4: 专项通过后同隔离配置跑完整 `node node_modules/@playwright/test/cli.js test --workers=1`，保留准确人数/认证/历史/对比既有断言；仅更新明确改变的搜索契约。** 保存桌面/手机截图，人工查看无裁切、框中框或撑高；测试退出前仅清理本轮已确认进程。
- [x] **Step 5: 测试中目录版本过期/新接口422须可理解，不悄悄忽略地区；缩放、横屏、键盘弹出等真实手机行为注明尚未实机验收。**

### Task 7: 证据、契约和用户验收交接

**Files:** Modify SPEC.md、PLAN.md、docs/PROJECT_HANDOFF.md、docs/competition/AI_CODING_PROCESS.md；Create docs/competition/DESTINATION_REGION_PROGRESS.md。

- [x] **Step 1: 每轮记录真实RED/GREEN命令、计数、修正和限制，维护任务checkbox；不把旧42项通过或Demo通过当作新正式功能证据。**
- [x] **Step 2: 将规格新增字段/regions端点/预算及搜索空间语义追加到SPEC/PLAN，标记2026-10-08变更而非覆盖暑期证据。** 地区列表来源、范围不穷举和未知归属提示写入交接。
- [x] **Step 3: 最终 `.venv/Scripts/python.exe -m pytest backend/tests -q`、Ruff、frontend完整Vitest/ESLint/tsc/build、完整Playwright与 `git diff --check` 均确认实际退出码。** 文档改变无需重复完整套件；最终代码验证完成后只做文档校对。
- [x] **Step 4: 单人自审类型/缓存/旧JSON/匿名权限/分享白名单/已提交摘要/请求上限；明确非独立审查。** 不自称Live、全国景点覆盖或真实手机通过。
- [x] **Step 5: 汇报已改文件、测试证据与截图，说明前后端均需重启/刷新生效，停止等待用户验收；不自动重启用户服务，不push或部署。**

## 执行审阅点

2026-10-08：来源用途冲突已通过用户批准的独立目录调整解决。正式实现完成；实际RED/GREEN和限制见docs/competition/DESTINATION_REGION_PROGRESS.md。测试名称/拆分按实际框架采用等价断言，不强制照抄蓝图名。旧历史只读保留缺字段，显式rerun才补缺省；地区目录显式进入Git/Docker上下文和wheel清单。

沿用用户已指定的“由当前Codex连续执行、需要新增批准或完成时停止”的方式，不创建湛卢窗口或子智能体。不重复已批准界面设计，不提交/推送，等待用户验收。
