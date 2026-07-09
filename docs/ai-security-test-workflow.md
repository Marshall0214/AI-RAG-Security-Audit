# 第六版：AI 安全红队测试集与执行流程

## 这一版解决什么问题

前五版已经把 RAG 权限边界、Agent 工具越权、审计日志和高风险操作二次确认跑通了。

第六版的目标是把这些安全场景沉淀成一套可以重复执行的红队测试集：

- 不只靠 Swagger 手工点接口。
- 不只证明“某一次测试成功”。
- 而是把攻击样例、预期结果、自动化验证脚本都放进项目里。

面试时可以这样概括：

> 第六版我把 RAG 和 Agent 的安全风险整理成红队测试集，并写了自动化执行脚本。它会自动准备 Alice/Bob 场景，批量执行跨用户文档访问、RAG 提示词注入式检索、Agent 工具越权读写、confirmation token 复用、审计日志校验等用例。这样项目不只是漏洞演示，而是有一套可复现、可回归的 AI 应用安全测试流程。

## 新增文件

```text
tests/ai_security_cases.json
tests/ai_red_team_suite.py
docs/ai-security-test-workflow.md
```

### `tests/ai_security_cases.json`

这个文件是红队测试用例库。

每个用例包含：

- `id`：用例唯一名称。
- `category`：安全分类，例如 RAG 安全、Agent 工具授权、审计能力。
- `risk`：这个用例模拟的风险。
- `attacker`：攻击者身份，例如 Bob。
- `method`：HTTP 方法。
- `endpoint`：测试接口。
- `payload`：攻击请求体。
- `expected`：预期安全结果。

它的价值是：安全测试不再散落在聊天记录或手工步骤里，而是变成可维护的测试资产。

### `tests/ai_red_team_suite.py`

这个脚本会读取 `ai_security_cases.json`，自动完成以下事情：

1. 启动临时 FastAPI 服务，或连接你已经启动的服务。
2. 自动注册 Alice 和 Bob。
3. Alice 创建私有文档、RAG 文档和订单。
4. Bob 执行跨用户攻击用例。
5. Alice 执行高风险写操作确认用例。
6. 校验安全接口是否阻断攻击。
7. 校验漏洞接口是否能稳定复现风险。
8. 校验审计日志是否记录了工具调用结果。

## 覆盖的安全场景

| 用例 | 验证点 |
|---|---|
| `direct_document_idor_blocked` | Bob 不能直接读取 Alice 的文档 |
| `safe_rag_prompt_injection_blocked` | Bob 即使用提示词注入式 query，也不能通过安全 RAG 召回 Alice 文档 |
| `vulnerable_rag_prompt_injection_leaks` | 漏洞 RAG 会泄露 Alice 文档切片 |
| `safe_agent_order_query_idor_blocked` | Bob 不能通过安全 Agent 工具查询 Alice 订单 |
| `vulnerable_agent_order_query_idor_leaks` | 漏洞 Agent 查询工具会泄露 Alice 订单 |
| `safe_agent_address_update_idor_blocked` | Bob 不能通过安全 Agent 工具修改 Alice 地址 |
| `vulnerable_agent_address_update_idor_writes` | 漏洞 Agent 修改工具会篡改 Alice 地址 |
| `safe_address_update_requires_confirmation` | Alice 自己修改地址也必须先拿 confirmation token |
| `safe_confirmation_token_accepts_exact_request` | token 与用户、订单、地址完全匹配时才能修改 |
| `safe_confirmation_token_reuse_blocked` | 已使用的 confirmation token 不能复用 |
| `safe_confirmation_token_mismatch_blocked` | token 不能被换到另一个地址请求上使用 |
| `agent_audit_logs_include_denied_and_vulnerable` | Bob 的工具调用会留下审计日志 |

## 执行方式一：自动启动临时服务

在项目目录执行：

```powershell
Set-Location D:\work\AI-RAG-Security-Audit
D:\Users\28020\anaconda3\envs\rag\python.exe tests\ai_red_team_suite.py
```

脚本会自动启动一个临时服务，跑完测试后自动关闭。

成功时你会看到类似：

```text
AI security red-team suite
===============================
[PASS] api-authorization / direct_document_idor_blocked - ...
[PASS] rag-security / safe_rag_prompt_injection_blocked - ...
[PASS] rag-security / vulnerable_rag_prompt_injection_leaks - ...
...
===============================
Total: 12 passed, 0 failed
```

## 执行方式二：测试已经运行的服务

如果你已经手动启动项目：

```powershell
Set-Location D:\work\AI-RAG-Security-Audit
D:\Users\28020\anaconda3\envs\rag\python.exe -m uvicorn app.main:app --reload --no-use-colors
```

另开一个终端执行：

```powershell
Set-Location D:\work\AI-RAG-Security-Audit
D:\Users\28020\anaconda3\envs\rag\python.exe tests\ai_red_team_suite.py --base-url http://127.0.0.1:8000
```

这种方式适合你一边打开 Swagger，一边跑红队测试脚本。

## 和第四版回归测试的区别

第四版的 `tests/security_regression.py` 更像“核心安全回归测试”：

- 验证主流程是否正常。
- 验证安全版能拦截。
- 验证漏洞版能复现。

第六版的 `tests/ai_red_team_suite.py` 更像“AI 安全红队用例集”：

- 用 JSON 管理攻击样例。
- 更强调攻击视角和风险分类。
- 增加 prompt-injection-style query。
- 增加 confirmation token 复用和参数篡改测试。
- 更适合后续扩展更多 payload。

两个脚本建议都保留：

```powershell
D:\Users\28020\anaconda3\envs\rag\python.exe tests\security_regression.py
D:\Users\28020\anaconda3\envs\rag\python.exe tests\ai_red_team_suite.py
```

## 面试讲法

可以分三层讲：

第一层，系统目标：

> 我的项目不是做普通聊天机器人，而是做 AI 应用安全审计实验平台，重点验证 RAG 检索阶段和 Agent 工具执行阶段的权限边界。

第二层，第六版做了什么：

> 第六版我把前面发现和演示的安全问题沉淀成红队测试集，用 JSON 维护攻击用例，用 Python 脚本自动执行。测试覆盖跨用户文档访问、RAG 检索泄露、Agent 工具越权读写、高风险写操作确认、confirmation token 复用防护和审计日志。

第三层，安全观点：

> 大模型不能作为权限边界。攻击者可以在 query 或工具参数里构造恶意输入，所以真正的权限校验必须在后端执行。红队测试集的作用就是持续验证这些边界没有被后续代码改坏。

## 后续可扩展方向

第六版之后可以继续扩展：

- 第七版已经支持通过 `--report` 导出 Markdown 安全测试报告。
- 接入 `promptfoo`，把 JSON 用例升级成标准 AI 评测配置。
- 增加更多 prompt injection payload。
- 增加 RAG 数据投毒测试。
- 增加 Agent 工具参数污染测试。
- 增加测试报告导出，例如 JSON、HTML 或 Markdown 报告。
- 替换关键词检索为 Chroma/Qdrant，同时保留 `owner_id` 和 `tenant_id` 过滤测试。
