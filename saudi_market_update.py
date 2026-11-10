#!/usr/bin/env python3
"""يجلب تلقائياً كل شركات السوق السعودي الرئيسية (مجاناً عبر yfinance) ويولّد:

  data/saudi_prices.json      -> الأسهم المميزة (FEATURED) لشريط الأسعار
  data/saudi_prices_all.json  -> كل الشركات المكتشفة (أسعار فقط)
  data/saudi_history.json     -> شموع يومية لكل الشركات (للشارت والتحليل)
  data/symbols_cache.json     -> ذاكرة الأرقام والأسماء (تتجدد أسبوعياً)

الاكتشاف التلقائي: يفحص نطاقات أرقام تداول المعروفة ويحتفظ بما له بيانات.
"""
import json
import os
import re
import sys
import time
import datetime as dt

import pandas as pd
import yfinance as yf

OUT_DIR = "data"
CACHE = os.path.join(OUT_DIR, "symbols_cache.json")
INCLUDE_NOMU = False            # اجعلها True لمحاولة إضافة السوق الموازية (نمو)
REDISCOVER_DAYS = 7             # إعادة فحص الأرقام كل كم يوم
HIST_FEATURED = "1y"            # تاريخ الأسهم المميزة
HIST_OTHERS = "6mo"             # تاريخ بقية الأسهم (لتقليل الحجم)
BATCH = 40
NAME_LOOKUPS_PER_RUN = 40       # عدد الأسماء الإنجليزية التي تُجلب في كل تشغيل

# الأسهم المميزة (تظهر في شريط الأسعار) مع أسماء عربية
FEATURED = {
    "2222": "أرامكو", "1120": "الراجحي", "1180": "الأهلي", "1010": "بنك الرياض", "1050": "السعودي الفرنسي",
    "1060": "الأول", "1140": "البلاد", "1150": "الإنماء", "2010": "سابك", "2020": "سابك للمغذيات",
    "2082": "أكوا", "2280": "المراعي", "2290": "ينساب", "2310": "سبكيم", "2350": "كيان", "2380": "بترو رابغ",
    "2223": "لوبريف", "1211": "معادن", "7010": "stc", "7020": "موبايلي", "7030": "زين", "7202": "سلوشنز",
    "4001": "العثيم", "4002": "المواساة", "4003": "إكسترا", "4004": "دله الصحية", "4013": "د. سليمان الحبيب",
    "4030": "البحري", "4190": "جرير", "4240": "الحكير", "4261": "ذيب", "5110": "السعودية للكهرباء",
    "6002": "هرفي", "8010": "التعاونية", "8210": "بوبا", "4300": "دار الأركان", "4321": "المراكز العربية",
    "4322": "رتال", "1303": "الصناعات الكهربائية",
}
INDEX = ("TASI", "^TASI.SR", "تاسي")

# نطاقات أرقام السوق الرئيسية في تداول
RANGES = [(1010, 1330), (2001, 2400), (3001, 3100), (4001, 4350), (5001, 5200),
          (6001, 6100), (7010, 7210), (8001, 8320)]
if INCLUDE_NOMU:
    RANGES.append((9500, 9700))


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def download(tickers, period):
    for _ in range(3):
        try:
            return yf.download(tickers, period=period, interval="1d", auto_adjust=False,
                               group_by="ticker", threads=True, progress=False)
        except Exception as e:
            print("إعادة محاولة:", e)
            time.sleep(5)
    return None


def frame(data, ysym):
    if data is None or getattr(data, "empty", True):
        return None
    try:
        if isinstance(data.columns, pd.MultiIndex):
            if ysym not in data.columns.get_level_values(0):
                return None
            df = data[ysym]
        else:
            df = data
        df = df.dropna(subset=["Close"])
        return None if df.empty else df
    except Exception:
        return None


def load_names_file():
    """يقرأ ملف الأسماء العربية الاختياري names_ar.json (الرمز -> الاسم). يقبل 2222 أو 2222.SR."""
    try:
        with open("names_ar.json", encoding="utf-8") as f:
            raw = json.load(f)
        out = {str(k).replace(".SR", "").strip(): str(v).strip() for k, v in raw.items() if v}
        return {k: v for k, v in out.items() if re.fullmatch(r"\d{4}", k) or k == "TASI"}
    except Exception:
        return {}


