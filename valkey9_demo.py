#!/usr/bin/env python3
"""ElastiCache Valkey 9.0 - Search & Aggregation Demo"""

import redis
import sys

# Connect
HOST = sys.argv[1] if len(sys.argv) > 1 else "localhost"
client = redis.Redis(host=HOST, port=6379, decode_responses=True)

print(f"Connected to {HOST}")
print(f"Engine: {client.info('server').get('redis_version', 'unknown')}\n")

# ========== 1. CREATE INDEX ==========
print("=" * 60)
print("1. 创建搜索索引")
print("=" * 60)

try:
    client.execute_command("FT.DROPINDEX", "products_idx")
except:
    pass

client.execute_command(
    "FT.CREATE", "products_idx",
    "ON", "HASH", "PREFIX", "1", "product:",
    "SCHEMA",
    "name", "TEXT",
    "description", "TEXT",
    "category", "TAG",
    "brand", "TAG",
    "price", "NUMERIC", "SORTABLE",
    "rating", "NUMERIC", "SORTABLE",
    "stock", "NUMERIC"
)
print("✅ 索引 products_idx 创建成功\n")

# ========== 2. LOAD DATA ==========
print("=" * 60)
print("2. 写入示例商品数据")
print("=" * 60)

products = [
    {"name": "iPhone 16 Pro Max", "description": "Apple flagship smartphone with A18 chip", "category": "electronics", "brand": "Apple", "price": "9999", "rating": "4.8", "stock": "150"},
    {"name": "MacBook Pro M4", "description": "Professional laptop with M4 chip 16GB RAM", "category": "electronics", "brand": "Apple", "price": "14999", "rating": "4.9", "stock": "80"},
    {"name": "Galaxy S25 Ultra", "description": "Samsung flagship phone with AI features", "category": "electronics", "brand": "Samsung", "price": "8999", "rating": "4.7", "stock": "200"},
    {"name": "Sony WH-1000XM5", "description": "Wireless noise cancelling headphones", "category": "audio", "brand": "Sony", "price": "2499", "rating": "4.6", "stock": "300"},
    {"name": "AirPods Pro 3", "description": "Apple wireless earbuds with spatial audio", "category": "audio", "brand": "Apple", "price": "1899", "rating": "4.5", "stock": "500"},
    {"name": "Dyson V15 Detect", "description": "Cordless vacuum cleaner with laser detection", "category": "home", "brand": "Dyson", "price": "4999", "rating": "4.4", "stock": "120"},
    {"name": "Kindle Paperwhite", "description": "E-reader with warm light display", "category": "electronics", "brand": "Amazon", "price": "999", "rating": "4.6", "stock": "400"},
    {"name": "Nintendo Switch 2", "description": "Portable gaming console with 4K dock", "category": "gaming", "brand": "Nintendo", "price": "2999", "rating": "4.8", "stock": "50"},
    {"name": "PS5 Pro", "description": "Sony gaming console with ray tracing", "category": "gaming", "brand": "Sony", "price": "4999", "rating": "4.7", "stock": "30"},
    {"name": "Bose QuietComfort Ultra", "description": "Premium wireless headphones immersive audio", "category": "audio", "brand": "Bose", "price": "2999", "rating": "4.5", "stock": "180"},
]

for i, p in enumerate(products):
    client.hset(f"product:{i+1}", mapping=p)

print(f"✅ 写入 {len(products)} 条商品数据\n")

# ========== 3. SEARCH DEMOS ==========
print("=" * 60)
print("3. 搜索演示")
print("=" * 60)

# 3a. Full-text search
print("\n--- 3a. 全文搜索: 'wireless headphones' ---")
results = client.execute_command(
    "FT.SEARCH", "products_idx", "wireless headphones",
    "RETURN", "3", "name", "brand", "price"
)
print(f"   找到 {results[0]} 条结果:")
for i in range(1, len(results), 2):
    fields = dict(zip(results[i+1][::2], results[i+1][1::2]))
    print(f"   • {fields.get('name')} | {fields.get('brand')} | ¥{fields.get('price')}")

# 3b. Prefix search (type-ahead)
print("\n--- 3b. 前缀搜索 (输入联想): 'air*' ---")
results = client.execute_command(
    "FT.SEARCH", "products_idx", "air*",
    "RETURN", "2", "name", "price"
)
print(f"   找到 {results[0]} 条结果:")
for i in range(1, len(results), 2):
    fields = dict(zip(results[i+1][::2], results[i+1][1::2]))
    print(f"   • {fields.get('name')} | ¥{fields.get('price')}")

# 3c. Tag exact match
print("\n--- 3c. 精确匹配: category=gaming ---")
results = client.execute_command(
    "FT.SEARCH", "products_idx", "@category:{gaming}",
    "RETURN", "3", "name", "brand", "price"
)
print(f"   找到 {results[0]} 条结果:")
for i in range(1, len(results), 2):
    fields = dict(zip(results[i+1][::2], results[i+1][1::2]))
    print(f"   • {fields.get('name')} | {fields.get('brand')} | ¥{fields.get('price')}")

