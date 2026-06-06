#!/usr/bin/env python3
"""Generate 20,000 unique product records into Valkey"""

import redis
import sys
import random
import time

HOST = sys.argv[1] if len(sys.argv) > 1 else "localhost"
client = redis.Redis(host=HOST, port=6379, decode_responses=True)

# 数据模板
brands = {
    "electronics": ["Apple", "Samsung", "Sony", "Huawei", "Xiaomi", "OPPO", "Lenovo", "ASUS", "Dell", "HP"],
    "audio": ["Sony", "Bose", "JBL", "Sennheiser", "Bang&Olufsen", "Harman", "Marshall", "Beats", "AKG", "Shure"],
    "gaming": ["Nintendo", "Sony", "Microsoft", "Razer", "Logitech", "SteelSeries", "Corsair", "HyperX", "ASUS", "MSI"],
    "home": ["Dyson", "Philips", "Panasonic", "Midea", "Haier", "Roborock", "iRobot", "Shark", "Bosch", "Siemens"],
    "wearable": ["Apple", "Samsung", "Garmin", "Fitbit", "Huawei", "Xiaomi", "Amazfit", "OPPO", "OnePlus", "Google"],
    "camera": ["Canon", "Nikon", "Sony", "Fujifilm", "Panasonic", "Olympus", "Leica", "DJI", "GoPro", "Insta360"],
    "storage": ["Samsung", "WD", "Seagate", "Kingston", "SanDisk", "Crucial", "Intel", "Sabrent", "Corsair", "ADATA"],
    "network": ["TP-Link", "ASUS", "Netgear", "Ubiquiti", "Linksys", "Huawei", "Xiaomi", "Aruba", "MikroTik", "Synology"],
}

products_templates = {
    "electronics": [
        ("Smartphone {v}", "flagship smartphone with {f} processor {g} display"),
        ("Laptop {v}", "professional laptop with {f} chip {g} RAM"),
        ("Tablet {v}", "lightweight tablet with {f} chip {g} screen"),
        ("Monitor {v}", "{g} inch {f} display with HDR support"),
        ("Desktop {v}", "high performance desktop with {f} CPU {g} GPU"),
    ],
    "audio": [
        ("Headphones {v}", "wireless noise cancelling headphones with {f} driver {g} audio"),
        ("Earbuds {v}", "true wireless earbuds with {f} ANC {g} battery life"),
        ("Speaker {v}", "portable bluetooth speaker with {f} watts {g} sound"),
        ("Soundbar {v}", "home theater soundbar with {f} channels {g} subwoofer"),
        ("DAC {v}", "high resolution DAC amplifier with {f} bit {g} output"),
    ],
    "gaming": [
        ("Console {v}", "gaming console with {f} GPU {g} storage"),
        ("Controller {v}", "wireless gaming controller with {f} haptics {g} triggers"),
        ("Gaming Mouse {v}", "precision gaming mouse with {f} DPI {g} buttons"),
        ("Gaming Keyboard {v}", "mechanical keyboard with {f} switches {g} RGB"),
        ("VR Headset {v}", "virtual reality headset with {f} resolution {g} tracking"),
    ],
    "home": [
        ("Vacuum {v}", "cordless vacuum cleaner with {f} suction {g} detection"),
        ("Air Purifier {v}", "smart air purifier with {f} filter {g} coverage"),
        ("Robot Mop {v}", "robot vacuum mop combo with {f} navigation {g} mapping"),
        ("Coffee Machine {v}", "automatic coffee machine with {f} brew {g} milk system"),
        ("Fan {v}", "bladeless fan with {f} airflow {g} quiet mode"),
    ],
    "wearable": [
        ("Smartwatch {v}", "smartwatch with {f} health sensors {g} GPS"),
        ("Fitness Band {v}", "fitness tracker with {f} tracking {g} battery"),
        ("Smart Ring {v}", "health monitoring ring with {f} sensors {g} sleep tracking"),
        ("AR Glasses {v}", "augmented reality glasses with {f} display {g} camera"),
        ("Clip Tracker {v}", "activity clip tracker with {f} monitoring {g} alerts"),
    ],
    "camera": [
        ("Mirrorless {v}", "mirrorless camera with {f} sensor {g} stabilization"),
        ("Action Cam {v}", "action camera with {f} video {g} waterproof"),
        ("Drone {v}", "camera drone with {f} flight time {g} obstacle avoidance"),
        ("Instant Camera {v}", "instant print camera with {f} lens {g} film"),
        ("Webcam {v}", "streaming webcam with {f} resolution {g} autofocus"),
    ],
    "storage": [
        ("SSD {v}", "NVMe solid state drive with {f} speed {g} capacity"),
        ("HDD {v}", "hard disk drive with {f} RPM {g} cache"),
        ("USB Drive {v}", "portable USB drive with {f} transfer {g} encryption"),
        ("Memory Card {v}", "high speed memory card with {f} read {g} write"),
        ("NAS {v}", "network attached storage with {f} bays {g} RAID"),
    ],
    "network": [
        ("Router {v}", "WiFi router with {f} speed {g} coverage"),
        ("Mesh System {v}", "mesh WiFi system with {f} nodes {g} coverage"),
        ("Switch {v}", "managed network switch with {f} ports {g} PoE"),
        ("Access Point {v}", "enterprise access point with {f} clients {g} band"),
        ("Extender {v}", "WiFi range extender with {f} speed {g} setup"),
    ],
}

features = ["next-gen", "ultra", "pro-level", "advanced", "AI-powered", "quantum", "turbo", "hyper", "max", "elite"]
extras = ["premium", "enhanced", "4K", "8K", "titanium", "carbon", "ceramic", "sapphire", "liquid-cooled", "solar"]
versions = ["Pro", "Max", "Ultra", "Plus", "Elite", "SE", "GT", "X", "Z", "S", "Air", "Lite", "Neo", "Prime", "Turbo"]

print(f"Connected to {HOST}")
print("Generating 20,000 products...")

pipe = client.pipeline()
start = time.time()
count = 0

for idx in range(13, 20013):  # Start from 13 to not overwrite existing 1-12
    category = random.choice(list(products_templates.keys()))
    brand = random.choice(brands[category])
    template = random.choice(products_templates[category])
    version = f"{random.choice(versions)} {random.randint(1,9)}"
    
    name = f"{brand} {template[0].format(v=version)}"
    desc = template[1].format(f=random.choice(features), g=random.choice(extras))
    price = random.randint(99, 29999)
    rating = round(random.uniform(3.5, 5.0), 1)
    stock = random.randint(5, 2000)

    pipe.hset(f"product:{idx}", mapping={
        "name": name,
        "description": desc,
        "category": category,
        "brand": brand,
        "price": str(price),
        "rating": str(rating),
        "stock": str(stock),
    })
    count += 1

    if count % 1000 == 0:
        pipe.execute()
        pipe = client.pipeline()
        print(f"  已写入 {count} 条...")

pipe.execute()
elapsed = time.time() - start

print(f"\n✅ 完成! 写入 {count} 条商品数据，耗时 {elapsed:.2f} 秒")
print(f"   平均 {count/elapsed:.0f} 条/秒")

# 验证
info = client.info("memory")
print(f"\n内存使用: {info['used_memory_human']}")
print(f"总 keys: {client.dbsize()}")
