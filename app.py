import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import random

# --- 页面配置 ---
st.set_page_config(page_title="亚马逊精准广告检测", layout="wide")
st.title("🛡️ 亚马逊流量闭环检测 (Selenium 精准版)")
st.sidebar.info("提示：此版本使用真实浏览器模拟，处理速度较慢（约15-20秒/ASIN），请耐心等待。")

# 备选美国邮编池，用于轮换
ZIP_CODES = ["10001", "90001", "33101", "60601", "75201"]

# --- 初始化云端浏览器 (这是最容易报错的地方，已做特殊适配) ---
def init_driver():
    options = Options()
    options.add_argument("--headless")  # 必须开启无头模式
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    
    # 自动下载适合 Linux 环境的驱动
    svc = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=svc, options=options)

# --- 核心逻辑：设置邮编 (确保广告位准确) ---
def set_zip_code(driver, zip_code):
    try:
        # 1. 点击左上角的配送位置
        nav_address = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "nav-global-location-slot"))
        )
        nav_address.click()
        time.sleep(2)

        # 2. 输入邮编
        zip_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "GLUXZipUpdateInput"))
        )
        zip_input.clear()
        zip_input.send_keys(zip_code)
        time.sleep(1)

        # 3. 点击 Apply
        driver.find_element(By.ID, "GLUXZipUpdate").click()
        time.sleep(2)
        
        # 4. 有时需要点击最后的 Done/Continue 按钮才能刷新页面
        try:
            driver.find_element(By.XPATH, "//button[@name='glowDoneButton']").click()
        except: pass
        
        time.sleep(3) # 等待页面刷新
        st.sidebar.success(f"已成功切换邮编至: {zip_code}")
    except:
        st.sidebar.warning(f"邮编 {zip_code} 设置失败，将使用默认定位抓取。")

# --- 核心逻辑：精准抓取广告位 (等待加载版) ---
def get_amazon_ads_precise(driver, asin):
    url = f"https://www.amazon.com/dp/{asin}?language=en_US"
    ad_asins = []
    
    try:
        driver.get(url)
        # --- 关键：等待页面上的 Sponsored 广告容器加载出来 ---
        # 亚马逊详情页广告位通常在 'celwidget' 或特定的 carousel 里
        st.write(f"正在加载页面: {asin}，请稍候...")
        
        # 显式等待：直到页面出现 data-asin 属性的元素（上限 15 秒）
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//*[@data-asin]"))
        )
        
        # 额外随机等待，确保 JavaScript 完全渲染
        time.sleep(random.uniform(5, 8))
        
        # 滚屏操作，触发懒加载的广告位
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
        time.sleep(2)
        
        # --- 抓取逻辑 (使用你的本地验证通过的准确 XPath/属性) ---
        elements = driver.find_elements(By.XPATH, "//*[@data-asin]")
        
        for el in elements:
            found_asin = el.get_attribute("data-asin").strip()
            # 排除本品、空值、非法 ASIN
            if found_asin and found_asin != asin and len(found_asin) == 10:
                if found_asin not in ad_asins:
                    ad_asins.append(found_asin)
            if len(ad_asins) >= 20: # 严格取前20个
                break
        return ad_asins
    except Exception as e:
        st.error(f"ASIN {asin} 抓取超时或失败: {str(e)[:100]}")
        return []

# --- 网页界面 ---
file = st.file_uploader("第一步：上传您的 Excel 表格", type=["xlsx"])

if file:
    df = pd.read_excel(file)
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    if st.button("🚀 开始精准检测"):
        # 初始化浏览器 (整个过程只初始化一次)
        status = st.empty()
        status.info("正在初始化云端浏览器环境，大约需要 30 秒...")
        driver = init_driver()
        
        # 初始化首个邮编
        current_zip = random.choice(ZIP_CODES)
        set_zip_code(driver, current_zip)
        
        results_e, results_f = [], []
        bar = st.progress(0)
        
        try:
            for i, row in df.iterrows():
                # 轮换邮编：每分析 5 个 ASIN 换一个邮编
                if i > 0 and i % 5 == 0:
                    new_zip = random.choice([z for z in ZIP_CODES if z != current_zip])
                    status.info(f"正在轮换邮编至: {new_zip}...")
                    set_zip_code(driver, new_zip)
                    current_zip = new_zip
                    
                asin = str(row['asin']).strip()
                target_str = str(row.get('排除本品同元素下其余asin合集', ''))
                target_pool = [a.strip() for a in target_str.replace('，',',').replace('\n',',').split(',') if len(a.strip())==10]
                
                status.text(f"正在精准分析 ({i+1}/{len(df)}): {asin}")
                
                # 执行精准抓取
                ads = get_amazon_ads_precise(driver, asin)
                
                # 比对逻辑
                matches = [a for a in ads if a in target_pool]
                count = len(matches)
                # 计算百分比
                percent = (count / len(ads) * 100) if len(ads) > 0 else 0
                
                results_e.append(count)
                results_f.append(f"{percent:.2f}%")
                
                bar.progress((i + 1) / len(df))
                # ASIN 之间的随机停顿
                time.sleep(random.uniform(3, 5))
                
            df['e列:包含本品个数'] = results_e
            df['f列:流量闭环百分比'] = results_f
            
            st.success("✅ 检测完成！")
            st.dataframe(df)
            
            # 提供下载
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下载分析结果", csv, "amazon_result.csv", "text/csv")
            
        except Exception as ce:
            st.error(f"运行过程中发生严重错误: {str(ce)}")
        finally:
            driver.quit() # 确保浏览器最终被关闭
