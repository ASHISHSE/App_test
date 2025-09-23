import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from calendar import monthrange
import re

# ------------------- DATA LOADING -------------------

@st.cache_data
def load_data():
    weather_url = "https://github.com/ASHISHSE/App_test/raw/main/weather.xlsx"
    rules_url = "https://github.com/ASHISHSE/App_test/raw/main/rules.xlsx"
    sowing_url = "https://github.com/ASHISHSE/App_test/raw/main/sowing_calendar.xlsx"

    weather_df = pd.read_excel(weather_url)
    rules_df = pd.read_excel(rules_url)
    sowing_df = pd.read_excel(sowing_url)

    # Ensure date column exists & convert
    if "DD-MM-YYYY" not in weather_df.columns:
        raise ValueError("weather.xlsx must have a column 'DD-MM-YYYY'")
    weather_df["Date_dt"] = pd.to_datetime(weather_df["DD-MM-YYYY"], format="%d-%m-%Y", errors="coerce")

    return weather_df, rules_df, sowing_df

weather_df, rules_df, sowing_df = load_data()

# ------------------- UTILITY FUNCTIONS -------------------

def parse_fn_date(year, fn_str):
    """Convert '1FN June' or '2FN July' to start/end datetime objects."""
    parts = fn_str.strip().split()
    if len(parts) != 2:
        return None, None
    fn, month_name = parts
    month = datetime.strptime(month_name, "%B").month
    if fn.upper() == "1FN":
        start = datetime(year, month, 1)
        end = datetime(year, month, 15)
    else:
        days_in_month = monthrange(year, month)[1]
        start = datetime(year, month, 16)
        end = datetime(year, month, days_in_month)
    return start, end

def match_condition(sowing_date, cond_str):
    """Fallback: Match sowing_date against FN-based IF condition (<, >, to)."""
    cond_str = str(cond_str).strip()
    year = sowing_date.year
    try:
        if "to" in cond_str:
            parts = cond_str.split("to")
            start_str, end_str = parts[0].strip(), parts[1].strip()
            start_date, _ = parse_fn_date(year, start_str)
            _, end_date = parse_fn_date(year, end_str)
            if start_date and end_date:
                return start_date <= sowing_date <= end_date
        elif cond_str.startswith("<"):
            ref_str = cond_str.replace("<", "").strip()
            _, end_date = parse_fn_date(year, ref_str)
            if end_date:
                return sowing_date < end_date + timedelta(days=1)
        elif cond_str.startswith(">"):
            ref_str = cond_str.replace(">", "").strip()
            _, end_date = parse_fn_date(year, ref_str)
            if end_date:
                return sowing_date > end_date
    except:
        return False
    return False

def parse_condition_with_dates(cond_str):
    """Extract start/end date from explicit range in parentheses."""
    date_range_match = re.search(r"\((\d{2}-\d{2}-\d{4})\s+to\s+(\d{2}-\d{2}-\d{4})\)", cond_str)
    if date_range_match:
        start = datetime.strptime(date_range_match.group(1), "%d-%m-%Y")
        end = datetime.strptime(date_range_match.group(2), "%d-%m-%Y")
        return start, end
    return None, None

def match_condition_with_dates(sowing_date, cond_str):
    start_date, end_date = parse_condition_with_dates(cond_str)
    if start_date and end_date:
        return start_date <= sowing_date <= end_date
    return False

def get_sowing_comments(sowing_date_str, district, taluka, circle, crop, sowing_df):
    if sowing_df.empty:
        return []
    sowing_dt = datetime.strptime(sowing_date_str, "%d/%m/%Y")
    results = []

    # Hierarchical filtering
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
                if match_condition_with_dates(sowing_dt, cond):
                    results.append(f"{cond}: {row.get('Comments on Sowing', '')}")
                elif match_condition(sowing_dt, cond):
                    results.append(f"{cond}: {row.get('Comments on Sowing', '')}")
            if results:
                break
    return results

# ------------------- STREAMLIT APP -------------------

