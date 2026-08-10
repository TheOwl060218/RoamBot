# RoamBot任务清单

## 0. 前置条件

- [x] 创建项目目录：`RoamBot`（由初始名 `sunny-week-travel` 重命名）
- [x] 初始化 Git 仓库
- [x] 检查基础工具：Git 可用，Docker 命令可用但本机 Docker 配置有权限警告
- [x] 确认可用运行时：Codex bundled Node.js 与 Python 可用
- [x] 在 Codex App 插件侧边栏搜索并安装 `Superpowers`
- [x] 使用多个不继承当前上下文的陌生 agent 完成冷启动验证
- [x] 在真实 provider 人工 smoke 前申请 API key：高德、QWeather、学校 LLM

## 1. 规约阶段：先写清楚，不写实现代码

- [x] 确定 B 类项目方向
- [x] 放弃 12306 与机票查询作为核心功能
- [x] 增加“1-2 个额外出发地址”的多人汇合旅游功能
- [x] 写出 `SPEC.md` 初稿
- [x] 写出 `PLAN.md` 初稿
- [x] 写出 `SPEC_PROCESS.md` 初稿
- [x] 使用 Superpowers / 当前 Codex 会话的 brainstorming 方式复核 `SPEC.md`
- [x] 使用 Superpowers / 当前 Codex 会话的 writing-plans 方式复核 `PLAN.md`
- [x] 人工确认完整设计与 PLAN 可以进入冷启动验证

## 2. 冷启动验证

- [x] 开一个不同类型或全新上下文的 agent
- [x] 只提供 `SPEC.md` 与 `PLAN.md`
- [x] 让它选择 1-2 个 task 试做，不补充口头解释
- [x] 记录它卡住、误解、提问的位置
- [x] 修改 `SPEC.md` 与 `PLAN.md`
- [x] 在 `SPEC_PROCESS.md` 记录第一次修订前后差异
- [x] 使用第二个全新 agent 复测修订后的根文档并记录第二次失败
- [x] 使用第三个全新 agent 复测第二次修订后的根文档并记录第三次失败
- [x] 使用第四个全新 agent 复测第三次修订后的根文档并记录第四次失败
- [x] 使用第五个全新 agent 复测第四次修订后的根文档并记录第五次失败
- [x] 使用第六个全新 agent 抽查并记录分享/Docker 冷启动失败
- [x] 使用第七个全新 agent 抽查 M2.1 数据库迁移与 M4.5 缓存降级并记录失败
- [x] 使用第八个全新 agent 复核修订后的 M2.1/M4.5 并记录剩余缓存契约缺口
- [x] 使用第九个全新 agent 复核缓存键、payload、trace 与调用顺序；定点修订后复测通过
- [x] 完成占位扫描、类型一致性检查与 `git diff --check`，规划阶段通过

## 3. 实现阶段：TDD

- [x] Task 1：项目骨架、配置与测试入口
- [x] Task 2：输入模型与校验
- [x] Task 3：地址解析接口抽象与 mock
- [x] Task 4：候选地点数据与筛选
- [x] Task 5：天气接口抽象与 mock
- [x] Task 6：天气适宜度评分
- [x] Task 7：多人汇合距离与公平性评分
- [x] Task 8：综合推荐排序
- [x] Task 9：LLM 解释接口与 mock
- [x] M2：SQLite/Alembic、账户、会话、收藏、历史、分享、缓存与加密凭据 CLI
- [x] Task 10：WebUI
- [x] M4.1-M4.7：真实 Provider 适配、缓存降级与零网络人工 Smoke 命令
- [x] Task 11：Docker 分发
- [x] Task 12：CI、部署证据与最终工程文档（学生个人反思和课程平台提交仍需本人完成）

## 4. 最终交付检查

- [x] `SPEC.md`
- [x] `PLAN.md`
- [x] `SPEC_PROCESS.md`
- [x] `AGENT_LOG.md`
- [x] `README.md`
- [ ] `REFLECTION.md`
- [x] 源代码
- [x] 一键测试命令
- [x] `.gitlab-ci.yml`，包含名为 `unit-test` 的 job
- [x] `Dockerfile`
- [x] `.env.example`
- [x] WebUI 可访问地址：[https://roambot-production.up.railway.app](https://roambot-production.up.railway.app)
- [x] 当前功能基线 CI/CD pass 记录：GitHub Actions `31368741662`，提交 `1bd06496b9af3743f7161bf1c5a524c0b378887d`
- [ ] 学生本人完成 `REFLECTION.md`
- [ ] 按课程平台要求提交 WebUI URL、NJU Git 地址和最终材料
