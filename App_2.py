import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
import urllib.parse
from io import BytesIO

# Set page configuration
st.set_page_config(
    page_title="Crop Advisory System",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load data from Excel files (assuming they're in the same directory)
@st.cache_data
def load_data():
    # In a real implementation, you would load from Excel files
    # For example:
    # districts_df = pd.read_excel('data/districts.xlsx')
    # crops_df = pd.read_excel('data/crops.xlsx')
    # weather_df = pd.read_excel('data/weather.xlsx')
    
    # For demonstration, we'll create sample data
    districts = [
        'Ahmednagar', 'Pune', 'Nashik', 'Kolhapur', 'Satara', 
        'Sangli', 'Jalgaon', 'Dhule', 'Nandurbar', 'Jalna',
        'Aurangabad', 'Beed', 'Latur', 'Osmanabad', 'Nanded',
        'Parbhani', 'Hingoli', 'Buldhana', 'Akola', 'Amravati',
        'Wardha', 'Nagpur', 'Bhandara', 'Gondia', 'Gadchiroli',
        'Chandrapur', 'Yavatmal', 'Washim', 'Thane', 'Palanpur',
        'Raigad', 'Ratnagiri', 'Sindhudurg'
    ]
    
    crops = ['Paddy', 'Cotton', 'Jowar', 'Maize', 'Onion', 'Soybean', 'Tur', 'Wheat', 'Sugarcane', 'Groundnut']
    
    # Sample talukas and circles data structure
    talukas_data = {
        'Ahmednagar': ['Ahmednagar', 'Parner', 'Sangamner', 'Karjat', 'Shrirampur', 'Rahata', 'Kopargaon', 'Akole', 'Nevasa', 'Shevgaon'],
        'Pune': ['Pune City', 'Haveli', 'Mulshi', 'Baramati', 'Indapur', 'Daund', 'Purandar', 'Velhe', 'Bhor', 'Junnar'],
        'Default': ['Taluka 1', 'Taluka 2', 'Taluka 3', 'Taluka 4', 'Taluka 5']
    }
    
    circles_data = {
        'Ahmednagar': ['Kapurwadi', 'Bhingar', 'Nagar', 'Savedi', 'Wadala', 'Shani Mandir', 'Kedgaon', 'Sambhapur', 'Pimpalgaon', 'Gholegaon'],
        'Pune City': ['Shivajinagar', 'Kothrud', 'Hadapsar', 'Viman Nagar', 'Aundh', 'Baner', 'Kharadi', 'Kondhwa', 'Katraj', 'Sinhagad Road'],
        'Default': ['Circle 1', 'Circle 2', 'Circle 3', 'Circle 4', 'Circle 5']
    }
    
    return districts, crops, talukas_data, circles_data

# Load data
districts, crops, talukas_data, circles_data = load_data()

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
    .advisory-result {
        background-color: #e8f4f8;
        border-left: 4px solid #3498db;
        padding: 20px;
        border-radius: 8px;
        margin-bottom: 20px;
    }
    .weather-info {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
    }
    .location-hierarchy {
        background-color: #e8f4f8;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 20px;
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

# Initialize session state for form values
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

# Location hierarchy display
st.markdown("""
    <div class="location-hierarchy">
        <h5><i class="fas fa-map-marker-alt me-2"></i>Selected Location</h5>
        <div class="d-flex flex-wrap gap-2 mt-2">
            <span class="hierarchy-item">District: <span id="selectedDistrict" class="badge bg-primary">Not selected</span></span>
            <span class="hierarchy-item">Taluka: <span id="selectedTaluka" class="badge bg-secondary">Not selected</span></span>
            <span class="hierarchy-item">Circle: <span id="selectedCircle" class="badge bg-info">Not selected</span></span>
        </div>
    </div>
""", unsafe_allow_html=True)

# Create form for user input
with st.form("crop_advisory_form"):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Location Information")
        district = st.selectbox("District *", options=[""] + districts, key="district_select")
        
        # Update taluka options based on district selection
        taluka_options = [""]
        if district in talukas_data:
            taluka_options.extend(talukas_data[district])
        else:
            taluka_options.extend(talukas_data['Default'])
            
        taluka = st.selectbox("Taluka", options=taluka_options, key="taluka_select", disabled=not district)
        
        # Update circle options based on taluka selection
        circle_options = [""]
        if taluka in circles_data:
            circle_options.extend(circles_data[taluka])
        else:
            circle_options.extend(circles_data['Default'])
            
        circle = st.selectbox("Circle", options=circle_options, key="circle_select", disabled=not taluka)
    
    with col2:
        st.subheader("Crop Information")
        crop = st.selectbox("Crop Name *", options=[""] + crops, key="crop_select")
        sowing_date = st.date_input("Sowing Date *", key="sowing_date_input")
    
    with col3:
        st.subheader("Date Information")
        current_date = st.date_input("Current Date *", value=date.today(), key="current_date_input")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.form_submit_button("📅 Set to Today", key="today_btn"):
            current_date = date.today()
            st.session_state.current_date = current_date
            st.experimental_rerun()
    
    # Generate advisory button
    generate_btn = st.form_submit_button("🌱 Generate Advisory", use_container_width=True)

# Update location hierarchy display
district_display = district if district else "Not selected"
taluka_display = taluka if taluka else "Not selected"
circle_display = circle if circle else "Not selected"

st.markdown(f"""
    <script>
        document.getElementById('selectedDistrict').textContent = '{district_display}';
        document.getElementById('selectedTaluka').textContent = '{taluka_display}';
        document.getElementById('selectedCircle').textContent = '{circle_display}';
    </script>
""", unsafe_allow_html=True)

# Process form submission
if generate_btn:
    # Validate inputs
    if not district or not crop or not sowing_date or not current_date:
        st.error("Please fill all required fields: District, Crop, Sowing Date, and Current Date.")
    else:
        # Calculate DAS (Days After Sowing)
        das = (current_date - sowing_date).days
        
        if das < 0:
            st.error("Sowing date cannot be in the future compared to current date.")
        else:
            # Generate weather information
            st.subheader("🌤️ Weather Information")
            st.info(f"Weather data for {district}{f', {taluka}' if taluka else ''}{f', {circle}' if circle else ''} from {sowing_date} to {current_date} ({das} days)")
            
            # Simulated weather data
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("""
                    <div class="weather-info text-center">
                        <p><i class="fas fa-cloud-rain weather-icon"></i>Rainfall</p>
                """, unsafe_allow_html=True)
                
                rainfall_last_week = (das * 0.7 + np.random.random() * 10)
                rainfall_last_month = (das * 2.5 + np.random.random() * 20)
                rainfall_das = (das * 1.2 + np.random.random() * 15)
                
                st.metric("Last Week", f"{rainfall_last_week:.1f} mm")
                st.metric("Last Month", f"{rainfall_last_month:.1f} mm")
                st.metric("Since Sowing", f"{rainfall_das:.1f} mm")
                st.markdown("</div>", unsafe_allow_html=True)
            
            with col2:
                st.markdown("""
                    <div class="weather-info text-center">
                        <p><i class="fas fa-temperature-high weather-icon"></i>Temperature</p>
                """, unsafe_allow_html=True)
                
                tmax_avg = (30 + np.random.random() * 10)
                tmin_avg = (20 + np.random.random() * 5)
                
                st.metric("Max", f"{tmax_avg:.1f} °C")
                st.metric("Min", f"{tmin_avg:.1f} °C")
                st.markdown("</div>", unsafe_allow_html=True)
            
            with col3:
                st.markdown("""
                    <div class="weather-info text-center">
                        <p><i class="fas fa-tint weather-icon"></i>Humidity</p>
                """, unsafe_allow_html=True)
                
                max_rh_avg = (70 + np.random.random() * 20)
                min_rh_avg = (40 + np.random.random() * 30)
                
                st.metric("Max", f"{max_rh_avg:.1f}%")
                st.metric("Min", f"{min_rh_avg:.1f}%")
                st.markdown("</div>", unsafe_allow_html=True)
            
            # Detailed weather table
            st.subheader("Detailed Weather Metrics")
            weather_data = {
                "Metric": ["Rainfall (mm)", "Max Temperature (°C)", "Min Temperature (°C)", "Max Humidity (%)", "Min Humidity (%)"],
                "Last Week": [
                    f"{rainfall_last_week:.1f}",
                    f"{(tmax_avg - 2):.1f}",
                    f"{(tmin_avg - 1):.1f}",
                    f"{(max_rh_avg - 5):.1f}",
                    f"{(min_rh_avg - 3):.1f}"
                ],
                "Last Month": [
                    f"{rainfall_last_month:.1f}",
                    f"{tmax_avg:.1f}",
                    f"{tmin_avg:.1f}",
                    f"{max_rh_avg:.1f}",
                    f"{min_rh_avg:.1f}"
                ],
                "Since Sowing": [
                    f"{rainfall_das:.1f}",
                    f"{(tmax_avg - 1):.1f}",
                    f"{(tmin_avg + 0.5):.1f}",
                    f"{(max_rh_avg + 2):.1f}",
                    f"{(min_rh_avg + 1):.1f}"
                ]
            }
            
            st.table(pd.DataFrame(weather_data))
            
            # Generate advisory
            st.subheader("📋 Advisory Results")
            st.success(f"Advisory generated for {crop} in {district}{f', {taluka}' if taluka else ''}{f', {circle}' if circle else ''}")
            
            # Sowing advisory based on month
            sowing_month = sowing_date.month
            sowing_day = sowing_date.day
            
            sowing_advisory = ''
            if sowing_month == 6:
                if sowing_day <= 15:
                    sowing_advisory = 'Early sowing due to rainfall on time / Water source available'
                else:
                    sowing_advisory = 'Ideal sowing period'
            elif sowing_month < 6:
                sowing_advisory = 'Very early sowing. Risk of unfavorable conditions.'
            elif sowing_month == 7:
                if sowing_day <= 15:
                    sowing_advisory = 'Ideal sowing period'
                else:
                    sowing_advisory = 'Late sowing due to rainfall delay / Moisture not sufficient in soil'
            else:
                sowing_advisory = 'Late sowing. Consider short duration varieties.'
            
            st.markdown(f"""
                <div class="advisory-result mb-4">
                    <h5><i class="fas fa-calendar-check me-2"></i>Sowing Advisory</h5>
                    <p id="sowingAdvisory" class="mb-0">{sowing_advisory}</p>
                </div>
            """, unsafe_allow_html=True)
            
            # Growth stage advisory based on DAS
            growth_stage = ''
            growth_advisory = ''
            
            if das == 0:
                growth_stage = 'Planting/Transplanting'
                growth_advisory = 'Ensure proper soil moisture for transplantation.'
            elif das > 0 and das <= 50:
                growth_stage = 'Vegetative (Tillering)'
                growth_advisory = 'Maintain shallow flooding. Monitor for nutrient deficiencies.'
            elif das > 50 and das <= 65:
                growth_stage = 'Reproductive (Panicle Initiation)'
                growth_advisory = 'Critical stage for water management. Avoid water stress.'
            elif das > 65 and das <= 90:
                growth_stage = 'Flowering'
                growth_advisory = 'Ensure adequate water supply for proper pollination.'
            elif das > 90 and das <= 115:
                growth_stage = 'Grain Filling/Maturation'
                growth_advisory = 'Gradual drying recommended. Avoid waterlogging.'
            else:
                growth_stage = 'Harvest'
                growth_advisory = 'Field should be dry for harvest operations.'
            
            st.markdown(f"""
                <div class="advisory-result">
                    <h5><i class="fas fa-seedling me-2"></i>Growth Stage Advisory</h5>
                    <p id="growthAdvisory" class="mb-0">Crop is at {growth_stage} stage ({das} Days After Sowing). {growth_advisory}</p>
                </div>
            """, unsafe_allow_html=True)
            
            # Share functionality
            st.subheader("📤 Share Advisory")
            st.write("Share this advisory with others via this link:")
            
            # Generate shareable link
            params = {
                "district": district,
                "taluka": taluka or "",
                "circle": circle or "",
                "crop": crop,
                "sowing": sowing_date.strftime("%Y-%m-%d"),
                "current": current_date.strftime("%Y-%m-%d")
            }
            
            query_string = urllib.parse.urlencode(params)
            shareable_link = f"{st.experimental_get_query_params().get('_url', [''])[0]}?{query_string}"
            
            st.code(shareable_link, language=None)
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("📋 Copy Link", use_container_width=True):
                    st.write("Link copied to clipboard!")  # In a real app, you'd use pyperclip or similar
            
            with col2:
                # WhatsApp share
                whatsapp_text = f"Check out this crop advisory for {crop} in {district}{f', {taluka}' if taluka else ''}{f', {circle}' if circle else ''}"
                whatsapp_url = f"https://wa.me/?text={urllib.parse.quote(whatsapp_text + ': ' + shareable_link)}"
                st.markdown(f'<a href="{whatsapp_url}" target="_blank"><button style="width:100%">📱 Share via WhatsApp</button></a>', unsafe_allow_html=True)
            
            with col3:
                # Email share
                subject = f"Crop Advisory for {crop} in {district}"
                body = f"Hello,\n\nI wanted to share this crop advisory with you:\n\nCrop: {crop}\nDistrict: {district}\nTaluka: {taluka or 'Not specified'}\nCircle: {circle or 'Not specified'}\nSowing Date: {sowing_date}\n\nLink: {shareable_link}\n\nBest regards."
                mailto_url = f"mailto:?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
                st.markdown(f'<a href="{mailto_url}"><button style="width:100%">📧 Share via Email</button></a>', unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown("<p style='text-align: center; color: #7f8c8d;'>Crop Advisory System © 2023. Designed for agricultural extension services.</p>", unsafe_allow_html=True)