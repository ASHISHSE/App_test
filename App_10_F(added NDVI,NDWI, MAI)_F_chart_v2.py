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
    # Updated URLs based on your files
    weather_url = "https://github.com/ASHISHSE/App_test/raw/main/weather.xlsb"
    rules_url = "https://github.com/ASHISHSE/App_test/raw/main/rules%20-%20Copy_F.xlsx"  # URL encoded space
    sowing_url = "https://github.com/ASHISHSE/App_test/raw/main/sowing_calendar1.xlsx"

    try:
        # Download files
        wres = requests.get(weather_url, timeout=30)
        rres = requests.get(rules_url, timeout=30)
        sres = requests.get(sowing_url, timeout=30)

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

        # Load weather data with pyxlsb
        try:
            weather_df = pd.read_excel(BytesIO(wres.content), engine='pyxlsb')
            st.success("✅ Weather data loaded successfully")
        except Exception as e:
            st.error(f"Error reading weather.xlsb: {str(e)}")
            return None, None, None, [], [], [], []

        # Load rules data
        try:
            rules_df = pd.read_excel(BytesIO(rres.content))
            st.success("✅ Rules data loaded successfully")
        except Exception as e:
            st.error(f"Error reading rules data: {str(e)}")
            return None, None, None, [], [], [], []

        # Load sowing data
        try:
            sowing_df = pd.read_excel(BytesIO(sres.content))
            st.success("✅ Sowing data loaded successfully")
        except Exception as e:
            st.error(f"Error reading sowing data: {str(e)}")
            return None, None, None, [], [], [], []

        # Debug: Show column names
        st.write("📋 Weather data columns:", list(weather_df.columns))
        st.write("📋 Sowing data columns:", list(sowing_df.columns))
        st.write("📋 Rules data columns:", list(rules_df.columns))

        # Process weather data
        # Flexible date column detection for weather data
        date_col = None
        for candidate in ["Date(DD-MM-YYYY)", "Date", "DD-MM-YYYY"]:
            if candidate in weather_df.columns:
                date_col = candidate
                break
        if date_col is None:
            # Use first column that contains 'date' in name
            for col in weather_df.columns:
                if 'date' in str(col).lower():
                    date_col = col
                    break
            if date_col is None:
                date_col = weather_df.columns[0]  # Use first column as fallback

        st.write(f"📅 Using date column: {date_col}")

        # Convert date column
        weather_df["Date_dt"] = pd.to_datetime(weather_df[date_col], format="%d-%m-%Y", errors="coerce")
        weather_df = weather_df.dropna(subset=["Date_dt"]).copy()

        # Convert numeric columns
        for col in ["Rainfall", "Tmax", "Tmin", "max_Rh", "min_Rh"]:
            if col in weather_df.columns:
                weather_df[col] = pd.to_numeric(weather_df[col], errors="coerce")

        # Clean text columns in all dataframes
        for df, df_name in [(weather_df, "weather"), (sowing_df, "sowing"), (rules_df, "rules")]:
            for col in df.columns:
                if df[col].dtype == 'object':
                    df[col] = df[col].astype(str).str.strip()

        # Get unique values for dropdowns from weather data
        districts = sorted(weather_df["District"].dropna().unique().tolist()) if "District" in weather_df.columns else []
        talukas = sorted(weather_df["Taluka"].dropna().unique().tolist()) if "Taluka" in weather_df.columns else []
        circles = sorted(weather_df["Circle"].dropna().unique().tolist()) if "Circle" in weather_df.columns else []
        
        # Get crops from rules data
        crops = sorted(rules_df["Crop"].dropna().unique().tolist()) if "Crop" in rules_df.columns else []

        st.write(f"📍 Found {len(districts)} districts, {len(talukas)} talukas, {len(circles)} circles, {len(crops)} crops")

        return weather_df, rules_df, sowing_df, districts, talukas, circles, crops

    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        import traceback
        st.error(f"Detailed error: {traceback.format_exc()}")
        return None, None, None, [], [], [], []

# ---------------------------
# LOAD CIRCLEWISE DATA MATRIX
# ---------------------------
@st.cache_data
def load_circlewise_data():
    url = "https://github.com/ASHISHSE/App_test/raw/main/Circlewise_Data_Matrix_Indicator_2024_F_upload.xlsx"
    try:
        df = pd.read_excel(url)
        st.success("✅ Circlewise data matrix loaded successfully")
        
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
        
        st.write("📋 Circlewise data columns:", list(df.columns))
        st.write(f"📍 Circlewise data shape: {df.shape}")
        
        return df
        
    except Exception as e:
        st.error(f"Error loading circlewise data: {str(e)}")
        return pd.DataFrame()

