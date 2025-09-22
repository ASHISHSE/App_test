import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import urllib.parse
import requests
from io import BytesIO

st.set_page_config(page_title="Crop Advisory System", page_icon="🌱", layout="wide")

def parse_ddmmyy_to_ddmmyyyy(val):
    try:
        s = str(int(val)).zfill(6)
        return datetime.strptime(s, "%d%m%y").strftime("%d/%m/%Y")
    except Exception:
        try:
            dt = pd.to_datetime(val, dayfirst=True)
            return dt.strftime("%d/%m/%Y")
        except Exception:
            return None

def parse_if_condition(cond_str):
    cond = str(cond_str).strip().replace("and", "&").replace("AND", "&")
    parts = [p.strip() for p in cond.split("&")]
    checks = []
    for p in parts:
        if p.startswith(">="):
            v = float(p.replace(">=", "").strip()); checks.append(lambda x, v=v: x >= v)
        elif p.startswith("<="):
            v = float(p.replace("<=", "").strip()); checks.append(lambda x, v=v: x <= v)
        elif p.startswith(">"):
            v = float(p.replace(">", "").strip()); checks.append(lambda x, v=v: x > v)
        elif p.startswith("<"):
            v = float(p.replace("<", "").strip()); checks.append(lambda x, v=v: x < v)
        else:
            try:
                v = float(p); checks.append(lambda x, v=v: x == v)
            except: pass
    return lambda x: all(check(x) for check in checks)

def das_in_range_string(das, das_str):
    s = str(das_str).strip()
    if "to" in s:
        try:
            a, b = [int(p.strip()) for p in s.split("to")]
            return a <= das <= b
        except: return False
    elif s.endswith("+"):
        try:
            a = int(s.replace("+", "").strip())
            return das >= a
        except: return False
    else:
        try:
            return int(s) == das
        except: return False

def fn_from_date(dt):
    return f"1FN {dt.strftime('%B')}" if dt.day <= 15 else f"2FN {dt.strftime('%B')}"

def normalize_fn_string(s):
    return str(s).replace(".", "").strip()

@st.cache_data
def load_data():
    weather_url = "https://github.com/ASHISHSE/App_test/raw/main/weather.xlsx"
    rules_url = "https://github.com/ASHISHSE/App_test/raw/main/rules.xlsx"
    sowing_url = "https://github.com/ASHISHSE/App_test/raw/main/sowing_calendar.xlsx"

    wres = requests.get(weather_url, timeout=10)
    rres = requests.get(rules_url, timeout=10)
    sres = requests.get(sowing_url, timeout=10)

    weather_df = pd.read_excel(BytesIO(wres.content))
    rules_df = pd.read_excel(BytesIO(rres.content))
    sowing_df = pd.read_excel(BytesIO(sres.content))

    if "Date(DDMMYY)" in weather_df.columns:
        weather_df["Date"] = weather_df["Date(DDMMYY)"].apply(parse_ddmmyy_to_ddmmyyyy)
    elif "Date" in weather_df.columns:
        weather_df["Date"] = pd.to_datetime(weather_df["Date"], errors="coerce").dt.strftime("%d/%m/%Y")

    for col in ["Rainfall", "Tmax", "Tmin", "max_Rh", "min_Rh"]:
        if col in weather_df.columns:
            weather_df[col] = pd.to_numeric(weather_df[col], errors="coerce")

    for c in ["District", "Taluka", "Circle"]:
        if c in weather_df.columns:
            weather_df[c] = weather_df[c].astype(str).str.strip()

    if "Crop" in rules_df.columns:
        rules_df["Crop"] = rules_df["Crop"].astype(str).str.strip()

    districts = sorted(weather_df["District"].dropna().unique().tolist())
    talukas = sorted(weather_df["Taluka"].dropna().unique().tolist()) if "Taluka" in weather_df.columns else []
    circles = sorted(weather_df["Circle"].dropna().unique().tolist())
    crops = sorted(rules_df["Crop"].dropna().unique().tolist())
    return weather_df, rules_df, sowing_df, districts, talukas, circles, crops

weather_df, rules_df, sowing_df, districts, talukas, circles, crops = load_data()

def calculate_weather_metrics(df, level, name, sowing_date_str, current_date_str):
    if level == "Circle": df = df[df["Circle"] == name]
    elif level == "Taluka": df = df[df["Taluka"] == name]
    else: df = df[df["District"] == name]

    df["Date_dt"] = pd.to_datetime(df["Date"], format="%d/%m/%Y", errors="coerce")
    sowing_dt = datetime.strptime(sowing_date_str, "%d/%m/%Y")
    current_dt = datetime.strptime(current_date_str, "%d/%m/%Y")

    das = max((current_dt - sowing_dt).days, 0)

    last_week = current_dt - timedelta(days=7)
    last_month = current_dt - timedelta(days=30)

    das_data = df[(df["Date_dt"] >= sowing_dt) & (df["Date_dt"] <= current_dt)]

    return {
        "rainfall_last_week": float(df[(df["Date_dt"] >= last_week)]["Rainfall"].sum()),
        "rainfall_last_month": float(df[(df["Date_dt"] >= last_month)]["Rainfall"].sum()),
        "rainfall_das": float(das_data["Rainfall"].sum()),
        "tmax_avg": float(das_data["Tmax"].dropna().mean()) if not das_data.empty else None,
        "tmin_avg": float(das_data["Tmin"].dropna().mean()) if not das_data.empty else None,
        "max_rh_avg": float(das_data["max_Rh"].dropna().mean()) if not das_data.empty else None,
        "min_rh_avg": float(das_data["min_Rh"].dropna().mean()) if not das_data.empty else None,
        "das": das
    }

