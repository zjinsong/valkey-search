# Valkey 向量搜索架构指南

## 概述

ElastiCache Valkey 9.0 内置向量搜索（基于 HNSW/FLAT 索引），结合 Amazon S3 Vectors 和 Neptune Analytics，可构建完整的 AI Agent 记忆系统和 RAG 应用。

---

## 架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AI Agent / 应用层                                │
│              (Strands / LangChain / 自定义 Agent)                        │
│                              │                                           │
│                         Mem0 记忆编排层                                   │
│              (提取、存储、检索、去重、衰减)                                │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          ▼                    ▼                    ▼
┌─────────────────┐  ┌──────────────────┐  ┌──────────────────────────────┐
│  ElastiCache    │  │ Neptune Analytics│  │       S3 Vectors             │
│  Valkey 9.0     │  │  (图谱记忆)       │  │  (冷向量归档)                 │
│                 │  │                  │  │                              │
│ • 向量搜索       │  │ • 实体关系图谱    │  │ • 20亿向量/索引               │
│   FT.SEARCH KNN │  │ • 多跳推理        │  │ • 比专用向量库便宜90%          │
│ • 全文搜索       │  │ • 知识图谱        │  │ • 100ms~亚秒级延迟            │
│ • 实时聚合       │  │ • 关系遍历        │  │ • 无需预置基础设施             │
│ • 微秒级延迟     │  │                  │  │                              │
│ • 写后即读一致性  │  │                  │  │                              │
└────────┬────────┘  └──────────────────┘  └──────────────┬───────────────┘
         │                                                 │
         │  热数据（近期记忆、活跃会话）                      │  冷数据（历史归档）
         └─────────────────────────────────────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │    Amazon S3       │
                    │  (原始文件存储)      │
                    │  PDF/图片/视频      │
                    └────────────────────┘
```

---

## 各层职责

### ElastiCache Valkey 9.0（热数据层）

**适用场景**：实时搜索、活跃 Agent 记忆、高频查询

```python
import redis
import numpy as np

client = redis.Redis(host="your-endpoint", port=6379, decode_responses=False)

# 1. 创建向量索引
client.execute_command(
    "FT.CREATE", "memory_idx",
    "ON", "HASH", "PREFIX", "1", "mem:",
    "SCHEMA",
    "content", "TEXT",
    "user_id", "TAG",
    "session_id", "TAG",
    "created_at", "NUMERIC", "SORTABLE",
    "embedding", "VECTOR", "FLAT", "6",
        "TYPE", "FLOAT32",
        "DIM", "1024",
        "DISTANCE_METRIC", "COSINE"
)

# 2. 存储记忆（向量 + metadata 在同一个 Hash）
def store_memory(mem_id, content, user_id, embedding):
    client.hset(f"mem:{mem_id}", mapping={
        "content": content,
        "user_id": user_id,
        "created_at": int(time.time()),
        "embedding": np.array(embedding, dtype=np.float32).tobytes()
    })

# 3. 语义检索（KNN 向量搜索）
def search_memory(query_embedding, user_id, top_k=5):
    query_vec = np.array(query_embedding, dtype=np.float32).tobytes()
    return client.execute_command(
        "FT.SEARCH", "memory_idx",
        f"@user_id:{{{user_id}}}=>[KNN {top_k} @embedding $vec AS score]",
        "RETURN", "3", "content", "created_at", "score",
        "SORTBY", "score",
        "DIALECT", "2",
        "PARAMS", "2", "vec", query_vec
    )
```

**性能指标**（单节点 cache.r7g.2xlarge，130万文档）：

| 查询类型 | P50 延迟 | QPS（300并发） |
|---------|---------|--------------|
| 精确匹配 | 0.135ms | 60,000 |
| 混合查询（文本+向量） | 0.135ms | 52,632 |
| 数值范围 | 0.175ms | 24,087 |

---

### S3 Vectors（冷数据层）

**适用场景**：历史记忆归档、数十亿级向量、低频查询、成本敏感

```python
import boto3

s3 = boto3.client("s3", region_name="cn-northwest-1")

# 1. 创建向量桶和索引
s3.create_bucket(
    Bucket="my-vector-archive",
    CreateBucketConfiguration={"LocationConstraint": "cn-northwest-1"}
)

# 注意：S3 Vectors 使用专用 API
s3vectors = boto3.client("s3vectors", region_name="cn-northwest-1")

s3vectors.create_index(
    Bucket="my-vector-archive",
    IndexName="long-term-memory",
    Dimension=1024,
    DistanceMetric="cosine"
)

# 2. 归档向量（从 ElastiCache 迁移冷数据）
s3vectors.put_vectors(
    Bucket="my-vector-archive",
    IndexName="long-term-memory",
    Vectors=[{
        "Key": "mem-001",
        "Data": {"Float32": embedding_list},
        "Metadata": {"user_id": "u123", "date": "2025-01"}
    }]
)

