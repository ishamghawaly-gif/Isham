# Isham XAUUSD Telegram Signal Bot

Experimental indicator-based Telegram alerts for manual review only. This bot does not place trades.

## Data limitation
The initial version uses Yahoo Finance `GC=F` COMEX gold-futures 15-minute candles as a free proxy. This is **not** the ECMarkets XAUUSD spot feed; prices, spreads, sessions and candles may differ. Verify every alert against ECMarkets MT5. Data availability and freshness are not guaranteed.

## Configure secrets
In Settings → Secrets and variables → Actions, create:
- `TELEGRAM_BOT_TOKEN`: your BotFather token. Never put it in code or share it in chat.
- `TELEGRAM_CHAT_ID`: your numeric Telegram chat ID.

## Find your chat ID
1. Open Telegram and send `/start` to your bot.
2. Add `TELEGRAM_BOT_TOKEN` first in repository Actions secrets.
3. Go to Actions → **Find Telegram chat ID** → **Run workflow**.
4. Open the completed run and copy the printed numeric `TELEGRAM_CHAT_ID`.
5. Add it as the second repository secret.

## Run
Actions → **XAUUSD Telegram signal checker** → **Run workflow**. It also checks on a 15-minute schedule; GitHub can delay scheduled runs.

Uses EMA20/EMA50, RSI14, MACD histogram and ATR14. BUY/SELL filters are restrictive; otherwise it sends WAIT. Stops/targets are ATR-derived estimates, not guarantees.

## Risk
Not a trained AI, financial advice, or a verified broker feed. False signals, missing candles, delays and API outages are possible. Demo-test only and decide manually. No auto-trading.
