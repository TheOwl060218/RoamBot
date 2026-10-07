# 同行计划开发记录（Codex）

日期：2026-10-05～2026-10-07（Asia/Shanghai）。执行者：Codex；本文件不属于湛卢生成证据。
依据：`docs/superpowers/specs/2026-10-05-travel-plan-collaboration-design.md`。
用户授权：直接继续 P1 及后续开发。当前分支 `experiment/ui-clean-a`，起点为干净 P0。
继续沿用该实验分支，不创建额外工作区，不提交或推送未验收代码。

## 2026-10-07 决策工作台收尾

最新追加（两端式页头）：用户明确旧右侧留白不是硬限制，批准Demo后要求实施。Codex缩小标题、去掉重复说明，左概况右进展，手机上下排列，实际已加入人数作为进度分母；不公开未授权进展、不增加轮询或后端。页面5项RED、浏览器4项RED后实现；旧完整业务三处投票人数定位限定区域，过程如实见 WORKBENCH_PROGRESS.md。最终Vitest150、ESLint/tsc/build、系统Chrome Mock全量E2E38/38（2.3m）通过。刷新前端即可，正式视觉待用户确认，未提交推送，非湛卢证据。

最新追加（当日说明）：用户批准原按钮锚定浅青浮层，取消内联撑高，原按钮/卡片/表格位置不变；同按钮、外部点击及Escape收起、单浮层、切换日期关闭。Codex组件2项RED和浏览器4项RED后实现，长说明追加检查暴露maxHeight覆盖上限，修正后全量系统Chrome Mock E2E34/34；可用宽度专项另4/4。前端145测试、ESLint/tsc/build通过。完整过程见 WORKBENCH_PROGRESS.md，用户视觉仍待确认。只改前端，刷新即可，未提交推送，非湛卢证据。

最新追加（展开提示）：用户只批准全部日期与第二候选，未加入管理/当日说明提示。复用淡青Portal胶囊2秒，按页面/内部滚动容器实际可见性条件触发，可见不提示、收起立即清除、不强制滚动。Codex先补两个页面RED与共享模块导入RED，修收起清理及Fast Refresh分文件，专项fixture补齐查询路程后通过；详见 WORKBENCH_PROGRESS.md。当前前端143测试、ESLint/tsc/build及全量系统Chrome Mock E2E30/30通过；仅前端，不需后端重启，未提交推送，非湛卢证据。

最新追加：用户批准三层工具栏，Codex将管理/投票从标题右侧移至比较标题同行，将日期/天气操作移至其下；12px紧邻按钮不再被时间文案撑开。保留所有权限和投票逻辑，仅前端。页面RED及浏览器几何RED、CSS覆盖与高度修正如实见 WORKBENCH_PROGRESS.md。当前Vitest138（23文件）、ESLint/tsc/build通过，全量系统Chrome Mock E2E26/26（1.9m），未验证Live/真实手机，未提交推送；刷新前端即可，不需后端重启。此轮同样非湛卢开发证据。

用户批准双角色原型后由 Codex 正式实施，无子智能体。新增 PlanComparison、PlanVotePanel，重排 PlanPages 与 plans.css；同时修 CreatePlanControl 内登录框 portal。沿用后端路径、匿名 CSRF、权限、确认框与先投后看；没有改后端或数据库。历史测试只对齐此前已批准的回流行为。

真实过程：两个模块不存在产生导入 RED（断言未执行），实现后8项 GREEN；页面旧布局契约2项 RED 后接入；浏览器无宽度过渡2项 RED 后 CSS 实现。手机管理编辑被投票面板挡住，新增页面 RED，再改为打开管理收起投票且保留草稿。完整浏览器曾21通过/3失败：历史测试旧路由断言两项、桌面登录弹窗被内容拦截一项；分别更新旧契约、修挂载位置后24通过。随后补少候选、减少动画及防重复提交回归，不声称这些是先 RED。详见 WORKBENCH_PROGRESS.md。

最新命令在 frontend 执行，使用本机 codex-primary-runtime Node v24.19.0：

