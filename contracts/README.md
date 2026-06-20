# contracts/ — 唯一共享契约层

所有 agent（前端/后端/测试）都以**只读**方式挂载本目录。它是前后端协作的唯一通道。

| 文件 | 来源 | 说明 |
|---|---|---|
| `openapi.json` | 后端 FastAPI 自动生成 | API 的权威定义。后端改模型 → `make sync-contracts` 重新生成 |
| `api_types.ts` | 由 openapi.json 生成 | 前端用的类型 |
| `db_schema.md` | 同步自 `tech_layer/DB_Schema.md` | MongoDB 集合结构（人读参考）|
| `API_Spec.md` | 同步自 `tech_layer/API_Spec.md` | 端点语义（人读参考）|

## 规则

- 任何人不得直接手改 `openapi.json` / `api_types.ts` —— 它们是生成物
- 后端改了请求/响应模型 → 跑 `make sync-contracts`
- 契约变更应单独成一个 commit（scope=`contracts`），便于审计 API 演进
- 契约的破坏性变更（删字段/改类型）需仲裁者审核