# 3. 查询（低频，100ms+）
results = s3vectors.query_vectors(
    Bucket="my-vector-archive",
    IndexName="long-term-memory",
    QueryVector={"Float32": query_embedding},
    TopK=10,
    Filter={"user_id": {"$eq": "u123"}}
)
```

---

### Neptune Analytics（关系记忆层）

**适用场景**：实体关系、多跳推理、知识图谱

```python
from mem0 import Memory

config = {
    "vector_store": {
        "provider": "valkey",
        "config": {
            "valkey_url": "your-elasticache-endpoint:6379",
            "index_name": "agent_memory",
            "embedding_model_dims": 1024
        }
    },
    "graph_store": {
        "provider": "neptune",
        "config": {
            "endpoint": "neptune-graph://<GRAPH_ID>"
        }
    }
}

memory = Memory.from_config(config)

# 存储记忆（自动路由到向量存储或图存储）
memory.add("用户喜欢 Python 和机器学习", user_id="user_001")

# 检索（语义 + 图关系联合查询）
results = memory.search("用户的技术偏好", user_id="user_001")
```

---

## 热冷分层策略

```
写入路径：
  新记忆 → ElastiCache（立即可搜索，微秒延迟）
              │
              │ TTL 到期 / 定期归档任务
              ▼
           S3 Vectors（永久保存，低成本）

读取路径：
  查询 → ElastiCache（命中：微秒返回）
              │ 未命中
              ▼
           S3 Vectors（回查：100ms+）
              │
              │ 热门记忆回填
              ▼
           ElastiCache（预热缓存）
```

**成本对比**：

| 存储层 | 延迟 | 成本 | 适用数据量 |
|--------|------|------|-----------|
| ElastiCache r7g.large | 微秒 | 高（内存价格） | 百万级 |
| S3 Vectors | 100ms+ | 低（比向量DB便宜90%） | 十亿级 |

---

## RAG 完整链路

```
用户提问
  │
  ▼
Bedrock Titan Embed V2（生成 query embedding，1024维）
  │
  ▼
ElastiCache 混合搜索
  @category:{tech} @date:[最近30天 +inf] => [KNN 5 @embedding $vec]
  │
  ├─ 命中 → 返回相关文档片段（微秒）
  │
  └─ 未命中或需要更多上下文
        │
        ▼
     S3 Vectors 查询（历史文档库）
        │
        ▼
     从 S3 取原始文件（用 s3_key 关联）
  │
  ▼
组合 context → Bedrock Claude 生成回答
```

---

## Mem0 + ElastiCache + Neptune 实测效果

来源：[AWS Blog - Build persistent memory for agentic AI applications](https://aws.amazon.com/cn/blogs/database/build-persistent-memory-for-agentic-ai-applications-with-mem0-open-source-amazon-elasticache-for-valkey-and-amazon-neptune-analytics/)

| 指标 | 无记忆 | 有记忆（ElastiCache） | 提升 |
|------|--------|---------------------|------|
| Token 消耗 | 70,373 | 6,344 | **减少 91%** |
| 响应时间 | 9.25s | 2s | **快 4.6x** |
| 工具调用次数 | 3次（网页抓取） | 0次（从记忆取） | **减少 100%** |

---

## 向量模型选择（中国区）

| 模型 | 维度 | 部署方式 | 适用场景 |
|------|------|---------|---------|
| Amazon Titan Embed V2 | 256/512/1024 | Bedrock（托管） | 通用，快速上手 |
| BAAI/BGE-M3 | 1024 | EC2/SageMaker 自部署 | 中文语义精度最高 |
| GTE-large（阿里） | 1024 | EC2/SageMaker 自部署 | 中英文均衡 |

**推荐**：中国区生产环境用 Bedrock Titan Embed V2（256维可降低存储和搜索成本）。

---

## 快速开始

```bash
# 1. 部署 CloudFormation 模板
aws cloudformation deploy \
  --template-file cloudformation.yaml \
  --stack-name valkey-search-stack \
  --parameter-overrides \
    VpcId=vpc-xxxxxxxx \
    SubnetIds="subnet-aaa,subnet-bbb" \
    AppSecurityGroupId=sg-xxxxxxxx \
    NodeType=cache.t4g.micro \
    ReservedMemoryPercent=50 \
  --region cn-northwest-1

# 2. 获取 Endpoint
aws cloudformation describe-stacks \
  --stack-name valkey-search-stack \
  --query "Stacks[0].Outputs[?OutputKey=='PrimaryEndpoint'].OutputValue" \
  --output text \
  --region cn-northwest-1

# 3. 运行 Demo
python3 valkey9_demo.py <endpoint>