- `node node_modules/vitest/vitest.mjs run`：**23文件 / 137 passed**，退出0。
- `node node_modules/eslint/bin/eslint.js .`、`node node_modules/typescript/bin/tsc -b`：退出0。
- `node node_modules/vite/bin/vite.js build`：1857 modules，CSS63.70kB / JS393.67kB，退出0。
- 设置 `ROAMBOT_E2E_BROWSER_CHANNEL=chrome`、`ROAMBOT_E2E_BACKEND_PORT=8010`、`ROAMBOT_E2E_FRONTEND_PORT=5180`、`ROAMBOT_E2E_RUN_ID=workbench-final-20261007`、`PW_REUSE_SERVERS=1`，运行 `node node_modules/@playwright/test/cli.js test --workers=1`：**26 passed（3.2m）**，退出0。执行前隔离端口无现有服务，配置启动自己的 Mock/demo 服务；此环境变量没有用于复用用户8000/5173。Windows teardown 卡在临时服务退出，确认 worker 已退出后，仅结束该次自己创建的已知服务PID，获得正常退出0和 passed 汇总。
- `git diff --check`：退出0，只有LF→CRLF警告；未跟踪源码亦通过 ESLint/tsc。

浏览器矩阵包括全量 API 拦截的合成 fixture 布局测试和隔离 Mock 后端实际业务 E2E。后者包含游客推荐、注册、显式重查、创建、邀请、匿名投票/改票、检查天气、结束/重开/决定、历史返回工作区；写入仅 `.playwright-data/workbench-final-20261007`，不写 `data-competition-demo`。不是第三方 API、真实手机或公网协作验证。

双角色截图已查看并保存在 `evidence/workbench-{owner,voter}-{desktop,mobile}-20261007.png`；最新业务截图仍由原 E2E 输出，邀请输入已遮盖。自审核对状态守卫、summary边界、草稿保留、忙碌锁、单表单/inert、源数据语义与管理按钮对齐。没有独立审查；1日特例、全部管理危险动作逐项 UI 自动化、用户最终视觉、Live/公网/真实手机仍待确认。没有下载、Docker、用户数据/服务操作、commit/push；只清理自己创建的临时测试进程，保留工作区待验收。

## P1

### 2026-10-07 用户验收后补修：天气建议与按钮对齐

本节为后续 Codex 修复，非湛卢生成。用户明确批准三项修复后，先获得接口字段缺失 RED、前端空说明/新建议2项RED、按钮几何桌面/手机2项RED（12.3125px错位）；实现后pytest317、Vitest138、完整Chrome E2E26项通过（2.2m），Ruff/ESLint/tsc/build退出0。完整命令沿用上节，数据目录改 `weather-final-20261007`；详见 WORKBENCH_PROGRESS.md。本次使用既有 score_daily_weather，从已保存天气生成建议，不改快照/排名，不新增外部调用或数据库结构。强降水/公开API/读旧记录回归是实现后补测，不伪称先RED。

前端使用后端新建议，旧后端缺字段时继续显示暂无判断，但隐藏无内容说明按钮；用户须重启后端一次。空数据的旧展开测试补完整内容fixture，不放宽新契约。未重启用户服务、未修改用户数据库、未下载/使用Docker、未提交推送。Live、真实手机、用户视觉仍未验证。

- 初次测试 fixture 只返回一个候选，修正为湖景/博物馆/古镇查询后重新运行；初次失败不作为功能 RED。
- 有效 RED：`pytest backend/tests/api/test_plans.py -q --tb=short`，3 失败；计划路由缺失（404），登录推荐未返回 history_id。
- GREEN：同命令加 `backend/tests/api/test_history.py`，12 通过。
- 验证：游客无可信历史；创建必须登录并校验 CSRF；候选从本人推荐历史复制；计划快照去除原始出发地/坐标/单人路程；历史删除不影响计划；跨账户读写统一 404。
- 迁移只增加计划表，未操作用户现存数据库。迁移与完整回归将在后续门禁单独验证。

## 执行状态

- P1–P3：可信历史、计划、邀请、匿名身份、投票、天气与决定 API 已实现。
- P4–P6：创建确认、计划中心、发起者详情、邀请页及动态导航已实现。
- P7：自动化验收、截图、架构/启动/演示脚本完成；人工验收、实际视频录制、PPT 成品和参赛提交尚未完成。
- 全部为 P0 `00f4e80` 之后的未提交修改，不对应新 Commit，不代表 GitHub 已更新。

## P2 / P3 聚焦记录

