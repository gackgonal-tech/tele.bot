# bot.py
import os
import requests
from collections import Counter

# استخدم numpy لو تحب، بس هنا نستخدم عمليات بايثون بسيطة لتقليل التعقيد
import numpy as np
import telebot

# اقرأ التوكن من متغيّر بيئي لتجنب نشره في الكود
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise RuntimeError("لا يوجد TOKEN. عيّن المتغير البيئي TELEGRAM_TOKEN في إعدادات Render أو البيئة المحلية.")

bot = telebot.TeleBot(TOKEN, parse_mode=None)

def get_klines(symbol, interval="1h", limit=100):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def calculate_sma(prices, period=14):
    arr = np.array(prices, dtype=float)
    if len(arr) < period:
        return float(np.mean(arr))
    return float(np.mean(arr[-period:]))

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50.0
    deltas = np.diff(np.array(prices, dtype=float))
    seed = deltas[:period]
    up = seed[seed > 0].sum() / period
    down = -seed[seed < 0].sum() / period
    if down == 0:
        return 100.0 if up > 0 else 50.0
    rs = up / down
    return float(100 - (100 / (1 + rs)))

def analyze(symbol="BTCUSDT"):
    try:
        klines = get_klines(symbol, limit=200)
        closes = [float(k[4]) for k in klines]
        current_price = closes[-1]
    except Exception as e:
        return f"❌ خطأ في جلب البيانات: {e}"

    lows = [float(k[3]) for k in klines]
    highs = [float(k[2]) for k in klines]

    # دعم ومقاومة بسيطة
    support_levels = sorted(set(lows))[:2] if len(lows) >= 2 else [min(lows)]
    resistance_levels = sorted(set(highs), reverse=True)[:3]
    # مناطق سيولة تقريبية: تكرار مستويات الأسعار (اقتراح بسيط)
    rounded = [round(p, 2) for p in closes]
    cnt = Counter(rounded)
    liquidity_zones = sorted(cnt.items(), key=lambda x: x[1], reverse=True)[:5]  # [(price, count), ...]

    sma14 = calculate_sma(closes, period=14)
    rsi14 = calculate_rsi(closes, period=14)

    trend = "📊 الاتجاه:"
    if current_price > sma14:
        trend += f"\n✅ السعر فوق SMA14 ({sma14:.4f}) → اتجاه صاعد."
    else:
        trend += f"\n⛔ السعر تحت SMA14 ({sma14:.4f}) → اتجاه هابط."

    if rsi14 > 70:
        trend += f"\n⚠️ RSI={rsi14:.2f} → منطقة تشبع شراء."
    elif rsi14 < 30:
        trend += f"\n⚠️ RSI={rsi14:.2f} → منطقة تشبع بيع."
    else:
        trend += f"\n✅ RSI={rsi14:.2f} → منطقة حيادية."

    if current_price > sma14 and rsi14 < 70:
        opportunity = "✅ فرصة شراء متاحة حاليًا!"
    elif current_price < sma14 and rsi14 > 30:
        opportunity = "⛔ فرصة بيع متاحة حاليًا!"
    else:
        opportunity = "ℹ️ لا توجد فرصة واضحة الآن."

    # إعداد مستويات دخول+وقف وخيارات الهدف
    entry = round(support_levels[0] * 1.000, 4)
    stop_loss = round(support_levels[0] * 0.995, 4)
    # إذا عدد المقاومة أقل من 3 عيّنها بقيم افتراضية
    while len(resistance_levels) < 3:
        resistance_levels.append(round(current_price * (1 + 0.01 * (len(resistance_levels)+1)), 4))
    tp1, tp2, tp3 = [round(r, 4) for r in resistance_levels[:3]]

    # نص الخرج (صيغة عربية سهلة القراءة)
    reply = f"""📊 تحليل {symbol}
💵 السعر الحالي: {current_price:.4f}

✅ الدعم:
- {support_levels[0]:.4f}
- {support_levels[1] if len(support_levels)>1 else support_levels[0]:.4f}

⛔ المقاومة:
- {resistance_levels[0]:.4f}
- {resistance_levels[1]:.4f}
- {resistance_levels[2]:.4f}

📍 مناطق السيولة (أقوى 5):
"""
    for p, c in liquidity_zones:
        reply += f"- {p:.2f} (تكرار: {c})\n"

    reply += f"\n{trend}\n\n💡 التوصية:\nشراء من {entry:.4f}\nوقف الخسارة: {stop_loss:.4f}\n\n📈 الأهداف:\n{tp1:.4f} → {tp2:.4f} → {tp3:.4f}\n\n📢 {opportunity}\n"
    return reply

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "👋 أهلاً! استخدم /analyze BTCUSDT مثلاً")

@bot.message_handler(commands=['analyze'])
def handle_analyze(message):
    parts = message.text.strip().split()
    if len(parts) != 2:
        bot.reply_to(message, "⚠️ الصيغة: /analyze <SYMBOL> مثل: /analyze BTCUSDT")
        return
    symbol = parts[1].upper()
    bot.reply_to(message, "⏳ جاري التحليل... انتظر قليلًا")
    analysis = analyze(symbol)
    bot.reply_to(message, analysis)

if __name__ == "__main__":
    # استعمل infinity_polling ليبقى البوت شغّال ويعيد المحاولة تلقائيًا
    bot.infinity_polling()