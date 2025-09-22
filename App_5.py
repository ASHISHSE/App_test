import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import requests
from io import BytesIO

st.set_page_config(page_title="Crop Advisory System", page_icon="🌱", layout="wide")

# -----------------------------
# Helpers
# -----------------------------
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
    cond = str(cond_str).strip()
    cond = cond.replace("and", "&").replace("AND", "&")
    parts = [p.strip() for p in cond.split("&")]

    checks = []
    for p in parts:
        if p.startswith(">="):
            v = float(p.replace(">=", "").strip())
            checks.append(lambda x, v=v: x >= v)
        elif p.startswith("<="):
            v = float(p.replace("<=", "").strip())
            checks.append(lambda x, v=v: x <= v)
        elif p.startswith(">"):
            v = float(p.replace(">", "").strip())
            checks.append(lambda x, v=v: x > v)
        elif p.startswith("<"):
            v = float(p.replace("<", "").strip())
            checks.append(lambda x, v=v: x < v)
        else:
            try:
                v = float(p)
                checks.append(lambda x, v=v: x == v)
            except Exception:
                pass

    def evaluator(x):
        try:
            for check in checks:
                if not check(x):
                    return False
            return True
        except Exception:
            return False

    return evaluator

def das_in_range_string(das, das_str):
    s = str(das_str).strip()
    if "to" in s:
        try:
            a, b = [int(p.strip()) for p in s.split("to")]
            return a <= das <= b
        except Exception:
            return False
    elif s.endswith("+"):
        try:
            a = int(s.replace("+", "").strip())
            return das >= a
        except Exception:
            return False
    else:
        try:
            return int(s) == das
        except Exception:
            return False

def fn_from_date(dt):
    month_name = dt.strftime("%B")
    day = dt.day
    return f"1FN {month_name}" if day <= 15 else f"2FN {month_name}"

def normalize_fn_string(s):
    return str(s).replace(".", "").strip()

# -----------------------------
# Load data
# -----------------------------
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

    # Use the new column name if available
    if "Date(DD-MM-YYYY)" in weather_df.columns:
        weather_df["Date"] = pd.to_datetime(weather_df["Date(DD-MM-YYYY)"], format="%d-%m-%Y", errors="coerce").dt.strftime("%d/%m/%Y")
    elif "Date(DDMMYY)" in weather_df.columns:
        weather_df["Date"] = weather_df["Date(DDMMYY)"].apply(parse_ddmmyy_to_ddmmyyyy)
    elif "Date" in weather_df.columns:
        weather_df["Date"] = pd.to_datetime(weather_df["Date"], errors="coerce").dt.strftime("%d/%m/%Y")
    else:
        weather_df["Date"] = None

    weather_df = weather_df.dropna(subset=["Date"]).copy()

    # numeric conversion
    for col in ["Rainfall", "Tmax", "Tmin", "max_Rh", "min_Rh"]:
        if col in weather_df.columns:
            weather_df[col] = pd.to_numeric(weather_df[col], errors="coerce")

    # strip text columns
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

# -----------------------------
# Metrics & Advisory Functions
# -----------------------------
def calculate_weather_metrics(weather_data, level, name, sowing_date_str, current_date_str):
    """
    A) Rainfall - Last Week (sum over last 7 days including current date)
    B) Rainfall - Last Month (sum over last 30 days including current date)
    C) Rainfall - Since Sowing (sum from sowing date to current date inclusive)
    D) Tmax/Tmin/max_Rh/min_Rh averages: computed on sowing->current window, ignoring 0 and NaN
    """
    df = weather_data.copy()

    # filter by location level
    if level == "Circle":
        df = df[df["Circle"] == name]
    elif level == "Taluka":
        df = df[df["Taluka"] == name]
    else:
        df = df[df["District"] == name]

    # ensure datetime column
    df["Date_dt"] = pd.to_datetime(df["Date"], format="%d/%m/%Y", errors="coerce")

    sowing_dt = datetime.strptime(sowing_date_str, "%d/%m/%Y")
    current_dt = datetime.strptime(current_date_str, "%d/%m/%Y")

    # DAS (days after sowing)
    das = max((current_dt - sowing_dt).days, 0)

    # Define inclusive windows:
    # - Last 7 days including current date -> start = current_dt - 6 days (7 days total)
    week_start = current_dt - timedelta(days=6)
    # - Last 30 days including current date -> start = current_dt - 29 days (30 days total)
    month_start = current_dt - timedelta(days=29)

    # Masks
    week_mask = (df["Date_dt"] >= week_start) & (df["Date_dt"] <= current_dt)
    month_mask = (df["Date_dt"] >= month_start) & (df["Date_dt"] <= current_dt)
    das_mask = (df["Date_dt"] >= sowing_dt) & (df["Date_dt"] <= current_dt)

    week_data = df.loc[week_mask]
    month_data = df.loc[month_mask]
    das_data = df.loc[das_mask]

    # Rainfall sums: treat NaN as 0 (no reading -> assume 0 contribution)
    rainfall_last_week = float(week_data["Rainfall"].fillna(0).sum()) if not week_data.empty else 0.0
    rainfall_last_month = float(month_data["Rainfall"].fillna(0).sum()) if not month_data.empty else 0.0
    rainfall_das = float(das_data["Rainfall"].fillna(0).sum()) if not das_data.empty else 0.0

    # Averages from sowing -> current: ignore NaN and zeros (so zeros won't bias the mean)
    def avg_ignore_zero_and_na(series):
        if (series is None) or (series.size == 0):
            return None
        s = pd.to_numeric(series, errors="coerce").replace(0, np.nan).dropna()
        if s.empty:
            return None
        return float(s.mean())

    tmax_avg = avg_ignore_zero_and_na(das_data["Tmax"]) if "Tmax" in das_data.columns else None
    tmin_avg = avg_ignore_zero_and_na(das_data["Tmin"]) if "Tmin" in das_data.columns else None
    max_rh_avg = avg_ignore_zero_and_na(das_data["max_Rh"]) if "max_Rh" in das_data.columns else None
    min_rh_avg = avg_ignore_zero_and_na(das_data["min_Rh"]) if "min_Rh" in das_data.columns else None

    metrics = {
        "rainfall_last_week": rainfall_last_week,
        "rainfall_last_month": rainfall_last_month,
        "rainfall_das": rainfall_das,
        "tmax_avg": tmax_avg,
        "tmin_avg": tmin_avg,
        "max_rh_avg": max_rh_avg,
        "min_rh_avg": min_rh_avg,
        "das": das,
    }
    return metrics

