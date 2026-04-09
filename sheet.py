import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import date, datetime

st.set_page_config(page_title="原民族群口腔健康檢查紀錄表", layout="wide")

# ==========================================
# Google Sheets 連線
# ==========================================
@st.cache_resource
def get_worksheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    credentials = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=scopes,
    )
    client = gspread.authorize(credentials)

    spreadsheet = client.open(st.secrets["sheets"]["spreadsheet_name"])
    worksheet = spreadsheet.worksheet(st.secrets["sheets"]["worksheet_name"])
    return worksheet


def safe_join(values):
    if not values:
        return ""
    return "、".join(map(str, values))


def append_dict_to_sheet(data_dict):
    worksheet = get_worksheet()

    headers = worksheet.row_values(1)

    # 如果工作表是空的，先寫入標題列
    if not headers:
        headers = list(data_dict.keys())
        worksheet.append_row(headers, value_input_option="USER_ENTERED")

    # 若有新欄位，自動補到表頭
    missing_headers = [key for key in data_dict.keys() if key not in headers]
    if missing_headers:
        headers.extend(missing_headers)
        worksheet.update("1:1", [headers])

    row = [data_dict.get(header, "") for header in headers]
    worksheet.append_row(row, value_input_option="USER_ENTERED")


st.title("🦷 原民族群口腔健康檢查紀錄表")

