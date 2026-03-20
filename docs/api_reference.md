
# DragonDB HTTP API 参考

本文档描述了 DragonDB 对外公开的所有 HTTP 接口，以及可选的内部管理接口。所有请求和响应均使用 JSON 格式。

## 基础信息

- **基础 URL**：`http://<node_host>:<node_port>`
- **认证**：DragonDB 本身不提供内置认证，建议在应用层或通过反向代理实现（如 API 网关）。
- **时间戳**：时间戳采用 Unix 时间戳（秒级浮点数）或 ISO 8601 字符串（取决于应用实现，本 API 使用浮点数）。

## 公共 API

### 文档操作

#### 写入/更新文档

- **URL**：`/collections/{collection}/documents/{id}`
- **方法**：`PUT`
- **查询参数**：
  - `w`（可选，整数）：写一致性级别，要求至少多少个副本确认写入。取值范围 1~N（N 为副本数），默认 `2`。
- **请求体**：JSON 文档（任意合法 JSON 对象）
- **成功响应**：
  - 状态码：`201 Created`
  - 响应体：
    ```json
    {
      "status": "success",
      "document": {
        "id": "1001",
        "collection": "users",
        "data": { ... },
        "version_vector": { "node1": 1 },
        "timestamp": 1645000000.123
      },
      "w": 2
    }
    ```
- **错误响应**：
  - `400 Bad Request`：请求体不是合法 JSON。
  - `500 Internal Server Error`：写入失败（如无法达到指定 `w`）。

**示例**：
```bash
curl -X PUT "http://127.0.0.1:8081/collections/users/documents/1001?w=2" \
     -H "Content-Type: application/json" \
     -d '{"name":"Alice","age":30}'
```

#### 读取文档

- **URL**：`/collections/{collection}/documents/{id}`
- **方法**：`GET`
- **查询参数**：
  - `r`（可选，整数）：读一致性级别，要求至少多少个副本响应。默认 `2`。
- **成功响应**：
  - 状态码：`200 OK`
  - 响应体：与写入成功响应中的 `document` 结构相同，但外层不包含 `status` 和 `w`。
    ```json
    {
      "id": "1001",
      "collection": "users",
      "data": { "name": "Alice", "age": 30 },
      "version_vector": { "node1": 1 },
      "timestamp": 1645000000.123
    }
    ```
- **错误响应**：
  - `404 Not Found`：文档不存在。
  - `500 Internal Server Error`：读取失败（无法达到指定 `r`）。

**示例**：
```bash
curl "http://127.0.0.1:8081/collections/users/documents/1001?r=2"
```

#### 删除文档

- **URL**：`/collections/{collection}/documents/{id}`
- **方法**：`DELETE`
- **成功响应**：
  - 状态码：`200 OK`
  - 响应体：
    ```json
    { "status": "success" }
    ```
- **错误响应**：
  - `404 Not Found`：文档不存在。
  - `500 Internal Server Error`：删除失败。

**示例**：
```bash
curl -X DELETE http://127.0.0.1:8081/collections/users/documents/1001
```

### 查询文档

- **URL**：`/collections/{collection}/query`
- **方法**：`POST`
- **请求体**：JSON 对象，支持以下字段：
  ```json
  {
    "filter": { "age": { "$gt": 25 }, "name": "Alice" },
    "sort": { "name": 1 },
    "limit": 100,
    "offset": 0
  }
  ```
  - `filter`（对象）：查询条件，支持的操作符：
    - `$eq`：等于（默认，可直接写值）
    - `$gt`：大于
    - `$lt`：小于
    - `$gte`：大于等于
    - `$lte`：小于等于
  - `sort`（对象）：排序字段，`1` 升序，`-1` 降序。
  - `limit`（整数）：返回最大文档数，默认 `100`。
  - `offset`（整数）：分页偏移，默认 `0`。
