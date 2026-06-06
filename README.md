# Valkey Search — ElastiCache Valkey 9.0 实时搜索 & 聚合

基于 **Amazon ElastiCache Valkey 9.0** 内置搜索引擎（`FT.SEARCH` / `FT.AGGREGATE`）的实时搜索与聚合分析演示项目。Valkey 9.0 内置搜索、聚合和向量能力，**无需额外费用**，可在很多实时场景中替代独立的 OpenSearch/Elasticsearch 集群。

> 部署区域：AWS 中国区（cn-northwest-1，宁夏）。全球区同样适用，仅 endpoint 域名后缀不同。

---

## 功能说明

### 1. 实时搜索（FT.SEARCH）

| 能力 | 示例 | 说明 |
|------|------|------|
| 全文搜索 | `wireless headphones` | TEXT 字段分词检索 |
| 前缀搜索 | `air*` | 输入联想 / type-ahead |
| 精确匹配 | `@category:{gaming}` | TAG 字段精确过滤 |
| 数值范围 | `@price:[1000 3000]` | NUMERIC 范围查询 |
| 组合查询 | `@brand:{Apple} @price:[0 10000] @rating:[4.5 +inf]` | 多条件 AND |
| 向量 KNN | `=>[KNN 5 @embedding $vec]` | 语义检索（见架构文档） |

### 2. 实时聚合（FT.AGGREGATE）

- `GROUPBY` 分组 + `REDUCE COUNT/SUM/AVG` 统计
- `APPLY` 计算派生字段（如 `@price * @stock` 库存价值）
- `SORTBY` 排序
- 写后即读一致性：数据写入后立即可被聚合，无刷新延迟

> 📖 完整的 FT.SEARCH / FT.AGGREGATE 命令语法、REDUCE 函数、APPLY 表达式和结果解析见 [`COMMANDS.md`](./COMMANDS.md)。

### 3. 向量搜索与热冷分层

内置 HNSW/FLAT 向量索引，结合 S3 Vectors（冷归档）和 Neptune Analytics（图谱记忆）构建 RAG / AI Agent 记忆系统。详见 [`vector-architecture.md`](./vector-architecture.md)。

---

## 索引架构

当前 Demo 使用单一索引 `products_idx`，绑定前缀 `product:`：

```
FT.CREATE products_idx ON HASH PREFIX 1 product:
  SCHEMA
    name        TEXT
    description TEXT
    category    TAG
    brand       TAG
    price       NUMERIC SORTABLE
    rating      NUMERIC SORTABLE
    stock       NUMERIC
```

> 一个集群可创建多个索引，分别绑定不同 key 前缀（如 `user:`、`order:`）。普通文本/标签/数值索引内存开销小；向量索引（尤其高维 KNN）内存开销大，需按数据量评估实例规格。

**数据规模实测**：20,012 条商品文档，索引 `num_records=140,084`，总内存约 **52 MB**（cache.t4g.micro 可用约 256 MB，余量充足）。

---

## 创建过程

完整的逐步创建过程（Subnet Group → 集群 → 参数组 → 内存预留 → 客户端连接）见 [`DEPLOYMENT.md`](./DEPLOYMENT.md)。

也可使用 CloudFormation 一键部署，见下文「AWS 场景与 CF 模板」。

---

## 使用说明

### 安装依赖

```bash
pip install redis valkey pandas streamlit numpy
```

> 注：`valkey-py` 在某些环境连接 ElastiCache 会报 `Connection closed by server`，可改用 `redis-py`（CLI 脚本用 redis，Dashboard 用 valkey，二者均可）。

### 运行 CLI Demo

```bash
python3 valkey9_demo.py <endpoint>
```

### 生成 2 万条模拟数据（可选）

```bash
python3 generate_data.py <endpoint>
```

脚本特点：8 个类别、80+ 品牌、pipeline 批量写入（约 1.6 万条/秒），从 `product:13` 起不覆盖基础数据。

### 运行 Streamlit Dashboard

```bash
streamlit run valkey9_dashboard.py \
  --server.port 8501 --server.address 0.0.0.0 --server.headless true
```

通过 SSH 隧道访问（ElastiCache 仅 VPC 内可达，需经 EC2 跳板机）：

```bash
ssh -L 8501:localhost:8501 -i <key.pem> ec2-user@<EC2公网IP>
```

然后浏览器访问 `http://localhost:8501`。Dashboard 侧边栏「🔄 初始化数据 & 索引」按钮会重建索引并写入 2 万余条演示数据。

