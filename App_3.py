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

        # read remote files
        weather_df = pd.read_excel(weather_url)
        rules_df = pd.read_excel(rules_url)
        sowing_df = pd.read_excel(sowing_url)

        # Normalize weather date column (try multiple possible column names)
        if 'Date(DDMMYY)' in weather_df.columns:
            # convert numeric ddmmyy -> dd-mm-YYYY
            def conv_ddmmyy(x):
                try:
                    s = str(int(x)).zfill(6)
                    return datetime.strptime(s, "%d%m%y").strftime("%d-%m-%Y")
                except Exception:
                    return None
            weather_df['Date'] = weather_df['Date(DDMMYY)'].apply(conv_ddmmyy)
        elif 'Date' in weather_df.columns:
            # try converting existing Date column to dd-mm-YYYY strings
            weather_df['Date'] = pd.to_datetime(weather_df['Date'], dayfirst=True, errors='coerce').dt.strftime("%d-%m-%Y")
        else:
            weather_df['Date'] = None

        # Trim whitespace from key text columns if present
        for c in ['District', 'Taluka', 'Circle', 'Crop', 'Location']:
            if c in weather_df.columns:
                weather_df[c] = weather_df[c].astype(str).str.strip()

        # Convert numeric columns to numeric; '#N/A' and blanks -> NaN
        for col in ['Rainfall', 'Tmax', 'Tmin', 'max_Rh', 'min_Rh']:
            if col in weather_df.columns:
                weather_df[col] = pd.to_numeric(weather_df[col], errors='coerce')

        # Standardize rules_df column names (strip)
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
# UI Inputs
# -----------------------------
params = st.query_params  # current API returns a dict-like of lists

# helper to get first value if param is provided as list
def first_param(p):
    if not p:
        return ""
    return p[0] if isinstance(p, (list, tuple)) else p

pref_district = first_param(params.get("district", ""))
# District / Taluka / Circle selection
districts = sorted(weather_df['District'].dropna().unique())
district_index = districts.index(pref_district) if pref_district in districts else 0
district = st.selectbox("District", ["Select District"] + districts, index=(district_index + 1) if pref_district else 0)

if district == "Select District":
    st.info("Please select a District to continue.")
    st.stop()

# Taluka options for selected district
taluka_options = sorted(weather_df.loc[weather_df['District'] == district, 'Taluka'].dropna().unique().tolist())
pref_taluka = first_param(params.get("taluka", ""))
taluka_index = taluka_options.index(pref_taluka) if pref_taluka in taluka_options else 0
taluka = st.selectbox("Taluka", ["All Talukas"] + taluka_options, index=(taluka_index + 1) if pref_taluka else 0)

# Circle options for selected taluka/district
if taluka != "All Talukas":
    circle_options = sorted(weather_df.loc[(weather_df['District'] == district) & (weather_df['Taluka'] == taluka), 'Circle'].dropna().unique().tolist())
else:
    circle_options = sorted(weather_df.loc[weather_df['District'] == district, 'Circle'].dropna().unique().tolist())

pref_circle = first_param(params.get("circle", ""))
circle_index = circle_options.index(pref_circle) if pref_circle in circle_options else 0
circle = st.selectbox("Circle", ["All Circles"] + circle_options, index=(circle_index + 1) if pref_circle else 0)

# Crop & dates
pref_crop = first_param(params.get("crop", ""))
# allow user to type/choose crop; using rules_df Crop list if available
crop_list = sorted(rules_df['Crop'].dropna().unique().tolist()) if 'Crop' in rules_df.columns else []
crop_name = st.selectbox("Crop Name", [""] + crop_list, index=(crop_list.index(pref_crop) + 1) if pref_crop in crop_list else 0)

sowing_date = st.date_input("Sowing Date (DD-MM-YYYY)", value=(datetime.today() - timedelta(days=30)).date())
current_date = st.date_input("Current Date (DD-MM-YYYY)", value=datetime.today().date())

# Basic validation
if sowing_date > current_date:
    st.error("Sowing date cannot be after current date.")
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

# Ensure Date column is datetime
loc_df['Date'] = pd.to_datetime(loc_df['Date'], dayfirst=True, errors='coerce')
loc_df = loc_df.dropna(subset=['Date'])
# Only up to current_date
loc_df = loc_df[loc_df['Date'] <= pd.to_datetime(current_date)]

# DAS and DAS-window data
DAS = (pd.to_datetime(current_date) - pd.to_datetime(sowing_date)).days
if DAS < 0:
    DAS = 0