# -----------------------------
# INITIALIZE APP
# -----------------------------
st.title("🌱 Crop Advisory System")
st.markdown("---")

# Load all data
with st.spinner("Loading data..."):
    weather_df, rules_df, sowing_df, districts, talukas, circles, crops = load_data()

if weather_df is None:
    st.error("❌ Failed to load data. Please check the error messages above.")
    st.stop()

# Load circlewise data
circlewise_df = load_circlewise_data()

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def get_filtered_talukas(selected_district):
    """Get talukas filtered by selected district"""
    if not selected_district or weather_df is None:
        return []
    filtered_df = weather_df[weather_df["District"] == selected_district]
    return sorted(filtered_df["Taluka"].dropna().unique().tolist())

def get_filtered_circles(selected_district, selected_taluka):
    """Get circles filtered by selected district and taluka"""
    if not selected_district or not selected_taluka or weather_df is None:
        return []
    filtered_df = weather_df[(weather_df["District"] == selected_district) & 
                            (weather_df["Taluka"] == selected_taluka)]
    return sorted(filtered_df["Circle"].dropna().unique().tolist())

def get_circlewise_data(district, taluka, circle, sowing_date, current_date):
    """Get circlewise data for selected location and date range"""
    df = circlewise_df.copy()
    
    if df.empty:
        return pd.DataFrame()

    # Filter by District, Taluka, Circle
    df = df[df["District"] == district]
    
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
        return result_df
    
    return pd.DataFrame()

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
            month_data['MAI_Value'] = row.get("MAI")
            month_data['MAI_Category'] = row.get("MAI_CAT")
            month_data['Indicator_1'] = row.get("Indicator-1 NDVI/NDWI")
            month_data['Indicator_2'] = row.get("Indicator-2 RAINFALL/MAI")
            month_data['Indicator_3'] = row.get("Indicator-3 NDVI_NDWI/RAINFALL_MAI")
        
        monthly_data.append(month_data)
    
    return pd.DataFrame(monthly_data)

def calculate_weather_metrics(weather_data, district, taluka, circle, sowing_date_str, current_date_str):
    """Calculate weather metrics for selected location"""
    df = weather_data.copy()
    
    # Filter by location
    if district:
        df = df[df["District"] == district]
    if taluka:
        df = df[df["Taluka"] == taluka]
    if circle:
        df = df[df["Circle"] == circle]

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
        "rainfall_das": das_data["Rainfall"].sum() if "Rainfall" in das_data.columns else 0,
        "rainfall_last_week": week_data["Rainfall"].sum() if "Rainfall" in week_data.columns else 0,
        "rainfall_last_month": month_data["Rainfall"].sum() if "Rainfall" in month_data.columns else 0,
        "rainy_days_das": (das_data["Rainfall"] > 0).sum() if "Rainfall" in das_data.columns else 0,
        "rainy_days_week": (week_data["Rainfall"] > 0).sum() if "Rainfall" in week_data.columns else 0,
        "rainy_days_month": (month_data["Rainfall"] > 0).sum() if "Rainfall" in month_data.columns else 0,
        "tmax_avg": avg_ignore_zero_and_na(das_data["Tmax"]) if "Tmax" in das_data.columns else None,
        "tmin_avg": avg_ignore_zero_and_na(das_data["Tmin"]) if "Tmin" in das_data.columns else None,
        "max_rh_avg": avg_ignore_zero_and_na(das_data["max_Rh"]) if "max_Rh" in das_data.columns else None,
        "min_rh_avg": avg_ignore_zero_and_na(das_data["min_Rh"]) if "min_Rh" in das_data.columns else None,
        "das": das,
        "das_data": das_data
    }

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
# MAIN UI
# -----------------------------
st.markdown(
    "<span style='color: red; font-weight: bold;'>⚠️ Testing Version:</span> "
    "Data uploaded from <b>01 June 2024</b> to <b>31 Oct 2024</b>. "
    "Please select (Sowing & Current) dates within this range.",
    unsafe_allow_html=True
)

# Input Form
col1, col2, col3 = st.columns(3)
with col1:
    district = st.selectbox("District *", [""] + districts)
    
