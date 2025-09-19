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
    try:
        # Load weather data
        weather_url = "https://github.com/ASHISHSE/App_test/raw/main/weather.xlsx"
        weather_response = requests.get(weather_url)
        weather_df = pd.read_excel(BytesIO(weather_response.content))
        
        # Convert Date(DDMMYY) to proper format
        weather_df['Date'] = weather_df['Date(DDMMYY)'].apply(
            lambda x: f"{str(x).zfill(6)[:2]}-{str(x).zfill(6)[2:4]}-20{str(x).zfill(6)[4:6]}"
        )
        
        # Load rules data
        rules_url = "https://github.com/ASHISHSE/App_test/raw/main/rules.xlsx"
        rules_response = requests.get(rules_url)
        rules_df = pd.read_excel(BytesIO(rules_response.content))
        
        # Load sowing calendar data
        sowing_url = "https://github.com/ASHISHSE/App_test/raw/main/sowing_calendar.xlsx"
        sowing_response = requests.get(sowing_url)
        sowing_df = pd.read_excel(BytesIO(sowing_response.content))
        
        # Extract unique districts, talukas, circles, and crops
        districts = sorted(weather_df['District'].dropna().unique())
        talukas = sorted(weather_df['Taluka'].dropna().unique())
        circles = sorted(weather_df['Circle'].dropna().unique())
        crops = sorted(rules_df['Crop'].dropna().unique())
        
        return weather_df, rules_df, sowing_df, districts, talukas, circles, crops
        
    except Exception as e:
        st.error(f"Error loading data from GitHub: {str(e)}")
        # Return sample data if there's an error
        districts = ['Ahmednagar', 'Pune', 'Nashik']
        talukas = ['Ahmednagar', 'Parner', 'Sangamner']
        circles = ['Bhingar', 'Kapurwadi', 'Savedi']
        crops = ['Paddy', 'Cotton', 'Jowar']
        
        # Create sample weather data
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
        
        # Sample rules data
        rules_data = [
            {'Crop': 'Paddy', 'Growth Stage': 'Planting/Transplanting', 'DAS (Days After Sowing)': '0', 'Ideal Water Required (in mm)': '10 to 30', 'IF Condition': '>=10 & <= 30', 'Farmer Advisory': 'Saturated mud'},
            {'Crop': 'Paddy', 'Growth Stage': 'Planting/Transplanting', 'DAS (Days After Sowing)': '0', 'Ideal Water Required (in mm)': '10 to 30', 'IF Condition': '<10', 'Farmer Advisory': 'Ensure mud is soft. Transplanting in dry mud causes root damage and poor seedling establishment.'},
            {'Crop': 'Paddy', 'Growth Stage': 'Planting/Transplanting', 'DAS (Days After Sowing)': '0', 'Ideal Water Required (in mm)': '10 to 30', 'IF Condition': '>30', 'Farmer Advisory': 'Wait for water to drain. Transplanting in deep water can drown seedlings and cause them to float.'},
            {'Crop': 'Paddy', 'Growth Stage': 'Vegetative (Tillering)', 'DAS (Days After Sowing)': '1 to 50', 'Ideal Water Required (in mm)': '30 to 50', 'IF Condition': '>=30 & <= 50', 'Farmer Advisory': 'Shallow flooding'},
            {'Crop': 'Paddy', 'Growth Stage': 'Vegetative (Tillering)', 'DAS (Days After Sowing)': '1 to 50', 'Ideal Water Required (in mm)': '30 to 50', 'IF Condition': '<30', 'Farmer Advisory': 'Light, frequent irrigation. Stress here reduces the number of tillers, directly impacting yield.'},
            {'Crop': 'Paddy', 'Growth Stage': 'Vegetative (Tillering)', 'DAS (Days After Sowing)': '1 to 50', 'Ideal Water Required (in mm)': '30 to 50', 'IF Condition': '>50', 'Farmer Advisory': 'Drain excess water. Stagnant water can lead to nutrient loss and root rot diseases.'},
            {'Crop': 'Paddy', 'Growth Stage': 'Reproductive (Panicle Init.)', 'DAS (Days After Sowing)': '50 to 65', 'Ideal Water Required (in mm)': '50 to 100', 'IF Condition': '>=50 & <= 100', 'Farmer Advisory': 'Critical Stage. Flooding'}
        ]
        
        rules_df = pd.DataFrame(rules_data)
        
        # Sample sowing calendar data
        sowing_data = [
            {'District': 'Ahmednagar', 'Taluka': 'Ahmednagar', 'Circle': 'Kapurwadi', 'Crop': 'Cotton', 'Ideal Sowing': '2FN June to 1FN July', 'IF condition': '< 2FN June', 'Comments on Sowing': 'Early Sowing due to Rainfall on time / Water source available'},
            {'District': 'Ahmednagar', 'Taluka': 'Ahmednagar', 'Circle': 'Kapurwadi', 'Crop': 'Cotton', 'Ideal Sowing': '2FN June to 1FN July', 'IF condition': '> 1FN July', 'Comments on Sowing': 'Late Sowing due to Rainfall delay /For sowing moisture is not sufficient in soil'}
        ]
        
        sowing_df = pd.DataFrame(sowing_data)
        
        return weather_df, rules_df, sowing_df, districts, talukas, circles, crops

