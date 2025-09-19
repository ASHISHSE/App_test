import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import urllib.parse
import requests
from io import BytesIO

# -----------------------------
# Crop Advisory - Streamlit App
# -----------------------------
# Features implemented/changed based on user instructions:
# - Location dropdown hierarchy: District -> Taluka -> Circle
#   If circle not selected, calculations are performed at Taluka level.
#   If taluka not selected, calculations are performed at District level.
# - Input parsing from query params so the advisory can be shared via link.
# - Weather metrics: rainfall cumulative (last week, last month, since sowing/DAS),
#   Tmax/Tmin/max_Rh/min_Rh averaged over DAS period at selected level.
# - Sowing advisory: computes 1FN/2FN based on sowing date and matches sowing_calendar rules.
# - Growth-stage advisory: computes DAS and compares rainfall since sowing with
#   Ideal Water Required (mm) using IF Condition entries in rules.xlsx and returns Farmer Advisory.
# - Improved handling of missing numeric data (don't replace with zeros for averages).
# - Shareable link with query parameters for district,taluka,circle,crop,sowing,current

st.set_page_config(page_title="Crop Advisory System", page_icon="🌱", layout="wide")

# -----------------------------
# Utility functions
# -----------------------------

def safe_to_int(x):
    try:
        return int(x)
    except:
        return None


def parse_ddmmyy_to_ddmmyyyy(val):
    # Accept various formats: numeric like 010624 or string '010624' or already 'dd-mm-YYYY'
    try:
        s = str(int(val)).zfill(6)
        return datetime.strptime(s, '%d%m%y').strftime('%d-%m-%Y')
    except:
        try:
            # try parse as dd-mm-yyyy
            dt = pd.to_datetime(val, dayfirst=True)
            return dt.strftime('%d-%m-%Y')
        except:
            return None


def parse_if_condition(cond_str):
    # Normalizes IF Condition strings like '>=10 & <= 30', '<10', '>30' to a callable
    cond = str(cond_str).strip()
    cond = cond.replace('and', '&').replace('AND', '&')
    parts = [p.strip() for p in cond.split('&')]

    checks = []
    for p in parts:
        if p.startswith('>='):
            val = float(p.replace('>=', '').strip())
            checks.append(lambda x, v=val: x >= v)
        elif p.startswith('<='):
            val = float(p.replace('<=', '').strip())
            checks.append(lambda x, v=val: x <= v)
        elif p.startswith('>'):
            val = float(p.replace('>', '').strip())
            checks.append(lambda x, v=val: x > v)
        elif p.startswith('<'):
            val = float(p.replace('<', '').strip())
            checks.append(lambda x, v=val: x < v)
        else:
            # fallback: equality or single number
            try:
                v = float(p)
                checks.append(lambda x, v=v: x == v)
            except:
                pass

    def evaluator(x):
        try:
            for check in checks:
                if not check(x):
                    return False
            return True
        except:
            return False

    return evaluator


