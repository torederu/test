import time
import pandas as pd
import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import requests
import html
from bs4 import BeautifulSoup
import re
import threading

def update_progress(status, bar, message, percent):
    if status:
        status.write(message)
    if bar:
        bar.progress(percent)

def scrape_function_health(user_email, user_pass, status=None):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920x1080")
    try:
        service = Service(ChromeDriverManager().install())
    except Exception:
        service = Service("/usr/bin/chromedriver")
        options.add_argument("--binary=/usr/bin/chromium")
    driver = None
    data = []
    def update_status(message):
        status.markdown(
            f'<div style="margin-left:2.0em; font-size:1rem; font-weight:400; line-height:1.2; margin-top:-0.6em; margin-bottom:0.1em;">⤷ {message}</div>',
            unsafe_allow_html=True
        )
    try:
        update_status("Launching remote browser")
        driver = webdriver.Chrome(service=service, options=options)
        time.sleep(1)
        update_status("Accessing Function Health")
        driver.get("https://my.functionhealth.com/")
        driver.maximize_window()
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "email"))
        ).send_keys(user_email)
        update_status("Logging into Function Health")
        driver.find_element(By.ID, "password").send_keys(user_pass + Keys.RETURN)
        time.sleep(5)
        if "login" in driver.current_url.lower():
            raise ValueError("Login failed — please check your Function Health credentials.")
        update_status("Importing biomarkers")
        driver.get("https://my.functionhealth.com/biomarkers")
        WebDriverWait(driver, 12).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[class^='biomarkerResultRow-styled__BiomarkerName']"))
        )
        everything = driver.find_elements(By.XPATH, "//h4 | //div[contains(@class, 'biomarkerResult-styled__ResultContainer')]")
        current_category = None
        total = len(everything)
        for i, el in enumerate(everything):
            tag = el.tag_name
            if tag == "h4":
                current_category = el.text.strip()
            elif tag == "div":
                try:
                    name = el.find_element(By.CSS_SELECTOR, "[class^='biomarkerResultRow-styled__BiomarkerName']").text.strip()
                    status_text = value = units = ""
                    values = el.find_elements(By.CSS_SELECTOR, "[class*='biomarkerChart-styled__ResultValue']")
                    texts = [v.text.strip() for v in values]
                    if len(texts) == 3:
                        status_text, value, units = texts
                    elif len(texts) == 2:
                        status_text, value = texts
                    elif len(texts) == 1:
                        value = texts[0]
                    try:
                        unit_el = el.find_element(By.CSS_SELECTOR, "[class^='biomarkerChart-styled__UnitValue']")
                        units = unit_el.text.strip()
                    except:
                        pass
                    data.append({
                        "category": current_category,
                        "name": name,
                        "status": status_text,
                        "value": value,
                        "units": units
                    })
                except Exception:
                    continue
        update_status("Closing remote browser")
        driver.quit()
        time.sleep(1)
        update_status("Cleaning data")
        time.sleep(1)
    except Exception as e:
        if driver:
            driver.quit()
        raise e
    return pd.DataFrame(data)