with col2:
    # Dynamic taluka dropdown based on selected district
    taluka_options = [""] + get_filtered_talukas(district)
    taluka = st.selectbox("Taluka", taluka_options)
    
with col3:
    # Dynamic circle dropdown based on selected district and taluka
    circle_options = [""] + get_filtered_circles(district, taluka)
    circle = st.selectbox("Circle", circle_options)

col4, col5, col6 = st.columns(3)
with col4:
    crop = st.selectbox("Crop Name *", [""] + crops)
with col5:
    sowing_date = st.date_input("Sowing Date (dd/mm/yyyy)", value=date.today() - timedelta(days=30), format="DD/MM/YYYY")
with col6:
    current_date = st.date_input("Current Date (dd/mm/yyyy)", value=date.today(), format="DD/MM/YYYY")

generate = st.button("🌱 Generate Advisory", type="primary")

# -----------------------------
# PROCESS RESULTS
# -----------------------------
if generate:
    if not district or not crop:
        st.error("❌ Please select District and Crop Name (required fields)")
    else:
        with st.spinner("Generating advisory..."):
            sowing_date_str = sowing_date.strftime("%d/%m/%Y")
            current_date_str = current_date.strftime("%d/%m/%Y")
            
            # Calculate weather metrics
            metrics = calculate_weather_metrics(weather_df, district, taluka, circle, sowing_date_str, current_date_str)
            das_data = metrics["das_data"]
            
            # Get circlewise data
            matrix_data = get_circlewise_data(district, taluka, circle, sowing_date, current_date)
            monthly_df = create_monthly_analysis(matrix_data) if not matrix_data.empty else None
            
            # Create tabs
            tab1, tab2, tab3, tab4 = st.tabs(["🌤️ Weather Metrics", "📊 Data Charts", "🔍 Combined Indicator", "💾 Data Download"])
            
            # TAB 1: WEATHER METRICS
            with tab1:
                st.header("🌤️ Weather Metrics")
                
                # Display metrics in columns
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Rainfall - Last Week (mm)", f"{metrics['rainfall_last_week']:.1f}")
                    st.metric("Rainy Days - Last Week", metrics["rainy_days_week"])
                    st.metric("Rainfall - Last Month (mm)", f"{metrics['rainfall_last_month']:.1f}")
                    st.metric("Rainy Days - Last Month", metrics["rainy_days_month"])
                with col2:
                    st.metric("Rainfall - Since Sowing (mm)", f"{metrics['rainfall_das']:.1f}")
                    st.metric("Rainy Days - Since Sowing", metrics["rainy_days_das"])
                    st.metric("Days After Sowing (DAS)", metrics["das"])
                    st.metric("Tmax Avg", f"{metrics['tmax_avg']:.1f}" if metrics['tmax_avg'] else "N/A")
                with col3:
                    st.metric("Tmin Avg", f"{metrics['tmin_avg']:.1f}" if metrics['tmin_avg'] else "N/A")
                    st.metric("Max RH Avg", f"{metrics['max_rh_avg']:.1f}" if metrics['max_rh_avg'] else "N/A")
                    st.metric("Min RH Avg", f"{metrics['min_rh_avg']:.1f}" if metrics['min_rh_avg'] else "N/A")

                # Daily Weather Data
                st.markdown("---")
                st.header("📅 Daily Weather Data")
                if not das_data.empty:
                    display_df = das_data.copy().sort_values("Date_dt")
                    display_df["Date"] = display_df["Date_dt"].dt.strftime("%d-%m-%Y")
                    columns_to_show = ["Date", "Rainfall", "Tmax", "Tmin", "max_Rh", "min_Rh"]
                    display_df = display_df[[c for c in columns_to_show if c in display_df.columns]]

                    def highlight_rainy_days(row):
                        return ["background-color: #e6f3ff" if row["Rainfall"] > 0 else "" for _ in row]

                    st.dataframe(display_df.style.apply(highlight_rainy_days, axis=1), use_container_width=True)
                else:
                    st.info("No daily weather data for selected date range.")

                # Sowing Comments
                st.markdown("---")
                st.header("📝 Comment on Sowing")
                comments = get_sowing_comments(sowing_date_str, district, taluka, circle, crop, sowing_df)
                if comments:
                    for c in comments:
                        st.write(f"**Matched Period:** {c['matched_fn']}")
                        st.write(f"**Comment:** {c['comment']}")
                else:
                    st.write("No matching sowing comments found.")

                # Growth Stage Advisory
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
                    st.subheader("📋 Monthly Data Summary")
                    if monthly_df is not None and not monthly_df.empty:
                        st.dataframe(monthly_df, use_container_width=True)
                        
                        # Create charts based on available data
                        if any(pd.notna(monthly_df['NDVI_Value'])) or any(pd.notna(monthly_df['NDWI_Value'])):
                            st.subheader("📈 Vegetation & Water Indices")
                            
                            # Create combined chart for NDVI and NDWI
                            fig = go.Figure()
                            
                            if any(pd.notna(monthly_df['NDVI_Value'])):
                                fig.add_trace(go.Scatter(
                                    x=monthly_df['Month'] + " " + monthly_df['Year'].astype(str),
                                    y=monthly_df['NDVI_Value'],
                                    mode='lines+markers',
                                    name='NDVI',
                                    line=dict(color='green', width=3),
                                    marker=dict(size=8)
                                ))
                            
                            if any(pd.notna(monthly_df['NDWI_Value'])):
                                fig.add_trace(go.Scatter(
                                    x=monthly_df['Month'] + " " + monthly_df['Year'].astype(str),
                                    y=monthly_df['NDWI_Value'],
                                    mode='lines+markers',
                                    name='NDWI',
                                    line=dict(color='blue', width=3),
                                    marker=dict(size=8)
                                ))
                            
                            fig.update_layout(
                                title="NDVI & NDWI Trends",
                                xaxis_title="Month",
                                yaxis_title="Index Value",
                                height=400,
                                template="plotly_white"
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        
                        # MAI Chart
                        if any(pd.notna(monthly_df['MAI_Value'])):
                            st.subheader("🌾 MAI Index")
                            fig_mai = px.bar(
                                monthly_df, 
                                x=monthly_df['Month'] + " " + monthly_df['Year'].astype(str),
                                y='MAI_Value',
                                title="Monthly MAI Values",
                                color='MAI_Value',
                                color_continuous_scale='viridis'
                            )
                            fig_mai.update_layout(height=400)
                            st.plotly_chart(fig_mai, use_container_width=True)
                            
                    else:
                        st.info("No monthly analysis data available.")
                else:
                    st.info("No circlewise data available for the selected parameters.")
                    
                    # Show available data for debugging
                    with st.expander("Debug: Available Circlewise Data"):
                        if not circlewise_df.empty:
                            st.write("Sample of available circlewise data:")
                            st.dataframe(circlewise_df.head(10))
                        else:
                            st.write("No circlewise data loaded")

            # TAB 3: COMBINED INDICATOR
            with tab3:
                st.header("🔍 Combined Indicator - Data Matrix")
                
                if not matrix_data.empty:
                    st.subheader("Complete Data Matrix")
                    st.dataframe(matrix_data, use_container_width=True)
                    
                    # Display indicators summary
                    if all(col in matrix_data.columns for col in ["Indicator-1 NDVI/NDWI", "Indicator-2 RAINFALL/MAI", "Indicator-3 NDVI_NDWI/RAINFALL_MAI"]):
                        st.subheader("📊 Monthly Indicator Summary")
                        
                        summary_data = []
                        for _, row in matrix_data.iterrows():
                            summary_data.append({
                                'Month-Year': f"{row['Month']} {row['Year']}",
                                'NDVI/NDWI': f"{get_status_icon(row['Indicator-1 NDVI/NDWI'])} {row['Indicator-1 NDVI/NDWI']}",
                                'Rainfall/MAI': f"{get_status_icon(row['Indicator-2 RAINFALL/MAI'])} {row['Indicator-2 RAINFALL/MAI']}",
                                'Composite': f"{get_status_icon(row['Indicator-3 NDVI_NDWI/RAINFALL_MAI'])} {row['Indicator-3 NDVI_NDWI/RAINFALL_MAI']}"
                            })
                        
                        if summary_data:
                            summary_df = pd.DataFrame(summary_data)
                            st.dataframe(summary_df, use_container_width=True)
                else:
                    st.info("No data matrix available for the selected parameters.")

            # TAB 4: DATA DOWNLOAD
            with tab4:
                st.header("💾 Data Download")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # Weather Data Download
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
                    # Data Matrix Download
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

# -----------------------------
# FOOTER
# -----------------------------
st.markdown("---")
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
            Version 2.0 | Powered by Agricose | Last Updated: Sept 2025
        </span>
    </div>
    """,
    unsafe_allow_html=True
)
