import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
from io import BytesIO

st.set_page_config(page_title="Crop Advisory System", page_icon="🌱", layout="wide")

# -----------------------------
# Helper Functions
# -----------------------------
def safe_sum(series):
    series = series.replace([0, -99, -999], np.nan).dropna()
    return series.sum(skipna=True) if not series.empty else np.nan

def safe_avg(series):
    series = series.replace([0, -99, -999], np.nan).dropna()
    return series.mean() if not series.empty else np.nan

@st.cache_data
def load_data():
    weather_url = "https://github.com/ASHISHSE/App_test/raw/main/weather.xlsx"
    wres = requests.get(weather_url, timeout=10)
    weather_df = pd.read_excel(BytesIO(wres.content))

    # ✅ Handle Date column
    if "Date(DD-MM-YYYY)" in weather_df.columns:
        weather_df["Date_dt"] = pd.to_datetime(weather_df["Date(DD-MM-YYYY)"], format="%d-%m-%Y", errors="coerce")
    else:
        weather_df["Date_dt"] = pd.to_datetime(weather_df["Date"], dayfirst=True, errors="coerce")

    # Convert numeric columns
    for col in ["Rainfall", "Tmax", "Tmin", "max_Rh", "min_Rh"]:
        if col in weather_df.columns:
            weather_df[col] = pd.to_numeric(weather_df[col], errors="coerce")

    for c in ["District", "Taluka", "Circle"]:
        if c in weather_df.columns:
            weather_df[c] = weather_df[c].astype(str).str.strip()

    weather_df.dropna(subset=["Date_dt"], inplace=True)
    return weather_df

weather_df = load_data()

# -----------------------------
# Accurate Metric Calculation
# -----------------------------
def calculate_weather_metrics(weather_data, level, name, sowing_date_str, current_date_str):
    df = weather_data.copy()

    # Filter by selected location level
    if level == "Circle":
        df = df[df["Circle"] == name]
    elif level == "Taluka":
        df = df[df["Taluka"] == name]
    else:
        df = df[df["District"] == name]

    if df.empty:
        return {k: np.nan for k in ["das","rainfall_last_week","rainfall_last_month","rainfall_das","tmax_avg","tmin_avg","max_rh_avg","min_rh_avg"]}

    sowing_dt = datetime.strptime(sowing_date_str, "%d/%m/%Y")
    current_dt = datetime.strptime(current_date_str, "%d/%m/%Y")
    das = (current_dt - sowing_dt).days if current_dt >= sowing_dt else 0

    # ✅ Inclusive date filtering
    df_since_sowing = df[(df["Date_dt"] >= sowing_dt) & (df["Date_dt"] <= current_dt)]

    # ✅ Rainfall calculations
    last_week_start = current_dt - timedelta(days=6)
    last_month_start = current_dt - timedelta(days=29)

    rainfall_last_week = safe_sum(df[(df["Date_dt"] >= last_week_start) & (df["Date_dt"] <= current_dt)]["Rainfall"])
    rainfall_last_month = safe_sum(df[(df["Date_dt"] >= last_month_start) & (df["Date_dt"] <= current_dt)]["Rainfall"])
    rainfall_das = safe_sum(df_since_sowing["Rainfall"])

    # ✅ Averages since sowing
    tmax_avg = safe_avg(df_since_sowing["Tmax"])
    tmin_avg = safe_avg(df_since_sowing["Tmin"])
    max_rh_avg = safe_avg(df_since_sowing["max_Rh"])
    min_rh_avg = safe_avg(df_since_sowing["min_Rh"])

    return {
        "das": das,
        "rainfall_last_week": np.round(rainfall_last_week, 1) if not np.isnan(rainfall_last_week) else None,
        "rainfall_last_month": np.round(rainfall_last_month, 1) if not np.isnan(rainfall_last_month) else None,
        "rainfall_das": np.round(rainfall_das, 1) if not np.isnan(rainfall_das) else None,
        "tmax_avg": np.round(tmax_avg, 1) if not np.isnan(tmax_avg) else None,
        "tmin_avg": np.round(tmin_avg, 1) if not np.isnan(tmin_avg) else None,
        "max_rh_avg": np.round(max_rh_avg, 1) if not np.isnan(max_rh_avg) else None,
        "min_rh_avg": np.round(min_rh_avg, 1) if not np.isnan(min_rh_avg) else None,
    }

# -----------------------------
# UI
# -----------------------------
st.title("🌱 Crop Weather & Advisory Dashboard")

district = st.selectbox("Select District", sorted(weather_df["District"].unique()))
circle = st.selectbox("Select Circle", sorted(weather_df["Circle"].unique()))
sowing_date = st.date_input("Sowing Date (dd/mm/yyyy)", value=datetime.today() - timedelta(days=20))
current_date = st.date_input("Current Date (dd/mm/yyyy)", value=datetime.today())

metrics = calculate_weather_metrics(
    weather_df, level="Circle", name=circle,
    sowing_date_str=sowing_date.strftime("%d/%m/%Y"),
    current_date_str=current_date.strftime("%d/%m/%Y")
)

# -----------------------------
# Display Metrics in Cards (Farmer-Friendly)
# -----------------------------
st.subheader("📊 Weather Metrics")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("DAS (Days After Sowing)", f"{metrics['das']} days")
    st.metric("Rainfall - Last Week", f"{metrics['rainfall_last_week']} mm")
with col2:
    st.metric("Rainfall - Last Month", f"{metrics['rainfall_last_month']} mm")
    st.metric("Rainfall - Since Sowing", f"{metrics['rainfall_das']} mm")
with col3:
    st.metric("Tmax Avg (Since Sowing)", f"{metrics['tmax_avg']} °C")
    st.metric("Tmin Avg (Since Sowing)", f"{metrics['tmin_avg']} °C")
    st.metric("Max RH Avg", f"{metrics['max_rh_avg']} %")
    st.metric("Min RH Avg", f"{metrics['min_rh_avg']} %")