- P2 RED：新增两项 API 测试，邀请路由缺失、邀请表缺失；3 通过 / 2 失败。
- P2 GREEN：5 通过。昵称 NFKC/大小写规范化唯一；匿名身份 Cookie 为 HttpOnly/SameSite=Lax；匿名写请求独立 CSRF；未投票不可看汇总；换新邀请令牌仅存哈希；参与者删除级联删除投票。
- 测试纠正：GET 会刷新匿名 CSRF，测试需使用刷新后的值；保留旧值导致 403 属于预期保护，不作为功能缺陷。
- P3 RED：决定与天气路由均缺失，5 通过 / 2 失败。
- P3 GREEN：7 通过。决定后关闭投票、重新开放保留投票；天气检查冷却一小时，失败保留最后成功数据和原始候选快照；结束后不再检查。
- 以上命令：`.venv/Scripts/python.exe -m pytest backend/tests/api/test_plans.py -q --tb=no`。
- 当前所有天气调用均为 Mock 或受控失败 fixture，未使用 Live。

## 决策

- 沿用历史仓储，新增计划服务负责事务和所有权；不改原推荐排序。
- 邀请页使用独立白名单数据，坐标仅保存为后端天气查询输入。
- 已批准设计与当前授权优先于历史暑期收尾限制、湛卢逐阶段等待条款。

## P4–P6 与浏览器集成

- 前端有效 RED：`PlanPages.test.tsx`、`PlanNavigation.test.tsx` 缺失目标组件；随后分别 GREEN 4 项、2 项。
- SearchWorkspace 接入创建操作；游客先登录再明确重新推荐，服务器只接收可信历史 ID 和候选 ID，不接收客户端评分。
- 单元测试环境缺少原生 dialog 方法，测试使用局部 shim；真实 Chrome E2E 检查创建弹窗与用户流程。
- 首次新流程 E2E 被旧注册 helper 的“注册后没有任何 dialog”假设拦住；本用例单独确认登录 dialog 消失、新创建 dialog 出现，不放宽旧 helper。
- 手机汇总文案同时出现在顶部和正文，改用 exact 文案定位，未删除用户行为断言。
- 聚焦桌面/手机 E2E 曾通过 2 项；不等同于全量 E2E 通过。
- 初次全量 12 项：4 workers 与其他门禁同时运行，2 个旧账户 dialog 用例失败、10 通过。隔离单 worker 后这两个用例通过，但手机布局用例因平滑滚动中的跨帧坐标测量失败，11 通过 / 1 失败。
- 布局测试修正为同一次 page.evaluate 内测量 5 个天气元素；保留原位置关系与溢出断言，不添加 sleep 或放宽阈值。
- Windows webServer 收尾未自动结束时，仅停止输出中确认由本次测试创建的 Uvicorn/Vite PID；不停止用户 8000/5173 服务。

## 收尾审查 RED→GREEN

1. 匿名投票响应缺少 CSRF，被响应模型补成 null，前端合并后无法直接再次改票。新增 API 测试 RED（1 失败 / 10 通过）→响应回传已验证的 CSRF→11 通过；E2E 增加不刷新直接改票。
2. 路由切换后 usePlan 仍保留上一个计划。新增 UI 测试 RED（1 失败 / 4 通过）→数据与错误绑定当前请求路径→5 通过，失效邀请不残留旧内容。
3. 仅删除字段不足以删除推荐理由中的地理编码出发地标签。新增脱敏测试 RED（1 失败 / 11 通过）→复用历史分享的 origin_labels 与递归字符串脱敏→12 通过。
4. 手机新计划原本只显示日期，不显示短暂展开状态。真实 Chrome RED 确认状态文本存在但隐藏；补齐移动端 58px 短暂状态、4 秒后收起，不横向展开，reduced-motion 时不使用过渡。最终 E2E 检查真实可见、收起和无溢出。

额外检查：UTC 时间输出、公开响应白名单、邀请访问日志脱敏、失败保留天气、最终候选检查与级联删除、0001→0004 迁移保留原用户、重复 upgrade。补充检查不是历史开发 RED，不能倒写成测试驱动过程。

## 自审边界与判定

Final review: self-review（仓库 AGENTS.md 禁止子智能体；未安排独立审查者）。人工审查仍待完成。