sowing_window_df = loc_df[(loc_df['Date'] >= pd.to_datetime(sowing_date)) & (loc_df['Date'] <= pd.to_datetime(current_date))].copy()

# Convert numeric columns in the window (coerce '#N/A' & blanks to NaN)
for col in ['Rainfall', 'Tmax', 'Tmin', 'max_Rh', 'min_Rh']:
    if col in sowing_window_df.columns:
        sowing_window_df[col] = pd.to_numeric(sowing_window_df[col], errors='coerce')

# -----------------------------
# Weather metrics calculations
# - Rainfall sums: last week, last month, since sowing (DAS)
# - Averages: Tmax/Tmin/max_Rh/min_Rh over DAS, IGNORING (#N/A, blanks, and zeros)
# -----------------------------
# Rainfall sums (treat NaN as 0 for sum)
rainfall_DAS = float(sowing_window_df['Rainfall'].fillna(0).sum()) if 'Rainfall' in sowing_window_df.columns else 0.0
rainfall_week = float(loc_df.loc[loc_df['Date'] >= (pd.to_datetime(current_date) - timedelta(days=7)), 'Rainfall'].fillna(0).sum()) if 'Rainfall' in loc_df.columns else 0.0
rainfall_month = float(loc_df.loc[loc_df['Date'] >= (pd.to_datetime(current_date) - timedelta(days=30)), 'Rainfall'].fillna(0).sum()) if 'Rainfall' in loc_df.columns else 0.0

# Averages ignoring NaN and zeros: replace 0 with NaN then compute mean over non-NaN values
def avg_ignore_zero_and_na(series):
    if series is None or series.size == 0:
        return None
    s = series.copy()
    # convert to numeric (should already be numeric), then treat 0 as missing
    s = pd.to_numeric(s, errors='coerce')
    s = s.replace(0, np.nan)
    s = s.dropna()
    if s.empty:
        return None
    return float(s.mean())

avg_Tmax = avg_ignore_zero_and_na(sowing_window_df['Tmax']) if 'Tmax' in sowing_window_df.columns else None
avg_Tmin = avg_ignore_zero_and_na(sowing_window_df['Tmin']) if 'Tmin' in sowing_window_df.columns else None
avg_maxRh = avg_ignore_zero_and_na(sowing_window_df['max_Rh']) if 'max_Rh' in sowing_window_df.columns else None
avg_minRh = avg_ignore_zero_and_na(sowing_window_df['min_Rh']) if 'min_Rh' in sowing_window_df.columns else None

# -----------------------------
# Sowing Advisory Logic
# - evaluate 1FN / 2FN and match sowing_calendar sheet entries
# -----------------------------
month_name = sowing_date.strftime("%B")
fortnight = "1FN" if sowing_date.day <= 15 else "2FN"
match_key = f"{fortnight} {month_name}"

# Sowing calendar columns expected: 'District','Taluka','Circle','Crop','IF condition','Comment on Sowing','Ideal Sowing'
# Use case-insensitive column lookup to be robust
sowing_cols = {c.lower(): c for c in sowing_df.columns}

def sc_get(colname):
    return sowing_cols.get(colname.lower())

# Filter sowing_df by hierarchy and crop (if provided)
sow_df = sowing_df.copy()
if 'district' in sowing_cols:
    sow_df = sow_df[sow_df[sc_get('district')] == district]
# taluka filtering: if user selected specific taluka, prefer exact match else keep all talukas for the district
if taluka != "All Talukas" and sc_get('taluka') is not None:
    sow_df = sow_df[sow_df[sc_get('taluka')] == taluka]
if sc_get('crop') is not None and crop_name:
    sow_df = sow_df[sow_df[sc_get('crop')] == crop_name]

