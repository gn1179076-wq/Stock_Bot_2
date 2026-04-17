# -*- coding: utf-8 -*-
import yfinance as yf
import requests
import os
import math
import json
import hashlib
import base64
from os import urandom
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ==========================================
# 1. 安全設定區 (從環境變數讀取)
# ==========================================
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
REPORT_PWD = os.getenv("REPORT_PWD")  # <--- 報表解鎖密碼
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
# 3. 抓取資料 & 產生報表
# ==========================================
def get_stock_summary(report_url_with_cache):
    print("正在分析資產狀況與黃金價格...")
    portfolio_data = load_portfolio()

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
                gold_twd_per_mace = (gold_usd / 31.1035 * 3.75) * rates["US"]
    except Exception as e:
        print(f"匯率或金價抓取失敗: {e}")

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

            symbol = {"US": "$", "HK": "HK$", "JP": "¥", "TW": "$"}.get(item['market'], "$")
            
            if roi < 0:
                loss_amt = int(v_twd - c_twd)
                loss_details += f"📉 <b>{item['name']}</b>\n <code>{symbol}{item['cost_price']:,.2f} → {symbol}{current:,.2f}</code> (<b>{roi:.1f}%</b> / {loss_amt:,})\n"

            display_name = item['name'].split(' ', 1)[-1] if ' ' in item['name'] else item['name']
            market_tag_class = {"TW": "tag-tw", "US": "tag-us", "HK": "tag-hk", "JP": "tag-jp"}.get(item['market'], "tag-tw")
            badge_class = "badge-up" if roi >= 0 else "badge-down"
            profit_amt = int(v_twd - c_twd)
            profit_color = "text-green" if profit_amt >= 0 else "text-red"

            html_rows += (
                "<tr>"
                f"<td><div class='stock-name'>{display_name}</div><div class='stock-ticker'>{item['ticker']}</div></td>"
                f"<td><span class='market-tag {market_tag_class}'>{item['market']}</span></td>"
                f"<td class='right mono'>{item['shares']:,}</td>"
                f"<td class='right mono'>{symbol}{item['cost_price']:,.2f}</td>"
                f"<td class='right mono'>{symbol}{current:,.2f}</td>"
                f"<td class='right mono'>${int(v_twd):,}</td>"
                f"<td class='right mono {profit_color}'>{profit_amt:+,}</td>"
                f"<td class='right'><span class='badge {badge_class}'>{roi:+.1f}%</span></td>"
                "</tr>"
            )
        except Exception as e:
            print(f"處理出錯: {e}")
            continue

    profit_total = total_value - total_cost
    roi_total = (profit_total / total_cost) * 100 if total_cost > 0 else 0
    total_icon = "🔴" if profit_total >= 0 else "🟢"

    tw_tz = timezone(timedelta(hours=8))
    current_time = datetime.now(tw_tz).strftime('%Y-%m-%d %H:%M')
    gold_display = f"${int(gold_twd_per_mace):,}" if gold_twd_per_mace > 0 else "暫無資料"

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
        f"📋 <a href='{report_url_with_cache}'>查看完整投資組合儀表板</a>"
    )

    generate_html_report(html_rows, gold_usd, gold_display, rates, total_cost, total_value, profit_total, roi_total, current_time)
    return tg_msg

def generate_html_report(rows, g_usd, g_twd, rates, t_cost, t_value, p_total, r_total, c_time):
    profit_color = "text-green" if p_total >= 0 else "text-red"
    report_inner = f"""
    <div class="header"><h1>📊 Fiona 資產日報</h1><div class="time">{c_time}</div></div>
    <div class="gold-bar">
        <div class="gold-item"><div class="gold-label">🟡 國際金價</div><div class="gold-value">${g_usd:,.1f} USD</div></div>
        <div class="gold-item"><div class="gold-label">💰 台灣金價</div><div class="gold-value">{g_twd} TWD/錢</div></div>
        <div class="gold-item"><div class="gold-label">💱 USD/TWD</div><div class="gold-value">{rates['US']:.2f}</div></div>
    </div>
    <div class="summary">
        <div class="summary-card"><div class="label">總投入</div><div class="value">${int(t_cost):,}</div></div>
        <div class="summary-card"><div class="label">總現值</div><div class="value">${int(t_value):,}</div></div>
        <div class="summary-card"><div class="label">總損益</div><div class="value {profit_color}">{p_total:+,.0f}</div><div class="sub {profit_color}">{r_total:+.2f}%</div></div>
    </div>
    <div class="card"><div class="card-header">📈 持股明細</div><div class="table-wrap"><table>
        <thead><tr><th>股票</th><th>市場</th><th class="right">股數</th><th class="right">成本</th><th class="right">現價</th><th class="right">現值</th><th class="right">損益</th><th class="right">報酬</th></tr></thead>
        <tbody>{rows}</tbody></table></div></div>
    """

    # AES 加密 (使用環境變數中的 REPORT_PWD)
    salt = urandom(16)
    iv = urandom(12)
    key = hashlib.pbkdf2_hmac('sha256', REPORT_PWD.encode(), salt, 100000, dklen=32)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, report_inner.encode('utf-8'), None)

    s_b64 = base64.b64encode(salt).decode()
    i_b64 = base64.b64encode(iv).decode()
    c_b64 = base64.b64encode(ciphertext).decode()

    # HTML 模板 (Plain String 避開 SyntaxError)
    html_template = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Fiona 資產日報</title>
