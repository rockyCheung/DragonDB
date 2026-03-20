# DragonDB 用户手册

## 1. 概述

DragonDB 是一款轻量级分布式文档数据库，采用 JSON 文档模型，支持动态模式、数据分片、多副本复制和可调一致性。它适用于需要弹性扩展和高可用性的中小规模应用。

**核心特性**：
- **文档模型**：无模式 JSON 文档，灵活存储。
- **分布式架构**：对等节点，数据自动分片（一致性哈希），多副本（默认3）。
- **可调一致性**：通过 `w` 和 `r` 参数调整读写一致性级别。
- **RESTful API**：简单 HTTP 接口，类 MongoDB 查询语法。
- **持久化存储**：自研 DragonStore 引擎，基于 LSM 树，支持 WAL、Bloom 过滤器和后台合并。
- **动态节点管理**：支持在线添加/删除节点，并自动迁移数据。

## 2. 安装与配置

### 2.1 环境要求
- Python 3.10 或更高版本
- 操作系统：Linux / macOS / Windows

### 2.2 安装
```bash
# 克隆仓库
git clone https://github.com/your-repo/dragondb.git
cd dragondb

# 安装依赖
pip install -r requirements.txt
```

`requirements.txt` 内容：
```
aiofiles>=23.0.0
mmh3>=4.0.0
aiohttp>=3.8.0
pyyaml>=6.0
```

### 2.3 配置文件
DragonDB 使用 YAML 格式配置文件 `config.yaml`，示例：
```yaml
# 全局集群设置
cluster:
  replication_factor: 3   # 默认副本数

# 节点列表
nodes:
  node1:
    host: 127.0.0.1
    port: 8081
    data_dir: ./data/node1
    storage_options:
      sync_wal: false
      memtable_size: 4194304      # 4MB
      cache_size: 67108864         # 64MB
  node2:
    host: 127.0.0.1
    port: 8082
    data_dir: ./data/node2
  node3:
    host: 192.168.1.100           # 多机环境
    port: 8083
    data_dir: /var/dragondb/data/node3
```

## 3. 快速入门

### 3.1 启动单节点
```bash
# 修改配置文件为单节点
python start.py --node node1
```

### 3.2 基本操作
```bash
# 写入文档
curl -X PUT http://127.0.0.1:8081/collections/users/documents/1001 \
     -H "Content-Type: application/json" -d '{"name":"Alice","age":30}'

# 读取文档
curl http://127.0.0.1:8081/collections/users/documents/1001

# 查询文档
curl -X POST http://127.0.0.1:8081/collections/users/query \
     -H "Content-Type: application/json" -d '{"filter":{"age":{"$gt":25}}}'

# 删除文档
curl -X DELETE http://127.0.0.1:8081/collections/users/documents/1001
```

## 4. 数据操作

### 4.1 集合管理
集合无需显式创建，在首次写入文档时自动创建。但支持删除集合（慎用）：
```http
DELETE /collections/{collection}
```
示例：
```bash
curl -X DELETE http://127.0.0.1:8081/collections/users
```

### 4.2 文档写入/更新
```http
PUT /collections/{collection}/documents/{id}?w={w}
```
- `{collection}`：集合名称
- `{id}`：文档唯一标识
- `{w}`：写一致性级别（1~N），默认 2。N 为副本数。
- 请求体：JSON 文档

示例：
```bash
curl -X PUT "http://127.0.0.1:8081/collections/users/documents/1002?w=2" \
     -H "Content-Type: application/json" -d '{"name":"Bob","age":25}'
```

### 4.3 文档读取
```http
GET /collections/{collection}/documents/{id}?r={r}
```
- `{r}`：读一致性级别，默认 2

示例：
```bash
curl "http://127.0.0.1:8081/collections/users/documents/1002?r=2"
```

### 4.4 文档删除
```http
DELETE /collections/{collection}/documents/{id}
```
示例：
```bash
curl -X DELETE http://127.0.0.1:8081/collections/users/documents/1002
```

### 4.5 查询文档
```http
POST /collections/{collection}/query
```
请求体（JSON）：
```json
{
  "filter": {
    "age": {"$gt": 25},
    "name": "Alice"
  },
  "sort": {"name": 1},
  "limit": 10,
  "offset": 0
}
```
支持的操作符：`$eq`（默认）、`$gt`、`$lt`、`$gte`、`$lte`。

示例：
```bash
curl -X POST http://127.0.0.1:8081/collections/users/query \
     -H "Content-Type: application/json" -d '{"filter":{"age":{"$gt":25}}}'
```

### 4.6 批量写入
可通过多次调用 `PUT` 实现，未来版本将支持批量 API。

## 5. 集群管理

### 5.1 启动集群
```bash
# 启动配置文件中所有节点
python start.py --all
```
每个节点在独立进程中运行，日志输出到控制台。可通过 `Ctrl+C` 终止所有节点。

