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
import xlrd  # Required for reading .xlsb files

st.set_page_config(page_title="🌱 Crop Advisory System", page_icon="🌱", layout="wide")

# -----------------------------
# LOAD DATA (WEATHER, RULES, SOWING)
# -----------------------------
@st.cache_data
def load_data():
    weather_url = "https://github.com/ASHISHSE/App_test/raw/main/weather.xlsb"
    rules_url = "https://github.com/ASHISHSE/App_test/raw/main/rules - Copy_F.xlsx"
    sowing_url = "https://github.com/ASHISHSE/App_test/raw/main/sowing_calendar1.xlsx"

    wres = requests.get(weather_url, timeout=10)
    rres = requests.get(rules_url, timeout=10)
    sres = requests.get(sowing_url, timeout=10)

    weather_df = pd.read_excel(BytesIO(wres.content), engine='pyxlsb')
    rules_df = pd.read_excel(BytesIO(rres.content))
    sowing_df = pd.read_excel(BytesIO(sres.content))

    # Flexible date column detection
    date_col = None
    for candidate in ["Date(DD-MM-YYYY)", "DD-MM-YYYY", "Date"]:
        if candidate in weather_df.columns:
            date_col = candidate
            break
    if date_col is None:
        raise ValueError("weather.xlsb must have a column named 'Date(DD-MM-YYYY)' or similar")

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
    url = "https://github.com/ASHISHSE/App_test/raw/main/Circlewise_Data_Matrix_Indicator_2024_F_upload.xlsx"
    xls = pd.ExcelFile(url)
    rs_data = pd.read_excel(xls, sheet_name="RS Data indices")
    matrix_data = pd.read_excel(xls, sheet_name="Data Matrix")
    return rs_data, matrix_data

rs_data_df, matrix_data_df = load_circlewise_data()

# -----------------------------
# MODIFIED HELPER FUNCTION FOR CIRCLEWISE DATA
# -----------------------------
def get_circlewise_data(district, taluka, circle, sowing_date, current_date):
    rs_df = rs_data_df.copy()
    matrix_df = matrix_data_df.copy()

    # Filter by District, Taluka, Circle
    rs_df = rs_df[(rs_df["District"] == district) & (rs_df["Taluka"] == taluka)]
    matrix_df = matrix_df[(matrix_df["District"] == district) & (matrix_df["Taluka"] == taluka)]
    if circle:
        rs_df = rs_df[rs_df["Circle"] == circle]
        matrix_df = matrix_df[matrix_df["Circle"] == circle]

    if rs_df.empty or matrix_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Generate list of months between sowing_date and current_date
    months = []
    current = sowing_date.replace(day=1)
    end = current_date.replace(day=1)
    
    while current <= end:
        months.append(current.strftime("%B"))
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    months = list(dict.fromkeys(months))  # Remove duplicates

    # Select relevant columns from RS Data indices (NDVI, NDWI, MAI)
    rs_cols = ["District", "Taluka", "Circle"]
    for col in rs_df.columns:
        col_lower = str(col).lower()
        if any(month.lower() in col_lower for month in months) and '2024' in col_lower:
            if any(ind in col_lower for ind in ['ndvi', 'ndwi', 'mai']) and 'cat' not in col_lower:
                rs_cols.append(col)

    # Select relevant columns from Data Matrix (Indicators)
    matrix_cols = ["District", "Taluka", "Circle"]
    for col in matrix_df.columns:
        col_lower = str(col).lower()
        if any(month.lower() in col_lower for month in months) and '2024' in col_lower:
            if 'indicator' in col_lower:
                matrix_cols.append(col)

    return rs_df[rs_cols], matrix_df[matrix_cols]

