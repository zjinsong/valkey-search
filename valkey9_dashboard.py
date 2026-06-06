#!/usr/bin/env python3
"""ElastiCache Valkey 9.0 - Search & Aggregation Dashboard (Streamlit)"""

import streamlit as st
import valkey
import pandas as pd

st.set_page_config(page_title="Valkey 9.0 Search & Aggregation", layout="wide")
st.title("🔍 ElastiCache Valkey 9.0 - 实时搜索 & 聚合 Demo")

# --- Connection ---
ENDPOINT = st.sidebar.text_input("ElastiCache Endpoint", "your-cluster.xxxxxx.ng.0001.cnw1.cache.amazonaws.com.cn")
PORT = st.sidebar.number_input("Port", value=6379)

@st.cache_resource
def get_client(host, port):
    return valkey.Valkey(host=host, port=port, decode_responses=True)

try:
    client = get_client(ENDPOINT, PORT)
    client.ping()
    st.sidebar.success("✅ 已连接")
except Exception as e:
    st.sidebar.error(f"❌ 连接失败: {e}")
    st.stop()

# --- Init Data ---
if st.sidebar.button("🔄 初始化数据 & 索引"):
    try:
        client.execute_command("FT.DROPINDEX", "products_idx")
    except:
        pass

    client.execute_command(
        "FT.CREATE", "products_idx", "ON", "HASH", "PREFIX", "1", "product:",
        "SCHEMA", "name", "TEXT", "description", "TEXT",
        "category", "TAG", "brand", "TAG",
        "price", "NUMERIC", "SORTABLE", "rating", "NUMERIC", "SORTABLE", "stock", "NUMERIC"
    )

    products = [
        {"name": "iPhone 16 Pro Max", "description": "Apple flagship smartphone with A18 chip", "category": "electronics", "brand": "Apple", "price": "9999", "rating": "4.8", "stock": "150"},
        {"name": "MacBook Pro M4", "description": "Professional laptop with M4 chip", "category": "electronics", "brand": "Apple", "price": "14999", "rating": "4.9", "stock": "80"},
        {"name": "Galaxy S25 Ultra", "description": "Samsung flagship phone with AI features", "category": "electronics", "brand": "Samsung", "price": "8999", "rating": "4.7", "stock": "200"},
        {"name": "Sony WH-1000XM5", "description": "Wireless noise cancelling headphones", "category": "audio", "brand": "Sony", "price": "2499", "rating": "4.6", "stock": "300"},
        {"name": "AirPods Pro 3", "description": "Apple wireless earbuds with spatial audio", "category": "audio", "brand": "Apple", "price": "1899", "rating": "4.5", "stock": "500"},
        {"name": "Dyson V15 Detect", "description": "Cordless vacuum cleaner with laser", "category": "home", "brand": "Dyson", "price": "4999", "rating": "4.4", "stock": "120"},
        {"name": "Kindle Paperwhite", "description": "E-reader with warm light display", "category": "electronics", "brand": "Amazon", "price": "999", "rating": "4.6", "stock": "400"},
        {"name": "Nintendo Switch 2", "description": "Portable gaming console with 4K dock", "category": "gaming", "brand": "Nintendo", "price": "2999", "rating": "4.8", "stock": "50"},
        {"name": "PS5 Pro", "description": "Sony gaming console with ray tracing", "category": "gaming", "brand": "Sony", "price": "4999", "rating": "4.7", "stock": "30"},
        {"name": "Bose QuietComfort Ultra", "description": "Premium wireless headphones immersive audio", "category": "audio", "brand": "Bose", "price": "2999", "rating": "4.5", "stock": "180"},
        {"name": "iPad Air M3", "description": "Apple tablet with M3 chip lightweight", "category": "electronics", "brand": "Apple", "price": "5999", "rating": "4.7", "stock": "250"},
        {"name": "Samsung OLED TV 65", "description": "Samsung 65 inch OLED 4K smart TV", "category": "electronics", "brand": "Samsung", "price": "12999", "rating": "4.8", "stock": "60"},
        {"name": "苹果手机 iPhone", "description": "苹果公司旗舰智能手机 中文测试", "category": "electronics", "brand": "苹果", "price": "9999", "rating": "4.8", "stock": "100"},
    ]
    for i, p in enumerate(products):
        client.hset(f"product:{i+1}", mapping=p)

    # ── 批量生成 20000 条模拟数据 (product:14 ~ product:20013) ──
    import random
    base = len(products)  # 13

    brands_map = {
        "electronics": ["Apple", "Samsung", "Sony", "Huawei", "Xiaomi", "OPPO", "Lenovo", "ASUS", "Dell", "HP"],
        "audio": ["Sony", "Bose", "JBL", "Sennheiser", "Bang&Olufsen", "Marshall", "Beats", "AKG", "Shure", "Harman"],
        "gaming": ["Nintendo", "Sony", "Microsoft", "Razer", "Logitech", "SteelSeries", "Corsair", "HyperX", "ASUS", "MSI"],
        "home": ["Dyson", "Philips", "Panasonic", "Midea", "Haier", "Roborock", "iRobot", "Shark", "Bosch", "Siemens"],
        "wearable": ["Apple", "Samsung", "Garmin", "Fitbit", "Huawei", "Xiaomi", "Amazfit", "OPPO", "OnePlus", "Google"],
        "camera": ["Canon", "Nikon", "Sony", "Fujifilm", "Panasonic", "Olympus", "Leica", "DJI", "GoPro", "Insta360"],
        "storage": ["Samsung", "WD", "Seagate", "Kingston", "SanDisk", "Crucial", "Intel", "Sabrent", "Corsair", "ADATA"],
        "network": ["TP-Link", "ASUS", "Netgear", "Ubiquiti", "Linksys", "Huawei", "Xiaomi", "Aruba", "MikroTik", "Synology"],
    }
    names_map = {
        "electronics": ["Smartphone", "Laptop", "Tablet", "Monitor", "Desktop"],
        "audio": ["Headphones", "Earbuds", "Speaker", "Soundbar", "DAC"],
        "gaming": ["Console", "Controller", "Gaming Mouse", "Gaming Keyboard", "VR Headset"],
        "home": ["Vacuum", "Air Purifier", "Robot Mop", "Coffee Machine", "Fan"],
        "wearable": ["Smartwatch", "Fitness Band", "Smart Ring", "AR Glasses", "Clip Tracker"],
        "camera": ["Mirrorless", "Action Cam", "Drone", "Instant Camera", "Webcam"],
        "storage": ["SSD", "HDD", "USB Drive", "Memory Card", "NAS"],
        "network": ["Router", "Mesh System", "Switch", "Access Point", "Extender"],
    }
    versions = ["Pro", "Max", "Ultra", "Plus", "Elite", "SE", "GT", "X", "Z", "S", "Air", "Lite", "Neo", "Prime"]

    progress = st.sidebar.progress(0, text="正在生成 20000 条模拟数据...")
    pipe = client.pipeline()
    total = 20000
    for n in range(1, total + 1):
        idx = base + n  # 14 起
        cat = random.choice(list(brands_map.keys()))
        brand = random.choice(brands_map[cat])
        name = f"{brand} {random.choice(names_map[cat])} {random.choice(versions)} {random.randint(1,9)}"
        pipe.hset(f"product:{idx}", mapping={
            "name": name,
            "description": f"{name} with advanced features and premium quality",
            "category": cat,
            "brand": brand,
            "price": str(random.randint(99, 29999)),
            "rating": str(round(random.uniform(3.5, 5.0), 1)),
            "stock": str(random.randint(5, 2000)),
        })
        if n % 1000 == 0:
            pipe.execute()
            pipe = client.pipeline()
            progress.progress(n / total, text=f"已生成 {n}/{total} 条...")
    pipe.execute()
    progress.empty()

    st.sidebar.success(f"✅ 已写入 {base + total} 条数据（{base} 条基础 + {total} 条模拟）")
    st.rerun()

