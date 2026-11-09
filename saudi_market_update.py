#!/usr/bin/env python3
"""يولّد ملفات أسعار وتاريخ السوق السعودي (مجاناً عبر yfinance) لتستخدمها لوحة تحكم المحتوى.

المخرجات:
  data/saudi_prices.json   -> شريط الأسعار
  data/saudi_history.json  -> الشارت الفني (شموع يومية لمدة سنة)
عدّل قائمة SYMBOLS أدناه لإضافة أو حذف أي سهم (الرمز، رمز ياهو، الاسم).
"""
import json
import os
import sys
import datetime as dt

import yfinance as yf

SYMBOLS = [
    ("TASI", "^TASI.SR", "تاسي"),
    ("2222", "2222.SR", "أرامكو"),
    ("1120", "1120.SR", "الراجحي"),
    ("1180", "1180.SR", "الأهلي"),
    ("1010", "1010.SR", "بنك الرياض"),
    ("1050", "1050.SR", "السعودي الفرنسي"),
    ("1060", "1060.SR", "الأول"),
    ("1140", "1140.SR", "البلاد"),
    ("1150", "1150.SR", "الإنماء"),
    ("2010", "2010.SR", "سابك"),
    ("2020", "2020.SR", "سابك للمغذيات"),
    ("2082", "2082.SR", "أكوا"),
    ("2280", "2280.SR", "المراعي"),
    ("2290", "2290.SR", "ينساب"),
    ("2310", "2310.SR", "سبكيم"),
    ("2350", "2350.SR", "كيان"),
    ("2380", "2380.SR", "بترو رابغ"),
    ("2223", "2223.SR", "لوبريف"),
    ("1211", "1211.SR", "معادن"),
    ("7010", "7010.SR", "stc"),
    ("7020", "7020.SR", "موبايلي"),
    ("7030", "7030.SR", "زين"),
    ("7202", "7202.SR", "سلوشنز"),
    ("4001", "4001.SR", "العثيم"),
    ("4002", "4002.SR", "المواساة"),
    ("4003", "4003.SR", "إكسترا"),
    ("4004", "4004.SR", "دله الصحية"),
    ("4013", "4013.SR", "د. سليمان الحبيب"),
    ("4030", "4030.SR", "البحري"),
    ("4190", "4190.SR", "جرير"),
    ("4240", "4240.SR", "الحكير"),
    ("4261", "4261.SR", "ذيب"),
    ("5110", "5110.SR", "السعودية للكهرباء"),
    ("6002", "6002.SR", "هرفي"),
    ("8010", "8010.SR", "التعاونية"),
    ("8210", "8210.SR", "بوبا"),
    ("4300", "4300.SR", "دار الأركان"),
    ("4321", "4321.SR", "المراكز العربية"),
    ("4322", "4322.SR", "رتال"),
    ("1303", "1303.SR", "الصناعات الكهربائية"),
]
HISTORY_PERIOD = "1y"
OUT_DIR = "data"


def fetch(ysym):
    df = yf.Ticker(ysym).history(period=HISTORY_PERIOD, interval="1d", auto_adjust=False)
    return df.dropna(subset=["Close"])


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=3))).isoformat(timespec="seconds")
    prices, history = [], {}
    for code, ysym, name in SYMBOLS:
        try:
            df = fetch(ysym)
            if df.empty:
                print("لا توجد بيانات:", ysym)
                continue
            last = float(df["Close"].iloc[-1])
            prev = float(df["Close"].iloc[-2]) if len(df) > 1 else last
            chg = round((last - prev) / prev * 100, 2) if prev else 0.0
            prices.append({"symbol": code, "name": name, "price": round(last, 2), "change": chg})
            history[code] = {
                "name": name,
                "candles": [
                    [i.strftime("%Y-%m-%d"), round(float(r.Open), 2), round(float(r.High), 2),
                     round(float(r.Low), 2), round(float(r.Close), 2), int(r.Volume or 0)]
                    for i, r in df.iterrows()
                ],
            }
        except Exception as e:  # سهم واحد فاشل لا يوقف الباقي
            print("تعذّر جلب", ysym, e)
    if not prices:
        print("لم يُجلب أي سهم؛ لن تُستبدل الملفات القديمة.")
        sys.exit(1)
    with open(os.path.join(OUT_DIR, "saudi_prices.json"), "w", encoding="utf-8") as f:
        json.dump({"updated": now, "data": prices}, f, ensure_ascii=False)
    with open(os.path.join(OUT_DIR, "saudi_history.json"), "w", encoding="utf-8") as f:
        json.dump({"updated": now, "symbols": history}, f, ensure_ascii=False)
    print("تم تحديث", len(prices), "سهم —", now)


if __name__ == "__main__":
    main()