# 4. 启动 Dashboard
streamlit run valkey9_dashboard.py --server.port 8501 --server.headless true
```

---

## 场景对比：Valkey 搜索/聚合 vs OpenSearch vs OLAP vs 数据仓库

### 能力对比矩阵

| 能力维度 | Valkey 9.0 | OpenSearch | ClickHouse/OLAP | Redshift/数据仓库 |
|---------|-----------|-----------|----------------|-----------------|
| **延迟** | 微秒级 | 毫秒~百毫秒 | 毫秒~秒 | 秒~分钟 |
| **数据量** | GB~TB（内存限制） | TB 级 | PB 级 | PB 级 |
| **全文搜索** | ✅ 基础（前缀/模糊/短语） | ✅ 强（分词/同义词/相关性调优） | ❌ 弱 | ❌ 弱 |
| **向量搜索** | ✅ 内置 KNN | ✅ k-NN 插件 | ⚠️ 部分支持 | ❌ |
| **精确匹配/Tag** | ✅ | ✅ | ✅ | ✅ |
| **数值范围** | ✅ | ✅ | ✅ | ✅ |
| **聚合分析** | ✅ 基础（GROUPBY/SUM/AVG） | ✅ 中等 | ✅ 强（复杂分析） | ✅ 最强（完整 SQL） |
| **多表 JOIN** | ❌ | ❌ | ✅ | ✅ |
| **写后即读一致性** | ✅ 同步索引 | ⚠️ 1秒 refresh delay | ⚠️ 近实时 | ❌ 批量加载 |
| **持久化** | ⚠️ RDB/AOF，可能丢数据 | ✅ 强 | ✅ 强 | ✅ 最强 |
| **中文分词** | ❌ 需自行处理 | ✅ IK 分词器 | ❌ | ❌ |
| **额外费用** | ✅ 免费（Valkey 9.0 内置） | 💰 独立集群 | 💰 独立集群 | 💰 独立集群 |
| **运维复杂度** | 低（托管） | 中 | 中~高 | 低（托管） |

### 适用场景决策树

```
需要搜索/查询数据？
│
├─ 数据已在 ElastiCache 里？
│   └─ YES → 直接用 Valkey FT.SEARCH（零额外成本，微秒延迟）
│
├─ 需要复杂中文分词/同义词/相关性评分？
│   └─ YES → OpenSearch
│
├─ 需要实时写入 + 毫秒级复杂聚合（亿行级）？
│   └─ YES → ClickHouse / OLAP
│
├─ 需要历史数据分析 / 复杂 SQL JOIN / BI 报表？
│   └─ YES → Redshift / Athena（数据仓库）
│
└─ 需要实时应用层搜索 + 低延迟 + 向量搜索？
    └─ YES → Valkey 9.0（本方案）
```

### 典型架构组合

```
实时应用层（用户请求）
    │
    ▼
ElastiCache Valkey 9.0
  • 商品搜索（FT.SEARCH）
  • 实时排行榜（FT.AGGREGATE）
  • 向量推荐（KNN）
  • 会话/缓存
    │
    │ 数据同步（CDC / Kinesis）
    ▼
OpenSearch（可选，需要复杂全文搜索时）
  • 中文分词
  • 相关性调优
  • 日志分析
    │
    │ 批量 ETL
    ▼
数据仓库（Redshift / Athena on S3）
  • 历史趋势分析
  • 多维度 BI 报表
  • 跨表 JOIN 分析
```

---

## Redis/Valkey 持久化说明

### 持久化方式

| 方式 | 机制 | 数据安全性 | 性能影响 |
|------|------|-----------|---------|
| **RDB** | 定期快照（如每5分钟） | 可能丢失最后几分钟数据 | 低 |
| **AOF** | 记录每条写命令 | 最多丢失1秒数据 | 中 |
| **RDB+AOF** | 两者结合 | 较强 | 中 |

### ElastiCache 的限制

ElastiCache 支持 RDB 快照，但：
- 节点故障替换时**可能丢失数据**
- 不保证零数据丢失
- 适合"可以重建"的缓存数据

### 需要强持久性？用 MemoryDB

**Amazon MemoryDB for Valkey** = Valkey + 事务日志（Multi-AZ 持久化）

| 特性 | ElastiCache Valkey | MemoryDB for Valkey |
|------|-------------------|---------------------|
| 延迟 | 微秒 | 微秒（单位数毫秒写入） |
| 持久性 | 弱（可能丢数据） | **强（零数据丢失）** |
| 用途 | 缓存、实时搜索 | 主数据库 + 缓存 |
| 成本 | 低 | 较高 |
| 搜索功能 | ✅ Valkey 9.0 | ✅ Valkey 9.0 |

**结论**：
- 数据可以重建（缓存、搜索索引）→ **ElastiCache**
- 数据不能丢失（订单、用户数据）→ **MemoryDB** 或传统数据库