def scrape_thorne_gut_report(user_email, user_pass, status=None):
    import streamlit as st
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920x1080")
    try:
        service = Service(ChromeDriverManager().install())
    except Exception:
        service = Service("/usr/bin/chromedriver")
        options.add_argument("--binary=/usr/bin/chromium")
    driver = None
    def update_status(message):
        status.markdown(
            f'<div style="margin-left:2.0em; font-size:1rem; font-weight:400; line-height:1.2; margin-top:-0.6em; margin-bottom:0.1em;">⤷ {message}</div>',
            unsafe_allow_html=True
        )
    try:
        update_status("Launching remote browser")
        driver = webdriver.Chrome(service=service, options=options)
        driver.get("https://www.thorne.com/login")
        wait = WebDriverWait(driver, 15)
        update_status("Logging into Thorne")
        wait.until(EC.element_to_be_clickable((By.NAME, "email"))).send_keys(user_email)
        wait.until(EC.element_to_be_clickable((By.NAME, "password"))).send_keys(user_pass + Keys.RETURN)
        try:
            wait.until(lambda d: "/login" not in d.current_url)
        except Exception:
            raise ValueError("Login failed — please check your Thorne credentials.")
        time.sleep(0.5)
        update_status("Navigating to Gut Health test")
        driver.get("https://www.thorne.com/account/tests")
        wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "View Results"))).click()
        wait.until(EC.url_contains("/account/tests/GUTHEALTH/"))
        update_status("Extracting session data")
        for popup_text in ["×", "Got it"]:
            try:
                wait.until(EC.element_to_be_clickable((By.XPATH, f"//button[contains(., '{popup_text}')]"))).click()
            except:
                pass
        cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
        update_status("Closing remote browser")
        time.sleep(1)
        driver.quit()
        resp = requests.get(
            "https://www.thorne.com/account/data/tests/reports/GUTHEALTH/details",
            cookies=cookies,
            headers={"Accept": "application/json"}
        )
        update_status("Cleaning data")
        time.sleep(1)
        resp.raise_for_status()
        report = (resp.json() or [{}])[0]
    except Exception as e:
        if driver:
            driver.quit()
        raise e
    rows = []
    for sec in report.get("bodySections", []):
        results = sec.get("results") or []
        if not results:
            continue
        insp = next(
            (s for s in report["bodySections"]
             if s.get("anchorId") == sec.get("anchorId", "").replace("_markers", "_insights")),
            {}
        )
        insights = insp.get("content", "").strip()
        first = results[0]
        rows.append({
            "section":       sec.get("title", ""),
            "item":          None,
            "score":         first.get("valueNumeric", first.get("value")),
            "risk":          first.get("riskClassification", ""),
            "optimal_range": first.get("content", "").strip(),
            "insights":      insights
        })
        for item in results[1:]:
            rows.append({
                "section":       sec.get("title", ""),
                "item":          item.get("title") or item.get("name"),
                "score":         item.get("valueNumeric", item.get("value")),
                "risk":          item.get("riskClassification", ""),
                "optimal_range": None,
                "insights":      insights
            })
    df = pd.DataFrame(rows)
    # --- Cleaning/post-processing logic from notebook ---
    df = (
        df.rename(columns={
            'section': 'Category',
            'item': 'Microbe',
            'optimal_range': 'Summary',
            'insights': 'Insights',
            'score': 'Score',
            'risk': 'Risk'
        })
        .assign(
            Microbe=lambda x: x['Microbe'].fillna('Composite'),
            Risk=lambda x: x['Risk'].str.title() if x['Risk'].dtype == 'object' else x['Risk']
        )
    )
    # Deduplicate Insights: only keep the first non-empty per Category
    df['Insights'] = df.groupby('Category')['Insights'] \
                       .transform(lambda grp: grp.where(grp.ne('').cumsum() <= 1, ''))
    # Cleaning function: un-escape entities, strip citations, remove HTML tags
    def clean_text(text):
        if not text:
            return ''
        text = html.unescape(text)
        text = re.sub(r'<div class="references".*$', '', text, flags=re.DOTALL)
        text = BeautifulSoup(text, 'html.parser').get_text(separator=' ')
        return re.sub(r'\s+', ' ', text).strip()
    for col in ['Insights', 'Summary']:
        df[col] = df[col].apply(clean_text)
    # Clear Summary for non-summary categories
    valid_categories = [
        'Digestion', 'Inflammation', 'Gut Dysbiosis',
        'Intestinal Permeability', 'Nervous System',
        'Diversity Score', 'Immune Readiness Score',
        'Pathogens'
    ]
    df.loc[~df['Category'].isin(valid_categories), 'Summary'] = ''
    return df 