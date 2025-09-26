import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime, date, timedelta
import requests
from io import BytesIO
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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
    return pd.read_excel(url)

circlewise_df = load_circlewise_data()

# -----------------------------
# MODIFIED HELPER FUNCTION FOR CIRCLEWISE DATA
# -----------------------------
def get_circlewise_data(district, taluka, circle, sowing_date, current_date):
    df = circlewise_df.copy()

    # Filter by District, Taluka, Circle
    if "District" in df.columns and "Taluka" in df.columns:
        df = df[(df["District"] == district) & (df["Taluka"] == taluka)]
    if circle and "Circle" in df.columns:
        df = df[df["Circle"] == circle]

    if df.empty:
        return pd.DataFrame()

    # Generate list of months between sowing_date and current_date
    months = []
    current = sowing_date.replace(day=1)
    end = current_date.replace(day=1)
    
    while current <= end:
        months.append(current.strftime("%B"))
        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    # Remove duplicates while preserving order
    months = list(dict.fromkeys(months))

    # Select relevant columns (District, Taluka, Circle + monthly data columns)
    selected_cols = []
    for base in ["District", "Taluka", "Circle"]:
        if base in df.columns:
            selected_cols.append(base)
    
    # Get all columns that contain any of the target months (case-insensitive)
    month_names = [m.lower() for m in months]
    for col in df.columns:
        col_lower = str(col).lower()
        if any(month in col_lower for month in month_names):
            if col not in selected_cols:
                selected_cols.append(col)

    # If no monthly columns found, fall back to returning the original dataframe (or empty)
    if len(selected_cols) <= len([c for c in ["District","Taluka","Circle"] if c in df.columns]):
        # attempt to return all monthly/indicator columns by looking for known keywords
        alt_cols = [c for c in df.columns if any(k in str(c).lower() for k in ['ndvi','ndwi','rainfall','mai','indicator','rainfall_dev','rainfall dev','rainfall_dev'])]
        selected_cols = selected_cols + alt_cols

    if len(selected_cols) <= len([c for c in ["District","Taluka","Circle"] if c in df.columns]):
        return pd.DataFrame()

    return df[selected_cols].reset_index(drop=True)