# (keep get_growth_advisory, get_sowing_comments unchanged from your existing code)
def get_growth_advisory(crop, das, rainfall_das, rules_df):
    candidates = rules_df[rules_df["Crop"] == crop]
    if candidates.empty:
        return None

    for _, row in candidates.iterrows():
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
    results = []

    filters = [
        (sowing_df["District"] == district) & (sowing_df["Taluka"] == taluka) & (sowing_df["Circle"] == circle) & (sowing_df["Crop"] == crop),
        (sowing_df["District"] == district) & (sowing_df["Taluka"] == taluka) & (sowing_df["Crop"] == crop),
        (sowing_df["District"] == district) & (sowing_df["Crop"] == crop),
    ]

    for f in filters:
        subset = sowing_df[f]
        if not subset.empty:
            for _, row in subset.iterrows():
                cond = normalize_fn_string(row.get("IF condition", ""))
                if cond and fn.lower() in cond.lower():
                    results.append(f"{row.get('IF condition','')}: {row.get('Comments on Sowing','')}")
            if results:
                break
    return results

# -----------------------------
# UI
# -----------------------------
qp = st.query_params

st.title("🌱 Crop Advisory System")

st.markdown(
    "<span style='color: red; font-weight: bold;'>⚠️ Testing Version:</span> "
    "Data uploaded from <b>01 June 2024</b> to <b>31 Oct 2024</b>. "
    "Please select dates within this range.",
    unsafe_allow_html=True
)

st.write("📍 Select a location and crop, enter **Sowing Date** & **Current Date**, then click **Generate Advisory**.")

col1, col2, col3 = st.columns(3)
with col1:
    district = st.selectbox("District *", [""] + districts)
    taluka_options = [""] + sorted(weather_df[weather_df["District"] == district]["Taluka"].dropna().unique().tolist()) if district else talukas
    taluka = st.selectbox("Taluka", taluka_options)
    circle_options = [""] + sorted(weather_df[weather_df["Taluka"] == taluka]["Circle"].dropna().unique().tolist()) if taluka else circles
    circle = st.selectbox("Circle", circle_options)

with col2:
    crop = st.selectbox("Crop Name *", [""] + crops)
    sowing_date = st.date_input("Sowing Date (dd/mm/yyyy)", value=date.today() - timedelta(days=30), format="DD/MM/YYYY")
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

        st.markdown("---")
        st.header("🌤️ Weather Metrics")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Rainfall - Last Week (mm)", f"{metrics['rainfall_last_week']:.1f}")
            st.metric("Rainfall - Last Month (mm)", f"{metrics['rainfall_last_month']:.1f}")
            st.metric("Rainfall - Since Sowing/DAS (mm)", f"{metrics['rainfall_das']:.1f}")
        with c2:
            st.metric("Tmax Avg (since sowing)", f"{metrics['tmax_avg']:.1f}" if metrics['tmax_avg'] is not None else "N/A")
            st.metric("Tmin Avg (since sowing)", f"{metrics['tmin_avg']:.1f}" if metrics['tmin_avg'] is not None else "N/A")
        with c3:
            st.metric("Max RH Avg (since sowing)", f"{metrics['max_rh_avg']:.1f}" if metrics['max_rh_avg'] is not None else "N/A")
            st.metric("Min RH Avg (since sowing)", f"{metrics['min_rh_avg']:.1f}" if metrics['min_rh_avg'] is not None else "N/A")

        st.markdown("---")
        st.header("📝 Comment on Sowing")
        sowing_comments = get_sowing_comments(sowing_date_str, district, taluka, circle, crop, sowing_df)
        for comment in sowing_comments:
            st.write(f"• {comment}")

        st.markdown("---")
        st.header("🌱 Growth Stage Advisory")
        growth_data = get_growth_advisory(crop, metrics["das"], metrics["rainfall_das"], rules_df)
        if growth_data:
            st.write(f"**Growth Stage:** {growth_data['growth_stage']}")
            st.write(f"**DAS:** {growth_data['das']}")
            st.write(f"**Ideal Water Required (mm):** {growth_data['ideal_water']}")
            st.write(f"**Farmer Advisory:** {growth_data['farmer_advisory']}")
        else:
            st.write("No matching growth advisory found.")