# -----------------------------
# Load data
# -----------------------------
@st.cache_data
def load_data():
    # Try load from GitHub first; on failure fall back to embedded sample data
    try:
        weather_url = "https://github.com/ASHISHSE/App_test/raw/main/weather.xlsx"
        rules_url = "https://github.com/ASHISHSE/App_test/raw/main/rules.xlsx"
        sowing_url = "https://github.com/ASHISHSE/App_test/raw/main/sowing_calendar.xlsx"

        wres = requests.get(weather_url, timeout=10)
        rres = requests.get(rules_url, timeout=10)
        sres = requests.get(sowing_url, timeout=10)

        weather_df = pd.read_excel(BytesIO(wres.content))
        rules_df = pd.read_excel(BytesIO(rres.content))
        sowing_df = pd.read_excel(BytesIO(sres.content))

        # Normalize weather date
        weather_df['Date'] = weather_df['Date(DDMMYY)'].apply(parse_ddmmyy_to_ddmmyyyy)
        weather_df = weather_df.dropna(subset=['Date']).copy()

        # Convert dataset string columns to consistent types and trim
        for c in ['District', 'Taluka', 'Circle', 'Crop']:
            if c in weather_df.columns:
                weather_df[c] = weather_df[c].astype(str).str.strip()
        if 'Crop' in rules_df.columns:
            rules_df['Crop'] = rules_df['Crop'].astype(str).str.strip()

        # Numeric columns: convert to numeric but keep NaN when missing (#N/A should become NaN)
        for col in ['Rainfall', 'Tmax', 'Tmin', 'max_Rh', 'min_Rh']:
            if col in weather_df.columns:
                weather_df[col] = pd.to_numeric(weather_df[col], errors='coerce')

        districts = sorted(weather_df['District'].dropna().unique().tolist())
        talukas = sorted(weather_df['Taluka'].dropna().unique().tolist())
        circles = sorted(weather_df['Circle'].dropna().unique().tolist())
        crops = sorted(rules_df['Crop'].dropna().unique().tolist())

        return weather_df, rules_df, sowing_df, districts, talukas, circles, crops

    except Exception as e:
        # Fallback sample data if remote read fails
        st.warning("Could not load remote files, using sample data. Error: {}".format(e))

        districts = ['Ahmednagar', 'Pune', 'Nashik']
        talukas = ['Ahmednagar', 'Parner', 'Sangamner']
        circles = ['Bhingar', 'Kapurwadi', 'Savedi']
        crops = ['Paddy', 'Cotton', 'Jowar']

        # sample weather
        weather_data = []
        start_date = date(2024, 1, 1)
        for i in range(365):
            current_date = start_date + timedelta(days=i)
            weather_data.append({
                'District': 'Ahmednagar',
                'Taluka': 'Ahmednagar',
                'Circle': 'Bhingar',
                'Date': current_date.strftime('%d-%m-%Y'),
                'Rainfall': max(0, np.random.normal(5, 3)),
                'Tmax': np.random.normal(35, 3),
                'Tmin': np.random.normal(22, 3),
                'max_Rh': np.random.normal(80, 5),
                'min_Rh': np.random.normal(50, 5)
            })
        weather_df = pd.DataFrame(weather_data)

        # sample rules (same as provided in prompt)
        rules_data = [
            {'Crop': 'Paddy', 'Growth Stage': 'Planting/Transplanting', 'DAS (Days After Sowing)': '0', 'Ideal Water Required (in mm)': '10 to 30', 'IF Condition': '>=10 & <= 30', 'Farmer Advisory': 'Saturated mud'},
            {'Crop': 'Paddy', 'Growth Stage': 'Planting/Transplanting', 'DAS (Days After Sowing)': '0', 'Ideal Water Required (in mm)': '10 to 30', 'IF Condition': '<10', 'Farmer Advisory': 'Ensure mud is soft. Transplanting in dry mud causes root damage and poor seedling establishment.'},
            {'Crop': 'Paddy', 'Growth Stage': 'Planting/Transplanting', 'DAS (Days After Sowing)': '0', 'Ideal Water Required (in mm)': '10 to 30', 'IF Condition': '>30', 'Farmer Advisory': 'Wait for water to drain. Transplanting in deep water can drown seedlings and cause them to float.'},
            # ... other rows omitted for brevity in sample
        ]
        rules_df = pd.DataFrame(rules_data)

        sowing_data = [
            {'District': 'Ahmednagar', 'Taluka': 'Ahmednagar', 'Circle': 'Kapurwadi', 'Crop': 'Cotton', 'Ideal Sowing': '2FN June to 1FN July', 'IF condition': '< 2FN June', 'Comment on Sowing': 'Early Sowing due Rainfall on time / Water source available'},
            {'District': 'Ahmednagar', 'Taluka': 'Ahmednagar', 'Circle': 'Kapurwadi', 'Crop': 'Cotton', 'Ideal Sowing': '2FN June to 1FN July', 'IF condition': '> 1FN July', 'Comment on Sowing': 'Late Sowing due to Rainfall delay /For sowing moisture is not sufficient in soil'},
            {'District': 'Ahmednagar', 'Taluka': 'Ahmednagar', 'Circle': 'Kapurwadi', 'Crop': 'Cotton', 'Ideal Sowing': '2FN June to 1FN July', 'IF condition': '2FN June to 1FN July', 'Comment on Sowing': 'Ideal Sowing Period'},
        ]
        sowing_df = pd.DataFrame(sowing_data)

        return weather_df, rules_df, sowing_df, districts, talukas, circles, crops


