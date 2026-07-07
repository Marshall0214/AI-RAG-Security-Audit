# 项目代码导读 + 面试问答版

## 这份文档怎么用

这份文档不是让你背代码，而是帮你做到三件事：

1. 面试时能讲清楚项目主线。
2. 被追问代码时能指出关键文件和关键函数。
3. 能解释安全版和漏洞版为什么行为不同。

建议背熟：

- 项目三层主线。
- 每个漏洞的根因。
- 安全接口和漏洞接口的代码差异。
- 5–8 个高频面试问答。

## 项目一句话介绍

这个项目是一个 AI 应用安全审计实验平台，分三版实现：

1. 第一版：实现用户、租户、文档权限边界，验证 API 越权访问会被拦截。
2. 第二版：实现 RAG 文档切片和检索，演示检索阶段缺少权限过滤会导致跨用户文档泄露。
3. 第三版：实现 Agent 工具调用实验，演示工具执行层缺少后端鉴权会导致跨用户订单查询和地址修改。

面试时可以这样开场：

> 我做的是一个面向 RAG 和 Agent 场景的 AI 应用安全审计实验平台。第一版先做身份、租户和文档权限边界；第二版加入 RAG 检索，对比安全检索和漏洞检索；第三版加入 Agent 工具调用，对比安全工具和漏洞工具。核心结论是：模型不能作为权限边界，后端必须在检索阶段和工具执行阶段强制鉴权。

## 代码地图

| 文件 | 你需要理解什么 |
|---|---|
| `app/models.py` | 用户、文档、文档切片、订单这些核心资产长什么样 |
| `app/schemas.py` | 每个接口接收什么请求、返回什么响应 |
| `app/security.py` | 密码哈希、Token 生成和 Token 校验 |
| `app/auth.py` | 如何从 Bearer Token 得到当前用户 |
| `app/database.py` | 权限判断、安全查询、漏洞查询的核心逻辑 |
| `app/rag.py` | 文档切片、关键词分词、检索评分 |
| `app/main.py` | 所有 HTTP API 入口，负责把请求转给数据库方法 |

## 第一部分：数据模型怎么看

### `Role`

位置：`app/models.py`

作用：

- 定义用户角色。
- 当前只有 `user` 和 `admin`。
- 普通用户走 owner/tenant 权限检查。
- 管理员可以查看全部资源。

面试说法：

> 我用 `Role` 区分普通用户和管理员。普通用户访问资源时必须检查 owner_id 和 tenant_id，管理员接口则单独做管理员角色校验。

### `User`

位置：`app/models.py`

核心字段：

- `id`：用户 ID。
- `username`：用户名。
- `password_hash`：密码哈希。
- `tenant_id`：租户 ID。
- `role`：用户角色。

为什么要有 `tenant_id`：

- AI 应用常见于企业知识库、多租户客服系统、内部助手。
- 同一个系统里可能有多个组织或租户。
- 只检查 `owner_id` 不够，真实场景还要考虑租户边界。

面试说法：

> 用户模型里我保留了 tenant_id，是为了模拟企业多租户场景。后续文档切片和订单也都带 tenant_id，这样能验证跨租户检索和工具调用越权。

### `Document`

位置：`app/models.py`

核心字段：

- `id`
- `title`
- `content`
- `owner_id`
- `tenant_id`

关键点：

- 文档不是孤立文本，它是有归属的资产。
- 后续 RAG 检索必须继承文档的权限属性。

面试说法：

> 我没有把文档只当成字符串处理，而是给文档绑定 owner_id 和 tenant_id。因为 RAG 泄露的根因往往是检索阶段丢失了这些权限属性。

### `DocumentChunk`

位置：`app/models.py`

核心字段：

- `document_id`：切片来自哪篇文档。
- `chunk_index`：第几个切片。
- `text`：切片内容。
- `owner_id`：继承文档上传者。
- `tenant_id`：继承文档租户。

为什么切片也要存权限字段：