- **成功响应**：
  - 状态码：`200 OK`
  - 响应体：
    ```json
    {
      "documents": [
        { "id": "...", "collection": "users", "data": { ... }, ... },
        ...
      ]
    }
    ```
- **错误响应**：
  - `400 Bad Request`：请求体格式错误。
  - `500 Internal Server Error`：查询执行失败。

**示例**：
```bash
curl -X POST http://127.0.0.1:8081/collections/users/query \
     -H "Content-Type: application/json" \
     -d '{"filter":{"age":{"$gt":25}},"limit":10}'
```

### 集合操作

#### 删除集合

- **URL**：`/collections/{collection}`
- **方法**：`DELETE`
- **成功响应**：
  - 状态码：`200 OK`
  - 响应体：
    ```json
    { "status": "success" }
    ```
- **错误响应**：
  - `404 Not Found`：集合不存在。
  - `500 Internal Server Error`：删除失败。

**示例**：
```bash
curl -X DELETE http://127.0.0.1:8081/collections/users
```

---

## 管理 API（可选）

这些接口用于管理和监控集群，通常只在内部使用，默认未开启认证，建议限制访问来源或添加简单令牌。

### 获取所有集合列表

- **URL**：`/admin/collections`
- **方法**：`GET`
- **成功响应**：
  - 状态码：`200 OK`
  - 响应体：
    ```json
    { "collections": ["users", "products", "orders"] }
    ```
- **错误响应**：
  - `500 Internal Server Error`：无法获取列表。

**示例**：
```bash
curl http://127.0.0.1:8081/admin/collections
```

### 获取指定集合的文档（分页）

- **URL**：`/admin/collections/{collection}/documents`
- **方法**：`GET`
- **查询参数**：
  - `limit`（可选，整数）：每页文档数，默认 `100`。
  - `offset`（可选，整数）：偏移量，默认 `0`。
- **成功响应**：
  - 状态码：`200 OK`
  - 响应体：
    ```json
    {
      "collection": "users",
      "count": 10,
      "offset": 0,
      "limit": 100,
      "documents": [
        { "id": "1001", "collection": "users", "data": { ... }, ... },
        ...
      ]
    }
    ```
- **错误响应**：
  - `400 Bad Request`：`limit`/`offset` 不是有效整数。
  - `500 Internal Server Error`：获取失败。

**示例**：
```bash
curl "http://127.0.0.1:8081/admin/collections/users/documents?limit=20&offset=0"
```

---

## 内部 RPC 接口（节点间通信）

这些接口仅供 DragonDB 节点内部使用，用于数据迁移、集群视图同步等。普通客户端不应直接调用。

| 端点 | 方法 | 用途 |
|------|------|------|
| `/internal/raw/{key}` | GET/PUT | 直接键值读写（key 为十六进制编码） |
| `/internal/raw/keys` | GET | 获取所有键的十六进制列表 |
| `/internal/cluster/update` | POST | 接收集群视图更新通知 |

---

## 错误码说明

| 状态码 | 含义 |
|--------|------|
| 200 | 请求成功 |
| 201 | 资源创建成功 |
| 400 | 请求格式错误（如无效 JSON、参数非法） |
| 404 | 文档或集合不存在 |
| 409 | 版本冲突（读取时返回多个版本） |
| 500 | 服务器内部错误（如一致性级别无法满足、存储故障） |

错误响应体示例：
```json
{ "error": "Write failed: only 1 acks, required 2" }
```

---

## 版本历史

- **v0.1.0**：初始版本，支持文档 CRUD、查询和基础管理接口。

---

## 注意事项

- 所有写入操作默认使用 `w=2`，读取操作默认 `r=2`。在单节点环境中，请指定 `w=1` 和 `r=1`。
- 查询功能目前支持简单等值过滤和比较操作符，不支持全文检索、正则表达式等复杂查询。
- 管理接口执行全表扫描，数据量大时性能较低，请勿频繁调用。

如有任何问题或建议，欢迎提交 Issue 或 Pull Request。