# -----------------------------
# NEW FUNCTION FOR MONTHLY ANALYSIS
# -----------------------------
def create_monthly_analysis(matrix_data):
    """Create detailed monthly analysis with index values and categories"""
    if matrix_data.empty:
        return None
    
    # Normalize column names for robust searching
    cols = [str(c) for c in matrix_data.columns]
    months_found = set()
    month_order = ['January','February','March','April','May','June','July','August','September','October','November','December']
    
    # Identify months present in any column name
    for c in cols:
        for m in month_order:
            if m.lower() in c.lower():
                months_found.add(m)
    months = sorted(list(months_found), key=lambda x: datetime.strptime(x, "%B"))
    if not months:
        return None

    # Build monthly rows by extracting relevant columns
    monthly_rows = []
    row0 = matrix_data.iloc[0]  # assume first row corresponds to the selected circle/taluka/district
    for m in months:
        item = {
            'Month': m,
            'NDVI_Value': np.nan,
            'NDVI_Category': np.nan,
            'NDWI_Value': np.nan,
            'NDWI_Category': np.nan,
            'Rainfall_Dev_Value': np.nan,
            'Rainfall_Dev_Category': np.nan,
            'MAI_Value': np.nan,
            'MAI_Category': np.nan,
            'Indicator_1': np.nan,
            'Indicator_2': np.nan,
            'Indicator_3': np.nan,
            'Rainfall': np.nan,
            'Rainy_Days': np.nan,
            'Tmax': np.nan,
            'Tmin': np.nan,
            'Max_RH': np.nan,
            'Min_RH': np.nan
        }
        m_lower = m.lower()
        for c in cols:
            c_lower = c.lower()
            if m_lower in c_lower:
                val = row0[c] if c in matrix_data.columns else np.nan
                # Use patterns to map
                if 'ndvi' in c_lower and 'cat' not in c_lower and 'indicator' not in c_lower:
                    item['NDVI_Value'] = val
                elif 'ndvi' in c_lower and ('cat' in c_lower or 'status' in c_lower or 'category' in c_lower):
                    item['NDVI_Category'] = val
                elif 'ndwi' in c_lower and 'cat' not in c_lower and 'indicator' not in c_lower:
                    item['NDWI_Value'] = val
                elif 'ndwi' in c_lower and ('cat' in c_lower or 'status' in c_lower or 'category' in c_lower):
                    item['NDWI_Category'] = val
                elif ('rainfall_dev' in c_lower) or ('rainfall dev' in c_lower) or ('rainfall deviation' in c_lower):
                    # some files might have plain numbers, others with category columns
                    if any(k in c_lower for k in ['cat','status','category']):
                        item['Rainfall_Dev_Category'] = val
                    else:
                        item['Rainfall_Dev_Value'] = val
                elif 'mai' in c_lower:
                    if any(k in c_lower for k in ['cat','status','category']):
                        item['MAI_Category'] = val
                    else:
                        item['MAI_Value'] = val
                elif 'indicator-1' in c_lower or ('indicator 1' in c_lower) or ('indicator_1' in c_lower):
                    item['Indicator_1'] = val
                elif 'indicator-2' in c_lower or ('indicator 2' in c_lower) or ('indicator_2' in c_lower):
                    item['Indicator_2'] = val
                elif 'indicator-3' in c_lower or ('indicator 3' in c_lower) or ('indicator_3' in c_lower):
                    item['Indicator_3'] = val
                elif 'rainfall' in c_lower and 'dev' not in c_lower and 'indicator' not in c_lower:
                    # sometimes raw rainfall maybe present
                    item['Rainfall'] = val
                elif 'rainy' in c_lower and 'day' in c_lower:
                    item['Rainy_Days'] = val
                elif 'tmax' in c_lower:
                    item['Tmax'] = val
                elif 'tmin' in c_lower:
                    item['Tmin'] = val
                elif ('max' in c_lower and 'rh' in c_lower) or ('max_rh' in c_lower):
                    item['Max_RH'] = val
                elif ('min' in c_lower and 'rh' in c_lower) or ('min_rh' in c_lower):
                    item['Min_RH'] = val
        monthly_rows.append(item)

    monthly_df = pd.DataFrame(monthly_rows)
    return monthly_df

def get_status_color(status):
    """Get color based on status"""
    if pd.isna(status):
        return '#f8f9fa'
    status_lower = str(status).lower()
    if any(word in status_lower for word in ['good', 'normal', 'above', 'excellent', 'satisfactory']):
        return '#d4edda'  # Light Green
    elif any(word in status_lower for word in ['moderate', 'average', 'medium', 'moderately']):
        return '#fff3cd'  # Light Yellow
    elif any(word in status_lower for word in ['poor', 'deficit', 'below', 'low', 'unsatisfactory']):
        return '#f8d7da'  # Light Red
    else:
        return '#e9ecef'  # Default

def get_status_icon(status):
    """Get icon based on status"""
    if pd.isna(status):
        return '⚪'
    status_lower = str(status).lower()
    if any(word in status_lower for word in ['good', 'normal', 'above', 'excellent', 'satisfactory']):
        return '🟢'
    elif any(word in status_lower for word in ['moderate', 'average', 'medium', 'moderately']):
        return '🟡'
    elif any(word in status_lower for word in ['poor', 'deficit', 'below', 'low', 'unsatisfactory']):
        return '🔴'
    else:
        return '⚪'