### 5.2 停止节点
停止单个节点：
```bash
# 使用停止脚本
./stop.sh --node node1
```
或直接终止进程。

### 5.3 动态添加节点
添加节点前，确保新节点已安装 DragonDB 并配置好数据目录。

**步骤**：
1. 在管理节点（任一现有节点）上执行添加命令：
```bash
python manage.py add node4 --host 192.168.1.101 --port 8084 --data-dir /data/node4
```
2. 脚本将更新所有节点的集群视图，并自动触发数据迁移，将属于新节点的数据从现有节点复制过去。
3. 启动新节点（如果尚未启动）：
```bash
python start.py --node node4
```

### 5.4 动态移除节点
移除节点前，确保目标节点已停止，或系统能容忍其下线。

**步骤**：
```bash
python manage.py remove node4
```
脚本将从集群元数据中移除该节点，并触发数据迁移，将原本存储在该节点上的数据复制到其他节点。完成后，节点可永久下线。

### 5.5 数据迁移
动态节点操作期间，系统会自动在后台迁移数据。迁移过程是全量扫描，数据量大时可能耗时较长，建议在业务低峰期执行。

可通过日志观察迁移进度：
```
Data migration to node4 completed.
Data migration after removal of node4 completed.
```

## 6. 配置详解

### 6.1 存储引擎选项
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `sync_wal` | 是否每次写入同步刷盘（true 保证数据不丢失，但降低性能） | `false` |
| `memtable_size` | MemTable 大小阈值（字节），超过后触发落盘 | 4194304 (4MB) |
| `cache_size` | 块缓存大小（字节） | 67108864 (64MB) |
| `l0_file_num_threshold` | Level 0 文件数触发合并 | 4 |
| `level_size_multiplier` | 层级大小倍数 | 10 |
| `base_level_size_mb` | Level 1 基准大小（MB） | 10 |

### 6.2 集群选项
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `replication_factor` | 副本数 | 3 |

## 7. 监控与维护

### 7.1 查看集群状态
可通过管理 API 获取集群信息（当前版本需手动实现或查看日志）。建议集成 Prometheus + Grafana 监控。

### 7.2 日志
每个节点将日志输出到控制台（或可重定向到文件）。可在启动脚本中添加重定向：
```bash
python start.py --node node1 > node1.log 2>&1
```

### 7.3 备份与恢复
**备份**：直接拷贝数据目录（如 `./data/node1`）即可。建议先停止节点，或使用文件系统快照。
```bash
tar -czf backup-node1.tar.gz ./data/node1
```

**恢复**：将备份目录解压到新节点的数据目录，启动节点即可自动恢复。

### 7.4 故障处理
**节点宕机**：
- 如果少于一半节点宕机，且副本数足够，读写仍可进行（取决于 `w` 和 `r` 设置）。
- 永久宕机节点需从集群中移除（`remove`），并确保数据已迁移。

**数据不一致**：DragonDB 使用向量时钟检测冲突，读取时会返回多个版本，由应用层选择合并（默认 LWW）。

**合并卡住**：检查磁盘空间和 SSTable 数量，可手动触发合并（需实现管理 API 或重启节点）。

## 8. API 参考（附录）

### 8.1 文档操作
| 方法 | 路径 | 说明 |
|------|------|------|
| PUT | `/collections/{collection}/documents/{id}?w={w}` | 写入/更新文档 |
| GET | `/collections/{collection}/documents/{id}?r={r}` | 读取文档 |
| DELETE | `/collections/{collection}/documents/{id}` | 删除文档 |
| POST | `/collections/{collection}/query` | 查询文档 |

### 8.2 集合操作
| 方法 | 路径 | 说明 |
|------|------|------|
| DELETE | `/collections/{collection}` | 删除集合（慎用） |

### 8.3 管理 API（内部）
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/admin/cluster/add_node` | 添加节点（请求体包含 node_id, host, port, data_dir） |
| POST | `/admin/cluster/remove_node` | 移除节点（请求体包含 node_id） |

## 9. 常见问题

### 9.1 为什么写入返回 `{"error": "Write failed: only 1 acks, required 2"}`？
- 当前请求的 `w` 值大于实际可用的副本数。在单节点集群中，应使用 `w=1`；三节点集群中，默认 `w=2` 需确保至少两个节点在线。

### 9.2 如何查看节点存储的数据？
数据存储在配置的 `data_dir` 目录下，包含 SSTable 文件和 WAL 日志。可通过 `ls` 查看。

### 9.3 动态添加节点后，数据未自动分布？
确保新节点已启动并运行，数据迁移可能需要时间。查看日志确认迁移已完成。

### 9.4 如何升级 DragonDB？
停止所有节点，备份数据目录，替换代码，重启节点。建议先在测试环境验证。

---

本手册覆盖了 DragonDB 的基本使用和运维操作。如有未尽事宜，请参考项目源码或提交 Issue。