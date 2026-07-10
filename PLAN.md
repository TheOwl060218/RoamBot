# PLAN: 晴游Bot

## 阶段 0：前置准备

### Task 0.1 安装 Superpowers

- 目标：满足作业强制工具链要求。
- 涉及文件：`AGENT_LOG.md`、`SPEC_PROCESS.md`。
- 操作要点：在 Codex App 插件侧边栏搜索并安装 `Superpowers`，确认可触发 brainstorming / writing-plans / TDD 相关技能。
- 验证步骤：记录安装方式、截图或文字记录可用状态。

### Task 0.2 准备凭据与环境变量模板

- 目标：明确地图、天气、LLM key 的配置方式。
- 涉及文件：`.env.example`、`.gitignore`、`README.md`。
- 验证步骤：确认 `.env` 不会被 Git 跟踪，`.env.example` 不含真实 key。

## 阶段 1：规约与计划

### Task 1.1 Superpowers brainstorming 复核 SPEC

- 目标：用 Superpowers 检查需求是否完整。
- 涉及文件：`SPEC.md`、`SPEC_PROCESS.md`。
- 验证步骤：至少记录 3 轮关键迭代与人工决策。

### Task 1.2 Superpowers writing-plans 复核 PLAN

- 目标：把计划拆到可由 subagent 执行的粒度。
- 涉及文件：`PLAN.md`。
- 验证步骤：每个实现 task 都有目标、文件、失败测试、验证命令。

### Task 1.3 陌生 agent 冷启动验证

- 目标：验证 SPEC/PLAN 离开当前对话后仍可理解。
- 涉及文件：`SPEC_PROCESS.md`、`SPEC.md`、`PLAN.md`。
- 验证步骤：记录陌生 agent 的问题、误解、产出差距和修订 diff。

## 阶段 2：实现

> 从本阶段开始才写实现代码。每个 task 都遵循 TDD：先写失败测试，再写最小实现，再重构。

### Task 2.1 项目骨架

- 目标：建立后端、测试、静态前端、配置入口。
- 涉及文件：`pyproject.toml`、`src/`、`tests/`、`Makefile`。
- 失败测试：`make test` 初始应能发现没有实现的基础测试。
- 验证步骤：`make test`。

### Task 2.2 输入模型与校验

- 目标：实现 `TravelRequest` 校验。
- 涉及文件：`src/models.py`、`tests/test_request_validation.py`。
- 失败测试：地址为空、额外地址超过 2 个、距离非正、日期超过 7 天应失败。
- 验证步骤：`make test`。

### Task 2.3 地址解析抽象

- 目标：定义 geocoder 接口，并实现 mock geocoder。
- 涉及文件：`src/geocoding.py`、`tests/test_geocoding.py`.
- 失败测试：未知地址返回明确错误。
- 验证步骤：`make test`。

### Task 2.4 候选地点筛选

- 目标：根据风景类型和距离筛选候选地点。
- 涉及文件：`src/places.py`、`tests/test_places.py`。
- 失败测试：超出最远距离的地点不应出现。
- 验证步骤：`make test`。

### Task 2.5 天气抽象与评分

- 目标：定义 weather provider，并实现天气适宜度评分。
- 涉及文件：`src/weather.py`、`src/scoring.py`、`tests/test_weather_scoring.py`。
- 失败测试：雨天分数低于多云；高温扣分；朝霞/晚霞考虑云量与降雨。
- 验证步骤：`make test`。

### Task 2.6 多人汇合公平性评分

- 目标：计算平均距离、最大距离、距离差异与公平性分。
- 涉及文件：`src/group_access.py`、`tests/test_group_access.py`。
- 失败测试：距离差异越大，公平性分越低。
- 验证步骤：`make test`。

### Task 2.7 综合推荐排序

- 目标：合并天气、风景、可达性、公平性分，输出排序结果。
- 涉及文件：`src/recommendation.py`、`tests/test_recommendation.py`。
- 失败测试：总分高的地点应排在前面；候选不足时返回可读原因。
- 验证步骤：`make test`。

### Task 2.8 LLM 解释封装

- 目标：封装 LLM provider，测试中使用 mock。
- 涉及文件：`src/explainer.py`、`tests/test_explainer.py`。
- 失败测试：LLM 失败时使用模板解释降级。
- 验证步骤：`make test`。

### Task 2.9 Web API 与 WebUI

- 目标：提供推荐接口和用户页面。
- 涉及文件：`src/app.py`、`static/`、`tests/test_api.py`。
- 失败测试：合法请求返回推荐列表；非法请求返回 400。
- 验证步骤：`make test`，浏览器手动验证页面。

## 阶段 3：交付

### Task 3.1 Docker 分发

- 目标：可通过 Docker 构建和运行。
- 涉及文件：`Dockerfile`、`README.md`。
- 验证步骤：`docker build`，`docker run`。

### Task 3.2 GitLab CI

- 目标：满足作业 CI 要求。
- 涉及文件：`.gitlab-ci.yml`。
- 验证步骤：存在名为 `unit-test` 的 job，最后一次 CI pass。

### Task 3.3 最终文档

- 目标：补齐 README、AGENT_LOG、REFLECTION。
- 涉及文件：`README.md`、`AGENT_LOG.md`、`REFLECTION.md`。
- 验证步骤：按 `TASKS.md` 最终交付检查逐项核对。
