import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta

st.set_page_config(page_title="🌱 Crop Advisory System", page_icon="🌱", layout="wide")

# -----------------------------
# Helpers
# -----------------------------
def fn_from_date(dt):
    """Return 1FN or 2FN based on date day."""
    return "1FN" if dt.day <= 15 else "2FN"

def detect_date_column(df):
    """Detects the date column by searching for 'date' or 'dd' in column names."""
    for col in df.columns:
        if "date" in col.lower() or "dd" in col.lower():
            return col
    return None

# -----------------------------
# Load Data from GitHub
# -----------------------------
@st.cache_data
def load_data():
    weather_url = "https://github.com/ASHISHSE/App_test/raw/main/weather.xlsx"
    rules_url = "https://github.com/ASHISHSE/App_test/raw/main/rules.xlsx"
    sowing_url = "https://github.com/ASHISHSE/App_test/raw/main/sowing_calendar.xlsx"

    try:
        weather_df = pd.read_excel(weather_url)
        date_col = detect_date_column(weather_df)
        if not date_col:
            st.error("❌ No valid date column found in weather.xlsx (expected something like 'Date' or 'DD-MM-YYYY').")
            return None, None, None

        weather_df["Date_dt"] = pd.to_datetime(weather_df[date_col], errors="coerce")
        weather_df = weather_df.dropna(subset=["Date_dt"]).copy()

        for col in ["Rainfall", "Tmax", "Tmin", "max_Rh", "min_Rh"]:
            if col in weather_df.columns:
                weather_df[col] = pd.to_numeric(weather_df[col], errors="coerce")
    except Exception as e:
        st.error(f"❌ Error loading weather.xlsx: {e}")
        return None, None, None

    try:
        rules_df = pd.read_excel(rules_url)
        if "Crop" in rules_df.columns:
            rules_df["Crop"] = rules_df["Crop"].astype(str).str.strip()
    except Exception as e:
        st.error(f"❌ Error loading rules.xlsx: {e}")
        rules_df = None

    try:
        sowing_df = pd.read_excel(sowing_url)
        for c in ["Crop", "IF condition", "Comments on Sowing"]:
            if c in sowing_df.columns:
                sowing_df[c] = sowing_df[c].astype(str).str.strip()
    except Exception as e:
        st.error(f"❌ Error loading sowing_calendar.xlsx: {e}")
        sowing_df = None

    return weather_df, rules_df, sowing_df

weather_df, rules_df, sowing_df = load_data()
if weather_df is None:
    st.stop()

# -----------------------------
# UI: Location and Crop Selection
# -----------------------------
st.title("🌱 Crop Advisory System")

districts = sorted(weather_df["District"].dropna().unique().tolist()) if "District" in weather_df.columns else []
talukas = sorted(weather_df["Taluka"].dropna().unique().tolist()) if "Taluka" in weather_df.columns else []
circles = sorted(weather_df["Circle"].dropna().unique().tolist()) if "Circle" in weather_df.columns else []

col1, col2, col3 = st.columns(3)
with col1:
    district = st.selectbox("District *", [""] + districts)
    taluka_options = [""] + sorted(weather_df[weather_df["District"] == district]["Taluka"].dropna().unique().tolist()) if district else talukas
    taluka = st.selectbox("Taluka", taluka_options)
    circle_options = [""] + sorted(weather_df[weather_df["Taluka"] == taluka]["Circle"].dropna().unique().tolist()) if taluka else circles
    circle = st.selectbox("Circle", circle_options)

with col2:
    crop = st.selectbox("Crop Name *", [""] + (rules_df["Crop"].dropna().unique().tolist() if rules_df is not None else []))
    sowing_date = st.date_input("Sowing Date", value=date.today() - timedelta(days=30), format="DD/MM/YYYY")
    current_date = st.date_input("Current Date", value=date.today(), format="DD/MM/YYYY")

generate = st.button("🌱 Generate Advisory")