- RAG 真正检索的是 chunk，不是原始文档。
- 如果 chunk 上没有权限字段，检索阶段很容易变成全局检索。

面试说法：

> RAG 检索的最小单位是 chunk，所以我让每个 chunk 继承 owner_id 和 tenant_id。这样安全检索可以在 chunk 层做权限过滤，而不是召回后再让模型判断。

### `Order`

位置：`app/models.py`

核心字段：

- `id`
- `item_name`
- `shipping_address`
- `owner_id`
- `tenant_id`

为什么引入订单：

- 用来模拟 Agent 工具操作真实业务资产。
- 查询订单是读操作。
- 修改地址是写操作。
- 读和写都必须做后端鉴权。

面试说法：

> 第三版我引入订单模型，是为了模拟 Agent 工具调用真实业务系统。订单也带 owner_id 和 tenant_id，安全工具执行前必须检查当前用户是否有权操作该订单。

## 第二部分：认证代码怎么看

### Token 生成和校验

位置：`app/security.py`

你需要知道：

- `hash_password`：用哈希保存密码，不存明文。
- `verify_password`：登录时比对密码。
- `create_token`：生成带签名的 Token。
- `verify_token`：校验 Token 签名，防止伪造。

面试说法：

> 这个项目没有引入完整 JWT 库，而是用 HMAC 签名实现了轻量 Token。重点是让每个受保护接口都能通过 Token 还原当前用户身份，后续权限判断都依赖 current_user。

### 获取当前用户

位置：`app/auth.py`

关键函数：

```text
get_current_user
```

逻辑：

1. 从 Swagger/请求头里的 Bearer Token 读取凭据。
2. 调用 `verify_token` 校验签名。
3. 从 Token payload 里取 `sub`，也就是用户 ID。
4. 到数据库里查用户。
5. 返回 `current_user`。

为什么重要：

- 安全接口都依赖 `current_user`。
- 没有当前用户，就没法判断 owner/tenant。

面试说法：

> 所有需要登录的接口都会 Depends `get_current_user`。它会从 Bearer Token 中解析用户 ID，然后返回当前用户对象。后续文档、RAG、Agent 工具都基于这个 current_user 做权限判断。

### 管理员校验

位置：`app/auth.py`

关键函数：

```text
require_admin
```

逻辑：

- 先复用 `get_current_user`。
- 再检查 `user.role == admin`。
- 不满足就返回 `403`。

面试说法：

> 管理员接口没有只靠前端隐藏，而是在后端通过 require_admin 强制校验角色。

## 第三部分：第一版权限边界怎么看

### 创建文档

位置：`app/main.py` 的 `POST /documents`

调用链：

```text
create_document API
-> get_current_user
-> db.create_document(...)
```

关键点：

- 文档的 `owner_id` 来自当前登录用户。
- 文档的 `tenant_id` 来自当前登录用户。
- 用户不能自己在请求体里伪造 owner_id 或 tenant_id。

面试说法：

> 创建文档时，owner_id 和 tenant_id 不是从前端传的，而是后端根据 current_user 写入。这样可以避免用户伪造资源归属。

### 安全读取文档

位置：`app/database.py`

关键函数：

```text
get_document_for_user
```

逻辑：

```text
如果文档不存在：返回 None
如果当前用户是管理员：返回文档
如果 document.owner_id == user.id 且 document.tenant_id == user.tenant_id：返回文档
否则：返回 None
```

API 处理：

- `None` 会被 `GET /documents/{document_id}` 转成 `403 Forbidden`。

面试说法：

> Bob 不能直接访问 Alice 文档，是因为接口调用了 get_document_for_user。这个函数会检查 owner_id 和 tenant_id，不匹配就返回 None，API 层再返回 403。

## 第四部分：第二版 RAG 安全怎么看

### 文档切片

位置：`app/rag.py`

关键函数：

```text
chunk_text
```

作用：

- 把文档内容切成多个 chunk。
- 当前是简化实现：按固定长度切片，并保留 overlap。

为什么这么做：