---

## AWS 场景与 CloudFormation 模板

### 适用场景

| 场景 | 说明 |
|------|------|
| 实时商品/内容搜索 | 数据已在 ElastiCache，零额外成本，微秒级延迟 |
| 实时排行榜 / 聚合看板 | FT.AGGREGATE 在内存中完成分组统计 |
| 向量推荐 / 语义检索 | 内置 KNN，配合 Bedrock embedding |
| AI Agent 记忆 / RAG | 热数据层，配合 S3 Vectors + Neptune |
| 缓存 + 搜索一体 | 同一份数据既做缓存又做搜索，省去数据同步 |

### CloudFormation 一键部署

[`cloudformation.yaml`](./cloudformation.yaml) 包含子网组、参数组（内存预留）、安全组规则和 Valkey 9.0 集群。**模板使用参数化输入，不含任何真实 VPC/子网/安全组 ID**，部署时传入你自己的值：

```bash
aws cloudformation deploy \
  --template-file cloudformation.yaml \
  --stack-name valkey-search-stack \
  --parameter-overrides \
    VpcId=vpc-xxxxxxxx \
    SubnetIds="subnet-aaa,subnet-bbb" \
    AppSecurityGroupId=sg-xxxxxxxx \
    NodeType=cache.t4g.micro \
    ReservedMemoryPercent=50 \
  --region cn-northwest-1 \
  --capabilities CAPABILITY_IAM
```

> 内存预留参数：micro=50，small=30，larger=25（默认）。小实例使用搜索功能前必须配置，否则报 `please configure memory reserve`。

---

## 安全组设置

ElastiCache 只能从 VPC 内部访问。安全组核心规则：放行来自应用安全组的 **TCP 6379** 入站。完整说明见 [`SECURITY_GROUP.md`](./SECURITY_GROUP.md)。

> ⚠️ **切勿对 `0.0.0.0/0` 开放 6379**。Valkey/Redis 协议默认无强认证，公网暴露极易被入侵或植入挖矿/勒索数据。

---

## 技术选型对比

Valkey 9.0 vs OpenSearch vs ClickHouse vs Redshift 的能力矩阵与决策树见 [`comparison.md`](./comparison.md) 和 [`vector-architecture.md`](./vector-architecture.md)。

简要结论：
- 数据已在 ElastiCache + 低延迟 → **Valkey 9.0**
- 需要中文分词 / 相关性调优 → **OpenSearch**
- 亿行级实时复杂聚合 → **ClickHouse / OLAP**
- 历史 BI 报表 / 复杂 SQL JOIN → **Redshift / Athena**

---

## 持久化提示

ElastiCache 仅支持 RDB 快照，节点故障替换时**可能丢数据**，适合「可重建」的缓存与搜索索引。若数据不可丢失（订单、用户主数据），请使用 **Amazon MemoryDB for Valkey**（事务日志 + Multi-AZ，零数据丢失，同样内置 Valkey 9.0 搜索能力）。

---

## 文件清单

| 文件 | 说明 |
|------|------|
| `README.md` | 项目总览（本文件） |
| `DEPLOYMENT.md` | 完整创建/部署过程与连接说明 |
| `COMMANDS.md` | FT.SEARCH / FT.AGGREGATE 命令语法详解 |
| `SECURITY_GROUP.md` | 安全组配置说明 |
| `cloudformation.yaml` | CloudFormation 一键部署模板（参数化，无敏感信息） |
| `vector-architecture.md` | 向量搜索架构指南（S3 Vectors / Neptune / Mem0 / RAG） |
| `comparison.md` / `comparison.html` | 技术选型对比 |
| `valkey9_demo.py` | CLI 演示脚本 |
| `valkey9_dashboard.py` | Streamlit Web Dashboard |
| `generate_data.py` | 2 万条模拟数据生成脚本 |
| `valkey-features.html` | Valkey 功能介绍页 |
| `*.drawio` | 架构图源文件 |
| `comparison_chart.png` | 对比图表 |

---

## 安全声明

本仓库所有文件均已脱敏，**不包含**任何真实的 VPC ID、子网 ID、安全组 ID、账户 ARN、Endpoint 或访问密钥。文档中出现的 `vpc-xxxxxxxx`、`sg-xxxxxxxx`、`subnet-xxxxxxxx`、`your-cluster.xxxxxx...` 等均为占位符，使用时请替换为你自己的资源标识。