weather_df, rules_df, sowing_df, districts, talukas, circles, crops = load_data()

# -----------------------------
# Functions for metrics and advisories
# -----------------------------

def calculate_weather_metrics(weather_data, level, name, sowing_date_str, current_date_str):
    # Filter by hierarchical level
    df = weather_data.copy()
    if level == 'Circle':
        df = df[df['Circle'] == name]
    elif level == 'Taluka':
        df = df[df['Taluka'] == name]
    else:
        df = df[df['District'] == name]

    # Ensure Date column is datetime
    df['Date_dt'] = pd.to_datetime(df['Date'], format='%d-%m-%Y', errors='coerce')
    sowing_dt = datetime.strptime(sowing_date_str, '%d-%m-%Y')
    current_dt = datetime.strptime(current_date_str, '%d-%m-%Y')

    das = (current_dt - sowing_dt).days
    if das < 0:
        das = 0

    last_week_start = current_dt - timedelta(days=7)
    last_month_start = current_dt - timedelta(days=30)

    last_week_data = df[(df['Date_dt'] >= last_week_start) & (df['Date_dt'] <= current_dt)]
    last_month_data = df[(df['Date_dt'] >= last_month_start) & (df['Date_dt'] <= current_dt)]
    das_data = df[(df['Date_dt'] >= sowing_dt) & (df['Date_dt'] <= current_dt)]

    # Sum rainfall, compute averages ignoring NaNs
    metrics = {
        'rainfall_last_week': float(last_week_data['Rainfall'].sum()) if not last_week_data.empty else 0.0,
        'rainfall_last_month': float(last_month_data['Rainfall'].sum()) if not last_month_data.empty else 0.0,
        'rainfall_das': float(das_data['Rainfall'].sum()) if not das_data.empty else 0.0,
        'tmax_avg': float(das_data['Tmax'].mean()) if not das_data['Tmax'].dropna().empty else np.nan,
        'tmin_avg': float(das_data['Tmin'].mean()) if not das_data['Tmin'].dropna().empty else np.nan,
        'max_rh_avg': float(das_data['max_Rh'].mean()) if not das_data['max_Rh'].dropna().empty else np.nan,
        'min_rh_avg': float(das_data['min_Rh'].mean()) if not das_data['min_Rh'].dropna().empty else np.nan,
        'das': das
    }

    # Replace NaN averages with None for display
    for k in ['tmax_avg', 'tmin_avg', 'max_rh_avg', 'min_rh_avg']:
        if pd.isna(metrics[k]):
            metrics[k] = None

    return metrics


def das_in_range_string(das, das_str):
    # das_str can be '0' or '1 to 50' or '115+'
    s = str(das_str).strip()
    if 'to' in s:
        parts = [p.strip() for p in s.split('to')]
        try:
            start = int(parts[0])
            end = int(parts[1])
            return start <= das <= end
        except:
            return False
    elif s.endswith('+'):
        try:
            start = int(s.replace('+', '').strip())
            return das >= start
        except:
            return False
    else:
        # single digit
        try:
            return int(s) == das
        except:
            return False


def parse_water_range(water_str):
    # "10 to 30" -> (10.0, 30.0). If single number -> (num,num)
    try:
        if 'to' in str(water_str):
            a, b = [float(x.strip()) for x in str(water_str).split('to')]
            return a, b
        else:
            val = float(str(water_str).strip())
            return val, val
    except:
        return None, None


