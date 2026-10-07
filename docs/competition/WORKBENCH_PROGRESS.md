# 执行记录 — docs/superpowers/plans/2026-10-06-plan-decision-workbench.md

## 2026-10-07 最终目的地标记移位

- 用户截图指出已决定卡片标签额外占行、左右不对称，批准标记放在名称旁。Codex修改PlanComparison.tsx与plans.css，不作为湛卢生成证据，不改后端、分数、排序或选择权限。
- 测试先行：新增final-candidate-alignment.spec.ts，使用合成计划拦截API；发起者/参与者×桌面/手机四项均有效RED，地址位置偏移50px（预期不超过1px）。移位后四项GREEN，逐项验证地址、指标、天气、操作行；长名称再次验证指标对齐和页面无横向溢出。
- 实现：标记改为头部浅青胶囊；名称单行省略，完整文字保留在title与可访问名称。保留最终卡片底色与边框，通用卡片头部仍52px最小高度。仅局部样式，无新增依赖。
- 命令均使用既有Node v24.19.0完整路径：`node node_modules/vitest/vitest.mjs run` 150/150（24文件）；`node node_modules/eslint/bin/eslint.js .`、`node node_modules/typescript/bin/tsc -b`退出0；`node node_modules/vite/bin/vite.js build`退出0，1860 modules，CSS66.59kB / JS399.60kB。
- 系统Chrome、Mock/demo、隔离8010/5180、`.playwright-data/final-marker-20261007`：`node node_modules/@playwright/test/cli.js test`最终42/42（1.6m）、退出0。已有NO_COLOR/FORCE_COLOR警告不影响退出；无Live调用。
- 作者自审确认仅显示位置改变，非独立审查；未执行用户视觉验收/真实手机验证。未commit/push，不操作用户8000/5173或data-competition-demo；刷新前端即可，无需重启后端。

## 2026-10-07 两端式紧凑页头（最新）

- 用户纠正“标题右侧留白不可改”的理解，批准缩小标题、左概况右进展的合成数据Demo，再明确“实施”。Codex仅修改PlanPages.tsx、plans.css、测试和文档，无子智能体，无后端/依赖/实时刷新；不作为湛卢生成证据。
- 先补页面5项RED：真实已加入分母、隐私进展不虚构、closed/decided/ended下一步；原18项通过。浏览器先RED4/4缺少具名同行进展区域。随后实现共用PlanHeader，标题最高1.5rem、删除重复城市说明，日期/状态/候选数左侧，右侧浅青文字进展与提示，740px以下上下排列，不改变下方投票布局。
- 投票分子/分母来自可见summary，或授权participants计数；分母非expected_count。不可见时先加入/先投票，不伪造0票、不新增请求或绕过先投后看。closed发起者等待自己决定、参与者等待发起者；decided显示最终地点，ended优先显示留档。详情页和邀请页共同适用。
- 首次全量36/38：同行流程两尺寸均因旧全页getByText('1/2 人已投票')同时匹配新页头与既有汇总而失败。第二轮仍36/38：另两处2/2断言也有同类歧义。三处统一限定具名同行进展区域，仍要求准确人数，不使用first/force/放宽断言。专项完整流程2/2（36.7s）；最终全量38/38通过（2.3m）。这是旧测试定位失效，不把它伪称产品功能RED。
- 实际命令在frontend，显式codex-primary-runtime Node24.19.0：`node node_modules/vitest/vitest.mjs run` **24文件150通过**；`node node_modules/eslint/bin/eslint.js .`及`node node_modules/typescript/bin/tsc -b`退出0（测试定位调整后再复核退出0）；`node node_modules/vite/bin/vite.js build`成功，1860 modules、CSS66.19kB/JS399.51kB。
- 最终 `node node_modules/@playwright/test/cli.js test --workers=1` **38/38、2.3m、退出0**，系统Chrome、Mock/demo、自建8010/5180、`.playwright-data/compact-header-20261007`，PW_REUSE_SERVERS=1。新4项为合成API fixture几何/隐私布局测试，含长标题；全量另含隔离Mock业务，不代表Live/真实手机。作者查看发起者桌面、参与者手机截图，四张存 evidence/compact-header-{owner,voter}-{desktop,mobile}-20261007.png，自审非独立审查。
- git diff --check无空白错误（LF→CRLF警告），HEAD仍00f4e80。仅停止本轮测试服务PID31244/19152，用户8000/5173与data-competition-demo不操作；未提交/推送，既有未提交工作完整保留。正式页头待用户刷新验收；当日说明用户已验收。

## 2026-10-07 上传前验证

