# AI 应用安全测试报告模板

## 1. 测试概览

- 项目名称：AI-RAG-Security-Audit
- 测试对象：RAG 检索权限边界、Agent 工具执行权限边界、高风险写操作确认、工具调用审计日志
- 测试方式：自动化红队测试集
- 测试命令：

```powershell
D:\Users\28020\anaconda3\envs\rag\python.exe tests\ai_red_team_suite.py --report reports\ai-security-red-team-report.md
```

## 2. 测试范围

| 范围 | 说明 |
|---|---|
| API 越权访问 | Bob 尝试直接访问 Alice 的文档 |
| RAG 检索安全 | Bob 尝试通过 query 召回 Alice 的文档切片 |
| Agent 工具读操作 | Bob 尝试查询 Alice 的订单 |
| Agent 工具写操作 | Bob 尝试修改 Alice 的订单地址 |
| 高风险操作确认 | Alice 修改地址必须经过 confirmation token |
| 审计日志 | 工具调用成功、拒绝、漏洞演示都应留下记录 |

## 3. 预期结论

- 安全接口必须阻断跨用户、跨租户访问。
- 漏洞接口必须稳定复现风险，用于对比说明问题。
- 高风险写操作不能一次请求直接执行。
- confirmation token 必须绑定用户、订单和请求参数，且不能复用。
- 审计日志必须能支持事后追踪。

## 4. 面试讲法

> 第七版我在红队测试脚本里加入了 Markdown 报告导出能力。测试完成后会自动生成安全报告，包含测试时间、总体结果、风险分类统计、每条用例的风险说明和验证证据。这样项目从“能自动测试”进一步变成“能输出安全审计交付物”。
