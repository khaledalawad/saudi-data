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
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlparse
import xml.etree.ElementTree as ET

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "data")
NEWS_FILE = os.path.join(OUT_DIR, "saudi_news.json")
NAMES_FILE = os.path.join(BASE_DIR, "names_ar.json")

FEEDS = [
    {
        "source": "أرقام - أخبار السوق",
        "category": "news",
        "url": "https://www.argaam.com/ar/rss/marketnews.rss",
    },
    {
        "source": "الاقتصادية - أخبار الأسواق والشركات السعودية",
        "category": "market",
        "format": "market_html",
        "url": "https://www.aleqt.com/",
    },
    {
        "source": "أرقام - إفصاحات الشركات",
        "category": "disclosure",
        "format": "html",
        "url": "https://www.argaam.com/ar/company/disclosure/sectionid/25/marketid/3/pageno/1",
    },
    {
        "source": "تداول وتاسي",
        "category": "market",
        "url": (
            "https://news.google.com/rss/search?q=(تاسي+OR+تداول+OR+\"السوق+السعودي\")+when:3d&hl=ar&gl=SA&ceid=SA:ar"
        ),
    },
]


def load_companies():
  try:
    with open(NAMES_FILE, "r", encoding="utf-8-sig") as f:
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
  months = {
      "يناير": 1, "فبراير": 2, "مارس": 3, "أبريل": 4, "ابريل": 4,
      "مايو": 5, "يونيو": 6, "يوليو": 7, "أغسطس": 8, "اغسطس": 8,
      "سبتمبر": 9, "أكتوبر": 10, "اكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12,
  }
  match = re.search(r"(\d{1,2})\s+([ء-ي]+)\s+(\d{4})", date_str)
  if match and match.group(2) in months:
    try:
      parsed = dt.datetime(int(match.group(3)), months[match.group(2)], int(match.group(1)), 12,
                           tzinfo=dt.timezone(dt.timedelta(hours=3)))
      return parsed.timestamp()
    except ValueError:
      pass
  try:
    parsed = dt.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
      parsed = parsed.replace(tzinfo=dt.timezone(dt.timedelta(hours=3)))
    return parsed.timestamp()
  except Exception:
    return 0


POLITICAL_CONFLICT_TERMS = (
  "حرب", "الحرب", "حروب", "عسكري", "عسكرية", "الجيش", "القوات المسلحة",
  "هجوم", "هجمات", "قصف", "صاروخ", "صواريخ", "غارة", "غارات",
  "غزة", "فلسطين", "إسرائيل", "اسرائيل", "إيران", "ايران", "لبنان",
  "اليمن", "سوريا", "السودان", "أوكرانيا", "اوكرانيا", "روسيا",
  "جيوسياسي", "جيوسياسية", "اشتباك", "اشتباكات", "نزاع", "صراع",
  "انتخابات", "الانتخابات", "سياسي", "سياسيون", "البرلمان", "الكونغرس",
  "رئيس الوزراء", "البيت الأبيض", "البيت الابيض", "ترامب", "بايدن",
  "نتنياهو", "بوتين", "زيلينسكي",
)


def is_excluded_article(article):
  source = str(article.get("source") or article.get("s") or "")
  link = str(article.get("link") or article.get("url") or article.get("u") or "")
  if "مباشر" in source or "mubasher.info" in link.lower():
    return True
  if "الاقتصادية" not in source and "aleqt.com" not in link.lower():
    return False
  text = " ".join(str(article.get(key) or "") for key in ("title", "t", "summary", "desc"))
  text = re.sub(r"[\u064b-\u065f\u0670\u0640]", "", text)
  text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
  terms = (term.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا") for term in POLITICAL_CONFLICT_TERMS)
  return any(term in text for term in terms)


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
              "category": feed_info.get("category", "news"),
              "t": title,
              "u": link,
              "s": source_name,
              "d": pub_date,
              "ts": parse_date(pub_date),
          })
  except Exception as e:
    print(f"تعذر قراءة خلاصة {feed_info['source']}:", e)
  return articles


class DisclosurePageParser(HTMLParser):
  """Extract disclosure links from Argaam's rendered disclosures page."""

  def __init__(self, page_url, source_name):
    super().__init__(convert_charrefs=True)
    self.page_url = page_url
    self.source_name = source_name
    self.current_date = ""
    self.anchor = None
    self.articles = []

  def handle_starttag(self, tag, attrs):
    attrs = dict(attrs)
    if tag == "a" and attrs.get("href"):
      link = urljoin(self.page_url, attrs["href"])
      if "/article/articledetail/" in link or "/reports/company-dividend/" in link:
        self.anchor = {"title_parts": [], "link": link, "published": self.current_date}

  def handle_endtag(self, tag):
    if tag == "a" and self.anchor:
      title = " ".join(" ".join(self.anchor["title_parts"]).split())
      date_text = self.anchor["published"]
      try:
        published = dt.datetime.strptime(date_text, "%Y/%m/%d").replace(
            tzinfo=dt.timezone(dt.timedelta(hours=3))
        ).isoformat(timespec="seconds")
      except ValueError:
        published = date_text
      if title:
        self.articles.append({
            "title": title,
            "link": self.anchor["link"],
            "published": published,
            "summary": "",
            "source": self.source_name,
            "category": "disclosure",
            "t": title,
            "u": self.anchor["link"],
            "s": self.source_name,
            "d": published,
            "ts": parse_date(published),
        })
      self.anchor = None

  def handle_data(self, data):
    if self.anchor:
      self.anchor["title_parts"].append(data)
      return
    found = re.search(r"\b(\d{4}/\d{2}/\d{2})\b", data)
    if found:
      self.current_date = found.group(1)


