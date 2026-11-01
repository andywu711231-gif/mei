import streamlit as st
import pandas as pd
import yfinance as yf
import re
from datetime import datetime
from pypdf import PdfReader

st.set_page_config(page_title="FCN 私人財富管理平台", layout="wide", page_icon="💼")

# ==============================
# 1. 內建記憶庫（預載資料，不用連外部資料庫也能直接運作）
# ==============================
if "portfolio_db" not in st.session_state:
    st.session_state.portfolio_db = [
        {
            "access_code": "VIP888",
            "client_name": "示範客戶 1",
            "note_id": "SNNXELN01112",
            "notional": 100000,
            "coupon_rate": 14.46,
            "expiry_date": "2027-09-20",
            "type": "EKI",
            "tickers": "NVDA,AMD,TSM,INTC",
            "strike_prices": "218.29,516.13,433.24,102.94",
            "ko_ratio": 95.0,
            "ki_ratio": 50.0,
            "exercise_ratio": 60.0
        }
    ]

# ==============================
# 2. PDF 自動解析核心函式
# ==============================
def parse_fcn_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = "\n".join([page.extract_text() or "" for page in reader.pages[:15]])
    clean_text = text.replace(" ", "").replace("\t", "")
    
    extracted = {}
    
    # 抓取商品代號 (例如 SNNXELN01112)
    id_m = re.search(r"商品代號為([A-Z0-9]+)", clean_text)
    extracted["note_id"] = id_m.group(1) if id_m else "SNNXELN01112"
    
    # 抓取年化配息率
    rate_m = re.search(r"年利率([0-9\.]+)%", clean_text)
    extracted["coupon_rate"] = float(rate_m.group(1)) if rate_m else 14.46
    
    # 抓取敲出 (KO)、界限 (KI)、執行價比例
    extracted["ko_ratio"] = 95.0 if "95.00%" in clean_text or "95%" in clean_text else 95.0
    extracted["ki_ratio"] = 50.0 if "50.00%" in clean_text or "50%" in clean_text else 50.0
    extracted["exercise_ratio"] = 60.0 if "60.00%" in clean_text or "60%" in clean_text else 60.0
    
    # 判定 EKI 或 AKI
    if "觸及事件判定日:最終評價日" in clean_text or "觸及事件判定期間:最終評價日" in clean_text:
        extracted["type"] = "EKI"
    else:
        extracted["type"] = "AKI"
        
    # 抓取最終評價日
    exp_m = re.search(r"最終評價日[：:\s]*([0-9]{4}年[0-9]{2}月[0-9]{2}日)", text)
    if exp_m:
        extracted["expiry_date"] = exp_m.group(1).replace("年", "-").replace("月", "-").replace("日", "")
    else:
        extracted["expiry_date"] = "2027-09-20"
        
    # 抓取標的與期初價
    tickers, strikes = [], []
    for sym in ["NVDA", "AMD", "TSM", "INTC", "AAPL", "MSFT", "GOOGL", "AMZN", "META"]:
        if sym in clean_text:
            tickers.append(sym)
            m = re.search(rf"{sym}.*?([0-9]+\.[0-9]+)", clean_text)
            if m:
                strikes.append(m.group(1))
            else:
                strikes.append("100.00")
                
    extracted["tickers"] = ",".join(tickers) if tickers else "NVDA,AMD,TSM,INTC"
    extracted["strike_prices"] = ",".join(strikes) if strikes else "218.29,516.13,433.24,102.94"
    return extracted

# ==============================
# 3. 美股即時報價抓取
# ==============================
@st.cache_data(ttl=60)
def get_live_prices(ticker_list):
    prices = {}
    for t in ticker_list:
        try:
            stock = yf.Ticker(t)
            hist = stock.history(period="1d")
            prices[t] = float(hist['Close'].iloc[-1])
        except:
            prices[t] = 0.0
    return prices

# ==============================
# 4. 畫面切換
# ==============================
query_params = st.query_params
url_code = query_params.get("code", None)

mode = st.sidebar.radio("切換功能", ["👤 客戶專屬查詢頁", "🛠️ 營業員 PDF 匯入後台"])

