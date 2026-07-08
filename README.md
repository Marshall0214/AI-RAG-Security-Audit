# AI-RAG-Security-Audit

## 第六版新增

第六版已经加入 AI 安全红队测试集：

- `tests/ai_security_cases.json`：用 JSON 维护 RAG、Agent、越权访问、confirmation token、审计日志等攻击用例。
- `tests/ai_red_team_suite.py`：自动准备 Alice/Bob 场景，并批量执行安全红队测试。
- `docs/ai-security-test-workflow.md`：记录第六版设计目标、执行方式、覆盖场景和面试讲法。

运行第六版红队测试：

```powershell
D:\Users\28020\anaconda3\envs\rag\python.exe tests\ai_red_team_suite.py
```

面向秋招展示的 AI 应用安全审计实验平台第一版。

第一版先不追求复杂页面和完整大模型能力，重点建立安全边界：

- 用户注册与登录
- Token 鉴权
- 租户隔离
- 文档上传
- 文档归属控制
- 越权访问验证
- 后续可扩展 RAG、Prompt Injection、Agent 工具越权、自动化红队测试

第二版已经加入轻量 RAG 检索安全实验：

- 文档上传后自动切片
- `POST /rag/query`：安全版 RAG 检索，只召回当前用户可访问文档
- `POST /lab/vulnerable-rag/query`：故意保留的漏洞版 RAG 检索，不做用户/租户过滤
- 用 Bob 检索 Alice 文档的方式演示 RAG 跨用户数据泄露

第三版已经加入 Agent 工具调用越权实验：

- `POST /orders`：创建订单
- `GET /orders`：查看当前用户可访问订单
- `POST /agent/tools/order-query`：安全版订单查询工具
- `POST /agent/tools/address-update`：安全版地址修改工具
- `POST /lab/vulnerable-agent/order-query`：漏洞版订单查询工具
- `POST /lab/vulnerable-agent/address-update`：漏洞版地址修改工具
- 用 Bob 查询和修改 Alice 订单的方式演示 Agent 工具越权

第四版已经加入自动化安全回归测试：

- `tests/security_regression.py`：一键验证第一版、第二版、第三版核心安全场景
- 自动验证 API 越权拦截、RAG 安全检索、RAG 漏洞泄露、Agent 安全工具、Agent 漏洞工具
- 支持启动内嵌临时服务测试，也支持对已运行的服务测试

第五版已经加入 Agent 工具审计日志与高风险操作二次确认：

- `POST /agent/tools/address-update`：安全版地址修改现在需要二次确认
- 第一次请求返回 `confirmation_token`，第二次带 token 才真正修改地址
- `GET /agent/audit-logs`：查看当前用户的 Agent 工具调用审计日志，管理员可查看全部
- 漏洞版地址修改仍然不需要确认，用来对比真实风险

## 项目定位

这是一个“可被攻击、可被修复、可被审计”的 AI 应用安全项目。

最终目标不是普通 RAG Demo，而是展示你能完成：

- AI 应用架构理解
- Web/API 安全测试
- RAG 安全审计
- Agent 工具调用安全审计
- 自动化红队测试
- 审计报告交付

## 第一版功能

### 已实现

- `POST /auth/register`：注册用户
- `POST /auth/login`：登录并获取访问 Token
- `GET /me`：查看当前用户
- `POST /documents`：上传文档
- `GET /documents`：查看当前用户可访问文档
- `GET /documents/{document_id}`：查看文档详情
- `GET /admin/documents`：管理员查看所有文档
- `POST /rag/query`：安全版 RAG 检索
- `POST /lab/vulnerable-rag/query`：漏洞版 RAG 检索演示
- `POST /orders`：创建订单
- `GET /orders`：查看当前用户可访问订单
- `POST /agent/tools/order-query`：安全版 Agent 订单查询工具
- `POST /agent/tools/address-update`：安全版 Agent 地址修改工具
- `POST /lab/vulnerable-agent/order-query`：漏洞版 Agent 订单查询工具
- `POST /lab/vulnerable-agent/address-update`：漏洞版 Agent 地址修改工具
- `GET /agent/audit-logs`：查看 Agent 工具调用审计日志
- `tests/security_regression.py`：自动化安全回归测试脚本

### 安全设计

- 普通用户只能访问自己租户下、自己上传的文档
- 管理员可以查看所有文档
- 文档记录包含 `owner_id` 和 `tenant_id`
- API 通过 Bearer Token 鉴权
- Token 使用 HMAC 签名，避免简单伪造

### 第一版刻意保留的学习点

当前版本没有接入真实 RAG 和大模型，原因是第一阶段要先把 AI 应用最基础的安全边界跑通：

- 谁上传了文档
- 文档属于哪个租户
- 谁能检索这个文档
- 是否能越权访问别人的文档
- 后续 RAG 检索必须继承这些权限约束

## 目录结构

