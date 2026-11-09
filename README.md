# ملفات بيانات السوق السعودي (مجانية) — للوحة تحكم المحتوى

تولّد هذه الحزمة ملفين تلقائياً كل 15 دقيقة أثناء التداول:

- `data/saudi_prices.json` ← لشريط أسعار الأسهم
- `data/saudi_history.json` ← للشارت الفني ولعنصر «تحليل الدعم والمقاومة والسمارت موني» (شموع يومية لسنة، حجمه نحو نصف ميغابايت)

المصدر Yahoo Finance عبر مكتبة yfinance (مجاني وغير رسمي، والأسعار متأخرة نحو 15–20 دقيقة).

## التشغيل خطوة بخطوة (مرة واحدة)

1. أنشئ حساباً على github.com ثم **مستودعاً عاماً (Public)** جديداً، مثلاً `saudi-data`.
2. ارفع محتويات هذا المجلد كلها إلى المستودع، مع مجلد `.github` (استخدم «Add file ← Upload files»؛ إن لم يظهر المجلد المخفي أنشئ الملف يدوياً بالمسار `.github/workflows/update-saudi-data.yml`).
3. من **Settings ← Actions ← General ← Workflow permissions** اختر **Read and write permissions** ثم Save.
4. من تبويب **Actions** اختر «Update Saudi market data» ثم **Run workflow** مرة واحدة. بعد دقيقة يظهر مجلد `data` بالملفين.
5. روابط الملفين تكون بهذا الشكل (غيّر USER وREPO):
   - `https://raw.githubusercontent.com/USER/REPO/main/data/saudi_prices.json`
   - `https://raw.githubusercontent.com/USER/REPO/main/data/saudi_history.json`
6. في لوحة تحكم المحتوى: ضع الرابط الأول في «شريط أسهم السوق السعودي» (الشريط المخصص)، والثاني في «شارت فني».

## تعديل الأسهم
القائمة الافتراضية نحو 40 سهماً، وقد يكون بعضها غير متاح عند ياهو فيُتخطى تلقائياً. لإضافة أي سهم أو تصحيح اسمه افتح `saudi_market_update.py` وعدّل قائمة `SYMBOLS` (الرمز، رمز ياهو بصيغة `1234.SR`، الاسم بالعربي).

## تشغيله على جهازك بدل GitHub
```
pip install -r requirements.txt
python saudi_market_update.py
```
ثم ارفع مجلد `data` على موقعك واستخدم روابطه.

## تنبيهات
- بيانات للاستئناس فقط وليست توصية، وقد تتأخر أو تتوقف إن غيّر المصدر واجهته.
- GitHub قد يتأخر ببضع دقائق في بدء الجدولة، ويحفظ الملفات مؤقتاً نحو 5 دقائق.