- Ruling: 继续现有实验分支、保留所有未提交代码，不创建新 worktree、不 commit/push — 用户已授权开发但未授权此次集成；代价是离开电脑前只有本地文件，远程仍是 P0 基线。
- Ruling: 本地最终 E2E 使用 `--workers=1` — 降低机器负载与 SQLite 写并发，保留全部用例；代价是不能据此宣称 4 workers 稳定或高并发能力。
- Deferred minor: 计划详情不自动实时推送其他参与者的票数，需要刷新页面；不新增 WebSocket。
- Deferred minor: 匿名 CSRF 在 GET/加入时刷新，多标签页可能需刷新后再投票；身份 Cookie 不丢失，错误有明确提示。
- Live 风险：天气网络查询当前持有 SQLite 写事务，慢服务可能影响其他写操作；未验证 Live 并发，不能宣称生产可扩展。
- 已审查明确没有新增聊天、地图、预订、后台天气任务、匿名发起者或远程部署。

## 最终检查（2026-10-06）

| 检查 | 实际命令 | 结果 |
|---|---|---|
| 后端全量 | `.venv/Scripts/python.exe -m pytest backend/tests -q --tb=no` | 311 通过 |
| 后端静态检查 | `.venv/Scripts/python.exe -m ruff check backend` | 退出 0 |
| 前端全量 | `node node_modules/vitest/vitest.mjs run` | 19 文件，98 通过 |
| 类型检查 | `node node_modules/typescript/bin/tsc -b` | 退出 0 |
| ESLint | `node node_modules/eslint/bin/eslint.js .` | 退出 0 |
| 生产构建 | `node node_modules/vite/bin/vite.js build` | 成功，1853 modules；JS 380.73 kB / CSS 48.15 kB |
| 完整 E2E | `node node_modules/@playwright/test/cli.js test --workers=1` | 桌面/手机 12 通过，退出 0 |
| 空白检查 | `git diff --check` | 退出 0，仅 LF→CRLF 警告 |

E2E 环境：`ROAMBOT_E2E_BROWSER_CHANNEL=chrome`，最终轮后端 8037、前端 5207，独立 run ID 与 SQLite 数据目录；未复用用户服务。包括新增手机短暂展开/收起检查在内，最终 12 项通过、退出 0。截图校正后的聚焦桌面/手机另一次 2 项通过。仍有工具环境的 NO_COLOR/FORCE_COLOR 警告。Playwright 时长包含终止收尾前的等待，不能作为性能指标。

实际版本：Node v24.19.0、Python 3.12.14、Vitest 4.1.10、Playwright 1.62.1、Vite 8.2.1。使用已安装的系统 Chrome channel，不是下载的固定版 Chromium；本轮未记录 Chrome 具体版本，不能补造版本号。

以上包含真实 FastAPI/SQLite/账户/匿名邀请与改票/天气 Mock/人工最终决定。失败重试与修正也保留在本文，不把首轮失败抹去。额外的截图校正仅调整截图前的滚动位置，避免固定导航在长图中间；不改变产品行为。

截图目录 `docs/competition/evidence/`；发起者详情对邀请复制框使用截图遮罩。原始 Playwright trace、测试 SQLite 与 Cookie 属于本地忽略产物，含会话信息，不应打包上传比赛材料。图像检查由 Codex 完成，用户尚未人工操作验收。

保留六张脱敏 Mock 图片：桌面/手机各一张计划中心、发起者详情、只读邀请页。已检查手机单列、顶部紧凑状态、底部操作可达；长图截图前回到顶部以正确呈现 sticky 导航。

演示启动使用的 `data-competition-demo/` 已加入 `.gitignore`，避免后续误收录账户/计划数据。测试服务均已停止，未结束用户原 8000/5173 进程；未删除任何用户数据。

启动、架构、视频脚本、PPT 大纲及备用方案见 [TRAVEL_PLAN_DEMO.md](TRAVEL_PLAN_DEMO.md)。完成当前范围后停止，不自动新增功能、提交、推送或部署。

## 2026-10-06 人工验收追加：醒目填写错误提示

用户报告最大距离输入 500000 后连续点击推荐看似没有反应。代码定位为 TravelForm.validate 仅设置字段下方错误后返回 false，没有醒目反馈。用户批准短设计：主题色顶部胶囊气泡、6 秒消失、重复提交重新计时、不堆叠、修正成功提交清除，保留内联定位提示；不使用阻塞对话框。

