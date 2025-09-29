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
    # FIXED: Use raw GitHub URLs
    weather_url = "https://github.com/ASHISHSE/App_test/raw/main/weather.xlsb"
    rules_url = "https://github.com/ASHISHSE/App_test/raw/main/rules - Copy_F.xlsx"
    sowing_url = "https://github.com/ASHISHSE/App_test/raw/main/sowing_calendar1.xlsx"

    try:
        wres = requests.get(weather_url, timeout=10)
        rres = requests.get(rules_url, timeout=10)
        sres = requests.get(sowing_url, timeout=10)

        # Check if requests were successful
        if wres.status_code != 200:
            st.error(f"Failed to download weather data: HTTP {wres.status_code}")
            return None, None, None, [], [], [], []
        
        if rres.status_code != 200:
            st.error(f"Failed to download rules data: HTTP {rres.status_code}")
            return None, None, None, [], [], [], []
            
        if sres.status_code != 200:
            st.error(f"Failed to download sowing data: HTTP {sres.status_code}")
            return None, None, None, [], [], [], []

        # Use pyxlsb engine for .xlsb file
        try:
            weather_df = pd.read_excel(BytesIO(wres.content), engine='pyxlsb')
        except Exception as e:
            st.error(f"Error reading weather.xlsb with pyxlsb: {str(e)}")
            return None, None, None, [], [], [], []

        rules_df = pd.read_excel(BytesIO(rres.content))
        sowing_df = pd.read_excel(BytesIO(sres.content))

        # Flexible date column detection
        date_col = None
        for candidate in ["Date(DD-MM-YYYY)", "DD-MM-YYYY", "Date"]:
            if candidate in weather_df.columns:
                date_col = candidate
                break
        if date_col is None:
            # Use first column as fallback
            date_col = weather_df.columns[0]
            st.warning(f"Using '{date_col}' as date column")

        weather_df["Date_dt"] = pd.to_datetime(weather_df[date_col], format="%d-%m-%Y", errors="coerce")
        weather_df = weather_df.dropna(subset=["Date_dt"]).copy()

        for col in ["Rainfall", "Tmax", "Tmin", "max_Rh", "min_Rh"]:
            if col in weather_df.columns:
                weather_df[col] = pd.to_numeric(weather_df[col], errors="coerce")

        # Data cleaning
        for c in ["District", "Taluka", "Circle", "Crop"]:
            if c in sowing_df.columns:
                sowing_df[c] = sowing_df[c].astype(str).str.strip()
            if c in weather_df.columns:
                weather_df[c] = weather_df[c].astype(str).str.strip()
                
        if "Crop" in rules_df.columns:
            rules_df["Crop"] = rules_df["Crop"].astype(str).str.strip()

        # Get unique values from weather data for dropdowns
        districts = sorted(weather_df["District"].dropna().unique().tolist()) if "District" in weather_df.columns else []
        talukas = sorted(weather_df["Taluka"].dropna().unique().tolist()) if "Taluka" in weather_df.columns else []
        circles = sorted(weather_df["Circle"].dropna().unique().tolist()) if "Circle" in weather_df.columns else []
        crops = sorted(rules_df["Crop"].dropna().unique().tolist()) if "Crop" in rules_df.columns else []

        return weather_df, rules_df, sowing_df, districts, talukas, circles, crops

    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return None, None, None, [], [], [], []

# Load data before UI
weather_df, rules_df, sowing_df, districts, talukas, circles, crops = load_data()

if weather_df is None:
    st.stop()

