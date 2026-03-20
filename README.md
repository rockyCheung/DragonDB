# DragonDB

**轻量级分布式文档数据库** · 弹性扩展 · 可调一致性 · 自研存储引擎

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/your-repo/dragondb/pulls)

---

## 简介

DragonDB 是一款由 Python 实现的轻量级分布式文档数据库，旨在为现代应用提供灵活、可扩展的数据存储方案。它采用 **JSON 文档模型**，支持动态模式（schema‑free），通过一致性哈希自动分片，并提供可调一致性（quorum NWR）与向量时钟冲突处理。自研存储引擎 **DragonStore** 基于 LSM 树，内置 WAL、Bloom 过滤器、缓存和后台合并，兼顾高性能写入与可靠持久化。

无论您是构建微服务、物联网平台还是电商应用，DragonDB 都能以简单的 RESTful API 和类 MongoDB 查询语法，助您快速迭代、轻松扩展。

---

## 核心特性

- 📄 **文档模型** – 无模式 JSON 文档，灵活应对业务变化。
- ⚖️ **分布式架构** – 对等节点，数据自动分片（一致性哈希），多副本复制（默认 3 副本）。
- 🔧 **可调一致性** – 通过 `w` 和 `r` 参数调整读写一致性级别，在可用性与强一致间自由权衡。
- 🗃️ **自研存储引擎 DragonStore** – LSM 树结构，支持 WAL、Bloom 过滤器、块缓存与分层合并，高效利用磁盘。
- 🌐 **RESTful API** – 简单易用的 HTTP 接口，查询语法兼容 MongoDB 风格。
- 🚀 **动态节点管理** – 支持在线添加/移除节点，数据自动迁移，集群无缝扩缩容。
- 📦 **轻量级** – 纯 Python 实现，依赖少，单节点内存占用低，启动快速。

---

## 快速开始

### 环境要求
- Python 3.10 或更高版本
- Linux / macOS / Windows

### 安装
```bash
git clone https://github.com/rockyCheung/DragonDB/dragondb.git
cd dragondb
pip install -r requirements.txt
```

### 配置集群
编辑 `config.yaml`，定义节点信息：
```yaml
cluster:
  replication_factor: 3
nodes:
  node1:
    host: 127.0.0.1
    port: 8081
    data_dir: ./data/node1
  node2:
    host: 127.0.0.1
    port: 8082
    data_dir: ./data/node2
  node3:
    host: 127.0.0.1
    port: 8083
    data_dir: ./data/node3
```

### 启动集群
```bash
# 启动所有节点（多进程）
python start.py --all
```

### 基础操作
```bash
# 写入文档
curl -X PUT http://127.0.0.1:8081/collections/users/documents/1001 \
     -H "Content-Type: application/json" -d '{"name":"Alice","age":30}'

# 读取文档
curl http://127.0.0.1:8081/collections/users/documents/1001

# 查询文档（年龄大于 25）
curl -X POST http://127.0.0.1:8081/collections/users/query \
     -H "Content-Type: application/json" -d '{"filter":{"age":{"$gt":25}}}'

# 删除文档
curl -X DELETE http://127.0.0.1:8081/collections/users/documents/1001
```

---

## 文档与资源

- [用户手册](docs/user_manual.md) – 安装、配置、API 详解、运维指南。
- [开发手册](docs/developer_manual.md) – 数据模型设计、权限管理、最佳实践。
- [API 参考](docs/api_reference.md) – 完整的 HTTP 接口说明。
- [贡献指南](CONTRIBUTING.md) – 如何参与项目开发。

---

## 架构概览

DragonDB 每个节点由以下模块构成：

- **API 层**：基于 `aiohttp` 提供 RESTful 接口。
- **协调器**：处理读写请求的 Quorum 协调、版本向量冲突检测。
- **集群管理器**：维护节点列表、一致性哈希环和副本映射。
- **存储引擎 DragonStore**：LSM 树持久化引擎，包含 MemTable、WAL、SSTable、Bloom 过滤器、缓存与合并管理器。

节点间通过 HTTP 进行 RPC 通信，实现真正的分布式协作。

---

## 为什么选择 DragonDB？

- **简单** – 无需学习复杂 SQL，JSON 文档 + HTTP 接口，上手即用。
- **灵活** – 动态模式，文档结构可随业务变化随时调整。
- **可靠** – 多副本 + WAL 保证数据不丢，可调一致性满足不同业务需求。
- **扩展性** – 在线节点扩缩容，数据自动重分布，无需停机。

---

## 贡献

欢迎提交 issue 和 pull request！请阅读 [贡献指南](CONTRIBUTING.md) 了解开发流程、代码风格和测试要求。

---

## 许可证

DragonDB 使用 [Apache 2.0 许可证](LICENSE)。

---

**DragonDB** – 让数据存储更简单、更弹性。
