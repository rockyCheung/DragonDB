
# DragonDB 开发手册

## 1. 引言

DragonDB 是一款基于文档模型的分布式数据库，旨在为现代应用提供灵活、可扩展的数据存储方案。本手册面向开发者，帮助您从传统关系型数据库思维过渡到文档模型，指导您如何设计数据模型、处理关联关系、实现权限管理，并总结开发过程中的注意事项和最佳实践。

## 2. 从关系模型到文档模型

### 2.1 关系模型的局限性
- 严格的表结构，修改 schema 成本高。
- 多表关联查询（JOIN）随数据量增长性能下降。
- 水平扩展复杂，通常需要分库分表。

### 2.2 文档模型的优势
- 无模式（schema-free），文档结构灵活，适应业务快速变化。
- 数据聚合存储，减少关联查询，提升读取性能。
- 天然支持分布式，通过一致性哈希自动分片。

### 2.3 映射策略
传统关系模型中的实体和关系，在文档模型中可通过以下方式表达：

| 关系类型 | 文档模型策略 | 适用场景 |
|----------|--------------|----------|
| 一对一 | 嵌入子文档 | 地址、配置信息 |
| 一对多 | 嵌入数组 | 订单中的商品列表、文章的评论 |
| 多对多 | 引用 + 反范式 | 用户与角色、商品与分类 |

**原则**：优先考虑嵌入（denormalization），以减少读取时的额外查询；当嵌入导致数据冗余过大或更新频繁时，采用引用。

## 3. 电商数据结构设计

本节以典型电商系统为例，详细说明如何在 DragonDB 中定义 Collection 和 Document。

### 3.1 集合规划

根据业务领域划分集合，每个集合对应一种文档类型：

- `users`：用户信息
- `products`：商品信息
- `orders`：订单信息
- `categories`：商品分类
- `reviews`：商品评价

### 3.2 用户集合（users）

```json
{
  "_id": "user_1001",                     // 文档唯一标识，建议使用业务前缀+唯一ID
  "username": "alice",
  "email": "alice@example.com",
  "phone": "+1234567890",
  "profile": {
    "avatar": "https://...",
    "bio": "I love shopping"
  },
  "addresses": [                          // 嵌入地址数组
    {
      "type": "home",
      "recipient": "Alice",
      "street": "123 Main St",
      "city": "Springfield",
      "zip": "12345",
      "is_default": true
    }
  ],
  "created_at": "2023-01-01T10:00:00Z",
  "updated_at": "2023-01-01T10:00:00Z"
}
```

- **设计要点**：
  - 地址数量有限，且常与用户信息一起读取，适合嵌入。
  - 密码等敏感信息应加密存储，避免明文。
- **索引建议**：为 `email`、`username` 建立唯一索引（需应用层保证）。

### 3.3 商品集合（products）

```json
{
  "_id": "prod_2001",
  "title": "Dell XPS 15 Laptop",
  "description": "Powerful laptop for developers",
  "price": 1499.99,
  "stock": 50,
  "categories": ["electronics", "computers"],   // 引用分类ID或分类名称
  "attributes": {
    "brand": "Dell",
    "processor": "Intel i7",
    "ram": "16GB",
    "storage": "512GB SSD"
  },
  "images": [                                    // 商品图片列表
    "https://.../img1.jpg",
    "https://.../img2.jpg"
  ],
  "seller_id": "user_1001",                      // 卖家ID（引用用户）
  "created_at": "2023-01-01T10:00:00Z",
  "updated_at": "2023-01-01T10:00:00Z"
}
```

- **设计要点**：
  - 通过 `seller_id` 引用卖家，避免在商品中嵌入完整用户信息。
  - 属性字段使用对象存储，支持动态键值。
- **索引建议**：为 `categories`、`price`、`seller_id` 建立索引，支持分类查询和价格范围查询。

### 3.4 订单集合（orders）

订单是核心聚合，应包含用户信息和商品快照，确保历史数据不变。

```json
{
  "_id": "order_3001",
  "user": {
    "id": "user_1001",
    "username": "alice",
    "email": "alice@example.com"
  },
  "items": [
    {
      "product_id": "prod_2001",
      "title": "Dell XPS 15 Laptop",
      "price": 1499.99,
      "quantity": 1,
      "subtotal": 1499.99
    }
  ],
  "total_amount": 1499.99,
  "payment": {
    "method": "credit_card",
    "transaction_id": "txn_123456",
    "status": "paid"
  },
  "shipping": {
    "address": {
      "recipient": "Alice",
      "street": "123 Main St",
      "city": "Springfield",
      "zip": "12345"
    },
    "method": "express",
    "tracking_number": "TRK123456",
    "status": "shipped"
  },
  "status": "completed",                         // 订单状态：pending, paid, shipped, completed, cancelled
  "order_date": "2023-02-01T11:00:00Z",
  "paid_at": "2023-02-01T11:05:00Z",
  "shipped_at": "2023-02-02T09:00:00Z"
}
```

