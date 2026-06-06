# Valkey 搜索与聚合命令说明（FT.SEARCH / FT.AGGREGATE）

本文档详细说明 ElastiCache Valkey 9.0 内置搜索引擎的查询命令语法，配合本项目 `products_idx` 索引讲解。

索引结构回顾：

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

---

## 一、FT.SEARCH（搜索）

### 基本结构

```
FT.SEARCH <索引名> <查询表达式>
  [RETURN <n> <字段...>]      # 只返回指定字段
  [SORTBY <字段> <ASC|DESC>]  # 排序
  [LIMIT <offset> <num>]      # 分页
```

### 查询表达式语法

| 类型 | 语法 | 示例 |
|------|------|------|
| 全文搜索 | `<词>` | `wireless headphones` |
| 前缀搜索 | `<词>*` | `air*` |
| TAG 精确匹配 | `@field:{value}` | `@category:{gaming}` |
| NUMERIC 范围 | `@field:[min max]` | `@price:[1000 3000]` |
| 无上下界 | `+inf` / `-inf` | `@rating:[4.5 +inf]` |
| 组合（AND） | 空格分隔 | `@brand:{Apple} @price:[0 10000]` |
| 组合（OR） | `\|` | `@category:{gaming\|audio}` |
| 否定 | `-` | `-@brand:{Apple}` |

### 示例

```bash
# 全文搜索
FT.SEARCH products_idx "wireless headphones" RETURN 3 name brand price

# 前缀搜索（输入联想）
FT.SEARCH products_idx "air*" RETURN 2 name price

# TAG 精确匹配
FT.SEARCH products_idx "@category:{gaming}" RETURN 3 name brand price

# 数值范围 + 排序
FT.SEARCH products_idx "@price:[1000 3000]" RETURN 3 name category price SORTBY price ASC

# 组合查询
FT.SEARCH products_idx "@brand:{Apple} @price:[0 10000] @rating:[4.5 +inf]" RETURN 4 name price rating category

# 中文 TAG 搜索
FT.SEARCH products_idx "@brand:{华为}" RETURN 3 name price category
```

---

## 二、FT.AGGREGATE（聚合分析）

### 基本结构

```
FT.AGGREGATE <索引名> <查询条件>
  LOAD    <n> <字段...>           # 载入要用的字段
  APPLY   <表达式> AS <别名>       # 计算派生字段（可选）
  GROUPBY <n> <分组字段...>        # 按字段分组
  REDUCE  <函数> <参数数> [字段] AS <别名>   # 对每组聚合
  SORTBY  <n> <字段> <ASC|DESC>   # 排序
  LIMIT   <offset> <num>          # 分页
```

### 关键规则（易踩坑）

1. **查询条件不能用 `*` 通配符** — 用 `@price:[-inf +inf]` 表示「全部」
2. **GROUPBY 字段必须先 LOAD** — 否则结果里取不到分组字段值
3. **数字参数语义**：
   - `LOAD 2 @a @b` → 2 表示载入 2 个字段
   - `GROUPBY 1 @category` → 1 表示按 1 个字段分组
   - `REDUCE COUNT 0 AS cnt` → 0 表示该函数不需要字段参数
   - `REDUCE AVG 1 @price AS avg` → 1 表示传 1 个字段参数
   - `SORTBY 2 @total DESC` → 2 表示后面跟 2 个参数（字段+方向）

### REDUCE 常用函数

| 函数 | 作用 | 写法 |
|------|------|------|
| `COUNT` | 计数 | `REDUCE COUNT 0 AS cnt` |
| `SUM` | 求和 | `REDUCE SUM 1 @price AS total` |
| `AVG` | 平均值 | `REDUCE AVG 1 @price AS avg` |
| `MIN` | 最小值 | `REDUCE MIN 1 @price AS min_p` |
| `MAX` | 最大值 | `REDUCE MAX 1 @price AS max_p` |
| `COUNT_DISTINCT` | 去重计数 | `REDUCE COUNT_DISTINCT 1 @brand AS n` |
| `STDDEV` | 标准差 | `REDUCE STDDEV 1 @price AS sd` |
| `QUANTILE` | 分位数 | `REDUCE QUANTILE 2 @price 0.5 AS median` |

### APPLY 表达式

`APPLY` 用于在聚合前/后计算派生字段，支持算术运算和内置函数：

```
APPLY "@price * @stock" AS inventory_value     # 算术
APPLY "floor(@price/5000)" AS price_tier        # floor 取整分桶
APPLY "@price * 0.9" AS discounted              # 打折
```

常用函数：`floor`、`ceil`、`round`、`abs`、`sqrt`、`log` 等。

### 示例

```bash
# 1. 各类别商品数量
FT.AGGREGATE products_idx "@price:[-inf +inf]"
  LOAD 1 @category
  GROUPBY 1 @category
  REDUCE COUNT 0 AS count
  SORTBY 2 @count DESC

# 2. 各类别平均价格
FT.AGGREGATE products_idx "@price:[-inf +inf]"
  LOAD 2 @category @price
  GROUPBY 1 @category
  REDUCE AVG 1 @price AS avg_price
  REDUCE COUNT 0 AS count
  SORTBY 2 @avg_price DESC

# 3. 品牌评分排行榜
FT.AGGREGATE products_idx "@price:[-inf +inf]"
  LOAD 2 @brand @rating
  GROUPBY 1 @brand
  REDUCE AVG 1 @rating AS avg_rating
  REDUCE COUNT 0 AS products
  SORTBY 2 @avg_rating DESC

# 4. 价格区间分布（用 APPLY 分桶）
FT.AGGREGATE products_idx "@category:{electronics}"
  LOAD 1 @price
  APPLY "floor(@price/5000)" AS price_tier
  GROUPBY 1 @price_tier
  REDUCE COUNT 0 AS count
  SORTBY 2 @price_tier ASC

# 5. 各品牌库存总价值（APPLY 算单品价值 → 按品牌 SUM）
FT.AGGREGATE products_idx "@price:[-inf +inf]"
  LOAD 3 @brand @price @stock
  APPLY "@price * @stock" AS inventory_value
  GROUPBY 1 @brand
  REDUCE SUM 1 @inventory_value AS total_value
  SORTBY 2 @total_value DESC
```

---

## 三、结果解析（Python）

Valkey 返回的是扁平数组，第一个元素是总数，后续是 key-value 交替的字段列表。常用解析方式：

```python
# FT.SEARCH 结果解析
results = client.execute_command("FT.SEARCH", "products_idx", query, "RETURN", "3", "name", "brand", "price")
count = results[0]                       # 总匹配数
for i in range(1, len(results), 2):
    # results[i] 是文档 key，results[i+1] 是字段数组
    fields = dict(zip(results[i+1][::2], results[i+1][1::2]))
    print(fields.get("name"), fields.get("price"))

# FT.AGGREGATE 结果解析
results = client.execute_command("FT.AGGREGATE", "products_idx", ...)
for row in results[1:]:                  # 跳过第一个元素（行数）
    d = dict(zip(row[::2], row[1::2]))
    print(d)
```

---

## 四、其他常用命令

| 命令 | 作用 |
|------|------|
| `FT._LIST` | 列出所有索引 |
| `FT.INFO <索引名>` | 查看索引详情（文档数、字段、内存等） |
| `FT.DROPINDEX <索引名>` | 删除索引（不删底层 Hash 数据） |
| `FT.CREATE ...` | 创建索引 |

> 注：`FT.DROPINDEX` 默认只删索引结构；加 `DD` 参数（`FT.DROPINDEX idx DD`）才会同时删除关联的 Hash 文档。
