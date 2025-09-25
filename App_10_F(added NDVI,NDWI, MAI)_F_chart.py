import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime, date, timedelta
import requests
from io import BytesIO
import matplotlib.pyplot as plt

st.set_page_config(page_title="Crop Advisory System", page_icon="🌱", layout="wide")

# -------------------------
# Load Data First
# ----------------------------
@st.cache_data
def load_data():
    weather_url = "https://github.com/ASHISHSE/App_test/raw/main/weather.xlsx"
    rules_url = "https://github.com/ASHISHSE/App_test/raw/main/rules.xlsx"
    sowing_url = "https://github.com/ASHISHSE/App_test/raw/main/sowing_calendar1.xlsx"
    indicator_url = "https://github.com/ASHISHSE/App_test/raw/main/Circlewise_Data_Matrix_Indicator_2024_v1.xlsx"

    wres = requests.get(weather_url, timeout=10)
    rres = requests.get(rules_url, timeout=10)
    sres = requests.get(sowing_url, timeout=10)
    ires = requests.get(indicator_url, timeout=10)

    weather_df = pd.read_excel(BytesIO(wres.content))
    rules_df = pd.read_excel(BytesIO(rres.content))
    sowing_df = pd.read_excel(BytesIO(sres.content))
    indicator_df = pd.read_excel(BytesIO(ires.content))

    # ✅ Flexible date detection
    date_col = None
    for candidate in ["Date(DD-MM-YYYY)", "DD-MM-YYYY", "Date"]:
        if candidate in weather_df.columns:
            date_col = candidate
            break
    if date_col is None:
        raise ValueError("weather.xlsx must have a column named 'Date(DD-MM-YYYY)' or 'DD-MM-YYYY' or 'Date'")

    weather_df["Date_dt"] = pd.to_datetime(weather_df[date_col], format="%d-%m-%Y", errors="coerce")
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

    return weather_df, rules_df, sowing_df, indicator_df, districts, talukas, circles, crops


weather_df, rules_df, sowing_df, indicator_df, districts, talukas, circles, crops = load_data()

# -----------------------------
# Helper Functions
# -----------------------------
def fn_from_date(dt):
    return f"1FN {dt.strftime('%B')}" if dt.day <= 15 else f"2FN {dt.strftime('%B')}"

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
    except:
        return False

def parse_condition_with_dates(cond_str):
    match = re.search(r"\((\d{2}-\d{2}-\d{4})\s+to\s+(\d{2}-\d{2}-\d{4})\)", cond_str)
    if match:
        return datetime.strptime(match.group(1), "%d-%m-%Y"), datetime.strptime(match.group(2), "%d-%m-%Y")
    return None, None

def match_condition_with_dates(sowing_date, cond_str):
    start_date, end_date = parse_condition_with_dates(cond_str)
    return start_date and end_date and start_date <= sowing_date <= end_date

def match_condition(sowing_date, cond_str):
    return fn_from_date(sowing_date).lower() in normalize_fn_string(cond_str).lower()

def get_sowing_comments(sowing_date_str, district, taluka, circle, crop, sowing_df):
    if sowing_df.empty:
        return []
    sowing_dt = datetime.strptime(sowing_date_str, "%d/%m/%Y")
    filters = [
        (sowing_df["District"] == district) & (sowing_df["Taluka"] == taluka) & (sowing_df["Circle"] == circle) & (sowing_df["Crop"] == crop),
        (sowing_df["District"] == district) & (sowing_df["Taluka"] == taluka) & (sowing_df["Crop"] == crop),
        (sowing_df["District"] == district) & (sowing_df["Crop"] == crop),
    ]
    for f in filters:
        subset = sowing_df[f]
        if not subset.empty:
            for _, row in subset.iterrows():
                cond = str(row.get("IF condition", "")).strip()
                if match_condition_with_dates(sowing_dt, cond) or match_condition(sowing_dt, cond):
                    return [{"matched_fn": fn_from_date(sowing_dt), "comment": row.get("Comments on Sowing", "")}]
    return []