- 用户批准当前工作备份至比赛仓库同名分支，不创建PR/merge或部署。由Codex执行，无子智能体。
- 新鲜验证：pytest317、Ruff通过；Vitest150（24文件）、ESLint/tsc/build通过；系统Chrome全量Mock E2E42/42（4.2m，退出0）。隔离8010/5180、backup-20261007，不操作用户服务或数据。后端首轮错误工作目录导致3项配置路径失败，改正目录后全量通过；不是业务RED。
- Windows测试服务退出等待时，只停止核实的本轮31520/12948进程，之后Playwright正常返回。暂存检查清理PlanPages一行尾随空格，无行为变更。美团查询仍为讨论，无接入或计费已确认的声明。

## 2026-10-07 当日说明浮层（最新）

- 用户指出内联展开移动按钮、撑高卡片，批准锚定小浮层。Codex实施，无子智能体，仅前端；不归入湛卢原生证据，无后端/API/依赖改动。
- 先补2条组件测试：旧实现无具名dialog、Escape不能收起，聚焦2失败/6通过；浏览器双角色×两尺寸4项均因缺少浮层失败。有效RED，不是环境失败。实现后新增断言通过；旧“最新天气说明”断言原先在card查找，改在具名dialog查找，同样保留最新说明可见、旧说明不存在的契约。
- 新增DayExplanationPopover通过Portal避开卡片裁切，焦点不滚动页面；按钮aria-expanded/haspopup/controls、具名非模态dialog、外部点击/Escape返回按钮。Escape捕获避免同时关闭投票栏。PlanComparison统一管理一个展开ID，切换日期清除。DailyWeatherList新增默认true的showSummary，只在比较卡片设false，查询页既有说明不变。
- 首次专项4/4通过；GREEN后追加右侧长说明与投票共存回归，首轮全量32通过/2失败：按320px计算定位但内联maxHeight覆盖CSS上限，长说明实际超出底部。修正为可用空间与320px取小值，不截断内容，内部滚动。最终全量34/34。截图看似右侧裁切，随后补documentElement.clientWidth可用宽度断言专项4/4，通过证实没有实际越界，未因此追加产品修改。
- 最终命令在frontend，显式codex-primary-runtime Node24.19.0：`node node_modules/vitest/vitest.mjs run` **24文件145通过**；`node node_modules/eslint/bin/eslint.js .`、`node node_modules/typescript/bin/tsc -b`退出0；`node node_modules/vite/bin/vite.js build`成功（1860 modules、CSS65.06kB/JS398.16kB）。
- `node node_modules/@playwright/test/cli.js test --workers=1` **34/34、2.2m、退出0**；随后新增可用宽度断言运行 `test e2e/day-explanation.spec.ts --workers=1` **4/4、11.7s、退出0**。系统Chrome、Mock/demo，隔离8010/5180、`.playwright-data/day-explanation-20261007`。专项为全API合成fixture，全量另含隔离Mock真实业务流程，不是Live或真实手机。原RED服务Windows teardown停留，复用自建服务完成验证后再停止，仅本轮PID1732/21920，不动用户服务。
- 几何断言保持按钮x/y、卡片高度、下方表格y误差<1px；同按钮原位置关闭、Escape焦点、外部点击、单浮层、日期回来不恢复、横向无溢出、长说明内部滚动。作者查看桌面/手机截图，四张存 evidence/day-explanation-{owner,voter}-{desktop,mobile}-20261007.png；自审非独立审查。用户视觉验收待确认，未提交/推送，无需后端重启。

## 2026-10-07 两个展开入口的可见性提醒（最新）

- 用户拒绝给管理计划/当日说明加提示，仅批准全部日期与第二个对比候选。Codex实施，无子智能体；不归入湛卢原生开发证据。
- RED：共享模块不存在，导入失败尚未执行断言；两个页面新断言缺提示失败，原22项通过。实现可见性判断、共享2秒Portal提示、两处接入。GREEN首轮2项仍失败：收起后等下一动画帧才清提示，改为点击时同步清除。143项随后通过。
- 可见性看新内容开头60px/120px，不要求长表整块塞进屏幕；计入页面、固定页头及祖先滚动/裁切区域。提示仅用户操作生成，不因查询或刷新自行触发；重复展开重置计时，不叠加；收起与点击查看对比清提示，第三候选不重复触发。管理、详情、评分、投票行为不变。
- ESLint曾报Fast Refresh组件与hook同文件导出；拆成 RevealNotice.tsx/useRevealNotice.ts，不屏蔽规则。浏览器首轮2通过/2失败：误用计划快照作为查询fixture，缺distances/provider_id导致查询页渲染失败；补齐查询结构后4/4通过（20.2s）。此失败不是产品RED，不改产品兜底掩盖fixture问题。
- 最终命令在frontend，显式codex-primary-runtime Node24.19.0：`node node_modules/vitest/vitest.mjs run` **24文件143通过**；`node node_modules/eslint/bin/eslint.js .` 与 `node node_modules/typescript/bin/tsc -b` 退出0；`node node_modules/vite/bin/vite.js build`成功（1859 modules，CSS64.56kB / JS396.17kB）。
- 全量 `node node_modules/@playwright/test/cli.js test --workers=1` **30/30、2.0m、退出0**。系统Chrome channel、Mock/demo、隔离8010/5180、`.playwright-data/reveal-notice-20261007`。新专项全API合成fixture检验桌面/手机实际裁切、无提示分支、2秒消失、第三候选不重复及胶囊横向边界；全量另含隔离Mock真实业务流程。不代表Live/真实手机，用户最终视觉仍待确认。
- 作者查看桌面全部日期与手机对比胶囊截图，四张存于 evidence/reveal-{all-dates,comparison}-{desktop,mobile}-20261007.png。自审非独立审查；未提交/推送，未修改用户演示数据或停止8000/5173。仅结束本轮23644/15344测试服务。