# -----------------------------
# CHART FUNCTIONS
# -----------------------------
def create_weather_bar_chart(metrics):
    """Create bar chart for weather parameters (3-period summary)"""
    # Prepare data for bar chart
    periods = ['Last Week', 'Last Month', 'Since Sowing']
    rainfall_data = [metrics.get('rainfall_last_week', 0), metrics.get('rainfall_last_month', 0), metrics.get('rainfall_das', 0)]
    rainy_days_data = [metrics.get('rainy_days_week', 0), metrics.get('rainy_days_month', 0), metrics.get('rainy_days_das', 0)]
    
    # Create subplots
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Rainfall (mm)', 'Rainy Days', 'Temperature Metrics', 'Humidity Metrics'),
        specs=[[{"secondary_y": False}, {"secondary_y": False}],
               [{"secondary_y": False}, {"secondary_y": False}]]
    )
    
    # Rainfall bar chart
    fig.add_trace(
        go.Bar(name='Rainfall (mm)', x=periods, y=rainfall_data),
        row=1, col=1
    )
    
    # Rainy days bar chart
    fig.add_trace(
        go.Bar(name='Rainy Days', x=periods, y=rainy_days_data),
        row=1, col=2
    )
    
    # Temperature metrics
    temp_metrics = ['Tmax Avg', 'Tmin Avg']
    temp_values = [metrics.get('tmax_avg') or 0, metrics.get('tmin_avg') or 0]
    fig.add_trace(
        go.Bar(name='Temperature (°C)', x=temp_metrics, y=temp_values),
        row=2, col=1
    )
    
    # Humidity metrics
    humidity_metrics = ['Max RH Avg', 'Min RH Avg']
    humidity_values = [metrics.get('max_rh_avg') or 0, metrics.get('min_rh_avg') or 0]
    fig.add_trace(
        go.Bar(name='Humidity (%)', x=humidity_metrics, y=humidity_values),
        row=2, col=2
    )
    
    fig.update_layout(
        title="Weather Parameters Analysis",
        height=600,
        showlegend=False,
        template="plotly_white"
    )
    return fig

def create_indices_line_chart(monthly_df, indicators=['NDVI','NDWI']):
    """Create line chart for NDVI and NDWI values across months"""
    if monthly_df is None or monthly_df.empty:
        return None
    
    df = monthly_df.copy()
    # Ensure Month sorting
    df['Month_Num'] = df['Month'].apply(lambda x: datetime.strptime(x, '%B').month)
    df = df.sort_values('Month_Num')
    fig = go.Figure()
    if 'NDVI' in indicators and 'NDVI_Value' in df.columns and df['NDVI_Value'].notna().any():
        fig.add_trace(go.Scatter(x=df['Month'], y=df['NDVI_Value'], mode='lines+markers', name='NDVI'))
    if 'NDWI' in indicators and 'NDWI_Value' in df.columns and df['NDWI_Value'].notna().any():
        fig.add_trace(go.Scatter(x=df['Month'], y=df['NDWI_Value'], mode='lines+markers', name='NDWI'))
    fig.update_layout(title="Monthly Indices Trend", xaxis_title="Month", yaxis_title="Value", template="plotly_white", height=400)
    return fig

def create_single_param_column_charts(monthly_df, params):
    """
    Create a dictionary of plotly figures for column charts for each parameter specified in `params`.
    params is a list of tuples: (column_name_in_monthly_df, display_title)
    """
    figs = {}
    if monthly_df is None or monthly_df.empty:
        return figs
    df = monthly_df.copy()
    df['Month_Num'] = df['Month'].apply(lambda x: datetime.strptime(x, '%B').month)
    df = df.sort_values('Month_Num')
    for col, title in params:
        if col in df.columns and df[col].notna().any():
            # ensure numeric when possible
            try:
                y = pd.to_numeric(df[col], errors='coerce')
            except Exception:
                y = df[col]
            fig = px.bar(df, x='Month', y=y, title=title)
            fig.update_layout(template="plotly_white", height=350)
            figs[col] = fig
    return figs

