import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="🌱 Crop Advisory System", layout="wide")

# --- Load Data ---
@st.cache_data
def load_data():
    try:
        locations = pd.read_excel("locations.xlsx")
        weather = pd.read_excel("weather.xlsx")
        rules = pd.read_excel("rules.xlsx")
        sowing_calendar = pd.read_excel("sowing_calendar.xlsx")
        return locations, weather, rules, sowing_calendar
    except FileNotFoundError as e:
        st.error(f"Missing required file: {e}")
        st.stop()

locations, weather, rules, sowing_calendar = load_data()

# --- UI Elements ---
st.title("🌱 Crop Advisory System")

st.write("Select a location and crop, enter sowing & current dates, and click Generate Advisory.")

districts = sorted(locations['District'].unique())
district = st.selectbox("District *", ["--Select--"] + districts)

if district != "--Select--":
    taluka_options = sorted(locations[locations['District'] == district]['Taluka'].unique())
else:
    taluka_options = []

taluka = st.selectbox("Taluka", ["--Select--"] + taluka_options)

if taluka != "--Select--":
    circle_options = sorted(locations[(locations['District'] == district) & (locations['Taluka'] == taluka)]['Circle'].dropna().unique())
else:
    circle_options = []

circle = st.selectbox("Circle", ["--Select--"] + circle_options)

crop_name = st.text_input("Crop Name")
sowing_date = st.date_input("Sowing Date (DD-MM-YYYY)")
current_date = st.date_input("Current Date (DD-MM-YYYY)", value=datetime.today())

if st.button("Generate Advisory"):
    das = (current_date - sowing_date).days

    # --- Filter weather data based on selection ---
    if circle != "--Select--":
        weather_sel = weather[weather['Circle'] == circle]
    elif taluka != "--Select--":
        weather_sel = weather[weather['Taluka'] == taluka]
    elif district != "--Select--":
        weather_sel = weather[weather['District'] == district]
    else:
        st.error("Please select at least a District.")
        st.stop()

    # Convert dates and filter by DAS period
    weather_sel['Date'] = pd.to_datetime(weather_sel['Date'], errors='coerce')
    sowing_start = pd.to_datetime(sowing_date)
    current_day = pd.to_datetime(current_date)
    das_weather = weather_sel[(weather_sel['Date'] >= sowing_start) & (weather_sel['Date'] <= current_day)]

    # Clean numeric fields (ignore NaN, 0, blanks)
    def clean_series(s):
        return pd.to_numeric(s, errors='coerce').replace(0, np.nan)

    das_weather['Rainfall'] = clean_series(das_weather['Rainfall'])
    das_weather['Tmax'] = clean_series(das_weather['Tmax'])
    das_weather['Tmin'] = clean_series(das_weather['Tmin'])
    das_weather['max_Rh'] = clean_series(das_weather['max_Rh'])
    das_weather['min_Rh'] = clean_series(das_weather['min_Rh'])

    rainfall_das = das_weather['Rainfall'].sum(skipna=True)
    tmax_avg = das_weather['Tmax'].mean(skipna=True)
    tmin_avg = das_weather['Tmin'].mean(skipna=True)
    max_rh_avg = das_weather['max_Rh'].mean(skipna=True)
    min_rh_avg = das_weather['min_Rh'].mean(skipna=True)

    # --- Display Weather Summary ---
    st.subheader("Weather Summary")
    st.write(f"DAS: {das} days")

    if das_weather['Rainfall'].notna().sum() > 0:
        st.write(f"Cumulative Rainfall (DAS): {rainfall_das:.1f} mm")
    else:
        st.error("❌ No valid rainfall data found for this period.")

    if das_weather['Tmax'].notna().sum() > 0:
        st.write(f"Average Tmax (DAS): {tmax_avg:.1f} °C")
    else:
        st.error("❌ No valid Tmax data found for this period.")

    if das_weather['Tmin'].notna().sum() > 0:
        st.write(f"Average Tmin (DAS): {tmin_avg:.1f} °C")
    else:
        st.error("❌ No valid Tmin data found for this period.")

    if das_weather['max_Rh'].notna().sum() > 0:
        st.write(f"Average max_Rh (DAS): {max_rh_avg:.1f}%")
    else:
        st.error("❌ No valid max_Rh data found for this period.")

    if das_weather['min_Rh'].notna().sum() > 0:
        st.write(f"Average min_Rh (DAS): {min_rh_avg:.1f}%")
    else:
        st.error("❌ No valid min_Rh data found for this period.")

    # --- Sowing Advisory ---
    sow_month = sowing_date.strftime('%B')
    sow_fn = '1FN' if sowing_date.day <= 15 else '2FN'

    sow_advisories = sowing_calendar[(sowing_calendar['Crop'] == crop_name)]
    sow_results = []
    for _, row in sow_advisories.iterrows():
        cond = str(row['Condition']).strip()
        if 'to' in cond:
            start, end = cond.split('to')
            if (sow_fn + ' ' + sow_month) >= start.strip() and (sow_fn + ' ' + sow_month) <= end.strip():
                sow_results.append(row['Advisory'])
        elif cond.startswith('<') and (sow_fn + ' ' + sow_month) < cond[1:].strip():
            sow_results.append(row['Advisory'])
        elif cond.startswith('>') and (sow_fn + ' ' + sow_month) > cond[1:].strip():
            sow_results.append(row['Advisory'])
        elif cond == (sow_fn + ' ' + sow_month):
            sow_results.append(row['Advisory'])

    if sow_results:
        st.subheader("Sowing Advisory")
        for adv in sow_results:
            st.write(f"✅ {adv}")

    # --- Growth Stage Advisory ---
    rule_matches = []
    for _, row in rules.iterrows():
        try:
            das_cond = str(row['DAS']).replace(' ', '')
            if '&' in das_cond:
                lower, upper = das_cond.split('&')
                if eval(f"{das}{lower}") and eval(f"{das}{upper}"):
                    pass
                else:
                    continue
            elif not eval(f"{das}{das_cond}"):
                continue

            ideal_water = pd.to_numeric(row['Ideal Water Required (in mm)'], errors='coerce')
            if pd.notna(ideal_water):
                if rainfall_das < ideal_water:
                    rule_matches.append(row['Advisory'])
            else:
                rule_matches.append(row['Advisory'])
        except Exception:
            continue

    if rule_matches:
        st.subheader("Growth Stage Advisory")
        for adv in rule_matches:
            st.write(f"🌾 {adv}")
