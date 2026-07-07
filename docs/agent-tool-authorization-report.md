# Agent 工具调用越权报告 v0.1

## 漏洞标题

Agent 工具执行层缺少后端权限校验，导致跨用户订单查询与地址修改。

## 风险等级

高危。

## 影响场景

客服 Agent、订单助手、财务助手、退款助手、运维 Agent 等系统中，如果工具调用只相信模型传入的参数，而不在后端重新校验当前用户权限，攻击者可能诱导 Agent 查询或修改其他用户资产。

## 受影响接口

漏洞演示接口：

```text
POST /lab/vulnerable-agent/order-query
POST /lab/vulnerable-agent/address-update
```

安全接口：

```text
POST /agent/tools/order-query
POST /agent/tools/address-update
```

## 前置条件

- Alice 已登录并创建订单。
- Bob 已登录。
- Bob 知道或猜到 Alice 的 `order_id`。

## 复现步骤

### 1. Alice 创建订单

```text
POST /orders
```

```json
{
  "item_name": "Security Book",
  "shipping_address": "Alice Old Address"
}
```

返回：

```json
{
  "id": 1,
  "item_name": "Security Book",
  "shipping_address": "Alice Old Address",
  "owner_id": 2,
  "tenant_id": "tenant-a"
}
```

### 2. Bob 调用安全查询工具

```text
POST /agent/tools/order-query
```

```json
{
  "order_id": 1
}
```

预期结果：

```text
403 Forbidden
```

说明安全版工具在执行前校验了订单归属。

### 3. Bob 调用漏洞查询工具

```text
POST /lab/vulnerable-agent/order-query
```

```json
{
  "order_id": 1
}
```

漏洞结果：

```json
{
  "id": 1,
  "item_name": "Security Book",
  "shipping_address": "Alice Old Address",
  "owner_id": 2,
  "tenant_id": "tenant-a"
}
```

说明漏洞版工具只按 `order_id` 查询，没有校验当前用户是否拥有该订单。

### 4. Bob 调用安全地址修改工具

```text
POST /agent/tools/address-update
```

```json
{
  "order_id": 1,
  "new_address": "Bob Attack Address"
}
```

预期结果：

```text
403 Forbidden
```

### 5. Bob 调用漏洞地址修改工具

```text
POST /lab/vulnerable-agent/address-update
```

```json
{
  "order_id": 1,
  "new_address": "Bob Attack Address"
}
```

漏洞结果：

```json
{
  "id": 1,
  "shipping_address": "Bob Attack Address"
}
```

说明 Bob 成功修改了 Alice 的订单地址。

## 根因分析

漏洞接口的问题不是“模型回答错了”，而是工具执行层没有权限控制：

```text
order = get_order(order_id)
order.shipping_address = new_address
```

安全实现必须把当前登录用户传入工具执行层，并在执行前校验：

```text
order.owner_id == current_user.id
order.tenant_id == current_user.tenant_id
```

## 修复方案

### 必须修复

- 工具执行前必须做后端鉴权。
- 工具参数不能完全相信模型输出。
- 写操作必须校验业务归属。
- 高风险操作建议增加二次确认。
- 工具调用需要记录审计日志。

### 推荐增强

- 为每个工具定义权限矩阵。
- 区分只读工具和写操作工具。
- 对退款、转账、删库、发邮件等高风险工具强制人工确认。
- 记录 `user_id`、`tenant_id`、`tool_name`、`order_id`、执行结果。
- 对异常工具调用频率做告警。

## 面试讲法

这个漏洞说明 Agent 安全不能依赖提示词或模型自觉。即使系统提示词要求“只能操作当前用户订单”，攻击者仍可能诱导模型传入其他人的 `order_id`。真正的安全边界必须在工具后端实现，模型只负责生成候选参数，后端负责鉴权和执行。
