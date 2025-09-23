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
def fn_from_date(dt):
    month_name = dt.strftime("%B")
    return f"1FN {month_name}" if dt.day <= 15 else f"2FN {month_name}"

def normalize_fn_string(s):
    return str(s).replace(".", "").strip()

def das_in_range_string(das, das_str):
    s = str(das_str).strip()
    try:
        if "to" in s:
            a, b = [int(p.strip()) for p in s.split("to")]
            return a <= das <= b
        elif s.endswith("+"):
            a = int(s.replace("+", "").strip())
            return das >= a
        else:
            return int(s) == das
    except Exception:
        return False

# -----------------------------
# Load data from GitHub
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

    # Parse date column (auto-detect)
    if "Date(DD-MM-YYYY)" in weather_df.columns:
        weather_df["Date_dt"] = pd.to_datetime(weather_df["Date(DD-MM-YYYY)"], format="%d-%m-%Y", errors="coerce")
    elif "Date" in weather_df.columns:
        weather_df["Date_dt"] = pd.to_datetime(weather_df["Date"], errors="coerce")
    else:
        weather_df["Date_dt"] = pd.NaT

    weather_df = weather_df.dropna(subset=["Date_dt"]).copy()

    for col in ["Rainfall", "Tmax", "Tmin", "max_Rh", "min_Rh"]:
        if col in weather_df.columns:
            weather_df[col] = pd.to_numeric(weather_df[col], errors="coerce")

    for c in ["District", "Taluka", "Circle", "Crop"]:
        if c in sowing_df.columns:
            sowing_df[c] = sowing_df[c].astype(str).str.strip()

    if "Crop" in rules_df.columns:
        rules_df["Crop"] = rules_df["Crop"].astype(str).str.strip()

    districts = sorted(sowing_df["District"].dropna().unique().tolist()) if "District" in sowing_df.columns else []
    talukas = sorted(sowing_df["Taluka"].dropna().unique().tolist()) if "Taluka" in sowing_df.columns else []
    circles = sorted(sowing_df["Circle"].dropna().unique().tolist()) if "Circle" in sowing_df.columns else []
    crops = sorted(rules_df["Crop"].dropna().unique().tolist()) if "Crop" in rules_df.columns else []

    return weather_df, rules_df, sowing_df, districts, talukas, circles, crops

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
    elif level == "District":
        df = df[df["District"] == name]

    sowing_dt = datetime.strptime(sowing_date_str, "%d/%m/%Y")
    current_dt = datetime.strptime(current_date_str, "%d/%m/%Y")
    das = max((current_dt - sowing_dt).days, 0)

    das_mask = (df["Date_dt"] >= sowing_dt) & (df["Date_dt"] <= current_dt)
    week_start = current_dt - timedelta(days=6)
    month_start = current_dt - timedelta(days=29)

    week_mask = (df["Date_dt"] >= week_start) & (df["Date_dt"] <= current_dt)
    month_mask = (df["Date_dt"] >= month_start) & (df["Date_dt"] <= current_dt)

    das_data = df.loc[das_mask]
    week_data = df.loc[week_mask]
    month_data = df.loc[month_mask]

    rainfall_das = das_data["Rainfall"].fillna(0).sum() if "Rainfall" in das_data else 0
    rainfall_last_week = week_data["Rainfall"].fillna(0).sum() if "Rainfall" in week_data else 0
    rainfall_last_month = month_data["Rainfall"].fillna(0).sum() if "Rainfall" in month_data else 0

    # ✅ Rainy Days Calculation
    rainy_days_das = (das_data["Rainfall"] > 0).sum() if "Rainfall" in das_data else 0
    rainy_days_week = (week_data["Rainfall"] > 0).sum() if "Rainfall" in week_data else 0
    rainy_days_month = (month_data["Rainfall"] > 0).sum() if "Rainfall" in month_data else 0

    def avg_ignore_zero_and_na(series):
        if (series is None) or (series.size == 0):
            return None
        s = pd.to_numeric(series, errors="coerce").dropna()
        s = s[s != 0]
        return float(s.mean()) if not s.empty else None

    tmax_avg = avg_ignore_zero_and_na(das_data["Tmax"]) if "Tmax" in das_data else None
    tmin_avg = avg_ignore_zero_and_na(das_data["Tmin"]) if "Tmin" in das_data else None
    max_rh_avg = avg_ignore_zero_and_na(das_data["max_Rh"]) if "max_Rh" in das_data else None
    min_rh_avg = avg_ignore_zero_and_na(das_data["min_Rh"]) if "min_Rh" in das_data else None

    return {
        "rainfall_last_week": rainfall_last_week,
        "rainfall_last_month": rainfall_last_month,
        "rainfall_das": rainfall_das,
        "rainy_days_week": rainy_days_week,
        "rainy_days_month": rainy_days_month,
        "rainy_days_das": rainy_days_das,
        "tmax_avg": tmax_avg,
        "tmin_avg": tmin_avg,
        "max_rh_avg": max_rh_avg,
        "min_rh_avg": min_rh_avg,
        "das": das,
    }