- **设计要点**：
  - 嵌入用户快照，避免用户信息变更影响订单历史。
  - 嵌入商品快照，保留下单时的商品信息（价格、标题）。
  - 订单状态变更通过更新文档实现，可使用版本向量防止并发覆盖。
- **索引建议**：为 `user.id`、`order_date`、`status` 建立索引，支持用户订单查询和时间范围统计。

### 3.5 商品分类集合（categories）

```json
{
  "_id": "cat_101",
  "name": "Electronics",
  "slug": "electronics",
  "parent_id": null,                             // 引用父分类，实现层级
  "path": "/electronics",
  "level": 1,
  "created_at": "2023-01-01T10:00:00Z"
}
```

- **设计要点**：
  - 通过 `parent_id` 构建树形结构，查询时需应用层递归。
  - 可预计算 `path` 字段加速查询。
- **索引建议**：为 `parent_id`、`slug` 建立索引。

### 3.6 商品评价集合（reviews）

```json
{
  "_id": "rev_5001",
  "product_id": "prod_2001",
  "user": {
    "id": "user_1001",
    "username": "alice"
  },
  "rating": 5,
  "title": "Great laptop!",
  "content": "Fast delivery, product as described.",
  "images": ["https://.../review1.jpg"],
  "created_at": "2023-02-05T15:30:00Z",
  "updated_at": "2023-02-05T15:30:00Z"
}
```

- **设计要点**：
  - 嵌入用户快照，避免关联用户表。
  - 评价通常与商品一起读取，但独立存储可避免商品文档过大。
- **索引建议**：为 `product_id`、`rating` 建立索引，支持商品评价列表和评分统计。

### 3.7 分片键选择

DragonDB 使用一致性哈希根据文档 `_id` 进行分片。分片键的选择影响数据分布和查询效率：

- **用户集合**：使用 `_id`（如 `user_{uuid}`），分布均匀。
- **商品集合**：同样使用 `_id`（如 `prod_{uuid}`）。
- **订单集合**：可考虑将用户 ID 作为 `_id` 的前缀（如 `user_1001:order_3001`），使同一用户的订单位于同一节点，便于批量查询。但需避免热点（如大 V 用户）。也可使用纯 UUID，通过索引查询用户订单。
- **评价集合**：使用 `product_id` 作为分片键（嵌入在 `_id` 中，如 `prod_2001:rev_5001`），使同一商品的评价集中在同一节点，便于聚合计算。

**最佳实践**：在 `_id` 中包含业务前缀和均匀分布的哈希值，例如 `user:{uuid}`、`order:{user_id}:{timestamp}`。

### 3.8 索引设计

通过元数据管理索引（需管理 API）。以下为电商场景建议的索引：

| 集合 | 索引字段 | 作用 |
|------|----------|------|
| users | `email` | 登录验证，唯一性 |
| users | `username` | 用户搜索 |
| products | `categories` | 按分类筛选商品 |
| products | `price` | 价格范围查询 |
| products | `seller_id` | 查询卖家商品 |
| orders | `user.id` | 查询用户订单 |
| orders | `order_date` | 时间范围统计 |
| orders | `status` | 按状态过滤订单 |
| reviews | `product_id` | 获取商品评价 |
| reviews | `rating` | 评分排序 |

### 3.9 数据访问模式示例

#### 3.9.1 用户注册
```http
PUT /collections/users/documents/user_{uuid}
{
  "username": "bob",
  "email": "bob@example.com",
  "password_hash": "...",  // 敏感信息建议加密
  "profile": {...}
}
```

#### 3.9.2 用户登录（验证邮箱）
```http
POST /collections/users/query
{
  "filter": {"email": "bob@example.com"},
  "limit": 1
}
```

#### 3.9.3 创建订单（涉及商品库存检查和扣减）
需结合应用层事务（目前不支持跨文档事务，建议使用乐观锁）：
- 读取商品文档，检查库存，获取版本向量。
- 写入订单文档。
- 更新商品库存，传入版本向量，若版本变化则重试。

```http
PUT /collections/products/documents/prod_2001
{
  "stock": 49  // 假设原库存50，需在应用层比较版本向量
}
```

#### 3.9.4 查询用户订单（按时间倒序）
```http
POST /collections/orders/query
{
  "filter": {"user.id": "user_1001"},
  "sort": {"order_date": -1},
  "limit": 20
}
```

#### 3.9.5 商品评价列表
```http
POST /collections/reviews/query
{
  "filter": {"product_id": "prod_2001"},
  "sort": {"created_at": -1},
  "limit": 50
}
```

### 3.10 数据一致性考虑

- **订单与库存**：使用版本向量实现乐观锁，避免超卖。写入订单前先读取商品，获取当前版本向量，写入时传入该向量，若版本变化则重试。
- **支付状态更新**：订单状态变更可视为单个文档更新，使用 `w=2` 确保至少两个副本确认。
- **用户信息修改**：直接更新用户文档，无需关心引用快照（订单中的用户快照已固化）。

## 4. 权限管理与访问控制

DragonDB 本身不提供内置的用户认证和授权机制，但可通过以下方式在应用层实现：

