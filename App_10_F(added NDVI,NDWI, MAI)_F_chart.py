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
    rules_url = "https://github.com/ASHISHSE/App_test/raw/main/rules - Copy_F.xlsx"
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
    selected_cols = ["District", "Taluka", "Circle"]
    
    # Get all columns that contain any of the target months
    for col in df.columns:
        col_lower = str(col).lower()
        # Skip the basic identifier columns we already have
        if col in selected_cols:
            continue
            
        # Check if this column contains any of our target months
        for month in months:
            month_lower = month.lower()
            if month_lower in col_lower and "2024" in col_lower:
                selected_cols.append(col)
                break  # Avoid adding same column multiple times

    # Ensure we have some data columns beyond the basic identifiers
    if len(selected_cols) <= 3:
        return pd.DataFrame()

    return df[selected_cols]

# -----------------------------
# IMPROVED FUNCTION FOR MONTHLY ANALYSIS WITH CORRECT COLUMN DETECTION
# -----------------------------
def create_monthly_analysis(matrix_data):
    """Create detailed monthly analysis with index values and categories"""
    if matrix_data.empty:
        return None
    
    monthly_data = []
    
    # Extract unique months from column names based on the specified format
    months = set()
    for col in matrix_data.columns:
        col_str = str(col)
        # Look for month names in the column names
        for month in ['January', 'February', 'March', 'April', 'May', 'June', 
                     'July', 'August', 'September', 'October', 'November', 'December']:
            if month.lower() in col_str.lower():
                months.add(month)
                break
    
    months = sorted(months, key=lambda x: datetime.strptime(x, "%B"))
    
    for month in months:
        month_data = {
            'Month': month,
            'NDVI_Value': None,
            'NDVI_Category': None,
            'NDWI_Value': None,
            'NDWI_Category': None,
            'Rainfall_Dev_Value': None,
            'Rainfall_Dev_Category': None,
            'MAI_Value': None,
            'MAI_Category': None,
            'Indicator_1': None,
            'Indicator_2': None,
            'Indicator_3': None
        }
        
        # Extract values for each parameter with improved pattern matching
        for col in matrix_data.columns:
            col_str = str(col)
            col_lower = col_str.lower()
            month_lower = month.lower()
            
            # Check if this column belongs to the current month
            if month_lower in col_lower and '2024' in col_str:
                
                value = matrix_data[col].iloc[0] if not matrix_data[col].empty else None
                
                # NDVI values and categories
                if 'ndvi' in col_lower and 'cat' not in col_lower and 'indicator' not in col_lower:
                    month_data['NDVI_Value'] = value
                elif 'ndvi' in col_lower and 'cat' in col_lower:
                    month_data['NDVI_Category'] = value
                
                # NDWI values and categories
                elif 'ndwi' in col_lower and 'cat' not in col_lower and 'indicator' not in col_lower:
                    month_data['NDWI_Value'] = value
                elif 'ndwi' in col_lower and 'cat' in col_lower:
                    month_data['NDWI_Category'] = value
                
                # Rainfall Deviation values and categories
                elif 'rainfall_dev' in col_lower and 'cat' not in col_lower:
                    month_data['Rainfall_Dev_Value'] = value
                elif 'rainfall_dev' in col_lower and 'cat' in col_lower:
                    month_data['Rainfall_Dev_Category'] = value
                
                # MAI values and categories
                elif 'mai' in col_lower and 'cat' not in col_lower:
                    month_data['MAI_Value'] = value
                elif 'mai' in col_lower and 'cat' in col_lower:
                    month_data['MAI_Category'] = value
        
        # Extract indicator values (they have different naming pattern)
        for col in matrix_data.columns:
            col_str = str(col)
            col_lower = col_str.lower()
            month_lower = month.lower()
            
            # Indicators have format like "Indicator-1 NDVI/NDWI_January"
            if 'indicator' in col_lower and month_lower in col_lower:
                value = matrix_data[col].iloc[0] if not matrix_data[col].empty else None
                
                if 'indicator-1' in col_lower or 'indicator-1' in col_lower:
                    month_data['Indicator_1'] = value
                elif 'indicator-2' in col_lower or 'indicator-2' in col_lower:
                    month_data['Indicator_2'] = value
                elif 'indicator-3' in col_lower or 'indicator-3' in col_lower:
                    month_data['Indicator_3'] = value
        
        monthly_data.append(month_data)
    
    return pd.DataFrame(monthly_data)

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
# IMPROVED DATA MATRIX PROCESSING FOR COMBINED INDICATOR TAB
# -----------------------------
def get_combined_indicators(matrix_data):
    """Extract combined indicators (Good, Moderate, Poor) for all months with correct column detection"""
    if matrix_data.empty:
        return pd.DataFrame()
    
    indicators_data = []
    months = ['January', 'February', 'March', 'April', 'May', 'June', 
              'July', 'August', 'September', 'October', 'November', 'December']
    
    for month in months:
        month_data = {'Month': month, 'Indicator_1': None, 'Indicator_2': None, 'Indicator_3': None}
        
        # Extract indicator values for the month with improved pattern matching
        for col in matrix_data.columns:
            col_str = str(col)
            col_lower = col_str.lower()
            month_lower = month.lower()
            
            # Look for indicators with the month name
            if 'indicator' in col_lower and month_lower in col_lower:
                value = matrix_data[col].iloc[0] if not matrix_data[col].empty else None
                
                if 'indicator-1' in col_lower or 'indicator-1' in col_lower:
                    month_data['Indicator_1'] = value
                elif 'indicator-2' in col_lower or 'indicator-2' in col_lower:
                    month_data['Indicator_2'] = value
                elif 'indicator-3' in col_lower or 'indicator-3' in col_lower:
                    month_data['Indicator_3'] = value
        
        indicators_data.append(month_data)
    
    return pd.DataFrame(indicators_data)

