# crop_advisory_app_updated.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="🌱 Crop Advisory System", layout="wide")

# -----------------------------
# Load data
# -----------------------------
@st.cache_data
def load_data():
    try:
        weather_url = "https://github.com/ASHISHSE/App_test/raw/main/weather.xlsx"
        rules_url = "https://github.com/ASHISHSE/App_test/raw/main/rules.xlsx"
        sowing_url = "https://github.com/ASHISHSE/App_test/raw/main/sowing_calendar.xlsx"

        weather_df = pd.read_excel(weather_url)
        rules_df = pd.read_excel(rules_url)
        sowing_df = pd.read_excel(sowing_url)

        # Convert Date to DD-MM-YYYY
        if "Date" in weather_df.columns:
            weather_df["Date"] = pd.to_datetime(weather_df["Date"], errors="coerce", dayfirst=True)
            weather_df["Date"] = weather_df["Date"].dt.strftime("%d-%m-%Y")
        elif "Date(DDMMYY)" in weather_df.columns:
            def conv_ddmmyy(x):
                try:
                    s = str(int(x)).zfill(6)
                    return datetime.strptime(s, "%d%m%y").strftime("%d-%m-%Y")
                except:
                    return None
            weather_df["Date"] = weather_df["Date(DDMMYY)"].apply(conv_ddmmyy)

        # Clean key columns
        for col in ["District", "Taluka", "Circle", "Crop"]:
            if col in weather_df.columns:
                weather_df[col] = weather_df[col].astype(str).str.strip()

        for col in ["Rainfall", "Tmax", "Tmin", "max_Rh", "min_Rh"]:
            if col in weather_df.columns:
                weather_df[col] = pd.to_numeric(weather_df[col], errors="coerce")

        rules_df.columns = [c.strip() for c in rules_df.columns]
        sowing_df.columns = [c.strip() for c in sowing_df.columns]
        weather_df.columns = [c.strip() for c in weather_df.columns]

        return weather_df, rules_df, sowing_df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None, None, None

weather_df, rules_df, sowing_df = load_data()
if weather_df is None:
    st.stop()

# -----------------------------
# Location & Crop Inputs
# -----------------------------
st.title("🌾 Crop Advisory Dashboard")
st.markdown("Select your **location, crop, and dates** to get personalized advisories.")

col1, col2, col3 = st.columns(3)
with col1:
    districts = sorted(weather_df["District"].dropna().unique())
    district = st.selectbox("📍 District", ["Select District"] + districts)
    if district == "Select District":
        st.warning("Please select a district.")
        st.stop()

with col2:
    taluka_options = sorted(weather_df.loc[weather_df["District"] == district, "Taluka"].dropna().unique())
    taluka = st.selectbox("🏢 Taluka", ["All Talukas"] + taluka_options)

with col3:
    if taluka != "All Talukas":
        circle_options = sorted(weather_df.loc[(weather_df["District"] == district) & (weather_df["Taluka"] == taluka), "Circle"].dropna().unique())
    else:
        circle_options = sorted(weather_df.loc[weather_df["District"] == district, "Circle"].dropna().unique())
    circle = st.selectbox("🔄 Circle", ["All Circles"] + circle_options)

crop_list = sorted(rules_df["Crop"].dropna().unique()) if "Crop" in rules_df.columns else []
crop_name = st.selectbox("🌱 Crop Name", [""] + crop_list)

col4, col5 = st.columns(2)
with col4:
    sowing_date = st.date_input("📅 Sowing Date (DD-MM-YYYY)", value=(datetime.today() - timedelta(days=30)).date())
with col5:
    current_date = st.date_input("📅 Current Date (DD-MM-YYYY)", value=datetime.today().date())

if sowing_date > current_date:
    st.error("❌ Sowing date cannot be after current date.")
    st.stop()

# -----------------------------
# Filter & Preprocess Weather Data
# -----------------------------
loc_df = weather_df.copy()
loc_df = loc_df[loc_df["District"] == district]
if taluka != "All Talukas":
    loc_df = loc_df[loc_df["Taluka"] == taluka]
if circle != "All Circles":
    loc_df = loc_df[loc_df["Circle"] == circle]

loc_df["Date"] = pd.to_datetime(loc_df["Date"], format="%d-%m-%Y", errors="coerce")
loc_df = loc_df.dropna(subset=["Date"])
loc_df = loc_df[loc_df["Date"] <= pd.to_datetime(current_date)]

DAS = max((pd.to_datetime(current_date) - pd.to_datetime(sowing_date)).days, 0)
sowing_window_df = loc_df[(loc_df["Date"] >= pd.to_datetime(sowing_date)) & (loc_df["Date"] <= pd.to_datetime(current_date))]

def avg_ignore_zero_and_na(series):
    s = pd.to_numeric(series, errors="coerce").replace(0, np.nan).dropna()
    return float(s.mean()) if not s.empty else None