### 4.1 集合级权限
根据业务需求将不同敏感级别的数据划分到不同集合，应用层在访问时根据用户角色限制可访问的集合。例如：
- `users_public`：公开用户信息
- `users_private`：敏感信息（如密码、邮箱）

### 4.2 文档级权限
通过在文档中嵌入权限标签，应用层在查询时过滤。例如，在订单文档中添加 `owner_id` 字段：
```json
{
  "_id": "order_3001",
  "owner_id": "user_1001",
  ...
}
```
查询时强制附加 `owner_id` 条件，确保用户只能访问自己的订单。

### 4.3 字段级权限
对于需要隐藏部分字段的场景，可在应用层读取文档后移除敏感字段，或使用投影查询（暂未支持，可自行实现）。

### 4.4 应用层认证与授权
推荐在 DragonDB 前端部署一个 API 网关或业务服务，负责：
- 用户认证（JWT、Session）
- 解析用户角色和权限
- 构造安全的数据库查询（自动附加 `owner_id` 等条件）
- 返回脱敏后的数据

例如，使用 Python 的 `aiohttp` 中间件实现：
```python
@web.middleware
async def auth_middleware(request, handler):
    token = request.headers.get('Authorization')
    user = decode_jwt(token)
    request['user'] = user
    # 在后续处理中，可根据 user.id 自动添加过滤条件
    return await handler(request)
```

## 5. 开发注意事项

### 5.1 数据分片与副本
- **选择分片键**：文档的 `_id` 默认作为分片键。对于频繁查询的字段，可考虑使用业务 ID 作为分片键，但要避免热点。
- **副本因子**：默认 3，确保高可用。写入时可通过 `w` 参数调整一致性，读取时通过 `r` 参数。

### 5.2 索引设计
- 索引会占用额外存储并略微降低写入性能，需权衡。
- 为常用查询字段建立索引，避免全表扫描。

### 5.3 版本向量与冲突处理
DragonDB 使用向量时钟检测并发更新。写入时，若检测到冲突，会返回多个版本，由应用层解决。建议：
- 在应用层实现冲突合并策略（例如最后写入胜利 LWW，或自定义合并逻辑）。
- 对于关键数据（如库存），使用版本向量实现乐观锁。

### 5.4 数据一致性
根据 CAP 理论，DragonDB 在分区发生时优先保证可用性（AP）。可通过设置 `w + r > N` 实现强一致性，但会降低可用性。根据业务需求选择合适级别：
- 金融交易：强一致性（w=N, r=1）
- 社交动态：最终一致性（w=1, r=1）

### 5.5 存储引擎调优
- **同步刷盘**：生产环境建议 `sync_wal: true` 保证数据不丢失。
- **MemTable 大小**：增大可减少落盘频率，但增加内存占用。
- **缓存大小**：根据可用内存调整，提升热点数据读取速度。

## 6. 开发流程与最佳实践

### 6.1 设计阶段
1. **识别聚合边界**：分析业务中哪些数据经常一起读取，将其设计为一个文档。
2. **确定分片键**：选择分布均匀且查询频繁的字段。
3. **规划索引**：列出所有查询模式，确定需要索引的字段。
4. **设计权限模型**：定义用户角色和文档所有权，确定如何在应用层过滤。

### 6.2 开发阶段
1. **使用 SDK 或 HTTP 客户端**：封装 API 调用，简化数据库操作。
2. **实现版本冲突处理**：读取时检查版本，写入时传入最新版本向量。
3. **测试覆盖**：包括单元测试（mock 数据库）、集成测试（真实集群）。

### 6.3 部署与运维
1. **配置管理**：使用 `config.yaml` 管理节点信息，避免硬编码。
2. **监控**：集成日志和指标（如请求延迟、存储使用量）。
3. **备份**：定期备份数据目录，测试恢复流程。
4. **动态节点管理**：使用 `manage.py` 脚本添加/移除节点，并监控数据迁移进度。

## 7. 常见陷阱与规避

- **过度嵌入**：嵌入数组无限增长（如文章评论），应分页或拆分为独立集合。
- **热点分片**：使用自增 ID 作为分片键可能导致写入集中在单个节点，改用 UUID 或哈希值。
- **忽略版本向量**：并发写入导致数据覆盖，务必使用版本向量进行冲突检测。
- **未考虑索引**：全表扫描查询性能差，需为常用查询建立索引。
- **忽略备份**：节点故障可能导致数据丢失，务必定期备份。

## 8. 开发路线图

- **第1周**：熟悉 DragonDB API，在本地运行单节点，完成 CRUD 操作。
- **第2周**：设计业务数据模型，实现应用层权限管理。
- **第3周**：搭建三节点集群，测试数据分片和副本复制。
- **第4周**：集成到业务代码，进行性能测试和优化。
- **第5周**：部署到生产环境，配置监控和备份。

---

本手册旨在帮助开发者快速上手 DragonDB，并遵循最佳实践构建可靠的应用。如有疑问，请参考项目源码或社区支持。