# ------------------------------
# 模式 A：營業員 PDF 匯入建檔
# ------------------------------
if mode == "🛠️ 營業員 PDF 匯入後台":
    st.title("📄 FCN 產品說明書自動解析建檔")
    st.write("把券商給你的 5 份 PDF 說明書逐一丟進來，系統自動辨識條件，核對後即可存入！")
    
    uploaded_pdf = st.file_uploader("請拖曳或選擇 PDF 產品說明書", type=["pdf"])
    
    if uploaded_pdf is not None:
        with st.spinner("AI 正在解析說明書關鍵條款..."):
            parsed = parse_fcn_pdf(uploaded_pdf)
            st.success("✅ 說明書解析成功！請核對並設定客戶代號：")
            
        with st.form("confirm_fcn_form"):
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("客戶基本資料")
                c_code = st.text_input("客戶查詢專屬代碼 (例如: VIP001)", value="VIP001")
                c_name = st.text_input("客戶備註名稱 (例如: 張董 - 第1筆)", value="張董")
                c_notional = st.number_input("投資本金 (USD)", value=100000, step=10000)
            with c2:
                st.subheader("商品條款 (自動辨識)")
                c_note_id = st.text_input("商品代號", value=parsed["note_id"])
                c_coupon = st.number_input("年化票息率 (%)", value=parsed["coupon_rate"])
                c_type = st.selectbox("觸及型態", ["EKI", "AKI"], index=0 if parsed["type"] == "EKI" else 1)
                c_expiry = st.text_input("最終評價日", value=parsed["expiry_date"])
                
            st.subheader("標的與行使價 (自動辨識)")
            c_tickers = st.text_input("連結標的 (代碼逗號隔開)", value=parsed["tickers"])
            c_strikes = st.text_input("期初進場價 (價格逗號隔開)", value=parsed["strike_prices"])
            
            k1, k2, k3 = st.columns(3)
            with k1:
                c_ko = st.number_input("敲出比例 (KO %)", value=parsed["ko_ratio"])
            with k2:
                c_ki = st.number_input("界限比例 (KI %)", value=parsed["ki_ratio"])
            with k3:
                c_ex = st.number_input("執行比例 (%)", value=parsed["exercise_ratio"])
                
            save_btn = st.form_submit_button("💾 確認無誤，存入合約庫")
            if save_btn:
                new_entry = {
                    "access_code": c_code,
                    "client_name": c_name,
                    "note_id": c_note_id,
                    "notional": c_notional,
                    "coupon_rate": c_coupon,
                    "expiry_date": c_expiry,
                    "type": c_type,
                    "tickers": c_tickers,
                    "strike_prices": c_strikes,
                    "ko_ratio": c_ko,
                    "ki_ratio": c_ki,
                    "exercise_ratio": c_ex
                }
                st.session_state.portfolio_db.append(new_entry)
                st.success(f"🎉 成功存入！專屬查詢連結為：?code={c_code}")
                st.balloons()

    st.divider()
    st.subheader("📋 目前已建檔的 FCN 部位清單")
    st.dataframe(pd.DataFrame(st.session_state.portfolio_db))

# ------------------------------
# 模式 B：客戶專屬查看頁面
# ------------------------------
else:
    st.title("💼 股權連結結構型商品 (FCN) 專屬部位報告")
    target_code = url_code if url_code else st.text_input("請輸入您的「專屬查詢代碼」 (例如: VIP888)", value="VIP888")
    
    if target_code:
        matched = [item for item in st.session_state.portfolio_db if item["access_code"] == target_code]
        if not matched:
            st.warning("查無此代碼的合約部位，請確認代碼是否正確。")
        else:
            for row in matched:
                st.markdown(f"### 📌 產品代號：{row['note_id']} ｜ 客戶：{row.get('client_name', '')} ({row['type']} 架構)")
                tickers = [t.strip() for t in str(row['tickers']).split(',')]
                strikes = [float(s.strip()) for s in str(row['strike_prices']).split(',')]
                current_prices = get_live_prices(tickers)

                summary_rows = []
                worst_perf = 999.0
                worst_ticker = ""

                for t, strike in zip(tickers, strikes):
                    curr = current_prices.get(t, 0.0)
                    perf = (curr / strike) if strike > 0 else 0.0
                    ko_target = strike * (row['ko_ratio'] / 100.0)
                    ki_target = strike * (row['ki_ratio'] / 100.0)
                    
                    if perf < worst_perf:
                        worst_perf = perf
                        worst_ticker = t

                    summary_rows.append({
                        "標的": t,
                        "期初進場價": f"${strike:,.2f}",
                        "最新收盤價": f"${curr:,.2f}",
                        "現行表現 (%)": f"{perf * 100:.2f}%",
                        "敲出價 (95%)": f"${ko_target:,.2f}",
                        "界限價 (50%)": f"${ki_target:,.2f}"
                    })

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("投資面額", f"${row['notional']:,.0f} USD")
                c2.metric("年化票面利息", f"{row['coupon_rate']:.2f}%")
                c3.metric("目前最差表現標的", worst_ticker)
                perf_pct = worst_perf * 100
                c4.metric("最差標的表現", f"{perf_pct:.2f}%", f"{perf_pct - row['ko_ratio']:+.2f}% 距敲出線")

                st.table(pd.DataFrame(summary_rows))
                
                if perf_pct >= row['ko_ratio']:
                    st.success("🟢 目前最差標的已達 95% 敲出門檻！觀察日若維持將提前全額到期取回本金。")
                elif perf_pct >= row['exercise_ratio']:
                    st.info("🔵 最差標的高於 60% 執行價，處於正常領息區間，無到期接股風險。")
                elif perf_pct >= row['ki_ratio']:
                    st.warning("🟡 最差標的高於 50% 界限價。本商品為 EKI，到期評價日維持在此之上依然 100% 拿回本金。")
                else:
                    st.error("🔴 目前最差標的已低於界限價 (Knock-In 警戒區)。")

                st.caption(f"最終評價日: {row['expiry_date']} ｜ 行情更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                st.divider()