def get_growth_advisory(crop, das, rainfall_das, rules_df):
    subset = rules_df[rules_df["Crop"] == crop]
    for _, row in subset.iterrows():
        if das_in_range_string(das, row.get("DAS (Days After Sowing)")):
            evaluator = parse_if_condition(row.get("IF Condition", ""))
            if evaluator(rainfall_das):
                return {
                    "growth_stage": row.get("Growth Stage", "Unknown"),
                    "das": das,
                    "ideal_water": row.get("Ideal Water Required (in mm)", ""),
                    "farmer_advisory": row.get("Farmer Advisory", "")
                }
    return None

def get_sowing_comments(sowing_date_str, district, taluka, circle, crop, sowing_df):
    sowing_dt = datetime.strptime(sowing_date_str, "%d/%m/%Y")
    fn = fn_from_date(sowing_dt)
    filters = [
        (sowing_df["District"] == district) & (sowing_df["Taluka"] == taluka) & (sowing_df["Circle"] == circle) & (sowing_df["Crop"] == crop),
        (sowing_df["District"] == district) & (sowing_df["Taluka"] == taluka) & (sowing_df["Crop"] == crop),
        (sowing_df["District"] == district) & (sowing_df["Crop"] == crop)
    ]
    results = []
    for f in filters:
        subset = sowing_df[f]
        for _, row in subset.iterrows():
            cond = normalize_fn_string(row.get("IF condition", ""))
            if fn.lower() in cond.lower():
                results.append(f"{row.get('IF condition','')}: {row.get('Comments on Sowing','')}")
        if results:
            break
    return results

st.title("🌱 Crop Advisory System")
col1, col2, col3 = st.columns(3)
with col1:
    district = st.selectbox("District *", [""] + districts)
    taluka_options = [""] + sorted(weather_df[weather_df["District"] == district]["Taluka"].dropna().unique().tolist()) if district else talukas
    taluka = st.selectbox("Taluka", taluka_options)
    circle_options = [""] + sorted(weather_df[weather_df["Taluka"] == taluka]["Circle"].dropna().unique().tolist()) if taluka else circles
    circle = st.selectbox("Circle", circle_options)
with col2:
    crop = st.selectbox("Crop Name *", [""] + crops)
    sowing_date = st.date_input("Sowing Date (dd/mm/yyyy)", value=date.today()-timedelta(days=30), format="DD/MM/YYYY")
with col3:
    current_date = st.date_input("Current Date (dd/mm/yyyy)", value=date.today(), format="DD/MM/YYYY")

generate = st.button("🌱 Generate Advisory")
if generate:
    if not district or not crop:
        st.error("Please select all required fields.")
    else:
        sowing_date_str = sowing_date.strftime("%d/%m/%Y")
        current_date_str = current_date.strftime("%d/%m/%Y")
        level = "Circle" if circle else "Taluka" if taluka else "District"
        level_name = circle if circle else taluka if taluka else district

        metrics = calculate_weather_metrics(weather_df, level, level_name, sowing_date_str, current_date_str)

        st.header("🌤️ Weather Metrics")
        st.dataframe(pd.DataFrame({
            "Metric": ["Rainfall Last Week", "Rainfall Last Month", "Rainfall DAS", "Avg Tmax", "Avg Tmin", "Avg max RH", "Avg min RH"],
            "Value": [metrics['rainfall_last_week'], metrics['rainfall_last_month'], metrics['rainfall_das'], metrics['tmax_avg'], metrics['tmin_avg'], metrics['max_rh_avg'], metrics['min_rh_avg']]
        }))

        st.header("📝 Comment in Sowing")
        comments = get_sowing_comments(sowing_date_str, district, taluka, circle, crop, sowing_df)
        if comments:
            for c in comments: st.write(f"• {c}")
        else:
            st.write("No matching sowing comment found.")

        st.header("🌱 Growth Stage Advisory")
        g = get_growth_advisory(crop, metrics['das'], metrics['rainfall_das'], rules_df)
        if g:
            st.write(f"**Growth Stage:** {g['growth_stage']}")
            st.write(f"**DAS:** {g['das']}")
            st.write(f"**Ideal Water Required (mm):** {g['ideal_water']}")
            st.write(f"**Farmer Advisory:** {g['farmer_advisory']}")
        else:
            st.write("No matching growth stage advisory found.")
