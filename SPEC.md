# SPEC: RoamBot

## 1. 问题陈述

短途出游常见困难不是“没有地方去”，而是用户很难同时判断未来天气、可接受距离和想看的风景类型。RoamBot 首先服务个人用户：当用户提出天气、距离和风景偏好要求后，程序帮助找到合适地点并给出推荐选项。多人多地汇合是额外功能，用于在有同行者时把目的地点到多个出发地的距离方差纳入推荐指数。

本项目构建一个 B 类应用项目：**RoamBot，一个天气感知的风景出行推荐助手**。用户输入主出发地址、最远可接受距离、风景类型与可出行日期范围；系统结合地点候选、天气预报和距离评分，输出按推荐度排序的地点与自然语言解释。用户也可以额外输入 1-2 个同行人地址，系统会将多个出发地到候选目的地的距离方差作为额外评分因素。项目最终目标是不预设城市范围，按用户输入的出发地与最大距离筛选候选地点；演示场景默认使用苏州，用户不填写城市时也以苏州作为默认城市。

RoamBot 同时支持两种使用模式：推荐模式与指定地点评估模式。推荐模式根据用户约束返回候选地点列表；指定地点评估模式允许用户直接输入目标地点，例如“金鸡湖”，系统只评估该地点在用户日期区间、天气和距离条件下的推荐指数，不返回其他地点列表。指定地点评估模式下不让用户填写风景类型，目标地点的风景标签由系统识别并用于解释。

本项目不是自主 agent。系统按固定流程调用地图、天气和 LLM；LLM 只负责基于结构化推荐结果生成解释文本，不自主选择工具、不循环决策、不执行外部动作。因此本项目适用 B 类应用要求，不触发 A 类 Coding Agent Harness 的额外要求。

## 2. 目标用户

- 想在未来可预测天气范围内安排短途风景出游的个人用户。
- 需要协调 2-3 个不同出发地的同行小组；这是增强场景，不是第一主线。
- 想根据天气决定是否看湖景、山景、城市夜景、朝霞/晚霞、公园等风景的人。

## 3. 用户故事

1. 作为个人用户，我希望输入出发地址和最远距离，以便系统推荐不超出可接受范围的风景地点。
2. 作为结伴出游组织者，我希望额外输入 1-2 个同行人地址，以便系统推荐对大家都相对公平的汇合地点。
3. 作为想看特定风景的人，我希望选择湖景、海景、古镇/历史街区、博物馆、公园/绿地/湿地、山地/徒步等类型，以便推荐结果符合我的偏好。
4. 作为担心天气影响出行的人，我希望系统查看我选择日期区间内每天的天气，以便判断某个地点是否在整个区间内都适合出行。
5. 作为决策者，我希望看到推荐理由、天气原因、距离原因和公平性说明，以便判断是否采纳推荐。
6. 作为新用户，我希望系统在外部 API key 缺失时给出明确提示，而不是直接崩溃。
7. 作为已经有目标地点的人，我希望直接输入地点名，例如“金鸡湖”，以便系统给出该地点是否适合我这次出行的推荐指数，而不是重新推荐地点列表。
8. 作为需要保留个人数据的用户，我希望使用用户名和密码注册、登录和退出，以便安全访问自己的收藏与历史记录。
9. 作为登录用户，我希望收藏感兴趣的地点，并在以后按新的日期和天气重新评估，以免依赖已经过期的推荐结果。
10. 作为登录用户，我希望查看过去成功查询的输入和结果摘要，并能重新查询，以便回顾原结论或获取当前天气下的新结论。
11. 作为登录用户，我希望把经过脱敏的推荐快照通过只读链接分享给他人，并能撤销链接，以便安全地交流推荐结论。
12. 作为首次访问的游客，我希望无需注册就能使用核心推荐和指定地点评估，以便先体验产品，再决定是否创建账户保存个人数据。
13. 作为 RoamBot 部署管理员，我希望在本机终端中安全录入、查看状态、更新和清除外部 API key，以便公开分发和部署时不泄露凭据。

## 4. 功能规约

### 4.1 输入与校验模块

输入：
- 使用模式：推荐模式或指定地点评估模式。
- 城市，可选；缺省时使用苏州。
- 主出发地址，必填。
- 额外出发地址，0-2 个。
- 指定目标地点，可选；仅在指定地点评估模式下必填。
- 最远可接受距离，单位 km。
- 风景类型，仅推荐模式可填写，可多选；支持湖景、海景、古镇/历史街区、博物馆、公园/绿地/湿地、山地/徒步。
- 多风景类型解释模式，仅推荐模式可填写：尽量覆盖全部偏好，或匹配任意偏好即可。
- 可出行日期范围，开始和结束日期均为闭区间；以 `Asia/Shanghai` 当地日期为准，允许今天至今天后第 6 天，共 7 个自然日。

行为：
- 校验地址非空、距离大于 0 且不超过 500 km、开始日期不早于今天、结束日期不早于开始日期，且结束日期不晚于今天后第 6 天。
- 城市为空时默认设为苏州。
- 限制总出发地址数量为 1-3 个。
- 指定地点评估模式下校验目标地点非空，并拒绝同时提交风景类型或多风景类型解释模式；推荐模式下目标地点可为空，风景类型必填。
- `weights` 整体可省略；一旦提供，`weather,distance,fairness,popularity` 四个有限数值字段必须全部存在、每项在 0-100、总和大于 0，额外字段拒绝。只有一个出发地时 `fairness` 必须为 0；两个或三个出发地时四项均可由用户设置。权重总和不要求调用方预先等于 100，后端按总和归一化。

输出：
- 结构化请求对象，或明确错误信息。

### 4.2 地址解析模块

输入：
- 地址文本列表。

行为：
- 通过高德地图 Web 服务 API 将地址解析为经纬度；测试环境使用 mock 地理编码器。

输出：
- `Origin` 列表：标签、原始地址、经纬度。

错误处理：
- 单个地址无法解析时，返回可读错误，要求用户修改地址。

### 4.3 候选地点模块

输入：
- 城市，默认苏州。
- 主出发点经纬度。
- 风景类型。
- 最远距离。

行为：
- 正常模式从高德地图 Web 服务 API 的 POI/周边检索能力获取地点；检索失败时只可使用仍在有效期内的同范围缓存，并在结果中标明缓存来源。
- 内置苏州候选数据仅在管理员显式启用演示模式时可用，WebUI 必须持续标注“演示数据”。正式模式不得用内置数据冒充高德结果；无有效缓存时返回地点检索服务暂时不可用。
- 候选地点优先覆盖苏州及周边可演示地点，同时保留按用户输入城市与距离扩展的设计。
- 将高德返回的 POI `type` / `typecode` 映射为 RoamBot 内部风景标签，并用地点名称关键词补充湖、海滩、古镇、博物馆、湿地、公园、山地和步道等细分语义。
- 支持对少量知名地点配置可审查的人工标签修正；同一地点可以拥有多个风景标签。无法可靠识别的地点标记为未知，不能由 LLM 临时猜测分类。
- POI 分类映射作为独立配置维护，业务代码不散落硬编码；映射变更必须有对应测试。
- 苏州默认演示优先覆盖湖景、古镇/历史街区、博物馆、公园/绿地/湿地、山地/徒步；海景作为跨城市或较远距离扩展类型保留。
- 过滤明显超出最远距离的地点。
- 给地点打基础风景匹配分。

输出：
- 候选 `Destination` 列表。

### 4.3.1 指定地点评估模块

输入：
- 指定目标地点名称。
- 城市，默认苏州。
- 主出发点经纬度。
- 额外出发点，经纬度可选。
- 日期区间。

