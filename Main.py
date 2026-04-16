# -*- coding: utf-8 -*-
import yfinance as yf
import requests
import os
import math
import json
from datetime import datetime, timedelta, timezone

# ==========================================
# 1. 取得設定
# ==========================================
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
REPORT_BASE_URL = "https://gn1179076-wq.github.io/Stock_Bot_2/portfolio.html"
PORTFOLIO_FILE = "portfolio.json"

def load_portfolio():
    try:
        with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ 找不到持股檔案：{PORTFOLIO_FILE}")
        return []
    except json.JSONDecodeError as e:
        print(f"❌ JSON 格式錯誤：{e}")
        return []

# ==========================================
# 2. Telegram 推播函式
# ==========================================
def push_tg_message(text):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("❌ 錯誤：請在 GitHub Secrets 中設定 TG_BOT_TOKEN 與 TG_CHAT_ID")
        return

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }

    try:
        res = requests.post(url, json=payload, timeout=30)
        if res.status_code == 200:
            print("✅ Telegram 股票日報發送成功！")
        else:
            print(f"❌ Telegram 發送失敗 ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"❌ Telegram 連線異常: {e}")

# ==========================================
# 3. 抓取資料 & 產生報表內容
# ==========================================
def get_stock_summary():
    print("正在分析資產狀況與黃金價格...")
    portfolio_data = load_portfolio()

    # 預設匯率
    rates = {"US": 32.5, "HK": 4.15, "JP": 0.21, "TW": 1.0}
    gold_usd = 0.0
    gold_twd_per_mace = 0.0

    try:
        data = yf.download(["USDTWD=X", "HKDTWD=X", "JPYTWD=X", "GC=F"], period="5d", progress=False, timeout=30, threads=False)
        if not data.empty:
            last_data = data['Close'].ffill().iloc[-1]
            if not math.isnan(last_data.get("USDTWD=X", float('nan'))): rates["US"] = float(last_data["USDTWD=X"])
            if not math.isnan(last_data.get("HKDTWD=X", float('nan'))): rates["HK"] = float(last_data["HKDTWD=X"])
            if not math.isnan(last_data.get("JPYTWD=X", float('nan'))): rates["JP"] = float(last_data["JPYTWD=X"])

            gold_usd_raw = last_data.get("GC=F", 0)
            if not math.isnan(gold_usd_raw):
                gold_usd = float(gold_usd_raw)
                # 金價換算 (1盎司=8.2944錢，此處採用一般黃金存摺換算率)
                gold_twd_per_mace = (gold_usd / 31.1035 * 3.75) * rates["US"]
    except Exception as e:
        print(f"匯率抓取失敗: {e}")

    total_cost, total_value = 0.0, 0.0
    loss_details = ""
    html_rows = ""

    for item in portfolio_data:
        try:
            stock = yf.Ticker(item['ticker'])
            hist = stock.history(period="5d", timeout=30)
            current = hist['Close'].ffill().iloc[-1] if not hist.empty else item['cost_price']

            rate = rates.get(item['market'], 1.0)
            c_twd = item['shares'] * item['cost_price'] * rate
            v_twd = item['shares'] * current * rate

            total_cost += c_twd
            total_value += v_twd

            roi = ((v_twd - c_twd) / c_twd) * 100 if c_twd != 0 else 0
            
            # --- Telegram 文字內容 (只列出虧損) ---
            symbol = {"US": "$", "HK": "HK$", "JP": "¥", "TW": "$"}.get(item['market'], "$")
            if roi < 0:
                loss_amt = int(v_twd - c_twd)
                loss_details += f"📉 <b>{item['name']}</b>\n   <code>{symbol}{item['cost_price']:,.2f} → {symbol}{current:,.2f}</code> (<b>{roi:.1f}%</b> / {loss_amt:,})\n"

            # --- HTML 報表行 ---
            display_name = item['name'].split(' ', 1)[-1] if ' ' in item['name'] else item['name']
            market_tag_class = {"TW": "tag-tw", "US": "tag-us", "HK": "tag-hk", "JP": "tag-jp"}.get(item['market'], "tag-tw")
            badge_class = "badge-up" if roi >= 0 else "badge-down"
            profit_amt = int(v_twd - c_twd)
            profit_color = "text-green" if profit_amt >= 0 else "text-red"

            html_rows += (
                f"<tr>"
                f"<td><div class='stock-name'>{display_name}</div><div class='stock-ticker'>{item['ticker']}</div></td>"
                f"<td><span class='market-tag {market_tag_class}'>{item['market']}</span></td>"
                f"<td class='right mono'>{item['shares']:,}</td>"
                f"<td class='right mono'>{symbol}{item['cost_price']:,.2f}</td>"
                f"<td class='right mono'>{symbol}{current:,.2f}</td>"
                f"<td class='right mono'>${int(v_twd):,}</td>"
                f"<td class='right mono {profit_color}'>{profit_amt:+,}</td>"
                f"<td class='right'><span class='badge {badge_class}'>{roi:+.1f}%</span></td>"
                f"</tr>"
            )
        except Exception as e:
            print(f"處理 {item['name']} 時出錯: {e}")
            continue

    profit_total = total_value - total_cost
    roi_total = (profit_total / total_cost) * 100 if total_cost > 0 else 0
    total_icon = "🔴" if profit_total >= 0 else "🟢"

    tw_tz = timezone(timedelta(hours=8))
    current_time = datetime.now(tw_tz).strftime('%Y-%m-%d %H:%M')
    gold_display = f"${int(gold_twd_per_mace):,}" if gold_twd_per_mace > 0 else "暫無資料"

    # ---- 組合 Telegram 訊息 ----
    tg_msg = (
        f"<b>📊 Fiona 持股資產日報</b>\n"
        f"📅 {current_time}\n"
        f"--------------------------\n"
        f"🟡 國際金價: <code>${gold_usd:.1f}</code>\n"
        f"💰 台灣金價: <code>{gold_display}</code> (錢)\n"
        f"💱 美元匯率: <code>{rates['US']:.2f}</code>\n"
        f"--------------------------\n"
        f"💰 總投入: <code>${int(total_cost):,}</code>\n"
        f"📈 總現值: <code>${int(total_value):,}</code>\n"
        f"🔥 總損益: <b>{int(profit_total):+,}</b> ({total_icon} <b>{roi_total:+.2f}%</b>)\n"
        f"--------------------------\n"
        f"{'🟢 <b>持股虧損清單：</b>' if loss_details else '🎉 全部持股皆為正報酬！'}\n"
        f"{loss_details}\n"
        f"📋 <a href='{REPORT_BASE_URL}'>查看完整投資組合儀表板</a>"
    )

    # ---- HTML 加密儀表板產生 (代碼維持不變，僅將變數注入) ----
    # [此部分維持您原有的 HTML 樣式與 AES 加密邏輯，確保佈署至 GitHub Pages]
    # (為了節省篇幅，此處省略重複的加密代碼部分，但在完整腳本中需保留)
    generate_html_report(html_rows, gold_usd, gold_display, rates, total_cost, total_value, profit_total, roi_total, current_time)

    return tg_msg

def generate_html_report(rows, g_usd, g_twd, rates, t_cost, t_value, p_total, r_total, c_time):
    # 此處放置您原有的加密與 HTML 寫入邏輯 (與原 Main.py 相同)
    import hashlib, base64
    from os import urandom
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    
    profit_color = "text-green" if p_total >= 0 else "text-red"
    
    report_content = f"""
    <div class="header"><h1>📊 Fiona 資產日報</h1><div class="time">{c_time}</div></div>
    <div class="gold-bar">
      <div class="gold-item"><div class="gold-label">🟡 國際金價</div><div class="gold-value">${g_usd:,.1f} USD</div></div>
      <div class="gold-item"><div class="gold-label">💰 台灣金價</div><div class="gold-value">{g_twd} TWD/錢</div></div>
      <div class="gold-item"><div class="gold-label">💱 USD/TWD</div><div class="gold-value">{rates['US']:.2f}</div></div>
    </div>
    <div class="summary">
      <div class="summary-card"><div class="label">總投入</div><div class="value">${int(t_cost):,}</div></div>
      <div class="summary-card"><div class="label">總現值</div><div class="value">${int(t_value):,}</div></div>
      <div class="summary-card"><div class="label">總損益</div><div class="value {profit_color}">{p_total:+,}</div><div class="sub {profit_color}">{r_total:+.2f}%</div></div>
    </div>
    <div class="card"><div class="card-header">📈 持股明細</div><div class="table-wrap"><table>
    <thead><tr><th>股票</th><th>市場</th><th class="right">股數</th><th class="right">成本</th><th class="right">現價</th><th class="right">現值</th><th class="right">損益</th><th class="right">報酬</th></tr></thead>
    <tbody>{rows}</tbody></table></div></div>
    """
    
    password = "vic2026"
    salt = urandom(16)
    iv = urandom(12)
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000, dklen=32)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, report_content.encode('utf-8'), None)
    
    # 這裡的 HTML 模板維持您原有的深色風格 (Dark Mode)
    # [省略部分 HTML Style 以確保代碼簡潔，請確保使用您原有的 CSS]
    # ... (HTML template code) ...
    
    # 最後寫入檔案
    os.makedirs("docs", exist_ok=True)
    # 此處應寫入完整的 HTML 字串，包含密碼驗證 JS
    # [請將您原本 script 產生的 html 字串填入此處]

# ==========================================
# 4. 主程式
# ==========================================
if __name__ == "__main__":
    # 強制使用時區與快取機制
    tw_tz = timezone(timedelta(hours=8))
    cache_bust = datetime.now(tw_tz).strftime('%Y%m%d%H%M')
    # 更新推播 URL (加上破快取)
    REPORT_URL_FINAL = f"{REPORT_BASE_URL}?t={cache_bust}"
    
    print("🚀 啟動資產分析任務...")
    msg = get_stock_summary()
    push_tg_message(msg)