- TDD 第一轮：新增 4 项行为测试，4 失败 / 原 11 通过，失败为缺少具名 alert；实现 Portal 提示（避免侧栏裁切）后 15 通过。原稳定字段空间断言改为在表单容器内查找，避免新增 Portal 相同文本歧义，空间断言未放宽。
- 第二轮：补服务端英文消息应标明中文字段的测试，1 失败 / 15 通过；增加字段名与友好中文翻译后，全量 Vitest 19 文件 103 通过。ESLint、tsc、Vite build 通过（1854 modules）。命令沿用上表，未安装依赖。
- 用户要求计划中心“开始一次推荐”去下划线、使用整体颜色字体；仅调整按钮样式，保留链接导航语义。创建计划位置和重新推荐文案仍处讨论，未修改。
- 新增 `frontend/e2e/form-validation.spec.ts` 验证桌面/手机：错误提交不发推荐请求、气泡位于固定导航下方且不超出视口、自动消失、计划中心入口样式。首轮气泡几何检查通过，但计划中心样式步骤因测试遗漏登录而两项失败；补现有 registerUser 登录步骤后 2 通过、退出 0。这是测试准备错误，不是功能 RED。Mock + Chrome、隔离端口 8039/5209；没有重跑完整 E2E，不能把上一轮 12 项和本轮 2 项写成同一次 14 项全量通过。
- Windows 测试服务收尾等待时，确认测试 worker 已退出后结束本轮自行启动的 Uvicorn/Vite PID，得到 Playwright 最终退出码；未触碰用户 8000/5173 服务。
- 关于用户报告“确认重新推荐反复确认”及计划中心请求失败：只读查询当前 `8000/openapi.json`，计划 API 不存在，推荐响应模型没有 history_id。运行接口版本与当前代码不一致；需重启当前工作区后端再验证，尚未操作用户服务。先前口头推测“失败仍关闭弹窗”经调用链核对已纠正：onRerun 实际会在 submit 无结果时抛错，不能记录为已复现代码缺陷。

本轮仅改前端与记录，未 commit/push、未 Live、未 Docker、未更改后端/数据库；用户视觉验收和新版后端完整运行仍待确认。

### 同日后续用户确认调整

### 同日卡片工作台布局确认

用户确认白卡片沿用产品主题，空状态在标题下方居中无框，超过三个横向滑动、手机露出下一张提示。先补测试与更新现有分组测试，4 失败 / 4 通过（新具名分组、空提示、右滑控件尚不存在；历史分组名称调整）；实现 PlansPage/PlanCollection 与主题 CSS 后全量前端 106 通过。新测试覆盖 0、2、5 张计划不补位、计划链接保留、右按钮触发局部滚动。jsdom 不证明 CSS 几何、真实触摸或键盘滚动；这轮未启动后端/未运行 E2E。

发现结束投票必须修改既有数据库 CHECK（目前只允许 voting/decided）、API Literal、服务状态判断和前端，按设计审查要求先编写补充设计，尚未修改后端。历史重查返回左右工作区同样尚未实施。不声称这两项已完成。

用户批准把创建同行计划放到左侧“查看对比结果”下方，要求提示更贴合使用者，并把错误气泡淡化、改为 2 秒。实现保持原有选中至少两个候选才允许创建、登录后显式更新推荐等边界；不自动创建或调用 Live。文案改为“更新一下推荐，就能把这些地点保存成同行计划”，按钮“更新推荐”，明确候选变化需重选、此步不直接创建。

测试先调整三个契约：左侧可找到创建按钮、更新推荐仍须明确点击、气泡重复提交后 2 秒消失。聚焦 38 项中 3 失败 / 35 通过，分别因入口仍在右侧、旧文案、旧 6 秒计时；实现后全量 Vitest 19 文件 103 通过，ESLint/tsc/build 通过，构建 1854 modules。E2E 文件同步按钮名和提示等待上限，但用户决定先关闭后端稍后重开，本轮未启动后端、未执行 E2E；不能沿用上一轮 E2E 结果声称此次布局实测通过。新位置与浅色视觉待用户重开后验收。无提交、推送或进程启动。

## 同日批准连续执行：结束投票与历史回流

### 用户验收反馈后的候选详情与浮动投票修订（2026-10-06）

用户指出前一版仍左右失衡、收起后详情不够直观，并明确拒绝单地点主从选择设计。批准保留多个候选摘要/展开、详情使用查询页带天气图示的说明但不含 AI 推荐理由，以及参与者右下角浮动投票。Codex 据此把发起者汇总移左栏，调整列比例；候选详情复用 DailyWeatherList 和匹配标签（原推荐天气评分明确标示），新检查没有逐日适宜性时不伪造新建议。保留最终目的地优先显示及摘要决定按钮。公开邀请候选也采用可展开天气详情。