def get_growth_advisory(crop, das, rainfall_das, rules_df):
    # Filter rules for the crop and find matching DAS row(s)
    candidates = rules_df[rules_df['Crop'] == crop]
    if candidates.empty:
        return "No rules found for selected crop."

    match_row = None
    for idx, row in candidates.iterrows():
        das_field = row.get('DAS (Days After Sowing)')
        if das_field is None:
            continue
        if das_in_range_string(das, das_field):
            match_row = row
            break

    if match_row is None:
        return "No advisory available for this growth stage."

    stage_name = match_row.get('Growth Stage', 'Unknown')
    ideal_water = match_row.get('Ideal Water Required (in mm)', '')
    if_cond = match_row.get('IF Condition', '')

    # Try to find the advisory that matches actual rainfall in the rules for the same stage
    same_stage = candidates[candidates['Growth Stage'] == stage_name]

    # Build evaluators for each row and test rainfall_das
    for idx, r in same_stage.iterrows():
        cond = r.get('IF Condition', '')
        evaluator = parse_if_condition(cond)
        try:
            if evaluator(float(rainfall_das)):
                return f"Crop is at {stage_name} stage ({das} DAS). {r.get('Farmer Advisory', '')}"
        except Exception:
            continue

    # If none matched, as fallback compare against Ideal Water Required (range)
    min_w, max_w = parse_water_range(ideal_water)
    try:
        if min_w is not None and max_w is not None:
            if min_w <= rainfall_das <= max_w:
                # find first row with range condition
                row = same_stage.iloc[0]
                return f"Crop is at {stage_name} stage ({das} DAS). {row.get('Farmer Advisory', '')}"
            elif rainfall_das < min_w:
                # find advisory with '<' condition
                low = same_stage[same_stage['IF Condition'].astype(str).str.strip().str.startswith('<')]
                if not low.empty:
                    return f"Crop is at {stage_name} stage ({das} DAS). {low.iloc[0].get('Farmer Advisory','Irrigation needed.')}"
                else:
                    return f"Crop is at {stage_name} stage ({das} DAS). Irrigation likely needed."
            else:
                high = same_stage[same_stage['IF Condition'].astype(str).str.strip().str.startswith('>')]
                if not high.empty:
                    return f"Crop is at {stage_name} stage ({das} DAS). {high.iloc[0].get('Farmer Advisory','Drainage needed.')}"
                else:
                    return f"Crop is at {stage_name} stage ({das} DAS). Drainage may be required."
    except:
        return f"Crop is at {stage_name} stage ({das} DAS). Advisory: {match_row.get('Farmer Advisory','') }"


# Sowing advisory: interpret 1FN/2FN and compare
def fn_from_date(dt):
    # Return string like '1FN June' or '2FN June'
    month_name = dt.strftime('%B')
    day = dt.day
    if day <= 15:
        return f"1FN {month_name}"
    else:
        return f"2FN {month_name}"


def normalize_fn_string(s):
    # Normalize spaces and case
    return str(s).replace('.', '').strip()


