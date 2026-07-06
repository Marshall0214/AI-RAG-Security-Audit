# RAG 跨用户检索泄露报告 v0.1

## 漏洞标题

RAG 检索阶段缺少用户与租户过滤，导致跨用户文档内容泄露。

## 风险等级

高危。

## 影响场景

企业知识库、客服助手、内部问答系统、文档问答系统等 RAG 应用中，如果检索阶段没有按当前用户权限过滤文档切片，攻击者可能通过关键词查询召回其他用户或其他租户的敏感文档内容。

## 受影响接口

漏洞演示接口：

```text
POST /lab/vulnerable-rag/query
```

安全接口：

```text
POST /rag/query
```

## 前置条件

- Alice 已登录并上传包含敏感关键词的文档。
- Bob 已登录。
- Bob 知道或猜到文档中的关键词，例如 `phoenix secret`。

## 复现步骤

### 1. Alice 注册并登录

```json
{
  "username": "alice",
  "password": "alice123",
  "tenant_id": "tenant-a",
  "role": "user"
}
```

### 2. Alice 上传敏感文档

```json
{
  "title": "Alice secret plan",
  "content": "Project phoenix secret: Alice owns this private RAG document."
}
```

### 3. Bob 注册并登录

```json
{
  "username": "bob",
  "password": "bob12345",
  "tenant_id": "tenant-b",
  "role": "user"
}
```

### 4. Bob 请求安全检索接口

```text
POST /rag/query
```

```json
{
  "query": "phoenix secret",
  "max_results": 5
}
```

预期结果：

```json
{
  "match_count": 0,
  "matches": []
}
```

说明安全接口在检索前执行了用户与租户过滤，Bob 无法召回 Alice 的文档切片。

### 5. Bob 请求漏洞演示接口

```text
POST /lab/vulnerable-rag/query
```

```json
{
  "query": "phoenix secret",
  "max_results": 5
}
```

漏洞结果：

```json
{
  "match_count": 1,
  "matches": [
    {
      "document_title": "Alice secret plan",
      "text": "Project phoenix secret: Alice owns this private RAG document.",
      "owner_id": 2,
      "tenant_id": "tenant-a"
    }
  ]
}
```

说明漏洞接口没有使用当前登录用户身份过滤切片，Bob 可以召回 Alice 的文档内容。

## 根因分析

漏洞接口使用了全局切片集合：

```text
all_chunks
```

而不是当前用户可访问切片集合：

```text
chunks where chunk.owner_id == current_user.id and chunk.tenant_id == current_user.tenant_id
```

RAG 应用中，权限控制必须发生在检索阶段。如果先召回所有文档，再让模型判断是否应该展示，权限边界就已经失效。

## 修复方案

### 必须修复

- 每个文档切片保存 `owner_id` 和 `tenant_id`。
- 检索前按当前用户身份过滤可访问切片。
- 普通用户只能检索自己的文档切片。
- 管理员接口必须单独鉴权。

### 推荐增强

- 文档级 ACL。
- 组织/租户级隔离。
- 检索日志记录当前用户、query、召回文档 ID。
- 对敏感文档启用额外审批或脱敏。
- 对异常 query 做风控，例如高频探测、关键词撞库。

## 修复后验证

安全接口 `/rag/query` 已经实现用户与租户过滤。Bob 查询 `phoenix secret` 时：

- 返回 `match_count = 0`
- 不返回 Alice 的 `document_title`
- 不返回 Alice 的 `text`
- 不返回 Alice 的 `tenant_id`

## 面试讲法

这个漏洞体现的是 RAG 应用里的典型权限问题：传统 API 可能已经禁止 Bob 直接访问 Alice 的文档，但如果 RAG 检索阶段没有继承相同权限控制，Bob 仍然可能通过关键词把 Alice 的文档召回到模型上下文里。因此 RAG 权限控制不能只做在文档详情接口，必须做在检索阶段。
