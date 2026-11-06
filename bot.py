import os, json, base64, requests
import pandas as pd
import yfinance as yf

TOKEN=os.environ["TELEGRAM_BOT_TOKEN"]; CHAT_ID=os.environ["TELEGRAM_CHAT_ID"]
REPO=os.environ["GITHUB_REPOSITORY"]; GH_TOKEN=os.environ["GH_TOKEN"]
STATE_PATH="state/last_signal.json"

def telegram(message):
    r=requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                    json={"chat_id":CHAT_ID,"text":message,"parse_mode":"HTML"},timeout=20)
    r.raise_for_status()

def load_state():
    h={"Authorization":f"Bearer {GH_TOKEN}","Accept":"application/vnd.github+json"}
    r=requests.get(f"https://api.github.com/repos/{REPO}/contents/{STATE_PATH}",headers=h,timeout=20)
    if r.status_code==404: return {},None
    r.raise_for_status(); obj=r.json()
    return json.loads(base64.b64decode(obj["content"]).decode()),obj["sha"]

def save_state(state,sha):
    h={"Authorization":f"Bearer {GH_TOKEN}","Accept":"application/vnd.github+json"}
    p={"message":"Record processed gold candle","content":base64.b64encode(json.dumps(state,indent=2).encode()).decode()}
    if sha: p["sha"]=sha
    r=requests.put(f"https://api.github.com/repos/{REPO}/contents/{STATE_PATH}",headers=h,json=p,timeout=20)
    r.raise_for_status()

def indicators(df):
    c=df["Close"]; df["ema20"]=c.ewm(span=20,adjust=False).mean(); df["ema50"]=c.ewm(span=50,adjust=False).mean()
    d=c.diff(); gain=d.clip(lower=0).ewm(alpha=1/14,adjust=False).mean(); loss=(-d.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
    df["rsi"]=100-100/(1+gain/loss.replace(0,float("nan")))
    macd=c.ewm(span=12,adjust=False).mean()-c.ewm(span=26,adjust=False).mean()
    df["macd_hist"]=macd-macd.ewm(span=9,adjust=False).mean()
    prev=c.shift(1); tr=pd.concat([df["High"]-df["Low"],(df["High"]-prev).abs(),(df["Low"]-prev).abs()],axis=1).max(axis=1)
    df["atr"]=tr.ewm(alpha=1/14,adjust=False).mean()
    return df.dropna()

def main():
    # GC=F is COMEX gold futures, not ECMarkets spot XAUUSD.
    df=yf.download("GC=F",period="5d",interval="15m",progress=False,auto_adjust=False)
    if df.empty: raise RuntimeError("No gold candles returned by Yahoo Finance.")
    if isinstance(df.columns,pd.MultiIndex): df.columns=df.columns.get_level_values(0)
    df=indicators(df)
    if len(df)<55: raise RuntimeError("Insufficient candles.")
    row=df.iloc[-1]; candle=str(df.index[-1]); price=float(row["Close"]); atr=float(row["atr"])
    if atr<=0 or not all(pd.notna(row[x]) for x in ["ema20","ema50","rsi","macd_hist","atr"]): raise RuntimeError("Invalid indicators.")
    side="WAIT"
    if row["ema20"]>row["ema50"] and 50<row["rsi"]<70 and row["macd_hist"]>0: side="BUY"
    elif row["ema20"]<row["ema50"] and 30<row["rsi"]<50 and row["macd_hist"]<0: side="SELL"
    state,sha=load_state()
    if state.get("last_candle")==candle:
        print("This candle was already alerted."); return
    if side=="WAIT":
        msg=f"🟡 <b>XAUUSD ANALYSIS — WAIT</b>\nGold futures proxy: {price:.2f}\n15m candle: {candle}\nRSI: {float(row['rsi']):.1f}\nFilters not aligned; no trade suggested.\nNot an ECMarkets quote."
    else:
        risk=1.5*atr; sign=1 if side=="BUY" else -1; sl=price-sign*risk
        tps=[price+sign*risk*n for n in (1,2,3)]
        msg=f"{'🟢' if side=='BUY' else '🔴'} <b>XAUUSD {side} SETUP</b>\nGold futures proxy: {price:.2f}\n15m candle: {candle}\nEntry: {price:.2f}\nSL: {sl:.2f}\nTP1: {tps[0]:.2f}\nTP2: {tps[1]:.2f}\nTP3: {tps[2]:.2f}\nRSI: {float(row['rsi']):.1f} | ATR: {atr:.2f}\n⚠️ Verify price and levels in ECMarkets MT5. Manual analysis only."
    telegram(msg)
    state["last_candle"]=candle
    save_state(state,sha)
    print("Alert sent:",side)

if __name__=="__main__": main()