def get_sowing_advisory(sowing_date_str, district, taluka, circle, crop, sowing_df):
    sowing_dt = datetime.strptime(sowing_date_str, '%d-%m-%Y')
    fn = fn_from_date(sowing_dt)

    # Search for exact match in sowing_df with hierarchy priority (Circle > Taluka > District)
    # Create possible filters
    filters = [
        (sowing_df['District'] == district) & (sowing_df['Taluka'] == taluka) & (sowing_df['Circle'] == circle) & (sowing_df['Crop'] == crop),
        (sowing_df['District'] == district) & (sowing_df['Taluka'] == taluka) & (sowing_df['Crop'] == crop),
        (sowing_df['District'] == district) & (sowing_df['Crop'] == crop),
    ]

    for f in filters:
        subset = sowing_df[f]
        if not subset.empty:
            # Try to match IF condition like '< 2FN June', '> 1FN July', '2FN June to 1FN July'
            for idx, row in subset.iterrows():
                cond = normalize_fn_string(row.get('IF condition', '') or row.get('IF Condition', ''))
                if not cond:
                    continue

                # Direct equality
                if fn.lower() in cond.lower():
                    return f"{row.get('IF condition','')}: {row.get('Comment on Sowing','')}"

                # Less than or greater than patterns
                if cond.startswith('<'):
                    # e.g. '< 2FN June' means sowing earlier than this -> fn must be earlier month or 1FN vs 2FN
                    target = cond.replace('<', '').strip()
                    # Very simple comparator: if month is earlier than target month OR same month and fn==1FN when target is 2FN
                    try:
                        t_parts = target.split()
                        t_fn = t_parts[0]
                        t_month = ' '.join(t_parts[1:])
                        # convert months
                        sow_month = sowing_dt.month
                        t_month_num = datetime.strptime(t_month, '%B').month
                        if sow_month < t_month_num:
                            return f"{row.get('IF condition','')}: {row.get('Comment on Sowing','')}"
                        if sow_month == t_month_num:
                            if t_fn.upper().startswith('2') and fn.startswith('1FN'):
                                return f"{row.get('IF condition','')}: {row.get('Comment on Sowing','')}"
                    except Exception:
                        pass

                if cond.startswith('>'):
                    target = cond.replace('>', '').strip()
                    try:
                        t_parts = target.split()
                        t_fn = t_parts[0]
                        t_month = ' '.join(t_parts[1:])
                        sow_month = sowing_dt.month
                        t_month_num = datetime.strptime(t_month, '%B').month
                        if sow_month > t_month_num:
                            return f"{row.get('IF condition','')}: {row.get('Comment on Sowing','')}"
                        if sow_month == t_month_num:
                            if t_fn.upper().startswith('1') and fn.startswith('2FN'):
                                return f"{row.get('IF condition','')}: {row.get('Comment on Sowing','')}"
                    except Exception:
                        pass

                # Range like '2FN June to 1FN July'
                if 'to' in cond:
                    try:
                        left, right = [c.strip() for c in cond.split('to')]
                        # Convert left and right to comparable month+fn indexes
                        def fn_index(token):
                            parts = token.split()
                            fnpart = parts[0]
                            monthpart = ' '.join(parts[1:])
                            mnum = datetime.strptime(monthpart, '%B').month
                            base = (mnum - 1) * 2
                            if fnpart.startswith('2'):
                                base += 1
                            return base

                        idx_fn = fn_index(fn)
                        left_idx = fn_index(left)
                        right_idx = fn_index(right)
                        if left_idx <= idx_fn <= right_idx:
                            return f"{row.get('IF condition','')}: {row.get('Comment on Sowing','')}"
                    except Exception:
                        pass

            # if subset exists but no rule matched, provide generic idea
            break

    # Fallback generic advisory based on first/second fortnight
    if fn.startswith('1FN'):
        return f"1FN (Month Date between 1 to 15): Early sowing/First fortnight sowing behavior."
    else:
        return f"2FN (Month Date between 16 to 31): Late sowing/Second fortnight sowing behavior."


# -----------------------------
# UI
# -----------------------------

# Read query params to prefill fields if present
qp = st.experimental_get_query_params()

pref_district = qp.get('district', [""])[0]
pref_taluka = qp.get('taluka', [""])[0]
pref_circle = qp.get('circle', [""])[0]
pref_crop = qp.get('crop', [""])[0]

pref_sowing = qp.get('sowing', [""])[0]
pref_current = qp.get('current', [""])[0]

# Page header
st.title("🌱 Crop Advisory System")
st.write("Select a location and crop, enter sowing & current dates, and click Generate Advisory.")

# Layout with three columns
col1, col2, col3 = st.columns(3)

with col1:
    district = st.selectbox("District *", options=[""] + districts, index=(districts.index(pref_district) + 1) if pref_district in districts else 0)
    # taluka options filtered by district
    taluka_options = [""]
    if district:
        district_talukas = sorted(weather_df[weather_df['District'] == district]['Taluka'].dropna().unique().tolist())
        taluka_options += district_talukas
    else:
        taluka_options += talukas
    taluka = st.selectbox("Taluka", options=taluka_options, index=(talaka_options.index(pref_taluka) if pref_taluka in taluka_options else 0))
    circle_options = [""]
    if taluka:
        circle_options += sorted(weather_df[weather_df['Taluka'] == taluka]['Circle'].dropna().unique().tolist())
    else:
        circle_options += circles
    circle = st.selectbox("Circle", options=circle_options, index=(circle_options.index(pref_circle) if pref_circle in circle_options else 0))