行为：
- 将目标地点解析为 `Destination`。
- 获取该地点的风景标签、热度/推荐度和天气数据。
- 如需展示建议游玩时长，系统按地点类型、热度/推荐度和内部规则估算；不把地图 API 视为稳定的游玩时长数据源。
- 使用与推荐模式一致的天气、距离、多人方差、热度评分规则计算该地点推荐指数。
- 根据系统识别出的地点风景标签解释该地点本身适合的游玩类型；不要求用户手动指定风景类型。
- 不执行候选地点列表排序，也不返回其他推荐地点。

输出：
- `PlaceEvaluationResponse`：指定地点、日期区间综合推荐度、每日旅游适宜度、距离/多人方差信息、热度/推荐度、原因与风险提示。

### 4.4 天气评估模块

输入：
- 候选地点经纬度。
- 可出行日期范围。

行为：
- 通过 QWeather（和风天气）每日天气预报 API 查询用户所选日期范围内的天气；日期范围默认限制在未来一周内，以避免远期天气预报不准。
- 即使天气供应商支持超过 7 天的预报，RoamBot 产品层仍只把未来 7 天作为默认可信窗口。
- 计算每个地点在所选日期范围内每天的天气适宜度，形成每日分数序列。
- 计算该地点在整个日期区间内的综合天气适配分，用于总体推荐排序。公式为 `每日适宜度平均分 × 70% + 最差一天适宜度 × 30%`，结果限制在 0-100 分，以体现“这 n 天整体都适合”，而不是让平均值掩盖某个明显不适合的日期。
- 每日适宜度需要保留可解释原因，例如天气状况、温度、降雨、风力、能见度与用户选择风景类型之间的关系。
- 当用户选择多个风景类型时，两种模式都要求候选至少匹配一个所选类型。`ANY` 模式只要匹配一个就不扣覆盖分；`COVER_ALL` 模式按 `20 × (1 - 已匹配类型数 / 所选类型数)` 从加权总分中扣除。RoamBot 不安排具体日程，不输出“第几天玩什么”，只说明偏好覆盖情况。
- 对山地/徒步、公园/绿地/湿地等户外类型，额外考虑降雨、高温、风力和能见度。
- 对博物馆等室内类型，恶劣天气扣分较低，可作为雨天备选。

V1 每日天气评分固定如下，所有扣分可累加，最终限制在 0-100：

- 初始分为 100。单位固定为摄氏度、毫米、公里/小时和公里；湿度单位为百分比，紫外线使用 QWeather 指数。
- 降水量 `>10mm`：户外扣 60，纯室内扣 35；`>1mm`：户外扣 35，纯室内扣 15；`>0mm`：户外扣 10，纯室内扣 5。
- 最高温 `>35°C` 或最低温 `<0°C` 扣 40；否则最高温 `>32°C` 或最低温 `<10°C` 扣 25；否则最高温 `>28°C` 或最低温 `<18°C` 扣 10。
- 风速 `>40km/h`：户外扣 40，纯室内扣 20；`>30km/h`：户外扣 25，纯室内扣 10；`>20km/h` 时户外扣 10。
- 能见度 `<2km` 扣 30，`<5km` 扣 15，`<10km` 扣 5；户外场景紫外线指数 `>8` 再扣 10。
- 湖景、海景、古镇/历史街区、公园/绿地/湿地、山地/徒步均按户外处理；只有博物馆标签时按纯室内处理；同时含室内和户外标签时按户外处理；标签未知时采用较保守的户外规则，但仍明确标注“风景类型未知”。
- `condition`、湿度和风力等级用于展示与解释；V1 数值扣分使用降水量、温度、风速、能见度和紫外线，不对湿度重复扣分。
- 用于评分的数值字段缺失或无效时，该地点不能生成完整天气分。推荐模式排除该候选并提示部分天气不可用；所有剩余候选都失败时整次请求失败且不写历史。指定地点评估缺失完整天气时请求失败。
- 指定地点评估使用系统识别出的全部地点标签套用上述规则，不计算用户风景偏好覆盖惩罚；未知标签使用保守规则，不交给 LLM 猜测。

输出：
- 每个地点在所选日期区间内的每日旅游适宜度。
- 每日旅游适宜度的解释文本。
- 每个地点面向整个日期区间的综合天气适配分。
- 风景偏好覆盖说明：已覆盖、未覆盖、部分覆盖的风景类型。

### 4.5 多人汇合评分模块

输入：
- 1-3 个出发点。
- 候选地点。

行为：
- 估算每个出发点到候选地点的距离或耗时。
- 计算平均距离、最大距离、距离方差或标准差。
- 多人公平性按距离差异/方差定义：各出发点到目的地的距离越接近，公平性分越高。
- 平均距离和最大距离用于结果解释；是否整体距离较近由独立的距离分处理，不混入公平性主定义。
- 距离分的输入为所有出发地距离的算术平均值；单人时即主出发地距离。固定公式为 `clamp2(100 × (1 - 平均距离km / 用户最大距离km))`。
- 多人方差使用总体方差 `pvariance`，标准差为其平方根；固定公平性公式为 `clamp2(100 × (1 - 总体标准差km / 用户最大距离km))`。只有一个出发地时公平性固定为 100，但其权重必须为 0。

输出：
- `GroupAccessibilityScore`。

### 4.6 推荐排序模块

输入：
- 候选地点。
- 天气分。
- 距离分。
- 公平性分。
- 景区热度/推荐度分。
- 用户自定义权重；可选项包括天气适配、距离远近、多人距离方差、景区热度/推荐度。

行为：
- 先执行硬过滤：候选至少匹配一个用户选择的风景类型，且主出发地到地点的距离不得超过用户填写的最大距离。
- 若硬过滤后无结果，常规推荐窗口返回“规定范围内无检索结果”；扩展推荐窗口返回最近距离的符合风景要求景点，以及最热门的符合风景要求景点。
- 景区热度分使用合并后的高德一基 `provider_rank`，固定公式为 `clamp2(100 - 4 × (provider_rank - 1) + local_bonus)`；rank 1 为 100，rank 25 为 4。`local_bonus` 只能来自按 provider ID 建立、进入版本控制并有测试的 `POPULARITY_BONUS_BY_PROVIDER_ID`，每项限制在 -20 到 20；V1 初始映射为空，不对任何地点暗中加分。结果必须标为“RoamBot 热度估算”，不得表示为高德官方评分。
- 单人默认权重为天气适配 40%、距离远近 30%、景区热度/推荐度 30%。
- 多人多地时默认权重为天气适配 40%、多人距离方差 40%、景区热度/推荐度 20%、距离远近 0%。
- 用户可调整权重；前端使用一个分段滑块条自动归一化。单人时显示两个滑块、三个区域：天气适配、距离远近、景区热度/推荐度；多人时显示三个滑块、四个区域：天气适配、距离远近、多人距离方差、景区热度/推荐度。
- 归一化权重为 `wi = 输入权重i / 四项权重总和`。推荐模式先计算 `weighted = 天气分×w_weather + 距离分×w_distance + 公平性分×w_fairness + 热度分×w_popularity`；`ANY` 模式的覆盖惩罚固定为 0，`COVER_ALL` 为 `20 × (1 - 匹配类型数 / 选择类型数)`；总分为 `clamp2(weighted - 覆盖惩罚)`。风景匹配不是第五个权重，只用于硬过滤与覆盖惩罚。
- 指定地点评估复用同一四项加权公式但覆盖惩罚固定为 0；不执行候选列表排序。
- `clamp2(x)` 定义为先限制到 0-100，再使用 Python `round(x, 2)`。每日天气、区间天气、距离、公平性、热度和最终总分分别在各自函数出口舍入两位；归一化权重保持完整浮点精度。API 返回两位精度数值，WebUI 显示一位小数。
- 推荐结果按总分降序；总分相同按主出发地距离升序；仍相同按 Unicode NFKC 规范化并去除首尾空白后的地点名升序；仍相同按 `provider_id` 升序。最多返回五项。

