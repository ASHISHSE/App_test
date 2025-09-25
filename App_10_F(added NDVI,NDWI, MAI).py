import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime, date, timedelta
import requests
from io import BytesIO
import plotly.express as px

st.set_page_config(page_title="🌱 Crop Advisory System", page_icon="🌱", layout="wide")

# -----------------------------
# LOAD DATA (WEATHER, RULES, SOWING)
# -----------------------------
@st.cache_data
def load_data():
    weather_url = "https://github.com/ASHISHSE/App_test/raw/main/weather.xlsx"
    rules_url = "https://github.com/ASHISHSE/App_test/raw/main/rules.xlsx"
    sowing_url = "https://github.com/ASHISHSE/App_test/raw/main/sowing_calendar1.xlsx"

    wres = requests.get(weather_url, timeout=10)
    rres = requests.get(rules_url, timeout=10)
    sres = requests.get(sowing_url, timeout=10)

    weather_df = pd.read_excel(BytesIO(wres.content))
    rules_df = pd.read_excel(BytesIO(rres.content))
    sowing_df = pd.read_excel(BytesIO(sres.content))

    # Flexible date column detection
    date_col = None
    for candidate in ["Date(DD-MM-YYYY)", "DD-MM-YYYY", "Date"]:
        if candidate in weather_df.columns:
            date_col = candidate
            break
    if date_col is None:
        raise ValueError("weather.xlsx must have a column named 'Date(DD-MM-YYYY)' or similar")

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

    return weather_df, rules_df, sowing_df, districts, talukas, circles, crops


# Load data before UI
weather_df, rules_df, sowing_df, districts, talukas, circles, crops = load_data()

# -----------------------------
# LOAD CIRCLEWISE DATA MATRIX
# -----------------------------
@st.cache_data
def load_circlewise_data():
    url = "https://github.com/ASHISHSE/App_test/raw/main/Circlewise_Data_Matrix_Indicator_2024_v1.xlsx"
    res = requests.get(url, timeout=10)
    df = pd.read_excel(BytesIO(res.content))
    return df

circlewise_df = load_circlewise_data()

# -----------------------------
# HELPER FUNCTIONS
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

def parse_condition_with_dates(cond_str):
    match = re.search(r"\((\d{2}-\d{2}-\d{4})\s+to\s+(\d{2}-\d{2}-\d{4})\)", cond_str)
    if match:
        start = datetime.strptime(match.group(1), "%d-%m-%Y")
        end = datetime.strptime(match.group(2), "%d-%m-%Y")
        return start, end
    return None, None

def match_condition_with_dates(sowing_date, cond_str):
    start_date, end_date = parse_condition_with_dates(cond_str)
    if start_date and end_date:
        return start_date <= sowing_date <= end_date
    return False

def match_condition(sowing_date, cond_str):
    cond = normalize_fn_string(cond_str).lower()
    fn = fn_from_date(sowing_date).lower()
    return fn in cond

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
                    matched_fn = fn_from_date(sowing_dt)
                    return [{"matched_fn": matched_fn, "comment": row.get("Comments on Sowing", "")}]
    return []

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

    das_data = df.loc[das_mask]
    week_data = df.loc[(df["Date_dt"] >= week_start) & (df["Date_dt"] <= current_dt)]
    month_data = df.loc[(df["Date_dt"] >= month_start) & (df["Date_dt"] <= current_dt)]

    def avg_ignore_zero_and_na(series):
        s = pd.to_numeric(series, errors="coerce").dropna()
        s = s[s != 0]
        return float(s.mean()) if not s.empty else None

    return {
        "rainfall_das": das_data["Rainfall"].sum() if "Rainfall" in das_data else 0,
        "rainfall_last_week": week_data["Rainfall"].sum() if "Rainfall" in week_data else 0,
        "rainfall_last_month": month_data["Rainfall"].sum() if "Rainfall" in month_data else 0,
        "rainy_days_das": (das_data["Rainfall"] > 0).sum() if "Rainfall" in das_data else 0,
        "rainy_days_week": (week_data["Rainfall"] > 0).sum() if "Rainfall" in week_data else 0,
        "rainy_days_month": (month_data["Rainfall"] > 0).sum() if "Rainfall" in month_data else 0,
        "tmax_avg": avg_ignore_zero_and_na(das_data["Tmax"]) if "Tmax" in das_data else None,
        "tmin_avg": avg_ignore_zero_and_na(das_data["Tmin"]) if "Tmin" in das_data else None,
        "max_rh_avg": avg_ignore_zero_and_na(das_data["max_Rh"]) if "max_Rh" in das_data else None,
        "min_rh_avg": avg_ignore_zero_and_na(das_data["min_Rh"]) if "min_Rh" in das_data else None,
        "das": das,
        "das_data": das_data
    }

def get_growth_advisory(crop, das, rainfall_das, rules_df):
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
# FILTER FUNCTION FOR CIRCLEWISE DATA
# -----------------------------
def get_circlewise_data(district, taluka, circle, sowing_date, current_date):
    df = circlewise_df.copy()
    df = df[(df["DTENAME"] == district) & (df["THENAME"] == taluka)]
    if circle:
        df = df[df["CIRNAME"] == circle]
    if df.empty:
        return pd.DataFrame()

    months = pd.date_range(start=sowing_date.replace(day=1),
                           end=current_date.replace(day=1),
                           freq='MS').strftime("%B").tolist()
    selected_cols = ["DTENAME", "THENAME", "CIRNAME"]

    for month in months:
        pattern = fr"(NDVI|NDWI|RAINFALL_DEV|MAI|Indicator).*{month}_2024"
        month_cols = [c for c in df.columns if re.search(pattern, c)]
        selected_cols.extend(month_cols)

    df = df[selected_cols]
    return df