## 2026-10-07 三层工具栏（最新）

- 用户批准标题右侧留空，管理/投票同行比较标题，日期/天气操作下一行。Codex实施，仅前端，没有子智能体、后端改动、数据操作或提交推送。
- 页面测试先RED：标题区仍含管理按钮，聚焦1失败/17通过；浏览器先RED：全部日期和天气按钮间距73.375px超过14px上限。实现共享外层操作行及内部日期行，按钮用两列max-content Grid、12px间距，时间跨两列且不参与固有宽度。
- 首轮全量24通过/2失败：旧comparison-toolbar规则覆盖新顶对齐（标题中心差12.8125px）；手机展开底部投票时管理按钮被遮住。提高新规则选择器特异性；手机测试显式收起面板后再管理，不强制点击、不放宽断言，草稿仍验收。第二轮25通过/1失败：标题40px与按钮44px中心差2px；将标题行最小高度统一44px。
- 最终实际命令：frontend内 `node node_modules/vitest/vitest.mjs run` **138/138、23文件**；`node node_modules/eslint/bin/eslint.js .`、`node node_modules/typescript/bin/tsc -b` 均退出0；`node node_modules/vite/bin/vite.js build`成功（1857 modules，CSS64.56kB / JS394.11kB）。node为codex-primary-runtime v24.19.0显式路径。
- `node node_modules/@playwright/test/cli.js test --workers=1` **26/26 passed（1.9m）、退出0**。Chrome channel、Mock/demo、8010/5180、隔离 `.playwright-data/toolbar-rows-20261007`，复用本轮创建的临时测试服务。用户8000/5173与演示库未操作。
- 全量通过后仅补收起状态截图采样，不改产品代码；专项双角色×两尺寸复核另记录。截图为合成API fixture布局，完整套件另含真实隔离Mock业务流程，不代表Live/第三方服务或真实手机验证。作者自审及截图检查不能代替用户视觉验收。
- 收起状态截图专项 **4/4 passed（15.8s）、退出0**，作者查看桌面展开/手机收起截图，四张收起状态存于 `evidence/toolbar-rows-{owner,voter}-{desktop,mobile}-20261007.png`。仅结束本轮临时测试服务14052/27688，保留用户8000/5173；git diff --check退出0（LF→CRLF提示非空白错误）。

- 2026-10-06：用户批准正式实施；当前 experiment/ui-clean-a，既有未提交修改保留。
- Ruling: 在用户批准的当前工作区直接执行，不新建 worktree、不提交，避免丢失尚未提交的同行计划实现。代价：需依靠聚焦文件审查隔离本轮改动。
- Ruling: 禁止子智能体，最终由作者单独自审而非独立 reviewer；验证证据与此限制分别报告。
- Pre-flight: Task 1 的 PlanComparison 与 Task 2 的 PlanVotePanel 均使用既有 TravelPlan/PlanCandidate；Task 3 编排，Task 4 几何验收，无新 API。
- Task 1/2: 正在编写 RED 测试；尚未实现。
- Task 1/2: 模块不存在的导入 RED → 共享组件实现 → 8/8 GREEN。页面旧契约更新后 2 项有效失败，接入后聚焦 25/25；全量 Vitest 135/135、ESLint 通过。
- Task 4 RED: 尚无 CSS 过渡时两个桌面测试宽度恒定（1200/940），失败符合预期。CSS 接入后桌面 2 项、参与者手机 1 项通过；发起者手机管理被投票面板挡住。
- Ruling: 打开管理时先收起投票（两端一致），保留未提交草稿 — 解决手机底部面板拦截编辑的真实失败 — 代价：桌面管理与投票默认不同时展开，可再手动展开投票。
- 管理/投票切换回归先补 RED（面板仍可操作），再改打开管理动作；后续验证待执行。
- 管理切换修复后，新工作台 4/4（两个角色×桌面/手机）、详情布局 2/2通过。旧浮层测试需等待新 280ms 动画结束再采样，保持原矩形边界断言，不强制紧凑页面产生垂直溢出。
- 全量 Vitest 136/136，ESLint/tsc/build 通过。全量浏览器检查发现两项旧问题：历史重新查询测试仍断言进入快照（已有设计已改为返回工作区）；创建计划登录框在 sticky/滚动左栏内，被右侧内容拦截点击。
- Ruling: 只修 CreatePlanControl 登录框挂载位置，portal 到 body，复用原 AuthDialog 和所有鉴权/注册逻辑 — 同行计划真实业务 E2E 已在创建账户点击处失败，需恢复可操作流程 — 代价：新增一处前端文件审查，不改账户 API。
- Ruling: account-personal-data 旧测试改为先验收重新查询返回工作区，再单独打开原快照；删除入口跟随既有更多操作 — 不更改历史产品代码，保留原业务覆盖 — 代价：测试选择器与已批准行为保持同步。