weather_df, rules_df, sowing_df, districts, talukas, circles, crops = load_data()

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
    current_stage = None
    for _, row in rules_df.iterrows():
        if row['Crop'] == crop:
            das_range = str(row['DAS (Days After Sowing)'])
            if '-' in das_range:
                start, end = map(int, das_range.split(' to '))
                if start <= das <= end:
                    current_stage = row
                    break
            elif das_range.isdigit() and int(das_range) == das:
                current_stage = row
                break
    
    if current_stage is None:
        return "No advisory available for this growth stage."
    
    stage_name = current_stage['Growth Stage']
    water_required_range = current_stage['Ideal Water Required (in mm)']
    
    # Parse water requirement range
    if ' to ' in water_required_range:
        try:
            min_water, max_water = map(float, water_required_range.split(' to '))
        except:
            min_water, max_water = 0, 100  # Default values if parsing fails
    else:
        min_water, max_water = 0, 100  # Default values
    
    # Get advisory based on condition
    if condition := current_stage['IF Condition']:
        if condition.startswith('>=') and condition.endswith('<= 30'):
            if min_water <= rainfall_das <= max_water:
                advisory = current_stage['Farmer Advisory']
            elif rainfall_das < min_water:
                # Find the advisory for low water condition
                low_water_adv = rules_df[
                    (rules_df['Crop'] == crop) & 
                    (rules_df['Growth Stage'] == stage_name) & 
                    (rules_df['IF Condition'].str.startswith('<'))
                ]
                advisory = low_water_adv['Farmer Advisory'].values[0] if not low_water_adv.empty else "Irrigation needed."
            else:
                # Find the advisory for high water condition
                high_water_adv = rules_df[
                    (rules_df['Crop'] == crop) & 
                    (rules_df['Growth Stage'] == stage_name) & 
                    (rules_df['IF Condition'].str.startswith('>'))
                ]
                advisory = high_water_adv['Farmer Advisory'].values[0] if not high_water_adv.empty else "Drainage needed."
        else:
            advisory = current_stage['Farmer Advisory']
    else:
        advisory = "No specific advisory available."
    
    return f"Crop is at {stage_name} stage ({das} Days After Sowing). {advisory}"

# Function to get sowing advisory
def get_sowing_advisory(sowing_date, district, taluka, circle, crop, sowing_df):
    sowing_dt = datetime.strptime(sowing_date, '%d-%m-%Y')
    sowing_day = sowing_dt.day
    sowing_month = sowing_dt.month
    
    # Try to find advisory from sowing calendar
    sowing_advisory_data = sowing_df[
        (sowing_df['District'] == district) &
        (sowing_df['Taluka'] == taluka) &
        (sowing_df['Circle'] == circle) &
        (sowing_df['Crop'] == crop)
    ]
    
    if not sowing_advisory_data.empty:
        # For simplicity, use the first matching advisory
        advisory_row = sowing_advisory_data.iloc[0]
        return f"{advisory_row['IF condition']}: {advisory_row['Comments on Sowing']}"
    else:
        # Fallback to general advisory based on day of month
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
            district_talukas = sorted(weather_df[weather_df['District'] == district]['Taluka'].dropna().unique())
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
            taluka_circles = sorted(weather_df[weather_df['Taluka'] == taluka]['Circle'].dropna().unique())
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
                        <p><i class="fas fa-cloud-rain weather-icon"></i>Rainfall (mm)</p>
                """, unsafe_allow_html=True)
                
                st.metric("Last Week", f"{metrics['rainfall_last_week']:.1f}")
                st.metric("Last Month", f"{metrics['rainfall_last_month']:.1f}")
                st.metric("Since Sowing", f"{metrics['rainfall_das']:.1f}")
                st.markdown("</div>", unsafe_allow_html=True)
            
            with col2:
                st.markdown("""
                    <div class="weather-info">
                        <p><i class="fas fa-temperature-high weather-icon"></i>Temperature (°C)</p>
                """, unsafe_allow_html=True)
                
                st.metric("Max Average", f"{metrics['tmax_avg']:.1f}")
                st.metric("Min Average", f"{metrics['tmin_avg']:.1f}")
                st.markdown("</div>", unsafe_allow_html=True)
            
            with col3:
                st.markdown("""
                    <div class="weather-info">
                        <p><i class="fas fa-tint weather-icon"></i>Humidity (%)</p>
                """, unsafe_allow_html=True)
                
                st.metric("Max Average", f"{metrics['max_rh_avg']:.1f}")
                st.metric("Min Average", f"{metrics['min_rh_avg']:.1f}")
                st.markdown("</div>", unsafe_allow_html=True)
            
            # Display advisory results
            st.markdown("---")
            st.markdown("## 📋 Advisory Results")
            
            # Sowing advisory
            sowing_advisory = get_sowing_advisory(sowing_date_str, district, taluka, circle, crop, sowing_df)
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
