""" Full-featured Telegram Crypto Bot (Webhook) — Technical Indicator Suite File: telegram_crypto_bot_full_indicators.py

Features:

Webhook-based Telegram bot (Flask) ready for Render/Railway

Price fetch from CoinGecko, OHLC from Binance

Wide set of indicators: SMA, EMA, MACD, Bollinger Bands, RSI, Stochastic, Stochastic RSI, ATR, Volume MA, OBV

Aggregated signal report + final recommendation based on indicator consensus

Inline comments explaining the logic and calculations


NOTES:

Set environment variables: TELEGRAM_TOKEN, WEBHOOK_URL, PORT (optional)

This is an advanced educational tool — NOT financial advice. """


import os import logging import requests import pandas as pd import numpy as np from flask import Flask, request from telegram import Update from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

--------- Configuration ---------

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', 'REPLACE_WITH_TOKEN') WEBHOOK_URL = os.environ.get('WEBHOOK_URL', 'https://your-domain.com/webhook') COINGECKO_API = 'https://api.coingecko.com/api/v3' BINANCE_KLINES = 'https://api.binance.com/api/v3/klines'

logging.basicConfig(level=logging.INFO) logger = logging.getLogger(name)

--------- Flask + Telegram Application ---------

flask_app = Flask(name) app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

--------- Market Data Helpers ---------

def fetch_price_coingecko(symbol: str, vs_currency: str = 'usd') -> dict: """Fetch simple price + 24h change from CoinGecko.""" try: resp = requests.get(f"{COINGECKO_API}/simple/price", params={'ids': symbol, 'vs_currencies': vs_currency, 'include_24hr_change': 'true'}, timeout=10) resp.raise_for_status() return resp.json().get(symbol, {}) except Exception: logger.exception('CoinGecko fetch failed') return {}

def symbol_to_binance_pair(symbol: str, vs: str = 'USDT') -> str: """Map human-friendly symbol to common Binance pair. If unknown, return SYMBOL+VS.""" mapping = {'BITCOIN': 'BTC', 'BTC': 'BTC', 'ETHEREUM': 'ETH', 'ETH': 'ETH', 'BNB': 'BNB', 'ADA': 'ADA', 'XRP': 'XRP', 'DOGE': 'DOGE', 'SOL': 'SOL', 'DOT': 'DOT'} s = symbol.upper() base = mapping.get(s, s) return f"{base}{vs}"

def fetch_ohlc_binance(pair: str, interval: str = '1h', limit: int = 500) -> pd.DataFrame: """Fetch OHLC candlesticks from Binance and return a cleaned DataFrame.""" try: r = requests.get(BINANCE_KLINES, params={'symbol': pair, 'interval': interval, 'limit': limit}, timeout=10) r.raise_for_status() data = r.json() df = pd.DataFrame(data, columns=['open_time','open','high','low','close','volume','close_time','quote_av','trades','taker_base','taker_quote','ignore']) df['open_time'] = pd.to_datetime(df['open_time'], unit='ms') # convert numeric columns to floats for calculations df[['open','high','low','close','volume']] = df[['open','high','low','close','volume']].astype(float) return df except Exception: logger.exception('Binance OHLC fetch failed') return pd.DataFrame()

--------- Indicator Calculations (vectorized with pandas) ---------

def sma(series: pd.Series, window: int) -> pd.Series: """Simple Moving Average.""" return series.rolling(window=window, min_periods=1).mean()

def ema(series: pd.Series, window: int) -> pd.Series: """Exponential Moving Average.""" return series.ewm(span=window, adjust=False).mean()

def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame: """MACD line, signal line, and histogram.""" fast_ema = ema(series, fast) slow_ema = ema(series, slow) macd_line = fast_ema - slow_ema signal_line = ema(macd_line, signal) hist = macd_line - signal_line return pd.DataFrame({'macd': macd_line, 'signal': signal_line, 'hist': hist})

def bollinger_bands(series: pd.Series, window: int = 20, num_std: int = 2) -> pd.DataFrame: """Bollinger Bands: middle SMA, upper and lower bands.""" mid = sma(series, window) std = series.rolling(window=window, min_periods=1).std() upper = mid + num_std * std lower = mid - num_std * std return pd.DataFrame({'bb_mid': mid, 'bb_upper': upper, 'bb_lower': lower})

def rsi(series: pd.Series, window: int = 14) -> pd.Series: """Relative Strength Index (classic implementation).""" delta = series.diff() gain = delta.clip(lower=0) loss = -delta.clip(upper=0) # use Wilder's smoothing (EMA) for RSI, more stable avg_gain = gain.ewm(alpha=1/window, adjust=False).mean() avg_loss = loss.ewm(alpha=1/window, adjust=False).mean() rs = avg_gain / (avg_loss.replace(0, np.nan)) rsi_vals = 100 - (100 / (1 + rs)) return rsi_vals.fillna(50)  # neutral where undefined