投票为非模态 Portal 面板，不遮罩或锁住正文。默认收起，打开聚焦首选输入，Escape/关闭按钮回到入口，隐藏但保留 VoteForm 草稿；提交成功才收起，失败保持草稿和错误反馈。仅 voting、未过期、已加入身份可显示，匿名投票仍用原 X-Plan-CSRF 边界；不改变首选/可接受模型或后端权限。手机为有高度上限的底部面板，长表单面板内滚动，页面仍可滚动。视觉自审发现重复“我的投票”标题，去掉冗余标题，并让公开候选卡片顶部对齐，避免一张展开强行拉长其他卡片。

真实 RED：调整展开详情不显示理由、旧流程改为点击投票入口，再新增草稿/Escape/明确提交与失败重试，聚焦 5 失败 / 12 通过（缺入口、旧解释仍出现）。实现后 17/17 通过；全量 Vitest 21 文件 / 127 通过。ESLint、tsc、build 退出 0。浏览器实现后补回归，不能写成先 RED：`PW_REUSE_SERVERS=1 ROAMBOT_E2E_BROWSER_CHANNEL=chrome` 配合 `node node_modules/@playwright/test/cli.js test e2e/floating-vote.spec.ts e2e/plan-detail-layout.spec.ts --workers=1` 四项通过（15.6s）；再单独 floating-vote 两项通过（9.1s）并截图自审，不能合称六项不同测试。

浏览器所有 `/api/v1/**` 请求为合成 fixture，不访问用户数据库。检查正文可滚动、浮层边界、天气 SVG、无推荐理由、草稿保留、提交 payload/匿名 header、结束状态不暴露投票、主详情双栏/手机单栏。截图位于忽略的 test-results/playwright 内，仅合成数据；截图自审不是用户验收。travel-plan.spec.ts 已适配新增打开入口，但本輪未执行真实后端完整业务 E2E。未改后端/数据库或重启服务，无依赖下载、commit/push。各项自动检查通过不代表视觉上已被用户认可。

### 后续计划详情布局调整（2026-10-06）

用户报告左栏内容结束而右侧候选逐日天气过长，批准紧凑管理栏、候选摘要按需展开、最终目的地优先、沿用主页配色及浅色短反馈。Codex 本轮仅修改 PlanPages.tsx、plans.css、页面测试、新增 plan-detail-layout.spec.ts 和记录；无子智能体、后端/数据库修改或依赖下载。

TDD：三个新增契约先失败，分别为编辑表单仍常驻、候选解释仍全展开、最终目的地未排第一；第一遍候选查询有多匹配测试错误，改为 queryAll 后重新取得真实 RED（3 失败 / 12 通过），不能将初始查询错误当作功能证据。实现后聚焦 15/15、全量 125/125（21 文件）通过。保留投票/关闭/决定/重新开放的旧契约；左栏由 ResizeObserver 判断高度是否适合吸顶，不引入独立滚动容器，公开邀请候选保持原展开行为。

浏览器几何回归在实现后添加，不声称先 RED。首轮两项目通过，但追加气泡不遮挡导航断言后，手机真实失败：气泡 top 92px，双行导航底边 104px。对照既有 validation-bubble，定位为缺少手机 112px header fallback；补响应式 top 后通过。最终执行 `PW_REUSE_SERVERS=1`、`ROAMBOT_E2E_BROWSER_CHANNEL=chrome`，`node node_modules/@playwright/test/cli.js test e2e/plan-detail-layout.spec.ts e2e/capsule-navigation.spec.ts --workers=1`，桌面/手机 4 项通过；所有 API 均合成 fixture，不读写运行中的账户/计划/数据库。

最终检查命令：`node node_modules/vitest/vitest.mjs run` 125 passed；`node node_modules/eslint/bin/eslint.js .`、`node node_modules/typescript/bin/tsc -b` 退出 0；`node node_modules/vite/bin/vite.js build` 1855 modules，退出 0。只覆盖此次 UI 专项浏览器流程，不是全量业务 E2E。自审核对收起不隐藏决定入口、保存失败不收起编辑、最终目的地 key 在决定后重建展开状态、公开页不启用 compact，以及手机不吸顶；用户实际视觉验收、Live 和真实手机尚待完成。没有提交/推送或更改用户服务。

