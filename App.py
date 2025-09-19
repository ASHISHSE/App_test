import streamlit as st
import pandas as pd
from datetime import datetime

# Load CSV data
@st.cache_data
def load_data():
    weather = pd.read_excel("weather.xlsx")  # Use relative paths for deployment
    rules = pd.read_excel("rules.xlsx")
    sowing_calendar = pd.read_excel("sowing_calendar.xlsx")
    return weather, rules, sowing_calendar

weather, rules, sowing_calendar = load_data()

st.title("🌱 Crop Advisory System")

# Location Selection
districts = sorted(weather["District"].unique())
selected_district = st.selectbox("Select District", ["All"] + districts)

if selected_district != "All":
    talukas = sorted(weather[weather["District"] == selected_district]["Taluka"].unique())
else:
    talukas = sorted(weather["Taluka"].unique())
selected_taluka = st.selectbox("Select Taluka", ["All"] + talukas)

if selected_taluka != "All":
    circles = sorted(weather[weather["Taluka"] == selected_taluka]["Circle"].unique())
else:
    circles = sorted(weather["Circle"].unique())
selected_circle = st.selectbox("Select Circle", ["All"] + circles)

# Crop & Date Selection
crops = sorted(sowing_calendar["Crop"].unique())
selected_crop = st.selectbox("Select Crop", crops)

sowing_date = st.date_input("Select Sowing Date")
current_date = st.date_input("Select Current Date", datetime.today())

if sowing_date and current_date:
    DAS = (current_date - sowing_date).days
    st.markdown(f"**Days After Sowing (DAS):** {DAS}")

    # Filter Weather Data
    filtered_weather = weather.copy()
    if selected_district != "All":
        filtered_weather = filtered_weather[filtered_weather["District"] == selected_district]
    if selected_taluka != "All":
        filtered_weather = filtered_weather[filtered_weather["Taluka"] == selected_taluka]
    if selected_circle != "All":
        filtered_weather = filtered_weather[filtered_weather["Circle"] == selected_circle]

    # Filter by DAS window
    filtered_weather["Date(DDMMYY)"] = pd.to_datetime(
        filtered_weather["Date(DDMMYY)"], dayfirst=True, errors="coerce"
    )
    filtered_weather = filtered_weather[(filtered_weather["Date(DDMMYY)"] >= pd.Timestamp(sowing_date)) &
                                       (filtered_weather["Date(DDMMYY)"] <= pd.Timestamp(current_date))]

    if not filtered_weather.empty:
        cum_rainfall = filtered_weather["Rainfall"].sum()
        avg_temp = filtered_weather[["Tmax", "Tmin"]].mean().mean()
        avg_humidity = filtered_weather[["max_Rh", "min_Rh"]].mean().mean()

        st.subheader("🌦 Weather Summary")
        st.write(f"**Cumulative Rainfall:** {cum_rainfall:.2f} mm")
        st.write(f"**Average Temperature:** {avg_temp:.2f} °C")
        st.write(f"**Average Humidity:** {avg_humidity:.2f} %")

        # Determine Growth Stage
        growth_stage = rules[(rules["Crop"] == selected_crop) &
                             (rules["DAS_Min"] <= DAS) & (rules["DAS_Max"] >= DAS)]

        if not growth_stage.empty:
            stage = growth_stage.iloc[0]["Growth_Stage"]
            water_req_min = growth_stage.iloc[0]["Ideal_Water_Min"]
            water_req_max = growth_stage.iloc[0]["Ideal_Water_Max"]
            advisory = growth_stage.iloc[0]["Advisory"]

            st.subheader("🌾 Growth Stage & Advisory")
            st.write(f"**Growth Stage:** {stage}")
            st.write(f"**Ideal Water Requirement:** {water_req_min}-{water_req_max} mm")
            st.write(f"**Cumulative Rainfall vs Requirement:** {cum_rainfall:.2f} mm")

            if cum_rainfall < water_req_min:
                st.warning("⚠ Water Deficit: Consider irrigation.")
            elif cum_rainfall > water_req_max:
                st.warning("⚠ Excess Rainfall: Watch for waterlogging.")
            else:
                st.success("✅ Rainfall is within ideal range.")

            st.info(f"**Advisory:** {advisory}")

        else:
            st.error("No matching growth stage found for this DAS.")

        # Sowing Calendar Check
        crop_calendar = sowing_calendar[sowing_calendar["Crop"] == selected_crop]
        if not crop_calendar.empty:
            st.subheader("📅 Sowing Window Check")
            start_date = pd.to_datetime(crop_calendar.iloc[0]["Start"], dayfirst=True, errors="coerce")
            end_date = pd.to_datetime(crop_calendar.iloc[0]["End"], dayfirst=True, errors="coerce")
            if pd.notnull(start_date) and pd.notnull(end_date):
                if sowing_date < start_date:
                    st.warning("⚠ Early Sowing: This is before the recommended period.")
                elif sowing_date > end_date:
                    st.warning("⚠ Late Sowing: This is after the recommended period.")
                else:
                    st.success("✅ Sowing date is within the ideal period.")
            else:
                st.info("No sowing period data available for this crop.")

    else:
        st.error("No weather data available for selected filters and dates.")


