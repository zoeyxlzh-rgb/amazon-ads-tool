import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time
import random

# --- 页面配置 ---
st.set_page_config(page_title="亚马逊流量闭环检测", layout="wide")
st.title("🛡️ 亚马逊广告位流量闭环检测工具")

st.markdown("""
### 💡 使用说明
1. **表格要求**：请确保表格包含以下四列（顺序不限）：`asin`, `元素`, `元素下asin个数`, `排除本品同元素下其余asin合集`。
2. **闭环定义**：检测详情页前20个广告位中，是否包含“排除本品”后的其他同元素产品。
""")

def get_amazon_ads(asin):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    # 模拟真实浏览器
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = None
    try:
        # 在 Conda 环境下，chromium 和 chromedriver 会自动进入 PATH
        # 我们不需要指定路径，直接启动即可
        driver = webdriver.Chrome(options=options)
        
        url = f"https://www.amazon.com/dp/{asin}?language=en_US&th=1&psc=1"
        driver.get(url)
        
        # 你的核心逻辑：等待加载
        time.sleep(random.uniform(6, 10))
        driver.execute_script("window.scrollTo(0, 1000);")
        time.sleep(2)

        elements = driver.find_elements(By.XPATH, "//*[@data-asin]")
        ad_asins = []
        for el in elements:
            val = el.get_attribute("data-asin").strip()
            if val and val != asin and len(val) == 10:
                if val not in ad_asins:
                    ad_asins.append(val)
            if len(ad_asins) >= 20: break
        return ad_asins
    except Exception as e:
        st.error(f"捕获到异常: {e}")
        return []
    finally:
        if driver:
            driver.quit()

# --- 1. 上传文件 ---
file = st.file_uploader("上传 Excel 表格", type=["xlsx"])

if file:
    df = pd.read_excel(file)
    
    # 自动处理列名：转为小写并去除空格，防止 KeyError
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    # 检查必要的列是否存在
    required_cols = ['asin', '排除本品同元素下其余asin合集']
    missing = [c for c in required_cols if c not in df.columns]
    
    if missing:
        st.error(f"表格中缺少必要的列: {missing}。请检查表头名称。")
    else:
        st.write("✅ 表格读取成功，预览前5行：", df.head())
        
        if st.button("🚀 开始自动化检测"):
            results_count = []
            results_percent = []
            results_found_asins = [] # 记录抓到了哪些
            
            progress_text = st.empty()
            bar = st.progress(0)
            
            for i, row in df.iterrows():
                current_asin = str(row['asin']).strip()
                # 获取对比池：将D列字符串转为列表
                target_str = str(row['排除本品同元素下其余asin合集'])
                # 支持中文逗号、英文逗号和换行符分割
                target_pool = target_str.replace('，', ',').replace('\n', ',').split(',')
                target_pool = [a.strip() for a in target_pool if len(a.strip()) == 10]
                
                progress_text.text(f"正在分析 ({i+1}/{len(df)}): {current_asin}")
                
                # 执行抓取
                scraped = get_amazon_ads(current_asin)
                
                # 比对逻辑
                matches = [a for a in scraped if a in target_pool]
                match_count = len(matches)
                
                # 计算百分比：D列产品在广告位中出现的比例（按你要求的公式）
                # 注意：你要求的公式是 (D列个数 / 详情页包含的个数)，这里做了安全处理防止除以0
                percent = (match_count / len(scraped)) * 100 if len(scraped) > 0 else 0
                
                results_count.append(match_count)
                results_percent.append(f"{percent:.2f}%")
                results_found_asins.append(", ".join(scraped))
                
                bar.progress((i + 1) / len(df))
            
            # 结果输出到原表
            df['E列:包含本品个数'] = results_count
            df['F列:流量闭环百分比'] = results_percent
            df['抓取到的前20个广告位ASIN'] = results_found_asins
            
            st.success("✨ 处理完成！")
            st.dataframe(df)
            
            # 提供下载
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下载检测结果", csv, "amazon_analysis_result.csv", "text/csv")
