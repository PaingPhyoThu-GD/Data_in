"""
Generator for sample Vercel NDJSON and CSV telemetry logs.
"""

import json
import random
import time
from pathlib import Path

sample_dir = Path("sample_telemetry")
sample_dir.mkdir(parents=True, exist_ok=True)

routes = [
    ("/", 200, 25.0),
    ("/api/ocr", 200, 310.0),
    ("/api/ocr", 429, 15.0),
    ("/api/telegram/convert", 200, 180.0),
    ("/api/database/convert", 200, 95.0),
    ("/api/youtube/fetch", 200, 220.0),
    ("/api/surveys/extract", 200, 85.0),
    ("/dashboard", 200, 42.0),
    ("/docs", 200, 18.0),
    ("/static/app.js", 200, 12.0),
    ("/static/style.css", 304, 8.0),
    ("/api/v1/invalid", 404, 14.0),
    ("/api/heavy-computation", 500, 450.0),
]

referrers = [
    "https://google.com/search?q=gemini+ocr",
    "https://github.com/myanmar-ocr",
    "https://twitter.com/ai_tools/status/12345",
    "https://linkedin.com/feed",
    "direct",
    "direct",
    "direct",
]

uas = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
]

countries = ["US", "MM", "SG", "TH", "JP", "DE", "GB", "IN"]

base_time = int(time.time() * 1000) - (86400 * 1000)

random.seed(42)  # Deterministic seed for reproducible tests

ndjson_lines = []
csv_rows = ["timestamp,path,status,latency_ms,ip,referrer,country,user_agent"]

for i in range(150):
    route_info = random.choice(routes)
    path = route_info[0]
    status = route_info[1]
    base_lat = route_info[2]
    latency = round(max(5.0, base_lat + random.uniform(-15, 60)), 1)

    ts = base_time + (i * 550000) + random.randint(1000, 45000)
    ref = random.choice(referrers)
    ua = random.choice(uas)
    country = random.choice(countries)
    ip = f"198.51.{random.randint(10, 99)}.{random.randint(2, 250)}"

    log_obj = {
        "id": f"dpl_log_{i:04d}",
        "deploymentId": "dpl_gemini_ocr_prod_99x",
        "source": "edge",
        "host": "ocr.vercel.app",
        "timestamp": ts,
        "level": "info" if status < 400 else "error",
        "proxy": {
            "statusCode": status,
            "clientIp": ip,
            "userAgent": [ua],
            "referer": ref,
            "region": "sfo1",
            "path": path,
            "method": "POST" if "/api/" in path else "GET",
            "executionTime": latency,
        },
    }
    ndjson_lines.append(json.dumps(log_obj))
    csv_rows.append(f'{ts},{path},{status},{latency},{ip},"{ref}",{country},"{ua}"')

with open(sample_dir / "vercel_logs_sample.ndjson", "w", encoding="utf-8") as f:
    f.write("\n".join(ndjson_lines) + "\n")

with open(sample_dir / "vercel_traffic_sample.csv", "w", encoding="utf-8") as f:
    f.write("\n".join(csv_rows) + "\n")

print("Generated sample_telemetry NDJSON and CSV successfully!")