# -----------------------------
# OTHER HELPER FUNCTIONS
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
    if level == "Circle" and "Circle" in df.columns:
        df = df[df["Circle"] == name]
    elif level == "Taluka" and "Taluka" in df.columns:
        df = df[df["Taluka"] == name]
    elif level == "District" and "District" in df.columns:
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
        "das_data": das_data.reset_index(drop=True)
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
            st.metric("Rainy Days - Last Week", int(metrics["rainy_days_week"]))
            st.metric("Rainfall - Last Month (mm)", f"{metrics['rainfall_last_month']:.1f}")
            st.metric("Rainy Days - Last Month", int(metrics["rainy_days_month"]))
        with c2:
            st.metric("Rainfall - Since Sowing (mm)", f"{metrics['rainfall_das']:.1f}")
            st.metric("Rainy Days - Since Sowing", int(metrics["rainy_days_das"]))
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
                return ["background-color: #0ea6ff" if (row.get("Rainfall", 0) > 0) else "" for _ in row]

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

        # Circlewise Data Matrix - ENHANCED MONTHLY ANALYSIS
        st.markdown("---")
        
        # Header with better styling
        st.markdown("""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 20px; 
                    border-radius: 10px; 
                    color: white; 
                    text-align: center;
                    margin-bottom: 20px;'>
            <h1 style='margin: 0; font-size: 28px;'>🌾 Monthly Crop Health Analysis</h1>
            <p style='margin: 5px 0 0 0; font-size: 16px; opacity: 0.9;'>
                Detailed monthly breakdown of vegetation, water, rainfall, and moisture indices
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        matrix_data = get_circlewise_data(district, taluka, circle, sowing_date, current_date)
        
        if not matrix_data.empty:
            # Create monthly analysis
            monthly_df = create_monthly_analysis(matrix_data)
            
            if monthly_df is not None and not monthly_df.empty:
                # Create Data Matrix for Combined Indicators (Indicator 1/2/3 across months)
                # We'll scan the original matrix_data for columns with 'indicator' + month
                def extract_indicator_matrix(mat_df):
                    # produce DataFrame: rows=Month, cols=Indicator 1/2/3
                    months = monthly_df['Month'].tolist()
                    ind_rows = []
                    # Look for columns that match patterns 'indicator-1' or 'indicator 1' and contain month
                    for m in months:
                        row = {'Month': m, 'Indicator-1': np.nan, 'Indicator-2': np.nan, 'Indicator-3': np.nan}
                        m_lower = m.lower()
                        for c in mat_df.columns:
                            c_lower = str(c).lower()
                            if m_lower in c_lower:
                                if 'indicator-1' in c_lower or ('indicator 1' in c_lower) or ('indicator_1' in c_lower):
                                    try:
                                        row['Indicator-1'] = mat_df[c].iloc[0]
                                    except Exception:
                                        row['Indicator-1'] = mat_df[c].values[0] if len(mat_df[c].values)>0 else np.nan
                                if 'indicator-2' in c_lower or ('indicator 2' in c_lower) or ('indicator_2' in c_lower):
                                    try:
                                        row['Indicator-2'] = mat_df[c].iloc[0]
                                    except Exception:
                                        row['Indicator-2'] = mat_df[c].values[0] if len(mat_df[c].values)>0 else np.nan
                                if 'indicator-3' in c_lower or ('indicator 3' in c_lower) or ('indicator_3' in c_lower):
                                    try:
                                        row['Indicator-3'] = mat_df[c].iloc[0]
                                    except Exception:
                                        row['Indicator-3'] = mat_df[c].values[0] if len(mat_df[c].values)>0 else np.nan
                        ind_rows.append(row)
                    return pd.DataFrame(ind_rows)

                indicator_matrix_df = extract_indicator_matrix(matrix_data)

                # Tabs: Monthly Summary Table, Data Charts, Combined Indicator (Data Matrix), Detailed Monthly Analysis, Data Download
                tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Monthly Summary Table", "📈 Data Charts", "🧩 Combined Indicator (Data Matrix)", "🔍 Detailed Monthly Analysis", "📥 Data download"])
                
                # -----------------------------
                # Tab 1: Monthly Summary Table
                # -----------------------------
                with tab1:
                    st.subheader("Monthly Index Summary")
                    
                    summary_data = []
                    for _, row in monthly_df.iterrows():
                        summary_data.append({
                            'Month': row['Month'],
                            '🌿 NDVI': f"{row['NDVI_Value'] if pd.notna(row['NDVI_Value']) else 'N/A'} {get_status_icon(row['NDVI_Category'])}",
                            '💧 NDWI': f"{row['NDWI_Value'] if pd.notna(row['NDWI_Value']) else 'N/A'} {get_status_icon(row['NDWI_Category'])}",
                            '🌧️ Rainfall Dev': f"{row['Rainfall_Dev_Value'] if pd.notna(row['Rainfall_Dev_Value']) else 'N/A'} {get_status_icon(row['Rainfall_Dev_Category'])}",
                            '📊 MAI': f"{row['MAI_Value'] if pd.notna(row['MAI_Value']) else 'N/A'} {get_status_icon(row['MAI_Category'])}"
                        })
                    
                    summary_df = pd.DataFrame(summary_data)
                    st.dataframe(summary_df, use_container_width=True)

                # -----------------------------
                # Tab 2: Data Charts
                # -----------------------------
                with tab2:
                    st.subheader("Monthly Charts - Individual Parameters")
                    # Column charts for Rainfall, Rainy Days, Tmax, Tmin, Max RH, Min RH
                    params_to_plot = [
                        ('Rainfall', 'Rainfall (Monthly)'),
                        ('Rainy_Days', 'Rainy Days (Monthly)'),
                        ('Tmax', 'Tmax (Monthly)'),
                        ('Tmin', 'Tmin (Monthly)'),
                        ('Max_RH', 'Max RH (Monthly)'),
                        ('Min_RH', 'Min RH (Monthly)')
                    ]
                    col_charts = create_single_param_column_charts(monthly_df, params_to_plot)
                    # display charts in 2 columns
                    chart_cols = st.columns(2)
                    i = 0
                    for key, fig in col_charts.items():
                        with chart_cols[i % 2]:
                            st.plotly_chart(fig, use_container_width=True)
                        i += 1
                    
                    st.markdown("---")
                    st.subheader("Line Chart - NDVI & NDWI (Monthly)")
                    indices_chart = create_indices_line_chart(monthly_df, indicators=['NDVI','NDWI'])
                    if indices_chart:
                        st.plotly_chart(indices_chart, use_container_width=True)
                    else:
                        st.info("Not enough NDVI/NDWI data for line chart.")
                    
                    st.markdown("---")
                    st.subheader("Column Charts - MAI & Rainfall Deviation (Monthly)")
                    special_params = [('MAI_Value', 'MAI (Monthly)'), ('Rainfall_Dev_Value', 'Rainfall Deviation (Monthly)')]
                    special_charts = create_single_param_column_charts(monthly_df, special_params)
                    for key, fig in special_charts.items():
                        st.plotly_chart(fig, use_container_width=True)

                # -----------------------------
                # Tab 3: Combined Indicator (Data Matrix)
                # -----------------------------
                with tab3:
                    st.subheader("Data Matrix - Combined Indicators (Indicator-1, 2 & 3 by Month)")
                    if indicator_matrix_df is not None and not indicator_matrix_df.empty:
                        # Normalize status values: only keep Good/Moderate/Poor if present
                        def normalize_status(v):
                            if pd.isna(v):
                                return ""
                            s = str(v).strip()
                            # try to extract Good/Moderate/Poor ignoring case
                            if re.search(r'good', s, re.IGNORECASE):
                                return "Good"
                            if re.search(r'moderate|average', s, re.IGNORECASE):
                                return "Moderate"
                            if re.search(r'poor|deficit|below', s, re.IGNORECASE):
                                return "Poor"
                            return s  # fallback to raw text

                        display_mat = indicator_matrix_df.copy()
                        for col in ['Indicator-1','Indicator-2','Indicator-3']:
                            if col in display_mat.columns:
                                display_mat[col] = display_mat[col].apply(normalize_status)
                        st.dataframe(display_mat, use_container_width=True)

                        # Also show a colored view with icons
                        colored_rows = []
                        for _, r in display_mat.iterrows():
                            colored_rows.append({
                                'Month': r['Month'],
                                'Indicator-1': f"{get_status_icon(r.get('Indicator-1',''))} {r.get('Indicator-1','')}",
                                'Indicator-2': f"{get_status_icon(r.get('Indicator-2',''))} {r.get('Indicator-2','')}",
                                'Indicator-3': f"{get_status_icon(r.get('Indicator-3',''))} {r.get('Indicator-3','')}"
                            })
                        st.markdown("### Visual status (icons)")
                        st.dataframe(pd.DataFrame(colored_rows), use_container_width=True)
                    else:
                        st.info("No indicator columns found in the data matrix for the selected area/date range.")
                    
                    st.markdown("---")
                    st.subheader("Original Matrix (Preview)")
                    st.dataframe(matrix_data.head(20), use_container_width=True)

                # -----------------------------
                # Tab 4: Detailed Monthly Analysis
                # -----------------------------
                with tab4:
                    st.subheader("Detailed Monthly Analysis")
                    for _, month_data in monthly_df.iterrows():
                        with st.expander(f"📅 {month_data['Month']} 2024 - Detailed Analysis", expanded=False):
                            col1, col2, col3, col4 = st.columns(4)
                            
                            with col1:
                                st.markdown(f"### 🌿 Vegetation Health (NDVI)")
                                st.metric("Value", f"{month_data['NDVI_Value']:.3f}" if pd.notna(month_data['NDVI_Value']) else "N/A")
                                st.markdown(f"**Status:** {get_status_icon(month_data['NDVI_Category'])} {month_data['NDVI_Category']}")
                            
                            with col2:
                                st.markdown(f"### 💧 Water Content (NDWI)")
                                st.metric("Value", f"{month_data['NDWI_Value']:.3f}" if pd.notna(month_data['NDWI_Value']) else "N/A")
                                st.markdown(f"**Status:** {get_status_icon(month_data['NDWI_Category'])} {month_data['NDWI_Category']}")
                            
                            with col3:
                                st.markdown(f"### 🌧️ Rainfall Deviation")
                                st.metric("Value", f"{month_data['Rainfall_Dev_Value']:.1f}%" if pd.notna(month_data['Rainfall_Dev_Value']) else "N/A")
                                st.markdown(f"**Status:** {get_status_icon(month_data['Rainfall_Dev_Category'])} {month_data['Rainfall_Dev_Category']}")
                            
                            with col4:
                                st.markdown(f"### 📊 Moisture Index (MAI)")
                                st.metric("Value", f"{month_data['MAI_Value']:.1f}" if pd.notna(month_data['MAI_Value']) else "N/A")
                                st.markdown(f"**Status:** {get_status_icon(month_data['MAI_Category'])} {month_data['MAI_Category']}")
                
                # -----------------------------
                # Tab 5: Data download
                # -----------------------------
                with tab5:
                    st.subheader("Download Data")
                    # Monthly analysis CSV
                    if monthly_df is not None and not monthly_df.empty:
                        csv_monthly = monthly_df.to_csv(index=False).encode('utf-8')
                        st.download_button("📥 Download Monthly Analysis (CSV)", csv_monthly, file_name=f"monthly_analysis_{district}_{taluka}_{circle}.csv", mime="text/csv")
                    else:
                        st.write("Monthly analysis not available to download.")
                    
                    # Indicator matrix CSV
                    if 'indicator_matrix_df' in locals() and indicator_matrix_df is not None and not indicator_matrix_df.empty:
                        csv_ind = indicator_matrix_df.to_csv(index=False).encode('utf-8')
                        st.download_button("📥 Download Indicator Matrix (CSV)", csv_ind, file_name=f"indicator_matrix_{district}_{taluka}_{circle}.csv", mime="text/csv")
                    else:
                        st.write("Indicator matrix not available for download.")
                    
                    # Original matrix CSV
                    if matrix_data is not None and not matrix_data.empty:
                        csv_matrix = matrix_data.to_csv(index=False).encode('utf-8')
                        st.download_button("📥 Download Original Data Matrix (CSV)", csv_matrix, file_name=f"original_matrix_{district}_{taluka}_{circle}.csv", mime="text/csv")
                    else:
                        st.write("Original matrix not available for download.")
                    
                    # Daily weather DAS data
                    if das_data is not None and not das_data.empty:
                        das_csv = das_data.copy().to_csv(index=False).encode('utf-8')
                        st.download_button("📥 Download Daily Weather (Since Sowing) (CSV)", das_csv, file_name=f"daily_weather_{district}_{taluka}_{circle}.csv", mime="text/csv")
                    else:
                        st.write("Daily weather (since sowing) not available for download.")
                    
                    # Full weather for selected area (optional slice)
                    try:
                        # slice weather_df for the selected administrative level for full period
                        w_df_slice = weather_df.copy()
                        if level == "Circle" and "Circle" in w_df_slice.columns:
                            w_df_slice = w_df_slice[w_df_slice["Circle"] == level_name]
                        elif level == "Taluka" and "Taluka" in w_df_slice.columns:
                            w_df_slice = w_df_slice[w_df_slice["Taluka"] == level_name]
                        elif level == "District" and "District" in w_df_slice.columns:
                            w_df_slice = w_df_slice[w_df_slice["District"] == level_name]
                        if not w_df_slice.empty:
                            w_csv = w_df_slice.to_csv(index=False).encode('utf-8')
                            st.download_button("📥 Download Full Weather Data (CSV)", w_csv, file_name=f"weather_full_{district}_{taluka}_{circle}.csv", mime="text/csv")
                        else:
                            st.write("No full weather data slice available for download.")
                    except Exception:
                        st.write("Could not prepare full weather data slice for download.")
                
                # Download option outside tabs (monthly)
                st.markdown("---")
                if monthly_df is not None and not monthly_df.empty:
                    csv = monthly_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Monthly Analysis as CSV",
                        data=csv,
                        file_name=f"monthly_analysis_{district}_{taluka}_{circle}.csv",
                        mime="text/csv"
                    )
            else:
                st.warning("Could not extract monthly analysis data from the matrix.")
                
            # Original matrix display (collapsible)
            with st.expander("🔍 View Original Data Matrix"):
                st.subheader("Original Data Matrix")
                st.dataframe(matrix_data, use_container_width=True)
                
        else:
            st.info("""
            ## 📊 No Data Available
            
            The Monthly Crop Health Analysis is not available for the selected parameters. 
            This could be due to:
            
            - **Data availability**: The selected area might not have satellite data coverage
            - **Date range**: The selected dates might be outside the data collection period
            - **Technical reasons**: Temporary unavailability of remote sensing data
            
            Please try adjusting your selection or check back later.
            """)

# -----------------------------
# FOOTER
# -----------------------------
st.markdown(
    """
    <div style='text-align: center; font-size: 16px; margin-top: 20px;'>
        💻 <b>Developed by:</b> Ashish Selokar <br>
        📧 For suggestions or queries, please email at:
        <a href="mailto:ashish111.selokar@gmail.com">ashish111.selokar@gmail.com</a> <br><br>
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
