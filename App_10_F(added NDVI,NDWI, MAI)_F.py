import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime, date, timedelta
import requests
from io import BytesIO
import plotly.express as px

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
# NEW FUNCTION FOR MONTHLY ANALYSIS
# -----------------------------
def create_monthly_analysis(matrix_data):
    """Create detailed monthly analysis with index values and categories"""
    if matrix_data.empty:
        return None
    
    monthly_data = []
    
    # Extract months from column names
    months = set()
    for col in matrix_data.columns:
        if '_' in col and any(month in col for month in ['January', 'February', 'March', 'April', 'May', 'June', 
                                                       'July', 'August', 'September', 'October', 'November', 'December']):
            for month in ['January', 'February', 'March', 'April', 'May', 'June', 
                         'July', 'August', 'September', 'October', 'November', 'December']:
                if month in col:
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
        
        # Extract values for each parameter
        for col in matrix_data.columns:
            col_lower = col.lower()
            if month.lower() in col_lower:
                value = matrix_data[col].iloc[0] if not matrix_data[col].empty else None
                
                if 'ndvi' in col_lower and 'cat' not in col_lower:
                    month_data['NDVI_Value'] = value
                elif 'ndvi' in col_lower and 'cat' in col_lower:
                    month_data['NDVI_Category'] = value
                elif 'ndwi' in col_lower and 'cat' not in col_lower:
                    month_data['NDWI_Value'] = value
                elif 'ndwi' in col_lower and 'cat' in col_lower:
                    month_data['NDWI_Category'] = value
                elif 'rainfall_dev' in col_lower and 'cat' not in col_lower:
                    month_data['Rainfall_Dev_Value'] = value
                elif 'rainfall_dev' in col_lower and 'cat' in col_lower:
                    month_data['Rainfall_Dev_Category'] = value
                elif 'mai' in col_lower and 'cat' not in col_lower:
                    month_data['MAI_Value'] = value
                elif 'mai' in col_lower and 'cat' in col_lower:
                    month_data['MAI_Category'] = value
                elif 'indicator-1' in col_lower or 'indicator-1' in col_lower:
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
                # Display monthly analysis in tabs
                tab1, tab2 = st.tabs(["📊 Monthly Summary Table", "📈 Detailed Monthly Analysis"])
                
                with tab1:
                    st.subheader("Monthly Index Summary")
                    
                    # Create a simplified summary table
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
                
                with tab2:
                    st.subheader("Detailed Monthly Analysis")
                    
                    # Display each month in an expandable section
                    for _, month_data in monthly_df.iterrows():
                        with st.expander(f"📅 {month_data['Month']} 2024 - Detailed Analysis", expanded=True):
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
                            
                            # Indicators section
                            st.markdown("---")
                            st.markdown("### 📈 Combined Indicators")
                            
                            ind_col1, ind_col2, ind_col3 = st.columns(3)
                            
                            with ind_col1:
                                st.markdown("#### Indicator 1: NDVI/NDWI")
                                st.markdown(f"**Status:** {get_status_icon(month_data['Indicator_1'])} {month_data['Indicator_1']}")
                                st.info("Measures vegetation health relative to water content")
                            
                            with ind_col2:
                                st.markdown("#### Indicator 2: Rainfall/MAI")
                                st.markdown(f"**Status:** {get_status_icon(month_data['Indicator_2'])} {month_data['Indicator_2']}")
                                st.info("Compares rainfall deviation with moisture availability")
                            
                            with ind_col3:
                                st.markdown("#### Indicator 3: Composite")
                                st.markdown(f"**Status:** {get_status_icon(month_data['Indicator_3'])} {month_data['Indicator_3']}")
                                st.info("Overall crop health and environmental condition")
                
                # Download option
                st.markdown("---")
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
