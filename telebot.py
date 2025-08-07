import telebot
import requests
import numpy as np
import time

TOKEN = "6613881787:AAGKbvKR5lMGDJ0GtsTWIuU9UDuuh0BLYzU"
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "👋 أهلاً بك في بوت تحليل العملات الرقمية.\nأرسل رمز العملة مثل: BTCUSDT")

@bot.message_handler(func=lambda m: True)
def analyze(message):
    symbol = message.text.upper()
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=15m&limit=100"
        data = requests.get(url).json()

        if 'code' in data:
            bot.send_message(message.chat.id, f"❌ الرمز غير صحيح أو غير مدعوم: {symbol}")
            return

        closes = [float(candle[4]) for candle in data]
        highs = [float(candle[2]) for candle in data]
        lows = [float(candle[3]) for candle in data]
        current_price = closes[-1]

        def support_resistance(levels, is_support=True):
            zones = []
            for i in range(2, len(levels)-2):
                if is_support:
                    if levels[i] < levels[i-1] and levels[i] < levels[i+1] and levels[i+1] < levels[i+2] and levels[i-1] < levels[i-2]:
                        zones.append(levels[i])
                else:
                    if levels[i] > levels[i-1] and levels[i] > levels[i+1] and levels[i+1] > levels[i+2] and levels[i-1] > levels[i-2]:
                        zones.append(levels[i])
            return sorted(set(zones), reverse=not is_support)

        support_levels = support_resistance(lows, is_support=True)[:2]
        resistance_levels = support_resistance(highs, is_support=False)[:3]

        sma = np.mean(closes[-20:])
        trend = "📉 الاتجاه: هابط 🔴" if current_price < sma else "📈 الاتجاه: صاعد 🟢"

        rsi_period = 14
        deltas = np.diff(closes)
        ups = deltas[deltas > 0].sum() / rsi_period
        downs = -deltas[deltas < 0].sum() / rsi_period
        rs = ups / downs if downs != 0 else 0
        rsi = 100 - (100 / (1 + rs))

        opportunity = "🚀 فرصة شراء محتملة!" if rsi < 30 else "⛔ لا توجد فرصة واضحة حالياً."

        entry = support_levels[0] if support_levels else current_price
        stop_loss = entry * 0.98
        tp1 = entry * 1.02
        tp2 = entry * 1.04
        tp3 = entry * 1.06

        reply = f"""📊 تحليل عملة 🔎 {symbol}
💵 السعر الحالي: {current_price:.4f} دولار

✅ الدعم:
- {support_levels[0]:.4f}
- {support_levels[1]:.4f}

⛔ المقاومة:
- {resistance_levels[0]:.4f}
- {resistance_levels[1]:.4f}
- {resistance_levels[2]:.4f}

📍 لم يتم تحديد مناطق السيولة في هذا الإصدار.

{trend}

💡 التوصية:
شراء من {entry:.4f} - {entry*1.001:.4f}
ووقف الخسارة: {stop_loss:.4f}

📈 الأهداف:
{tp1:.4f} → {tp2:.4f} → {tp3:.4f}

📢 {opportunity}
"""

        bot.send_message(message.chat.id, reply)

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ حدث خطأ أثناء التحليل: {str(e)}")

while True:
    try:
        bot.polling(none_stop=True)
    except Exception:
        time.sleep(5)