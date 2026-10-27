# 卡片图片试版 · 2026-10-26

用户先授权提交当前版本作为回退点，再试一张图片。

## 回退点

- 本地提交：`7b96ea5`，`chore: checkpoint current RoamBot before card photo preview`。
- 标签：`checkpoint/pre-card-photo-20261026`。
- 提交包含此前当前分支的项目源码、测试和说明；没有推送、部署或重启实际服务。它是工作区快照，不意味着未同步的后端代码已在8034上线。
- 8034前端构建另存 `test-results/card-photo-20261026/baseline-dist`，仍是index-5XwQvl4e.js/index-D7BrzEBH.css。数据库、运行日志、依赖和凭据不进提交。
- 本轮照片试版保持未提交；不需要恢复主站，8034尚未替换为试版。后续如要撤回源码只撤本轮图片变更，不做整树reset/clean，以免损失新工作。

## 当前第二版：详情照片，外层无图

用户否决首版：小卡横幅损失信息、排版偏高、详情没有照片、竖图无证据。已撤掉外层照片，主详情及地图卡展开后使用完整画面；不固定横幅比例，object-fit:contain，横图上下布局，竖图桌面照片/文字并排、移动端上下布局。作者与许可移到照片下方，不盖住画面。页内大图复用OverlayHost，关闭/Escape恢复详情和触发焦点。

追加真正500x889竖图：三猎拍摄的九溪十八涧石板小径，2016-08-07，CC BY-SA4.0，仅绑定相符公开夹具；杨公堤960x720横图继续使用。来源详见资源归属文件。没有自动选图或运行真实查询。

27项相关检查、类型、局部lint、构建通过。8140浏览器确认外层0张照片，横图详情约499x374、竖图详情约211x374且比例保持；390px窄屏完整竖图与页内大图已实测，大图关闭回原详情。首次大图实际发现旧OverlayHost上下预留空间使底部溢出，给大图独立蒙层留白后修复；最终720px桌面视口大图y91至681，完整可见。外链大图点击没有在IAB产生可用新页，因此改为页内查看，不记外链成功。

当前预览8140 worker16336、session1307，构建index-B1s1b2hu.js/index-BewwdulS.css。8034只读HTTP200，原构建index-5XwQvl4e.js保持；不动8026/部署/提交推送，回退点仍7b96ea5。桌面tab11保留deliverable并停留竖图详情，窄屏临时页关闭。截图detail-landscape.png、detail-portrait.png、detail-portrait-mobile.png、portrait-viewer.png、portrait-viewer-mobile.png位于test-results/card-photo-20261026。非手机实机验收，自动选图和实际资料覆盖率仍未接入。

## 首版内容（已否决）

可选photo元数据和独立照片组件，外层卡片顶部12:5横幅，object-fit:cover及明确焦点；没有图片或加载失败均不保留空图片区，保留原文字与动作。原始照片像素未改，只由CSS裁切。初次16:9实际观察卡片偏高，缩至12:5后单卡约402px（当前桌面缩放/字体下）。

只有8140隔离服务的公开杨公堤夹具带photo；没有按关键词自动选图、没有把同一张照片用于其他地点、没有修改真实用户推荐记录。照片为钉钉2021年9月18日杨公堤实拍，CC BY-SA 4.0，图上保留作者/来源/许可及裁切说明，具体归属见frontend/public/assets/card-preview/ATTRIBUTION.md。

## 首版验证与体验（历史记录）

- 图片组件2项检查、类型检查、局部ESLint、构建通过；构建保留既有chunk体积警告。
- 8140浏览器实际确认仅1张图片、960x720已加载；桌面裁切/图上归属可见，390px窄屏滚动和加入比较切换成功，未验收手机实机。
- 截图：test-results/card-photo-20261026/desktop.png、mobile.png。没有打开图片来源页面或真实地图、没有新模型/推荐/天气请求。
- 预览：`http://127.0.0.1:8140/motion-results`，进程34020，exec session 21850，保留以供用户查看；用户数据位于独立Mock目录。浏览器桌面预览tab 11标记deliverable，窄屏临时页关闭。
- 预览构建index-G5LeTKfx.js/index-TtKzNC-x.css；8034/8140均HTTP核对，记录test-results/card-photo-20261026/checkpoint.json。主站8034原版未动，8026未动，未提交试版、未推送。

## 已放弃 · 2026-10-26
用户认为图片方案效果不合适，决定转向无照片装饰。已将5个现有前端文件恢复至7b96ea5；新增图片/组件/测试移至test-results/card-photo-20261026/abandoned保留，前端dist恢复原构建。8140本轮预览session1307关闭。8034原版HTTP200、index-5XwQvl4e.js不变，无业务查询、部署或其他服务操作。此前图片截图仅作被否决方案记录。