rainfall_DAS = sowing_window_df["Rainfall"].fillna(0).sum()
rainfall_week = loc_df.loc[loc_df["Date"] >= (pd.to_datetime(current_date) - timedelta(days=7)), "Rainfall"].fillna(0).sum()
rainfall_month = loc_df.loc[loc_df["Date"] >= (pd.to_datetime(current_date) - timedelta(days=30)), "Rainfall"].fillna(0).sum()

avg_Tmax = avg_ignore_zero_and_na(sowing_window_df["Tmax"])
avg_Tmin = avg_ignore_zero_and_na(sowing_window_df["Tmin"])
avg_maxRh = avg_ignore_zero_and_na(sowing_window_df["max_Rh"])
avg_minRh = avg_ignore_zero_and_na(sowing_window_df["min_Rh"])

# -----------------------------
# Sowing Calendar Advisory
# -----------------------------
month_name = sowing_date.strftime("%B")
fortnight = "1FN" if sowing_date.day <= 15 else "2FN"
match_key = f"{fortnight} {month_name}"

sow_df = sowing_df[sowing_df["District"] == district]
if taluka != "All Talukas" and "Taluka" in sow_df.columns:
    sow_df = sow_df[sow_df["Taluka"] == taluka]
if crop_name:
    sow_df = sow_df[sow_df["Crop"] == crop_name]

advisory_sowing = []
for _, row in sow_df.iterrows():
    cond = str(row["IF condition"]).strip()
    comment = str(row["Comment on Sowing"])
    if match_key.lower() in cond.lower():
        advisory_sowing.append(f"{cond} : {comment}")

if not advisory_sowing:
    advisory_sowing = [f"{fortnight} ({month_name}): Generic sowing advisory (no specific match found)."]

# -----------------------------
# Growth Stage Advisory
# -----------------------------
rules_subset = rules_df.copy()
if crop_name:
    rules_subset = rules_subset[rules_subset["Crop"] == crop_name]

growth_advisories = []
for _, row in rules_subset.iterrows():
    try:
        das_range = str(row["DAS"]).strip()
        if "to" in das_range:
            a, b = [int(x) for x in das_range.replace("-", "to").split("to")]
            if not (a <= DAS <= b):
                continue
        elif das_range.endswith("+"):
            if DAS < int(das_range.replace("+", "")):
                continue
        elif das_range.isnumeric():
            if DAS != int(das_range):
                continue

        ideal_water = row["Ideal Water Required (in mm)"]
        min_w, max_w = None, None
        if isinstance(ideal_water, str) and "to" in ideal_water:
            min_w, max_w = [float(x) for x in ideal_water.replace("-", "to").split("to")]
        elif pd.notna(ideal_water):
            min_w = max_w = float(ideal_water)

        if min_w is not None:
            if rainfall_DAS < min_w:
                advisory_text = f"⚠️ Water Deficit! Consider irrigation. (Rainfall {rainfall_DAS:.1f} mm, Ideal {min_w}-{max_w} mm)"
            elif max_w and rainfall_DAS > max_w:
                advisory_text = f"💧 Excess rainfall, ensure drainage. (Rainfall {rainfall_DAS:.1f} mm)"
            else:
                advisory_text = row["Farmer Advisory"]
        else:
            advisory_text = row["Farmer Advisory"]

        growth_advisories.append(f"{row['Growth Stage']} ({DAS} DAS): {advisory_text}")
    except:
        continue

if not growth_advisories:
    growth_advisories = ["No growth stage advisory found for current DAS."]

# -----------------------------
# Display Results (Landscape Layout)
# -----------------------------
st.subheader("📊 Weather Summary")
wc1, wc2, wc3, wc4, wc5 = st.columns(5)
wc1.metric("🌧 Rainfall (DAS)", f"{rainfall_DAS:.1f} mm")
wc2.metric("🌧 Last 7 Days", f"{rainfall_week:.1f} mm")
wc3.metric("🌧 Last 30 Days", f"{rainfall_month:.1f} mm")
wc4.metric("🌡 Avg Tmax", f"{avg_Tmax:.1f}" if avg_Tmax else "N/A")
wc5.metric("🌡 Avg Tmin", f"{avg_Tmin:.1f}" if avg_Tmin else "N/A")

wr1, wr2 = st.columns(2)
wr1.metric("💧 Avg max_Rh", f"{avg_maxRh:.1f}" if avg_maxRh else "N/A")
wr2.metric("💧 Avg min_Rh", f"{avg_minRh:.1f}" if avg_minRh else "N/A")

st.subheader("🌱 Sowing Advisory")
for adv in advisory_sowing:
    st.write(f"- {adv}")

st.subheader("📖 Growth Stage Advisory")
for adv in growth_advisories:
    st.write(f"- {adv}")
