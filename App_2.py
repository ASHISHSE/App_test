import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import urllib.parse
import requests
from io import BytesIO

# Set page configuration
st.set_page_config(
    page_title="Crop Advisory System",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown("""
    <style>
    .header {
        background: linear-gradient(135deg, #2c3e50, #3498db);
        color: white;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 25px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    }
    .card {
        border-radius: 10px;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        margin-bottom: 20px;
        border: none;
    }
    .card-header {
        background-color: #2c3e50;
        color: white;
        border-radius: 10px 10px 0 0 !important;
        padding: 15px 20px;
    }
    .btn-primary {
        background-color: #3498db;
        border: none;
        padding: 12px 25px;
        font-weight: 600;
        border-radius: 8px;
    }
    .btn-primary:hover {
        background-color: #2980b9;
    }
    .advisory-result {
        background-color: #e8f4f8;
        border-left: 4px solid #3498db;
        padding: 15px;
        border-radius: 5px;
        margin-bottom: 20px;
    }
    .weather-icon {
        font-size: 24px;
        margin-right: 10px;
        color: #3498db;
    }
    .section-title {
        color: #2c3e50;
        border-bottom: 2px solid #3498db;
        padding-bottom: 10px;
        margin-bottom: 20px;
    }
    .share-link {
        background-color: #e8f4f8;
        padding: 10px;
        border-radius: 5px;
        word-break: break-all;
        font-family: monospace;
    }
    .weather-info {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        height: 100%;
        text-align: center;
    }
    .location-hierarchy {
        background-color: #e8f4f8;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 20px;
    }
    .stSelectbox, .stDateInput {
        margin-bottom: 15px;
    }
    </style>
""", unsafe_allow_html=True)

# Header section
st.markdown("""
    <div class="header text-center">
        <h1><i class="fas fa-seedling me-2"></i>Crop Advisory System</h1>
        <p class="lead">Get personalized crop recommendations based on location, weather data, and growth stage</p>
    </div>
""", unsafe_allow_html=True)

# Load data from GitHub
@st.cache_data
def load_data():
    # Load weather data
    weather_url = "https://github.com/ASHISHSE/App_test/raw/main/weather.xlsx"
    weather_response = requests.get(weather_url)
    weather_df = pd.read_excel(BytesIO(weather_response.content))
    
    # Load rules data
    rules_url = "https://github.com/ASHISHSE/App_test/raw/main/rules.xlsx"
    rules_response = requests.get(rules_url)
    rules_df = pd.read_excel(BytesIO(rules_response.content))
    
    # Load sowing calendar data
    sowing_url = "https://github.com/ASHISHSE/App_test/raw/main/sowing_calendar.xlsx"
    sowing_response = requests.get(sowing_url)
    sowing_df = pd.read_excel(BytesIO(sowing_response.content))
    
    # Extract unique districts, talukas, circles, and crops
    districts = sorted(weather_df['District'].unique())
    talukas = sorted(weather_df['Taluka'].unique())
    circles = sorted(weather_df['Circle'].unique())
    crops = sorted(rules_df['Crop'].unique())
    
    return weather_df, rules_df, sowing_df, districts, talukas, circles, crops

try:
    weather_df, rules_df, sowing_df, districts, talukas, circles, crops = load_data()
except:
    st.error("Error loading data from GitHub. Please check the file URLs.")
    st.stop()

# Initialize session state
if 'district' not in st.session_state:
    st.session_state.district = ""
if 'taluka' not in st.session_state:
    st.session_state.taluka = ""
if 'circle' not in st.session_state:
    st.session_state.circle = ""
if 'crop' not in st.session_state:
    st.session_state.crop = ""
if 'sowing_date' not in st.session_state:
    st.session_state.sowing_date = None
if 'current_date' not in st.session_state:
    st.session_state.current_date = date.today()

# Function to convert date format
def convert_date_format(date_str, input_format='%Y-%m-%d', output_format='%d-%m-%Y'):
    try:
        date_obj = datetime.strptime(date_str, input_format)
        return date_obj.strftime(output_format)
    except:
        return date_str

# Function to calculate weather metrics
def calculate_weather_metrics(weather_data, location_level, location_name, sowing_date, current_date):
    # Filter weather data based on location
    if location_level == 'Circle':
        filtered_data = weather_data[weather_data['Circle'] == location_name]
    elif location_level == 'Taluka':
        filtered_data = weather_data[weather_data['Taluka'] == location_name]
    else:  # District
        filtered_data = weather_data[weather_data['District'] == location_name]
    
    # Convert date strings to datetime objects for filtering
    filtered_data['Date_dt'] = pd.to_datetime(filtered_data['Date'], format='%d-%m-%Y')
    sowing_dt = datetime.strptime(sowing_date, '%d-%m-%Y')
    current_dt = datetime.strptime(current_date, '%d-%m-%Y')
    
    # Calculate DAS (Days After Sowing)
    das = (current_dt - sowing_dt).days
    
    # Filter data for different time periods
    last_week_start = current_dt - timedelta(days=7)
    last_month_start = current_dt - timedelta(days=30)
    
    last_week_data = filtered_data[(filtered_data['Date_dt'] >= last_week_start) & (filtered_data['Date_dt'] <= current_dt)]
    last_month_data = filtered_data[(filtered_data['Date_dt'] >= last_month_start) & (filtered_data['Date_dt'] <= current_dt)]
    das_data = filtered_data[(filtered_data['Date_dt'] >= sowing_dt) & (filtered_data['Date_dt'] <= current_dt)]
    
    # Calculate metrics
    metrics = {
        'rainfall_last_week': last_week_data['Rainfall'].sum(),
        'rainfall_last_month': last_month_data['Rainfall'].sum(),
        'rainfall_das': das_data['Rainfall'].sum(),
        'tmax_avg': das_data['Tmax'].mean(),
        'tmin_avg': das_data['Tmin'].mean(),
        'max_rh_avg': das_data['max_Rh'].mean(),
        'min_rh_avg': das_data['min_Rh'].mean(),
        'das': das
    }
    
    return metrics

# Function to get growth stage advisory
def get_growth_advisory(crop, das, rainfall_das, rules_df):
    # Find the current growth stage
    current_stage = rules_df[(rules_df['Crop'] == crop) & (rules_df['DAS_Start'] <= das) & (rules_df['DAS_End'] >= das)]
    
    if current_stage.empty:
        return "No advisory available for this growth stage."
    
    stage_name = current_stage['Growth_Stage'].values[0]
    water_required = current_stage['Water_Required'].values[0]
    
    # Compare rainfall with water requirement
    water_deficit = water_required - rainfall_das
    
    if water_deficit > 0:
        advisory = f"Water deficit of {water_deficit:.1f} mm detected. Irrigation recommended."
    elif water_deficit < 0:
        advisory = f"Excess water of {abs(water_deficit):.1f} mm detected. Drainage may be needed."
    else:
        advisory = "Adequate water available. No irrigation needed."
    
    return f"Crop is at {stage_name} stage ({das} Days After Sowing). {advisory}"

# Function to get sowing advisory
def get_sowing_advisory(sowing_date, sowing_df):
    sowing_dt = datetime.strptime(sowing_date, '%d-%m-%Y')
    sowing_day = sowing_dt.day
    sowing_month = sowing_dt.month
    
    # Find sowing advisory from sowing calendar
    sowing_advisory_data = sowing_df[(sowing_df['Month'] == sowing_month) & (sowing_df['Day_Start'] <= sowing_day) & (sowing_df['Day_End'] >= sowing_day)]
    
    if not sowing_advisory_data.empty:
        fn = sowing_advisory_data['FN'].values[0]
        advisory = sowing_advisory_data['Advisory'].values[0]
        return f"{fn}: {advisory}"
    else:
        if sowing_day <= 15:
            fn = "1FN"
            advisory = "Early sowing due to rainfall on time / Water source available"
        else:
            fn = "2FN"
            advisory = "Ideal sowing period"
        
        return f"{fn} (Month Date between {1 if sowing_day <= 15 else 16} to {15 if sowing_day <= 15 else 31}): {advisory}"

# Create form for user input
with st.form("crop_advisory_form"):
    # Location hierarchy display
    st.markdown("""
        <div class="location-hierarchy">
            <h5><i class="fas fa-map-marker-alt me-2"></i>Selected Location</h5>
            <div class="d-flex flex-wrap gap-2 mt-2">
                <span class="hierarchy-item">District: <span class="badge bg-primary">%s</span></span>
                <span class="hierarchy-item">Taluka: <span class="badge bg-secondary">%s</span></span>
                <span class="hierarchy-item">Circle: <span class="badge bg-info">%s</span></span>
            </div>
        </div>
    """ % (
        st.session_state.district if st.session_state.district else "Not selected",
        st.session_state.taluka if st.session_state.taluka else "Not selected",
        st.session_state.circle if st.session_state.circle else "Not selected"
    ), unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### Location Information")
        district = st.selectbox(
            "District *", 
            options=[""] + districts, 
            key="district_select",
            index=districts.index(st.session_state.district) + 1 if st.session_state.district in districts else 0
        )
        
        # Filter talukas based on district selection
        taluka_options = [""]
        if district:
            district_talukas = sorted(weather_df[weather_df['District'] == district]['Taluka'].unique())
            taluka_options.extend(district_talukas)
        else:
            taluka_options.extend(talukas)
            
        taluka = st.selectbox(
            "Taluka", 
            options=taluka_options, 
            key="taluka_select", 
            disabled=not district,
            index=taluka_options.index(st.session_state.taluka) if st.session_state.taluka in taluka_options else 0
        )
        
        # Filter circles based on taluka selection
        circle_options = [""]
        if taluka:
            taluka_circles = sorted(weather_df[weather_df['Taluka'] == taluka]['Circle'].unique())
            circle_options.extend(taluka_circles)
        else:
            circle_options.extend(circles)
            
        circle = st.selectbox(
            "Circle", 
            options=circle_options, 
            key="circle_select", 
            disabled=not taluka,
            index=circle_options.index(st.session_state.circle) if st.session_state.circle in circle_options else 0
        )
    
    with col2:
        st.markdown("### Crop Information")
        crop = st.selectbox(
            "Crop Name *", 
            options=[""] + crops, 
            key="crop_select",
            index=crops.index(st.session_state.crop) + 1 if st.session_state.crop in crops else 0
        )
        
        # Sowing date with DD-MM-YYYY format
        sowing_date = st.date_input(
            "Sowing Date (DD-MM-YYYY) *", 
            key="sowing_date_input",
            value=st.session_state.sowing_date,
            format="DD-MM-YYYY"
        )
    
    with col3:
        st.markdown("### Date Information")
        # Current date with DD-MM-YYYY format
        current_date = st.date_input(
            "Current Date (DD-MM-YYYY) *", 
            value=st.session_state.current_date,
            key="current_date_input",
            format="DD-MM-YYYY"
        )
        
        st.markdown("<br>", unsafe_allow_html=True)
        if st.form_submit_button("📅 Set to Today", key="today_btn"):
            current_date = date.today()
            st.session_state.current_date = current_date
            st.experimental_rerun()
    
    # Generate advisory button
    generate_btn = st.form_submit_button("🌱 Generate Advisory", use_container_width=True)

# Process form submission
if generate_btn:
    # Update session state
    st.session_state.district = district
    st.session_state.taluka = taluka
    st.session_state.circle = circle
    st.session_state.crop = crop
    st.session_state.sowing_date = sowing_date
    st.session_state.current_date = current_date
    
    # Validate inputs
    if not district or not crop or not sowing_date or not current_date:
        st.error("Please fill all required fields: District, Crop, Sowing Date, and Current Date.")
    else:
        # Convert dates to DD-MM-YYYY format
        sowing_date_str = sowing_date.strftime('%d-%m-%Y')
        current_date_str = current_date.strftime('%d-%m-%Y')
        
        # Check if sowing date is in the future
        if sowing_date > current_date:
            st.error("Sowing date cannot be in the future compared to current date.")
        else:
            # Determine location level for weather data
            if circle:
                location_level = "Circle"
                location_name = circle
            elif taluka:
                location_level = "Taluka"
                location_name = taluka
            else:
                location_level = "District"
                location_name = district
            
            # Calculate weather metrics
            metrics = calculate_weather_metrics(weather_df, location_level, location_name, sowing_date_str, current_date_str)
            
            # Display weather information
            st.markdown("---")
            st.markdown("## 🌤️ Weather Information")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("""
                    <div class="weather-info">
                        <p><i class="fas fa-cloud-rain weather-icon"></i>Rainfall</p>
                """, unsafe_allow_html=True)
                
                st.metric("Last Week", f"{metrics['rainfall_last_week']:.1f} mm")
                st.metric("Last Month", f"{metrics['rainfall_last_month']:.1f} mm")
                st.metric("Since Sowing", f"{metrics['rainfall_das']:.1f} mm")
                st.markdown("</div>", unsafe_allow_html=True)
            
            with col2:
                st.markdown("""
                    <div class="weather-info">
                        <p><i class="fas fa-temperature-high weather-icon"></i>Temperature</p>
                """, unsafe_allow_html=True)
                
                st.metric("Max", f"{metrics['tmax_avg']:.1f} °C")
                st.metric("Min", f"{metrics['tmin_avg']:.1f} °C")
                st.markdown("</div>", unsafe_allow_html=True)
            
            with col3:
                st.markdown("""
                    <div class="weather-info">
                        <p><i class="fas fa-tint weather-icon"></i>Humidity</p>
                """, unsafe_allow_html=True)
                
                st.metric("Max", f"{metrics['max_rh_avg']:.1f} %")
                st.metric("Min", f"{metrics['min_rh_avg']:.1f} %")
                st.markdown("</div>", unsafe_allow_html=True)
            
            # Display advisory results
            st.markdown("---")
            st.markdown("## 📋 Advisory Results")
            
            # Sowing advisory
            sowing_advisory = get_sowing_advisory(sowing_date_str, sowing_df)
            st.markdown("""
                <div class="advisory-result">
                    <h5><i class="fas fa-calendar-check me-2"></i>Sowing Advisory</h5>
                    <p id="sowingAdvisory" class="mb-0">%s</p>
                </div>
            """ % sowing_advisory, unsafe_allow_html=True)
            
            # Growth stage advisory
            growth_advisory = get_growth_advisory(crop, metrics['das'], metrics['rainfall_das'], rules_df)
            st.markdown("""
                <div class="advisory-result">
                    <h5><i class="fas fa-seedling me-2"></i>Growth Stage Advisory</h5>
                    <p id="growthAdvisory" class="mb-0">%s</p>
                </div>
            """ % growth_advisory, unsafe_allow_html=True)
            
            # Share functionality
            st.markdown("---")
            st.markdown("## 📤 Share Advisory")
            st.write("Share this advisory with others via this link:")
            
            # Generate shareable link
            params = {
                "district": district,
                "taluka": taluka or "",
                "circle": circle or "",
                "crop": crop,
                "sowing": sowing_date_str,
                "current": current_date_str
            }
            
            query_string = urllib.parse.urlencode(params)
            # For Streamlit sharing, we need to construct the URL properly
            shareable_link = f"https://share.streamlit.io/your-username/your-repo/main/app.py?{query_string}"
            
            st.markdown(f"""
                <div class="share-link">
                    {shareable_link}
                </div>
            """, unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("📋 Copy Link", key="copy_btn", use_container_width=True):
                    st.write("Link copied to clipboard!")
            
            with col2:
                # WhatsApp share
                whatsapp_text = f"Check out this crop advisory for {crop} in {district}{f', {taluka}' if taluka else ''}{f', {circle}' if circle else ''}"
                whatsapp_url = f"https://wa.me/?text={urllib.parse.quote(whatsapp_text + ': ' + shareable_link)}"
                st.markdown(f'<a href="{whatsapp_url}" target="_blank"><button style="width:100%">📱 Share via WhatsApp</button></a>', unsafe_allow_html=True)
            
            with col3:
                # Email share
                subject = f"Crop Advisory for {crop} in {district}"
                body = f"Hello,\n\nI wanted to share this crop advisory with you:\n\nCrop: {crop}\nDistrict: {district}\nTaluka: {taluka or 'Not specified'}\nCircle: {circle or 'Not specified'}\nSowing Date: {sowing_date_str}\nCurrent Date: {current_date_str}\n\nLink: {shareable_link}\n\nBest regards."
                mailto_url = f"mailto:?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
                st.markdown(f'<a href="{mailto_url}"><button style="width:100%">📧 Share via Email</button></a>', unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown("<p style='text-align: center; color: #7f8c8d;'>Crop Advisory System © 2023. Designed for agricultural extension services.</p>", unsafe_allow_html=True)
