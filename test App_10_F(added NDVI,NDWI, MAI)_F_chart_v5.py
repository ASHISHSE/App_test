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
from PIL import Image


# --- Page Config ---
st.set_page_config(
    page_title="👨‍🌾 Smart Crop Advisory Dashboard",
    page_icon="👨‍🌾",
    layout="wide"
)

# --- Modern Tech Dashboard Styling ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
            background-color: #0f1117;
            color: #e5e5e5;
        }

        .main-header {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            margin-top: 20px;
            margin-bottom: 10px;
            text-align: center;
        }

        .logo-icon {
            width: 95px;
            height: auto;
            margin-bottom: 12px;
            border-radius: 50%;
            box-shadow: 0 0 12px rgba(116,198,157,0.35);
        }

        .main-title {
            font-size: 2.6rem;
            font-weight: 700;
            color: #74c69d;
            letter-spacing: 0.5px;
            text-shadow: 0 0 8px rgba(116,198,157,0.25);
        }

        .subtitle {
            font-size: 1.1rem;
            color: #95d5b2;
            font-weight: 500;
            margin-top: 4px;
            letter-spacing: 0.3px;
        }

        div.stButton > button:first-child {
            background: linear-gradient(90deg, #2d6a4f, #52b788);
            color: white;
            border-radius: 8px;
            font-weight: 600;
            padding: 0.5rem 1.2rem;
            border: none;
            box-shadow: 0 0 10px rgba(45,106,79,0.3);
            transition: all 0.25s ease;
        }

        div.stButton > button:hover {
            background: linear-gradient(90deg, #52b788, #2d6a4f);
            transform: scale(1.02);
            box-shadow: 0 0 15px rgba(82,183,136,0.4);
        }

        .footer {
            text-align: center;
            font-size: 0.85rem;
            color: #adb5bd;
            margin-top: 40px;
        }
    </style>
""", unsafe_allow_html=True)

# --- HEADER (with uploaded farmer-tech icon) ---
st.markdown('<div class="main-header">', unsafe_allow_html=True)
st.image(
    "https://raw.githubusercontent.com/ASHISHSE/App_test/main/icon.png",
    width=95
)
st.markdown("""
    <div class="main-title">Smart Crop Advisory Dashboard</div>
    <div class="subtitle">Empowering Farmers with Data-Driven Insights</div>
</div>
""", unsafe_allow_html=True)

# --- Example Footer ---
st.markdown("""
<div class="footer">
    👨‍🌾 Developed by <b>Ashish Selokar</b> | Version 1.0 | Powered by AgricosE<br>
    <small>Last Updated: Oct 2025</small>
</div>
""", unsafe_allow_html=True)




# -----------------------------
# LOAD DATA (WEATHER, RULES, SOWING) - UPDATED URLS
# -----------------------------
@st.cache_data
def load_data():
    # Updated URLs as per request
    weather_url = "https://github.com/ASHISHSE/App_test/raw/main/weather_f_upload.xlsx"
    rules_url = "https://github.com/ASHISHSE/App_test/raw/main/rules - Copy_F.xlsx"
    sowing_url = "https://github.com/ASHISHSE/App_test/raw/main/sowing_calendar1_f_upload.xlsx"

    wres = requests.get(weather_url, timeout=30)
    rres = requests.get(rules_url, timeout=10)
    sres = requests.get(sowing_url, timeout=10)

    # Load weather data from .xlsb file
    try:
        # For .xlsb files, we need to use pyxlsb
        import pyxlsb
        weather_df = pd.read_excel(BytesIO(wres.content), engine='pyxlsb')
    except ImportError:
        #st.error("pyxlsb library required for .xlsb files. Install with: pip install pyxlsb")
        # Fallback to openpyxl if pyxlsb not available
        weather_df = pd.read_excel(BytesIO(wres.content), engine='openpyxl')
    except Exception as e:
        #st.error(f"Error loading weather.xlsb: {e}")
        # Try alternative method
        weather_df = pd.read_excel(BytesIO(wres.content))

    rules_df = pd.read_excel(BytesIO(rres.content))
    sowing_df = pd.read_excel(BytesIO(sres.content))

    # Flexible date column detection for weather data
    date_col = None
    for candidate in ["Date(DD-MM-YYYY)", "DD-MM-YYYY", "Date"]:
        if candidate in weather_df.columns:
            date_col = candidate
            break
    if date_col is None:
        raise ValueError("weather.xlsb must have a column named 'Date(DD-MM-YYYY)' or similar")

    weather_df["Date_dt"] = pd.to_datetime(weather_df[date_col], format="%d-%m-%Y", errors="coerce")
    weather_df = weather_df.dropna(subset=["Date_dt"]).copy()

    # Convert numeric columns
    for col in ["Rainfall", "Tmax", "Tmin", "max_Rh", "min_Rh"]:
        if col in weather_df.columns:
            weather_df[col] = pd.to_numeric(weather_df[col], errors="coerce")

    # Clean string columns
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
# LOAD CIRCLEWISE DATA MATRIX - UPDATED URL
# -----------------------------
@st.cache_data
def load_circlewise_data():
    url = "https://github.com/ASHISHSE/App_test/raw/main/Circlewise_Data_Matrix_Indicator_2024_f_upload.xlsx"
    return pd.read_excel(url)

circlewise_df = load_circlewise_data()

# -----------------------------
# MODIFIED HELPER FUNCTION FOR CIRCLEWISE DATA - HANDLE ALL LEVELS
# -----------------------------
def get_circlewise_data(district, taluka, circle, sowing_date, current_date, include_all_sublevels=False):
    df = circlewise_df.copy()

    # Filter based on selected level
    if district:
        df = df[df["District"] == district]
    
    # If include_all_sublevels is True, we don't filter by taluka/circle to get all sub-level data
    if not include_all_sublevels:
        if taluka and taluka != "":
            df = df[df["Taluka"] == taluka]
        
        if circle and circle != "" and "Circle" in df.columns:
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

    # Filter data for the selected months and year 2024
    filtered_df = df[(df["Year"] == 2024) & (df["Month"].isin(months))]
    
    return filtered_df

# -----------------------------
# NEW FUNCTION TO GET ALL SUB-LEVELS DATA FOR COMPARISON CHARTS
# -----------------------------
def get_comparison_data(district, taluka, circle, sowing_date, current_date):
    """Get data for all sub-levels within the selected level for comparison charts"""
    df = circlewise_df.copy()
    
    # Filter by district (always required)
    if district:
        df = df[df["District"] == district]
    else:
        return pd.DataFrame()
    
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

    months = list(dict.fromkeys(months))
    
    # Filter data for the selected months and year 2024
    filtered_df = df[(df["Year"] == 2024) & (df["Month"].isin(months))]
    
    return filtered_df

# -----------------------------
# MODIFIED FUNCTION TO CREATE COMPARISON LINE CHARTS WITH AUTO SPACING
# -----------------------------
def create_comparison_line_charts_modified(comparison_data, selected_level, selected_name, district, taluka, circle):
    """Create line charts based on the selection level conditions with automatic spacing"""
    if comparison_data.empty:
        return None, None
    
    # Convert month names to datetime for proper sorting
    month_order = ['January', 'February', 'March', 'April', 'May', 'June', 
                   'July', 'August', 'September', 'October', 'November', 'December']
    comparison_data['Month_Num'] = comparison_data['Month'].apply(
        lambda x: month_order.index(x) + 1 if x in month_order else 13
    )
    comparison_data = comparison_data.sort_values('Month_Num')
    
    # Calculate dynamic height and legend position based on number of items
    def calculate_chart_dimensions(num_items):
        """Calculate dynamic chart height and legend position based on number of data series"""
        base_height = 500
        extra_height_per_item = 30
        mobile_height = 600  # Fixed height for mobile
        
        # Check if mobile view (approximate based on typical mobile screen width)
        is_mobile = st.get_option('browser.gatherUsageStats')  # This is a proxy, actual mobile detection is complex
        
        if is_mobile or num_items > 8:
            height = mobile_height
            legend_orientation = "v"  # Vertical for mobile or many items
            legend_y = -0.3
        else:
            height = base_height + (num_items * extra_height_per_item)
            legend_orientation = "h"  # Horizontal for desktop
            legend_y = -0.2
            
        return height, legend_orientation, legend_y
    
    # Condition I: If user select up to Taluka level only
    if selected_level == "Taluka" and selected_name and not circle:
        # Generate separately NDVI & NDWI line charts of all circles within the taluka
        ndvi_fig = go.Figure()
        ndwi_fig = go.Figure()
        
        # Show all Circles within the Taluka
        circles_in_taluka = comparison_data[comparison_data['Taluka'] == selected_name]['Circle'].unique()
        
        # Calculate dynamic dimensions
        height, legend_orientation, legend_y = calculate_chart_dimensions(len(circles_in_taluka))
        
        for circle_name in circles_in_taluka:
            circle_data = comparison_data[comparison_data['Circle'] == circle_name]
            
            # NDVI Chart - all circles
            if any(pd.notna(circle_data['NDVI'])):
                ndvi_fig.add_trace(go.Scatter(
                    x=circle_data['Month'],
                    y=circle_data['NDVI'],
                    mode='lines+markers',
                    name=f'Circle: {circle_name}',
                    line=dict(width=3),
                    marker=dict(size=8)
                ))
            
            # NDWI Chart - all circles
            if any(pd.notna(circle_data['NDWI'])):
                ndwi_fig.add_trace(go.Scatter(
                    x=circle_data['Month'],
                    y=circle_data['NDWI'],
                    mode='lines+markers',
                    name=f'Circle: {circle_name}',
                    line=dict(width=3),
                    marker=dict(size=8)
                ))
        
        # Auto-adjust layout for NDVI
        ndvi_fig.update_layout(
            title=f"NDVI Comparison - All Circles in {selected_name} Taluka",
            xaxis_title="Month",
            yaxis_title="NDVI Value",
            height=height,
            template="plotly_white",
            legend=dict(
                orientation=legend_orientation,
                yanchor="top",
                y=legend_y,
                xanchor="center",
                x=0.5,
                font=dict(size=10)
            ),
            margin=dict(l=50, r=50, t=80, b=150)  # Extra bottom margin for legend
        )
        
        # Auto-adjust layout for NDWI
        ndwi_fig.update_layout(
            title=f"NDWI Comparison - All Circles in {selected_name} Taluka",
            xaxis_title="Month",
            yaxis_title="NDWI Value",
            height=height,
            template="plotly_white",
            legend=dict(
                orientation=legend_orientation,
                yanchor="top",
                y=legend_y,
                xanchor="center",
                x=0.5,
                font=dict(size=10)
            ),
            margin=dict(l=50, r=50, t=80, b=150)  # Extra bottom margin for legend
        )
        
        return ndvi_fig, ndwi_fig
    
    # Condition II: If user select up to District level only
    elif selected_level == "District" and selected_name and not taluka:
        # Generate separate charts for Talukas (averaged) and All Circles
        
        # 1. Charts for Talukas (Averaging circles, excluding 0 values)
        ndvi_taluka_fig = go.Figure()
        ndwi_taluka_fig = go.Figure()
        
        # 2. Charts for All Circles
        ndvi_circle_fig = go.Figure()
        ndwi_circle_fig = go.Figure()
        
        talukas_in_district = comparison_data['Taluka'].unique()
        
        # Calculate dimensions for taluka charts (usually fewer items)
        taluka_height, taluka_legend_orientation, taluka_legend_y = calculate_chart_dimensions(len(talukas_in_district))
        
        # Calculate total circles for circle charts (usually more items)
        total_circles = 0
        for taluka_name in talukas_in_district:
            circles_in_taluka = comparison_data[comparison_data['Taluka'] == taluka_name]['Circle'].unique()
            total_circles += len(circles_in_taluka)
        
        circle_height, circle_legend_orientation, circle_legend_y = calculate_chart_dimensions(total_circles)
        
        for taluka_name in talukas_in_district:
            taluka_data = comparison_data[comparison_data['Taluka'] == taluka_name]
            
            # Calculate average for taluka (excluding 0 values)
            monthly_avg_ndvi = []
            monthly_avg_ndwi = []
            
            for month in comparison_data['Month'].unique():
                month_data = taluka_data[taluka_data['Month'] == month]
                # Exclude 0 values for averaging
                ndvi_values = month_data['NDVI'].replace(0, np.nan).dropna()
                ndwi_values = month_data['NDWI'].replace(0, np.nan).dropna()
                
                avg_ndvi = ndvi_values.mean() if not ndvi_values.empty else np.nan
                avg_ndwi = ndwi_values.mean() if not ndwi_values.empty else np.nan
                
                monthly_avg_ndvi.append(avg_ndvi)
                monthly_avg_ndwi.append(avg_ndwi)
            
            # Add taluka average to NDVI chart
            if any(pd.notna(monthly_avg_ndvi)):
                ndvi_taluka_fig.add_trace(go.Scatter(
                    x=comparison_data['Month'].unique(),
                    y=monthly_avg_ndvi,
                    mode='lines+markers',
                    name=f'Taluka: {taluka_name}',
                    line=dict(width=3),
                    marker=dict(size=8)
                ))
            
            # Add taluka average to NDWI chart
            if any(pd.notna(monthly_avg_ndwi)):
                ndwi_taluka_fig.add_trace(go.Scatter(
                    x=comparison_data['Month'].unique(),
                    y=monthly_avg_ndwi,
                    mode='lines+markers',
                    name=f'Taluka: {taluka_name}',
                    line=dict(width=3),
                    marker=dict(size=8)
                ))
            
            # Add individual circles for circle-level charts
            circles_in_taluka = taluka_data['Circle'].unique()
            for circle_name in circles_in_taluka:
                circle_data = taluka_data[taluka_data['Circle'] == circle_name]
                
                # NDVI Chart - individual circles
                if any(pd.notna(circle_data['NDVI'])):
                    ndvi_circle_fig.add_trace(go.Scatter(
                        x=circle_data['Month'],
                        y=circle_data['NDVI'],
                        mode='lines+markers',
                        name=f'{taluka_name} - {circle_name}',
                        line=dict(width=2),
                        marker=dict(size=6)
                    ))
                
                # NDWI Chart - individual circles
                if any(pd.notna(circle_data['NDWI'])):
                    ndwi_circle_fig.add_trace(go.Scatter(
                        x=circle_data['Month'],
                        y=circle_data['NDWI'],
                        mode='lines+markers',
                        name=f'{taluka_name} - {circle_name}',
                        line=dict(width=2),
                        marker=dict(size=6)
                    ))
        
        # Update taluka chart layouts with auto spacing
        ndvi_taluka_fig.update_layout(
            title=f"NDVI - Taluka Averages (Excluding 0 values) in {selected_name} District",
            xaxis_title="Month",
            yaxis_title="NDVI Value",
            height=taluka_height,
            template="plotly_white",
            legend=dict(
                orientation=taluka_legend_orientation,
                yanchor="top",
                y=taluka_legend_y,
                xanchor="center",
                x=0.5,
                font=dict(size=10)
            ),
            margin=dict(l=50, r=50, t=80, b=150)
        )
        
        ndwi_taluka_fig.update_layout(
            title=f"NDWI - Taluka Averages (Excluding 0 values) in {selected_name} District",
            xaxis_title="Month",
            yaxis_title="NDWI Value",
            height=taluka_height,
            template="plotly_white",
            legend=dict(
                orientation=taluka_legend_orientation,
                yanchor="top",
                y=taluka_legend_y,
                xanchor="center",
                x=0.5,
                font=dict(size=10)
            ),
            margin=dict(l=50, r=50, t=80, b=150)
        )
        
        # Update circle chart layouts with auto spacing
        ndvi_circle_fig.update_layout(
            title=f"NDVI - All Circles in {selected_name} District",
            xaxis_title="Month",
            yaxis_title="NDVI Value",
            height=circle_height,
            template="plotly_white",
            legend=dict(
                orientation=circle_legend_orientation,
                yanchor="top",
                y=circle_legend_y,
                xanchor="center",
                x=0.5,
                font=dict(size=9)  # Smaller font for many items
            ),
            margin=dict(l=50, r=50, t=80, b=200)  # Even more bottom margin for many items
        )
        
        ndwi_circle_fig.update_layout(
            title=f"NDWI - All Circles in {selected_name} District",
            xaxis_title="Month",
            yaxis_title="NDWI Value",
            height=circle_height,
            template="plotly_white",
            legend=dict(
                orientation=circle_legend_orientation,
                yanchor="top",
                y=circle_legend_y,
                xanchor="center",
                x=0.5,
                font=dict(size=9)  # Smaller font for many items
            ),
            margin=dict(l=50, r=50, t=80, b=200)  # Even more bottom margin for many items
        )
        
        # Return all four figures
        return (ndvi_taluka_fig, ndwi_taluka_fig, ndvi_circle_fig, ndwi_circle_fig)
    
    else:
        # Default behavior for other cases
        return create_comparison_line_charts(comparison_data, selected_level, selected_name)

# -----------------------------
# ORIGINAL FUNCTION TO CREATE COMPARISON LINE CHARTS (with auto spacing)
# -----------------------------
def create_comparison_line_charts(comparison_data, selected_level, selected_name):
    """Create line charts comparing all sub-levels within the selected level with auto spacing"""
    if comparison_data.empty:
        return None, None
    
    # Convert month names to datetime for proper sorting
    month_order = ['January', 'February', 'March', 'April', 'May', 'June', 
                   'July', 'August', 'September', 'October', 'November', 'December']
    comparison_data['Month_Num'] = comparison_data['Month'].apply(
        lambda x: month_order.index(x) + 1 if x in month_order else 13
    )
    comparison_data = comparison_data.sort_values('Month_Num')
    
    # Calculate dynamic dimensions
    def calculate_chart_dimensions(num_items):
        base_height = 500
        extra_height_per_item = 30
        mobile_height = 600
        
        # Simple mobile detection based on number of items (proxy for complexity)
        is_mobile = num_items > 6  # More items likely need mobile layout
        
        if is_mobile:
            height = mobile_height
            legend_orientation = "v"
            legend_y = -0.3
        else:
            height = base_height + (num_items * extra_height_per_item)
            legend_orientation = "h"
            legend_y = -0.2
            
        return height, legend_orientation, legend_y
    
    # Create NDVI comparison chart
    ndvi_fig = go.Figure()
    
    if selected_level == "District" and selected_name:
        # Show all Talukas within the District
        talukas_in_district = comparison_data['Taluka'].unique()
        height, legend_orientation, legend_y = calculate_chart_dimensions(len(talukas_in_district))
        
        for taluka in talukas_in_district:
            taluka_data = comparison_data[comparison_data['Taluka'] == taluka]
            if any(pd.notna(taluka_data['NDVI'])):
                ndvi_fig.add_trace(go.Scatter(
                    x=taluka_data['Month'],
                    y=taluka_data['NDVI'],
                    mode='lines+markers',
                    name=f'Taluka: {taluka}',
                    line=dict(width=3),
                    marker=dict(size=8)
                ))
        ndvi_fig.update_layout(
            title=f"NDVI Comparison - All Talukas in {selected_name} District",
            xaxis_title="Month",
            yaxis_title="NDVI Value",
            height=height,
            template="plotly_white",
            legend=dict(
                orientation=legend_orientation,
                yanchor="top",
                y=legend_y,
                xanchor="center",
                x=0.5,
                font=dict(size=10)
            ),
            margin=dict(l=50, r=50, t=80, b=150)
        )
    
    elif selected_level == "Taluka" and selected_name:
        # Show all Circles within the Taluka
        circles_in_taluka = comparison_data[comparison_data['Taluka'] == selected_name]['Circle'].unique()
        height, legend_orientation, legend_y = calculate_chart_dimensions(len(circles_in_taluka))
        
        for circle in circles_in_taluka:
            circle_data = comparison_data[comparison_data['Circle'] == circle]
            if any(pd.notna(circle_data['NDVI'])):
                ndvi_fig.add_trace(go.Scatter(
                    x=circle_data['Month'],
                    y=circle_data['NDVI'],
                    mode='lines+markers',
                    name=f'Circle: {circle}',
                    line=dict(width=3),
                    marker=dict(size=8)
                ))
        ndvi_fig.update_layout(
            title=f"NDVI Comparison - All Circles in {selected_name} Taluka",
            xaxis_title="Month",
            yaxis_title="NDVI Value",
            height=height,
            template="plotly_white",
            legend=dict(
                orientation=legend_orientation,
                yanchor="top",
                y=legend_y,
                xanchor="center",
                x=0.5,
                font=dict(size=10)
            ),
            margin=dict(l=50, r=50, t=80, b=150)
        )
    
    # Create NDWI comparison chart
    ndwi_fig = go.Figure()
    
    if selected_level == "District" and selected_name:
        # Show all Talukas within the District
        talukas_in_district = comparison_data['Taluka'].unique()
        height, legend_orientation, legend_y = calculate_chart_dimensions(len(talukas_in_district))
        
        for taluka in talukas_in_district:
            taluka_data = comparison_data[comparison_data['Taluka'] == taluka]
            if any(pd.notna(taluka_data['NDWI'])):
                ndwi_fig.add_trace(go.Scatter(
                    x=taluka_data['Month'],
                    y=taluka_data['NDWI'],
                    mode='lines+markers',
                    name=f'Taluka: {taluka}',
                    line=dict(width=3),
                    marker=dict(size=8)
                ))
        ndwi_fig.update_layout(
            title=f"NDWI Comparison - All Talukas in {selected_name} District",
            xaxis_title="Month",
            yaxis_title="NDWI Value",
            height=height,
            template="plotly_white",
            legend=dict(
                orientation=legend_orientation,
                yanchor="top",
                y=legend_y,
                xanchor="center",
                x=0.5,
                font=dict(size=10)
            ),
            margin=dict(l=50, r=50, t=80, b=150)
        )
    
    elif selected_level == "Taluka" and selected_name:
        # Show all Circles within the Taluka
        circles_in_taluka = comparison_data[comparison_data['Taluka'] == selected_name]['Circle'].unique()
        height, legend_orientation, legend_y = calculate_chart_dimensions(len(circles_in_taluka))
        
        for circle in circles_in_taluka:
            circle_data = comparison_data[comparison_data['Circle'] == circle]
            if any(pd.notna(circle_data['NDWI'])):
                ndwi_fig.add_trace(go.Scatter(
                    x=circle_data['Month'],
                    y=circle_data['NDWI'],
                    mode='lines+markers',
                    name=f'Circle: {circle}',
                    line=dict(width=3),
                    marker=dict(size=8)
                ))
        ndwi_fig.update_layout(
            title=f"NDWI Comparison - All Circles in {selected_name} Taluka",
            xaxis_title="Month",
            yaxis_title="NDWI Value",
            height=height,
            template="plotly_white",
            legend=dict(
                orientation=legend_orientation,
                yanchor="top",
                y=legend_y,
                xanchor="center",
                x=0.5,
                font=dict(size=10)
            ),
            margin=dict(l=50, r=50, t=80, b=150)
        )
    
    return ndvi_fig, ndwi_fig

# -----------------------------
# MODIFIED FUNCTION FOR MAI ANALYSIS - CLUSTER COLUMN CHART WITH AUTO SPACING
# -----------------------------
def create_mai_analysis_clustered(comparison_data, selected_level, selected_name, district, taluka, circle):
    """Create clustered column chart for MAI analysis with averages excluding 0 values and auto spacing"""
    if comparison_data.empty:
        return None
    
    # Convert month names to datetime for proper sorting
    month_order = ['January', 'February', 'March', 'April', 'May', 'June', 
                   'July', 'August', 'September', 'October', 'November', 'December']
    comparison_data['Month_Num'] = comparison_data['Month'].apply(
        lambda x: month_order.index(x) + 1 if x in month_order else 13
    )
    comparison_data = comparison_data.sort_values('Month_Num')
    
    # Calculate average MAI values excluding 0 values based on selection level
    months = comparison_data['Month'].unique()
    
    # Dynamic height calculation for mobile
    def get_dynamic_height():
        return 600  # Fixed height that works well for both desktop and mobile
    
    height = get_dynamic_height()
    
    if selected_level == "District" and selected_name and not taluka:
        # District level - average across all talukas/circles
        avg_mai_values = []
        for month in months:
            month_data = comparison_data[comparison_data['Month'] == month]
            # Exclude 0 values for averaging
            mai_values = month_data['MAI'].replace(0, np.nan).dropna()
            avg_mai = mai_values.mean() if not mai_values.empty else 0
            avg_mai_values.append(avg_mai)
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=months,
            y=avg_mai_values,
            name='Average MAI',
            marker_color='orange'
        ))
        
        fig.update_layout(
            title=f"MAI Analysis - District Level Average (Excluding 0 values) - {selected_name}",
            xaxis_title="Month",
            yaxis_title="MAI Value",
            height=height,
            template="plotly_white",
            showlegend=True,
            margin=dict(l=50, r=50, t=80, b=80)
        )
        
    elif selected_level == "Taluka" and selected_name and not circle:
        # Taluka level - average across all circles in the taluka
        taluka_data = comparison_data[comparison_data['Taluka'] == selected_name]
        avg_mai_values = []
        for month in months:
            month_data = taluka_data[taluka_data['Month'] == month]
            # Exclude 0 values for averaging
            mai_values = month_data['MAI'].replace(0, np.nan).dropna()
            avg_mai = mai_values.mean() if not mai_values.empty else 0
            avg_mai_values.append(avg_mai)
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=months,
            y=avg_mai_values,
            name='Average MAI',
            marker_color='orange'
        ))
        
        fig.update_layout(
            title=f"MAI Analysis - Taluka Level Average (Excluding 0 values) - {selected_name}",
            xaxis_title="Month",
            yaxis_title="MAI Value",
            height=height,
            template="plotly_white",
            showlegend=True,
            margin=dict(l=50, r=50, t=80, b=80)
        )
    
    else:
        # For circle level or other cases, show individual values
        if selected_level == "Circle" and selected_name:
            circle_data = comparison_data[comparison_data['Circle'] == selected_name]
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=circle_data['Month'],
                y=circle_data['MAI'],
                name='MAI',
                marker_color='orange'
            ))
            
            fig.update_layout(
                title=f"MAI Analysis - {selected_name}",
                xaxis_title="Month",
                yaxis_title="MAI Value",
                height=height,
                template="plotly_white",
                showlegend=True,
                margin=dict(l=50, r=50, t=80, b=80)
            )
        else:
            # Default case
            fig = go.Figure()
            if any(pd.notna(comparison_data['MAI'])):
                fig.add_trace(go.Bar(
                    x=comparison_data['Month'],
                    y=comparison_data['MAI'],
                    name='MAI',
                    marker_color='orange'
                ))
            
            fig.update_layout(
                title="MAI Analysis",
                xaxis_title="Month",
                yaxis_title="MAI Value",
                height=height,
                template="plotly_white",
                showlegend=True,
                margin=dict(l=50, r=50, t=80, b=80)
            )
    
    return fig

# -----------------------------
# IMPROVED FUNCTION FOR MONTHLY ANALYSIS WITH TAB-SPECIFIC DATA
# -----------------------------
def create_monthly_analysis(matrix_data, data_type="RS Data indices"):
    """Create detailed monthly analysis with index values and categories"""
    if matrix_data.empty:
        return None
    
    if data_type == "RS Data indices":
        # For NDVI, NDWI, MAI values from "RS Data indices" tab
        monthly_data = []
        
        for _, row in matrix_data.iterrows():
            month_data = {
                'District': row.get('District'),
                'Taluka': row.get('Taluka'),
                'Circle': row.get('Circle'),
                'Month': row['Month'],
                'NDVI_Value': row.get('NDVI'),
                'NDVI_Category': row.get('NDVI_CAT'),
                'NDWI_Value': row.get('NDWI'),
                'NDWI_Category': row.get('NDWI_CAT'),
                'MAI_Value': row.get('MAI'),
                'MAI_Category': row.get('MAI_CAT'),
                'Rainfall_Dev_Value': row.get('RAINFALL_DEV'),
                'Rainfall_Dev_Category': row.get('RAINFALL_DEV_CAT') 
            }
            monthly_data.append(month_data)
        
        return pd.DataFrame(monthly_data)
    
    elif data_type == "Data Matrix":
        # For Indicators values from "Data Matrix" tab
        monthly_data = []
        
        for _, row in matrix_data.iterrows():
            month_data = {
                'District': row.get('District'),
                'Taluka': row.get('Taluka'),
                'Circle': row.get('Circle'),
                'Month': row['Month'],
                'Indicator_1': row.get('Indicator-1 NDVI/NDWI'),
                'Indicator_2': row.get('Indicator-2 RAINFALL/MAI'),
                'Indicator_3': row.get('Indicator-3 NDVI_NDWI/RAINFALL_MAI'),
            }
            monthly_data.append(month_data)
        
        return pd.DataFrame(monthly_data)
    
    return None

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
# MODIFIED DATA MATRIX PROCESSING FOR COMBINED INDICATOR TAB - EXCLUDE INDICATOR-3
# -----------------------------
def get_combined_indicators(matrix_data):
    """Extract combined indicators (Good, Moderate, Poor) for all months - EXCLUDING Indicator-3"""
    if matrix_data.empty:
        return pd.DataFrame()
    
    indicators_data = []
    
    for _, row in matrix_data.iterrows():
        month_data = {
            'District': row.get('District'),
            'Taluka': row.get('Taluka'),
            'Circle': row.get('Circle'),
            'Month': row['Month'],
            'Indicator_1': row.get('Indicator-1 NDVI/NDWI'),
            'Indicator_2': row.get('Indicator-2 RAINFALL/MAI'),
            # 'Indicator_3': row.get('Indicator-3 NDVI_NDWI/RAINFALL_MAI')  # EXCLUDED AS PER REQUIREMENT
        }
        indicators_data.append(month_data)
    
    return pd.DataFrame(indicators_data)

# -----------------------------
# CHART FUNCTIONS FOR DATA CHARTS TAB WITH AUTO SPACING
# -----------------------------
def create_weather_parameters_charts(monthly_df):
    """Create column charts for weather parameters with auto spacing"""
    if monthly_df is None or monthly_df.empty:
        return None
    
    # Convert month names to datetime for proper sorting
    monthly_df['Month_Num'] = monthly_df['Month'].apply(lambda x: datetime.strptime(x, '%B').month)
    monthly_df = monthly_df.sort_values('Month_Num')
    
    # Dynamic height for mobile
    height = 900
    
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
        height=height,
        showlegend=False,
        template="plotly_white",
        margin=dict(l=50, r=50, t=100, b=50)
    )
    
    # Update y-axis titles
    fig.update_yaxes(title_text="Deviation %", row=1, col=1)
    fig.update_yaxes(title_text="MAI Value", row=1, col=2)
    fig.update_yaxes(title_text="NDVI Value", row=2, col=1)
    fig.update_yaxes(title_text="NDWI Value", row=2, col=2)
    
    return fig

def create_indices_line_chart(monthly_df):
    """Create line chart for NDVI, NDWI indices with auto spacing"""
    if monthly_df is None or monthly_df.empty:
        return None
    
    # Convert month names to datetime for proper sorting
    monthly_df['Month_Num'] = monthly_df['Month'].apply(lambda x: datetime.strptime(x, '%B').month)
    monthly_df = monthly_df.sort_values('Month_Num')
    
    # Dynamic height
    height = 500
    
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
        height=height,
        template="plotly_white",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=50, r=50, t=80, b=80)
    )
    
    return fig

def create_mai_rainfall_chart(monthly_df):
    """Create column chart for MAI and Rainfall Deviation with auto spacing"""
    if monthly_df is None or monthly_df.empty:
        return None
    
    # Convert month names to datetime for proper sorting
    monthly_df['Month_Num'] = monthly_df['Month'].apply(lambda x: datetime.strptime(x, '%B').month)
    monthly_df = monthly_df.sort_values('Month_Num')
    
    # Dynamic height
    height = 500
    
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
        height=height,
        template="plotly_white",
        margin=dict(l=50, r=50, t=80, b=80)
    )
    
    return fig

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
    
    # Filter data based on selected level
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
# MOBILE-FRIENDLY UI ENHANCEMENTS
# -----------------------------
def is_mobile_view():
    """Simple check for mobile view (this is a basic approximation)"""
    # In a real scenario, you might use streamlit's experimental_get_query_params
    # or check screen dimensions. This is a basic approximation.
    return False  # Default to desktop, actual detection would be more complex

# -----------------------------
# MAIN UI WITH TABS - MOBILE OPTIMIZED
# -----------------------------
st.markdown(
    """
    <style>
    @media (max-width: 768px) {
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            padding-left: 1rem;
            padding-right: 1rem;
        }
        .stButton button {
            width: 100%;
        }
        .stSelectbox, .stDateInput {
            font-size: 14px;
        }
    }
    </style>
    """,
    unsafe_allow_html=True
)

    
st.markdown(
    "<span style='color: red; font-weight: bold;'>⚠️ Testing Version:</span> "
    "Data uploaded from <b>01 June 2024</b> to <b>31 Oct 2024</b>. "
    "Please select (Sowing & Current) dates within this range.",
    unsafe_allow_html=True
)

# Responsive columns - stack on mobile
if is_mobile_view():
    col1, col2, col3 = st.columns(1)  # Single column on mobile
else:
    col1, col2, col3 = st.columns(3)  # Three columns on desktop

with col1:
    district = st.selectbox("District *", [""] + districts)
    # Update taluka options based on selected district
    if district:
        taluka_options = [""] + sorted(weather_df[weather_df["District"] == district]["Taluka"].dropna().unique().tolist())
    else:
        taluka_options = [""] + talukas
    taluka = st.selectbox("Taluka", taluka_options)
    
    # Update circle options based on selected taluka
    if taluka and taluka != "":
        circle_options = [""] + sorted(weather_df[weather_df["Taluka"] == taluka]["Circle"].dropna().unique().tolist())
    else:
        circle_options = [""] + circles
    circle = st.selectbox("Circle", circle_options)

with col2:
    crop = st.selectbox("Crop Name *", [""] + crops)
    sowing_date = st.date_input("Sowing Date (dd/mm/yyyy)", value=date.today() - timedelta(days=30), format="DD/MM/YYYY")
    current_date = st.date_input("Current Date (dd/mm/yyyy)", value=date.today(), format="DD/MM/YYYY")

# Make button full width on mobile
if is_mobile_view():
    generate = st.button("🌱 Generate Advisory", use_container_width=True)
else:
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
        
        # Determine level and name for calculations
        if circle and circle != "":
            level = "Circle"
            level_name = circle
        elif taluka and taluka != "":
            level = "Taluka"
            level_name = taluka
        else:
            level = "District"
            level_name = district

        st.info(f"📊 Calculating metrics for **{level}**: {level_name}")

        metrics = calculate_weather_metrics(weather_df, level, level_name, sowing_date_str, current_date_str)
        das_data = metrics["das_data"]
        
        # Get circlewise data for both RS Data indices and Data Matrix
        matrix_data_rs = get_circlewise_data(district, taluka, circle, sowing_date, current_date)
        monthly_df_rs = create_monthly_analysis(matrix_data_rs, "RS Data indices") if not matrix_data_rs.empty else None
        monthly_df_matrix = create_monthly_analysis(matrix_data_rs, "Data Matrix") if not matrix_data_rs.empty else None
        
        # Get comparison data for sub-level charts
        comparison_data = get_comparison_data(district, taluka, circle, sowing_date, current_date)
        
        # Create tabs
        tab1, tab2, tab3, tab4 = st.tabs(["🌤️ Weather Metrics", "📊 Data Charts", "🔍 Combined Indicator", "💾 Data Download"])
        
        # TAB 1: WEATHER METRICS (Existing functionality)
        with tab1:
            st.header(f"🌤️ Weather Metrics - {level}: {level_name}")
            
            # Use responsive columns for metrics
            if is_mobile_view():
                c1, c2, c3 = st.columns(1)  # Stack on mobile
            else:
                c1, c2, c3 = st.columns(3)  # Side by side on desktop
                
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
        
        # TAB 2: DATA CHARTS (MODIFIED AS PER REQUIREMENTS)
        with tab2:
            st.header(f"📊 Data Charts - Monthly Analysis - {level}: {level_name}")
            
            if not matrix_data_rs.empty:
                # Display RS Data indices (NDVI, NDWI, MAI)
                st.subheader("🛰️ RS Data Indices (NDVI, NDWI, MAI)")
                if monthly_df_rs is not None and not monthly_df_rs.empty:
                    st.dataframe(monthly_df_rs, use_container_width=True)
                    
                    # NDVI/NDWI Line Chart - MODIFIED FOR CONDITIONS I & II
                    st.subheader("📈 NDVI & NDWI Indices - Monthly Line Chart")
                    
                    # Use modified function for comparison charts based on conditions
                    comparison_charts = create_comparison_line_charts_modified(
                        comparison_data, level, level_name, district, taluka, circle
                    )
                    
                    if comparison_charts:
                        # Condition I: Taluka level only - show 2 charts
                        if level == "Taluka" and level_name and not circle:
                            ndvi_fig, ndwi_fig = comparison_charts
                            if ndvi_fig and len(ndvi_fig.data) > 0:
                                st.plotly_chart(ndvi_fig, use_container_width=True, config={'responsive': True})
                            else:
                                st.info("No NDVI comparison data available.")
                            
                            if ndwi_fig and len(ndwi_fig.data) > 0:
                                st.plotly_chart(ndwi_fig, use_container_width=True, config={'responsive': True})
                            else:
                                st.info("No NDWI comparison data available.")
                        
                        # Condition II: District level only - show 4 charts
                        elif level == "District" and level_name and not taluka:
                            ndvi_taluka_fig, ndwi_taluka_fig, ndvi_circle_fig, ndwi_circle_fig = comparison_charts
                            
                            st.subheader("Taluka Level Averages (Excluding 0 values)")
                            if is_mobile_view():
                                # Stack charts on mobile
                                if ndvi_taluka_fig and len(ndvi_taluka_fig.data) > 0:
                                    st.plotly_chart(ndvi_taluka_fig, use_container_width=True, config={'responsive': True})
                                else:
                                    st.info("No NDVI taluka average data available.")
                                
                                if ndwi_taluka_fig and len(ndwi_taluka_fig.data) > 0:
                                    st.plotly_chart(ndwi_taluka_fig, use_container_width=True, config={'responsive': True})
                                else:
                                    st.info("No NDWI taluka average data available.")
                            else:
                                # Side by side on desktop
                                col1, col2 = st.columns(2)
                                with col1:
                                    if ndvi_taluka_fig and len(ndvi_taluka_fig.data) > 0:
                                        st.plotly_chart(ndvi_taluka_fig, use_container_width=True, config={'responsive': True})
                                    else:
                                        st.info("No NDVI taluka average data available.")
                                with col2:
                                    if ndwi_taluka_fig and len(ndwi_taluka_fig.data) > 0:
                                        st.plotly_chart(ndwi_taluka_fig, use_container_width=True, config={'responsive': True})
                                    else:
                                        st.info("No NDWI taluka average data available.")
                            
                            st.subheader("All Circles")
                            if is_mobile_view():
                                # Stack charts on mobile
                                if ndvi_circle_fig and len(ndvi_circle_fig.data) > 0:
                                    st.plotly_chart(ndvi_circle_fig, use_container_width=True, config={'responsive': True})
                                else:
                                    st.info("No NDVI circle data available.")
                                
                                if ndwi_circle_fig and len(ndwi_circle_fig.data) > 0:
                                    st.plotly_chart(ndwi_circle_fig, use_container_width=True, config={'responsive': True})
                                else:
                                    st.info("No NDWI circle data available.")
                            else:
                                # Side by side on desktop
                                col1, col2 = st.columns(2)
                                with col1:
                                    if ndvi_circle_fig and len(ndvi_circle_fig.data) > 0:
                                        st.plotly_chart(ndvi_circle_fig, use_container_width=True, config={'responsive': True})
                                    else:
                                        st.info("No NDVI circle data available.")
                                with col2:
                                    if ndwi_circle_fig and len(ndwi_circle_fig.data) > 0:
                                        st.plotly_chart(ndwi_circle_fig, use_container_width=True, config={'responsive': True})
                                    else:
                                        st.info("No NDWI circle data available.")
                        else:
                            # Default behavior for other cases
                            if len(comparison_charts) == 2:
                                ndvi_fig, ndwi_fig = comparison_charts
                                if ndvi_fig and len(ndvi_fig.data) > 0:
                                    st.plotly_chart(ndvi_fig, use_container_width=True, config={'responsive': True})
                                if ndwi_fig and len(ndwi_fig.data) > 0:
                                    st.plotly_chart(ndwi_fig, use_container_width=True, config={'responsive': True})
                    else:
                        st.info("No comparison data available for line charts.")
                    
                    # MAI Analysis - MODIFIED TO USE CLUSTER COLUMN CHART
                    st.subheader("🌧️ MAI Analysis - Monthly Column Chart")
                    mai_clustered_chart = create_mai_analysis_clustered(
                        comparison_data, level, level_name, district, taluka, circle
                    )
                    if mai_clustered_chart:
                        st.plotly_chart(mai_clustered_chart, use_container_width=True, config={'responsive': True})
                    else:
                        st.info("MAI data not available for clustered column chart.")
                else:
                    st.info("No RS Data indices available for the selected parameters.")
                
                # Display Data Matrix indicators
                st.subheader("📋 Data Matrix Indicators")
                if monthly_df_matrix is not None and not monthly_df_matrix.empty:
                    st.dataframe(monthly_df_matrix, use_container_width=True)
                else:
                    st.info("No Data Matrix indicators available.")
            else:
                st.info("No monthly analysis data available for the selected parameters.")
        
        # TAB 3: COMBINED INDICATOR (MODIFIED TO EXCLUDE INDICATOR-3)
        with tab3:
            st.header(f"🔍 Combined Indicator - Data Matrix - {level}: {level_name}")
            
            if not matrix_data_rs.empty:
                # Get combined indicators (EXCLUDING Indicator-3)
                indicators_df = get_combined_indicators(matrix_data_rs)
                
                if not indicators_df.empty:
                    st.subheader("Monthly Indicator Status")
                    
                    # Create a styled table for indicators (EXCLUDING Indicator-3)
                    display_data = []
                    for _, row in indicators_df.iterrows():
                        if pd.notna(row.get('Indicator_1')) or pd.notna(row.get('Indicator_2')):
                            display_data.append({
                                'District': row.get('District', ''),
                                'Taluka': row.get('Taluka', ''),
                                'Circle': row.get('Circle', ''),
                                'Month': row['Month'],
                                'Indicator-1 (NDVI/NDWI)': f"{get_status_icon(row.get('Indicator_1', ''))} {row.get('Indicator_1', 'N/A')}",
                                'Indicator-2 (Rainfall/MAI)': f"{get_status_icon(row.get('Indicator_2', ''))} {row.get('Indicator_2', 'N/A')}",
                                # 'Indicator-3 (Composite)': f"{get_status_icon(row.get('Indicator_3', ''))} {row.get('Indicator_3', 'N/A')}"  # EXCLUDED
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
                        
                        # Summary statistics (EXCLUDING Indicator-3)
                        st.subheader("Indicator Summary")
                        if is_mobile_view():
                            # Stack on mobile
                            st.metric("Good Indicators", indicators_display_df.applymap(
                                lambda x: 'good' in str(x).lower() if pd.notna(x) else False
                            ).sum().sum())
                            st.metric("Moderate Indicators", indicators_display_df.applymap(
                                lambda x: 'moderate' in str(x).lower() if pd.notna(x) else False
                            ).sum().sum())
                            st.metric("Poor Indicators", indicators_display_df.applymap(
                                lambda x: 'poor' in str(x).lower() if pd.notna(x) else False
                            ).sum().sum())
                        else:
                            # Side by side on desktop
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
                    st.dataframe(matrix_data_rs, use_container_width=True)
            else:
                st.info("No data matrix available for the selected parameters.")
        
        # TAB 4: DATA DOWNLOAD
        with tab4:
            st.header(f"💾 Data Download - {level}: {level_name}")
            
            # Available datasets for download
            st.subheader("Available Datasets")
            
            if is_mobile_view():
                # Stack download buttons on mobile
                col1, col2 = st.columns(1)
            else:
                col1, col2 = st.columns(2)
            
            with col1:
                # Weather Data
                st.write("**🌤️ Weather Data**")
                if not das_data.empty:
                    weather_csv = das_data.to_csv(index=False)
                    st.download_button(
                        label="Download Weather Data (CSV)",
                        data=weather_csv,
                        file_name=f"weather_data_{level}_{level_name}.csv",
                        mime="text/csv",
                        use_container_width=is_mobile_view()
                    )
                else:
                    st.write("No weather data available")
                
                # RS Data Indices
                st.write("**🛰️ RS Data Indices**")
                if monthly_df_rs is not None and not monthly_df_rs.empty:
                    monthly_csv = monthly_df_rs.to_csv(index=False)
                    st.download_button(
                        label="Download RS Data Indices (CSV)",
                        data=monthly_csv,
                        file_name=f"rs_data_indices_{level}_{level_name}.csv",
                        mime="text/csv",
                        use_container_width=is_mobile_view()
                    )
                else:
                    st.write("No RS data indices available")
            
            with col2:
                # Data Matrix
                st.write("**🔍 Data Matrix**")
                if not matrix_data_rs.empty:
                    matrix_csv = matrix_data_rs.to_csv(index=False)
                    st.download_button(
                        label="Download Data Matrix (CSV)",
                        data=matrix_csv,
                        file_name=f"data_matrix_{level}_{level_name}.csv",
                        mime="text/csv",
                        use_container_width=is_mobile_view()
                    )
                else:
                    st.write("No data matrix available")
                
                # Combined Indicators (EXCLUDING Indicator-3)
                st.write("**📈 Combined Indicators**")
                if not matrix_data_rs.empty:
                    indicators_df = get_combined_indicators(matrix_data_rs)
                    if not indicators_df.empty:
                        indicators_csv = indicators_df.to_csv(index=False)
                        st.download_button(
                            label="Download Indicators (CSV)",
                            data=indicators_csv,
                            file_name=f"indicators_{level}_{level_name}.csv",
                            mime="text/csv",
                            use_container_width=is_mobile_view()
                        )
                    else:
                        st.write("No indicators data available")
                else:
                    st.write("No indicators data available")
            
            # Data preview sections
            st.subheader("Data Previews")
            
            preview_tabs = st.tabs(["Weather Data", "RS Data Indices", "Data Matrix", "Indicators"])
            
            with preview_tabs[0]:
                if not das_data.empty:
                    st.dataframe(das_data.head(10), use_container_width=True)
                else:
                    st.info("No weather data available for preview")
            
            with preview_tabs[1]:
                if monthly_df_rs is not None and not monthly_df_rs.empty:
                    st.dataframe(monthly_df_rs, use_container_width=True)
                else:
                    st.info("No RS data indices available for preview")
            
            with preview_tabs[2]:
                if not matrix_data_rs.empty:
                    st.dataframe(matrix_data_rs.head(), use_container_width=True)
                else:
                    st.info("No data matrix available for preview")
                    
            with preview_tabs[3]:
                if not matrix_data_rs.empty:
                    indicators_df = get_combined_indicators(matrix_data_rs)
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


