### 后续独立调整：状态条收紧与历史胶囊工具栏（2026-10-06）

用户在查看真实界面后批准两项前端调整，未授权本轮后端或数据库变更。Codex 实现，非湛卢生成；未分派子智能体。保留原计划逻辑与历史二次删除确认，ShareActions 持续挂载以免工具栏收起丢失已创建分享状态。桌面状态条向左按内容展开，长文省略；历史工具栏用既有白底/青色主题，手机底部浮动，更多中的删除不默认暴露。

真实验证过程：新增 HistoryActionsMenu 测试并更新 PersonalPages 删除路径，聚焦 RED 为 3 失败 / 8 通过（缺 toolbar、缺更多操作、删除直接可见），Escape 属于原已通过回归，不写成新 RED。浏览器 RED 两项失败：桌面短状态实际仍为 340px；手机缺新 toolbar。最小实现后聚焦 11 通过；实现后补外部点击/重开清理、初始焦点/方向键两项回归，全量 **21 文件 / 122 通过**。这些后补测试不声称先 RED。

命令均在 frontend 执行，node 使用本机 codex-primary-runtime 的 v24.19.0 可执行文件：

- `node node_modules/vitest/vitest.mjs run`：122 passed，退出 0。
- `node node_modules/eslint/bin/eslint.js .`：退出 0。
- `node node_modules/typescript/bin/tsc -b`：退出 0。
- `node node_modules/vite/bin/vite.js build`：1855 modules，CSS 51.56kB / JS 386.64kB，退出 0。
- 设置 `PW_REUSE_SERVERS=1` 与 `ROAMBOT_E2E_BROWSER_CHANNEL=chrome` 后，`node node_modules/@playwright/test/cli.js test e2e/capsule-navigation.spec.ts --workers=1`：桌面/手机 **2 passed**，最后一轮 8.7s、退出 0。测试拦截所有 `/api/v1/**` 请求，用合成账户、计划、历史和分享响应；不读写实际演示数据库。覆盖长短标题宽度变化/上限、工具栏横向边界、删除默认隐藏、Escape 返回焦点、创建分享后重新打开保留复制/撤销、撤销后恢复创建入口。不是全量 E2E，也不能代替关闭投票/历史真实回流的业务 E2E。

本轮仅改前端、测试及开发记录。人工自审检查了 ShareActions 状态保留、Portal 外部点击包含判定、删除仍交给父页确认，以及移动端/减少动画规则；没有独立第三方代码审查。未改后端/数据库，未重启本地服务，未下载依赖，未 commit/push。系统 Chrome 浏览器检查不代表真实手机、所有浏览器或最终人工视觉验收；不支持 intrinsic width 动画的浏览器可正常显示宽度但动画效果待验证。

用户批准补充设计和实施计划后，由 Codex 在本工作区连续开发，没有分派子智能体。新增 closed（待决定）及确认结束入口；关闭保留投票，发起者可决定或重开，匿名页只读汇总；过期拒绝写入。SQLite 0005 迁移仅在临时测试库运行，保留关联行，不清用户数据。历史重查恢复原条件、新结果与当前账户所有权，回到左右工作区；历史查看保持快照。路由内存传递覆盖 sessionStorage 不可写的情况。

真实过程：后端新增 4 个 RED（3 个缺 API、1 个旧 CHECK），实现后修正原版本断言 0004→0005；页面 4 个 RED 后补 closed 操作和状态；历史回流路由失败与模块不存在后实现，并修正旧测试缺 AuthProvider。自审补缓存旧值和舍入合计 101 的两项 RED 后修正。并发关闭与改票、导航标示是在实现后补测，不能写成 RED。完整命令、数量及失败分类见 [VOTING_CLOSE_PROGRESS.md](VOTING_CLOSE_PROGRESS.md)。

本轮实测：pytest **316 passed**，Vitest **20 文件 / 117 passed**，Ruff/ESLint/tsc/build 退出 0；构建 1855 modules。扩展关闭/重开/决定和历史回流 E2E 文件，**未运行浏览器 E2E**，未启动用户服务，未执行用户数据库迁移。旧数据库重启不会自动升级 CHECK，需备份、schema/版本审核和副本验证后再获准升级。自审不是独立审查；Live、公网协作、真实手机及最终用户验收仍未验证。无 commit/push/PR/merge、无依赖下载或 Docker。
