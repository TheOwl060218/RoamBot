# Photo Home Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 将用户确认的福州照片首页接入正式网站，不改变既有查询、认证及个人功能。

**Architecture:** 独立 HomePage 位于 `/`，不使用 AppShell；SearchPage 改为 `/recommend`，业务页面继续使用 AppShell。首页复用 AuthProvider/AuthDialog，静态 JPEG 与局部 CSS 提供背景及响应式布局。

**Tech Stack:** React 19、TypeScript、React Router、现有 Lucide、Vitest、Playwright；不增依赖。

**Spec:** `docs/superpowers/specs/2026-10-08-photo-home-design.md`（用户已确认）。

## Global Constraints

- 保留现有未提交修改，不部署、不推送，不改后端或数据库。
- 普通登录成功留首页；匿名我的计划先登录再进入 `/plans`；查询匿名可用。
- 原查询用途的 `/` 迁移至 `/recommend`，路由 state 与查询草稿不丢失。
- 精确沿用 spec 的尺寸/间距/断点/悬停倍率；登录前后两排同水平；手机按钮文字居中。
- 全部验证只用 Mock/demo/HTTP fixture；隔离 8010/5180 与本轮专用数据目录，不停止用户服务。
- 每任务先写测试并观察有效失败，再实现；本轮不自动提交，交付后由用户决定备份。

## Review Focus

- 会话初始化/长用户名：固定两排布局，无访客闪烁或横向溢出。
- 取消/重复开启注册弹窗：无残留凭据或错误，下一次初始模式正确。
- 退出失败：账户仍显示登录态，并显示错误，不重复发请求。
- 收藏重评/历史重查：进入查询页，携带原 state，不落到照片首页。
- 窄屏/低高度/减少动画：入口可访问、无横向溢出，文字中心与箭头互不影响。

## Task 1: 首页组件与认证复用

**Files:** 新建 `frontend/src/pages/HomePage.tsx`、`frontend/src/styles/home.css`、`frontend/src/assets/fuzhou-home.jpg`、`frontend/tests/HomePage.test.tsx`；修改 `frontend/src/features/auth/AuthDialog.tsx`、`frontend/tests/AuthDialog.test.tsx`、`frontend/src/main.tsx`。

**Interfaces:** `HomePage(): JSX.Element` 消费 `useAuth()`、router navigate；AuthDialog 新增可选 `initialMode?: 'login' | 'register'`，默认 login，现有调用不变。首页通过关闭/成功回调控制弹窗及可选计划目标。

- [x] 写测试：guest 查询链接 `/recommend`、两个登录入口对应模式、普通登录后 URL 不变且关闭弹窗、计划入口成功后 `/plans`、取消不跳转、退出失败/重复点击、初始化与长名称。
- [x] `node node_modules/vitest/vitest.mjs run tests/HomePage.test.tsx tests/AuthDialog.test.tsx`，确认失败来自缺失首页/模式能力。
- [x] 实现组件及 optional 初始模式，弹窗重新挂载隔离表单状态；真实用户名代替演示账户，退出 await/catch/finally；认证未完成时预留固定行高。保留既有 AuthDialog 验证和焦点管理。
- [x] 从已确认本地 derivative `fuzhou-home-photo.jpg` 复制二进制资源至 assets，检查存在/尺寸；局部 home.css 移植已确认参数，正式页面使用最小窗口高度和自然滚动，而非预览固定外壳高度。
- [x] 重跑以上测试，通过后进入 Task 2。

## Task 2: 路由迁移与回流

**Files:** 修改 `frontend/src/app/router.tsx`、`frontend/src/app/AppShell.tsx`、`frontend/src/features/favorites/FavoriteDetail.tsx`、`frontend/src/pages/HistoryPage.tsx`、`frontend/src/features/plans/PlanPages.tsx`、`frontend/tests/AppShell.test.tsx`；新增 `frontend/tests/homeNavigation.test.tsx`；更新既有浏览器测试中真正查询用途的根路径。

**Interfaces:** `/` → HomePage，`/recommend` → SearchPage；其余路径不变。品牌仅返回首页；推荐导航执行 clearSearchResult + HOME_RESET_REQUEST_EVENT 并进入 `/recommend`。

- [x] 写回归断言：品牌 href `/`、推荐 href `/recommend`；收藏重评携带 evaluationTarget；历史 rerun 携带 restoredSearch；计划开始推荐指向 `/recommend`。保留 RequireAuth 取消到首页的语义。
- [x] 跑专项测试观察旧 `/` 回流导致失败。
- [x] 修改路由与上述明确查询链接，保持 state、权限、参数不变；搜索其余 `/` 跳转并逐项按“首页/查询”语义检查，不全局盲替换。
- [x] 更新既有 e2e 查询入口/回流断言，新增首页断言；运行专项及全量 Vitest，通过后进入 Task 3。

## Task 3: 浏览器验收与交接

**Files:** 新建 `frontend/e2e/photo-home.spec.ts`、`docs/competition/PHOTO_HOME_PROGRESS.md`；更新 `docs/PROJECT_HANDOFF.md`；截图至 `evidence/photo-home-*-20261008.png`。

**Interfaces:** 使用 Task 1/2 正式组件和路由，以 fixture 提供匿名、已登录、延迟会话、认证错误等状态；不依赖真实账户。

- [x] 写浏览器几何/行为测试：1440/375/320 与低高度，匿名/登录两排 top 一致；手机按钮 text center 偏差 ≤1px；桌面六入口悬停 matrix scale1.08、无下划线，查询1.01；桌面只福州、手机保留拍摄地。
- [x] 覆盖普通登录留首页、注册正确模式、我的计划登录回跳、失败/取消、退出防重入、长用户名、直接刷新 `/recommend` 与业务回流；图片 decode 成功、无横向溢出；保存并目视检查截图。
- [x] 用系统浏览器通道及隔离端口运行新专项/受影响既有 e2e，检查进程退出码；只终止本轮创建的测试服务。
- [x] 运行 `node node_modules/vitest/vitest.mjs run`、`node node_modules/eslint/bin/eslint.js .`、`node node_modules/typescript/bin/tsc -b`、`node node_modules/vite/bin/vite.js build`（frontend cwd）。
- [x] 自审差异与查询回流清单，更新交接/验证记录，明确未测试 Live/真实手机/公网、未提交推送；交付用户刷新查看。