st.title("🌱 Crop Advisory System")
st.write("Select a location and crop, enter sowing & current dates, and click Generate Advisory.")

# Location selectors
col1, col2, col3, col4 = st.columns(4)
with col1:
    district = st.selectbox("District", weather_df["District"].unique())
with col2:
    taluka = st.selectbox("Taluka", weather_df[weather_df["District"] == district]["Taluka"].unique())
with col3:
    circle = st.selectbox("Circle", weather_df[(weather_df["District"] == district) & (weather_df["Taluka"] == taluka)]["Circle"].unique())
with col4:
    crop = st.selectbox("Crop", sowing_df["Crop"].unique())

sowing_date_str = st.date_input("Sowing Date").strftime("%d/%m/%Y")
current_date_str = st.date_input("Current Date").strftime("%d/%m/%Y")

if st.button("Generate Advisory"):
    sowing_date = datetime.strptime(sowing_date_str, "%d/%m/%Y")
    current_date = datetime.strptime(current_date_str, "%d/%m/%Y")
    df = weather_df[
        (weather_df["District"] == district) &
        (weather_df["Taluka"] == taluka) &
        (weather_df["Circle"] == circle)
    ]

    mask = (df["Date_dt"] >= sowing_date) & (df["Date_dt"] <= current_date)
    das_data = df.loc[mask]

    # --------- WEATHER METRICS ----------
    st.subheader("📊 Weather Metrics")
    st.metric("Rainfall Since Sowing (mm)", round(das_data["Rainfall"].sum(), 1))
    st.metric("Tmax Avg (°C)", round(das_data["Tmax"].mean(), 1))
    st.metric("Tmin Avg (°C)", round(das_data["Tmin"].mean(), 1))
    st.metric("Max RH Avg (%)", round(das_data["max_Rh"].mean(), 1))
    st.metric("Min RH Avg (%)", round(das_data["min_Rh"].mean(), 1))

    # --------- RAINY DAYS TAB ----------
    st.markdown("---")
    st.subheader("🌧 Rainy Days (Highlighted)")
    if not das_data.empty:
        display_df = das_data.copy().sort_values("Date_dt")
        display_df["Date"] = display_df["Date_dt"].dt.strftime("%d-%m-%Y")
        columns_to_show = ["Date", "Rainfall", "Tmax", "Tmin", "max_Rh", "min_Rh"]
        display_df = display_df[[c for c in columns_to_show if c in display_df.columns]]

        def highlight_rainy_days(row):
            return [
                "background-color: #0ea6ff; font-weight: bold;" if (col == "Rainfall" and row["Rainfall"] > 0)
                else "background-color: #0ea6ff;" if row["Rainfall"] > 0
                else ""
                for col in row.index
            ]
        st.dataframe(display_df.style.apply(highlight_rainy_days, axis=1), use_container_width=True)
    else:
        st.info("No data for selected date range.")

    # --------- COMMENT ON SOWING ----------
    st.markdown("---")
    st.subheader("💬 Comment on Sowing")
    comments = get_sowing_comments(sowing_date_str, district, taluka, circle, crop, sowing_df)
    if comments:
        for c in comments:
            st.success(c)
    else:
        st.warning("No matching comment found for this sowing date.")

    # --------- GROWTH STAGE ADVISORY ----------
    st.markdown("---")
    st.subheader("🌱 Growth Stage Advisory")
    das = (current_date - sowing_date).days
    st.metric("DAS", das)
    stage_row = rules_df[(rules_df["DAS (Days After Sowing) Start"] <= das) & (rules_df["DAS (Days After Sowing) End"] >= das)]
    if not stage_row.empty:
        st.write(f"**Growth Stage:** {stage_row.iloc[0]['Growth Stage']}")
        st.write(f"**Ideal Water Required (mm):** {stage_row.iloc[0]['Ideal Water Required (in mm)']}")
        st.info(f"👨‍🌾 Farmer Advisory: {stage_row.iloc[0]['Farmer Advisory']}")
    else:
        st.warning("No matching growth stage found for this DAS.")
