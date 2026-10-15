# Conversational Business Implementation Plan

**Goal:** 自然语言覆盖现有用户业务及页面动作，保留按钮。
**Architecture:** 受约束工具注册表、现有 API 执行器、持久化操作记录及显式前端动作桥接。
**Tech Stack:** 现有 FastAPI、Pydantic、SQLite、React、TypeScript，无新增框架。
**Spec:** ../specs/2026-10-15-conversational-business-design.md
**Execution:** 用户已授权本会话直接实施；不使用子代理、不部署。

## Global Constraints

- 身份从会话取得，权限沿用现有接口；不接受任意 URL 或模型提供的地点资料。
- 只操作独立工作树及测试数据库；真实 Provider 验证单独计量。
- 记录完整范围与未完成项，不把注册了工具等同于全站已验收。

## Review Focus

- 同名/指代不明时追问，不猜对象。
- 旧结果或手动编辑后不能把旧响应写入新页面。
- 重复创建、部分失败、跨用户 request_id 不产生越权或重复写入。
- 匿名邀请保留身份、CSRF 及投票前后可见性规则。
- 破坏性操作与分享使用当前真实对象，秘密不进入模型。

## Tasks

- [x] 1. 工具合同与对象绑定：先写 test_business_tools.py，确认缺失模块失败，再实现 domain/business_tools.py。
- [x] 2. 后端执行与日志：先 API 测试现有查询→收藏→建计划→邀请及所有权/CSRF/重试，再实现执行器与命令路由。
- [x] 3. 模型规划：注入现有 Provider，验证 native tool_calls 与错误响应，保持旧条件协议；按真实网关行为增加类型化步骤合同。
- [x] 4. 前端动作总线及聊天接入：先测试明确动作、跨页、状态失效，再接入 Studio、计划及个人页面。
- [x] 5. 全范围回归与文档：后端774、前端291、浏览器3项目通过；真模型完整批次10/12，2超时定向复验2/2。详见验收矩阵，辅助页面动作尚未逐项浏览器/Live验收。
