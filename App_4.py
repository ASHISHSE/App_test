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

        # Normalize dates
        if 'Date(DDMMYY)' in weather_df.columns:
            def conv_ddmmyy(x):
                try:
                    s = str(int(x)).zfill(6)
                    return datetime.strptime(s, "%d%m%y")
                except:
                    return None
            weather_df['Date'] = weather_df['Date(DDMMYY)'].apply(conv_ddmmyy)
        elif 'Date' in weather_df.columns:
            weather_df['Date'] = pd.to_datetime(weather_df['Date'], dayfirst=True, errors='coerce')

        for c in ['District', 'Taluka', 'Circle', 'Crop']:
            if c in weather_df.columns:
                weather_df[c] = weather_df[c].astype(str).str.strip()

        for col in ['Rainfall', 'Tmax', 'Tmin', 'max_Rh', 'min_Rh']:
            if col in weather_df.columns:
                weather_df[col] = pd.to_numeric(weather_df[col], errors='coerce')

        # Clean column names
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
# UI Inputs - Show all dropdowns at once
# -----------------------------
params = st.query_params
districts = sorted(weather_df['District'].dropna().unique())
district = st.selectbox("District", ["Select District"] + districts)

taluka_options = sorted(weather_df.loc[weather_df['District'] == district, 'Taluka'].dropna().unique()) if district != "Select District" else []
taluka = st.selectbox("Taluka", ["All Talukas"] + taluka_options)

circle_options = sorted(weather_df.loc[
    (weather_df['District'] == district) &
    ((weather_df['Taluka'] == taluka) | (taluka == "All Talukas")),
    'Circle'
].dropna().unique()) if district != "Select District" else []
circle = st.selectbox("Circle", ["All Circles"] + circle_options)

crop_list = sorted(rules_df['Crop'].dropna().unique()) if 'Crop' in rules_df.columns else []
crop_name = st.selectbox("Crop Name", [""] + crop_list)

sowing_date = st.date_input("Sowing Date (DD-MM-YYYY)", value=datetime.today() - timedelta(days=30))
current_date = st.date_input("Current Date (DD-MM-YYYY)", value=datetime.today())

if district == "Select District":
    st.stop()

# -----------------------------
# Filter data by location & date
# -----------------------------
loc_df = weather_df.copy()
loc_df = loc_df[loc_df['District'] == district]
if taluka != "All Talukas":
    loc_df = loc_df[loc_df['Taluka'] == taluka]
if circle != "All Circles":
    loc_df = loc_df[loc_df['Circle'] == circle]

loc_df = loc_df.dropna(subset=['Date(DDMMYY)'])
loc_df = loc_df[loc_df['Date(DDMMYY)'] <= current_date]

DAS = (current_date - sowing_date).days
sowing_window_df = loc_df[(loc_df['Date(DDMMYY)'] >= sowing_date) & (loc_df['Date(DDMMYY)'] <= current_date)].copy()

for col in ['Rainfall', 'Tmax', 'Tmin', 'max_Rh', 'min_Rh']:
    if col in sowing_window_df.columns:
        sowing_window_df[col] = pd.to_numeric(sowing_window_df[col], errors='coerce').replace(0, np.nan)

rainfall_DAS = sowing_window_df['Rainfall'].fillna(0).sum()
rainfall_week = loc_df[loc_df['Date'] >= (current_date - timedelta(days=7))]['Rainfall'].fillna(0).sum()
rainfall_month = loc_df[loc_df['Date'] >= (current_date - timedelta(days=30))]['Rainfall'].fillna(0).sum()

avg_Tmax = sowing_window_df['Tmax'].dropna().mean()
avg_Tmin = sowing_window_df['Tmin'].dropna().mean()
avg_maxRh = sowing_window_df['max_Rh'].dropna().mean()
avg_minRh = sowing_window_df['min_Rh'].dropna().mean()

# -----------------------------
# Sowing Advisory (using Comments on Sowing)
# -----------------------------
month_name = sowing_date.strftime("%B")
fortnight = "1FN" if sowing_date.day <= 15 else "2FN"
match_key = f"{fortnight} {month_name}"

advisory_sowing = []
if 'IF condition' in sowing_df.columns and 'Comments on Sowing' in sowing_df.columns:
    sow_matches = sowing_df[
        (sowing_df['District'] == district) &
        ((sowing_df['Taluka'] == taluka) | (taluka == "All Talukas"))
    ]
    for _, row in sow_matches.iterrows():
        cond = str(row['IF condition']).strip()
        if match_key.lower() in cond.lower():
            advisory_sowing.append(row['Comments on Sowing'])

if not advisory_sowing:
    advisory_sowing = [f"No specific advisory found. General recommendation for {match_key}."]

# -----------------------------
# Growth Stage Advisory
# -----------------------------
rules_cols = {c.lower(): c for c in rules_df.columns}
def rcol(part): return next((v for k, v in rules_cols.items() if part in k), None)

col_das = rcol("das")
col_growth = rcol("growth")
col_ideal_water = rcol("ideal")
col_advisory = rcol("advisory")

growth_advisories = []
if col_das:
    for _, row in rules_df.iterrows():
        das_rule = str(row[col_das]).strip()
        try:
            if "-" in das_rule:
                start, end = [int(x) for x in das_rule.split('-')]
                match = start <= DAS <= end
            elif das_rule.endswith('+'):
                match = DAS >= int(das_rule[:-1])
            else:
                match = DAS == int(das_rule)
        except:
            match = False
        if match:
            required = float(row[col_ideal_water]) if pd.notna(row[col_ideal_water]) else None
            if required and rainfall_DAS < required:
                growth_advisories.append(f"{row[col_growth]} ({DAS} DAS): {row[col_advisory]}")
            else:
                growth_advisories.append(f"{row[col_growth]} ({DAS} DAS): No additional irrigation required.")

if not growth_advisories:
    growth_advisories = ["No matching growth stage advisory found."]

# -----------------------------
# Display Results
# -----------------------------
st.subheader("📊 Weather Summary")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Rainfall (DAS)", f"{rainfall_DAS:.1f} mm")
c2.metric("Rainfall (7d)", f"{rainfall_week:.1f} mm")
c3.metric("Rainfall (30d)", f"{rainfall_month:.1f} mm")
c4.metric("Avg Tmax", f"{avg_Tmax:.1f}" if not np.isnan(avg_Tmax) else "N/A")
c5.metric("Avg Tmin", f"{avg_Tmin:.1f}" if not np.isnan(avg_Tmin) else "N/A")

d1, d2 = st.columns(2)
d1.metric("Avg maxRh", f"{avg_maxRh:.1f}" if not np.isnan(avg_maxRh) else "N/A")
d2.metric("Avg minRh", f"{avg_minRh:.1f}" if not np.isnan(avg_minRh) else "N/A")

st.subheader("🌱 Sowing Advisory")
for adv in advisory_sowing:
    st.write(f"- {adv}")

st.subheader("📖 Growth Stage Advisory")
for adv in growth_advisories:
    st.write(f"- {adv}")

