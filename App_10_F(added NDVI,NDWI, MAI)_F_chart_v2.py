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
    # Return empty figure - no data display
    fig = go.Figure()
    fig.update_layout(
        title="Data Display Disabled",
        xaxis_title="",
        yaxis_title="",
        height=400,
        template="plotly_white",
        annotations=[dict(text="Data display is currently disabled", x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False)]
    )
    return fig

def create_indices_line_chart(monthly_df):
    """Create line chart for NDVI, NDWI indices"""
    # Return empty figure - no data display
    fig = go.Figure()
    fig.update_layout(
        title="Data Display Disabled",
        xaxis_title="",
        yaxis_title="",
        height=400,
        template="plotly_white",
        annotations=[dict(text="Data display is currently disabled", x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False)]
    )
    return fig

def create_mai_rainfall_chart(monthly_df):
    """Create column chart for MAI and Rainfall Deviation"""
    # Return empty figure - no data display
    fig = go.Figure()
    fig.update_layout(
        title="Data Display Disabled",
        xaxis_title="",
        yaxis_title="",
        height=400,
        template="plotly_white",
        annotations=[dict(text="Data display is currently disabled", x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False)]
    )
    return fig

# -----------------------------
# DEBUG FUNCTION TO SHOW COLUMN NAMES
# -----------------------------
def debug_column_names(matrix_data):
    """Debug function to show available column names"""
    return pd.DataFrame()  # Return empty DataFrame

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
    return []  # Return empty list - no data display

def calculate_weather_metrics(weather_data, level, name, sowing_date_str, current_date_str):
    # Return empty metrics - no data display
    return {
        "rainfall_das": 0,
        "rainfall_last_week": 0,
        "rainfall_last_month": 0,
        "rainy_days_das": 0,
        "rainy_days_week": 0,
        "rainy_days_month": 0,
        "tmax_avg": None,
        "tmin_avg": None,
        "max_rh_avg": None,
        "min_rh_avg": None,
        "das": 0,
        "das_data": pd.DataFrame()  # Empty DataFrame
    }

def get_growth_advisory(crop, das, rainfall_das, rules_df):
    return None  # Return None - no data display

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

        # Create tabs but don't display any data
        tab1, tab2, tab3, tab4 = st.tabs(["🌤️ Weather Metrics", "📊 Data Charts", "🔍 Combined Indicator", "💾 Data Download"])
        
        # TAB 1: WEATHER METRICS - No data displayed
        with tab1:
            st.header("🌤️ Weather Metrics")
            st.info("Data display is currently disabled for this section.")
            
            # Empty columns - no metrics displayed
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Rainfall - Last Week (mm)", "N/A")
                st.metric("Rainy Days - Last Week", "N/A")
                st.metric("Rainfall - Last Month (mm)", "N/A")
                st.metric("Rainy Days - Last Month", "N/A")
            with c2:
                st.metric("Rainfall - Since Sowing (mm)", "N/A")
                st.metric("Rainy Days - Since Sowing", "N/A")
                st.metric("Tmax Avg", "N/A")
                st.metric("Tmin Avg", "N/A")
            with c3:
                st.metric("Max RH Avg", "N/A")
                st.metric("Min RH Avg", "N/A")

            # Empty sections
            st.markdown("---")
            st.header("📅 Daily Weather Data")
            st.info("Daily weather data display is currently disabled.")
            
            st.markdown("---")
            st.header("📝 Comment on Sowing")
            st.info("Sowing comments display is currently disabled.")
            
            st.markdown("---")
            st.header("🌱 Growth Stage Advisory")
            st.info("Growth stage advisory display is currently disabled.")
        
        # TAB 2: DATA CHARTS - No data displayed
        with tab2:
            st.header("📊 Data Charts - Monthly Analysis")
            st.info("Data charts display is currently disabled.")
            
            # Empty charts
            st.subheader("🌤️ Weather Parameters - Monthly Column Charts")
            weather_chart = create_weather_parameters_charts(None)
            st.plotly_chart(weather_chart, use_container_width=True)
            
            st.subheader("📈 NDVI & NDWI Indices - Monthly Line Chart")
            indices_chart = create_indices_line_chart(None)
            st.plotly_chart(indices_chart, use_container_width=True)
            
            st.subheader("🌧️ MAI & Rainfall Deviation - Monthly Column Chart")
            mai_chart = create_mai_rainfall_chart(None)
            st.plotly_chart(mai_chart, use_container_width=True)
        
        # TAB 3: COMBINED INDICATOR - No data displayed
        with tab3:
            st.header("🔍 Combined Indicator - Data Matrix")
            st.info("Combined indicator display is currently disabled.")
            
            # Empty indicator table
            st.subheader("Monthly Indicator Status")
            st.info("Indicator data display is currently disabled.")
            
            # Empty summary
            st.subheader("Indicator Summary")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Good Indicators", "N/A")
            with col2:
                st.metric("Moderate Indicators", "N/A")
            with col3:
                st.metric("Poor Indicators", "N/A")
        
        # TAB 4: DATA DOWNLOAD - No data displayed
        with tab4:
            st.header("💾 Data Download")
            st.info("Data download functionality is currently disabled.")
            
            # Empty download sections
            st.subheader("Available Datasets")
            st.info("No datasets available for download.")
            
            st.subheader("Data Previews")
            st.info("No data previews available.")

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