def calculate_weather_metrics(weather_data, level, name, sowing_date_str, current_date_str):
    df = weather_data.copy()
    if level == "Circle": df = df[df["Circle"] == name]
    elif level == "Taluka": df = df[df["Taluka"] == name]
    elif level == "District": df = df[df["District"] == name]

    sowing_dt = datetime.strptime(sowing_date_str, "%d/%m/%Y")
    current_dt = datetime.strptime(current_date_str, "%d/%m/%Y")
    das = max((current_dt - sowing_dt).days, 0)
    das_mask = (df["Date_dt"] >= sowing_dt) & (df["Date_dt"] <= current_dt)
    week_start, month_start = current_dt - timedelta(days=6), current_dt - timedelta(days=29)

    das_data = df.loc[das_mask]
    week_data = df[(df["Date_dt"] >= week_start) & (df["Date_dt"] <= current_dt)]
    month_data = df[(df["Date_dt"] >= month_start) & (df["Date_dt"] <= current_dt)]

    avg = lambda s: float(pd.to_numeric(s, errors="coerce").replace(0, np.nan).dropna().mean()) if not s.empty else None
    return {
        "rainfall_das": das_data["Rainfall"].sum() if "Rainfall" in das_data else 0,
        "rainfall_last_week": week_data["Rainfall"].sum() if "Rainfall" in week_data else 0,
        "rainfall_last_month": month_data["Rainfall"].sum() if "Rainfall" in month_data else 0,
        "rainy_days_das": (das_data["Rainfall"] > 0).sum() if "Rainfall" in das_data else 0,
        "rainy_days_week": (week_data["Rainfall"] > 0).sum() if "Rainfall" in week_data else 0,
        "rainy_days_month": (month_data["Rainfall"] > 0).sum() if "Rainfall" in month_data else 0,
        "tmax_avg": avg(das_data["Tmax"]) if "Tmax" in das_data else None,
        "tmin_avg": avg(das_data["Tmin"]) if "Tmin" in das_data else None,
        "max_rh_avg": avg(das_data["max_Rh"]) if "max_Rh" in das_data else None,
        "min_rh_avg": avg(das_data["min_Rh"]) if "min_Rh" in das_data else None,
        "das": das,
        "das_data": das_data
    }

# -----------------------------
# UI with Tabs
# -----------------------------
tab1, tab2 = st.tabs(["🌱 Crop Advisory", "📊 Monthly Indicator Comparison"])

with tab1:
    st.title("🌱 Crop Advisory System") 
    st.markdown("<span style='color: red; font-weight: bold;'>⚠️ Testing Version:</span> Data uploaded from <b>01 June 2024</b> to <b>31 Oct 2024</b>. Please select (Sowing & Current) dates within this range.", unsafe_allow_html=True)

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

            st.subheader("🌤️ Weather Metrics")
            st.metric("Rainfall - Last Week (mm)", f"{metrics['rainfall_last_week']:.1f}")
            st.metric("Rainfall - Last Month (mm)", f"{metrics['rainfall_last_month']:.1f}")

            st.subheader("📅 Daily Weather Data")
            if not metrics["das_data"].empty:
                display_df = metrics["das_data"].copy().sort_values("Date_dt")
                display_df["Date"] = display_df["Date_dt"].dt.strftime("%d-%m-%Y")
                st.dataframe(display_df[["Date", "Rainfall", "Tmax", "Tmin", "max_Rh", "min_Rh"]], use_container_width=True)

            st.subheader("📝 Comment on Sowing")
            comments = get_sowing_comments(sowing_date_str, district, taluka, circle, crop, sowing_df)
            if comments:
                for c in comments:
                    st.write(f"**Matched:** {c['matched_fn']} • {c['comment']}")
            else:
                st.info("No matching sowing comments found.")

with tab2:
    st.header("📊 Monthly Indicator Comparison")
    districts_i = indicator_df["District"].unique()
    selected_district = st.selectbox("Select District", options=districts_i)
    talukas_i = indicator_df[indicator_df["District"] == selected_district]["Taluka"].unique()
    selected_taluka = st.selectbox("Select Taluka", options=talukas_i)
    circles_i = indicator_df[(indicator_df["District"] == selected_district) & (indicator_df["Taluka"] == selected_taluka)]["Circle"].unique()
    selected_circle = st.selectbox("Select Circle", options=circles_i)

    filtered_df = indicator_df[
        (indicator_df["District"] == selected_district) &
        (indicator_df["Taluka"] == selected_taluka) &
        (indicator_df["Circle"] == selected_circle)
    ]

    indicator_cols = [c for c in filtered_df.columns if c.startswith("Indicator-")]
    monthly_df = pd.DataFrame()
    monthly_df["Month"] = [c.split("_")[-1] for c in indicator_cols]
    for c in indicator_cols:
        monthly_df[c] = filtered_df[c].apply(lambda x: x if str(x) in ["Good", "Moderate", "Poor"] else None).values

    st.dataframe(monthly_df, use_container_width=True)

    for c in indicator_cols:
        st.markdown(f"**{c}**")
        value_counts = monthly_df[c].value_counts()
        fig, ax = plt.subplots(figsize=(5, 3))
        value_counts.plot(kind="bar", ax=ax, color=["green", "orange", "red"])
        ax.set_ylabel("Count")
        ax.set_xlabel("Category")
        ax.set_title(f"{c} (Good/Moderate/Poor)")
        st.pyplot(fig)

st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; font-size: 16px; margin-top: 20px;'>
        💻 <b>Developed by:</b> Ashish Selokar <br>
        📧 For suggestions or queries, please email at: <a href="mailto:ashish111.selokar@gmail.com">ashish111.selokar@gmail.com</a> <br><br>
        <span style="font-size:15px; color:green;">
        🌾 Empowering Farmers with Data-Driven Insights 🌾
        </span><br>
        <span style="font-size:13px; color:gray;">
        Version 1.0 | Powered by Agricose | Last Updated: Sept 2025
        </span>
    </div>
    """,
    unsafe_allow_html=True
)