- 真正 RAG 系统不会直接检索整篇文档，而是检索 chunk。
- 这个项目先用轻量切片模拟真实 RAG 流程。

面试说法：

> 第二版我没有直接上向量数据库，而是用轻量 chunk 和关键词检索模拟 RAG，因为我要突出的是检索阶段权限过滤问题。后续可以把底层检索替换成 Chroma 或 Qdrant，但权限过滤原则不变。

### 创建文档时自动切片

位置：`app/database.py`

调用链：

```text
create_document
-> create_chunks_for_document
```

关键点：

- 文档创建后自动生成 `DocumentChunk`。
- 每个 chunk 继承文档的 `owner_id` 和 `tenant_id`。

面试说法：

> 文档上传后会自动切片，每个 chunk 都继承 owner_id 和 tenant_id。这是为了保证 RAG 检索时仍然能做权限过滤。

### 安全 RAG 检索

位置：

- `app/main.py` 的 `POST /rag/query`
- `app/database.py` 的 `search_chunks_for_user`

安全逻辑：

```text
普通用户只能在自己的 chunk 中检索：
chunk.owner_id == user.id
chunk.tenant_id == user.tenant_id
```

管理员逻辑：

- 管理员可以检索全部 chunk。

面试说法：

> 安全版 RAG 查询会先根据 current_user 过滤可访问 chunk，然后再做关键词检索。因此 Bob 查询 `phoenix secret` 时，根本不会进入 Alice 的 chunk 集合，自然返回 0 条。

### 漏洞 RAG 检索

位置：

- `app/main.py` 的 `POST /lab/vulnerable-rag/query`
- `app/database.py` 的 `search_all_chunks`

漏洞逻辑：

```text
不管当前用户是谁，直接搜索全部 chunk。
```

结果：

- Bob 只要猜到关键词，就能召回 Alice 的文档切片。

面试说法：

> 漏洞版 RAG 查询调用的是 search_all_chunks，它没有使用 current_user 做 owner_id 和 tenant_id 过滤，所以 Bob 可以通过关键词召回 Alice 的文档内容。

### RAG 漏洞根因

一句话：

> RAG 检索阶段没有继承业务系统的权限控制。

更完整说法：

> 传统 API 可能已经禁止 Bob 访问 Alice 文档详情，但如果 RAG 检索阶段对所有 chunk 做全局检索，Alice 文档仍然可能被塞进模型上下文。这个时候即使详情接口安全，RAG 仍然泄露数据。

## 第五部分：第三版 Agent 工具安全怎么看

### 创建订单

位置：`app/main.py` 的 `POST /orders`

调用链：

```text
create_order API
-> get_current_user
-> db.create_order
```

关键点：

- 订单的 `owner_id` 和 `tenant_id` 来自当前用户。
- 请求体只能传商品名和地址。
- 用户不能伪造订单归属。

面试说法：

> 创建订单时，owner_id 和 tenant_id 同样由后端根据 current_user 写入，避免用户在请求体里伪造归属。

### 安全订单查询工具

位置：

- `app/main.py` 的 `POST /agent/tools/order-query`
- `app/database.py` 的 `get_order_for_user`

安全逻辑：

```text
根据 order_id 找订单
如果当前用户是管理员：允许
否则必须满足：
order.owner_id == user.id
order.tenant_id == user.tenant_id
```

Bob 查询 Alice 订单：

- `owner_id` 不匹配。
- 返回 `None`。
- API 返回 `403 Forbidden`。

面试说法：

> 安全版工具不是直接按 order_id 返回订单，而是调用 get_order_for_user。这个函数会校验当前用户是否拥有该订单，不满足就返回 403。

### 漏洞订单查询工具

位置：

- `app/main.py` 的 `POST /lab/vulnerable-agent/order-query`
- `app/database.py` 的 `get_order_without_authorization`

漏洞逻辑：

```text
只按 order_id 查订单。
不检查 owner_id。
不检查 tenant_id。
```

结果：

