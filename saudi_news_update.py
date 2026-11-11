#!/usr/bin/env python3
"""يجلب أحدث أخبار وإفصاحات السوق السعودي ويحتفظ بآخر الأخبار المسجلة لكل شركة
بحيث إذا لم يصدر خبر جديد اليوم يظل محتفظاً بآخر خبر مسجل لها.
الملف الناتج: data/saudi_news.json
"""

import datetime as dt
from email.utils import parsedate_to_datetime
import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET

OUT_DIR = "data"
NEWS_FILE = os.path.join(OUT_DIR, "saudi_news.json")
NAMES_FILE = "names_ar.json"

FEEDS = [
    {
        "source": "أرقام - أخبار السوق",
        "url": "https://www.argaam.com/ar/rss/marketnews.rss",
    },
    {
        "source": "أرقام - إفصاحات الشركات",
        "url": "https://www.argaam.com/ar/rss/disclosure.rss",
    },
    {
        "source": "تداول وتاسي",
        "url": (
            "https://news.google.com/rss/search?q=(تاسي+OR+تداول+OR+\"السوق+السعودي\")+when:3d&hl=ar&gl=SA&ceid=SA:ar"
        ),
    },
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
  return " ".join(re.sub(cleaner, "", text).split())


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
        source_name = (
            source_el.text.strip()
            if source_el is not None and source_el.text
            else feed_info["source"]
        )

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
              "ts": parse_date(pub_date),
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
    if re.search(r"\b" + re.escape(code) + r"\b", text) or (
        len(name) >= 3 and name in text
    ):
      matched.append(code)
  return matched


def main():
  os.makedirs(OUT_DIR, exist_ok=True)
  companies = load_companies()

  # 1. استرجاع الأخبار السابقة من الملف إن وُجد لضمان عدم ضياع آخر خبر لأي شركة
  existing_by_symbol = {}
  existing_general = []
  if os.path.exists(NEWS_FILE):
    try:
      with open(NEWS_FILE, "r", encoding="utf-8") as f:
        old_data = json.load(f)
        existing_by_symbol = old_data.get(
            "by_symbol", old_data.get("news", {})
        )
        existing_general = old_data.get("general", [])
    except Exception as e:
      print("تنبيه: لا يوجد أرشيف سابق أو تعذر قراءته:", e)

  # 2. جلب الأخبار اللحظية الجديدة
  fresh_articles = []
  seen = set()
  for feed in FEEDS:
    for item in fetch_feed(feed):
      key = item["title"][:50]
      if key not in seen:
        seen.add(key)
        fresh_articles.append(item)

  # 3. تصنيف الأخبار الجديدة وتوزيعها
  new_by_symbol = {}
  new_general = []
  for item in fresh_articles:
    syms = match_symbols(item, companies)
    item["symbols"] = syms
    if syms:
      for s in syms:
        new_by_symbol.setdefault(s, []).append(item)
    else:
      new_general.append(item)

  # 4. دمج الأخبار الجديدة مع السابقة لكل شركة والفرز تنازلياً
  merged_by_symbol = {}
  all_symbols = set(list(existing_by_symbol.keys()) + list(new_by_symbol.keys()))

  for sym in all_symbols:
    seen_titles = set()
    combined = []
    # نبدأ بالأخبار الجديدة أولاً
    for art in new_by_symbol.get(sym, []) + existing_by_symbol.get(sym, []):
      t = art.get("title") or art.get("t")
      if t and t not in seen_titles:
        seen_titles.add(t)
        if "ts" not in art:
          art["ts"] = parse_date(
              art.get("published") or art.get("date") or art.get("d")
          )
        combined.append(art)
    # ترتيب من الأحدث إلى الأقدم
    combined.sort(key=lambda x: x.get("ts", 0), reverse=True)
    merged_by_symbol[sym] = combined[:15]  # الاحتفاظ بآخر 15 خبراً لكل شركة

  # 5. دمج الأخبار العامة
  merged_general = []
  seen_gen = set()
  for art in new_general + existing_general:
    t = art.get("title") or art.get("t")
    if t and t not in seen_gen:
      seen_gen.add(t)
      if "ts" not in art:
        art["ts"] = parse_date(
            art.get("published") or art.get("date") or art.get("d")
        )
      merged_general.append(art)
  merged_general.sort(key=lambda x: x.get("ts", 0), reverse=True)
  merged_general = merged_general[:35]

  now = (
      dt.datetime.now(dt.timezone(dt.timedelta(hours=3)))
      .isoformat(timespec="seconds")
  )

  output_data = {
      "updated": now,
      "by_symbol": merged_by_symbol,
      "general": merged_general,
      "news": {
          **merged_by_symbol,
          "TASI": merged_general,
          "general": merged_general,
      },
  }

  with open(NEWS_FILE, "w", encoding="utf-8") as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2)

  print(
      f"✓ تم بنجاح دمج وحفظ الأخبار لـ {len(merged_by_symbol)} شركة — التاريخ:"
      f" {now}"
  )


if __name__ == "__main__":
  main()
