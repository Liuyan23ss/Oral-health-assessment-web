import streamlit as st
import os
import base64
from streamlit_option_menu import option_menu
import streamlit as st
import pandas as pd
import gspread
import json
from google.oauth2.service_account import Credentials

# ==========================================
# 網頁基本設定 (開啟 Wide 模式)
# ==========================================
st.set_page_config(page_title="口腔健康計畫", layout="wide")

# ==========================================
# 圖片轉 Base64 輔助函數
# ==========================================
def get_image_base64(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            ext = image_path.split('.')[-1].lower()
            mime_type = "image/jpeg"
            if ext == "png": mime_type = "image/png"
            elif ext == "avif": mime_type = "image/avif"
            
            b64_data = base64.b64encode(img_file.read()).decode('utf-8')
            return f"data:{mime_type};base64,{b64_data}"
    return ""

# ==========================================
# Google Sheets 連線
# ==========================================
@st.cache_resource
def get_gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    credentials = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=scopes,
    )
    client = gspread.authorize(credentials)
    return client


def get_worksheet(worksheet_name: str):
    client = get_gspread_client()
    spreadsheet = client.open_by_key(st.secrets["sheets"]["spreadsheet_id"])
    return spreadsheet.worksheet(worksheet_name)


@st.cache_data(ttl=30)
def load_ktv_results():
    worksheet = get_worksheet(st.secrets["sheets"]["ktv_worksheet_name"])
    records = worksheet.get_all_records()

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    # 數值欄位轉型
    numeric_cols = ["final_score", "overall_precision", "overall_recall", "overall_f1"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # category_metrics_json 轉 dict
    if "category_metrics_json" in df.columns:
        def parse_json(x):
            try:
                return json.loads(x) if x else {}
            except:
                return {}
        df["category_metrics_dict"] = df["category_metrics_json"].apply(parse_json)

    return df

def render_ktv_results_page():
    st.markdown("""
        <style>
        .ktv-banner {
            position: relative;
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            padding: 90px 20px;
            text-align: center;
            margin-bottom: 25px;
            border-radius: 0 0 20px 20px;
            overflow: hidden;
        }

        .ktv-banner::before {
            content: "";
            position: absolute;
            inset: 0;
            background: rgba(0, 0, 0, 0.35);   /* 讓字更清楚 */
        }

        .ktv-banner-content {
            position: relative;
            z-index: 1;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown(f"""
        <div class="ktv-banner" style="background-image: url('{img_ktv_banner_b64}');">
            <div class="ktv-banner-content">
                <h1 style="margin:0; color:white; font-size:3.2rem; font-weight:900;">
                    KTV檢測結果
                </h1>
                <p style="margin-top:15px; color:white; font-size:1.4rem;">
                    顯示受試者 KTV 歌唱辨識分析結果與 F1-score
                </p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    df = load_ktv_results()

    if df.empty:
        st.warning("目前還沒有 KTV 檢測結果資料。")
        return

    # 依建立時間排序，新到舊
    if "created_at" in df.columns:
        df = df.sort_values(by="created_at", ascending=False)

    # 建立下拉選單
    if "song_name" in df.columns and "created_at" in df.columns:
        df["display_name"] = df["created_at"].astype(str) + "｜" + df["song_name"].astype(str)
    elif "created_at" in df.columns:
        df["display_name"] = df["created_at"].astype(str)
    else:
        df["display_name"] = df.index.astype(str)

    selected_display = st.selectbox(
        "選擇一筆檢測結果",
        df["display_name"].tolist()
    )

    selected_row = df[df["display_name"] == selected_display].iloc[0]

    # 1. 核心分數
    st.markdown('<div class="ktv-card">', unsafe_allow_html=True)
    st.subheader("總體表現")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("F1-score", f"{selected_row.get('final_score', 0):.2f}")
    c2.metric("Precision", f"{selected_row.get('overall_precision', 0):.3f}")
    c3.metric("Recall", f"{selected_row.get('overall_recall', 0):.3f}")
    c4.metric("F1", f"{selected_row.get('overall_f1', 0):.3f}")

    st.markdown('</div>', unsafe_allow_html=True)

    # 2. 基本資訊
    st.markdown('<div class="ktv-card">', unsafe_allow_html=True)
    st.subheader("檢測資訊")

    info_col1, info_col2 = st.columns(2)

    with info_col1:
        st.write("**建立時間：**", selected_row.get("created_at", ""))
        st.write("**歌曲名稱：**", selected_row.get("song_name", ""))
        st.write("**模型：**", selected_row.get("model", ""))
        st.write("**語言：**", selected_row.get("language", ""))

    with info_col2:
        st.write("**音檔路徑：**", selected_row.get("audio_path", ""))
        st.write("**歌詞檔路徑：**", selected_row.get("ref_lyrics_path", ""))

    st.markdown('</div>', unsafe_allow_html=True)

    # 3. 辨識結果
    st.markdown('<div class="ktv-card">', unsafe_allow_html=True)
    st.subheader("文字比對")

    if "reference_text" in selected_row:
        st.text_area("標準歌詞", selected_row.get("reference_text", ""), height=180)

    if "recognized_text_raw" in selected_row:
        st.text_area("Whisper 辨識結果", selected_row.get("recognized_text_raw", ""), height=180)

    st.markdown('</div>', unsafe_allow_html=True)

    # 4. 聲母分類指標
    st.markdown('<div class="ktv-card">', unsafe_allow_html=True)
    st.subheader("分類指標分析")

    category_metrics = selected_row.get("category_metrics_dict", {})

    if category_metrics:
        rows = []
        for category, metrics in category_metrics.items():
            rows.append({
                "分類": category,
                "TP": metrics.get("tp", 0),
                "FP": metrics.get("fp", 0),
                "FN": metrics.get("fn", 0),
                "Precision": metrics.get("precision", 0),
                "Recall": metrics.get("recall", 0),
                "F1": metrics.get("f1", 0),
            })

        category_df = pd.DataFrame(rows)
        st.dataframe(category_df, use_container_width=True, hide_index=True)
    else:
        st.info("目前沒有分類指標資料。")

    st.markdown('</div>', unsafe_allow_html=True)

    # 5. 歷史紀錄
    st.markdown('<div class="ktv-card">', unsafe_allow_html=True)
    st.subheader("最近 KTV 檢測紀錄")

    preview_cols = [col for col in [
        "created_at", "song_name", "final_score", "overall_precision", "overall_recall", "overall_f1"
    ] if col in df.columns]

    if preview_cols:
        preview_df = df[preview_cols].copy().head(10)
        st.dataframe(preview_df, use_container_width=True, hide_index=True)

    st.markdown('</div>', unsafe_allow_html=True)

def draw_navbar(active_tab):
    # active_tab: 1 (首頁), 2 (介紹), 3 (訓練)
    c1, c2, c3 = st.columns([1, 1, 1])
    
    # 樣式定義
    style_active = "background-color: #28A745; color: white; padding: 10px; border-radius: 10px; text-align: center; font-weight: bold; cursor: pointer; display: block; text-decoration: none;"
    style_inactive = "background-color: #FFA500; color: white; padding: 10px; border-radius: 10px; text-align: center; font-weight: bold; cursor: pointer; display: block; text-decoration: none;"

    with c1:
        if st.button("🏠 首頁", key="nav_home", use_container_width=True):
            st.session_state.sub_page = "小小首頁"
            st.rerun()
    with c2:
        # 介紹頁面 (B, C, D 都在這區)
        st.markdown(f"<div style='{style_active if active_tab==2 else style_inactive}'>📋 口腔衰弱與保健介紹</div>", unsafe_allow_html=True)
    with c3:
        if st.button("🏋️ 口腔機能運動訓練", key="nav_train", use_container_width=True):
            st.session_state.sub_page = "訓練頁面" # 假設的頁面名
            st.rerun()

def draw_more_info():
    st.write("---")
    st.subheader("想知道更多嗎？")
    
    # 使用圓角藥丸按鈕樣式
    if st.button("👉 預防口腔衰弱的重要性 〉", key="more_b", use_container_width=True):
        st.session_state.sub_page = "預防口腔衰弱的重要性"
        st.rerun()
        
    if st.button("👥 哪些人容易出現口腔衰弱 〉", key="more_d", use_container_width=True):
        st.session_state.sub_page = "哪些人容易出現口腔衰弱"
        st.rerun()

def go_to_page(main_page, sub_page=None):
    st.session_state.main_page = main_page
    if sub_page is not None:
        st.session_state.sub_page = sub_page
    st.rerun()

# 讀取圖片 (請確保圖片檔案與 app.py 放在同一個資料夾)
img_a_b64 = get_image_base64("a.avif")
img_b_b64 = get_image_base64("b.avif")
img_c_b64 = get_image_base64("c.avif")
img_d_b64 = get_image_base64("d.avif")
img_e_b64 = get_image_base64("e.avif")
img_team_b64 = get_image_base64("image_d95f6b.jpg")
imgs = {"bg2" : get_image_base64("bg2.png"), "z1": get_image_base64("z1.png"), "z2": get_image_base64("z2.png"), "z3": get_image_base64("z3.png"),}
img_ktv_banner_b64 = get_image_base64("ktv_banner.jpg")

# 備用圖片 (若找不到圖片則顯示空白避免報錯)
if not img_team_b64:
    img_team_b64 = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"

# ==========================================
# 全局 CSS 樣式設定
# ==========================================
st.markdown(
    """
    <style>
    /* 1. 隱藏右上角預設的 header */
    [data-testid="stHeader"] {
        display: none !important;
    }

    /* 2. 針對所有可能的 Streamlit 容器徹底移除邊距與寬度限制 */
    [data-testid="block-container"], 
    [data-testid="stMainBlockContainer"], 
    .block-container {
        padding-top: 0rem !important;
        padding-bottom: 0rem !important;
        padding-left: 0rem !important;
        padding-right: 0rem !important;
        max-width: 100% !important;
        width: 100% !important;
    }

    /* 3. 強制主畫面滿版，並防止因為小誤差產生底部的橫向捲軸 */
    .stApp, html, body {
        overflow-x: hidden !important;
        margin: 0px !important;
        padding: 0px !important;
    }

    /* 讓選單文字更粗更顯眼 */
    .nav-link {
        font-weight: bold !important;
    }
    </style>
    <style>
    div[data-testid="stButton"] > button {
        background-color: #28a745;
        color: white;
        border-radius: 25px;
        font-weight: bold;
        padding: 10px;
        border: none;
    }

    div[data-testid="stButton"] > button:hover {
        background-color: #218838;
    }
    </style>
    <style>

    /* 全站字體放大基準 */
    html {
        font-size: 30px;  /* 原本大概 14~16，這裡直接 +20~30% */
    }

    /* 標題優化（避免過大破版） */
    h1 { font-size: 2.5rem !important; }
    h2 { font-size: 2rem !important; }
    h3 { font-size: 1.6rem !important; }

    /* 一般文字 */
    p, span, label, div {
        font-size: 1.1rem !important;
    }

    /* Streamlit 元件 */
    .stMarkdown, .stText, .stDataFrame {
        font-size: 1.05rem !important;
    }

    /* Button 字體 */
    div[data-testid="stButton"] > button {
        font-size: 1.1rem !important;
    }

    /* selectbox */
    div[data-baseweb="select"] {
        font-size: 1.1rem !important;
    }

    </style>
    """,
    unsafe_allow_html=True
)
# ==========================================
# 頂部導覽列 (改為橘色底、內容置中)
# ==========================================
st.markdown("<div style='padding-top: 15px;'></div>", unsafe_allow_html=True)
# ==========================================
# Session State 初始化
# ==========================================
if "main_page" not in st.session_state:
    st.session_state.main_page = "首頁"

if "sub_page" not in st.session_state:
    st.session_state.sub_page = "小小首頁"

# ==========================================
# 接收網址參數來控制跳頁
# ==========================================
query_params = st.query_params

if "page" in query_params:
    target_page = query_params["page"]

    if target_page == "intro":
        st.session_state.main_page = "口腔衰弱與保健介紹"
        st.session_state.sub_page = "小小首頁"
    elif target_page == "train":
        st.session_state.main_page = "口腔機能運動訓練"

page_options = [
    "首頁",
    "口腔衰弱與保健介紹",
    "口腔機能運動訓練",
    "KTV檢測結果",
    "舌肌運動檢測結果"
]
default_index = page_options.index(st.session_state.main_page)
selected_page = option_menu(
    menu_title=None,
    options=page_options,
    icons=["house", "journal-medical", "person-arms-up", "bar-chart", "activity"],
    default_index=default_index,
    orientation="horizontal",
    styles={
        "container": {
            "padding": "0!important",
            "background-color": "#FF9900",
            "border-radius": "0px",
            "margin": "0px !important",
            "max-width": "100% !important",
            "width": "100%",
            "display": "flex",
            "justify-content": "center"
        },
        "icon": {"color": "white", "font-size": "28px"},
        "nav-link": {
            "font-size": "28px",
            "text-align": "center",
            "margin": "0px 20px",
            "color": "white",
            "--hover-color": "#E67E22"
        },
        "nav-link-selected": {
            "background-color": "#28a745",
            "color": "white",
            "font-weight": "bold"
        },
    }
)
# Session State 初始化
if "main_page" not in st.session_state:
    st.session_state.main_page = "首頁"

if "sub_page" not in st.session_state:
    st.session_state.sub_page = "小小首頁"

# 接收網址參數來控制跳頁
query_params = st.query_params

if "page" in query_params:
    target_page = query_params["page"]

    if target_page == "intro":
        st.session_state.main_page = "口腔衰弱與保健介紹"
        st.session_state.sub_page = "小小首頁"
    elif target_page == "train":
        st.session_state.main_page = "口腔機能運動訓練"

# page_options = ["首頁", "口腔衰弱與保健介紹", "口腔機能運動訓練"]
default_index = page_options.index(st.session_state.main_page)
st.session_state.main_page = selected_page
# 頁面 1：首頁 
if selected_page == "首頁":
    
    # 1. 滿版橫幅
    st.markdown(f"""
    <div style='position: relative; width: 100%; height: 450px; overflow: hidden; background-color: #f0f2f6;'>
    <img src='{img_a_b64}' style='width: 100%; height: 100%; object-fit: cover; display: block;' onerror="this.style.display='none';"/>
    <div style='position: absolute; top: 0; left: 0; width: 100%; height: 100%; display: flex; align-items: center; background: linear-gradient(to right, rgba(255,255,255,0.9) 0%, rgba(255,255,255,0.4) 50%, rgba(0,0,0,0) 100%); padding-left: 5%;'>
    <div>
    <h2 style='color: #333; font-weight: bold; margin: 0; font-size: 24px;'>專為中高年齡口腔衰弱者製作的</h2>
    <h1 style='color: #ff4b4b; font-weight: bold; font-size: 3.5rem !important; margin: 5px 0 0 0;'>口腔機能運動訓練</h1>
    </div>
    </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 2. 滿版雙拼圖卡
    st.markdown(f"""
    <div style='display: flex; width: 100%; flex-wrap: wrap;'>
    <div style='flex: 1; min-width: 300px; position: relative; height: 350px; overflow: hidden; background-color: #6c757d;'>
    <img src='{img_b_b64}' style='width: 100%; height: 100%; object-fit: cover; display: block;' onerror="this.style.display='none';" />
    <div style='position: absolute; top: 0; left: 0; width: 100%; height: 100%; background-color: rgba(0, 0, 0, 0.4); display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; padding: 0 10%;'>
    <h2 style='color: white; font-weight: bold; margin-bottom: 15px;'>💡 關於口腔衰弱</h2>
    <p style='color: white; font-size: 18px;'>為一種因老化而引起咀嚼相關障礙的症候群。</p>
    </div>
    </div>
    <div style='flex: 1; min-width: 300px; position: relative; height: 350px; overflow: hidden; background-color: #343a40;'>
    <img src='{img_c_b64}' style='width: 100%; height: 100%; object-fit: cover; display: block;' onerror="this.style.display='none';" />
    <div style='position: absolute; top: 0; left: 0; width: 100%; height: 100%; background-color: rgba(0, 0, 0, 0.6); display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; padding: 0 10%;'>
    <h2 style='color: white; font-weight: bold; margin-bottom: 15px;'>🏃 關於口腔機能運動訓練</h2>
    <p style='color: white; font-size: 18px;'>針對中高年齡口腔衰弱者提供口腔運動訓練，提升吞嚥相關肌群的協調性，進而促進身體健康。</p>
    </div>
    </div>
    </div>
    """, unsafe_allow_html=True)
    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        if st.button("💡 看更多：關於口腔衰弱", key="go_intro", use_container_width=True):
            go_to_page("口腔衰弱與保健介紹", "小小首頁")

    with col_btn2:
        if st.button("🏃 看更多：口腔機能運動訓練", key="go_train", use_container_width=True):
            go_to_page("口腔機能運動訓練")

    # 3. 團隊介紹區塊 (底色、圖片、置中排版)
    st.markdown(f"""
    <div style='background: linear-gradient(to bottom, #fdfbfb 0%, #ebedee 100%); padding: 50px 10%; margin: 40px 5%; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); text-align: center;'>
    <img src='{img_team_b64}' style='width: 160px; height: 160px; object-fit: cover; border-radius: 50%; box-shadow: 0 6px 20px rgba(0,0,0,0.15); margin-bottom: 20px;' onerror="this.style.display='none';" />
    <h2 style='color: #2c3e50; font-weight: bold; margin-bottom: 15px;'>口腔健康團隊</h2>
    <p style='color: #555; font-size: 18px; max-width: 750px; margin: 0 auto 35px auto; line-height: 1.8;'>
    我們提供中高齡者口腔衰弱評估及健康訓練。期望能幫助您及家人維持口腔與吞嚥肌群的健康。
    </p>
    <a href="https://oral-health-assessment-xayzsljqe5fxkafaugb6qs.streamlit.app/" target="_blank" style="display: inline-block; background-color: #ff4b4b; color: white; padding: 18px 45px; font-size: 20px; font-weight: bold; text-decoration: none; border-radius: 40px; box-shadow: 0 4px 15px rgba(255, 75, 75, 0.4); transition: transform 0.2s;">
    👉 點此進入【原民族群口腔健康檢查紀錄表】
    </a>
    </div>
    """, unsafe_allow_html=True)
# 頁面 2：口腔衰弱與保健介紹 (含狀態切換與淡入動畫)
elif selected_page == "口腔衰弱與保健介紹":
    
    # 1. 初始化 Session State (用來記憶目前在哪個子頁面)
    if "sub_page" not in st.session_state:
        st.session_state.sub_page = "小小首頁"

    # 2. 注入「變白再淡入顯示」的 CSS 動畫
    st.markdown("""
        <style>
        @keyframes fadeInFromWhite {
            0% { opacity: 0; filter: brightness(2); transform: translateY(10px); }
            100% { opacity: 1; filter: brightness(1); transform: translateY(0); }
        }
        .fade-in-content {
            animation: fadeInFromWhite 0.8s ease-out forwards;
            width: 100%;
        }
        /* 美化返回按鈕 */
        div[data-testid="stButton"] > button {
            border-radius: 20px;
            font-weight: bold;
        }
        </style>
    """, unsafe_allow_html=True)

    # --- 狀態 A：關於口腔衰弱 (小小首頁) ---
    if st.session_state.sub_page == "小小首頁":
        # 1. 注入背景與標題樣式
        st.markdown(f"""
            <style>
            .stApp {{
                background-image: url('{imgs['bg2']}');
                background-size: cover;
                background-position: center;
                background-attachment: fixed;
            }}
            /* 標題橫幅樣式 */
            .header-banner {{
                background-color: rgba(121, 184, 230, 0.85); /* 之前的粉藍色，加點透明度配背景 */
                padding: 50px 20px;
                text-align: center;
                color: white;
                margin: 0px -50px 40px -50px; /* 向上向左右抵消邊距 */
            }}
            .info-card {{
                background-color: rgba(255, 255, 255, 0.95);
                border-radius: 15px;
                padding: 30px 20px;
                text-align: center;
                height: 280px;
                display: flex;
                flex-direction: column;
                justify-content: center;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            }}
            .card-number {{
                background-color: #D5D3D3;
                color: #555;
                width: 40px;
                height: 40px;
                border-radius: 50%;
                line-height: 40px;
                font-weight: bold;
                margin: 0 auto 15px auto;
            }}
            </style>
            
            <div class="header-banner">
                <h2 style="margin: 0; font-size: 24px; font-weight: bold; letter-spacing: 2px;">中高齡長者</h2>
                <h1 style="margin: 10px 0 0 0; font-size: 42px; font-weight: bold; letter-spacing: 3px;">口腔衰弱照護</h1>
            </div>

            <h2 style="text-align: center; color: #333; margin-bottom: 40px; font-weight: bold;">
                關於口腔衰弱
            </h2>
        """, unsafe_allow_html=True)

        # 3. 三張卡片排版
        col1, col2, col3 = st.columns(3, gap="large")

        with col1:
            st.markdown('<div class="info-card"><div class="card-number">1</div><h4 style="font-weight:bold;">預防口腔衰弱的重要性</h4><p style="font-size:0.9rem; color:#666;">您知道口腔的功能有哪些嗎？<br>什麼是口腔衰弱？</p></div>', unsafe_allow_html=True)
            if st.button("瞭解更多 〉", key="btn_sub1"):
                st.session_state.sub_page = "預防口腔衰弱的重要性"
                st.rerun()

        with col2:
            st.markdown('<div class="info-card"><div class="card-number">2</div><h4 style="font-weight:bold;">口腔衰弱會怎麼樣嗎</h4><p style="font-size:0.9rem; color:#666;">您是否有咬不動、吞不好、吃不下、口氣差、人衰老等症狀？</p></div>', unsafe_allow_html=True)
            if st.button("瞭解更多 〉", key="btn_sub2"):
                st.session_state.sub_page = "口腔衰弱會怎麼樣嗎"
                st.rerun()

        with col3:
            st.markdown('<div class="info-card"><div class="card-number">3</div><h4 style="font-weight:bold;">哪些人容易出現口腔衰弱</h4><p style="font-size:0.9rem; color:#666;">您是否為口腔衰弱高風險者</p></div>', unsafe_allow_html=True)
            if st.button("瞭解更多 〉", key="btn_sub3"):
                st.session_state.sub_page = "哪些人容易出現口腔衰弱"
                st.rerun()
    # ---------------------------------------------------------
    # 狀態 B：內容頁 - 預防口腔衰弱的重要性
    # ---------------------------------------------------------
    elif st.session_state.sub_page == "預防口腔衰弱的重要性":
        # 使用欄位來限制內容寬度，讓左右兩側留白，閱讀起來比較舒適
        col_space1, col_main, col_space2 = st.columns([1, 8, 1])
        with col_main:
            st.markdown('<div class="fade-in-content" style="padding: 40px 0;">', unsafe_allow_html=True)
            # 返回按鈕
            if st.button("〈 返回", key="back_1"):
                st.session_state.sub_page = "小小首頁"
                st.rerun()
                
            st.title("❓ 預防口腔衰弱的重要性")
            st.divider()
            
            # ==========================================
            # 上半部：左圖 (d.avif) / 右文
            # ==========================================
            top_col1, top_col2 = st.columns(2, gap="large")
            
            with top_col1:
                # 放入 d.avif (若找不到檔案會顯示預設提示)
                try:
                    st.image(img_d_b64, width="stretch")
                except:
                    st.error("找不到 d.avif 圖片，請確認檔案已放置於同一資料夾。")
                    
            with top_col2:
                st.markdown("<h3 style='color: #E67E22; font-weight: bold;'>口腔的功能有哪些</h3>", unsafe_allow_html=True)
                st.write("從小到大，口腔一直執行著許多的功能，包含進食 (咀嚼、吞嚥)，品嘗美味 (感受酸甜苦辣、冷熱)、分泌口水讓食物容易吞嚥、說話發音及藉由嘴型的變化做出不同的表情。")

            # 加上一點垂直間距
            st.markdown("<br><br>", unsafe_allow_html=True)

            # ==========================================
            # 下半部：左文 / 右圖 (e.avif)
            # ==========================================
            bottom_col1, bottom_col2 = st.columns(2, gap="large")
            
            with bottom_col1:
                st.markdown("<h3 style='color: #E67E22; font-weight: bold;'>口腔衰弱是什麼</h3>", unsafe_allow_html=True)
                st.write("當口腔、舌頭肌肉力量減少、神經出現不協調時，口腔功能就會退化，您會注意到以下症狀出現：")
                st.markdown("""
                1. 水、食物不能好好含在口中，容易從嘴巴流出或掉出。
                2. 食物吞不乾淨，口腔內有明顯食物殘渣。
                3. 吃流質食物 (水、湯、水量較多的稀飯)容易嗆到。
                4. 吞固體的食物會有吞嚥困難情形。
                5. 咬不動較硬或韌的食物。
                6. 常常覺得口渴。
                7. 舌苔變多、變厚。
                8. 出現口臭。
                9. 開始說話口齒不清。
                """)
                
            with bottom_col2:
                # 放入 e.avif
                try:
                    st.image(img_e_b64, width="stretch")
                except:
                    st.error("找不到 e.avif 圖片，請確認檔案已放置於同一資料夾。")
            
            st.markdown('</div>', unsafe_allow_html=True)
    # ---------------------------------------------------------
    # 狀態 C：內容頁 - 口腔衰弱會怎麼樣嗎 (回歸狀態 B 穩定版)
    # ---------------------------------------------------------
    elif st.session_state.sub_page == "口腔衰弱會怎麼樣嗎":
        
        # 1. 返回按鈕
        if st.button("〈 返回", key="back_final_stable"):
            st.session_state.sub_page = "小小首頁"
            st.rerun()

        # 2. 標題與橘色提示區
        st.markdown("<h1 style='text-align: center; color: #2C3E50;'>口腔衰弱會怎麼樣嗎？</h1>", unsafe_allow_html=True)
        st.markdown("""
            <div style='text-align: center; background-color: #E67E22; color: white; padding: 10px; border-radius: 8px; font-weight: bold; margin-bottom: 20px;'>
                中高年齡者口腔衰弱會面臨的困擾是什麼?
            </div>
        """, unsafe_allow_html=True)

        # 3. 左右排版 (模仿狀態 B)
        col_left, col_right = st.columns([1, 1.3], gap="large")

        with col_left:
            # 顯示左側圖片 f.png
            import os
            if os.path.exists("f.png"):
                st.image("f.png", width="stretch")
            else:
                st.warning("⚠️ 找不到 f.png，請確認檔案已放入資料夾")

        with col_right:
            # 五大核心內容 (加上黃底亮點)
            st.markdown("""
            <div style="line-height: 2.3; font-size: 1.2rem; color: #333;">
                <p>1. <span style="background-color: #FFF06C; font-weight: bold; padding: 0 5px;">咬不動</span>，減少咀嚼刺激，會使認知障礙及失智風險增加。</p>
                <p>2. <span style="background-color: #FFF06C; font-weight: bold; padding: 0 5px;">吞不好</span>，容易嗆到，吸入性肺炎發生增加。</p>
                <p>3. <span style="background-color: #FFF06C; font-weight: bold; padding: 0 5px;">吃不下</span>，出現營養不良，肌肉減少，開始衰弱。</p>
                <p>4. <span style="background-color: #FFF06C; font-weight: bold; padding: 0 5px;">口氣差</span>，會缺乏自信，社交活動就減少。</p>
                <p>5. <span style="background-color: #FFF06C; font-weight: bold; padding: 0 5px;">人衰老</span>，生活需要人協助，生活品質下降。</p>
            </div>
            """, unsafe_allow_html=True)

    # ---------------------------------------------------------
    # 狀態 D：內容頁 - 哪些人容易出現口腔衰弱 (精簡純淨版)
    # ---------------------------------------------------------
    elif st.session_state.sub_page == "哪些人容易出現口腔衰弱":
        
        # 1. 頁面淡入效果容器
        st.markdown('<div class="fade-in" style="padding: 20px 50px;">', unsafe_allow_html=True)
        
        # 返回按鈕 (使用 key 確保唯一性)
        if st.button("〈 返回", key="back_to_sub_home_d"):
            st.session_state.sub_page = "小小首頁"
            st.rerun()

        # 2. 標題與子標題區塊
        st.markdown("""
            <div style='text-align: center; margin-bottom: 30px;'>
                <h1 style='color: #2C3E50; margin-bottom: 10px;'>哪些人容易出現口腔衰弱</h1>
                <div style='background-color: #E67E22; color: white; padding: 8px 25px; border-radius: 50px; display: inline-block; font-weight: bold; font-size: 1.1rem;'>
                    哪些人容易出現口腔衰弱
                </div>
            </div>
        """, unsafe_allow_html=True)

        # 3. 左右排版：左文右圖 (對應您的需求)
        col_text, col_img = st.columns([1.2, 1], gap="large")

        with col_text:
            # 依照您提供的完整內文
            st.markdown("""
                <div style="line-height: 2.1; font-size: 1.2rem; color: #333; text-align: justify; background-color: #F8F9FA; padding: 25px; border-radius: 15px; border-left: 5px solid #E67E22;">
                    除了中風、神經功能障礙的病人外，<b>老年人</b>是出現口腔衰弱的高風險族群。
                    但這不代表只有老年人有口腔衰弱的問題，根據研究舌頭肌肉質量的減少於男性 <b>40 歲</b>即開始，
                    而女性甚至早至 <b>30 歲</b>。<br><br>
                    因此若能趁早開始鍛鍊口腔肌肉，即可避免肌肉萎縮，而長者若能多加練習，
                    除了可維持口腔機能，改善進食情況，更可避免吃飯、喝水時嗆到，進而預防吸入性肺炎的可能。
                </div>
            """, unsafe_allow_html=True)

        with col_img:
            # 顯示右側圖片 i.png
            import os
            if os.path.exists("i.png"):
                st.image("i.png", use_container_width=True)
            else:
                # 提示：如果還沒準備好 i.png，可以先用您截圖中的 e.avif 替代測試
                st.warning("⚠️ 請確認資料夾中已有 i.png 檔案")
                if os.path.exists("e.avif"):
                    st.info("暫時以 e.avif 替代顯示中...")
                    st.image("e.avif", use_container_width=True)

        st.markdown('</div>', unsafe_allow_html=True)
        
        # 底部會自動銜接您主程式的 Footer
# ==========================================
# 頁面 3：口腔機能運動訓練 (完整還原版)
# ==========================================
elif selected_page == "口腔機能運動訓練":
    
    # 1. CSS 樣式：定義背景與元件微調
    st.markdown(f"""
        <style>
        /* 強制移除全域背景，確保頁面乾淨 */
        .stApp {{ background-image: none !important; background-color: white !important; }}
        
        /* 移除 Streamlit 預設邊距 */
        .block-container {{ 
            padding: 0rem !important; 
            max-width: 100% !important; 
        }}
        
        /* 中間 z1 背景容器 */
        .z1-bg-area {{
            background-image: url('{imgs['z1']}');
            background-size: cover;
            background-position: center;
            width: 100%;
            padding: 60px 0;
            display: flex;
            justify-content: center;
        }}
        
        /* 內容白底區域：設定為稍微窄一點且置中 */
        .main-content-box {{
            background-color: white;
            padding: 40px;
            display: flex;
            align-items: center;
            gap: 30px;
            max-width: 900px;
            width: 90%;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        }}
        </style>
    """, unsafe_allow_html=True)

    # 2. 頂部 Banner (z3.png) - 加上標題文字
    # 這裡直接用 st.image，因為 z3 本身已經包含文字與背景
    # 1. 頂部 Banner 區塊 (z3 當底，疊加文字)
    # 我們使用一個 div 容器來精確定位標題位置
    st.markdown(f"""
        <div style="
            position: relative; 
            width: 100%; 
            height: 350px; 
            background-image: url('{imgs['z3']}'); 
            background-size: cover; 
            background-position: center;
            display: flex;
            align-items: center;
            justify-content: flex-end; /* 讓文字靠右 */
            padding-right: 10%;
        ">
            <div style="text-align: right; color: #1A5276; font-family: 'Microsoft JhengHei', sans-serif;">
                <h1 style="font-size: 3.5rem; font-weight: 900; margin: 0; letter-spacing: 5px;">口腔衰弱</h1>
                <h1 style="font-size: 2.5rem; font-weight: 800; margin: 0; letter-spacing: 3px;">機能運動訓練</h1>
                <div style="margin-top: 20px;">
                    <p style="font-size: 1.5rem; font-weight: bold; color: #333; margin: 0;">活到老、動到老</p>
                    <p style="font-size: 1.1rem; color: #555; margin: 5px 0 0 0;">針對中高年齡口腔衰弱者提供的口腔機能運動訓練介紹</p>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # 3. 中間核心區 (z1 背景 + z2 圖片 + 文本內容)
    st.markdown(f"""
        <div class="z1-bg-area">
            <div class="main-content-box">
                <div style="flex: 1;">
                    <img src="{imgs['z2']}" style="width: 100%; border-radius: 5px; box-shadow: 2px 2px 10px rgba(0,0,0,0.2);">
                </div>
                <div style="flex: 1.2; padding-left: 20px;">
                    <div style="line-height: 1.8; font-size: 1.05rem; color: #444; text-align: justify; font-family: 'Microsoft JhengHei', sans-serif;">
                        透過自身或照顧者的協助執行口腔肌肉運動，提升口腔、顏面和胸腔以上的肌肉強度，增強唾液腺機能，提升吞嚥相關肌群的協調性，促進口腔和身體健康。<br><br>
                        期許能透過日常多做口腔的肌肉訓練，促進個人的口腔機能健康，進而給予自己一個優質的晚年生活。
                    </div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# ==========================================
# 頁面 4：KTV檢測結果
# ==========================================
elif selected_page == "KTV檢測結果":
    render_ktv_results_page()

# ==========================================
# 頁面 5：舌肌運動檢測結果
# ==========================================
elif selected_page == "舌肌運動檢測結果":

    st.markdown("""
        <style>
        .tongue-banner {
            background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
            padding: 60px 20px;
            text-align: center;
            margin-bottom: 30px;
        }
        .tongue-card {
            background-color: white;
            border-radius: 20px;
            padding: 35px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.08);
            margin: 20px 5%;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div class="tongue-banner">
            <h1 style="margin: 0; color: #2E7D32; font-size: 3rem; font-weight: 900;">
                舌肌運動檢測結果
            </h1>
            <p style="margin-top: 15px; color: #444; font-size: 1.2rem;">
                這裡將顯示舌肌運動檢測數據、分析與訓練建議
            </p>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div class="tongue-card">
            <h2 style="color:#2C3E50;">檢測結果總覽</h2>
            <p style="font-size:1.05rem; color:#555;">
                這個頁面目前先建立版型，之後可放入：
            </p>
            <ul style="font-size:1.05rem; color:#555; line-height:1.9;">
                <li>舌肌運動檢測數值</li>
                <li>運動軌跡分析</li>
                <li>檢測結果判讀</li>
                <li>訓練建議與改善方向</li>
            </ul>
        </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown("""
            <div class="tongue-card">
                <h3 style="color:#2E7D32;">檢測數據區</h3>
                <p style="color:#666;">之後可放量測數值、檢測時間、比較資料。</p>
            </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
            <div class="tongue-card">
                <h3 style="color:#2E7D32;">結果分析區</h3>
                <p style="color:#666;">之後可放分析圖、AI 判讀、訓練建議。</p>
            </div>
        """, unsafe_allow_html=True)
# ==========================================
# 頁尾
# ==========================================
html_footer = f"""
<div style='display: flex; width: 100%; text-align: center; font-family: sans-serif; flex-wrap: wrap;'>
<div style='flex: 1; min-width: 250px; background-color: #D35400; color: white; padding: 40px 20px;'>
<h3 style='font-weight: bold; margin-bottom: 15px; font-size: 22px; color: white;'>聯絡地址</h3>
<p style='font-size: 16px; margin: 0; font-weight: bold; line-height: 1.6;'>口腔健康團隊</p>
</div>
<div style='flex: 1; min-width: 250px; background-color: #E67E22; color: white; padding: 40px 20px;'>
<h3 style='font-weight: bold; margin-bottom: 15px; font-size: 22px; color: white;'>連絡電話</h3>
<p style='font-size: 16px; margin: 0; font-weight: bold; line-height: 1.6;'>陳彥旭教授<br>Email: infchen@gmail.com<br>Tel: 07-3121101#2137</p>
</div>
<div style='flex: 1; min-width: 250px; background-color: #D35400; color: white; padding: 40px 20px;'>
<h3 style='font-weight: bold; margin-bottom: 15px; font-size: 22px; color: white;'>更多口腔照護資訊</h3>
<div style='display: flex; justify-content: center; gap: 20px; margin-top: 10px;'>
<a href="#" style="text-decoration: none; font-size: 35px;">📷</a>
<a href="#" style="text-decoration: none; font-size: 35px;">📘</a>
<a href="#" style="text-decoration: none; font-size: 35px;">▶️</a>
</div>
</div>
</div>
"""
st.markdown(html_footer, unsafe_allow_html=True)