# -----------------------------
# IMPROVED FUNCTION FOR MONTHLY ANALYSIS
# -----------------------------
def create_monthly_analysis(rs_data, matrix_data):
    if rs_data.empty or matrix_data.empty:
        return None
    
    monthly_data = []
    months = ['January', 'February', 'March', 'April', 'May', 'June', 
              'July', 'August', 'September', 'October', 'November', 'December']
    
    for month in months:
        month_data = {
            'Month': month,
            'NDVI_Value': None,
            'NDVI_Category': None,
            'NDWI_Value': None,
            'NDWI_Category': None,
            'MAI_Value': None,
            'MAI_Category': None,
            'Indicator_1': None,
            'Indicator_2': None,
            'Indicator_3': None
        }
        
        # Extract from RS Data indices
        for col in rs_data.columns:
            col_str = str(col)
            col_lower = col_str.lower()
            month_lower = month.lower()
            
            if month_lower in col_lower and '2024' in col_str:
                value = rs_data[col].iloc[0] if not rs_data[col].empty else None
                
                if 'ndvi' in col_lower and 'cat' not in col_lower:
                    month_data['NDVI_Value'] = value
                elif 'ndvi' in col_lower and 'cat' in col_lower:
                    month_data['NDVI_Category'] = value
                elif 'ndwi' in col_lower and 'cat' not in col_lower:
                    month_data['NDWI_Value'] = value
                elif 'ndwi' in col_lower and 'cat' in col_lower:
                    month_data['NDWI_Category'] = value
                elif 'mai' in col_lower and 'cat' not in col_lower:
                    month_data['MAI_Value'] = value
                elif 'mai' in col_lower and 'cat' in col_lower:
                    month_data['MAI_Category'] = value
        
        # Extract from Data Matrix
        for col in matrix_data.columns:
            col_str = str(col)
            col_lower = col_str.lower()
            month_lower = month.lower()
            
            if 'indicator' in col_lower and month_lower in col_lower:
                value = matrix_data[col].iloc[0] if not matrix_data[col].empty else None
                
                if 'indicator-1' in col_lower:
                    month_data['Indicator_1'] = value
                elif 'indicator-2' in col_lower:
                    month_data['Indicator_2'] = value
                elif 'indicator-3' in col_lower:
                    month_data['Indicator_3'] = value
        
        monthly_data.append(month_data)
    
    return pd.DataFrame([m for m in monthly_data if any(v is not None for k, v in m.items() if k != 'Month')])

def get_status_color(status):
    if pd.isna(status):
        return '#f8f9fa'
    status_lower = str(status).lower()
    if any(word in status_lower for word in ['good', 'normal', 'above', 'excellent', 'satisfactory']):
        return '#d4edda'
    elif any(word in status_lower for word in ['moderate', 'average', 'medium', 'moderately']):
        return '#fff3cd'
    elif any(word in status_lower for word in ['poor', 'deficit', 'below', 'low', 'unsatisfactory']):
        return '#f8d7da'
    else:
        return '#e9ecef'

def get_status_icon(status):
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
# COMBINED INDICATOR PROCESSING
# -----------------------------
def get_combined_indicators(matrix_data):
    if matrix_data.empty:
        return pd.DataFrame()
    
    indicators_data = []
    months = ['January', 'February', 'March', 'April', 'May', 'June', 
              'July', 'August', 'September', 'October', 'November', 'December']
    
    for month in months:
        month_data = {'Month': month, 'Indicator_1': None, 'Indicator_2': None, 'Indicator_3': None}
        
        for col in matrix_data.columns:
            col_str = str(col)
            col_lower = col_str.lower()
            month_lower = month.lower()
            
            if 'indicator' in col_lower and month_lower in col_lower:
                value = matrix_data[col].iloc[0] if not matrix_data[col].empty else None
                
                if 'indicator-1' in col_lower:
                    month_data['Indicator_1'] = value
                elif 'indicator-2' in col_lower:
                    month_data['Indicator_2'] = value
                elif 'indicator-3' in col_lower:
                    month_data['Indicator_3'] = value
        
        indicators_data.append(month_data)
    
    return pd.DataFrame([m for m in indicators_data if any(v is not None for k, v in m.items() if k != 'Month')])