# -----------------------------
# UI - SELECTIONS
# -----------------------------
st.markdown(
    "<span style='color: red; font-weight: bold;'>⚠️ Testing Version:</span> "
    "Data uploaded from <b>01 June 2024</b> to <b>31 Oct 2024</b>. "
    "Please select (Sowing & Current) dates within this range.",
    unsafe_allow_html=True
)

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

# -----------------------------
# MAIN LOGIC
# -----------------------------
if generate:
    if not district or not crop:
        st.error("Please select all required fields.")
    else:
        sowing_date_str = sowing_date.strftime("%d/%m/%Y")
        current_date_str = current_date.strftime("%d/%m/%Y")
        level = "Circle" if circle else "Taluka" if taluka else "District"
        level_name = circle if circle else taluka if taluka else district

        metrics = calculate_weather_metrics(weather_df, level, level_name, sowing_date_str, current_date_str)
        das_data = metrics["das_data"]

        # Weather Metrics
        st.markdown("---")
        st.header("🌤️ Weather Metrics")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Rainfall - Last Week (mm)", f"{metrics['rainfall_last_week']:.1f}")
            st.metric("Rainy Days - Last Week", metrics["rainy_days_week"])
            st.metric("Rainfall - Last Month (mm)", f"{metrics['rainfall_last_month']:.1f}")
            st.metric("Rainy Days - Last Month", metrics["rainy_days_month"])
        with c2:
            st.metric("Rainfall - Since Sowing (mm)", f"{metrics['rainfall_das']:.1f}")
            st.metric("Rainy Days - Since Sowing", metrics["rainy_days_das"])
            st.metric("Tmax Avg", f"{metrics['tmax_avg']:.1f}" if metrics['tmax_avg'] else "N/A")
            st.metric("Tmin Avg", f"{metrics['tmin_avg']:.1f}" if metrics['tmin_avg'] else "N/A")
        with c3:
            st.metric("Max RH Avg", f"{metrics['max_rh_avg']:.1f}" if metrics['max_rh_avg'] else "N/A")
            st.metric("Min RH Avg", f"{metrics['min_rh_avg']:.1f}" if metrics['min_rh_avg'] else "N/A")

        # Daily Weather
        st.markdown("---")
        st.header("📅 Daily Weather Data (Highlighted Rainy Days)")
        if not das_data.empty:
            display_df = das_data.copy().sort_values("Date_dt")
            display_df["Date"] = display_df["Date_dt"].dt.strftime("%d-%m-%Y")
            columns_to_show = ["Date", "Rainfall", "Tmax", "Tmin", "max_Rh", "min_Rh"]
            display_df = display_df[[c for c in columns_to_show if c in display_df.columns]]

            def highlight_rainy_days(row):
                return ["background-color: #0ea6ff" if row["Rainfall"] > 0 else "" for _ in row]

            st.dataframe(display_df.style.apply(highlight_rainy_days, axis=1), use_container_width=True)
        else:
            st.info("No daily weather data for selected date range.")

        # Sowing Comments
        st.markdown("---")
        st.header("📝 Comment on Sowing")
        comments = get_sowing_comments(sowing_date_str, district, taluka, circle, crop, sowing_df)
        if comments:
            for c in comments:
                st.write(f"**Matched:** {c['matched_fn']}")
                st.write(f"• {c['comment']}")
        else:
            st.write("No matching sowing comments found.")

        # Growth Stage
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

        # Circlewise Data Matrix
        st.markdown("---")
        st.header("📊 Circlewise Data Matrix (NDVI, NDWI, Rainfall Dev, MAI, Indicators)")
        matrix_data = get_circlewise_data(district, taluka, circle, sowing_date, current_date)
        if not matrix_data.empty:
            def color_categories(val):
                if isinstance(val, str):
                    if val.lower() == "good":
                        return "background-color: #b6fcb6"
                    elif val.lower() == "moderate":
                        return "background-color: #fff59d"
                    elif val.lower() == "poor":
                        return "background-color: #ff9999"
                return ""

            st.dataframe(matrix_data.style.applymap(color_categories), use_container_width=True)

            # NDVI/NDWI Trend
            st.subheader("📈 NDVI & NDWI Trend")
            trend_df = matrix_data.melt(id_vars=["DTENAME", "THENAME", "CIRNAME"],
                                        var_name="Parameter_Month", value_name="Value")
            trend_df = trend_df[trend_df["Value"].apply(lambda x: isinstance(x, (int, float, np.number)))]
            if not trend_df.empty:
                trend_df[["Parameter", "Month"]] = trend_df["Parameter_Month"].str.extract(r"(NDVI|NDWI).*([A-Za-z]+)_2024")
                fig = px.line(trend_df, x="Month", y="Value", color="Parameter",
                              markers=True, title="NDVI & NDWI Monthly Trend")
                fig.update_layout(xaxis_title="Month", yaxis_title="Index Value", template="plotly_white")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No numeric NDVI/NDWI values found for plotting.")
        else:
            st.info("No Circlewise Data Matrix available for selected range.")

        st.markdown("---")
        st.markdown("""
        <div style='text-align: center; font-size: 16px; margin-top: 20px;'>
        💻 <b>Developed by:</b> Ashish Selokar <br>
        📧 For suggestions or queries, email: 
        <
