# RoamBot 公网阶段版本 · 2026-10-27

目标为将本地国内功能版本发布到原公网 https://roambot-production.up.railway.app/ ，不扩展海外功能。

## 发布产物

- 源码基线：`7b96ea5` 加当前已确认的未提交阶段改动，未暂存共享工作区、未推送 Git。
- 发布前补正式配置 `ROAMBOT_DISCOVERY_ORCHESTRATION_MODE`，选择 `source`，与本地 open-places-v3 流程保持一致；保留 `legacy` 默认兼容旧启动方式，非法值拒绝启动。
- 生产模型保持 qwen3.7-plus，live/non-demo，Secure Cookies 保持启用；超时与本地候选一致（Provider 15秒，assistant 8秒）。
- 用户明确授权把本地现有 Tavily 密钥通过 stdin 写入指定生产服务的密钥变量；没有打印或写入代码、日志、发布包。先前自动审批拒绝在取得该项明确授权后解除。
- 初次源码构建 `17617a24-25e1-4084-8a4b-21ed8769e0b5` 在云端 pip wheel 阶段失败，详细包管理器输出不可得；npm 阶段为随构建取消而退出137，不据此归因为前端故障。本地相同应用源码 wheel 构建成功，不能确认云端失败根因。
- 最终发布改用已验收前端 dist 和固定 Linux/Python3.13 wheels，离线安装，避免云端再次解析浮动依赖。应用 wheel 内112个文件逐字节与冻结源码一致；运行依赖按本地已测试版本固定，Linux离线解析通过。
- 候选部署：`97363965-4a81-4970-8204-a155c42f331b`。发布前旧部署为 `b53320af-d347-4b9e-be47-8422dc23e797`。

## 数据与恢复

- 维持原 production 服务、单副本和原 `/data` 持久化卷。
- 当前 Railway 套餐不支持卷快照，普通 SSH 又缺少已有密钥。本轮不升级套餐或扩大 SSH 权限。
- 发布专用启动脚本在应用初始化前使用 SQLite backup API 将数据库备份到 `/data/release-backups/stage-20261027/`，校验 integrity_check，权限限制为目录700/文件600，重启不覆盖原副本。只有日志确认后才算生产备份实际完成。
- 隔离检查确认旧版15张表字段与 DDL 不变，仅新增 itineraries、itinerary_workspaces；没有破坏性迁移。WAL数据库一致性备份及再次启动不覆盖原备份的检查通过。
- 此恢复副本位于同一持久化卷，不能当成异地备份。

## 验证证据与边界

- 正式配置/启动相关24项通过；冻结包推荐历史和命令接口22项通过；行程和健康接口7项通过，合计53项。本轮均为Mock/隔离库，未重复此前整套界面测试。
- 最初配置测试误加载旧安装包导致3项失败，显式指定工作树PYTHONPATH后24项通过；不算作生产故障。备份夹具暴露连接未显式关闭导致Windows rename失败，已修复并复查。
- 局部Ruff发现 main.py既有导入排序问题，未以无关格式改动扩大本轮范围；不声称全项目lint通过。
- 发布包、源码和产物SHA256清单、非敏感配置回执、测试XML、备份检查结果在 `test-results/public-release-20261027/`，该目录Git忽略。
- 不含本地用户数据库、会话、凭据库或密钥。不额外发起真实推荐/路线/天气查询，不把部署与只读页面通过等同于推荐质量验收。

## 实际发布结果

- Railway最终部署 `97363965-4a81-4970-8204-a155c42f331b` 为 SUCCESS，实例 `07a66107-a7f2-49bd-957a-83de87fc3c0a` RUNNING，单副本。
- 启动日志确认 `/data/release-backups/stage-20261027/roambot.db` 实际生成，integrity=ok，SHA256 `7b7004c9f063617539d51f1caa863412634fb985bfe2262e937fa2ef76f1a9d4`；随后应用启动完成。日志确认 workflow=source、model=qwen3.7-plus、search_configured=true。
- 公网 `/`、`/explore`、`/itineraries`、`/api/v1/health`、`/api/v1/regions`、`/api/v1/maps/config`、`/api/v1/itineraries` 全部HTTP200，health=ready，地图配置启用。没有打印地图Key。
- 公网HTML与验收构建一致，JS `index-CqfXAf8f.js`、CSS `index-CCBvbT39.css` 逐字节匹配，SHA256分别为 `e6f400115b12edd4eafe1c105a9520b37dcdcb246dcbbc8f40b39ddc25a1e5e1`、`a21af00a2d72b748fbacce678f172fecd95f315c69277188e6cf22ed25b0bf4d`。
- 1440×900浏览器已查看新版首页，登录/注册、开始探索、行程中心、同行计划均存在，实际点击开始探索抵达新版 `/explore`。截图 `public-home-desktop.jpg`。随后浏览器控制超时两次，没有把该工具故障记为业务故障；未完成公网手机和行程页的浏览器专项检查，复用相同构建此前本地响应式证据，保留公网交互边界。
- 初次只读验收脚本误禁用系统代理导致连接超时；恢复既有系统代理后7个HTTP路径和前端字节校验通过，不归因为后端失败。
- Git共享工作树仍未暂存、提交或推送。平台发布已完成，不代表Git阶段存档也已完成。
- 无新增真实模型/检索/路线/天气验收调用，无真实账号、收藏、行程、分享写入。海外、定位物理精度和完整真实多轮质量仍按阶段清单保留待验。

## 回退方式

旧部署ID `b53320af-d347-4b9e-be47-8422dc23e797` 与镜像仍由Railway保留，可从部署历史回退代码。现有表没有修改，新增表旧版可忽略；生产数据库恢复必须在停止写入并再次确认后按SQLite恢复流程执行，不能把恢复副本直接覆盖正在使用的数据库。恢复副本与应用在同一卷，不能保障卷本身丢失的情况。