# -----------------------------
# CHART FUNCTIONS
# -----------------------------
def create_weather_parameters_charts(monthly_df):
    if monthly_df is None or monthly_df.empty:
        return None
    
    monthly_df['Month_Num'] = monthly_df['Month'].apply(lambda x: datetime.strptime(x, '%B').month)
    monthly_df = monthly_df.sort_values('Month_Num')
    
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('NDVI Index', 'NDWI Index', 'MAI Index', 'Vegetation & Water Status'),
        vertical_spacing=0.15,
        horizontal_spacing=0.1
    )
    
    # NDVI Index
    if any(pd.notna(monthly_df['NDVI_Value'])):
        fig.add_trace(
            go.Bar(name='NDVI', x=monthly_df['Month'], y=monthly_df['NDVI_Value'],
                   marker_color='green'),
            row=1, col=1
        )
    
    # NDWI Index
    if any(pd.notna(monthly_df['NDWI_Value'])):
        fig.add_trace(
            go.Bar(name='NDWI', x=monthly_df['Month'], y=monthly_df['NDWI_Value'],
                   marker_color='blue'),
            row=1, col=2
        )
    
    # MAI Index
    if any(pd.notna(monthly_df['MAI_Value'])):
        fig.add_trace(
            go.Bar(name='MAI', x=monthly_df['Month'], y=monthly_df['MAI_Value'],
                   marker_color='orange'),
            row=2, col=1
        )
    
    # Combined Vegetation Health and Water Content
    if any(pd.notna(monthly_df['NDVI_Category'])) or any(pd.notna(monthly_df['NDWI_Category'])):
        category_map = {'Good': 3, 'Moderate': 2, 'Poor': 1, 'Very Poor': 0}
        veg_health = monthly_df['NDVI_Category'].map(category_map)
        water_content = monthly_df['NDWI_Category'].map(category_map)
        
        fig.add_trace(
            go.Bar(name='Vegetation Health (NDVI)', x=monthly_df['Month'], y=veg_health,
                   marker_color='darkgreen'),
            row=2, col=2
        )
        fig.add_trace(
            go.Bar(name='Water Content (NDWI)', x=monthly_df['Month'], y=water_content,
                   marker_color='darkblue', xaxis='x4', offsetgroup=2),
            row=2, col=2
        )
        fig.update_yaxes(title_text="Score (3=Good, 0=Poor)", row=2, col=2)
    
    fig.update_layout(
        title="Monthly Parameters Analysis",
        height=600,
        showlegend=True,
        template="plotly_white",
        barmode='group'
    )
    
    fig.update_yaxes(title_text="NDVI Value", row=1, col=1)
    fig.update_yaxes(title_text="NDWI Value", row=1, col=2)
    fig.update_yaxes(title_text="MAI Value", row=2, col=1)
    
    return fig