with col2:
    crop = st.selectbox("Crop Name *", options=[""] + crops, index=(crops.index(pref_crop) + 1) if pref_crop in crops else 0)
    sowing_default = None
    if pref_sowing:
        try:
            sowing_default = datetime.strptime(pref_sowing, '%d-%m-%Y').date()
        except:
            sowing_default = None
    sowing_date = st.date_input("Sowing Date (DD-MM-YYYY) *", value=sowing_default or date.today() - timedelta(days=30), format='DD-MM-YYYY')

with col3:
    current_default = None
    if pref_current:
        try:
            current_default = datetime.strptime(pref_current, '%d-%m-%Y').date()
        except:
            current_default = date.today()
    current_date = st.date_input("Current Date (DD-MM-YYYY) *", value=current_default or date.today(), format='DD-MM-YYYY')

# Action buttons
generate = st.button("🌱 Generate Advisory")

if generate:
    # Validate
    if not district or not crop or not sowing_date or not current_date:
        st.error("Please select District, Crop and enter both Sowing and Current dates.")
    else:
        if sowing_date > current_date:
            st.error("Sowing date cannot be after current date.")
        else:
            sowing_date_str = sowing_date.strftime('%d-%m-%Y')
            current_date_str = current_date.strftime('%d-%m-%Y')

            # Determine level
            if circle:
                level = 'Circle'
                level_name = circle
            elif taluka:
                level = 'Taluka'
                level_name = taluka
            else:
                level = 'District'
                level_name = district

            metrics = calculate_weather_metrics(weather_df, level, level_name, sowing_date_str, current_date_str)

            st.markdown('---')
            st.header('🌤️ Weather Metrics')
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric('Rainfall - Last Week (mm)', f"{metrics['rainfall_last_week']:.1f}")
                st.metric('Rainfall - Last Month (mm)', f"{metrics['rainfall_last_month']:.1f}")
                st.metric('Rainfall - Since Sowing/DAS (mm)', f"{metrics['rainfall_das']:.1f}")
            with c2:
                tmax = metrics['tmax_avg']
                tmin = metrics['tmin_avg']
                st.metric('Tmax Avg (since sowing)', f"{tmax:.1f}" if tmax is not None else 'N/A')
                st.metric('Tmin Avg (since sowing)', f"{tmin:.1f}" if tmin is not None else 'N/A')
            with c3:
                maxrh = metrics['max_rh_avg']
                minrh = metrics['min_rh_avg']
                st.metric('Max RH Avg (since sowing)', f"{maxrh:.1f}" if maxrh is not None else 'N/A')
                st.metric('Min RH Avg (since sowing)', f"{minrh:.1f}" if minrh is not None else 'N/A')

            st.markdown('---')
            st.header('📋 Advisory Results')

            sowing_advisory = get_sowing_advisory(sowing_date_str, district, taluka, circle, crop, sowing_df)
            st.subheader('Sowing Advisory')
            st.write(sowing_advisory)

            growth_advisory = get_growth_advisory(crop, metrics['das'], metrics['rainfall_das'], rules_df)
            st.subheader('Growth Stage Advisory')
            st.write(growth_advisory)

            # Share link
            params = {
                'district': district,
                'taluka': taluka or '',
                'circle': circle or '',
                'crop': crop,
                'sowing': sowing_date_str,
                'current': current_date_str
            }
            query_string = urllib.parse.urlencode(params)
            shareable_link = f"{st.runtime.get_url()}?{query_string}" if hasattr(st, 'runtime') else f"?{query_string}"

            st.markdown('---')
            st.header('📤 Share Advisory')
            st.write('Share this advisory with others via this link:')
            st.code(shareable_link, language='')

            # Quick share actions
            whatsapp_text = f"Crop advisory for {crop} in {district}{', ' + taluka if taluka else ''}{', ' + circle if circle else ''} - {shareable_link}"
            whatsapp_url = f"https://wa.me/?text={urllib.parse.quote(whatsapp_text)}"
            st.markdown(f"[Share on WhatsApp]({whatsapp_url})")
            st.markdown(f"mailto:?subject={urllib.parse.quote('Crop Advisory')}&body={urllib.parse.quote(whatsapp_text)}")

# Footer
st.markdown('---')
st.caption('Crop Advisory System — generated with local rules and weather files.')
