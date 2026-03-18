import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import random

st.set_page_config(page_title="亚马逊广告位检测", layout="wide")
st.title("🛡️ 亚马逊流量闭环检测工具")

def get_ads(asin):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    url = f"https://www.amazon.com/dp/{asin}?language=en_US"
    try:
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.find_all(attrs={"data-asin": True})
        found = [i['data-asin'] for i in items if len(i['data-asin']) == 10 and i['data-asin'] != asin]
        return list(set(found))[:20]
    except: return []

file = st.file_uploader("上传 Excel 表格", type=["xlsx"])
if file:
    df = pd.read_excel(file)
    df.columns = [str(c).strip().lower() for c in df.columns]
    if st.button("🚀 开始检测"):
        res_e, res_f = [], []
        bar = st.progress(0)
        for i, row in df.iterrows():
            asin = str(row['asin']).strip()
            target_str = str(row.get('排除本品同元素下其余asin合集', ''))
            pool = [a.strip() for a in target_str.replace('，',',').replace('\n',',').split(',') if len(a.strip())==10]
            ads = get_ads(asin)
            matches = [a for a in ads if a in pool]
            res_e.append(len(matches))
            res_f.append(f"{(len(matches)/len(ads)*100 if ads else 0):.2f}%")
            bar.progress((i+1)/len(df))
            time.sleep(1)
        df['e列:包含本品个数'] = res_e
        df['f列:流量闭环百分比'] = res_f
        st.dataframe(df)
        st.download_button("📥 下载结果", df.to_csv(index=False).encode('utf-8-sig'), "result.csv")