def create_indices_line_chart(monthly_df):
    if monthly_df is None or monthly_df.empty:
        return None
    
    monthly_df['Month_Num'] = monthly_df['Month'].apply(lambda x: datetime.strptime(x, '%B').month)
    monthly_df = monthly_df.sort_values('Month_Num')
    
    fig = go.Figure()
    
    if any(pd.notna(monthly_df['NDVI_Value'])):
        fig.add_trace(go.Scatter(
            x=monthly_df['Month'],
            y=monthly_df['NDVI_Value'],
            mode='lines+markers',
            name='NDVI',
            line=dict(color='green', width=3),
            marker=dict(size=8)
        ))
    
    if any(pd.notna(monthly_df['NDWI_Value'])):
        fig.add_trace(go.Scatter(
            x=monthly_df['Month'],
            y=monthly_df['NDWI_Value'],
            mode='lines+markers',
            name='NDWI',
            line=dict(color='blue', width=3),
            marker=dict(size=8)
        ))
    
    fig.update_layout(
        title="Monthly NDVI & NDWI Indices Trend",
        xaxis_title="Month",
        yaxis_title="Index Value",
        height=400,
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig

def create_mai_chart(monthly_df):
    if monthly_df is None or monthly_df.empty:
        return None
    
    monthly_df['Month_Num'] = monthly_df['Month'].apply(lambda x: datetime.strptime(x, '%B').month)
    monthly_df = monthly_df.sort_values('Month_Num')
    
    fig = go.Figure()
    
    if any(pd.notna(monthly_df['MAI_Value'])):
        fig.add_trace(go.Bar(
            name='MAI',
            x=monthly_df['Month'],
            y=monthly_df['MAI_Value'],
            marker_color='orange'
        ))
    
    fig.update_layout(
        title="Monthly MAI Analysis",
        xaxis_title="Month",
        yaxis_title="MAI Value",
        height=400,
        template="plotly_white"
    )
    
    return fig

# -----------------------------
# DEBUG FUNCTION
# -----------------------------
def debug_column_names(rs_data, matrix_data):
    columns_info = []
    for col in rs_data.columns:
        col_str = str(col)
        columns_info.append({
            'Source': 'RS Data indices',
            'Column Name': col_str,
            'Has NDVI': 'NDVI' in col_str.upper(),
            'Has NDWI': 'NDWI' in col_str.upper(),
            'Has MAI': 'MAI' in col_str.upper(),
            'Has Category': 'CAT' in col_str.upper()
        })
    for col in matrix_data.columns:
        col_str = str(col)
        columns_info.append({
            'Source': 'Data Matrix',
            'Column Name': col_str,
            'Has Indicator': 'INDICATOR' in col_str.upper(),
            'Has Category': 'CAT' in col_str.upper()
        })
    
    return pd.DataFrame(columns_info)

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
# MAIN UI WITH TABS
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
# MAIN LOGIC WITH TABS
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
        rs_data, matrix_data = get_circlewise_data(district, taluka, circle, sowing_date, current_date)
        monthly_df = create_monthly_analysis(rs_data, matrix_data) if not rs_data.empty and not matrix_data.empty else None
        
        tab1, tab2, tab3, tab4 = st.tabs(["🌤️ Weather Metrics", "📊 Data Charts", "🔍 Combined Indicator", "💾 Data Download"])
        
        with tab1:
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

            st.markdown("---")
            st.header("📝 Comment on Sowing")
            comments = get_sowing_comments(sowing_date_str, district, taluka, circle, crop, sowing_df)
            if comments:
                for c in comments:
                    st.write(f"**Matched:** {c['matched_fn']}")
                    st.write(f"• {c['comment']}")
            else:
                st.write("No matching sowing comments found.")

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
        
        with tab2:
            st.header("📊 Data Charts - Monthly Analysis")
            
            if not rs_data.empty or not matrix_data.empty:
                with st.expander("🔍 Debug: View Column Names Structure"):
                    st.write("This section shows how the system is interpreting your data columns:")
                    debug_df = debug_column_names(rs_data, matrix_data)
                    st.dataframe(debug_df, use_container_width=True)
            
            if monthly_df is not None and not monthly_df.empty:
                st.subheader("📋 Detected Monthly Data")
                st.dataframe(monthly_df, use_container_width=True)
                
                st.subheader("🌤️ Parameters - Monthly Column Charts")
                weather_chart = create_weather_parameters_charts(monthly_df)
                if weather_chart:
                    st.plotly_chart(weather_chart, use_container_width=True)
                else:
                    st.info("Parameters chart data not available.")
                
                st.subheader("📈 NDVI & NDWI Indices - Monthly Line Chart")
                indices_chart = create_indices_line_chart(monthly_df)
                if indices_chart:
                    st.plotly_chart(indices_chart, use_container_width=True)
                else:
                    st.info("NDVI/NDWI data not available for line chart.")
                
                st.subheader("🌧️ MAI - Monthly Column Chart")
                mai_chart = create_mai_chart(monthly_df)
                if mai_chart:
                    st.plotly_chart(mai_chart, use_container_width=True)
                else:
                    st.info("MAI data not available.")
            else:
                st.info("No monthly analysis data available for the selected parameters.")
                if not rs_data.empty or not matrix_data.empty:
                    st.write("Available columns in RS Data indices:")
                    st.write(list(rs_data.columns))
                    st.write("Available columns in Data Matrix:")
                    st.write(list(matrix_data.columns))
        
        with tab3:
            st.header("🔍 Combined Indicator - Data Matrix")
            
            if not matrix_data.empty:
                indicators_df = get_combined_indicators(matrix_data)
                
                if not indicators_df.empty:
                    st.subheader("Monthly Indicator Status")
                    st.write("Detected Indicator Values:")
                    st.dataframe(indicators_df, use_container_width=True)
                    
                    display_data = []
                    for _, row in indicators_df.iterrows():
                        if pd.notna(row.get('Indicator_1')) or pd.notna(row.get('Indicator_2')) or pd.notna(row.get('Indicator_3')):
                            display_data.append({
                                'Month': row['Month'],
                                'Indicator-1 (NDVI/NDWI)': f"{get_status_icon(row.get('Indicator_1', ''))} {row.get('Indicator_1', 'N/A')}",
                                'Indicator-2 (Rainfall/MAI)': f"{get_status_icon(row.get('Indicator_2', ''))} {row.get('Indicator_2', 'N/A')}",
                                'Indicator-3 (Composite)': f"{get_status_icon(row.get('Indicator_3', ''))} {row.get('Indicator_3', 'N/A')}"
                            })
                    
                    if display_data:
                        indicators_display_df = pd.DataFrame(display_data)
                        
                        def style_indicators(val):
                            if pd.isna(val):
                                return ''
                            val_str = str(val).lower()
                            if any(word in val_str for word in ['good', 'normal', 'above']):
                                return 'background-color: #d4edda; color: #155724;'
                            elif any(word in val_str for word in ['moderate', 'average']):
                                return 'background-color: #fff3cd; color: #856404;'
                            elif any(word in val_str for word in ['poor', 'deficit', 'below']):
                                return 'background-color: #f8d7da; color: #721c24;'
                            return ''
                        
                        styled_df = indicators_display_df.style.map(lambda x: style_indicators(x))
                        st.dataframe(styled_df, use_container_width=True)
                        
                        st.subheader("Indicator Summary")
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            good_count = indicators_display_df.applymap(
                                lambda x: 'good' in str(x).lower() if pd.notna(x) else False
                            ).sum().sum()
                            st.metric("Good Indicators", good_count)
                        
                        with col2:
                            moderate_count = indicators_display_df.applymap(
                                lambda x: 'moderate' in str(x).lower() if pd.notna(x) else False
                            ).sum().sum()
                            st.metric("Moderate Indicators", moderate_count)
                        
                        with col3:
                            poor_count = indicators_display_df.applymap(
                                lambda x: 'poor' in str(x).lower() if pd.notna(x) else False
                            ).sum().sum()
                            st.metric("Poor Indicators", poor_count)
                    else:
                        st.info("No indicator data found for the selected time period.")
                
                with st.expander("View Original Data Matrix"):
                    st.dataframe(matrix_data, use_container_width=True)
            else:
                st.info("No data matrix available for the selected parameters.")
        
        with tab4:
            st.header("💾 Data Download")
            
            st.subheader("Available Datasets")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**🌤️ Weather Data**")
                if not das_data.empty:
                    weather_csv = das_data.to_csv(index=False)
                    st.download_button(
                        label="Download Weather Data (CSV)",
                        data=weather_csv,
                        file_name=f"weather_data_{district}_{taluka}_{circle}.csv",
                        mime="text/csv"
                    )
                else:
                    st.write("No weather data available")
                
                st.write("**📊 Monthly Analysis Data**")
                if monthly_df is not None and not monthly_df.empty:
                    monthly_csv = monthly_df.to_csv(index=False)
                    st.download_button(
                        label="Download Monthly Analysis (CSV)",
                        data=monthly_csv,
                        file_name=f"monthly_analysis_{district}_{taluka}_{circle}.csv",
                        mime="text/csv"
                    )
                else:
                    st.write("No monthly analysis data available")
            
            with col2:
                st.write("**🔍 RS Data indices**")
                if not rs_data.empty:
                    rs_csv = rs_data.to_csv(index=False)
                    st.download_button(
                        label="Download RS Data indices (CSV)",
                        data=rs_csv,
                        file_name=f"rs_data_{district}_{taluka}_{circle}.csv",
                        mime="text/csv"
                    )
                else:
                    st.write("No RS data available")
                
                st.write("**📈 Combined Indicators**")
                if not matrix_data.empty:
                    indicators_df = get_combined_indicators(matrix_data)
                    if not indicators_df.empty:
                        indicators_csv = indicators_df.to_csv(index=False)
                        st.download_button(
                            label="Download Indicators (CSV)",
                            data=indicators_csv,
                            file_name=f"indicators_{district}_{taluka}_{circle}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.write("No indicators data available")
                else:
                    st.write("No indicators data available")
            
            st.subheader("Data Previews")
            
            preview_tabs = st.tabs(["Weather Data", "Monthly Analysis", "RS Data indices", "Indicators"])
            
            with preview_tabs[0]:
                if not das_data.empty:
                    st.dataframe(das_data.head(10), use_container_width=True)
                else:
                    st.info("No weather data available for preview")
            
            with preview_tabs[1]:
                if monthly_df is not None and not monthly_df.empty:
                    st.dataframe(monthly_df, use_container_width=True)
                else:
                    st.info("No monthly analysis data available for preview")
            
            with preview_tabs[2]:
                if not rs_data.empty:
                    st.dataframe(rs_data.head(), use_container_width=True)
                else:
                    st.info("No RS data available for preview")
                    
            with preview_tabs[3]:
                if not matrix_data.empty:
                    indicators_df = get_combined_indicators(matrix_data)
                    if not indicators_df.empty:
                        st.dataframe(indicators_df, use_container_width=True)
                    else:
                        st.info("No indicators data available for preview")
                else:
                    st.info("No indicators data available for preview")

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
