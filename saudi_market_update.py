#!/usr/bin/env python3
"""يجلب تلقائياً كل شركات السوق السعودي الرئيسية (عبر yfinance) ويولّد ملفات JSON:
  data/saudi_prices.json
  data/saudi_prices_all.json
  data/saudi_history.json
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
HIST_FEATURED = "1y"
HIST_OTHERS = "6mo"
BATCH = 25  # تقليل حجم الدفعة لتجنب حظر Yahoo أو سقوط البيانات

# الأسهم المميزة لشريط الأسعار السريع
FEATURED = {
    "2222": "أرامكو", "1120": "الراجحي", "1180": "الأهلي", "1010": "بنك الرياض", "1050": "السعودي الفرنسي",
    "1060": "الأول", "1140": "البلاد", "1150": "الإنماء", "2010": "سابك", "2020": "سابك للمغذيات",
    "2082": "أكوا", "2280": "المراعي", "2290": "ينساب", "2310": "سبكيم", "2350": "كيان", "2380": "بترو رابغ",
    "2223": "لوبريف", "1211": "معادن", "7010": "stc", "7020": "موبايلي", "7030": "زين", "7202": "سلوشنز",
    "4001": "العثيم", "4002": "المواساة", "4003": "إكسترا", "4004": "دله الصحية", "4013": "د. سليمان الحبيب",
    "4030": "البحري", "4190": "جرير", "4240": "الحكير", "4261": "ذيب", "5110": "السعودية للكهرباء",
    "6002": "هرفي", "8010": "التعاونية", "8210": "بوبا", "4300": "دار الأركان", "4321": "سينومي سنترز",
    "4322": "رتال", "1303": "الصناعات الكهربائية", "4163": "الدواء", "3030": "أسمنت السعودية"
}
INDEX = ("TASI", "^TASI.SR", "تاسي")


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def download(tickers, period):
    for attempt in range(3):
        try:
            data = yf.download(
                tickers,
                period=period,
                interval="1d",
                auto_adjust=False,
                threads=True,
                progress=False
            )
            if data is not None and not getattr(data, "empty", True):
                return data
        except Exception as e:
            print(f"إعادة محاولة للدفعة ({attempt + 1}):", e)
            time.sleep(3)
    return None


def extract_ticker_df(data, ysym):
    """استخراج DataFrame لسهم معين بشكل متوافق تماماً مع جميع إصدارات yfinance"""
    if data is None or getattr(data, "empty", True):
        return None
    try:
        if isinstance(data.columns, pd.MultiIndex):
            # فحص إذا كان الرمز في المستوى الأول أو الثاني
            if ysym in data.columns.levels[0]:
                df = data[ysym].copy()
            elif len(data.columns.levels) > 1 and ysym in data.columns.levels[1]:
                df = data.xs(ysym, axis=1, level=1).copy()
            else:
                return None
        else:
            df = data.copy()

        if "Close" not in df.columns:
            return None

        df = df.dropna(subset=["Close"])
        return None if df.empty else df
    except Exception:
        return None


def load_names_file():
    """قراءة ملف names_ar.json"""
    try:
        with open("names_ar.json", encoding="utf-8") as f:
            raw = json.load(f)
        out = {str(k).replace(".SR", "").strip(): str(v).strip() for k, v in raw.items() if v}
        return {k: v for k, v in out.items() if re.fullmatch(r"\d{4}", k) or k == "TASI"}
    except Exception as e:
        print("خطأ قراءة names_ar.json:", e)
        return {}


def dump(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def build_market_data(codes, period, names, prices, history):
    for batch in chunks(codes, BATCH):
        ys = [("^TASI.SR" if c == "TASI" else c + ".SR") for c in batch]
        data = download(ys, period)

        for c, y in zip(batch, ys):
            df = extract_ticker_df(data, y)
            
            # محاولة احتياطية فردية إذا سقط السهم في الدفعة
            if df is None:
                try:
                    single_data = yf.download(y, period=period, interval="1d", auto_adjust=False, progress=False)
                    df = extract_ticker_df(single_data, y)
                except Exception:
                    df = None

            if df is None:
                continue

            try:
                last = float(df["Close"].iloc[-1])
                prev = float(df["Close"].iloc[-2]) if len(df) > 1 else last
                chg = round((last - prev) / prev * 100, 2) if prev else 0.0
                name = names.get(c, c)

                prices[c] = {
                    "symbol": c,
                    "name": name,
                    "price": round(last, 2),
                    "change": chg
                }

                history[c] = {
                    "name": name,
                    "candles": [
                        [
                            i.strftime("%Y-%m-%d"),
                            round(float(r.Open), 2),
                            round(float(r.High), 2),
                            round(float(r.Low), 2),
                            round(float(r.Close), 2),
                            int(r.Volume) if pd.notna(r.Volume) else 0
                        ]
                        for i, r in df.iterrows()
                    ]
                }
            except Exception as e:
                print(f"تعذّر معالجة {c}:", e)

        time.sleep(0.5)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    
    # 1. دمج الأسماء من ملف names_ar.json مع القائمة المميزة
    ar_names = load_names_file()
    names = dict(FEATURED)
    names.update(ar_names)
    names[INDEX[0]] = INDEX[2]

    # الاعتماد على الأسهم الموجودة في names_ar.json كمرجع أساسي لقائمة الشركات
    all_codes = sorted(list(set(c for c in names.keys() if c != INDEX[0])))
    
    feat = [INDEX[0]] + [c for c in FEATURED if c in names]
    others = [c for c in all_codes if c not in FEATURED]

    prices, history = {}, {}

    print(f"جاري سحب بيانات {len(feat)} سهم مميز...")
    build_market_data(feat, HIST_FEATURED, names, prices, history)

    print(f"جاري سحب بيانات بقية الشركات ({len(others)} سهم)...")
    build_market_data(others, HIST_OTHERS, names, prices, history)

    if len(prices) < 5:
        print("بيانات قليلة جداً؛ لن يتم استبدال الملفات لتفادي تلف البيانات.")
        sys.exit(1)

    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=3))).isoformat(timespec="seconds")

    dump(os.path.join(OUT_DIR, "saudi_prices.json"),
         {"updated": now, "data": [prices[c] for c in feat if c in prices]})
         
    dump(os.path.join(OUT_DIR, "saudi_prices_all.json"),
         {"updated": now, "data": [prices[c] for c in sorted(prices)]})
         
    dump(os.path.join(OUT_DIR, "saudi_history.json"),
         {"updated": now, "symbols": history})

    print(f"تم بنجاح تحديث {len(prices)} شركة — التوقيت: {now}")


if __name__ == "__main__":
    main()
