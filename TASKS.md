# 晴行一周任务清单

## 0. 前置条件

- [x] 创建项目目录：`sunny-week-travel`
- [x] 初始化 Git 仓库
- [x] 检查基础工具：Git 可用，Docker 命令可用但本机 Docker 配置有权限警告
- [x] 确认可用运行时：Codex bundled Node.js 与 Python 可用
- [ ] 在 Codex App 插件侧边栏搜索并安装 `Superpowers`
- [ ] 选择一个“陌生 agent”用于冷启动验证，例如 Cursor / Claude Code / 另一个全新 Codex 会话
- [ ] 申请或准备 API key：地图、天气、LLM

## 1. 规约阶段：先写清楚，不写实现代码

- [x] 确定 B 类项目方向
- [x] 放弃 12306 与机票查询作为核心功能
- [x] 增加“1-2 个额外出发地址”的多人汇合旅游功能
- [x] 写出 `SPEC.md` 初稿
- [x] 写出 `PLAN.md` 初稿
- [x] 写出 `SPEC_PROCESS.md` 初稿
- [ ] 使用 Superpowers `brainstorming` 复核 `SPEC.md`
- [ ] 使用 Superpowers `writing-plans` 复核 `PLAN.md`
- [ ] 人工签字确认 SPEC/PLAN 可以进入冷启动验证

## 2. 冷启动验证

- [ ] 开一个不同类型或全新上下文的 agent
- [ ] 只提供 `SPEC.md` 与 `PLAN.md`
- [ ] 让它选择 1-2 个 task 试做，不补充口头解释
- [ ] 记录它卡住、误解、提问的位置
- [ ] 修改 `SPEC.md` 与 `PLAN.md`
- [ ] 在 `SPEC_PROCESS.md` 记录修订前后差异

## 3. 实现阶段：TDD

- [ ] Task 1：项目骨架、配置与测试入口
- [ ] Task 2：输入模型与校验
- [ ] Task 3：地址解析接口抽象与 mock
- [ ] Task 4：候选地点数据与筛选
- [ ] Task 5：天气接口抽象与 mock
- [ ] Task 6：天气适宜度评分
- [ ] Task 7：多人汇合距离与公平性评分
- [ ] Task 8：综合推荐排序
- [ ] Task 9：LLM 解释接口与 mock
- [ ] Task 10：WebUI
- [ ] Task 11：Docker 分发
- [ ] Task 12：CI 与最终文档

## 4. 最终交付检查

- [ ] `SPEC.md`
- [ ] `PLAN.md`
- [ ] `SPEC_PROCESS.md`
- [ ] `AGENT_LOG.md`
- [ ] `README.md`
- [ ] `REFLECTION.md`
- [ ] 源代码
- [ ] 一键测试命令
- [ ] `.gitlab-ci.yml`，包含名为 `unit-test` 的 job
- [ ] `Dockerfile`
- [ ] `.env.example`
- [ ] WebUI 可访问地址
- [ ] 最后一次 CI/CD pass 记录