输出：
- 推荐结果列表，包含地点、日期区间综合推荐度、每日旅游适宜度、天气摘要、距离信息、景区热度/推荐度、推荐分。
- 无结果状态与扩展推荐结果。

### 4.7 LLM 解释模块

输入：
- 结构化推荐结果。
- LLM 配置，可选，包括 `base_url`、`api_key`、`model`。

行为：
- 使用 OpenAI-compatible provider 抽象调用 LLM，默认演示模型为学校额度平台的 DeepSeek V4 Flash。
- LLM 只根据结构化推荐结果生成简短、可读、可比较的推荐理由，不参与地点筛选、评分或工具调用。
- 未配置 LLM key 或 LLM 调用失败时，使用模板解释降级，不影响推荐主流程。
- 测试与 CI 环境使用 mock/template，不调用真实 LLM，不消耗 token。

输出：
- 每个推荐地点的自然语言理由与注意事项。

### 4.8 WebUI 模块

输入：
- 用户表单。

行为：
- 首屏直接展示可操作的推荐工具，不增加营销式落地页；顶部导航提供推荐、收藏、历史和账户入口。
- 桌面端输入区与结果区左右排列，手机端改为上下排列；使用分段控件切换推荐模式与指定地点评估模式。
- 表单初始值固定为：推荐模式、城市“苏州”、空主出发地、无同行人、最大距离 50 km、开始与结束日期均为 `Asia/Shanghai` 明天、未选择风景类型、偏好匹配 `any`、空目标地点。指定地点评估沿用同一城市/地址/距离/日期默认值并使用同一单人或多人权重规则。
- 模式分段控件的可访问名称固定为“推荐地点”和“评估指定地点”。字段标签固定为“城市”“主出发地”“同行人 1 出发地”“同行人 2 出发地”“最大距离（km）”“开始日期”“结束日期”“目标地点”；分组名称固定为“风景类型”“偏好匹配”“推荐权重”。提交按钮固定为“开始推荐”或“评估这个地点”。
- 模式切换时在本次页面会话内保留两个模式各自已输入的可见字段，但提交序列化必须彻底省略当前模式的隐藏字段：推荐请求不含 `target_place`，指定地点评估请求不含 `scenery_types` 和 `scenery_match_mode`。风景类型数组按用户首次勾选顺序保存；取消会移除，再次勾选会追加到末尾，高德检索沿用该顺序。
- 权重控件内部使用总和恒为 100 的整数百分比。单人为天气/距离/热度三段，默认 `40/30/30`；多人为天气/距离/公平性/热度四段，默认 `40/0/40/20`。每个分隔手柄以 5 个百分点为步长移动，只改变其左右相邻两段，允许某段为 0；重叠手柄必须保持独立键盘焦点和可访问名称。添加或删除同行人导致单人/多人状态变化时恢复对应默认权重；模式切换但出发地数量不变时保留该模式上次权重。指定地点评估也显示相同权重控件。
- 前端在提交前执行与后端一致的结构校验并将错误放在对应字段旁：空主出发地“请输入主出发地”，空同行人行“请输入同行人出发地”，非正或超过 500 km“最大距离必须在 0 到 500 km 之间”，日期错误“日期必须在今天至未来第 6 天内”，结束早于开始“结束日期不能早于开始日期”，推荐模式未选风景“请至少选择一种风景类型”，评估模式目标为空“请输入目标地点”。后端 `error.fields` 仍是最终依据并覆盖同字段客户端错误。
- 展示输入区、推荐结果卡片、配置缺失提示，以及实时结果、缓存结果、演示数据、部分降级和服务不可用等来源/状态标记。
- 推荐结果卡片展示地点、距离、所选日期区间内的每日天气、分项评分、总体推荐度和推荐理由。
- 不嵌入地图，不绘制路线，不提供导航或具体日程安排。
- 游客无需登录即可提交推荐模式或指定地点评估请求；登录提示不得阻断核心查询。
- 当前布局是 V1 实现基线；开发阶段允许根据桌面、手机截图和用户实际体验调整视觉与交互，但不得在前端复制评分规则或改变已确认的数据语义。

输出：
- 可访问 Web 页面。

### 4.9 用户账户模块

输入：
- 注册时的用户名和密码。
- 登录时的用户名和密码。
- 退出请求。

行为：
- 允许用户使用唯一用户名和密码注册本地账户。
- 密码不得明文保存，只保存由成熟密码哈希库生成的安全哈希。
- 登录成功后创建安全会话；退出时使当前会话失效。
- 需要访问收藏和历史记录的接口必须先验证登录状态。
- 核心推荐和指定地点评估不要求登录；游客查询不创建个人历史记录。
- 不实现邮箱验证、找回密码或第三方登录。
- V1 不收集手机号，不发送短信验证码，也不接入图片、滑块或云验证码服务。
- 用户名重复时返回明确错误；登录失败时不泄露用户名是否存在。

输出：
- 当前登录状态和非敏感用户信息。
- 注册、登录或退出的成功结果，或可读错误。

### 4.10 地点收藏模块

输入：
- 当前登录用户。
- 目标地点标识。

行为：
- 登录用户可添加收藏、取消收藏和查看自己的收藏地点列表。
- 同一用户对同一地点最多保留一条收藏记录；重复添加按幂等成功处理。
- 收藏只保存地点关联和收藏时间，不保存当时的天气、评分或推荐理由。
- 用户从收藏列表重新打开地点时，系统要求新的出发地与日期，并按当前可用天气重新执行指定地点评估。
- 未登录用户不能读取或修改收藏；用户不能访问其他用户的收藏。

输出：
- 当前用户的收藏地点列表。
- 添加或取消收藏的结果。

### 4.11 查询历史模块

输入：
- 当前登录用户。
- 一次成功完成的推荐或指定地点评估及其结构化结果。

行为：
- 仅在查询形成完整可返回结果后自动创建历史记录；有效缓存、演示模式、直线距离估算、部分候选天气被排除或 LLM 模板解释仍属于带来源说明的成功结果，应记录历史。输入非法、全部天气失败、地理编码失败、POI 服务无缓存且不可用或其他未得到结果的请求不记录。
- 历史记录保存查询输入、生成时间和当时的结构化结果摘要，不保存 API key、密码、会话标识或完整外部 API 响应。
- 历史详情必须标明这是生成时的快照，旧天气和旧评分不会自动更新。
- 用户可按时间倒序查看自己的历史记录，不能访问其他用户的历史。
- 用户点击“重新查询”时复用历史输入，使用当前可用天气重新计算，并把新结果保存为一条新的历史记录；原历史保持不变。
- 用户可删除一条自己的历史记录，也可清空自己的全部历史记录。
- 删除历史记录时，其关联的公开分享链接必须同时失效；收藏地点不受影响。
- 当前不实现历史数据导出或账户注销。

输出：
- 当前用户的历史记录列表与历史详情。
- 重新查询产生的新推荐或指定地点评估。

### 4.12 只读分享模块

输入：
- 当前登录用户。
- 该用户拥有的一条历史记录。

行为：
- 登录用户可为自己的历史快照创建不可猜测的只读分享链接，也可撤销自己创建的链接。
- 分享链接的公开页面无需登录，但只能读取已脱敏的结果快照。
- 公开内容包含地点、城市、日期、天气摘要、评分、推荐理由、同行人数和生成时间；删除主出发地址与全部同行地址正文，不做部分遮盖，不得包含用户名、用户标识、API key、会话标识或其他私人数据。
- 分享令牌只在创建时返回明文，数据库只保存令牌哈希；已撤销或不存在的链接返回统一的不可用状态。
- 分享页面明确标注内容是生成时的历史快照，不自动刷新天气或评分。
- 关联历史被删除后，分享链接必须与主动撤销时一样立即不可用。
- 每次 `POST /history/{history_id}/share` 都在同一事务中撤销该用户该历史的旧活动分享，并生成新的 32 字节 URL-safe token；因此旧链接立即失效，成功始终返回 201，不尝试从哈希恢复或复用旧明文 token。
- 不实现社交动态、评论、关注、组队或微信专用分享接口。