## 2026-10-07 继续执行

- Portal 修复及历史测试更新后，全量浏览器 24/24 通过（4.1m）。Windows 下 Playwright 等待自己创建的 webServer 退出；结束本轮已确认 PID 的两个临时服务后，命令正常返回退出 0。未停止用户 8000/5173 服务。
- 实现后补测：1/2 候选无补空卡、减少动画、Escape 返回入口、重复提交防护。这些不是先 RED 的证据。
- 全量 Vitest 23 文件 / 137 通过；ESLint、tsc、Vite build 退出 0，1857 modules，CSS 63.70kB / JS 393.67kB。
- 新增两项浏览器边界后复跑完整 **26/26 passed（3.2m）、退出 0**。同样只结束自己创建的临时服务使 Windows teardown 返回。
- 自审：owned/public 路径和匿名 CSRF 沿用；summary=null 不重建汇总；失败保留计划及草稿；隐藏投票 inert；关闭/决定/结束均禁止编辑。没有独立 reviewer。
- 已查看并保存双角色桌面/手机截图至 evidence/workbench-*-20261007.png；桌面最后采样 1024px，手机 390×650。自动几何和作者截图检查不能代替用户视觉验收。
- `git diff --check` 退出 0，只有 LF→CRLF 提示。分支和 HEAD 未变；未提交/推送。本次批准实施范围停止；1 日天气范围特例、全部管理危险动作的逐项浏览器测试、Live/公网/真实手机不在已验证结论内。

## 2026-10-07 用户验收后的天气与工具栏修复

- 用户批准修复按钮错位、最新天气无逐日建议、空的当日说明入口。范围是既有流程，不新增 AI/Provider 调用，不改推荐排名、数据表或用户数据。
- RED：后端天气检查契约缺 `daily_suitability`（1失败）；比较组件新增/扩展断言2失败（未使用新建议、空说明仍有按钮）；桌面/手机几何各失败，按钮 y 差12.3125px。
- 实现：WeatherCheck 增加逐日建议；序列化从最近成功保存的天气与候选场景类型复用 score_daily_weather。失败时仍使用最近成功天气/建议并保留失败与时间标记，首次失败无数据返回空建议。读取旧天气记录即可生成，不改快照/原评分，不写数据库，不请求 Provider。
- 前端使用最新检查建议，不套旧快照建议；当日无天气/非空说明时不显示展开按钮。工具栏顶对齐，按钮等高，说明置于天气按钮下方，手机自然换行。
- 聚焦后端1通过、比较5通过。全量后端317通过；Ruff初次两个测试行长报错，格式修正后通过。全量前端初次2失败：旧页面 fixture 用空天气检验展开；补充完整天气/建议并区分外层卡片与嵌套天气后，138/138通过。没有放宽“空说明隐藏”的断言。
- 曾中止一次全量E2E：误复用RED阶段未重载的临时后端；仅结束本轮隔离服务并重启最新代码，没有把被中止运行作为通过证据。最终完整E2E **26/26 passed（2.2m）、退出0**，隔离 `.playwright-data/weather-final-20261007`。
- ESLint/tsc/build通过，CSS63.81kB / JS393.76kB。新增强降水/风速回归为实现后补测：确认建议由新天气生成、快照评分不变、公开返回同一建议、GET不依赖Provider；不声称先RED。
- 用户需手动重启8000后端一次，再刷新前端。无需重建计划、数据库迁移或再次检查天气；保留旧演示目录。未自动重启用户服务，未commit/push。
- 截图复核按钮同线及检查后的逐日建议，保存 `evidence/weather-toolbar-{desktop,mobile}-20261007.png`；真实Mock业务E2E原输出的截图也已更新。系统Chrome不代表真实手机，未验证Live；作者自审不是独立审查。
