# 第八版：Chroma 向量库与 Metadata 权限过滤

## 这一版解决什么问题

前面的 RAG 检索使用关键词匹配，已经能说明“检索阶段必须做权限过滤”这个安全原则。

第八版把 RAG 检索升级成 Chroma 向量检索，让项目更接近真实 RAG 应用：

- 文档上传后仍然会被切成 chunk。
- 每个 chunk 会写入 Chroma collection。
- Chroma 中保存 chunk 文本、向量和 metadata。
- 安全检索通过 metadata filter 限制召回范围。
- 漏洞检索故意不使用 metadata filter，用来复现跨用户向量召回泄露。

## 新增文件

```text
app/vector_store.py
```

## 依赖变化

```text
chromadb==0.5.23
```

## 数据流

### 文档上传

```text
POST /documents
  -> create_document()
  -> create_chunks_for_document()
  -> rag_store.add_chunk()
  -> Chroma collection.add()
```

每个 chunk 写入 Chroma 时会携带 metadata：

```json
{
  "chunk_id": 1,
  "document_id": 1,
  "chunk_index": 0,
  "owner_id": 2,
  "tenant_id": "tenant-a",
  "document_title": "Alice secret plan"
}
```

这些 metadata 是 RAG 权限过滤的关键。

## 安全版检索

接口：

```text
POST /rag/query
```

安全版会根据当前登录用户构造 Chroma `where` 过滤条件：

```python
where = {
    "$and": [
        {"owner_id": {"$eq": current_user.id}},
        {"tenant_id": {"$eq": current_user.tenant_id}},
    ]
}
```

含义是：

- Bob 的向量检索只能在 Bob 自己的 chunk 中查。
- 即使 Bob 的 query 命中了 Alice 的语义内容，也不会进入候选召回集。
- 权限过滤发生在向量检索阶段，而不是把结果召回后再交给模型判断。

管理员角色可以不带该过滤条件，用于审计或平台管理场景。

## 漏洞版检索

接口：

```text
POST /lab/vulnerable-rag/query
```

漏洞版调用 Chroma 查询时不传 `where`：

```python
where = None
```

这样 Bob 虽然已经登录，但检索范围是全库 chunk。

结果是：

- Bob 查询 `phoenix secret`。
- Chroma 可以召回 Alice 的文档切片。
- 返回结果中能看到 Alice 的 `owner_id` 和 `tenant_id`。

这就是真实 RAG 系统中常见的漏洞：向量库只做相似度检索，没有做 metadata 权限过滤。

## 为什么使用本地确定性 embedding

第八版没有直接调用 OpenAI embedding 或 HuggingFace 模型，而是使用本地确定性 embedding。

原因：

- 避免面试演示时依赖 API Key。
- 避免第一次运行时下载大模型。
- 保持项目轻量、稳定、可离线测试。
- 当前版本重点是验证 Chroma metadata filter，而不是追求 embedding 效果。

可以这样解释：

> 第八版我接入了真实向量库 Chroma，但 embedding 使用本地确定性实现，目的是把重点放在 RAG 权限过滤上。后续如果替换成 OpenAI embedding 或 bge-small，只需要替换 embedding function，metadata filter 的安全原则不变。

## 测试验证

运行：

```powershell
D:\Users\28020\anaconda3\envs\rag\python.exe tests\security_regression.py
```

关键预期：

- Alice 上传包含 `Project phoenix secret` 的文档。
- Alice 请求 `/rag/query` 可以召回自己的 chunk。
- Bob 请求 `/rag/query` 返回 0 条结果。
- Bob 请求 `/lab/vulnerable-rag/query` 可以召回 Alice chunk。

运行红队测试和报告生成：

```powershell
D:\Users\28020\anaconda3\envs\rag\python.exe tests\ai_red_team_suite.py --report reports\ai-security-red-team-report.md
```

关键预期：

- `safe_rag_prompt_injection_blocked` 通过。
- `vulnerable_rag_prompt_injection_leaks` 通过。

## 面试讲法

可以这样讲：

> 前面版本用关键词检索模拟 RAG 权限边界。第八版我把它升级成 Chroma 向量检索，每个文档切片写入向量库时都会保存 owner_id 和 tenant_id。安全版 RAG 查询会在 Chroma 查询阶段加 metadata filter，只在当前用户可访问的 chunk 里做相似度检索；漏洞版故意不加 filter，Bob 就能通过语义查询召回 Alice 的文档切片。这个版本说明了真实 RAG 系统中权限控制必须进入向量检索阶段，不能只依赖应用层或模型回答阶段。

## 后续升级

- 将本地确定性 embedding 替换为 OpenAI embedding、bge-small 或其他真实 embedding 模型。
- 将 Chroma 从 `EphemeralClient` 换成 `PersistentClient`，让向量索引持久化。
- 增加 RAG 数据投毒测试。
- 接入 promptfoo，把 Chroma RAG 的安全用例纳入标准 AI 红队测试。