def stochastic(df: pd.DataFrame, k_window: int = 14, d_window: int = 3) -> pd.DataFrame: """Stochastic oscillator (%K and %D).""" low_k = df['low'].rolling(window=k_window, min_periods=1).min() high_k = df['high'].rolling(window=k_window, min_periods=1).max() k = 100 * (df['close'] - low_k) / (high_k - low_k).replace(0, np.nan) d = k.rolling(window=d_window, min_periods=1).mean() return pd.DataFrame({'stoch_k': k.fillna(50), 'stoch_d': d.fillna(50)})

def stochastic_rsi(series: pd.Series, rsi_window: int = 14, k_window: int = 14, d_window: int = 3) -> pd.DataFrame: """Stochastic RSI — applies stochastic oscillator to the RSI values.""" rsi_series = rsi(series, rsi_window) min_rsi = rsi_series.rolling(window=k_window, min_periods=1).min() max_rsi = rsi_series.rolling(window=k_window, min_periods=1).max() stoch_rsi_k = 100 * (rsi_series - min_rsi) / (max_rsi - min_rsi).replace(0, np.nan) stoch_rsi_d = stoch_rsi_k.rolling(window=d_window, min_periods=1).mean() return pd.DataFrame({'stoch_rsi_k': stoch_rsi_k.fillna(50), 'stoch_rsi_d': stoch_rsi_d.fillna(50)})

def atr(df: pd.DataFrame, window: int = 14) -> pd.Series: """Average True Range (volatility measure).""" high_low = df['high'] - df['low'] high_close = (df['high'] - df['close'].shift()).abs() low_close = (df['low'] - df['close'].shift()).abs() true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1) # Wilder's smoothing return true_range.ewm(alpha=1/window, adjust=False).mean()

def obv(df: pd.DataFrame) -> pd.Series: """On-Balance Volume — measures buying/selling pressure using volume direction.""" direction = np.sign(df['close'].diff()).fillna(0) return (direction * df['volume']).cumsum()

--------- Analysis and Aggregation ---------

def analyze_df(df: pd.DataFrame) -> dict: """Run all indicators and produce a structured report (signals + numeric values).""" result = {} close = df['close']

# Moving averages
result['sma20'] = sma(close, 20).iloc[-1]
result['sma50'] = sma(close, 50).iloc[-1]
result['ema9'] = ema(close, 9).iloc[-1]
result['ema21'] = ema(close, 21).iloc[-1]

# RSI
result['rsi14'] = rsi(close, 14).iloc[-1]

# MACD
macd_df = macd(close)
result['macd'] = macd_df['macd'].iloc[-1]
result['macd_signal'] = macd_df['signal'].iloc[-1]
result['macd_hist'] = macd_df['hist'].iloc[-1]

# Bollinger Bands
bb = bollinger_bands(close)
result['bb_upper'] = bb['bb_upper'].iloc[-1]
result['bb_lower'] = bb['bb_lower'].iloc[-1]
result['bb_mid'] = bb['bb_mid'].iloc[-1]

# Stochastic
stoch = stochastic(df)
result['stoch_k'] = stoch['stoch_k'].iloc[-1]
result['stoch_d'] = stoch['stoch_d'].iloc[-1]

# Stochastic RSI
stoch_r = stochastic_rsi(close)
result['stoch_rsi_k'] = stoch_r['stoch_rsi_k'].iloc[-1]
result['stoch_rsi_d'] = stoch_r['stoch_rsi_d'].iloc[-1]

# ATR & OBV
result['atr14'] = atr(df).iloc[-1]
result['obv'] = obv(df).iloc[-1]

# Volume moving average (recent)
result['vol_ma20'] = sma(df['volume'], 20).iloc[-1]
result['last_volume'] = df['volume'].iloc[-1]

# Signals (simple rule-based checks)
signals = []
last = close.iloc[-1]

# Trend from SMA50
if last > result['sma50']:
    signals.append('price_above_sma50')
else:
    signals.append('price_below_sma50')

# EMA crossover (short-term)
if result['ema9'] > result['ema21']:
    signals.append('ema_bull')
else:
    signals.append('ema_bear')

# MACD direction
if result['macd_hist'] > 0:
    signals.append('macd_bull')
else:
    signals.append('macd_bear')

# RSI thresholds
if result['rsi14'] > 70:
    signals.append('rsi_overbought')
elif result['rsi14'] < 30:
    signals.append('rsi_oversold')
else:
    signals.append('rsi_neutral')

# Bollinger band squeeze or breakout
if last > result['bb_upper']:
    signals.append('bb_breakout_up')
elif last < result['bb_lower']:
    signals.append('bb_breakout_down')
else:
    signals.append('bb_inside')

# Stochastic
if result['stoch_k'] > 80 and result['stoch_d'] > 80:
    signals.append('stoch_overbought')
elif result['stoch_k'] < 20 and result['stoch_d'] < 20:
    signals.append('stoch_oversold')
else:
    signals.append('stoch_neutral')