class AleqtMarketParser(HTMLParser):
  """Collect company and stock-market articles from Aleqt's front page."""

  def __init__(self, page_url, source_name):
    super().__init__(convert_charrefs=True)
    self.page_url = page_url
    self.source_name = source_name
    self.current_date = ""
    self.anchor = None
    self.articles = []

  def handle_starttag(self, tag, attrs):
    attrs = dict(attrs)
    if tag == "a" and attrs.get("href"):
      link = urljoin(self.page_url, attrs["href"])
      path = unquote(urlparse(link).path)
      if re.match(r"^/(?:الشركات|الأسواق)/.+-\d+$", path):
        self.anchor = {"title_parts": [], "link": link, "published": self.current_date}

  def handle_endtag(self, tag):
    if tag == "a" and self.anchor:
      title = " ".join(" ".join(self.anchor["title_parts"]).split())
      if title:
        published = self.anchor["published"]
        self.articles.append({
            "title": title,
            "link": self.anchor["link"],
            "published": published,
            "summary": "",
            "source": self.source_name,
            "category": "market",
            "t": title,
            "u": self.anchor["link"],
            "s": self.source_name,
            "d": published,
            "ts": parse_date(published),
        })
      self.anchor = None

  def handle_data(self, data):
    if self.anchor:
      self.anchor["title_parts"].append(data)
      return
    if re.search(r"\d{1,2}\s+[ء-ي]+\s+\d{4}", data):
      self.current_date = data.strip()


def fetch_aleqt_market(feed_info):
  headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
  try:
    req = urllib.request.Request(feed_info["url"], headers=headers)
    with urllib.request.urlopen(req, timeout=15) as res:
      charset = res.headers.get_content_charset() or "utf-8"
      page = res.read().decode(charset, errors="replace")
    parser = AleqtMarketParser(feed_info["url"], feed_info["source"])
    parser.feed(page)
    parser.close()
    return parser.articles
  except Exception as e:
    print("تعذر قراءة أخبار الأسواق والشركات من الاقتصادية:", e)
    return []


def fetch_disclosures(feed_info):
  headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
  try:
    req = urllib.request.Request(feed_info["url"], headers=headers)
    with urllib.request.urlopen(req, timeout=15) as res:
      charset = res.headers.get_content_charset() or "utf-8"
      page = res.read().decode(charset, errors="replace")
    parser = DisclosurePageParser(feed_info["url"], feed_info["source"])
    parser.feed(page)
    parser.close()
    return parser.articles
  except Exception as e:
    print(f"تعذر قراءة صفحة إفصاحات الشركات:", e)
    return []


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
        old_by_symbol = old_data.get("by_symbol", old_data.get("news", {}))
        existing_by_symbol = old_by_symbol if isinstance(old_by_symbol, dict) else {}
        old_general = old_data.get("general", [])
        existing_general = old_general if isinstance(old_general, list) else []
        existing_by_symbol = {
            sym: [article for article in articles if not is_excluded_article(article)]
            for sym, articles in existing_by_symbol.items()
            if isinstance(articles, list)
        }
        existing_general = [article for article in existing_general if not is_excluded_article(article)]
    except Exception as e:
      print("تنبيه: لا يوجد أرشيف سابق أو تعذر قراءته:", e)

  # 2. جلب الأخبار اللحظية الجديدة
  fresh_articles = []
  seen = set()
  for feed in FEEDS:
    if feed.get("format") == "html":
      items = fetch_disclosures(feed)
    elif feed.get("format") == "market_html":
      items = fetch_aleqt_market(feed)
    else:
      items = fetch_feed(feed)
    for item in items:
      if is_excluded_article(item):
        continue
      key = re.sub(r"\s+", " ", item["title"]).strip().casefold()
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
    old_items = existing_by_symbol.get(sym, [])
    if not isinstance(old_items, list):
      old_items = []
    for art in new_by_symbol.get(sym, []) + old_items:
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
    merged_by_symbol[sym] = combined[:60]  # الاحتفاظ بآخر 60 خبراً لكل شركة

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