# -----------------------------
# CHART FUNCTIONS FOR DATA CHARTS TAB
# -----------------------------
def create_weather_parameters_charts(monthly_df):
    """Create column charts for weather parameters"""
    if monthly_df is None or monthly_df.empty:
        return None
    
    # Convert month names to datetime for proper sorting
    monthly_df['Month_Num'] = monthly_df['Month'].apply(lambda x: datetime.strptime(x, '%B').month)
    monthly_df = monthly_df.sort_values('Month_Num')
    
    # Create subplots for weather parameters
    fig = make_subplots(
        rows=3, cols=2,
        subplot_titles=('Rainfall Deviation (%)', 'MAI Index', 'NDVI Index', 'NDWI Index', 
                       'Vegetation Health', 'Water Content'),
        vertical_spacing=0.15,
        horizontal_spacing=0.1
    )
    
    # Rainfall Deviation
    if any(pd.notna(monthly_df['Rainfall_Dev_Value'])):
        fig.add_trace(
            go.Bar(name='Rainfall Deviation', x=monthly_df['Month'], y=monthly_df['Rainfall_Dev_Value'], 
                   marker_color='blue'),
            row=1, col=1
        )
    
    # MAI Index
    if any(pd.notna(monthly_df['MAI_Value'])):
        fig.add_trace(
            go.Bar(name='MAI', x=monthly_df['Month'], y=monthly_df['MAI_Value'],
                   marker_color='lightblue'),
            row=1, col=2
        )
    
    # NDVI Index
    if any(pd.notna(monthly_df['NDVI_Value'])):
        fig.add_trace(
            go.Bar(name='NDVI', x=monthly_df['Month'], y=monthly_df['NDVI_Value'],
                   marker_color='green'),
            row=2, col=1
        )
    
    # NDWI Index
    if any(pd.notna(monthly_df['NDWI_Value'])):
        fig.add_trace(
            go.Bar(name='NDWI', x=monthly_df['Month'], y=monthly_df['NDWI_Value'],
                   marker_color='orange'),
            row=2, col=2
        )
    
    # Vegetation Health (NDVI Category as numeric for visualization)
    if any(pd.notna(monthly_df['NDVI_Category'])):
        # Convert categories to numeric values for visualization
        category_map = {'Good': 3, 'Moderate': 2, 'Poor': 1, 'Very Poor': 0}
        veg_health = monthly_df['NDVI_Category'].map(category_map)
        fig.add_trace(
            go.Bar(name='Vegetation Health', x=monthly_df['Month'], y=veg_health,
                   marker_color='darkgreen'),
            row=3, col=1
        )
        fig.update_yaxes(title_text="Health Score (3=Good, 0=Poor)", row=3, col=1)
    
    # Water Content (NDWI Category as numeric for visualization)
    if any(pd.notna(monthly_df['NDWI_Category'])):
        category_map = {'Good': 3, 'Moderate': 2, 'Poor': 1, 'Very Poor': 0}
        water_content = monthly_df['NDWI_Category'].map(category_map)
        fig.add_trace(
            go.Bar(name='Water Content', x=monthly_df['Month'], y=water_content,
                   marker_color='darkblue'),
            row=3, col=2
        )
        fig.update_yaxes(title_text="Water Score (3=Good, 0=Poor)", row=3, col=2)
    
    fig.update_layout(
        title="Monthly Parameters Analysis",
        height=900,
        showlegend=False,
        template="plotly_white"
    )
    
    # Update y-axis titles
    fig.update_yaxes(title_text="Deviation %", row=1, col=1)
    fig.update_yaxes(title_text="MAI Value", row=1, col=2)
    fig.update_yaxes(title_text="NDVI Value", row=2, col=1)
    fig.update_yaxes(title_text="NDWI Value", row=2, col=2)
    
    return fig

