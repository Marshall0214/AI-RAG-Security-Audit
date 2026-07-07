# 实现细节说明：第一版与第二版

## 第一版：身份、租户与文档权限边界

第一版的目标不是马上接入大模型，而是先建立 AI/RAG 应用最基础的安全边界：

- 用户是谁
- 用户属于哪个租户
- 文档是谁上传的
- 文档属于哪个租户
- 当前用户能不能访问某份文档

如果这几个问题没有先解决，后续接入 RAG 后就很容易出现跨用户检索、跨租户数据泄露、敏感信息进入模型上下文等问题。

### 第一版核心文件

| 文件 | 作用 |
|---|---|
| `app/models.py` | 定义 `User`、`Document`、`Role` 数据结构 |
| `app/database.py` | 使用内存数据库保存用户和文档 |
| `app/security.py` | 实现密码哈希、Token 生成和 Token 校验 |
| `app/auth.py` | 实现 Bearer Token 鉴权和管理员校验 |
| `app/main.py` | 提供注册、登录、文档上传、文档查询、管理员接口 |
| `docs/threat-model.md` | 记录第一版威胁模型 |
| `docs/audit-checklist.md` | 记录第一版安全检查清单 |

### 第一版数据模型

`User`：

- `id`：用户 ID
- `username`：用户名
- `password_hash`：密码哈希
- `tenant_id`：租户 ID
- `role`：角色，分为 `user` 和 `admin`

`Document`：

- `id`：文档 ID
- `title`：文档标题
- `content`：文档内容
- `owner_id`：上传者 ID
- `tenant_id`：文档所属租户

### 第一版接口

| 接口 | 说明 | 是否需要登录 |
|---|---|---|
| `GET /health` | 健康检查 | 否 |
| `POST /auth/register` | 注册用户 | 否 |
| `POST /auth/login` | 登录并获取 Token | 否 |
| `GET /me` | 查看当前用户 | 是 |
| `POST /documents` | 上传文档 | 是 |
| `GET /documents` | 查看当前用户可访问文档 | 是 |
| `GET /documents/{document_id}` | 查看文档详情 | 是 |
| `GET /admin/documents` | 管理员查看全部文档 | 是，管理员 |

### 第一版权限逻辑

普通用户访问文档时，必须同时满足：

```text
document.owner_id == current_user.id
document.tenant_id == current_user.tenant_id
```

管理员可以访问全部文档，但必须通过管理员角色校验。

### 第一版安全验证

验证路径：

1. 注册 Alice，租户为 `tenant-a`。
2. 注册 Bob，租户为 `tenant-b`。
3. Alice 上传文档。
4. Alice 可以读取自己的文档。
5. Bob 使用自己的 Token 读取 Alice 文档，应返回 `403 Forbidden`。
6. Admin 登录后可以查看全部文档。

这个验证证明：第一版已经建立 RAG 前置权限边界。

## 第二版：RAG 文档切片与检索安全

第二版的目标是把第一版从“普通 API 权限项目”升级为“RAG 安全项目”。

这一版暂时不接真实向量数据库和大模型，而是使用轻量关键词检索模拟 RAG 检索。这样做的原因：

- 秋招项目第一阶段要优先讲清楚安全边界，不被复杂依赖拖慢。
- RAG 安全风险的核心是“检索阶段是否召回了不该看的文档”，不依赖真实 embedding 才能说明问题。
- 后续可以平滑替换为 Chroma/Qdrant。

### 第二版新增能力

- 文档上传后自动切片。
- 为每个切片保存 `owner_id` 和 `tenant_id`。
- 新增安全检索接口：`POST /rag/query`。
- 新增漏洞演示接口：`POST /lab/vulnerable-rag/query`。
- 新增 RAG 跨用户检索漏洞报告。

### 第二版新增数据模型

`DocumentChunk`：

- `id`：切片 ID
- `document_id`：来源文档 ID
- `chunk_index`：切片序号
- `text`：切片内容
- `owner_id`：文档上传者 ID
- `tenant_id`：文档所属租户

### 第二版安全接口

`POST /rag/query`

安全逻辑：

1. 用户必须登录。
2. 检索前先确定当前用户身份。
3. 只在当前用户可访问的文档切片中检索。
4. 普通用户不能召回其他用户或其他租户的切片。
5. 管理员可以检索全部切片。

伪代码：

```text
allowed_chunks = chunks where:
  chunk.owner_id == current_user.id
  chunk.tenant_id == current_user.tenant_id

matches = search(allowed_chunks, query)
```

### 第二版漏洞演示接口

`POST /lab/vulnerable-rag/query`

漏洞逻辑：

1. 用户必须登录。
2. 但是检索时不使用当前用户身份做过滤。
3. 直接在全部文档切片中检索。
4. Bob 可以通过关键词检索到 Alice 文档内容。

伪代码：

```text
matches = search(all_chunks, query)
```

这个接口是故意设计的漏洞，用来展示 RAG 跨用户数据泄露。

### 第二版检索策略

当前使用关键词评分模拟向量检索：

1. 把 query 拆成关键词。
2. 在文档标题和切片内容中匹配关键词。
3. 命中越多，分数越高。
4. 返回分数最高的前 `max_results` 个切片。

后续替换向量库时，只需要替换底层检索实现，权限过滤原则不变。

### 第二版安全验证

验证路径：

