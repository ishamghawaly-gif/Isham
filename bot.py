import os, json, base64, requests
import pandas as pd
import yfinance as yf

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
REPO = os.environ["GITHUB_REPOSITORY"]
GH_TOKEN = os.environ["GH_TOKEN"]
STATE_PATH = "state/last_signal.json"

def telegram(message):
    r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                      json={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"},
                      timeout=20)
    r.raise_for_status()

def load_state():
    headers={"Authorization": f"Bearer {GH_TOKEN}", "Accept":"application/vnd.github+json"}
    r=requests.get(f"https://api.github.com/repos/{REPO}/contents/{STATE_PATH}",
                   headers=headers, timeout=20)
    if r.status_code == 404: return {}, None
    r.raise_for_status()
    obj=r.json()
    content=base64.b64decode(obj["content"]).decode()
    return json.loads(content), obj["sha"]

def save_state(state, sha):
    headers={"Authorization": f"Bearer {GH_TOKEN}", "Accept":"application/vnd.github+json"}
    payload={"message":"Update last processed XAUUSD signal candle",
             "content":base64.b64encode(json.dumps(state, indent=2).encode()).decode()}
    if sha: payload["sha"]=sha
    r=requests.put(f"https://api.github.com/repos/{REPO}/contents/{STATE_PATH}",
                   headers=headers, json=payload, timeout=20)
    r.raise_for_status()

def indicators(df):
    c=df["Close"]
    df["ema20"]=c.ewm(span=20, adjust=False).mean()
    df["ema50"]=c.ewm(span=50, adjust=False).mean()
    delta=c.diff()
    gain=delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss=(-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rs=gain/loss.replace(0, float("nan"))
    df["rsi"]=100-(100/(1+rs))
    fast=c.ewm(span=12, adjust=False).mean()
    slow=c.ewm(span=26, adjust=False).mean()
    macd=fast-slow
    df["macd_hist"]=macd-macd.ewm(span=9, adjust=False).mean()
    prev=df["Close"].shift(1)
    tr=pd.concat([df["High"]-df["Low"], (df["High"]-prev).abs(),
                  (df["Low"]-prev).abs()], axis=1).max(axis=1)
    df["atr"]=tr.ewm(alpha=1/14, adjust=False).mean()
    return df.dropna()

def main():
    # GC=F is COMEX gold futures, used as a free market proxy, NOT ECMarkets XAUUSD.
    df=yf.download("GC=F", period="5d", interval="15m", progress=False, auto_adjust=False)
    if df.empty: raise RuntimeError("Yahoo Finance returned no gold candles.")
    if isinstance(df.columns, pd.MultiIndex): df.columns=df.columns.get_level_values(0)
    df=indicators(df)
    if len(df)<55: raise RuntimeError("Not enough candles for indicators.")
    row=df.iloc[-1]
    candle=str(df.index[-1])
    price=float(row["Close"]); atr=float(row["atr"])
    if not all(pd.notna(row[x]) for x in ["ema20","ema50","rsi","macd_hist","atr"]) or atr<=0:
        raise RuntimeError("Invalid indicator values.")
    side="WAIT"
    if row["ema20"]>row["ema50"] and 50<row["rsi"]<70 and row["macd_hist"]>0:
        side="BUY"
    elif row["ema20"]<row["ema50"] and 30<row["rsi"]<50 and row["macd_hist"]<0:
        side="SELL"
    state, sha=load_state()
    if state.get("last_candle")==candle:
        print("Already processed this candle; no duplicate alert.")
        return
    state["last_candle"]=candle
    save_state(state, sha)
    if side=="WAIT":
        message=(f"🟡 <b>XAUUSD ANALYSIS — WAIT</b>\n"
                 f"Gold futures proxy (GC=F): {price:.2f}\n"
                 f"15m candle: {candle}\nRSI: {float(row['rsi']):.1f}\n"
                 "Conditions are not aligned. No trade suggested.\n"
                 "Data is a futures proxy, not your ECMarkets quote.")
    else:
        entry=price
        risk=1.5*atr
        sl=entry-risk if side=="BUY" else entry+risk
        sign=1 if side=="BUY" else -1
        tps=[entry+sign*risk*x for x in (1,2,3)]
        message=(f"{'🟢' if side=='BUY' else '🔴'} <b>XAUUSD {side} SETUP</b>\n"
                 f"Gold futures proxy (GC=F): {price:.2f}\n"
                 f"15m candle: {candle}\nEntry: {entry:.2f}\nSL: {sl:.2f}\n"
                 f"TP1: {tps[0]:.2f}\nTP2: {tps[1]:.2f}\nTP3: {tps[2]:.2f}\n"
                 f"RSI: {float(row['rsi']):.1f} | ATR: {atr:.2f}\n"
                 "⚠️ Analysis only. Verify against ECMarkets MT5 before any manual trade.")
    telegram(message)
    print("Telegram alert sent:", side)

if __name__=="__main__": main()
