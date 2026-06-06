# ElastiCache Valkey 9.0 - 实时搜索 & 聚合 Demo

## 概述

本目录记录了在 AWS 中国区（cn-northwest-1）部署 Amazon ElastiCache Valkey 9.0 并演示实时搜索（FT.SEARCH）和聚合（FT.AGGREGATE）功能的完整过程。

Valkey 9.0 是 ElastiCache 推荐引擎，内置搜索和聚合能力，无需额外费用，可替代独立的 OpenSearch/Elasticsearch 集群用于实时搜索场景。

---

## 环境信息

| 项目 | 值 |
|------|-----|
| 区域 | cn-northwest-1（宁夏） |
| 引擎 | Valkey 9.0 |
| 节点类型 | cache.t4g.micro（ARM Graviton2） |
| VPC | vpc-xxxxxxxx（替换为你的 VPC ID） |
| 安全组 | sg-xxxxxxxx（替换为你的安全组 ID） |
| Endpoint | your-cluster.xxxxxx.ng.0001.cnw1.cache.amazonaws.com.cn:6379 |

---

## 实施步骤

### 1. 创建 ElastiCache Subnet Group

```bash
aws elasticache create-cache-subnet-group \
  --cache-subnet-group-name valkey-demo-sg \
  --cache-subnet-group-description "Valkey demo subnet group" \
  --subnet-ids subnet-xxxxxxxx subnet-yyyyyyyy subnet-zzzzzzzz \
  --region cn-northwest-1
```

### 2. 创建 Valkey 9.0 集群

```bash
aws elasticache create-replication-group \
  --replication-group-id valkey9-demo \
  --replication-group-description "Valkey 9.0 search demo" \
  --engine valkey \
  --engine-version 9.0 \
  --cache-node-type cache.t4g.micro \
  --num-node-groups 1 \
  --replicas-per-node-group 0 \
  --transit-encryption-enabled false \
  --cache-subnet-group-name valkey-demo-sg \
  --security-group-ids sg-xxxxxxxx \
  --region cn-northwest-1
```

### 3. 配置内存预留（micro 实例必须）

micro 实例使用搜索功能前必须设置 `reserved-memory-percent=50`，否则报错：
> please configure memory reserve to 50% on a micro instance

```bash
# 创建自定义参数组
aws elasticache create-cache-parameter-group \
  --cache-parameter-group-family valkey9 \
  --cache-parameter-group-name valkey9-search \
  --description "Valkey 9 with search memory reserve" \
  --region cn-northwest-1

# 设置内存预留
aws elasticache modify-cache-parameter-group \
  --cache-parameter-group-name valkey9-search \
  --parameter-name-values ParameterName=reserved-memory-percent,ParameterValue=50 \
  --region cn-northwest-1

# 应用到集群
aws elasticache modify-replication-group \
  --replication-group-id valkey9-demo \
  --cache-parameter-group-name valkey9-search \
  --apply-immediately \
  --region cn-northwest-1
```

### 4. 安装依赖

```bash
pip install redis pandas streamlit
```

> 注意：valkey-py 客户端在某些环境下连接 ElastiCache 会报 `Connection closed by server`，改用 redis-py 可正常连接。

### 5. 运行 CLI Demo

```bash
python3 valkey9_demo.py <endpoint>
```

### 6. 运行 Streamlit Dashboard

```bash
streamlit run valkey9_dashboard.py \
  --server.port 8501 \
  --server.address 0.0.0.0 \
  --server.headless true
```

通过 SSH 端口转发访问（PuTTY 或 ssh -L）：
```bash
ssh -L 8501:localhost:8501 -i key.pem ec2-user@<EC2公网IP>
```
然后浏览器访问 `http://localhost:8501`

---

## 搜索功能演示结果

### 索引定义

```
FT.CREATE products_idx ON HASH PREFIX 1 product:
  SCHEMA
    name TEXT
    description TEXT
    category TAG
    brand TAG
    price NUMERIC SORTABLE
    rating NUMERIC SORTABLE
    stock NUMERIC
```

### 搜索结果

| 查询类型 | 查询语句 | 结果 |
|---------|---------|------|
| 全文搜索 | `wireless headphones` | Sony WH-1000XM5、Bose QuietComfort Ultra |
| 前缀搜索 | `air*` | AirPods Pro 3 |
| 精确匹配 | `@category:{gaming}` | PS5 Pro、Nintendo Switch 2 |
| 数值范围 | `@price:[1000 3000]` | 4 件商品 |
| 组合查询 | `@brand:{Apple} @price:[0 10000] @rating:[4.5 +inf]` | iPhone 16 Pro Max、AirPods Pro 3 |

---

## 聚合功能演示结果

| 聚合类型 | 结果 |
|---------|------|
| 各类别数量 | electronics 4件、audio 3件、gaming 2件、home 1件 |
| 各类别均价 | electronics ¥8749、home ¥4999、gaming ¥3999、audio ¥2466 |
| 品牌评分排行 | Nintendo ⭐4.80、Apple ⭐4.73、Samsung ⭐4.70 |
| 各品牌库存价值 | Apple ¥3,649,270、Samsung ¥1,799,800、Sony ¥899,670 |

---

## 注意事项

1. **FT.AGGREGATE 不支持 `*` 通配符**，用 `@price:[-inf +inf]` 代替
2. **GROUPBY 字段需要先 LOAD**，否则结果中不包含分组字段值
3. **自定义查询框**中含空格的过滤表达式需用引号括起来（已用 `shlex.split` 处理）
4. **小实例（micro/small）** 使用搜索前必须配置 `reserved-memory-percent`（micro=50，small=30）

---

## 文件说明

| 文件 | 说明 |
|------|------|
| `valkey9_demo.py` | CLI 版演示脚本，包含搜索和聚合全部示例 |
| `valkey9_dashboard.py` | Streamlit Web Dashboard（含 2 万条数据初始化按钮） |
| `generate_data.py` | 批量生成 2 万条不重复模拟商品数据的脚本 |
| `cloudformation.yaml` | CloudFormation 模板，可一键复用部署 |
| `vector-architecture.md` | 向量搜索架构指南（含 S3 Vectors 分层方案） |
| `SECURITY_GROUP.md` | 安全组配置说明 |

---

## 安全组设置

ElastiCache 只能从 VPC 内部访问，需要正确配置安全组。详见 [`SECURITY_GROUP.md`](./SECURITY_GROUP.md)。

核心规则：在 ElastiCache 所用安全组上，放行来自应用（EC2/Lambda）安全组的 **TCP 6379** 入站流量。

```bash
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxxxxxx \
  --protocol tcp --port 6379 \
  --source-group sg-xxxxxxxx \
  --region cn-northwest-1
```

> ⚠️ 切勿对 `0.0.0.0/0` 开放 6379 端口。Valkey/Redis 协议默认无强认证，公网暴露极易被入侵。