# ---------------------------
# LOAD CIRCLEWISE DATA MATRIX - UPDATED
# ---------------------------
@st.cache_data
def load_circlewise_data():
    # UPDATED: New file name
    url = "https://github.com/ASHISHSE/App_test/raw/main/Circlewise_Data_Matrix_Indicator_2024_F_upload.xlsx"
    try:
        df = pd.read_excel(url)
        
        # Clean column names and data
        df.columns = [str(col).strip() for col in df.columns]
        
        # Clean string columns
        for col in ["District", "Taluka", "Circle", "Month"]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
                
        # Clean numeric columns
        numeric_cols = ["NDVI", "NDWI", "RAINFALL_DEV", "MAI"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
        # Clean categorical columns
        cat_cols = ["NDVI_CAT", "NDWI_CAT", "MAI_CAT", 
                   "Indicator-1 NDVI/NDWI", "Indicator-2 RAINFALL/MAI", 
                   "Indicator-3 NDVI_NDWI/RAINFALL_MAI"]
        for col in cat_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
        
        return df
        
    except Exception as e:
        st.error(f"Error loading circlewise data: {str(e)}")
        return pd.DataFrame()

circlewise_df = load_circlewise_data()

# -----------------------------
# IMPROVED FUNCTION FOR CIRCLEWISE DATA FILTERING
# -----------------------------
def get_circlewise_data(district, taluka, circle, sowing_date, current_date):
    df = circlewise_df.copy()
    
    if df.empty:
        return pd.DataFrame()

    # Filter by District, Taluka, Circle
    df = df[(df["District"] == district)]
    
    if taluka and "Taluka" in df.columns:
        df = df[df["Taluka"] == taluka]
    
    if circle and "Circle" in df.columns:
        df = df[df["Circle"] == circle]

    if df.empty:
        return pd.DataFrame()

    # Generate list of months and years between sowing_date and current_date
    months_years = []
    current = sowing_date.replace(day=1)
    end = current_date.replace(day=1)
    
    while current <= end:
        months_years.append((current.strftime("%B"), current.year))
        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    # Remove duplicates while preserving order
    months_years = list(dict.fromkeys(months_years))

    # Filter data for the specific months and years
    filtered_data = []
    for month, year in months_years:
        month_data = df[(df["Month"].str.strip() == month.strip()) & (df["Year"] == year)]
        if not month_data.empty:
            filtered_data.append(month_data)
    
    if filtered_data:
        result_df = pd.concat(filtered_data, ignore_index=True)
        
        # Select relevant columns based on your data format
        selected_cols = []
        possible_cols = [
            "District", "Taluka", "Circle", "Year", "Month",
            "NDVI", "NDVI_CAT", "NDWI", "NDWI_CAT",
            "Indicator-1 NDVI/NDWI", "RAINFALL_DEV", "MAI", "MAI_CAT",
            "Indicator-2 RAINFALL/MAI", "Indicator-3 NDVI_NDWI/RAINFALL_MAI"
        ]
        
        for col in possible_cols:
            if col in result_df.columns:
                selected_cols.append(col)
        
        return result_df[selected_cols]
    
    return pd.DataFrame()

# -----------------------------
# IMPROVED FUNCTION FOR MONTHLY ANALYSIS
# -----------------------------
def create_monthly_analysis(matrix_data):
    """Create detailed monthly analysis with index values and categories"""
    if matrix_data.empty:
        return None
    
    monthly_data = []
    
    # Get unique months and years
    months_years = matrix_data[["Month", "Year"]].drop_duplicates().values
    months_years = sorted(months_years, key=lambda x: datetime.strptime(f"{x[0]} {x[1]}", "%B %Y"))
    
    for month, year in months_years:
        month_data = {
            'Month': month,
            'Year': year,
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
        
        # Filter data for the specific month and year
        month_df = matrix_data[(matrix_data["Month"] == month) & (matrix_data["Year"] == year)]
        if not month_df.empty:
            row = month_df.iloc[0]
            
            # Extract values with proper error handling
            month_data['NDVI_Value'] = row.get("NDVI")
            month_data['NDVI_Category'] = row.get("NDVI_CAT")
            month_data['NDWI_Value'] = row.get("NDWI")
            month_data['NDWI_Category'] = row.get("NDWI_CAT")
            month_data['Rainfall_Dev_Value'] = row.get("RAINFALL_DEV")
            month_data['Rainfall_Dev_Category'] = row.get("RAINFALL_DEV")  # This might need adjustment based on your data
            month_data['MAI_Value'] = row.get("MAI")
            month_data['MAI_Category'] = row.get("MAI_CAT")
            month_data['Indicator_1'] = row.get("Indicator-1 NDVI/NDWI")
            month_data['Indicator_2'] = row.get("Indicator-2 RAINFALL/MAI")
            month_data['Indicator_3'] = row.get("Indicator-3 NDVI_NDWI/RAINFALL_MAI")
        
        monthly_data.append(month_data)
    
    return pd.DataFrame(monthly_data)

# -----------------------------
# UPDATED UI WITH FIXED DROPDOWNS
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
    
    # FIXED: Taluka dropdown - filter based on selected district
    if district:
        taluka_options = [""] + sorted(weather_df[weather_df["District"] == district]["Taluka"].dropna().unique().tolist())
    else:
        taluka_options = [""]
    taluka = st.selectbox("Taluka", taluka_options)
    
    # FIXED: Circle dropdown - filter based on selected taluka
    if taluka:
        circle_options = [""] + sorted(weather_df[(weather_df["District"] == district) & (weather_df["Taluka"] == taluka)]["Circle"].dropna().unique().tolist())
    else:
        circle_options = [""]
    circle = st.selectbox("Circle", circle_options)

with col2:
    crop = st.selectbox("Crop Name *", [""] + crops)
    sowing_date = st.date_input("Sowing Date (dd/mm/yyyy)", value=date.today() - timedelta(days=30), format="DD/MM/YYYY")
    current_date = st.date_input("Current Date (dd/mm/yyyy)", value=date.today(), format="DD/MM/YYYY")

generate = st.button("🌱 Generate Advisory")

# -----------------------------
# REST OF THE CODE REMAINS THE SAME (with minor improvements)
# -----------------------------

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

# [Keep all the existing chart functions and helper functions as they are]
# ... (rest of your existing code for chart functions, weather metrics, etc.)

if generate:
    if not district or not crop:
        st.error("Please select all required fields.")
    else:
        sowing_date_str = sowing_date.strftime("%d/%m/%Y")
        current_date_str = current_date.strftime("%d/%m/%Y")
        level = "Circle" if circle else "Taluka" if taluka else "District"
        level_name = circle if circle else taluka if taluka else district

        # Calculate metrics and get data
        metrics = calculate_weather_metrics(weather_df, level, level_name, sowing_date_str, current_date_str)
        das_data = metrics["das_data"]
        matrix_data = get_circlewise_data(district, taluka, circle, sowing_date, current_date)
        monthly_df = create_monthly_analysis(matrix_data) if not matrix_data.empty else None
        
        # Create tabs
        tab1, tab2, tab3, tab4 = st.tabs(["🌤️ Weather Metrics", "📊 Data Charts", "🔍 Combined Indicator", "💾 Data Download"])
        
        # TAB 1: WEATHER METRICS (same as before)
        with tab1:
            # ... (keep your existing tab1 content)
            pass
            
        # TAB 2: DATA CHARTS - IMPROVED
        with tab2:
            st.header("📊 Data Charts - Monthly Analysis")
            
            if not matrix_data.empty:
                # Debug information
                with st.expander("🔍 Debug: View Data Structure"):
                    st.write("Circlewise Data Matrix Sample:")
                    st.dataframe(matrix_data.head(), use_container_width=True)
                    
                    st.write("Available Columns:")
                    st.write(list(matrix_data.columns))
            
            if monthly_df is not None and not monthly_df.empty:
                # Display the monthly data
                st.subheader("📋 Monthly Data Summary")
                st.dataframe(monthly_df, use_container_width=True)
                
                # Create charts based on available data
                if any(pd.notna(monthly_df['NDVI_Value'])) or any(pd.notna(monthly_df['NDWI_Value'])):
                    st.subheader("📈 Vegetation & Water Indices")
                    fig_indices = go.Figure()
                    
                    if any(pd.notna(monthly_df['NDVI_Value'])):
                        fig_indices.add_trace(go.Scatter(
                            x=monthly_df['Month'] + " " + monthly_df['Year'].astype(str),
                            y=monthly_df['NDVI_Value'],
                            mode='lines+markers',
                            name='NDVI',
                            line=dict(color='green', width=3),
                            marker=dict(size=8)
                        ))
                    
                    if any(pd.notna(monthly_df['NDWI_Value'])):
                        fig_indices.add_trace(go.Scatter(
                            x=monthly_df['Month'] + " " + monthly_df['Year'].astype(str),
                            y=monthly_df['NDWI_Value'],
                            mode='lines+markers',
                            name='NDWI',
                            line=dict(color='blue', width=3),
                            marker=dict(size=8)
                        ))
                    
                    fig_indices.update_layout(
                        title="NDVI & NDWI Trends",
                        xaxis_title="Month",
                        yaxis_title="Index Value",
                        height=400,
                        template="plotly_white"
                    )
                    st.plotly_chart(fig_indices, use_container_width=True)
                
                # MAI and Rainfall charts
                if any(pd.notna(monthly_df['MAI_Value'])) or any(pd.notna(monthly_df['Rainfall_Dev_Value'])):
                    st.subheader("🌧️ MAI & Rainfall Analysis")
                    
                    fig_mai_rain = go.Figure()
                    
                    if any(pd.notna(monthly_df['MAI_Value'])):
                        fig_mai_rain.add_trace(go.Bar(
                            name='MAI',
                            x=monthly_df['Month'] + " " + monthly_df['Year'].astype(str),
                            y=monthly_df['MAI_Value'],
                            marker_color='orange'
                        ))
                    
                    if any(pd.notna(monthly_df['Rainfall_Dev_Value'])):
                        fig_mai_rain.add_trace(go.Bar(
                            name='Rainfall Deviation (%)',
                            x=monthly_df['Month'] + " " + monthly_df['Year'].astype(str),
                            y=monthly_df['Rainfall_Dev_Value'],
                            marker_color='lightblue'
                        ))
                    
                    fig_mai_rain.update_layout(
                        title="MAI & Rainfall Deviation",
                        xaxis_title="Month",
                        yaxis_title="Value",
                        barmode='group',
                        height=400,
                        template="plotly_white"
                    )
                    st.plotly_chart(fig_mai_rain, use_container_width=True)
            else:
                st.info("No monthly analysis data available for the selected parameters.")
        
        # TAB 3: COMBINED INDICATOR - IMPROVED
        with tab3:
            st.header("🔍 Combined Indicator - Data Matrix")
            
            if not matrix_data.empty:
                # Display the complete data matrix
                st.subheader("Complete Data Matrix")
                st.dataframe(matrix_data, use_container_width=True)
                
                # Create a summary table of indicators
                if all(col in matrix_data.columns for col in ["Indicator-1 NDVI/NDWI", "Indicator-2 RAINFALL/MAI", "Indicator-3 NDVI_NDWI/RAINFALL_MAI"]):
                    st.subheader("📊 Monthly Indicator Summary")
                    
                    summary_data = []
                    for _, row in matrix_data.iterrows():
                        summary_data.append({
                            'Month-Year': f"{row['Month']} {row['Year']}",
                            'NDVI/NDWI': row['Indicator-1 NDVI/NDWI'],
                            'Rainfall/MAI': row['Indicator-2 RAINFALL/MAI'],
                            'Composite': row['Indicator-3 NDVI_NDWI/RAINFALL_MAI']
                        })
                    
                    if summary_data:
                        summary_df = pd.DataFrame(summary_data)
                        
                        # Apply styling
                        def color_indicator(val):
                            if pd.isna(val):
                                return ''
                            val_lower = str(val).lower()
                            if 'good' in val_lower:
                                return 'background-color: #d4edda; color: #155724;'
                            elif 'moderate' in val_lower:
                                return 'background-color: #fff3cd; color: #856404;'
                            elif 'poor' in val_lower:
                                return 'background-color: #f8d7da; color: #721c24;'
                            return ''
                        
                        styled_summary = summary_df.style.applymap(color_indicator)
                        st.dataframe(styled_summary, use_container_width=True)
            else:
                st.info("No data matrix available for the selected parameters.")
        
        # TAB 4: DATA DOWNLOAD (same as before)
        with tab4:
            # ... (keep your existing tab4 content)
            pass

# [Keep the footer and remaining functions the same]