输出：
- 可复制的只读分享 URL。
- 脱敏的公开快照页面，或链接不可用提示。

### 4.13 加密凭据管理模块

输入：
- 本机管理员终端中的初始化、状态、更新、清除、解锁或紧急重置命令。
- 隐藏输入的主密码与高德、QWeather、LLM key。

行为：
- 使用成熟密码学库提供的口令派生与认证加密能力，不自行实现加密算法。
- 首次运行由本机管理员在终端中设置主密码并隐藏录入 API key；磁盘只保存加密凭据库，不保存主密码或明文 key。
- 支持查看各服务“已配置/未配置”状态、更新和清除 key；状态输出不得回显 key。
- `credentials status` 在凭据库不存在时直接报告三项均未配置；凭据库存在时必须隐藏提示当前主密码、完成一次认证解密后只输出三项布尔状态，不在磁盘另存可被篡改的明文状态元数据。错误主密码与畸形库统一失败且不返回部分状态。
- 正常更新和清除必须验证当前主密码。
- 忘记主密码时，只能由拥有 Docker 主机和数据卷权限的管理员在本机终端执行紧急重置，并输入不可逆确认。重置只删除旧加密凭据库，不删除 SQLite 中的账户、收藏和历史；旧供应商 key 仍需在供应商控制台吊销或重新录入。
- 应用解锁后只在进程内存中保留明文 key；日志、错误信息、历史记录和状态接口必须脱敏。
- 普通 WebUI 与公开 API 不提供初始化、更新、清除、解锁或重置入口，只能显示相关服务当前是否可用。
- `.env` 只允许保存非敏感配置，例如服务地址、模型名和数据目录；真实 API key 和主密码不得写入 `.env`、命令行参数、源码、镜像或 Git。
- 本地交互式运行通过隐藏终端输入解锁；无人值守部署可从部署平台密钥管理服务挂载的只读 secret 文件读取主密码，不接受命令行明文参数。

输出：
- 加密凭据库文件。
- 不含明文 key 的配置状态或操作结果。

## 5. 非功能需求

- 性能：一次推荐请求在正常外部 API 响应下应在 10 秒内返回。
- 持久化：账户、会话、收藏、历史和分享链接使用 SQLite 保存；Docker 运行时数据库文件必须位于挂载数据卷中，容器重建不得默认清空用户数据。
- 可用性：外部 API 失败时应返回降级提示，不显示堆栈错误；缓存和演示数据来源必须透明，正式模式不得静默使用演示数据。
- 可测试性：评分、排序、输入校验、LLM 解释封装必须可用 mock 测试。
- 可观测性：后端记录请求阶段、外部 API 成败、降级原因；不得记录真实 API key。
- 安全：凭据不得硬编码、不得提交 Git、不得输出到日志；真实 API key 必须存入带主密码的加密凭据库；用户密码不得明文存储或写入日志，会话标识不得通过页面内容泄露；公开分享必须使用不可猜测令牌并对快照脱敏。

## 6. 凭据威胁模型与对策

凭据包括地图 API key、天气 API key、LLM API key。

威胁：
- key 被硬编码进源码、写入 `.env`、提交进 Git 或打入 Docker 镜像。
- 日志、错误信息、终端 history、历史记录或状态接口泄露 key。
- 公开 WebUI 暴露凭据管理能力，被普通用户清除或替换 key。
- 加密凭据库被复制、删除或篡改。
- 管理员忘记主密码，无法解密原凭据库。

对策：
- 真实 key 只写入带主密码的加密凭据库；`.env.example` 只列非敏感配置，`.env` 加入 `.gitignore` 并在 README 说明其明文风险。
- 初始化、更新、清除和重置只允许从本机管理员终端执行；公开 WebUI 只显示“服务可用/不可用”。
- 主密码和 key 使用隐藏输入，不作为命令行参数，不写入日志；解密后的 key 只驻留进程内存。
- Docker 镜像不包含凭据库或真实 key；凭据库保存在受限权限的数据卷中并允许备份。
- 正常清除需要当前主密码；紧急重置需要 Docker 主机权限和不可逆确认，且不影响 SQLite 用户数据。
- 无人值守部署仅允许通过部署平台密钥管理服务挂载的只读 secret 文件提供主密码。
- 测试与 CI 使用临时凭据库和假 key，不要求任何真实外部凭据。

## 7. 系统架构

React + TypeScript 前端通过 JSON API 调用 FastAPI 后端。

- 开发环境：Vite 前端开发服务器与 FastAPI 后端分别运行，Vite 将 `/api` 请求代理到后端。
- 生产环境：先构建 React 静态产物，再由同一个 Docker 镜像和同一域名提供前端页面与 `/api` 接口；不拆成两个云服务。
- 源码边界：`frontend/` 负责页面、交互与客户端状态；`backend/` 负责认证、推荐、外部 API、SQLite、凭据和授权。业务评分规则不得复制到前端。
- API 使用 `/api/v1` 前缀。推荐与指定地点评估使用独立入口并复用同一领域服务；收藏、历史、重新查询和分享管理必须在后端验证资源归属。
- 匿名分享只通过公开只读接口返回脱敏历史快照。统一错误响应固定为 `{"error":{"code":str,"message":str,"fields":[{"path":str,"message":str}]}}`；无字段错误时 `fields` 为空数组，不返回堆栈、内部路径、原始 provider 响应或敏感数据。
- 登录使用服务端固定 24 小时、不可滑动续期的会话。浏览器 Cookie 固定名为 `roambot_session`，属性为 `HttpOnly`、`SameSite=Lax`、`Path=/`、`Max-Age=86400`，生产环境再启用 `Secure`；退出时用相同路径和安全属性清除。Cookie 只包含不透明 session token，JSON 永不返回该 token。
- 注册和登录请求体均固定为 `{"username":str,"password":str}`。注册成功即自动登录：注册返回 201、登录返回 200，成功响应均为 `{"user":{"username":"alice_01"},"csrf_token":"<opaque>"}` 并设置会话 Cookie。`GET /auth/me` 对有效会话返回同一 JSON 形状；退出返回 204 空响应。所有认证成功响应增加 `Cache-Control: no-store`。
- 数据库每个会话只保存 session token 与 CSRF token 的 SHA-256 哈希，不保存可恢复的 CSRF 明文。注册和登录生成初始 CSRF；每次成功调用 `GET /auth/me` 都在同一数据库事务中生成新 token、替换 `csrf_hash`，并只在本次响应返回新明文，因此旧 CSRF 立即失效。会话本身的 24 小时到期时间不因 `/auth/me` 轮换而延长。
- 前端只在模块内存保存最新 CSRF，并通过 `X-CSRF-Token` 发送，不写入 localStorage、sessionStorage 或其他浏览器持久化存储。mutation 若收到 403 `csrf_invalid`，前端至多调用一次 `/auth/me` 刷新 token，并只重试原 mutation 一次；CSRF 校验必须发生在任何业务写入和 provider 调用之前。刷新返回 401 时清空本地认证状态，不再重试。
- 注册和登录不要求 CSRF；游客核心查询也不要求。已有有效会话时，退出、收藏修改、历史重新查询/删除/清空、分享创建/撤销，以及会自动写历史的两个核心 POST 都必须校验 CSRF。只读 GET 除 `/auth/me` 的显式 token 轮换外不修改状态。

固定路由与成功状态码：

