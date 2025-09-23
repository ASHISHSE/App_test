import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# ---------------------------
# Load Data
# ---------------------------
@st.cache_data
def load_data():
    try:
        weather_df = pd.read_excel("weather.xlsx")
        weather_df["Date_dt"] = pd.to_datetime(weather_df["DD-MM-YYYY"], format="%d-%m-%Y", errors="coerce")
    except Exception as e:
        st.error(f"❌ Error loading weather.xlsx: {e}")
        return None, None, None

    try:
        rules_df = pd.read_excel("rules.xlsx")
        if "Crop" in rules_df.columns:
            rules_df["Crop"] = rules_df["Crop"].astype(str).str.strip()
    except Exception as e:
        st.error(f"❌ Error loading rules.xlsx: {e}")
        return weather_df, None, None

    try:
        sowing_calendar_df = pd.read_excel("sowing_calendar.xlsx")
        if "Crop" in sowing_calendar_df.columns:
            sowing_calendar_df["Crop"] = sowing_calendar_df["Crop"].astype(str).str.strip()
        if "IF condition" in sowing_calendar_df.columns:
            sowing_calendar_df["IF condition"] = sowing_calendar_df["IF condition"].astype(str).str.strip()
    except Exception as e:
        st.error(f"❌ Error loading sowing_calendar.xlsx: {e}")
        return weather_df, rules_df, None

    return weather_df, rules_df, sowing_calendar_df


# ---------------------------
# Helper Functions
# ---------------------------
def get_filtered_weather(weather_df, level, level_name):
    """Filter weather data based on District/Taluka/Circle level selection"""
    if level == "Circle":
        return weather_df[weather_df["Circle"] == level_name]
    elif level == "Taluka":
        return weather_df[weather_df["Taluka"] == level_name]
    else:
        return weather_df[weather_df["District"] == level_name]


def calculate_metrics(filtered_df, sowing_date, current_date):
    """Calculate rainfall metrics, averages, and DAS"""
    das_df = filtered_df[(filtered_df["Date_dt"] >= sowing_date) & (filtered_df["Date_dt"] <= current_date)]

    # Rainfall metrics
    rainfall_since_sowing = das_df["Rainfall"].sum()
    rainfall_last_week = filtered_df[
        (filtered_df["Date_dt"] >= current_date - timedelta(days=6)) & (filtered_df["Date_dt"] <= current_date)
    ]["Rainfall"].sum()
    rainfall_last_month = filtered_df[
        (filtered_df["Date_dt"] >= current_date - timedelta(days=29)) & (filtered_df["Date_dt"] <= current_date)
    ]["Rainfall"].sum()

    # Temperature & RH averages
    tmax_avg = das_df["Tmax"].mean()
    tmin_avg = das_df["Tmin"].mean()
    max_rh_avg = das_df["max_Rh"].mean()
    min_rh_avg = das_df["min_Rh"].mean()

    # DAS (Days After Sowing)
    das = (current_date - sowing_date).days

    return {
        "rainfall_since_sowing": rainfall_since_sowing,
        "rainfall_last_week": rainfall_last_week,
        "rainfall_last_month": rainfall_last_month,
        "tmax_avg": tmax_avg,
        "tmin_avg": tmin_avg,
        "max_rh_avg": max_rh_avg,
        "min_rh_avg": min_rh_avg,
        "das": das,
    }


def get_growth_stage(rules_df, selected_crop, das):
    if rules_df is None:
        return None, None, None
    df_crop = rules_df[rules_df["Crop"].str.lower() == selected_crop.lower()]
    stage_row = df_crop[df_crop["DAS (Days After Sowing)"].apply(lambda x: das in range(int(x.split("-")[0]), int(x.split("-")[1])+1))]

    if not stage_row.empty:
        stage = stage_row.iloc[0]["Growth Stage"]
        ideal_water = stage_row.iloc[0]["Ideal Water Required (in mm)"]
        advisory = stage_row.iloc[0]["Farmer Advisory"]
        return stage, ideal_water, advisory
    return None, None, None


def get_sowing_comment(sowing_calendar_df, selected_crop, sowing_date):
    if sowing_calendar_df is None:
        return None, None
    fn = "1FN" if sowing_date.day <= 15 else "2FN"
    comment_row = sowing_calendar_df[
        (sowing_calendar_df["Crop"].str.lower() == selected_crop.lower()) &
        (sowing_calendar_df["IF condition"].str.upper() == fn)
    ]
    if not comment_row.empty:
        return comment_row.iloc[0]["Comments on Sowing"], fn
    return None, fn


# ---------------------------
# Streamlit App
# ---------------------------
st.title("🌱 Crop Advisory System")
st.write("Select a level (District/Taluka/Circle), crop, sowing & current dates, and click Generate Advisory.")