# 3d. Numeric range
print("\n--- 3d. 数值范围: price 1000~3000 ---")
results = client.execute_command(
    "FT.SEARCH", "products_idx", "@price:[1000 3000]",
    "RETURN", "3", "name", "category", "price",
    "SORTBY", "price", "ASC"
)
print(f"   找到 {results[0]} 条结果:")
for i in range(1, len(results), 2):
    fields = dict(zip(results[i+1][::2], results[i+1][1::2]))
    print(f"   • {fields.get('name')} | {fields.get('category')} | ¥{fields.get('price')}")

# 3e. Combined filter
print("\n--- 3e. 组合查询: brand=Apple AND price<10000 AND rating>=4.5 ---")
results = client.execute_command(
    "FT.SEARCH", "products_idx",
    "@brand:{Apple} @price:[0 10000] @rating:[4.5 +inf]",
    "RETURN", "4", "name", "price", "rating", "category"
)
print(f"   找到 {results[0]} 条结果:")
for i in range(1, len(results), 2):
    fields = dict(zip(results[i+1][::2], results[i+1][1::2]))
    print(f"   • {fields.get('name')} | ¥{fields.get('price')} | ⭐{fields.get('rating')} | {fields.get('category')}")

# ========== 4. AGGREGATION DEMOS ==========
print("\n" + "=" * 60)
print("4. 聚合演示")
print("=" * 60)

# 4a. Count by category
print("\n--- 4a. 按类别统计商品数量 ---")
results = client.execute_command(
    "FT.AGGREGATE", "products_idx", "@price:[-inf +inf]",
    "LOAD", "1", "@category",
    "GROUPBY", "1", "@category",
    "REDUCE", "COUNT", "0", "AS", "count",
    "SORTBY", "2", "@count", "DESC"
)
print(f"   结果:")
for i in range(1, len(results)):
    row = dict(zip(results[i][::2], results[i][1::2]))
    print(f"   • {row.get('category')}: {row.get('count')} 件")

# 4b. Average price by category
print("\n--- 4b. 各类别平均价格 ---")
results = client.execute_command(
    "FT.AGGREGATE", "products_idx", "@price:[-inf +inf]",
    "LOAD", "2", "@category", "@price",
    "GROUPBY", "1", "@category",
    "REDUCE", "AVG", "1", "@price", "AS", "avg_price",
    "REDUCE", "COUNT", "0", "AS", "count",
    "SORTBY", "2", "@avg_price", "DESC"
)
print(f"   结果:")
for i in range(1, len(results)):
    row = dict(zip(results[i][::2], results[i][1::2]))
    avg = float(row.get('avg_price', 0))
    print(f"   • {row.get('category')}: 平均 ¥{avg:.0f} ({row.get('count')} 件)")

# 4c. Top brands by average rating
print("\n--- 4c. 品牌评分排行榜 ---")
results = client.execute_command(
    "FT.AGGREGATE", "products_idx", "@price:[-inf +inf]",
    "LOAD", "2", "@brand", "@rating",
    "GROUPBY", "1", "@brand",
    "REDUCE", "AVG", "1", "@rating", "AS", "avg_rating",
    "REDUCE", "COUNT", "0", "AS", "products",
    "SORTBY", "2", "@avg_rating", "DESC"
)
print(f"   结果:")
for i in range(1, len(results)):
    row = dict(zip(results[i][::2], results[i][1::2]))
    rating = float(row.get('avg_rating', 0))
    print(f"   • {row.get('brand')}: ⭐{rating:.2f} ({row.get('products')} 款产品)")

# 4d. Price range distribution
print("\n--- 4d. 价格区间分布 (electronics 类) ---")
results = client.execute_command(
    "FT.AGGREGATE", "products_idx", "@category:{electronics}",
    "LOAD", "1", "@price",
    "APPLY", "floor(@price/5000)", "AS", "price_tier",
    "GROUPBY", "1", "@price_tier",
    "REDUCE", "COUNT", "0", "AS", "count",
    "SORTBY", "2", "@price_tier", "ASC"
)
print(f"   结果:")
for i in range(1, len(results)):
    row = dict(zip(results[i][::2], results[i][1::2]))
    tier = int(float(row.get('price_tier', 0)))
    print(f"   • ¥{tier*5000}~¥{(tier+1)*5000}: {row.get('count')} 件")

# 4e. Total inventory value by brand
print("\n--- 4e. 各品牌库存总价值 ---")
results = client.execute_command(
    "FT.AGGREGATE", "products_idx", "@price:[-inf +inf]",
    "LOAD", "3", "@brand", "@price", "@stock",
    "APPLY", "@price * @stock", "AS", "inventory_value",
    "GROUPBY", "1", "@brand",
    "REDUCE", "SUM", "1", "@inventory_value", "AS", "total_value",
    "SORTBY", "2", "@total_value", "DESC"
)
print(f"   结果:")
for i in range(1, len(results)):
    row = dict(zip(results[i][::2], results[i][1::2]))
    val = float(row.get('total_value', 0))
    print(f"   • {row.get('brand')}: ¥{val:,.0f}")

print("\n" + "=" * 60)
print("✅ 演示完成!")
print("=" * 60)