1. Alice 上传包含 `project phoenix secret` 的文档。
2. Bob 登录。
3. Bob 请求安全接口 `/rag/query` 查询 `phoenix secret`。
4. 安全接口应返回 0 条结果。
5. Bob 请求漏洞接口 `/lab/vulnerable-rag/query` 查询 `phoenix secret`。
6. 漏洞接口会返回 Alice 的文档切片。

结论：

- 安全接口证明权限过滤有效。
- 漏洞接口证明 RAG 检索如果不做权限过滤，会造成跨用户数据泄露。

### 第二版面试讲法

可以这样讲：

> 第一版我先实现了用户、租户、文档归属和 Bearer Token 鉴权，验证了 Bob 无法通过 API 直接读取 Alice 文档。第二版我进一步模拟 RAG 检索，把文档切成 chunk，并且在每个 chunk 上保留 owner_id 和 tenant_id。安全版 `/rag/query` 会先按当前用户过滤可访问 chunk，再做检索；漏洞版 `/lab/vulnerable-rag/query` 故意不做过滤，用来演示 Bob 可以通过关键词召回 Alice 的文档内容。这个实验说明 RAG 的权限控制必须发生在检索阶段，不能把所有内容召回后再交给模型判断。

## 第三版：Agent 工具调用越权实验

第三版的目标是把项目从 RAG 检索安全扩展到 Agent 工具调用安全。

真实 AI Agent 应用通常不会只回答问题，还会调用后端工具完成业务操作，例如：

- 查询订单
- 修改收货地址
- 发起退款
- 查询用户资料
- 创建工单

这些工具一旦连接真实业务系统，就不能把“模型说可以操作”当成权限依据。模型只能生成候选参数，真正的权限判断必须在后端工具执行前完成。

### 第三版新增能力

- 新增订单数据模型 `Order`。
- 新增普通用户创建订单接口。
- 新增安全版 Agent 工具接口：
  - `POST /agent/tools/order-query`
  - `POST /agent/tools/address-update`
- 新增漏洞版 Agent 工具接口：
  - `POST /lab/vulnerable-agent/order-query`
  - `POST /lab/vulnerable-agent/address-update`
- 新增 Agent 工具调用越权报告。

### 第三版新增数据模型

`Order`：

- `id`：订单 ID
- `item_name`：商品名称
- `shipping_address`：收货地址
- `owner_id`：订单所属用户 ID
- `tenant_id`：订单所属租户

订单和文档一样，都必须绑定 `owner_id` 和 `tenant_id`。原因是 Agent 工具最终操作的是业务资产，不是抽象文本。

### 安全版工具接口

#### `POST /agent/tools/order-query`

安全逻辑：

1. 用户必须登录。
2. 后端根据 `order_id` 查询订单。
3. 普通用户只能查询自己的订单。
4. 普通用户不能查询其他用户或其他租户订单。
5. 管理员可以查询全部订单。

伪代码：

```text
order = get_order(order_id)

if current_user.role != admin:
  require order.owner_id == current_user.id
  require order.tenant_id == current_user.tenant_id

return order
```

#### `POST /agent/tools/address-update`

安全逻辑：

1. 用户必须登录。
2. 后端根据 `order_id` 查询订单。
3. 后端校验当前用户是否有权修改该订单。
4. 只有校验通过后才更新地址。

伪代码：

```text
order = get_order(order_id)
authorize(current_user, order)
order.shipping_address = new_address
```

### 漏洞版工具接口

#### `POST /lab/vulnerable-agent/order-query`

漏洞逻辑：

1. 用户必须登录。
2. 但后端只按 `order_id` 查询订单。
3. 不校验 `owner_id`。
4. 不校验 `tenant_id`。
5. Bob 可以查询 Alice 的订单。

#### `POST /lab/vulnerable-agent/address-update`

漏洞逻辑：

1. 用户必须登录。
2. 但后端只按 `order_id` 修改订单。
3. 不校验当前用户是否拥有该订单。
4. Bob 可以修改 Alice 的收货地址。

这个接口模拟了 Agent 工具调用中最危险的一类问题：模型或 Agent 传入了一个看似合法的 `order_id`，后端工具却没有重新做权限校验。

### 第三版安全验证

验证路径：

1. Alice 创建订单。
2. Bob 登录。
3. Bob 调用安全查询工具查询 Alice 订单，应返回 `403 Forbidden`。
4. Bob 调用漏洞查询工具查询 Alice 订单，会成功返回订单。
5. Bob 调用安全地址修改工具修改 Alice 订单，应返回 `403 Forbidden`。
6. Bob 调用漏洞地址修改工具修改 Alice 订单，会成功修改。
7. Alice 再查询自己的订单，可以看到地址已被漏洞接口篡改。

结论：

- Agent 工具执行前必须做后端鉴权。
- 不能相信模型生成的 `order_id`、`user_id`、`tenant_id`。
- 不能把系统提示词、Agent 规划或“用户声明”当作权限边界。

### 第三版面试讲法

可以这样讲：

> 第三版我模拟了 Agent 工具调用场景，设计了订单查询和地址修改两个工具。安全版工具会在执行前根据当前登录用户校验订单的 owner_id 和 tenant_id，因此 Bob 不能查询或修改 Alice 的订单。漏洞版工具故意只按 order_id 操作，不做后端鉴权，结果 Bob 可以读取并修改 Alice 的订单。这个实验说明 Agent 安全的关键不是让模型“更听话”，而是工具执行层必须有强制权限控制。
