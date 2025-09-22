# crop_advisory_app_ddmmyyyy.py
# Full Streamlit Crop Advisory app with:
# - Sowing advisory fixes (using Comment on Sowing)
# - Dropdowns all displayed at once
# - Date format changed to dd/mm/yyyy everywhere

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import urllib.parse
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

def parse_water_range(water_str):
    try:
        s = str(water_str)
        if "to" in s:
            a, b = [float(x.strip()) for x in s.split("to")]
            return a, b
        else:
            v = float(s.strip())
            return v, v
    except Exception:
        return None, None

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
    try:
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
            weather_df["Date"] = weather_df["Date"].apply(lambda x: pd.to_datetime(x).strftime("%d/%m/%Y"))

        for col in ["Rainfall", "Tmax", "Tmin", "max_Rh", "min_Rh"]:
            if col in weather_df.columns:
                weather_df[col] = pd.to_numeric(weather_df[col], errors="coerce")

        for c in ["District", "Taluka", "Circle"]:
            if c in weather_df.columns:
                weather_df[c] = weather_df[c].astype(str).str.strip()

        if "Crop" in rules_df.columns:
            rules_df["Crop"] = rules_df["Crop"].astype(str).str.strip()

        districts = sorted(weather_df["District"].dropna().unique().tolist())
        talukas = sorted(weather_df["Taluka"].dropna().unique().tolist())
        circles = sorted(weather_df["Circle"].dropna().unique().tolist())
        crops = sorted(rules_df["Crop"].dropna().unique().tolist())

        return weather_df, rules_df, sowing_df, districts, talukas, circles, crops

    except Exception as e:
        st.warning(f"Could not load remote files, using sample data. Error: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), [], [], [], []

weather_df, rules_df, sowing_df, districts, talukas, circles, crops = load_data()

# -----------------------------
# Metrics & Advisory Functions
# -----------------------------
def calculate_weather_metrics(weather_data, level, name, sowing_date_str, current_date_str):
    df = weather_data.copy()
    if level == "Circle":
        df = df[df["Circle"] == name]
    elif level == "Taluka":
        df = df[df["Taluka"] == name]
    else:
        df = df[df["District"] == name]

    df["Date_dt"] = pd.to_datetime(df["Date"], format="%d/%m/%Y", errors="coerce")
    sowing_dt = datetime.strptime(sowing_date_str, "%d/%m/%Y")
    current_dt = datetime.strptime(current_date_str, "%d/%m/%Y")

    das = (current_dt - sowing_dt).days
    if das < 0:
        das = 0

    last_week_start = current_dt - timedelta(days=7)
    last_month_start = current_dt - timedelta(days=30)

    last_week_data = df[(df["Date_dt"] >= last_week_start) & (df["Date_dt"] <= current_dt)]
    last_month_data = df[(df["Date_dt"] >= last_month_start) & (df["Date_dt"] <= current_dt)]
    das_data = df[(df["Date_dt"] >= sowing_dt) & (df["Date_dt"] <= current_dt)]

    return {
        "rainfall_last_week": float(last_week_data["Rainfall"].sum()) if not last_week_data.empty else 0.0,
        "rainfall_last_month": float(last_month_data["Rainfall"].sum()) if not last_month_data.empty else 0.0,
        "rainfall_das": float(das_data["Rainfall"].sum()) if not das_data.empty else 0.0,
        "tmax_avg": float(das_data["Tmax"].mean()) if not das_data["Tmax"].dropna().empty else None,
        "tmin_avg": float(das_data["Tmin"].mean()) if not das_data["Tmin"].dropna().empty else None,
        "max_rh_avg": float(das_data["max_Rh"].mean()) if not das_data["max_Rh"].dropna().empty else None,
        "min_rh_avg": float(das_data["min_Rh"].mean()) if not das_data["min_Rh"].dropna().empty else None,
        "das": das,
    }

def get_sowing_advisory(sowing_date_str, district, taluka, circle, crop, sowing_df):
    sowing_dt = datetime.strptime(sowing_date_str, "%d/%m/%Y")
    fn = fn_from_date(sowing_dt)

    filters = [
        (sowing_df["District"] == district) & (sowing_df["Taluka"] == taluka) & (sowing_df["Circle"] == circle) & (sowing_df["Crop"] == crop),
        (sowing_df["District"] == district) & (sowing_df["Taluka"] == taluka) & (sowing_df["Crop"] == crop),
        (sowing_df["District"] == district) & (sowing_df["Crop"] == crop),
    ]

    for f in filters:
        subset = sowing_df[f]
        if not subset.empty:
            for _, row in subset.iterrows():
                cond = normalize_fn_string(row.get("IF condition", "") or row.get("IF Condition", ""))
                if not cond:
                    continue
                if fn.lower() in cond.lower():
                    return row.get("Comment on Sowing", "")
                if cond.startswith("<") or cond.startswith(">") or "to" in cond:
                    return row.get("Comment on Sowing", "")
            break

    return "No sowing advisory available for this date."

# -----------------------------
# UI
# -----------------------------
qp = st.query_params

pref_district = qp.get("district", [""])[0] if "district" in qp else ""
pref_taluka = qp.get("taluka", [""])[0] if "taluka" in qp else ""
pref_circle = qp.get("circle", [""])[0] if "circle" in qp else ""
pref_crop = qp.get("crop", [""])[0] if "crop" in qp else ""
pref_sowing = qp.get("sowing", [""])[0] if "sowing" in qp else ""
pref_current = qp.get("current", [""])[0] if "current" in qp else ""

st.title("🌱 Crop Advisory System")
st.write("Select a location and crop, enter sowing & current dates, and click Generate Advisory.")

col1, col2, col3 = st.columns(3)

with col1:
    district = st.selectbox("District *", options=[""] + districts, index=(districts.index(pref_district) + 1) if pref_district in districts else 0)
    taluka_options = [""] + (sorted(weather_df[weather_df["District"] == district]["Taluka"].dropna().unique().tolist()) if district else talukas)
    taluka = st.selectbox("Taluka", options=taluka_options, index=(taluka_options.index(pref_taluka) if pref_taluka in taluka_options else 0))
    circle_options = [""] + (sorted(weather_df[weather_df["Taluka"] == taluka]["Circle"].dropna().unique().tolist()) if taluka else circles)
    circle = st.selectbox("Circle", options=circle_options, index=(circle_options.index(pref_circle) if pref_circle in circle_options else 0))

with col2:
    crop = st.selectbox("Crop Name *", options=[""] + crops, index=(crops.index(pref_crop) + 1) if pref_crop in crops else 0)
    sowing_default = None
    if pref_sowing:
        try:
            sowing_default = datetime.strptime(pref_sowing, "%d/%m/%Y").date()
        except:
            pass
    sowing_date = st.date_input("Sowing Date (dd/mm/yyyy) *", value=sowing_default or date.today() - timedelta(days=30), format="DD/MM/YYYY")

with col3:
    current_default = None
    if pref_current:
        try:
            current_default = datetime.strptime(pref_current, "%d/%m/%Y").date()
        except:
            current_default = date.today()
    current_date = st.date_input("Current Date (dd/mm/yyyy) *", value=current_default or date.today(), format="DD/MM/YYYY")

generate = st.button("🌱 Generate Advisory")

if generate:
    if not district or not crop or not sowing_date or not current_date:
        st.error("Please select District, Crop and enter both Sowing and Current dates.")
    elif sowing_date > current_date:
        st.error("Sowing date cannot be after current date.")
    else:
        sowing_date_str = sowing_date.strftime("%d/%m/%Y")
        current_date_str = current_date.strftime("%d/%m/%Y")
        level = "Circle" if circle else "Taluka" if taluka else "District"
        level_name = circle or taluka or district
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
        st.header("📋 Advisory Results")
        st.subheader("Sowing Advisory")
        st.write(get_sowing_advisory(sowing_date_str, district, taluka, circle, crop, sowing_df))

        st.markdown("---")
        st.header("📤 Share Advisory")
        params = {"district": district, "taluka": taluka or "", "circle": circle or "", "crop": crop, "sowing": sowing_date_str, "current": current_date_str}
        query_string = urllib.parse.urlencode(params)
        shareable_link = f"?{query_string}"
        st.code(shareable_link, language="")