def load_cache():
    try:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def discover(cache):
    old = cache.get("updated")
    fresh = False
    if old and cache.get("codes"):
        try:
            age = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(old)).days
            fresh = age < REDISCOVER_DAYS
        except Exception:
            pass
    if fresh:
        return cache
    print("اكتشاف الشركات…")
    listed = sorted(c for c in load_names_file() if re.fullmatch(r"\d{4}", c))
    if len(listed) >= 50:          # ملف الأسماء هو قائمة الشركات المعتمدة
        cands = listed
    else:                          # بدون ملف أسماء: فحص النطاقات المعروفة
        cands = [str(c) for a, b in RANGES for c in range(a, b + 1)]
    found = set(FEATURED)
    for batch in chunks(cands, 60):
        data = download([c + ".SR" for c in batch], "5d")
        for c in batch:
            if frame(data, c + ".SR") is not None:
                found.add(c)
        time.sleep(1)
    cache["codes"] = sorted(found)
    cache["updated"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    cache.setdefault("names", {})
    print("عدد الشركات المكتشفة:", len(found))
    return cache


def fill_names(cache):
    names = cache.setdefault("names", {})
    todo = [c for c in cache["codes"] if c not in FEATURED and c not in names and c not in load_names_file()][:NAME_LOOKUPS_PER_RUN]
    for c in todo:
        try:
            info = yf.Ticker(c + ".SR").info or {}
            n = info.get("shortName") or info.get("longName")
            if n:
                names[c] = n
        except Exception:
            pass
        time.sleep(0.3)


def build(codes, period, names, prices, history):
    for batch in chunks(codes, BATCH):
        ys = [("^TASI.SR" if c == "TASI" else c + ".SR") for c in batch]
        data = download(ys, period)
        for c, y in zip(batch, ys):
            df = frame(data, y)
            if df is None:
                continue
            try:
                last = float(df["Close"].iloc[-1])
                prev = float(df["Close"].iloc[-2]) if len(df) > 1 else last
                chg = round((last - prev) / prev * 100, 2) if prev else 0.0
                name = names.get(c) or c
                prices[c] = {"symbol": c, "name": name, "price": round(last, 2), "change": chg}
                history[c] = {"name": name, "candles": [
                    [i.strftime("%Y-%m-%d"), round(float(r.Open), 2), round(float(r.High), 2),
                     round(float(r.Low), 2), round(float(r.Close), 2), int(r.Volume) if r.Volume == r.Volume else 0]
                    for i, r in df.iterrows()]}
            except Exception as e:
                print("تعذّر", c, e)
        time.sleep(1)


def dump(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    cache = discover(load_cache())
    fill_names(cache)
    names = dict(cache.get("names", {}))
    names.update(FEATURED)
    names.update(load_names_file())   # الأسماء العربية من ملفك لها الأولوية
    names[INDEX[0]] = INDEX[2]
    prices, history = {}, {}
    feat = [INDEX[0]] + list(FEATURED)
    others = [c for c in cache["codes"] if c not in FEATURED]
    build(feat, HIST_FEATURED, names, prices, history)
    build(others, HIST_OTHERS, names, prices, history)
    if len(prices) < 5:
        print("بيانات قليلة جداً؛ لن تُستبدل الملفات القديمة.")
        sys.exit(1)
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=3))).isoformat(timespec="seconds")
    dump(CACHE, cache)
    dump(os.path.join(OUT_DIR, "saudi_prices.json"),
         {"updated": now, "data": [prices[c] for c in feat if c in prices]})
    dump(os.path.join(OUT_DIR, "saudi_prices_all.json"),
         {"updated": now, "data": [prices[c] for c in sorted(prices)]})
    dump(os.path.join(OUT_DIR, "saudi_history.json"), {"updated": now, "symbols": history})
    print("تم تحديث", len(prices), "رمز —", now)


if __name__ == "__main__":
    main()