st.markdown(
    """
    <style>
    label[data-testid="stWidgetLabel"] div {
        font-size: 20px !important;
        font-weight: bold !important;
    }

    div[data-testid="stMarkdownContainer"] p {
        font-size: 18px !important;
    }

    input, textarea, div[data-baseweb="select"] > div {
        font-size: 18px !important;
    }

    button[data-baseweb="tab"] div {
        font-size: 20px !important;
        font-weight: bold !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "一、基本資料與病史",
    "二、吞嚥與咀嚼評估",
    "三、OFI-8問卷",
    "四、醫師臨床檢查",
    "五、口腔機能檢測"
])

with st.form(key="full_exam_form"):

    # ==========================================
    # Tab 1: 基本資料與病史
    # ==========================================
    with tab1:
        st.header("一般民眾口腔健康檢查紀錄表")
        col1, col2, col3 = st.columns(3)
        with col1:
            patient_id = st.text_input("編號 (收案日期+序號)")
            name = st.text_input("姓名")
        with col2:
            irb = st.checkbox("IRB同意書 已完成")
            gender = st.radio("性別", ["男", "女"], horizontal=True)
        with col3:
            dob = st.date_input("生日", min_value=date(1900, 1, 1))
            comm = st.radio("溝通能力", ["正常", "可簡單溝通", "理解能力差", "無語言能力"])

        st.subheader("慢性病史")
        chronic_diseases = st.multiselect(
            "請選擇慢性病 (可多選)",
            ["糖尿病", "高血壓", "心血管疾病", "癌症", "高血脂", "帕金森氏症", "中風", "失智", "慢性阻塞性肺疾病", "精神疾病相關", "胃食道逆流", "消化道潰瘍性疾病", "睡眠呼吸中止", "無"]
        )
        other_chronic = st.text_input("其他慢性病")

        st.subheader("日常生活習慣")
        c1, c2, c3 = st.columns(3)
        smoke = c1.radio("1. 抽菸", ["無", "有"])
        smoke_freq = c1.text_input("抽菸頻率") if smoke == "有" else ""

        alcohol = c2.radio("2. 喝酒", ["無", "有"])
        alcohol_freq = c2.text_input("喝酒頻率") if alcohol == "有" else ""

        betel = c3.radio("3. 嚼檳榔", ["無", "有"])
        betel_freq = c3.text_input("嚼檳榔頻率") if betel == "有" else ""

        c4, c5, c6 = st.columns(3)
        brush = c4.radio("4. 刷牙", ["無", "有"])
        brush_times = c4.number_input("一天刷幾次", min_value=1, value=1) if brush == "有" else 0

        toothpaste = c5.radio("5. 使用牙膏", ["無", "有"])
        anti_bact = c6.radio("6. 牙膏是否含抗菌處方", ["無", "有"])

        st.subheader("嗆咳與住院經驗")
        choke_freq = st.radio("最近3個月內嗆咳情形?", ["經常嗆咳", "偶爾嗆咳", "少有嗆咳", "無"], horizontal=True)
        choke_type = st.radio("會引致嗆咳食物類型?", ["固體", "液體", "固液體都會", "無"], horizontal=True)

        hosp = st.radio("過去一年曾有住院經驗", ["無", "有"])
        hosp_times = st.number_input("住院幾次", min_value=1, value=1) if hosp == "有" else 0
        hosp_reason = st.text_input("住院原因") if hosp == "有" else ""

    # ==========================================
    # Tab 2: 吞嚥能力篩查評估 (EAT-10) & 咀嚼能力
    # ==========================================
    with tab2:
        st.header("吞嚥能力篩查評估 (EAT-10)")
        st.markdown("**請評估您的狀態，每題分數: 0 (沒有) – 4 (嚴重)**")

        eat10_questions = [
            "1. 我的吞嚥問題令我體重下降", "2. 我的吞嚥問題影響了我外出用膳",
            "3. 需要比較費勁才能吞嚥液體", "4. 需要比較費勁才能吞嚥固體",
            "5. 需要比較費勁才能吞嚥藥丸", "6. 吞嚥時感到痛楚",
            "7. 吞嚥問題影響了我的進食樂趣", "8. 吞嚥時感到食物黏在咽喉",
            "9. 進食時我會咳嗽", "10. 我對吞嚥感到有壓力"
        ]

        eat10_scores = {}
        for idx, q in enumerate(eat10_questions, start=1):
            eat10_scores[f"EAT10_{idx}"] = st.slider(q, 0, 4, 0)

        st.divider()
        st.header("咀嚼能力評估 (6個月內自評)")
        diet_type = st.radio("您的飲食習慣為？", ["葷食", "素食"], horizontal=True)

        chew_options = ["容易吃", "有些吃力", "不能吃"]
        chew_answers = {}

        if diet_type == "葷食":
            meat_items = [
                "水煮花枝", "炒花生", "炸雞", "滷豬耳朵", "水煮玉米(整枝)", "芭樂(切片處理)",
                "蘋果/梨子(切片處理)", "烤魷魚/雞胗", "甘蔗(非榨汁)", "小黃瓜(切片處理)/敏豆",
                "竹筍/花椰菜", "柳丁(切片處理)", "楊桃/蓮霧(切片處理)", "煮熟的紅蘿蔔/煮熟的白蘿蔔"
            ]
            for item in meat_items:
                chew_answers[f"咀嚼_{item}"] = st.radio(f"{item}", chew_options, horizontal=True, key=f"meat_{item}")
        else:
            veg_items = [
                "硬豆干(蒟蒻/鐵蛋)", "炒花生(堅果)", "芭樂(整顆)", "炸蒟蒻", "水煮玉米(整枝)",
                "蘋果/梨子(切片處理)", "香菇頭", "甘蔗(非榨汁)", "小黃瓜(切片處理)/敏豆", "竹筍/花椰菜"
            ]
            for item in veg_items:
                chew_answers[f"咀嚼_{item}"] = st.radio(f"{item}", chew_options, horizontal=True, key=f"veg_{item}")

    # ==========================================
    # Tab 3: OFI-8問卷
    # ==========================================
    with tab3:
        st.header("OFI-8 問卷")
        ofi_questions = [
            "與6個月前相比，您在吃堅硬的食物時是否有困難？",
            "您最近是否有被茶或湯噎住了？",
            "使用假牙？",
            "您是否經常感到口乾舌燥？",
            "與去年相比，您外出的次數是否減少了？",
            "可以吃魷魚乾，醃蘿蔔(乾芋頭)等硬的食物嗎?",
            "您每天刷幾次牙？(<3次/天為否)",
            "您至少每年都會去一次牙醫診所嗎?"
        ]

        ofi_answers = {}
        for i, q in enumerate(ofi_questions, start=1):
            ofi_answers[f"OFI_{i}"] = st.radio(f"{i}. {q}", ["是", "否"], horizontal=True, key=f"ofi_{i}")

    # ==========================================
    # Tab 4: 醫師臨床檢查
    # ==========================================
    with tab4:
        st.header("醫師臨床檢查")
        col_d1, col_d2 = st.columns(2)
        exam_date = col_d1.date_input("檢查日期", date.today())
        dentist_name = col_d2.text_input("檢查醫師")

        st.subheader("一、口腔衛生")
        oral_hygiene = st.radio("衛生狀況", ["優良", "良好", "尚可", "待加強"], horizontal=True)
        brushing_doer = st.radio("潔牙工作", ["很少做", "自己來", "照護者幫忙", "其他"], horizontal=True)

        st.subheader("二、牙齒狀況")
        tooth_count = st.number_input("牙齒顆數 (不包含活動假牙)", min_value=0, max_value=32)
        dentures = st.multiselect("活動假牙", ["上", "下"])
        uncooperative = st.checkbox("無法配合檢查")
        need_caries_tx = st.checkbox("需治療齲齒 (蛀牙)")

        st.markdown("*註：詳細牙位圖 (1-8象限) 建議配合紙本或專業牙科牙位點選套件紀錄。*")

        st.subheader("三、牙周狀況")
        periodontal = st.multiselect("狀況 (可多選)", ["良好", "牙齦炎", "牙齦腫脹", "牙結石，需定期洗牙", "牙周病，需進一步診治"])

        st.subheader("四、其他狀況")
        other_oral = st.multiselect("其他 (可多選)", ["咬合不正", "口腔潰瘍", "有阻生齒", "口腔黏膜異常，需進一步診治"])

        st.subheader("五、建議事項")
        suggestions = st.multiselect("建議 (可多選)", ["繼續維持口腔清潔", "定期至牙醫院所洗牙", "需至牙醫院所診治 (蛀牙/牙周病/拔牙)", "口腔問題複雜，建議至醫學中心診治"])
        other_suggestions = st.text_input("其他建議")

    # ==========================================
    # Tab 5: 口腔健康機能檢測
    # ==========================================
    with tab5:
        st.header("口腔機能檢測紀錄")

        st.subheader("1. 舌口唇運動機能")
        st.write("每音節快速重複唸5秒 (異常值：<6次/秒)")
        col_da, col_ba, col_ga = st.columns(3)
        da_val = col_da.number_input("DA (搭) 次/秒", min_value=0.0)
        ba_val = col_ba.number_input("BA (八) 次/秒", min_value=0.0)
        ga_val = col_ga.number_input("GA (尬) 次/秒", min_value=0.0)

        st.subheader("2. 口腔乾燥 (舌底含紗布1分鐘)")
        st.write("異常值：≦0.1 ml/min")
        col_w1, col_w2, col_w3 = st.columns(3)
        total_weight = col_w1.number_input("總重量 (g)", min_value=0.0)
        cup_gauze_weight = col_w2.number_input("杯+紗布重量 (g)", min_value=0.0)
        saliva_vol = col_w3.number_input("實際唾液量 (ml)", min_value=0.0)

        st.subheader("3. 握力、舌壓、吞嚥壓")
        st.write("握力：正坐，慣用手呈90度握緊2-3秒後放手 | 舌壓異常值：<30 kPa")

        def measure_table(label):
            st.write(f"**{label}**")
            c1, c2, c3, c4 = st.columns(4)
            v1 = c1.number_input(f"{label} 第一次", min_value=0.0, key=f"{label}_1")
            v2 = c2.number_input(f"{label} 第二次", min_value=0.0, key=f"{label}_2")
            v3 = c3.number_input(f"{label} 第三次", min_value=0.0, key=f"{label}_3")
            avg = (v1 + v2 + v3) / 3 if (v1 or v2 or v3) else 0
            c4.metric(label="平均", value=f"{avg:.2f}")
            return v1, v2, v3, avg

        grip_1, grip_2, grip_3, grip_avg = measure_table("握力")
        tongue_1, tongue_2, tongue_3, tongue_avg = measure_table("舌壓")
        swallow_1, swallow_2, swallow_3, swallow_avg = measure_table("吞嚥壓")

        st.subheader("4. 吞嚥功能與口腔衛生")
        rsst = st.number_input("RSST (30秒內共吞口水幾次)", min_value=0)
        st.write("異常值：<3次/30秒")

        st.markdown("**口腔衛生 (舌苔)**")
        st.write("異常值：舌苔 ≧ 50%。分9個區域，0=無，1=薄，2=厚")
        tongue_coating_scores = []
        tongue_areas = st.columns(9)
        for i in range(9):
            score = tongue_areas[i].selectbox(f"區{i+1}", [0, 1, 2], key=f"tongue_{i}")
            tongue_coating_scores.append(score)

        st.subheader("5. 咬合力與咀嚼功能")
        teeth_less_than_20 = st.checkbox("牙齒 < 20顆 (由牙醫師檢測)")
        xylitol_done = st.checkbox("Xylitol口香糖 說明時已完成")
        chewing_abnormal = st.checkbox("咀嚼功能：不能咀嚼 > 4項")
        basic_info_checked = st.checkbox("基本資料已詢問")

    # ==========================================
    # 送出按鈕
    # ==========================================
    st.divider()
    submit_button = st.form_submit_button(label="💾 儲存並送出此份紀錄表")

    if submit_button:
        if not patient_id.strip():
            st.error("請輸入編號")
        elif not name.strip():
            st.error("請輸入姓名")
        else:
            try:
                form_data = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "patient_id": patient_id,
                    "name": name,
                    "irb": irb,
                    "gender": gender,
                    "dob": str(dob),
                    "comm": comm,
                    "chronic_diseases": safe_join(chronic_diseases),
                    "other_chronic": other_chronic,
                    "smoke": smoke,
                    "smoke_freq": smoke_freq,
                    "alcohol": alcohol,
                    "alcohol_freq": alcohol_freq,
                    "betel": betel,
                    "betel_freq": betel_freq,
                    "brush": brush,
                    "brush_times": brush_times,
                    "toothpaste": toothpaste,
                    "anti_bact": anti_bact,
                    "choke_freq": choke_freq,
                    "choke_type": choke_type,
                    "hosp": hosp,
                    "hosp_times": hosp_times,
                    "hosp_reason": hosp_reason,
                    "diet_type": diet_type,
                    "exam_date": str(exam_date),
                    "dentist_name": dentist_name,
                    "oral_hygiene": oral_hygiene,
                    "brushing_doer": brushing_doer,
                    "tooth_count": tooth_count,
                    "dentures": safe_join(dentures),
                    "uncooperative": uncooperative,
                    "need_caries_tx": need_caries_tx,
                    "periodontal": safe_join(periodontal),
                    "other_oral": safe_join(other_oral),
                    "suggestions": safe_join(suggestions),
                    "other_suggestions": other_suggestions,
                    "da_val": da_val,
                    "ba_val": ba_val,
                    "ga_val": ga_val,
                    "total_weight": total_weight,
                    "cup_gauze_weight": cup_gauze_weight,
                    "saliva_vol": saliva_vol,
                    "grip_1": grip_1,
                    "grip_2": grip_2,
                    "grip_3": grip_3,
                    "grip_avg": grip_avg,
                    "tongue_1": tongue_1,
                    "tongue_2": tongue_2,
                    "tongue_3": tongue_3,
                    "tongue_avg": tongue_avg,
                    "swallow_1": swallow_1,
                    "swallow_2": swallow_2,
                    "swallow_3": swallow_3,
                    "swallow_avg": swallow_avg,
                    "rsst": rsst,
                    "tongue_coating_scores": ",".join(map(str, tongue_coating_scores)),
                    "teeth_less_than_20": teeth_less_than_20,
                    "xylitol_done": xylitol_done,
                    "chewing_abnormal": chewing_abnormal,
                    "basic_info_checked": basic_info_checked,
                }

                form_data.update(eat10_scores)
                form_data.update(chew_answers)
                form_data.update(ofi_answers)

                append_dict_to_sheet(form_data)

                st.success(f"✅ 已成功儲存病患 {name} ({patient_id}) 的完整紀錄表！")

            except Exception as e:
                st.error(f"❌ 儲存失敗：{e}")