<style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0d1117; color: #c9d1d9; font-family: 'Segoe UI', sans-serif; min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; }
    #login-screen { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 40px; width: 320px; text-align: center; }
    #pwd-input { width: 100%; padding: 10px; background: #0d1117; border: 1px solid #30363d; border-radius: 6px; color: #c9d1d9; font-size: 16px; margin-bottom: 12px; }
    #login-btn { width: 100%; padding: 10px; background: #238636; border: none; border-radius: 6px; color: white; cursor: pointer; }
    #error-msg { color: #f85149; margin-top: 10px; font-size: 14px; }
    #report { display: none; width: 100%; max-width: 1000px; padding: 20px; }
    .header { text-align: center; margin-bottom: 20px; }
    .gold-bar, .summary { display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }
    .gold-item, .summary-card { flex: 1; background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px; min-width: 140px; }
    .gold-value, .value { font-size: 18px; font-weight: bold; }
    .text-green { color: #3fb950; } .text-red { color: #f85149; }
    .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; overflow: hidden; }
    .card-header { padding: 12px 16px; background: #21262d; font-weight: bold; color: #58a6ff; }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; font-size: 14px; }
    th { background: #21262d; color: #8b949e; padding: 10px 12px; text-align: left; }
    td { padding: 10px 12px; border-top: 1px solid #21262d; }
    .right { text-align: right; } .mono { font-family: monospace; }
    .badge { padding: 3px 8px; border-radius: 10px; font-weight: bold; }
    .badge-up { background: #1f4e3d; color: #3fb950; } .badge-down { background: #4a1e1e; color: #f85149; }
    .market-tag { padding: 2px 6px; border-radius: 4px; font-size: 11px; }
    .tag-tw { background: #1f4e3d; color: #3fb950; } .tag-us { background: #1a3a5c; color: #58a6ff; }
</style>
</head>
<body>
<div id="login-screen">
    <h2 style="color:#58a6ff;margin-bottom:20px;">🔐 請輸入密碼</h2>
    <input type="password" id="pwd-input" placeholder="輸入密碼..." />
    <button id="login-btn" onclick="decrypt()">查看報表</button>
    <div id="error-msg"></div>
</div>
<div id="report"></div>
<script>
const S_B64 = "REPLACE_SALT", I_B64 = "REPLACE_IV", C_B64 = "REPLACE_CT";
function b2b(b) { const bin = atob(b); return Uint8Array.from(bin, c => c.charCodeAt(0)); }
async function decrypt() {
    const pw = document.getElementById('pwd-input').value;
    const err = document.getElementById('error-msg');
    try {
        const enc = new TextEncoder();
        const km = await crypto.subtle.importKey('raw', enc.encode(pw), 'PBKDF2', false, ['deriveKey']);
        const salt = b2b(S_B64), iv = b2b(I_B64), ct = b2b(C_B64);
        const key = await crypto.subtle.deriveKey(
            { name: 'PBKDF2', salt, iterations: 100000, hash: 'SHA-256' },
            km, { name: 'AES-GCM', length: 256 }, false, ['decrypt']
        );
        const dec = await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, ct);
        document.getElementById('login-screen').style.display = 'none';
        const r = document.getElementById('report');
        r.style.display = 'block';
        r.innerHTML = new TextDecoder().decode(dec);
    } catch (e) { err.textContent = '❌ 密碼錯誤'; }
}
document.getElementById('pwd-input').addEventListener('keydown', e => { if (e.key === 'Enter') decrypt(); });
</script>
</body>
</html>"""

    final_html = html_template.replace("REPLACE_SALT", s_b64).replace("REPLACE_IV", i_b64).replace("REPLACE_CT", c_b64)

    # 1. 寫入主要的 GitHub Pages 檔案
    os.makedirs("docs", exist_ok=True)
    with open("docs/portfolio.html", "w", encoding="utf-8") as f:
        f.write(final_html)
    print("✅ 主要報表已更新：docs/portfolio.html")

    # 2. 寫入 Daily_Report 備份檔案
    os.makedirs("Daily_Report", exist_ok=True)
    tw_tz = timezone(timedelta(hours=8))
    report_date = datetime.now(tw_tz).strftime('%Y-%m-%d')
    backup_path = f"Daily_Report/portfolio_{report_date}.html"
    with open(backup_path, "w", encoding="utf-8") as f:
        f.write(final_html)
    print(f"✅ 歷史備份已存檔：{backup_path}")

# ==========================================
# 4. 主程式
# ==========================================
if __name__ == "__main__":
    print("🚀 啟動資產分析任務...")
    git_branch = os.getenv("GITHUB_REF_NAME", "unknown_branch") 
    
    # 安全檢查：確保密碼已設定
    if not REPORT_PWD:
        print("❌ 嚴重錯誤：找不到環境變數 REPORT_PWD，無法產生加密報表。")
        exit(1)

    tw_tz = timezone(timedelta(hours=8))
    cache_bust = datetime.now(tw_tz).strftime('%Y%m%d%H%M')
    
    # 👈 修改這行：將 git_branch 傳入 get_stock_summary
    final_url = f"{REPORT_BASE_URL}?t={cache_bust}"
    msg = get_stock_summary(final_url, git_branch) 
    push_tg_message(msg)