def create_indices_line_chart(monthly_df):
    """Create line chart for NDVI, NDWI indices"""
    if monthly_df is None or monthly_df.empty:
        return None
    
    # Convert month names to datetime for proper sorting
    monthly_df['Month_Num'] = monthly_df['Month'].apply(lambda x: datetime.strptime(x, '%B').month)
    monthly_df = monthly_df.sort_values('Month_Num')
    
    fig = go.Figure()
    
    # Add NDVI line
    if any(pd.notna(monthly_df['NDVI_Value'])):
        fig.add_trace(go.Scatter(
            x=monthly_df['Month'],
            y=monthly_df['NDVI_Value'],
            mode='lines+markers',
            name='NDVI',
            line=dict(color='green', width=3),
            marker=dict(size=8)
        ))
    
    # Add NDWI line
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

def create_mai_rainfall_chart(monthly_df):
    """Create column chart for MAI and Rainfall Deviation"""
    if monthly_df is None or monthly_df.empty:
        return None
    
    # Convert month names to datetime for proper sorting
    monthly_df['Month_Num'] = monthly_df['Month'].apply(lambda x: datetime.strptime(x, '%B').month)
    monthly_df = monthly_df.sort_values('Month_Num')
    
    fig = go.Figure()
    
    # Add MAI bars
    if any(pd.notna(monthly_df['MAI_Value'])):
        fig.add_trace(go.Bar(
            name='MAI',
            x=monthly_df['Month'],
            y=monthly_df['MAI_Value'],
            marker_color='orange',
            yaxis='y'
        ))
    
    # Add Rainfall Deviation bars on secondary axis if values are very different
    if any(pd.notna(monthly_df['Rainfall_Dev_Value'])):
        fig.add_trace(go.Bar(
            name='Rainfall Deviation (%)',
            x=monthly_df['Month'],
            y=monthly_df['Rainfall_Dev_Value'],
            marker_color='purple',
            yaxis='y2'
        ))
        
        # Add secondary y-axis for Rainfall Deviation
        fig.update_layout(
            yaxis2=dict(
                title='Rainfall Deviation (%)',
                overlaying='y',
                side='right'
            )
        )
    else:
        # If no rainfall deviation data, use single y-axis
        fig.update_layout(yaxis_title="Value")
    
    fig.update_layout(
        title="Monthly MAI & Rainfall Deviation Analysis",
        xaxis_title="Month",
        barmode='group',
        height=400,
        template="plotly_white"
    )
    
    return fig