- Bob 知道 Alice 的 `order_id` 就能查到 Alice 订单。

面试说法：

> 漏洞版工具调用 get_order_without_authorization，只按 order_id 查询，不校验当前用户身份。这模拟了 Agent 工具只相信模型参数、没有后端鉴权的情况。

### 安全地址修改工具

位置：`app/main.py` 的 `POST /agent/tools/address-update`

安全逻辑：

```text
先 get_order_for_user 做鉴权
鉴权通过才 update_order_address
```

关键点：

- 写操作必须先授权，再修改。
- 不能先修改，再判断。

面试说法：

> 安全版地址修改工具在更新前先调用 get_order_for_user。只有当前用户有权访问该订单时，才会执行 update_order_address。

### 漏洞地址修改工具

位置：`app/main.py` 的 `POST /lab/vulnerable-agent/address-update`

漏洞逻辑：

```text
get_order_without_authorization(order_id)
update_order_address(order, new_address)
```

结果：

- Bob 可以修改 Alice 的收货地址。
- Alice 再查自己的订单时，会看到地址被改成 `Bob Attack Address`。

面试说法：

> 漏洞版地址修改工具没有鉴权，只要 order_id 存在就修改。这比信息泄露更严重，因为它是越权写操作，可能造成真实业务损失。

### Agent 漏洞根因

一句话：

> 工具执行层把模型传入的参数当成可信输入，没有做后端强制鉴权。

更完整说法：

> Agent 的模型层只能生成候选参数，不能决定用户是否有权执行操作。真正的权限判断必须在工具后端完成。否则攻击者可以通过提示注入、参数猜测或上下文污染诱导 Agent 调用工具操作其他用户资源。

## 第六部分：安全版和漏洞版对照表

| 场景 | 安全接口 | 漏洞接口 | 差异 |
|---|---|---|---|
| 文档详情 | `GET /documents/{id}` | 无 | 调用 `get_document_for_user` |
| RAG 检索 | `POST /rag/query` | `POST /lab/vulnerable-rag/query` | 安全版先按 user/tenant 过滤 chunk，漏洞版全局搜索 |
| 订单查询 | `POST /agent/tools/order-query` | `POST /lab/vulnerable-agent/order-query` | 安全版调用 `get_order_for_user`，漏洞版只按 `order_id` 查 |
| 地址修改 | `POST /agent/tools/address-update` | `POST /lab/vulnerable-agent/address-update` | 安全版先鉴权再修改，漏洞版直接修改 |

## 高频面试问答

### Q1：这个项目解决什么问题？

答：

> 这个项目模拟 AI 应用里的三类关键安全问题：API 权限边界、RAG 检索越权、Agent 工具调用越权。它通过安全接口和漏洞接口对比，展示同一个业务场景下后端是否做权限校验会导致完全不同的安全结果。

### Q2：为什么不一开始就接真实大模型？

答：

> 因为这个阶段重点是安全边界，不是模型效果。RAG 泄露和 Agent 越权的根因在后端检索和工具执行层，即使用关键词检索也能清楚复现。后续可以替换成真实向量数据库和 LLM，但 owner_id、tenant_id、后端鉴权这些原则不变。

### Q3：RAG 安全接口为什么 Bob 查不到 Alice 文档？

答：

> `/rag/query` 会通过 Token 得到 current_user，然后调用 `search_chunks_for_user`。这个方法只在当前用户可访问的 chunk 里检索，普通用户必须满足 chunk.owner_id 等于当前用户 ID，且 tenant_id 相同。因此 Bob 的检索范围里没有 Alice 的 chunk。

### Q4：漏洞 RAG 为什么能查到？

答：

> `/lab/vulnerable-rag/query` 调用的是 `search_all_chunks`，它对所有文档切片做全局检索，没有使用 current_user 做权限过滤。所以 Bob 只要输入匹配 Alice 文档的关键词，就能召回 Alice 的 chunk。

### Q5：Agent 安全接口为什么能拦截 Bob？

答：