advisory_sowing = []
if sc_get('if condition') is not None and sc_get('comment on sowing') is not None:
    # find rows where IF condition contains the match_key, or evaluate '<'/'>' conditions w.r.t. fortnight
    for _, row in sow_df.iterrows():
        cond = str(row[sc_get('if condition')]).strip()
        comment = str(row[sc_get('comment on sowing')])
        # direct contain (e.g., '2FN June to 1FN July' or '2FN June')
        if match_key.lower() in cond.lower():
            advisory_sowing.append(f"{cond} : {comment}")
            continue
        # handle patterns like '< 2FN June' or '> 1FN July'
        if cond.startswith('<') or cond.startswith('>'):
            # crude check: compare months & 1FN/2FN ordering
            try:
                token = cond.lstrip('<>').strip()
                # parse token like '2FN June'
                parts = token.split()
                token_fn = parts[0]
                token_month = " ".join(parts[1:])
                token_month_num = datetime.strptime(token_month, "%B").month
                sow_month_num = sowing_date.month
                if cond.startswith('<'):
                    # earlier than token: true if month < token_month or same month and fn is earlier
                    if sow_month_num < token_month_num:
                        advisory_sowing.append(f"{cond} : {comment}")
                    elif sow_month_num == token_month_num:
                        if token_fn.startswith('2') and fortnight == '1FN':
                            advisory_sowing.append(f"{cond} : {comment}")
                else:
                    # '>' later than token
                    if sow_month_num > token_month_num:
                        advisory_sowing.append(f"{cond} : {comment}")
                    elif sow_month_num == token_month_num:
                        if token_fn.startswith('1') and fortnight == '2FN':
                            advisory_sowing.append(f"{cond} : {comment}")
            except Exception:
                # ignore parsing errors
                pass
else:
    # if required columns missing, leave advisory_sowing empty and we will show a friendly message later
    pass

# If no sowing advisory found, provide generic 1FN/2FN advisory
if not advisory_sowing:
    if fortnight == '1FN':
        advisory_sowing = [f"1FN (Month Date between 1 to 15): Early/first-fortnight sowing guidance (no specific rule found)."]
    else:
        advisory_sowing = [f"2FN (Month Date between 16 to 31): Second-fortnight sowing guidance (no specific rule found)."]

# -----------------------------
# Growth Stage Advisory using rules.xlsx
# - The rules file has columns like:
#   Crop, Growth Stage, DAS (Days After Sowing), Ideal Water Required (in mm), IF Condition, Farmer Advisory
# - We handle flexible column names by matching substrings.
# -----------------------------
# Identify relevant columns in rules_df (case-insensitive search)
rules_cols = {c.lower(): c for c in rules_df.columns}

def rcol(part):
    # return first column name containing 'part' substring, else None
    for k, orig in rules_cols.items():
        if part.lower() in k:
            return orig
    return None

col_crop = rcol('crop')
col_growth = rcol('growth')
col_das = rcol('das')  # e.g., 'DAS (Days After Sowing)' or 'DAS'
col_ideal_water = rcol('ideal water') or rcol('ideal')
col_ifcond = rcol('if condition') or rcol('if')
col_advisory = rcol('farmer') or rcol('advisory') or rcol('farmer advisory')

growth_advisories = []

if col_crop is None or col_das is None or col_ideal_water is None:
    # rules file doesn't appear to have expected columns
    growth_advisories.append("Rules file missing expected columns; cannot generate growth stage advisories.")
