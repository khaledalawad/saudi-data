#!/usr/bin/env python3
"""يجلب أحدث أخبار السوق السعودي اللحظية وإفصاحات الشركات
الملف الناتج: data/saudi_news.json
"""

import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
import datetime as dt
from email.utils import parsedate_to_datetime

OUT_DIR = "data"
NEWS_FILE = os.path.join(OUT_DIR, "saudi_news.json")
NAMES_FILE = "names_ar.json"

# خلاصات إخبارية لحظية مخصصة لتداول والأسهم السعودية اليومية
FEEDS = [
    {
        "source": "أرقام - أخبار السوق",
        "url": "https://www.argaam.com/ar/rss/marketnews.rss"
    },
    {
        "source": "أرقام - إفصاحات وإعلانات الشركات",
        "url": "https://www.argaam.com/ar/rss/disclosure.rss"
    },
    {
        "source": "أخبار تداول اللحظية",
        "url": "https://news.google.com/rss/search?q=(تاسي+OR+تداول+OR+\"السوق+السعودي\")+when:1d&hl=ar&gl=SA&ceid=SA:ar"
    }
]

def load_companies():
    try:
        with open(NAMES_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        companies = {}
        for code, name in raw.items():
            clean_code = str(code).replace(".SR", "").strip()
            companies[clean_code] = str(name).strip()
        return companies
    except Exception as e:
        print(f"تعذر قراءة {NAMES_FILE}:", e)
        return {}

def clean_html(text):
    if not text:
        return ""
    cleaner = re.compile(r"<.*?>")
    clean_text = re.sub(cleaner, "", text)
    return " ".join(clean_text.split())

def parse_date(date_str):
    if not date_str:
        return 0
    try:
        return parsedate_to_datetime(date_str).timestamp()
    except Exception:
        pass
    try:
        return dt.datetime.fromisoformat(date_str).timestamp()
    except Exception:
        return 0

def fetch_feed(feed_info):
    articles = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        req = urllib.request.Request(feed_info["url"], headers=headers)
        with urllib.request.urlopen(req, timeout=12) as res:
            root = ET.fromstring(res.read())
            for item in root.findall(".//item"):
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                pub_date = item.findtext("pubDate", "").strip()
                desc = clean_html(item.findtext("description", ""))

                source_el = item.find("source")
                source_name = source_el.text.strip() if source_el is not None and source_el.text else feed_info["source"]

                if title:
                    articles.append({
                        "title": title,
                        "link": link,
                        "published": pub_date,
                        "summary": desc[:220] + ("..." if len(desc) > 220 else ""),
                        "source": source_name,
                        "t": title,
                        "u": link,
                        "s": source_name,
                        "d": pub_date,
                        "ts": parse_date(pub_date)
                    })
    except Exception as e:
        print(f"تعذر قراءة خلاصة {feed_info['source']}:", e)
    return articles

def match_symbols(article, companies):
    text = f"{article['title']} {article['summary']}"
    matched = []
    for code, name in companies.items():
        if code == "TASI":
            continue
        if re.search(r"\b" + re.escape(code) + r"\b", text) or (len(name) >= 3 and name in text):
            matched.append(code)
    return matched

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    companies = load_companies()

    all_raw = []
    seen = set()
    for feed in FEEDS:
        for item in fetch_feed(feed):
            key = item["title"][:50]
            if key not in seen:
                seen.add(key)
                all_raw.append(item)

    # فرز جميع الأخبار تنازلياً من الأحدث إلى الأقدم
    all_raw.sort(key=lambda x: x.get("ts", 0), reverse=True)

    by_symbol = {}
    general_news = []

    for item in all_raw:
        syms = match_symbols(item, companies)
        item["symbols"] = syms
        if syms:
            for s in syms:
                by_symbol.setdefault(s, []).append(item)
        else:
            general_news.append(item)

    # فرز أخبار كل سهم لضمان أحدث الأخبار في الصدارة
    for s in by_symbol:
        by_symbol[s].sort(key=lambda x: x.get("ts", 0), reverse=True)

    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=3))).isoformat(timespec="seconds")
    
    output_data = {
        "updated": now,
        "count": len(all_raw),
        "by_symbol": by_symbol,
        "general": general_news[:30],
        "news": {**by_symbol, "TASI": general_news[:30], "general": general_news[:30]}
    }

    with open(NEWS_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"تم بنجاح تحديث وفرز الأخبار وحفظ الملف في {NEWS_FILE} — {now}")

if __name__ == "__main__":
    main()