| 方法与路径 | 成功状态 | 登录/CSRF |
| --- | ---: | --- |
| `GET /api/v1/health` | 200 | 无 |
| `POST /api/v1/recommendations` | 200 | 游客无；已有会话时需要 CSRF |
| `POST /api/v1/place-evaluations` | 200 | 游客无；已有会话时需要 CSRF |
| `POST /api/v1/auth/register` | 201 | 无 |
| `POST /api/v1/auth/login` | 200 | 无 |
| `POST /api/v1/auth/logout` | 204 | 登录 + CSRF |
| `GET /api/v1/auth/me` | 200 | 有效会话；游客返回 401 |
| `GET /api/v1/favorites` | 200 | 登录 |
| `POST /api/v1/favorites` | 201；重复收藏为 200 | 登录 + CSRF |
| `DELETE /api/v1/favorites/{favorite_id}` | 204 | 登录 + CSRF |
| `GET /api/v1/history` | 200 | 登录 |
| `GET /api/v1/history/{history_id}` | 200 | 登录 |
| `POST /api/v1/history/{history_id}/rerun` | 200 | 登录 + CSRF |
| `DELETE /api/v1/history/{history_id}` | 204 | 登录 + CSRF |
| `DELETE /api/v1/history` | 204 | 登录 + CSRF |
| `POST /api/v1/history/{history_id}/share` | 201 | 登录 + CSRF |
| `DELETE /api/v1/shares/{share_id}` | 204 | 登录 + CSRF |
| `GET /api/v1/public/shares/{token}` | 200 | 无 |

分享接口成功 JSON 固定如下：

- 创建：`{"share":{"id":"<uuid>","history_id":"<uuid>","url":"/share/<token>","created_at":"<UTC RFC3339>"}}`。明文 token 只作为相对 Web URL 的最后一段返回这一次，不另设 token 字段；前端用当前 origin 生成可复制绝对 URL。数据库只存 SHA-256。
- 撤销：204 空响应。非所有者或不存在的私有 share ID 返回 404 `resource_not_found`。
- 公开读取：`{"snapshot":{"mode":"recommendation|place_evaluation","city":"苏州","companion_count":0,"start_date":"YYYY-MM-DD","end_date":"YYYY-MM-DD","items":[...],"generated_at":"<UTC RFC3339>"}}`。
- `snapshot.items[]` 只含 `destination:{name,address,city,scenery_tags}`、`weather:list[DailyWeather]`、`daily_suitability:list[DailySuitability]`、`score:ScoreBreakdown`、`explanation`；不含主/同行地址、距离明细、坐标、provider/type code、username/user ID、history/share ID、Cookie/CSRF 或任何凭据。公开 token 不存在、已撤销或历史已删除均返回相同 404 `share_unavailable`。

核心接口没有符合条件的候选时仍返回 200、空 `items` 和稳定提示，不用 404 表示“无推荐”。固定错误映射：输入结构错误和日期/权重错误为 422 `validation_error`；出发地址无法解析为 422 `origin_not_found`；指定目标地点不存在为 404 `place_not_found`；未登录为 401 `authentication_required`；错误登录凭据为 401 `invalid_credentials`；重复用户名为 409 `username_taken`；CSRF 缺失或错误为 403 `csrf_invalid`；无权或不存在的私有资源统一为 404 `resource_not_found`；撤销、不存在或因历史删除失效的公开分享统一为 404 `share_unavailable`；外部服务或必要配置不可用为 503 `provider_unavailable`；未知后端错误为 500 `unexpected_error`。

登录用户的推荐结果在完整响应形成后，以短 SQLite 事务写入历史；事务提交成功后才返回 200，失败则回滚并返回 500，不保留半条历史。外部 API 调用不得放在数据库事务中。游客路径不启动历史写事务。

生产静态目录固定为 `frontend/dist`。`/assets/*` 只返回真实构建文件，缺失资源返回 404；不带文件扩展名且不以 `/api` 开头的前端路由回退到 `index.html`；任何 `/api/v1/*` 都保持 JSON 响应，不得被 SPA 回退捕获。

静态目录通过 `create_app(frontend_dist: Path | None = None)` 注入：开发阶段为 `None` 时不挂静态页面，Vite 单独提供 WebUI，后端 API 仍正常；测试使用临时目录创建最小 `index.html/assets/app.js`，不依赖真实 `frontend/dist` 或先运行前端 build；生产 entrypoint 必须传入存在且含 `index.html` 的 `/app/frontend/dist`，否则以配置错误退出。挂载顺序固定为 API/router、真实 `/assets`、最后无后缀 SPA fallback；带文件后缀的其他缺失路径返回 404。

推荐模式下后端按固定流程执行：
1. 校验输入。
2. 解析出发地址。
3. 获取候选地点。
4. 获取用户选择日期区间内的天气。
5. 计算天气分、风景分、距离分；如有额外出发地，再计算多人距离方差分。
6. 排序。
7. 调用 LLM 生成解释。
8. 返回结果给 WebUI。

指定地点评估模式下后端按固定流程执行：
1. 校验输入。
2. 解析出发地址和目标地点。
3. 获取目标地点天气、热度和标签。
4. 计算日期区间每日适宜度和综合推荐指数。
5. 调用 LLM 生成解释。
6. 返回单地点评估结果给 WebUI。

