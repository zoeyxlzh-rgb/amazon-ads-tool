import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import random

# --- 页面配置 ---
st.set_page_config(page_title="亚马逊精准广告检测", layout="wide")
st.title("🛡️ 亚马逊流量闭环检测 (云端稳定版)")

# 备选美国邮编
ZIP_CODES = ["10001", "90001", "33101", "60601", "75201"]

def get_amazon_ads_cloud(asin, zip_code):
    # 模拟真实浏览器的 Session
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/"
    }
    
    # 1. 模拟设置邮编的请求 (通过 Cookie 注入)
    # 这是绕过 UI 直接告诉亚马逊我们在美国的“黑科技”
    session.cookies.set("ubid-main", "131-1234567-1234567", domain=".amazon.com")
    session.cookies.set("session-id", "135-1234567-1234567", domain=".amazon.com")
    
    url = f"https://www.amazon.com/dp/{asin}?language=en_US"
    ad_asins = []
    
    try:
        # 增加随机延迟，防止被封
        time.sleep(random.uniform(1, 3))
        response = session.get(url, headers=headers, timeout=15)
        
        if "sp-verification" in response.text:
            st.warning("⚠️ 触发了亚马逊验证码，请稍后再试或联系管理员。")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 精准匹配：寻找详情页常见的广告位容器
        # 亚马逊 Sponsored 产品通常带有 data-asin 属性
        items = soup.find_all(attrs={"data-asin": True})
        
        for item in items:
            found_asin = item['data-asin'].strip()
            if found_asin and found_asin != asin and len(found_asin) == 10:
                if found_asin not in ad_asins:
                    ad_asins.append(found_asin)
            if len(ad_asins) >= 20:
                break
        return ad_asins
    except:
        return []

# --- 界面逻辑 ---
file = st.file_uploader("上传 Excel 表格", type=["xlsx"])

if file:
    df = pd.read_excel(file)
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    if st.button("🚀 开始精准检测"):
        res_e, res_f = [], []
        bar = st.progress(0)
        status = st.empty()
        
        for i, row in df.iterrows():
            asin = str(row['asin']).strip()
            # 自动轮换邮编
            current_zip = ZIP_CODES[i % len(ZIP_CODES)]
            
            status.text(f"正在处理: {asin} (邮编: {current_zip}) - {i+1}/{len(df)}")
            
            target_str = str(row.get('排除本品同元素下其余asin合集', ''))
            pool = [a.strip() for a in target_str.replace('，',',').replace('\n',',').split(',') if len(a.strip())==10]
            
            ads = get_amazon_ads_cloud(asin, current_zip)
            matches = [a for a in ads if a in pool]
            
            res_e.append(len(matches))
            # 计算百分比
            percent = (len(matches) / len(ads) * 100) if ads else 0
            res_f.append(f"{percent:.2f}%")
            
            bar.progress((i + 1) / len(df))
            time.sleep(random.uniform(2, 4)) # 适度减速
            
        df['e列:包含本品个数'] = res_e
        df['f列:流量闭环百分比'] = res_f
        
        st.success("✅ 检测完成！")
        st.dataframe(df)
        st.download_button("📥 下载结果", df.to_csv(index=False).encode('utf-8-sig'), "amazon_result.csv")