```text
AI-RAG-Security-Audit/
├── app/
│   ├── main.py
│   ├── auth.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   └── security.py
├── docs/
│   ├── audit-checklist.md
│   ├── interview-notes.md
│   └── threat-model.md
├── tests/
│   └── manual-test.http
├── requirements.txt
└── README.md
```

## 本地运行

创建虚拟环境：

```bash
python -m venv .venv
```

安装依赖：

```bash
pip install -r requirements.txt
```

启动服务：

```bash
uvicorn app.main:app --reload
```

访问接口文档：

```text
http://127.0.0.1:8000/docs
```

## 快速验证路径

1. 注册普通用户 Alice。
2. 注册普通用户 Bob。
3. Alice 上传一份文档。
4. Alice 可以查看自己的文档。
5. Bob 尝试访问 Alice 的文档，应返回 `403 Forbidden`。
6. 注册管理员 Admin。
7. Admin 可以查看所有文档。
8. Alice 上传包含 `Project phoenix secret` 的文档。
9. Bob 请求 `/rag/query` 查询 `phoenix secret`，应返回 0 条结果。
10. Bob 请求 `/lab/vulnerable-rag/query` 查询 `phoenix secret`，会召回 Alice 文档，用于演示漏洞。
11. Alice 创建订单。
12. Bob 请求 `/agent/tools/order-query` 查询 Alice 订单，应返回 `403 Forbidden`。
13. Bob 请求 `/lab/vulnerable-agent/order-query` 查询 Alice 订单，会返回订单详情。
14. Alice 请求 `/agent/tools/address-update` 修改自己的地址，会先返回 `confirmation_token`。
15. Alice 再次请求 `/agent/tools/address-update` 并带上 `confirmation_token`，地址才会修改成功。
16. Bob 请求 `/agent/tools/address-update` 修改 Alice 订单地址，应返回 `403 Forbidden`。
17. Bob 请求 `/lab/vulnerable-agent/address-update` 修改 Alice 订单地址，会成功修改，用于演示漏洞。
18. Bob 请求 `/agent/audit-logs`，可以看到自己的工具调用审计记录。

## 自动化安全回归测试

推荐使用 `rag` Conda 环境运行：

```powershell
D:\Users\28020\anaconda3\envs\rag\python.exe tests\security_regression.py
```

脚本会自动启动一个临时测试服务，运行完整安全场景，然后释放端口。

如果你已经手动启动了服务：

```powershell
D:\Users\28020\anaconda3\envs\rag\python.exe -m uvicorn app.main:app --reload --no-use-colors
```

也可以对当前服务运行测试：

```powershell
D:\Users\28020\anaconda3\envs\rag\python.exe tests\security_regression.py --base-url http://127.0.0.1:8000
```

测试覆盖：

- Alice/Bob 注册和登录
- Bob 直接访问 Alice 文档被 `403` 拦截
- Alice 可以通过安全 RAG 检索自己的文档
- Bob 通过安全 RAG 无法检索 Alice 文档
- Bob 通过漏洞 RAG 可以检索 Alice 文档
- Bob 通过安全 Agent 工具无法查询和修改 Alice 订单
- Bob 通过漏洞 Agent 工具可以查询和修改 Alice 订单
- Alice 可以观察到漏洞工具造成的地址篡改结果
- 安全版高风险地址修改必须经过 confirmation token 二次确认
- Agent 工具调用会生成审计日志

## Swagger 页面授权方式

打开接口页面：

```text
http://127.0.0.1:8000/docs
```

登录接口 `/auth/login` 会返回：

```json
{
  "access_token": "token value",
  "token_type": "bearer"
}
```

点击页面右上角 `Authorize`，在 `Bearer Token` 输入框里只粘贴 `access_token` 的值，不需要手动输入 `Bearer ` 前缀。

授权成功后，`GET /me`、`POST /documents`、`GET /documents`、`GET /admin/documents` 这些接口旁边会显示小锁，可以直接在 Swagger 页面里测试。

## 秋招简历写法

项目：AI-RAG-Security-Audit：面向 RAG 与 Agent 应用的安全审计实验平台

- 基于 FastAPI 设计 AI 应用安全审计实验平台，第一版实现用户注册登录、Token 鉴权、租户隔离、文档上传与文档归属访问控制。
- 围绕 RAG 场景设计文档资产边界，记录 `owner_id`、`tenant_id` 等权限字段，为后续向量检索权限过滤和跨租户数据泄露测试打基础。
- 设计越权访问验证路径，覆盖普通用户访问自身文档、跨用户访问被拒绝、管理员查看全部文档等安全场景。
- 后续计划接入 LangChain/LlamaIndex、Chroma/Qdrant、promptfoo、garak/PyRIT，扩展 Prompt Injection、RAG 污染、工具调用越权和自动化红队测试。

## 下一版计划

第三版目标：

- 增加退款申请工具
- 增加 promptfoo 自动化测试

第四版目标：

- 接入 promptfoo
- 建立 100 条 payload
- 输出自动化安全测试报告