if generate:
    if not district or not crop:
        st.error("Please select all required fields.")
    else:
        sowing_date_str = sowing_date.strftime("%d/%m/%Y")
        current_date_str = current_date.strftime("%d/%m/%Y")
        level = "Circle" if circle else "Taluka" if taluka else "District"
        level_name = circle if circle else taluka if taluka else district

        # Filter weather data based on selected level
        df = weather_df.copy()
        if level == "Circle":
            df = df[df["Circle"] == level_name]
        elif level == "Taluka":
            df = df[df["Taluka"] == level_name]
        else:
            df = df[df["District"] == level_name]

        if df.empty:
            st.warning("No weather data available for this location.")
        else:
            sowing_dt = datetime.strptime(sowing_date_str, "%d/%m/%Y")
            current_dt = datetime.strptime(current_date_str, "%d/%m/%Y")

            # Masks
            week_start = current_dt - timedelta(days=6)
            month_start = current_dt - timedelta(days=29)

            week_mask = (df["Date_dt"] >= week_start) & (df["Date_dt"] <= current_dt)
            month_mask = (df["Date_dt"] >= month_start) & (df["Date_dt"] <= current_dt)
            das_mask = (df["Date_dt"] >= sowing_dt) & (df["Date_dt"] <= current_dt)

            week_data = df[week_mask]
            month_data = df[month_mask]
            das_data = df[das_mask]

            # Metrics
            rainfall_last_week = week_data["Rainfall"].fillna(0).sum() if not week_data.empty else 0.0
            rainfall_last_month = month_data["Rainfall"].fillna(0).sum() if not month_data.empty else 0.0
            rainfall_das = das_data["Rainfall"].fillna(0).sum() if not das_data.empty else 0.0

            rainy_days_week = (week_data["Rainfall"] > 0).sum()
            rainy_days_month = (month_data["Rainfall"] > 0).sum()
            rainy_days_das = (das_data["Rainfall"] > 0).sum()

            def avg_ignore_zero(series):
                s = series.dropna()
                s = s[s != 0]
                return s.mean() if not s.empty else None

            tmax_avg = avg_ignore_zero(das_data["Tmax"]) if "Tmax" in das_data.columns else None
            tmin_avg = avg_ignore_zero(das_data["Tmin"]) if "Tmin" in das_data.columns else None
            max_rh_avg = avg_ignore_zero(das_data["max_Rh"]) if "max_Rh" in das_data.columns else None
            min_rh_avg = avg_ignore_zero(das_data["min_Rh"]) if "min_Rh" in das_data.columns else None

            st.markdown("---")
            st.header("🌤️ Weather Metrics")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Rainfall - Last Week (mm)", f"{rainfall_last_week:.1f}")
                st.metric("Rainy Days (Week)", rainy_days_week)
                st.metric("Rainfall - Last Month (mm)", f"{rainfall_last_month:.1f}")
                st.metric("Rainy Days (Month)", rainy_days_month)
                st.metric("Rainfall - Since Sowing/DAS (mm)", f"{rainfall_das:.1f}")
                st.metric("Rainy Days (Since Sowing)", rainy_days_das)
            with c2:
                st.metric("Tmax Avg (since sowing)", f"{tmax_avg:.1f}" if tmax_avg else "N/A")
                st.metric("Tmin Avg (since sowing)", f"{tmin_avg:.1f}" if tmin_avg else "N/A")
            with c3:
                st.metric("Max RH Avg (since sowing)", f"{max_rh_avg:.1f}" if max_rh_avg else "N/A")
                st.metric("Min RH Avg (since sowing)", f"{min_rh_avg:.1f}" if min_rh_avg else "N/A")

            st.markdown("---")
            st.header("📅 Daily Weather Data (Highlighted Rainy Days)")
            if not das_data.empty:
                display_df = das_data.copy().sort_values("Date_dt")
                display_df["Date"] = display_df["Date_dt"].dt.strftime("%d-%m-%Y")
                columns_to_show = ["Date", "Rainfall", "Tmax", "Tmin", "max_Rh", "min_Rh"]
                display_df = display_df[columns_to_show]

                def highlight_rainy_days(row):
                    return ["background-color: #d0f0c0" if row["Rainfall"] > 0 else "" for _ in row]

                st.dataframe(display_df.style.apply(highlight_rainy_days, axis=1), use_container_width=True)
            else:
                st.info("No daily weather data for selected date range.")

            st.markdown("---")
            st.header("📝 Comment on Sowing")
            if sowing_df is not None:
                fn = fn_from_date(sowing_dt)
                filtered = sowing_df[(sowing_df["Crop"].str.lower() == crop.lower()) &
                                     (sowing_df["IF condition"].str.upper() == fn)]
                if not filtered.empty:
                    for _, row in filtered.iterrows():
                        st.write(f"• {row['Comments on Sowing']}")
                    st.caption(f"(Matched on {fn} for sowing date {sowing_date_str})")
                else:
                    st.warning("No matching sowing comment found for this crop & sowing date.")
            else:
                st.warning("Sowing calendar not available.")

            st.markdown("---")
            st.header("🌱 Growth Stage Advisory")
            if rules_df is not None:
                das = (current_dt - sowing_dt).days
                matched = rules_df[(rules_df["Crop"].str.lower() == crop.lower())]
                found = False
                for _, row in matched.iterrows():
                    das_str = str(row.get("DAS (Days After Sowing)", "")).strip()
                    if "-" in das_str:
                        try:
                            a, b = [int(x.strip()) for x in das_str.split("-")]
                            if a <= das <= b:
                                st.success(f"**Growth Stage:** {row.get('Growth Stage','Unknown')}")
                                st.write(f"**DAS:** {das}")
                                st.write(f"**Ideal Water Required (mm):** {row.get('Ideal Water Required (in mm)','')}")
                                st.write(f"**Farmer Advisory:** {row.get('Farmer Advisory','')}")
                                found = True
                                break
                        except:
                            continue
                if not found:
                    st.info("No matching growth stage found for DAS.")
            else:
                st.warning("Rules data not available.")