外部依赖：
- 凭据服务：本地加密凭据库；交互运行从隐藏终端输入解锁，无人值守部署可由平台 secret 文件解锁。
- 地图服务：主选高德地图 Web 服务 API，用于地理编码、POI/周边景点检索、地点分类与距离估算；百度地图作为备选调研对象；测试环境使用本地 mock。高德只作为后台数据服务，前端不展示地图、路线或导航。
- 高德固定主机为 `https://restapi.amap.com`，所有坐标均按 GCJ-02 的 `经度,纬度`、最多六位小数传输。地理编码只调用 `GET /v3/geocode/geo`，参数为 `key,address,city,output=json`；POI 只调用 `GET /v5/place/around` 或 `GET /v5/place/text`；距离只调用 `GET /v3/distance`。V3/V5 顶层响应仅在 `status="1"` 且 `infocode="10000"` 时视为成功，否则映射为不含 key、完整 URL 或原始响应的 `ProviderError`。
- 推荐检索的六个固定关键词为：湖景=`湖泊景区`、海景=`海滩`、古镇=`古镇`、博物馆=`博物馆`、公园=`公园`、山地=`山岳景区`。按用户选择顺序，每个去重类型最多请求一次，总数最多六次。最大距离不超过 50 km 时使用 around，参数固定为 `key,keywords,location,radius,sortrule=weight,region,city_limit=true,show_fields=business,page_size=25,page_num=1,output=json`；`radius` 为四舍五入后的米数并限制在 1-50000。最大距离超过 50 km 时使用 text，参数固定为 `key,keywords,region,city_limit=true,show_fields=business,page_size=25,page_num=1,output=json`，随后按本地 haversine 对最大距离做粗过滤。只取第一页，合并候选最多 25 个。
- 指定地点解析使用同一 text 端点和参数，其中 `keywords` 为用户地点名；先选择规范化名称完全相等的 POI，否则选择 provider 返回顺序第一项。有效空列表映射 `not_found`，不是 provider outage。
- POI 合并顺序固定为“用户选择类型顺序，再按每次响应中的 provider 顺序”。非空 POI `id` 是首选去重键；缺失 ID 但其余字段有效时，以“规范化名称 + 经度六位 + 纬度六位”为去重键，并生成 `amap:synthetic:` 加该键 SHA-256 前 16 个十六进制字符的稳定 ID。`name,location,type,typecode` 任一缺失或坐标非法时跳过该 POI；若声明 `count>0` 但所有 POI 都畸形，则返回 `bad_response`。`address` 可为空，`cityname` 缺失时使用请求城市；可选 rating 不参与跨类别热度分，合并顺序生成一基 `provider_rank`。
- 距离请求参数固定为 `key,origins,destination,type=1,output=json`，`origins` 按输入顺序以 `|` 连接，最多 100 个；RoamBot 业务层仍最多三个出发地。每个结果必须能解析 `distance` 米和 `duration` 秒，转换为公里和分钟并保持输入顺序；结果数量不等、结果级错误或字段畸形均为 `bad_response`。只使用距离与耗时，不请求路线几何、道路步骤或导航。
- 高德适配器自动测试固定使用 `geocode_success.json`、`poi_around_success.json`、`poi_text_success.json` 和 `distance_success.json` 四个合成 fixture，通过 `httpx.MockTransport` 断言完整路径与参数，禁止联网。
- 天气服务：主选 QWeather（和风天气）每日天气预报 API，用于按地点经纬度查询未来天气；测试环境使用本地 mock。V1 使用官方仍支持的 API KEY Header 认证，不实现 JWT 签名；官方契约参考 [每日天气预报](https://dev.qweather.com/docs/api/weather/weather-daily-forecast/) 与 [身份认证](https://dev.qweather.com/docs/configuration/authentication/)。
- QWeather 账户 API Host 作为非秘密配置字段 `qweather_api_host`，输入必须是 `https://`、无用户名/密码/端口/路径/查询/片段且主机名以 `.qweatherapi.com` 结尾；去除末尾 `/` 后作为 base URL，拒绝旧公共 host。API key 只来自解锁后的凭据库。
- `QWeatherProvider(http: ProviderHttpClient, api_key: str, today: Callable[[], date])` 实现同步方法 `daily(coordinate: Coordinate, start: date, end: date) -> list[DailyWeather]`。只执行一次 `GET /v7/weather/7d`，query 固定为 `location={longitude:.2f},{latitude:.2f}&lang=zh&unit=m`，经度在前、纬度在后并保留两位尾零；key 只放 `X-QW-Api-Key` Header，URL/query 不含 key 或 token。`httpx` 负责自动解压 gzip。
- V1 将高德 GCJ-02 坐标按原值四舍五入到两位后传给 QWeather，不做未经官方契约要求的坐标转换；两位小数约为公里级定位，人工真实 smoke 需核对苏州地点返回城市与天气是否合理。若后续证据表明账户接口要求其他坐标系，再作为单独、带回归测试的适配变更。
- QWeather 仅在顶层 `code="200"` 时成功。`daily` 中每项先读取 `fxDate`；重复日期或非法日期为 `bad_response`，请求区间外条目除日期外可忽略。请求区间内每一天必须且只能有一项，并要求 `tempMin,tempMax,textDay,textNight,windSpeedDay,windSpeedNight,humidity,precip,uvIndex,vis` 均存在且可解析为有限值；`tempMin<=tempMax`，降水/风速/能见度/UV 非负，湿度在 0-100。日间夜间文案相同则使用一次，不同则使用“`textDay`转`textNight`”；评分风速取日间与夜间数值较大者。结果按日期升序，只返回闭区间日期。
- 请求开始早于 `today()`、结束早于开始或结束晚于 `today()+6` 时，在 HTTP 前返回 `ProviderError("forecast_unavailable","所选日期超出七日天气预报范围")`。缺少任一请求日期同样为 `forecast_unavailable`；顶层业务 code 非 200 为 `unavailable`；请求日期内字段缺失、重复或畸形为 `bad_response`。错误和日志不得含 key、完整 URL 或原始响应。自动测试固定使用 `backend/tests/fixtures/qweather/weather_7d_success.json` 与 `httpx.MockTransport`，禁止联网。
- LLM 服务：OpenAI-compatible provider 抽象；默认演示模型为学校额度平台的 DeepSeek V4 Flash；测试与 CI 使用 mock/template。

成本控制：
- 测试与 CI 不调用真实地图、天气或 LLM API。
- 推荐模式先对高德 POI 结果或同范围有效缓存候选执行坐标粗距离筛选：按主出发地到候选的 haversine 距离排除超过 `max_distance_km` 的项，保留既有“类型选择顺序 + provider 顺序”，再截取前五项。只对这五项逐候选调用一次高德多起点距离和一次 QWeather；精确主出发地距离仍超限的项直接排除，不再从第六项回填。因此单请求距离和天气调用都最多五次。
- 高德距离调用失败时，对该候选的每个出发地使用 haversine 公里数（四舍五入到两位）生成 `DistanceEstimate(distance_km, duration_minutes=None, estimated=True)`；这属于可返回的降级结果。天气调用失败时只排除该候选；只要仍有一项完整结果就返回 200，全部候选天气均失败时返回 503 `provider_unavailable`、固定 message“全部候选天气数据暂时不可用”，且不写历史。
- Provider 缓存采用 cache-first：只有 `now < expires_at` 才是新鲜命中，到期瞬间及之后均视为 miss；新鲜命中不调用真实 provider。miss 后才调用 provider 并在成功时写缓存；任何 `ProviderError`、预算错误、校验错误或畸形响应都不得写缓存，过期缓存不得作为降级结果。这样“provider 失败时可用缓存”仅指请求开始时已经命中的同范围新鲜缓存，不允许 stale-if-error。
- 缓存 TTL 固定为 geocode 30 天、`poi_search` 7 天、distance 1 天、weather 1 小时。缓存键为 `sha256(canonical_json({"schema_version":1,"provider", "operation", "params"}))`：JSON 使用 UTF-8、键排序、无多余空格；字符串做 NFC、去首尾空白并折叠连续空白，枚举取 JSON value，日期取 ISO `YYYY-MM-DD`，列表保留业务顺序。`provider` 固定为 `amap|qweather`，`operation` 固定为 `geocode|poi_search|distance|weather`。各操作 `params` 恰为：geocode=`{address,city}`；POI search=`{query_kind:"search",center:"lon6,lat6",city,scenery_types:[按用户顺序的枚举值],radius_km:"三位小数"}`；POI resolve=`{query_kind:"resolve",name,city}`；distance=`{origins:[按输入顺序的"lon6,lat6"],destination:"lon6,lat6",type:"driving"}`；weather=`{coordinate:"lon2,lat2",start,end,lang:"zh",unit:"m"}`。`params` 不含 key、Authorization、主密码、header、显示 label 或原始地址以外的私人数据。
- 缓存 payload 也固定为 canonical JSON envelope：`{"schema_version":1,"model":"Origin|Destination|DestinationList|DistanceEstimateList|DailyWeatherList","value":...}`。POI resolve 使用单对象 `Destination`，POI search 使用 `DestinationList`；`value` 是对应 Pydantic 模型的 JSON mode 输出，列表保持 provider/出发地/日期顺序。模型名、schema version、JSON 解析或 Pydantic 校验不匹配均视为损坏缓存，删除该条后按 miss 处理，不输出原 payload。
- 内部缓存协议固定为 `CacheEntry(cache_key:str,provider:str,operation:str,payload_json:str,created_at:datetime,expires_at:datetime)`；`CacheRepository.get_fresh(cache_key:str,now:datetime)->CacheEntry|None`、`put(cache_key:str,provider:str,operation:str,payload_json:str,created_at:datetime,expires_at:datetime)->None`、`delete(cache_key:str)->None`、`delete_expired(now:datetime)->int`。全部 datetime 必须是 aware UTC；`get_fresh` 执行严格 `now < expires_at`。
- 内部来源追踪不得放在单例 provider 的共享可变字段或全局变量。`ProviderEvent` 是字符串枚举 `CACHE|DEMO|WEATHER_EXCLUDED|STRAIGHT_LINE|TEMPLATE_EXPLANATION|INSUFFICIENT_CANDIDATES`；`ProviderTrace(events:set[ProviderEvent])` 提供 `mark(event)->None` 和 `to_source_state(final_item_count:int)->SourceState`。应用 lifespan 只共享 `ProviderRuntime`（HTTP client、真实 adapter、cache repository）；每次 API 请求调用 `ProviderRuntime.new_request_bundle()->ProviderBundle`，返回字段 `geocoder,places,distance,weather,explanations,trace`，其中 trace 必须全新。
- 来源提示使用固定文本并按以下顺序去重：`使用未过期缓存结果`、`使用内置苏州演示数据`、`部分候选因天气不可用已排除`、`部分路程使用直线距离估算`、`推荐理由由本地模板生成`、`符合条件的候选不足 3 个`。成功请求中，只要事件在本次处理期间真实发生就保留，即使相关候选随后因精确超距或天气失败被排除；`insufficient_candidates` 仅按最终返回项少于三项触发。失败请求不返回 `SourceState`。`SourceState.kind` 仍按 `degraded > demo > cache > live` 取最高优先级；天气排除、直线估算或模板解释均使其为 `degraded`。
- 候选处理顺序固定为“精确距离（失败则直线估算）→ 主出发地硬过滤 → 天气”。精确或估算主距离超限的候选不得调用 QWeather；“全部候选天气失败”只统计通过距离硬过滤、实际进入天气步骤的候选。若没有候选通过距离过滤，按正常无候选返回 200 空 items，不误报天气服务失败。
- 真实 provider 凭据不作为设计、骨架、评分或自动测试阶段的前置条件；只有 provider 适配器和 mock 测试通过后，管理员才在手动真实 API 冒烟测试前通过本机隐藏终端录入凭据。
- 真实 API 冒烟测试使用固定、少量的苏州输入并记录调用次数，不进入默认测试命令或 CI。

## 8. 数据模型

- `User`
  - `id`
  - `username`
  - `password_hash`
  - `created_at`

- `UserSession`
  - `id`
  - `user_id`
  - `token_hash`
  - `csrf_hash`
  - `expires_at`
  - `revoked_at`

- `UserFavorite`
  - `id`
  - `user_id`
  - `place_id`
  - `created_at`
  - 唯一约束：`user_id + destination_id`

- `SearchHistory`
  - `id`
  - `user_id`
  - `request_snapshot`
  - `result_summary`
  - `created_at`

- `ShareLink`
  - `id`
  - `owner_user_id`
  - `history_id`
  - `token_hash`
  - `created_at`
  - `revoked_at`

- `ProviderCache`
  - `cache_key`
  - `provider`
  - `operation`
  - `payload_json`
  - `created_at`
  - `expires_at`

SQLite/Alembic 持久化契约固定如下：

- 业务表恰为 `users,user_sessions,places,favorites,histories,shares,api_cache` 七张；Alembic 迁移后另有框架表 `alembic_version`，迁移测试应看到总计八张表，不能把它误判为业务表。
- 所有业务 `id` 都是在应用层生成的规范小写 UUID 字符串并以 `String(36)` 保存；哈希以 64 位小写十六进制 `String(64)` 保存。时间字段使用 SQLAlchemy `DateTime(timezone=True)`，写入前必须转换为 UTC；SQLite 读出的无时区值按 UTC 恢复，不接受本地时区值。JSON 使用 `Text` 保存 canonical JSON（UTF-8、`sort_keys=True`、无多余空格），不用 pickle 或 SQLite 私有 JSON 扩展。
- `users(id PK, username String(32) UNIQUE NOT NULL, password_hash Text NOT NULL, created_at UTC NOT NULL)`。
- `user_sessions(id PK, user_id FK users.id ON DELETE CASCADE, token_hash UNIQUE NOT NULL, csrf_hash NOT NULL, expires_at UTC NOT NULL, revoked_at UTC NULL)`；索引 `user_id` 和 `expires_at`。
- `places(id PK, provider String(32), provider_place_id String(255), name String(200), address String(500), city String(100), longitude Float, latitude Float, type_name String(200), type_code String(100), scenery_tags_json Text, updated_at UTC)`；以上均 NOT NULL，唯一约束 `(provider,provider_place_id)`。
- `favorites(id PK, user_id FK users.id ON DELETE CASCADE, place_id FK places.id ON DELETE CASCADE, created_at UTC NOT NULL)`；唯一约束 `(user_id,place_id)`，并索引 `user_id`。
- `histories(id PK, user_id FK users.id ON DELETE CASCADE, mode String(32), request_json Text, result_json Text, created_at UTC)`；以上均 NOT NULL，并以 `(user_id,created_at)` 建索引。历史 JSON 是完整结构化快照，不保存凭据、Cookie 或原始 provider 响应。
- `shares(id PK, owner_user_id FK users.id ON DELETE CASCADE, history_id FK histories.id ON DELETE CASCADE, token_hash UNIQUE NOT NULL, created_at UTC NOT NULL, revoked_at UTC NULL)`；索引 `owner_user_id`、`history_id`。删除 history 由外键级联删除关联 share 行，因此公开链接立即失效。
- `api_cache(cache_key String(64) PK, provider String(32), operation String(32), payload_json Text, created_at UTC, expires_at UTC)`；除主键外均 NOT NULL，并索引 `expires_at`。不保存原始参数、地址或凭据；`cache_key` 已包含规范化参数的不可逆摘要。
- 每个 SQLite 连接必须执行 `PRAGMA foreign_keys=ON`。`backend/alembic.ini` 的 `sqlalchemy.url` 默认为空；`backend/alembic/env.py` 优先使用测试通过 Alembic `Config` 注入的 URL，否则从 `Settings().database_path` 生成 URL。生产默认只由非秘密 `ROAMBOT_DATA_DIR` 和固定文件名 `roambot.db` 决定。

领域/API 模型固定契约如下。全部使用 Pydantic v2、`extra="forbid"`、`allow_inf_nan=False`；所有必填字段传 `null` 都拒绝。请求文字先 `strip`；主出发地、同行地址和目标地点清理后长度 1-200，城市清理后为空则为“苏州”，显式 `null` 仍拒绝。领域校验抛 `pydantic.ValidationError`，单元测试断言稳定字段 `loc/type`，不绑定 Pydantic 的英文 message；API 层统一转为 422 `validation_error`。

- 枚举 JSON 值：`SceneryType = lake|sea|old_town|museum|park|mountain`；`SceneryMatchMode = any|cover_all`；`SourceKind = live|cache|demo|degraded`。中文只作为 WebUI 标签，不作为 API 枚举值。
- `RankingWeights`：`weather:float`、`distance:float`、`fairness:float`、`popularity:float`，四项全部必填、各在 0-100、有限且总和大于 0。
- `TravelRequestBase`：`city:str="苏州"`、`main_origin:str`、`companion_origins:list[str]=[]`（最多 2）、`max_distance_km:float`（`0<x<=500`）、`start_date:date`、`end_date:date`、`weights:RankingWeights|null=None`。省略 weights 后请求对象保持 `None`，服务层再按出发地数量选择默认值；单出发地若显式提交非零 fairness 则校验失败。
- `RecommendationRequest(TravelRequestBase)`：`scenery_types:list[SceneryType]`（1-6 个、禁止重复、保留输入顺序）、`scenery_match_mode:SceneryMatchMode="any"`。由于 extra forbid，`target_place` 即使为 null 也拒绝。
- `PlaceEvaluationRequest(TravelRequestBase)`：`target_place:str`。`scenery_types` 或 `scenery_match_mode` 即使为 null 也作为额外字段拒绝。
- `Coordinate`：`longitude:float[-180,180]`、`latitude:float[-90,90]`、`system:Literal["gcj02"]="gcj02"`。
- `Origin`：`label:str`、`address:str`、`coordinate:Coordinate`。
- `Destination`：`provider_id:str`、`name:str`、`address:str`（允许空字符串）、`city:str`、`coordinate:Coordinate`、`type_name:str`、`type_code:str`、`scenery_tags:frozenset[SceneryType]=frozenset()`、`popularity_rank:int>=1`。
- `DailyWeather`：`date:date`、`condition:str`、`temp_min_c:float`、`temp_max_c:float`、`precipitation_mm:float>=0`、`wind_speed_kmh:float>=0`、`humidity_percent:float[0,100]`、`visibility_km:float>=0`、`uv_index:float>=0`；全部必填且不可 null。
- `DailySuitability`：`date:date`、`score:float[0,100]`、`reasons:list[str]`（至少一项）。
- `DistanceEstimate`：`origin_label:str`、`distance_km:float>=0`、`duration_minutes:float>=0|null=None`、`estimated:bool=False`。
- `GroupAccessibilityScore`：`average_distance_km:float>=0`、`max_distance_km:float>=0`、`distance_variance:float>=0`、`distance_stddev:float>=0`、`fairness_score:float[0,100]`；单人方差和标准差为 0、公平性为 100。
- `ScoreBreakdown`：`weather,distance,fairness,popularity,total:float[0,100]`、`coverage_penalty:float[0,20]`。
- `SourceState`：`kind:SourceKind`、`notices:list[str]=[]`。
- `RecommendationItem`：`destination:Destination`、`distances:list[DistanceEstimate]`、`group_accessibility:GroupAccessibilityScore`、`weather:list[DailyWeather]`、`daily_suitability:list[DailySuitability]`、`score:ScoreBreakdown`、`explanation:str`。
- `RecommendationResponse`：`items:list[RecommendationItem]`、`source_state:SourceState`、`generated_at:str`（UTC RFC3339）。
- `PlaceEvaluationResponse`：`item:RecommendationItem`、`source_state:SourceState`、`generated_at:str`（UTC RFC3339）。

- `LLMConfig`
  - `base_url`
  - `api_key_configured`
  - `model`
  - `enabled`

## 9. 技术选型

暂定技术栈：
- 后端：Python + FastAPI。
- 前端：React + TypeScript + Vite，适配桌面与手机浏览器。
- 数据库：SQLite；测试使用隔离的临时数据库，Docker 使用持久化数据卷。
- 凭据存储：使用成熟密码学库实现带主密码的认证加密文件，不自行实现密码学算法。
- 测试：后端 pytest；前端 Vitest；关键用户流程 Playwright。
- 分发：多阶段 Docker 构建，最终以单镜像、单域名部署，并发布到公开镜像仓库。
- CI：GitLab CI，包含 `unit-test` job。
- LLM：OpenAI-compatible provider 抽象，默认演示模型使用学校额度平台的 DeepSeek V4 Flash；测试使用 mock/template。

理由：
- Python 适合快速实现推荐评分、API 适配与测试。
- FastAPI 上手成本低，便于提供 Web API。
- React 适合承载双模式表单、权重滑块、登录、收藏、历史和分享等交互状态；TypeScript 用于减少前后端字段不一致。
- 开发时保持前后端职责分离，生产时同域名单镜像部署，以保留组件化能力并控制认证、跨域和分发复杂度。
- Docker 分发最符合“全新机器从零运行”的作业要求。

## 10. 验收标准

- 用户可使用唯一用户名和密码注册、登录和退出；重复用户名、错误凭据和未登录访问均得到明确且不泄露账户信息的响应。
- 数据库和日志中不出现明文密码；退出后原会话不能继续访问受保护的个人数据。
- 游客无需登录即可完成核心推荐和指定地点评估；游客查询不生成个人历史，也不能收藏或创建分享链接。
- 登录用户可添加、取消和查看自己的收藏地点；重复收藏不生成重复记录，其他用户不能访问该收藏。
- 收藏记录不保存旧天气或旧评分；重新评估收藏地点时使用新的出发地、日期和当前可用天气。
- 登录用户的成功查询自动生成历史快照；非法或失败请求不进入历史，其他用户不能访问该记录。
- 历史详情明确显示生成时间且不自动刷新；重新查询使用当前可用天气并生成新记录，不覆盖原历史。
- 登录用户可删除单条历史或清空自己的全部历史，不能删除其他用户的历史；删除历史不影响收藏。
- 历史删除后，其关联分享链接立即不可用。
- 登录用户可为自己的历史快照创建和撤销只读分享链接；其他用户不能替其创建或撤销。
- 有效分享链接无需登录即可查看脱敏快照；页面不泄露用户身份或详细出发地址，撤销后链接立即不可用。
- 本机管理员可通过隐藏终端输入初始化、查看状态、更新和清除 API key；任何状态输出都不回显明文。
- 真实 API key 不出现在源码、Git、`.env`、日志、Docker 镜像、SQLite 业务表或公开 WebUI 中。
- 忘记主密码时，只有拥有 Docker 主机权限的管理员可执行紧急重置；重置不删除账户、收藏和历史数据。
- 用户可在 WebUI 输入 1-3 个出发地址、距离、风景类型、日期范围。
- 用户可选择推荐模式或指定地点评估模式。
- 推荐模式下用户必须填写风景类型；指定地点评估模式下用户不能填写风景类型，前端隐藏或禁用该输入，后端拒绝矛盾请求。
- 系统返回至少 3 个按日期区间整体推荐度排序的地点，或说明候选不足原因。
- 指定地点评估模式下，系统只返回目标地点的推荐指数、每日适宜度、原因与风险提示，不返回推荐地点列表。
- 当用户填写范围内不存在符合风景类型的地点时，系统显示“规定范围内无检索结果”，并展示最近距离与最热门的扩展建议。
- 每个推荐结果包含用户所选日期区间内每天的旅游适宜度、区间整体推荐度、天气摘要、距离/公平性说明、推荐理由。
- WebUI 以结果卡片呈现推荐信息，不展示地图、路线、导航或具体日程。
- 输入非法时返回明确错误。
- 外部 API 在测试中可被 mock。
- `make test` 或等价命令可一键运行核心测试。
- Docker 可构建并运行。
- 前端组件测试、后端单元测试和关键 Playwright 流程均可由一键测试命令触发。
- 真实 API 冒烟测试必须与一键自动测试分离，默认不执行且不得在 CI 中消耗真实额度。
- Docker 使用挂载数据卷保存 SQLite 文件，容器重建后账户与个人数据仍可读取。
- `.gitlab-ci.yml` 包含 `unit-test` job。

## 11. 风险与未决问题

- 高德地图 API、QWeather API 的免费额度与申请流程需要确认。
- V1 已固定将高德 GCJ-02 坐标按原值、两位小数传给 QWeather；真实 smoke 必须核对苏州样本的地点与天气合理性，发现偏差时再以独立坐标适配任务修订。
- SQLite 适合当前课程项目和小规模使用；若未来需要多实例部署或高并发写入，应迁移到服务端数据库，但不属于当前范围。
- 真实距离/耗时查询可能产生较多 API 调用，需做数量限制。
- 真实 API 按请求计费；开发测试阶段必须默认 mock，演示阶段应限制候选数量和调用次数。
- 地图 API 不稳定提供“推荐游玩时长”；如产品需要展示，应采用内部估算规则并标注为估算值。
- LLM 输出可能不稳定且真实调用会消耗学校额度 token；测试只验证输入输出封装、mock 行为和模板降级，不依赖真实 LLM。
- 不接入 12306、机票和 SunsetBot；朝霞/晚霞不作为当前核心风景类型。
- 不收集手机号，不接入短信或网页验证码供应商；这些属于主项目验收后的可选账户增强。
- 不做地图展示、路线绘制、导航或具体日程安排；这些属于用户采纳推荐后的出行执行范围。
- 当前交付只实现响应式 Web 应用。微信小程序不属于本轮验收标准；仅在 Web 主项目全部完成后作为独立扩展重新评估，不得影响必做功能、测试、CI、分发和线上 WebUI。
- 苏州默认演示中海景候选较少，海景作为跨城市或较远距离扩展类型保留。