def get_sowing_comments(sowing_date_str, district, taluka, circle, crop, sowing_df):
    if sowing_df.empty:
        return []
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

def get_growth_advisory(crop, das, rainfall_das, rules_df):
    if "Crop" not in rules_df.columns:
        return None
    candidates = rules_df[rules_df["Crop"] == crop]
    if candidates.empty:
        return None

    for _, row in candidates.iterrows():
        if das_in_range_string(das, row.get("DAS (Days After Sowing)", "")):
            return {
                "growth_stage": row.get("Growth Stage", "Unknown"),
                "das": das,
                "ideal_water": row.get("Ideal Water Required (in mm)", ""),
                "farmer_advisory": row.get("Farmer Advisory", "")
            }
    return None

# -----------------------------
# UI
# -----------------------------
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
            st.metric("Rainy Days - Last Week", metrics["rainy_days_week"])
            st.metric("Rainfall - Last Month (mm)", f"{metrics['rainfall_last_month']:.1f}")
            st.metric("Rainy Days - Last Month", metrics["rainy_days_month"])
        with c2:
            st.metric("Rainfall - Since Sowing/DAS (mm)", f"{metrics['rainfall_das']:.1f}")
            st.metric("Rainy Days - Since Sowing", metrics["rainy_days_das"])
            st.metric("Tmax Avg (since sowing)", f"{metrics['tmax_avg']:.1f}" if metrics['tmax_avg'] is not None else "N/A")
            st.metric("Tmin Avg (since sowing)", f"{metrics['tmin_avg']:.1f}" if metrics['tmin_avg'] is not None else "N/A")
        with c3:
            st.metric("Max RH Avg (since sowing)", f"{metrics['max_rh_avg']:.1f}" if metrics['max_rh_avg'] is not None else "N/A")
            st.metric("Min RH Avg (since sowing)", f"{metrics['min_rh_avg']:.1f}" if metrics['min_rh_avg'] is not None else "N/A")

        # -------------------------------------
        # 📅 Daily Weather Table (Highlighted)
        # -------------------------------------
        st.markdown("---")
        st.header("📅 Daily Weather Data (Highlighted Rainy Days)")

        df_filtered = weather_df.copy()
        if level == "Circle":
            df_filtered = df_filtered[df_filtered["Circle"] == level_name]
        elif level == "Taluka":
            df_filtered = df_filtered[df_filtered["Taluka"] == level_name]
        elif level == "District":
            df_filtered = df_filtered[df_filtered["District"] == level_name]

        sowing_dt = datetime.strptime(sowing_date_str, "%d/%m/%Y")
        current_dt = datetime.strptime(current_date_str, "%d/%m/%Y")
        mask = (df_filtered["Date_dt"] >= sowing_dt) & (df_filtered["Date_dt"] <= current_dt)
        das_data = df_filtered.loc[mask]

        if not das_data.empty:
            display_df = das_data.copy().sort_values("Date_dt")
            display_df["Date"] = display_df["Date_dt"].dt.strftime("%d-%m-%Y")
            columns_to_show = ["Date", "Rainfall", "Tmax", "Tmin", "max_Rh", "min_Rh"]
            display_df = display_df[[col for col in columns_to_show if col in display_df.columns]]

            def highlight_rainy_days(row):
                return [
                    "background-color: #0ea6ff; font-weight: bold;" if (col == "Rainfall" and row["Rainfall"] > 0)
                    else "background-color: #0ea6ff;" if row["Rainfall"] > 0
                    else ""
                    for col in row.index
                ]

            st.dataframe(display_df.style.apply(highlight_rainy_days, axis=1), use_container_width=True)
        else:
            st.info("No daily weather data for selected date range.")

        # -------------------------------------
        # 📝 Comment on Sowing
        # -------------------------------------
        st.markdown("---")
        st.header("📝 Comment on Sowing")
        sowing_comments = get_sowing_comments(sowing_date_str, district, taluka, circle, crop, sowing_df)
        if sowing_comments:
            for comment in sowing_comments:
                st.write(f"• {comment}")
        else:
            st.write("No matching sowing comments found.")

        # -------------------------------------
        # 🌱 Growth Stage Advisory
        # -------------------------------------
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