# Stoch RSI
if result['stoch_rsi_k'] > 80:
    signals.append('stochrsi_overbought')
elif result['stoch_rsi_k'] < 20:
    signals.append('stochrsi_oversold')
else:
    signals.append('stochrsi_neutral')

# Volume confirmation
if result['last_volume'] > result['vol_ma20']:
    signals.append('volume_confirm')
else:
    signals.append('volume_weak')

result['signals'] = signals

# Aggregate a simple recommendation by counting bullish vs bearish signals
bull_keywords = {'price_above_sma50','ema_bull','macd_bull','stoch_oversold','stochrsi_oversold','rsi_oversold','bb_breakout_up','volume_confirm'}
bear_keywords = {'price_below_sma50','ema_bear','macd_bear','stoch_overbought','stochrsi_overbought','rsi_overbought','bb_breakout_down'}

score = 0
for s in signals:
    if s in bull_keywords:
        score += 1
    if s in bear_keywords:
        score -= 1

if score >= 2:
    final_rec = 'Bullish — bias to long (consider small position / confirm with risk management)'
elif score <= -2:
    final_rec = 'Bearish — bias to avoid longs or consider shorts when appropriate'
else:
    final_rec = 'Neutral — wait for clearer signals or manage risk tightly'

result['score'] = score
result['recommendation'] = final_rec

return result

--------- Telegram Commands (handlers) ---------

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text('👋 مرحبًا! أرسل /help لرؤية الأوامر المتاحة.')

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text('/price <coingecko_id> - جلب سعر فوري\n/analyze <symbol> [vs] - تحليل فني متقدم')

async def price_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE): if not context.args: await update.message.reply_text('اكتب رمز العملة. مثال: /price bitcoin') return symbol = context.args[0].lower() data = fetch_price_coingecko(symbol) if data: await update.message.reply_text(f"{symbol.upper()} = {data.get('usd')} USD (24h {data.get('usd_24h_change'):.2f}%)") else: await update.message.reply_text('تعذر جلب السعر.')

async def analyze_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE): if not context.args: await update.message.reply_text('مثال: /analyze bitcoin usdt') return

symbol = context.args[0]
vs = context.args[1].upper() if len(context.args) > 1 else 'USDT'
pair = symbol_to_binance_pair(symbol, vs)

# fetch OHLC data
df = fetch_ohlc_binance(pair, interval='1h', limit=500)
if df.empty or len(df) < 50:
    await update.message.reply_text('لا توجد بيانات كافية من Binance — تأكد من الرمز أو جرّب فترة أخرى.')
    return

# run analysis
report = analyze_df(df)

# build concise message (Arabic) summarizing key values and recommendation
msg = []
msg.append(f'📊 تحليل فني متقدم لـ {pair}')
msg.append(f"آخر سعر: {df['close'].iloc[-1]}")
msg.append(f"SMA20: {report['sma20']:.6f} | SMA50: {report['sma50']:.6f}")
msg.append(f"EMA9: {report['ema9']:.6f} | EMA21: {report['ema21']:.6f}")
msg.append(f"RSI14: {report['rsi14']:.2f} | ATR14: {report['atr14']:.6f}")
msg.append(f"MACD(hist): {report['macd_hist']:.6f} | BB upper/lower: {report['bb_upper']:.6f}/{report['bb_lower']:.6f}")
msg.append(f"Stoch K/D: {report['stoch_k']:.1f}/{report['stoch_d']:.1f} | StochRSI K: {report['stoch_rsi_k']:.1f}")
msg.append(f"حجم اليوم: {report['last_volume']:.6f} | Vol MA20: {report['vol_ma20']:.6f}")
msg.append('\n⚡ إشارات مختصرة: ' + ', '.join(report['signals']))
msg.append(f"\n🔎 التقييم النهائي (score={report['score']}): {report['recommendation']}")
msg.append('\n(ملاحظة: هذه مؤشرات تعليمية وليست نصيحة استثمارية)')

await update.message.reply_text('\n'.join(msg))

register handlers

app.add_handler(CommandHandler('start', start_cmd)) app.add_handler(CommandHandler('help', help_cmd)) app.add_handler(CommandHandler('price', price_cmd)) app.add_handler(CommandHandler('analyze', analyze_cmd))

--------- Webhook endpoint for Telegram updates ---------

@flask_app.route('/webhook', methods=['POST']) def webhook(): # Telegram will POST JSON updates here — convert to Update and enqueue update = Update.de_json(request.get_json(force=True), app.bot) app.update_queue.put(update) return 'OK', 200

--------- Bootstrapping when running directly ---------

if name == 'main': # set webhook with Telegram so Telegram knows where to send updates try: app.bot.set_webhook(url=WEBHOOK_URL) logger.info(f'Webhook set to {WEBHOOK_URL}') except Exception: logger.exception('Setting webhook failed — ensure WEBHOOK_URL and TELEGRAM_TOKEN are correct')

# run Flask app to receive updates
flask_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