weather_df, rules_df, sowing_calendar_df = load_data()

if weather_df is not None:
    level = st.selectbox("Select Level", ["District", "Taluka", "Circle"])
    level_name = st.selectbox(f"Select {level}", sorted(weather_df[level].dropna().unique()))
    selected_crop = st.selectbox("Select Crop", sorted(weather_df["Crop"].dropna().unique()))
    sowing_date_str = st.date_input("Sowing Date").strftime("%d/%m/%Y")
    current_date_str = st.date_input("Current Date", value=datetime.today()).strftime("%d/%m/%Y")

    if st.button("Generate Advisory"):
        sowing_date = datetime.strptime(sowing_date_str, "%d/%m/%Y")
        current_date = datetime.strptime(current_date_str, "%d/%m/%Y")
        filtered_df = get_filtered_weather(weather_df, level, level_name)
        metrics = calculate_metrics(filtered_df, sowing_date, current_date)

        tabs = st.tabs([
            "Rainfall Since Sowing/DAS (mm)",
            "Rainfall - Last Month (mm)",
            "Rainfall - Last Week (mm)",
            "Tmax/Tmin/RH Averages",
            "Growth Stage Advisory",
            "Comment on Sowing",
            "Rainy Days",
            "Daily Weather Data"
        ])

        with tabs[0]:
            st.metric("Rainfall Since Sowing (mm)", f"{metrics['rainfall_since_sowing']:.1f}")

        with tabs[1]:
            st.metric("Rainfall Last Month (mm)", f"{metrics['rainfall_last_month']:.1f}")

        with tabs[2]:
            st.metric("Rainfall Last Week (mm)", f"{metrics['rainfall_last_week']:.1f}")

        with tabs[3]:
            st.metric("Tmax Avg (°C)", f"{metrics['tmax_avg']:.1f}")
            st.metric("Tmin Avg (°C)", f"{metrics['tmin_avg']:.1f}")
            st.metric("Max RH Avg (%)", f"{metrics['max_rh_avg']:.1f}")
            st.metric("Min RH Avg (%)", f"{metrics['min_rh_avg']:.1f}")

        with tabs[4]:
            stage, ideal_water, advisory = get_growth_stage(rules_df, selected_crop, metrics["das"])
            st.metric("DAS", metrics["das"])
            if stage:
                st.write(f"**Growth Stage:** {stage}")
                st.write(f"**Ideal Water Required (mm):** {ideal_water}")
                st.info(f"**Farmer Advisory:** {advisory}")
            else:
                st.warning("No matching growth stage found for this DAS.")

        with tabs[5]:
            comment, fn = get_sowing_comment(sowing_calendar_df, selected_crop, sowing_date)
            if comment:
                st.success(f"FN: **{fn}** → {comment}")
            else:
                st.warning(f"No sowing comment found for FN: {fn}")

        with tabs[6]:
            # Rainy Days Count
            rainy_das = (filtered_df[(filtered_df["Date_dt"] >= sowing_date) & (filtered_df["Date_dt"] <= current_date)]["Rainfall"] > 0).sum()
            rainy_week = (filtered_df[(filtered_df["Date_dt"] >= current_date - timedelta(days=6)) & (filtered_df["Date_dt"] <= current_date)]["Rainfall"] > 0).sum()
            rainy_month = (filtered_df[(filtered_df["Date_dt"] >= current_date - timedelta(days=29)) & (filtered_df["Date_dt"] <= current_date)]["Rainfall"] > 0).sum()

            st.metric("Rainy Days (Since Sowing)", rainy_das)
            st.metric("Rainy Days (Last Week)", rainy_week)
            st.metric("Rainy Days (Last Month)", rainy_month)

        with tabs[7]:
            st.subheader("📅 Daily Weather Data (Highlighted Rainy Days)")
            display_df = filtered_df[(filtered_df["Date_dt"] >= sowing_date) & (filtered_df["Date_dt"] <= current_date)]
            if not display_df.empty:
                display_df = display_df.sort_values("Date_dt")
                display_df["Date"] = display_df["Date_dt"].dt.strftime("%d-%m-%Y")
                columns_to_show = ["Date", "Rainfall", "Tmax", "Tmin", "max_Rh", "min_Rh"]
                display_df = display_df[columns_to_show]

                def highlight_rainy_days(row):
                    color = "background-color: #d0f0c0;" if row["Rainfall"] > 0 else ""
                    return [color] * len(row)

                st.dataframe(display_df.style.apply(highlight_rainy_days, axis=1), use_container_width=True)
            else:
                st.info("No weather data available for selected range.")
