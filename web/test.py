import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

@st.cache_resource
def get_sheet():
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    client = gspread.authorize(creds)
    sheet = client.open("問卷回覆資料").sheet1
    return sheet

if st.button("測試寫入"):
    sheet = get_sheet()
    sheet.append_row(["測試", "成功"])
    st.success("寫入成功")