> 安全版 Agent 工具会调用 `get_order_for_user`。这个函数不仅看 order_id 是否存在，还会检查订单 owner_id 和 tenant_id 是否匹配当前登录用户。Bob 查询或修改 Alice 的订单时不满足条件，所以返回 403。

### Q6：漏洞 Agent 接口为什么危险？

答：

> 漏洞接口只按 order_id 查订单，不校验当前用户是否拥有订单。查询接口会泄露订单信息，地址修改接口还能直接篡改 Alice 的订单地址。这说明 Agent 工具执行层必须做后端鉴权。

### Q7：系统提示词能不能防住这些问题？

答：

> 不能。提示词只能约束模型行为，不能作为强制权限边界。攻击者可能通过提示注入、多轮对话或参数猜测绕过模型约束。真正的安全控制必须在后端检索和工具执行阶段完成。

### Q8：这个项目里 `owner_id` 和 `tenant_id` 为什么都要检查？

答：

> owner_id 解决资源属于哪个用户的问题，tenant_id 解决资源属于哪个组织或租户的问题。真实企业应用通常是多租户系统，只检查 owner_id 不够完整。RAG chunk 和订单都继承这两个字段，才能统一做权限控制。

### Q9：管理员为什么可以查看全部资源？

答：

> 管理员角色通过 `require_admin` 单独校验。普通用户走 owner/tenant 限制，管理员用于审计或运维场景，可以查看全部资源。但管理员接口也必须后端鉴权，不能只靠前端隐藏。

### Q10：如果要继续完善，你会怎么做？

答：

> 我会做四件事：第一，接入 Chroma 或 Qdrant，把关键词检索替换成向量检索；第二，增加工具调用审计日志；第三，对地址修改、退款这类高风险工具加二次确认；第四，用 promptfoo 或 PyRIT 建立自动化安全测试集，把 RAG 泄露和 Agent 越权加入回归测试。

## 你需要重点背的 5 句话

1. 模型不能作为权限边界，后端必须强制鉴权。
2. RAG 权限控制必须发生在检索阶段，而不是召回后交给模型判断。
3. Agent 工具执行前必须校验当前用户是否有权操作目标资源。
4. 文档 chunk 和订单都要保留 `owner_id`、`tenant_id`，否则权限会在链路中丢失。
5. 安全版和漏洞版的核心差异是：是否使用 `current_user` 做资源过滤和操作授权。

## 面试演示顺序

推荐演示 6 分钟版本：

1. 先讲项目三版结构。
2. 演示 Alice 上传文档，Bob 直接访问被 `403`。
3. 演示 Bob 调 `/rag/query` 查不到 Alice 文档。
4. 演示 Bob 调 `/lab/vulnerable-rag/query` 能召回 Alice 文档。
5. 演示 Bob 调安全 Agent 工具查 Alice 订单被 `403`。
6. 演示 Bob 调漏洞 Agent 工具能查订单并改地址。
7. 总结：AI 应用安全关键在后端权限边界，不在模型“听不听话”。

## 代码追问时的回答策略

如果面试官问“你具体哪里实现了权限控制”，你按这个顺序答：

1. `auth.py` 里 `get_current_user` 从 Token 解析当前用户。
2. `database.py` 里安全函数使用 current_user 做 owner/tenant 检查。
3. `main.py` 里安全接口调用安全函数，漏洞接口调用不鉴权函数。
4. `models.py` 里所有资源都绑定 owner_id 和 tenant_id。

如果面试官问“漏洞是怎么故意制造的”，你这样答：

> 我没有绕过登录，用户仍然要登录；漏洞点在登录后没有做资源级授权。比如 vulnerable RAG 接口虽然拿到了 Bob 的 Token，但检索时没有用 Bob 的身份过滤 chunk；vulnerable Agent 接口虽然知道当前用户是 Bob，但查询和修改订单时没有校验订单归属。

这个回答很重要，因为它说明你理解：

- 认证 authentication 和授权 authorization 是两回事。
- 登录成功不代表有权访问所有资源。

