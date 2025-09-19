import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import re

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
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None, None, None
    return weather_df, rules_df, sowing_df

weather_df, rules_df, sowing_df = load_data()
if weather_df is None:
    st.stop()

# -----------------------------
# UI Inputs
# -----------------------------
params = st.query_params

# District / Taluka / Circle selection
districts = sorted(weather_df['District'].dropna().unique())
pref_district = params.get("district", "")
district_index = districts.index(pref_district) + 1 if pref_district in districts else 0
district = st.selectbox("District", ["Select District"] + districts, index=district_index)

if district == "Select District":
    st.stop()

taluka_options = sorted(weather_df.loc[weather_df['District'] == district, 'Taluka'].dropna().unique())
pref_taluka = params.get("taluka", "")
taluka_index = taluka_options.index(pref_taluka) + 1 if pref_taluka in taluka_options else 0
taluka = st.selectbox("Taluka", ["All Talukas"] + taluka_options, index=taluka_index)

circle_options = sorted(weather_df.loc[(weather_df['District'] == district) & ((weather_df['Taluka'] == taluka) | (taluka == "All Talukas")), 'Circle'].dropna().unique())
pref_circle = params.get("circle", "")
circle_index = circle_options.index(pref_circle) + 1 if pref_circle in circle_options else 0
circle = st.selectbox("Circle", ["All Circles"] + circle_options, index=circle_index)

crop_name = st.text_input("Crop Name", value=params.get("crop", ""))
sowing_date = st.date_input("Sowing Date", value=datetime.today() - timedelta(days=30))
current_date = st.date_input("Current Date", value=datetime.today())

# -----------------------------
# Filter data by location
# -----------------------------
loc_df = weather_df.copy()
loc_df = loc_df[loc_df['District'] == district]
if taluka != "All Talukas":
    loc_df = loc_df[loc_df['Taluka'] == taluka]
if circle != "All Circles":
    loc_df = loc_df[loc_df['Circle'] == circle]

loc_df['Date'] = pd.to_datetime(loc_df['Date'], errors='coerce')
loc_df = loc_df.dropna(subset=['Date'])
loc_df = loc_df[loc_df['Date'] <= current_date]

DAS = (current_date - sowing_date).days
sowing_window_df = loc_df[(loc_df['Date'] >= sowing_date) & (loc_df['Date'] <= current_date)]

# Convert columns to numeric and ignore 0/#N/A for averages
for col in ['Rainfall', 'Tmax', 'Tmin', 'max_Rh', 'min_Rh']:
    if col in sowing_window_df:
        sowing_window_df[col] = pd.to_numeric(sowing_window_df[col], errors='coerce')
        if col != 'Rainfall':
            sowing_window_df[col] = sowing_window_df[col].replace(0, np.nan)

# Rainfall sums (0 treated as 0 for rainfall only)
rainfall_DAS = sowing_window_df['Rainfall'].fillna(0).sum()
rainfall_week = loc_df[loc_df['Date'] >= (current_date - timedelta(days=7))]['Rainfall'].fillna(0).sum()
rainfall_month = loc_df[loc_df['Date'] >= (current_date - timedelta(days=30))]['Rainfall'].fillna(0).sum()

# Averages ignoring NaN/0
avg_Tmax = sowing_window_df['Tmax'].dropna().mean()
avg_Tmin = sowing_window_df['Tmin'].dropna().mean()
avg_maxRh = sowing_window_df['max_Rh'].dropna().mean()
avg_minRh = sowing_window_df['min_Rh'].dropna().mean()

# -----------------------------
# Sowing Advisory using Comments on Sowing
# -----------------------------
month_name = sowing_date.strftime("%B")
fortnight = "1FN" if sowing_date.day <= 15 else "2FN"
match_key = f"{fortnight} {month_name}"

sowing_matches = sowing_df[(sowing_df['District'] == district) & ((sowing_df['Taluka'] == taluka) | (taluka == "All Talukas"))]
advisory_sowing = sowing_matches[sowing_matches['Sowing_Window'].str.contains(match_key, na=False)]

# -----------------------------
# Growth Stage Advisory
# -----------------------------
def check_das_condition(rule, das):
    if pd.isna(rule):
        return False
    rule = str(rule).strip()
    if '-' in rule:
        start, end = [int(x) for x in rule.split('-')]
        return start <= das <= end
    elif rule.startswith('<'):
        return das < int(rule[1:])
    elif rule.startswith('>'):
        return das > int(rule[1:])
    return False

rule_matches = rules_df.copy()
rule_matches['Match'] = rule_matches['DAS'].apply(lambda r: check_das_condition(r, DAS))
final_rules = rule_matches[rule_matches['Match']]

if not final_rules.empty:
    final_rules['Advisory'] = final_rules.apply(
        lambda x: x['Advisory'] if rainfall_DAS < x['Ideal Water Required (mm)'] else "No additional irrigation required",
        axis=1,
    )

# -----------------------------
# Display Results
# -----------------------------
st.header("📊 Weather Metrics")
with st.container():
    c1, c2, c3 = st.columns(3)
    c1.metric("Rainfall - Last Week", f"{rainfall_week:.1f}")
    c2.metric("Rainfall - Last Month", f"{rainfall_month:.1f}")
    c3.metric("Rainfall - Since Sowing/DAS", f"{rainfall_DAS:.1f}")

    c4, c5 = st.columns(2)
    c4.metric("Tmax Avg (since sowing)", f"{avg_Tmax:.1f}" if not np.isnan(avg_Tmax) else "N/A")
    c5.metric("Tmin Avg (since sowing)", f"{avg_Tmin:.1f}" if not np.isnan(avg_Tmin) else "N/A")

    c6, c7 = st.columns(2)
    c6.metric("Max Rh Avg (since sowing)", f"{avg_maxRh:.1f}" if not np.isnan(avg_maxRh) else "N/A")
    c7.metric("Min Rh Avg (since sowing)", f"{avg_minRh:.1f}" if not np.isnan(avg_minRh) else "N/A")

st.header("🌱 Sowing Advisory")
if not advisory_sowing.empty:
    for _, row in advisory_sowing.iterrows():
        if 'Comments on Sowing' in row:
            st.markdown(f"- **{row['Comments on Sowing']}**")
else:
    st.info("No sowing advisory found for this window.")

st.header("📖 Growth Stage Advisory")
if not final_rules.empty:
    for _, row in final_rules.iterrows():
        st.markdown(f"- **{row['Advisory']}**")
else:
    st.info("No matching growth stage advisory.")