# ========== TAB LAYOUT ==========
tab1, tab2 = st.tabs(["🔍 搜索", "📊 聚合分析"])

# ========== TAB 1: SEARCH ==========
with tab1:
    st.subheader("实时搜索")
    col1, col2, col3 = st.columns(3)
    with col1:
        query = st.text_input("关键词搜索", placeholder="如: wireless, phone, apple...")
    with col2:
        category = st.selectbox("类别过滤", ["全部", "electronics", "audio", "gaming", "home", "wearable", "camera", "storage", "network"])
    with col3:
        price_range = st.slider("价格范围 (¥)", 0, 30000, (0, 30000), step=500)

    # Build query
    parts = []
    if query:
        parts.append(query)
    if category != "全部":
        parts.append(f"@category:{{{category}}}")
    parts.append(f"@price:[{price_range[0]} {price_range[1]}]")
    q = " ".join(parts) if parts else "*"

    try:
        results = client.execute_command(
            "FT.SEARCH", "products_idx", q,
            "RETURN", "6", "name", "brand", "category", "price", "rating", "stock",
            "SORTBY", "price", "ASC", "LIMIT", "0", "20"
        )
        count = results[0]
        rows = []
        for i in range(1, len(results), 2):
            fields = dict(zip(results[i+1][::2], results[i+1][1::2]))
            rows.append(fields)

        st.metric("搜索结果数", count)
        if rows:
            df = pd.DataFrame(rows)
            for col in ["price", "rating", "stock"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("无匹配结果")
    except Exception as e:
        st.error(f"搜索错误: {e}")

# ========== TAB 2: AGGREGATION ==========
with tab2:
    st.subheader("实时聚合分析")

    col1, col2 = st.columns(2)

    # 4a. Count by category
    with col1:
        st.markdown("#### 📦 各类别商品数量")
        try:
            agg = client.execute_command(
                "FT.AGGREGATE", "products_idx", "@price:[-inf +inf]",
                "LOAD", "1", "@category",
                "GROUPBY", "1", "@category",
                "REDUCE", "COUNT", "0", "AS", "count",
                "SORTBY", "2", "@count", "DESC"
            )
            df = pd.DataFrame([dict(zip(r[::2], r[1::2])) for r in agg[1:]])
            df["count"] = df["count"].astype(int)
            st.bar_chart(df.set_index("category")["count"])
        except Exception as e:
            st.error(str(e))

    # 4b. Avg price by category
    with col2:
        st.markdown("#### 💰 各类别平均价格")
        try:
            agg = client.execute_command(
                "FT.AGGREGATE", "products_idx", "@price:[-inf +inf]",
                "LOAD", "2", "@category", "@price",
                "GROUPBY", "1", "@category",
                "REDUCE", "AVG", "1", "@price", "AS", "avg_price",
                "SORTBY", "2", "@avg_price", "DESC"
            )
            df = pd.DataFrame([dict(zip(r[::2], r[1::2])) for r in agg[1:]])
            df["avg_price"] = df["avg_price"].astype(float).round(0)
            st.bar_chart(df.set_index("category")["avg_price"])
        except Exception as e:
            st.error(str(e))

    col3, col4 = st.columns(2)

    # 4c. Brand rating ranking
    with col3:
        st.markdown("#### ⭐ 品牌评分排行")
        try:
            agg = client.execute_command(
                "FT.AGGREGATE", "products_idx", "@price:[-inf +inf]",
                "LOAD", "2", "@brand", "@rating",
                "GROUPBY", "1", "@brand",
                "REDUCE", "AVG", "1", "@rating", "AS", "avg_rating",
                "REDUCE", "COUNT", "0", "AS", "products",
                "SORTBY", "2", "@avg_rating", "DESC"
            )
            df = pd.DataFrame([dict(zip(r[::2], r[1::2])) for r in agg[1:]])
            df["avg_rating"] = df["avg_rating"].astype(float).round(2)
            df["products"] = df["products"].astype(int)
            st.dataframe(df, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(str(e))

    # 4d. Inventory value by brand
    with col4:
        st.markdown("#### 🏭 各品牌库存总价值")
        try:
            agg = client.execute_command(
                "FT.AGGREGATE", "products_idx", "@price:[-inf +inf]",
                "LOAD", "3", "@brand", "@price", "@stock",
                "APPLY", "@price * @stock", "AS", "value",
                "GROUPBY", "1", "@brand",
                "REDUCE", "SUM", "1", "@value", "AS", "total_value",
                "SORTBY", "2", "@total_value", "DESC"
            )
            df = pd.DataFrame([dict(zip(r[::2], r[1::2])) for r in agg[1:]])
            df["total_value"] = df["total_value"].astype(float)
            st.bar_chart(df.set_index("brand")["total_value"])
        except Exception as e:
            st.error(str(e))

    # 4e. Custom aggregation
    st.markdown("---")
    st.markdown("#### 🧪 自定义聚合查询")
    custom_q = st.text_input("FT.AGGREGATE 查询 (不含命令前缀)", 
                             value='products_idx "@price:[-inf +inf]" LOAD 2 @brand @stock GROUPBY 1 @brand REDUCE SUM 1 @stock AS total_stock SORTBY 2 @total_stock DESC')
    if st.button("执行聚合"):
        try:
            import shlex
            parts = shlex.split(custom_q)
            result = client.execute_command("FT.AGGREGATE", *parts)
            rows = [dict(zip(r[::2], r[1::2])) for r in result[1:]]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"执行错误: {e}")

st.sidebar.markdown("---")
st.sidebar.markdown("**技术栈:** ElastiCache Valkey 9.0 + FT.SEARCH + FT.AGGREGATE")