else:
    # Filter rules by crop if crop chosen
    rules_subset = rules_df.copy()
    if crop_name and col_crop in rules_subset.columns:
        rules_subset = rules_subset[rules_subset[col_crop] == crop_name]

    # Helper: check if DAS value/range matches current DAS
    def das_matches_field(field_val, das):
        if pd.isna(field_val):
            return False
        s = str(field_val).strip()
        # common formats: '0', '1 to 50', '70 to 90', '115+', '1-50'
        if 'to' in s:
            # '1 to 50'
            parts = [p.strip() for p in s.replace('-', ' to ').split('to')]
            try:
                a = int(parts[0]); b = int(parts[1])
                return a <= das <= b
            except Exception:
                return False
        elif '-' in s:
            try:
                a, b = [int(x.strip()) for x in s.split('-')]
                return a <= das <= b
            except Exception:
                return False
        elif s.endswith('+'):
            try:
                a = int(s.replace('+', '').strip())
                return das >= a
            except Exception:
                return False
        elif s.startswith('<'):
            try:
                a = int(s.replace('<', '').strip())
                return das < a
            except Exception:
                return False
        elif s.startswith('>'):
            try:
                a = int(s.replace('>', '').strip())
                return das > a
            except Exception:
                return False
        else:
            # exact numeric match
            try:
                return int(s) == das
            except Exception:
                return False

    # Search rows where DAS matches
    matched_rules = []
    for _, row in rules_subset.iterrows():
        if das_matches_field(row[col_das], DAS):
            matched_rules.append(row)

    # For each matched rule, evaluate rainfall_DAS vs Ideal Water Required and IF Condition
    for row in matched_rules:
        ideal_water_field = row.get(col_ideal_water, "")
        # parse ideal water numeric range "10 to 30" -> min,max
        min_w, max_w = None, None
        try:
            s = str(ideal_water_field)
            if 'to' in s:
                parts = [p.strip() for p in s.replace('-', ' to ').split('to')]
                min_w = float(parts[0]); max_w = float(parts[1])
            elif '-' in s:
                a, b = [float(x.strip()) for x in s.split('-')]
                min_w, max_w = a, b
            else:
                # single number or 0
                min_w = max_w = float(s)
        except Exception:
            min_w = max_w = None

        # Check IF Condition column first (if provided in rules)
        condition_passed = False
        advisory_text = ""
        if col_ifcond and col_ifcond in row.index:
            cond_str = str(row[col_ifcond]).strip()
            # create simple evaluator for conditions like '>=10 & <= 30', '<10', '>30'
            def eval_cond(cond, value):
                cond = cond.replace('AND', '&').replace('and', '&')
                parts = [p.strip() for p in cond.split('&') if p.strip()]
                for p in parts:
                    if p.startswith('>='):
                        if not (value >= float(p.replace('>=','').strip())):
                            return False
                    elif p.startswith('<='):
                        if not (value <= float(p.replace('<=','').strip())):
                            return False
                    elif p.startswith('>'):
                        if not (value > float(p.replace('>','').strip())):
                            return False
                    elif p.startswith('<'):
                        if not (value < float(p.replace('<','').strip())):
                            return False
                    else:
                        # equality or direct numeric
                        try:
                            if not (value == float(p)):
                                return False
                        except:
                            return False
                return True

            try:
                # rainfall_DAS is numeric, evaluate cond against rainfall_DAS
                if eval_cond(cond_str, rainfall_DAS):
                    condition_passed = True
                    advisory_text = str(row.get(col_advisory, "") or "")
            except Exception:
                condition_passed = False

        # If no IF Condition matched (or none present), fallback to comparing against Ideal Water Required range
        if not condition_passed:
            if min_w is not None and max_w is not None:
                if min_w <= rainfall_DAS <= max_w:
                    advisory_text = str(row.get(col_advisory, "") or "")
                elif rainfall_DAS < (min_w if min_w is not None else 0):
                    # find advisory for '<' conditions in same growth stage (if exists)
                    if col_ifcond in row.index:
                        # try to find matching rows for less-than in rules_subset (same growth stage)
                        same_stage = rules_subset[rules_subset.get(col_das) == row.get(col_das)]
                        # fallback advisory
                    advisory_text = str(row.get(col_advisory, "") or "Irrigation recommended based on low rainfall since sowing.")
                else:
                    advisory_text = str(row.get(col_advisory, "") or "Drainage/avoid excess water based on high rainfall since sowing.")
            else:
                advisory_text = str(row.get(col_advisory, "") or "Advisory not specific; please check rules file.")

        growth_stage_name = row.get(col_growth, "Unknown Stage") if col_growth in row.index else "Growth stage"
        growth_advisories.append(f"{growth_stage_name} ({DAS} DAS): {advisory_text}")

# If no matched rules were found, show friendly message
if not growth_advisories:
    growth_advisories = ["No matching growth stage advisory found for the current DAS/crop combination."]

# -----------------------------
# Display Results
# -----------------------------
st.subheader("📊 Weather Summary (based on selected location & DAS window)")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Rainfall (since sowing/DAS)", f"{rainfall_DAS:.1f} mm")
c2.metric("Rainfall (last 7 days)", f"{rainfall_week:.1f} mm")
c3.metric("Rainfall (last 30 days)", f"{rainfall_month:.1f} mm")
c4.metric("Avg Tmax (since sowing)", f"{avg_Tmax:.1f}" if avg_Tmax is not None else "N/A")
c5.metric("Avg Tmin (since sowing)", f"{avg_Tmin:.1f}" if avg_Tmin is not None else "N/A")

d1, d2 = st.columns(2)
d1.metric("Avg max_Rh (since sowing)", f"{avg_maxRh:.1f}" if avg_maxRh is not None else "N/A")
d2.metric("Avg min_Rh (since sowing)", f"{avg_minRh:.1f}" if avg_minRh is not None else "N/A")

st.subheader("🌱 Sowing Advisory")
for adv in advisory_sowing:
    st.write(f"- {adv}")

st.subheader("📖 Growth Stage Advisory")
for adv in growth_advisories:
    st.write(f"- {adv}")
