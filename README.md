# RoamBot

当前阶段包含对话推荐、地图联动、收藏、历史、同行计划与行程中心。2026-10-27阶段产物已发布到公网；本次主仓库集成与检查边界见 `docs/MAIN_INTEGRATION_2026-10-27.md`，发布记录见 `docs/PUBLIC_RELEASE_2026-10-27.md`。
比赛仓库的 `submission/2026-10-15` 分支保留原始 388 文件快照，提交 `44ecc7b`；
对应原演示发布 `b53320af-d347-4b9e-be47-8422dc23e797`（2026-10-14）。
`SOURCE_MANIFEST.json` 仅用于核对该参赛基线，不代表当前开发分支的文件哈希。
改造范围和当前验收见 `docs/PROJECT_HANDOFF.md`、`docs/conversational-business-acceptance.md`。

## 使用入口

当前阶段公网体验：https://roambot-production.up.railway.app （已更新为2026-10-27阶段版）

评委本地复现推荐使用Mock模式，无需配置真实服务凭据。Mock的自然语言解析仅支持有限示例；
可用条件拼图手动设置苏州站、明天、湖景等条件。Mock不替代线上真实模型和地图的验收。

### Docker方式

安装Docker并在本目录执行：

```shell
docker build -t roambot:submission .
docker run --rm -p 8000:8000 -v roambot-submission-data:/data -e ROAMBOT_PROVIDER_MODE=mock -e ROAMBOT_DEMO_MODE=true roambot:submission
```

然后打开 http://127.0.0.1:8000 。也可以执行 `docker compose up --build roambot`。
首次构建需要网络下载Node/Python依赖；依赖和构建产物没有打入源码包。

### 不使用Docker：Windows PowerShell

安装Python 3.12或3.13，以及Node.js 24。在本目录执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
Push-Location frontend
npm ci
npm run build
Pop-Location
$env:ROAMBOT_DATA_DIR = 'data-submission'
$env:ROAMBOT_PROVIDER_MODE = 'mock'
$env:ROAMBOT_DEMO_MODE = 'true'
.\.venv\Scripts\python.exe -m uvicorn roambot.main:app --host 127.0.0.1 --port 8000
```

新数据库在初次应用启动时初始化。现有数据库迁移脚本位于`backend/alembic/`；
本包不含任何真实数据库或已登录账号，需要自行注册演示账号。

## Live方式与凭据

Live模式使用高德、和风天气和兼容OpenAI协议的模型服务，必须由运行者配置自己的凭据。
代码包不含API Key、主密码、Cookie、Token、加密凭据库或生产数据库。
用 `.\.venv\Scripts\python.exe -m roambot.cli credentials --help` 查看凭据配置入口；
CLI通过隐藏交互输入接收凭据。相关服务配置见`backend/src/roambot/config.py`和Compose的live profile。
地图JS能力还需要浏览器地图Key与安全码，不能将已有线上凭据复制到本包。

## 功能与验收范围

支持推荐、指定地点评估、同行出发地与权重、地点详情和地图、条件聊天、收藏、比较、历史分享，
以及计划创建、匿名邀请、首选/可接受投票、天气复查、关闭投票和定案。
当前开发分支接入 60 项具名业务/页面动作：模型提出有序步骤，后端校验对象、身份和状态后执行，
前端同步查询、收藏、计划、邀请、投票、天气、历史分享及页面浮层。原有按钮保留。
登录密码仍通过账户表单输入，不交给模型；凭据管理与部署操作不向聊天开放。
多步方案、确认、并发与重试分别受程序约束；真实模型验收范围见本分支验收文档。

本地体验版支持 `Alt+/` 唤起或聚焦当前层的聊天；跨页面和浮层可继续发指令，不需要先点击聊天球。
可直接按名称操作自己的计划、收藏和历史。登录/注册由聊天打开，密码只在安全表单中用键盘输入。
无鼠标验收与剩余边界见 `docs/mouseless-control.md`，不能把工具数量当作任意表达都正确的证明。

以下为参赛基线的历史记录，不作为当前改造版本的验收：
2026-10-14线上手机宽度390×844完整13阶段交互通过，桌面完成业务串联后对地图修复做专项复验。
原句模型、上海同行角色、金鸡湖原名评估通过；地图底图已实际查看。
正常生产链路可能使用有效缓存，部分推荐理由回退本地模板；真机/Safari和泛化自然语言仍有验收边界。
详见`docs/验证与版本.md`。脚本在`docs/competition/移动杯视频操作脚本.md`，SRT共33条、4分35秒，
源码包不含最终录制视频。

## 自动测试

安装上述开发依赖后执行：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
Push-Location frontend
npm test
npm run build
Pop-Location
```

Playwright旅程测试通过`frontend/playwright.config.ts`配置，运行前安装浏览器：
`npx playwright install chromium`，然后执行`npm run e2e`。
日期与外部服务状态会随时间变化；历史通过记录不等于任意日期的新运行结果。

## AI协作归属与材料

湛卢候选比较开发记录见`docs/competition/AI_CODING_PROCESS.md`；
后续Codex同行增量单列于`CODEX_PLAN_IMPLEMENTATION.md`。这些记录不能替代湛卢原生IDE截图。
作品说明文档、实际演示视频和原生过程证据应作为参赛材料另行附上。

文件哈希见`SOURCE_MANIFEST.json`。本包没有携带Git历史、依赖目录、个人数据或测试临时产物。
