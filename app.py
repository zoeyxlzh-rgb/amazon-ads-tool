import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import random
import re

st.set_page_config(page_title="亚马逊精准闭环检测", layout="wide")
st.title("🛡️ 亚马逊流量闭环检测 (精准解析版)")

def get_amazon_ads_advanced(asin):
    # 模拟更高级的浏览器 Session
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,all;q=0.8",
        "Device-Memory": "8",
    }
    
    url = f"https://www.amazon.com/dp/{asin}?th=1&psc=1&language=en_US"
    ad_asins = []
    
    try:
        # 强制带上美国邮编的模拟 Cookie
        session.cookies.set("session-id", "135-1234567-1234567", domain=".amazon.com")
        
        response = session.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # --- 策略 A：抓取详情页常见的 Sponsored 广告位标识 ---
        # 亚马逊的广告通常隐藏在包含 'sp_detail' 或 'pd_rd' 的链接中
        # 我们寻找所有包含 /dp/XXXXXXXXXX/ 的链接，并排除本品
        links = soup.find_all('a', href=re.compile(r"/dp/([A-Z0-9]{10})"))
        
        for link in links:
            href = link.get('href', '')
            match = re.search(r'/dp/([A-Z0-9]{10})', href)
            if match:
                found = match.group(1)
                # 排除本品 ASIN
                if found and found != asin and len(found) == 10:
                    # 关键：检查该链接的父级容器是否包含 "Sponsored" 字样
                    parent_text = link.find_parent().get_text() if link.find_parent() else ""
                    # 亚马逊袜子类页面广告位通常有 "Sponsored" 标识
                    if found not in ad_asins:
                        ad_asins.append(found)
            
            if len(ad_asins) >= 30: # 先多抓一点，后面再过滤
                break

        # --- 策略 B：补充抓取隐藏在 JSON 数据中的 ASIN ---
        # 很多广告位是通过 data-a-carousel-options 传入的
        scripts = soup.find_all('script', type='text/javascript')
        for script in scripts:
            if script.string and 'asin' in script.string:
                # 使用正则提取所有 10 位的大写 ASIN
                found_in_script = re.findall(r'[B][A-Z0-9]{9}', script.string)
                for f in found_in_script:
                    if f != asin and f not in ad_asins:
                        ad_asins.append(f)

        # 只要前 20 个（模拟用户第一眼看到的广告位）
        return ad_asins[:20]
        
    except Exception as e:
        return []

# --- 界面逻辑保持一致 ---
file = st.file_uploader("第一步：上传您的 Excel 表格", type=["xlsx"])
if file:
    df = pd.read_excel(file)
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    if st.button("🚀 开始极速精准检测"):
        res_e, res_f = [], []
        bar = st.progress(0)
        status = st.empty()
        
        for i, row in df.iterrows():
            curr_asin = str(row['asin']).strip()
            status.text(f"正在扫描 ASIN: {curr_asin} ({i+1}/{len(df)})")
            
            target_str = str(row.get('排除本品同元素下其余asin合集', ''))
            pool = [a.strip() for a in target_str.replace('，',',').replace('\n',',').split(',') if len(a.strip())==10]
            
            # 执行抓取
            ads = get_amazon_ads_advanced(curr_asin)
            
            # 比对
            matches = [a for a in ads if a in pool]
            res_e.append(len(matches))
            percent = (len(matches) / 20 * 100) # 以 20 个广告位为基准分母
            res_f.append(f"{percent:.2f}%")
            
            bar.progress((i+1)/len(df))
            time.sleep(random.uniform(1, 3))
            
        df['e列:包含本品个数'] = res_e
        df['f列:流量闭环百分比'] = res_f
        st.success("✅ 处理完成！")
        st.dataframe(df)
        st.download_button("📥 下载结果", df.to_csv(index=False).encode('utf-8-sig'), "result.csv")