# -----------------------------
# DEBUG FUNCTION TO SHOW COLUMN NAMES
# -----------------------------
def debug_column_names(matrix_data):
    """Debug function to show available column names"""
    if matrix_data.empty:
        return "No data available"
    
    columns_info = []
    for col in matrix_data.columns:
        col_str = str(col)
        columns_info.append({
            'Column Name': col_str,
            'Has NDVI': 'NDVI' in col_str.upper(),
            'Has NDWI': 'NDWI' in col_str.upper(),
            'Has MAI': 'MAI' in col_str.upper(),
            'Has Rainfall': 'RAINFALL' in col_str.upper(),
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
        matrix_data = get_circlewise_data(district, taluka, circle, sowing_date, current_date)
        monthly_df = create_monthly_analysis(matrix_data) if not matrix_data.empty else None
        
        # Create tabs
        tab1, tab2, tab3, tab4 = st.tabs(["🌤️ Weather Metrics", "📊 Data Charts", "🔍 Combined Indicator", "💾 Data Download"])
        
        # TAB 1: WEATHER METRICS (Existing functionality)
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
        
        # TAB 2: DATA CHARTS
        with tab2:
            st.header("📊 Data Charts - Monthly Analysis")
            
            if not matrix_data.empty:
                # Debug information (collapsible)
                with st.expander("🔍 Debug: View Column Names Structure"):
                    st.write("This section shows how the system is interpreting your data columns:")
                    debug_df = debug_column_names(matrix_data)
                    st.dataframe(debug_df, use_container_width=True)
            
            if monthly_df is not None and not monthly_df.empty:
                # Display the monthly data for verification
                st.subheader("📋 Detected Monthly Data")
                st.dataframe(monthly_df, use_container_width=True)
                
                # Weather Parameters Column Charts
                st.subheader("🌤️ Weather Parameters - Monthly Column Charts")
                weather_chart = create_weather_parameters_charts(monthly_df)
                if weather_chart:
                    st.plotly_chart(weather_chart, use_container_width=True)
                else:
                    st.info("Weather parameters chart data not available.")
                
                # NDVI/NDWI Line Chart
                st.subheader("📈 NDVI & NDWI Indices - Monthly Line Chart")
                indices_chart = create_indices_line_chart(monthly_df)
                if indices_chart:
                    st.plotly_chart(indices_chart, use_container_width=True)
                else:
                    st.info("NDVI/NDWI data not available for line chart.")
                
                # MAI & Rainfall Deviation Column Chart
                st.subheader("🌧️ MAI & Rainfall Deviation - Monthly Column Chart")
                mai_chart = create_mai_rainfall_chart(monthly_df)
                if mai_chart:
                    st.plotly_chart(mai_chart, use_container_width=True)
                else:
                    st.info("MAI and Rainfall Deviation data not available.")
            else:
                st.info("No monthly analysis data available for the selected parameters.")
                if not matrix_data.empty:
                    st.write("Available columns in your data:")
                    st.write(list(matrix_data.columns))
        
        # TAB 3: COMBINED INDICATOR
        with tab3:
            st.header("🔍 Combined Indicator - Data Matrix")
            
            if not matrix_data.empty:
                # Get combined indicators
                indicators_df = get_combined_indicators(matrix_data)
                
                if not indicators_df.empty:
                    st.subheader("Monthly Indicator Status")
                    
                    # Display the indicators data for verification
                    st.write("Detected Indicator Values:")
                    st.dataframe(indicators_df, use_container_width=True)
                    
                    # Create a styled table for indicators
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
                        
                        # Apply styling based on status
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
                        
                        # Style the dataframe
                        styled_df = indicators_display_df.style.map(lambda x: style_indicators(x))
                        st.dataframe(styled_df, use_container_width=True)
                        
                        # Summary statistics
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
                
                # Original matrix data (collapsible)
                with st.expander("View Original Data Matrix"):
                    st.dataframe(matrix_data, use_container_width=True)
            else:
                st.info("No data matrix available for the selected parameters.")
        
        # TAB 4: DATA DOWNLOAD
        with tab4:
            st.header("💾 Data Download")
            
            # Available datasets for download
            st.subheader("Available Datasets")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Weather Data
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
                
                # Monthly Analysis Data
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
                # Data Matrix
                st.write("**🔍 Data Matrix**")
                if not matrix_data.empty:
                    matrix_csv = matrix_data.to_csv(index=False)
                    st.download_button(
                        label="Download Data Matrix (CSV)",
                        data=matrix_csv,
                        file_name=f"data_matrix_{district}_{taluka}_{circle}.csv",
                        mime="text/csv"
                    )
                else:
                    st.write("No data matrix available")
                
                # Combined Indicators
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
            
            # Data preview sections
            st.subheader("Data Previews")
            
            preview_tabs = st.tabs(["Weather Data", "Monthly Analysis", "Data Matrix", "Indicators"])
            
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
                if not matrix_data.empty:
                    st.dataframe(matrix_data.head(), use_container_width=True)
                else:
                    st.info("No data matrix available for preview")
                    
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

