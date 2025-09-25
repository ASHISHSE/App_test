import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime, date, timedelta
import requests
from io import BytesIO
import plotly.graph_objects as go

st.set_page_config(page_title="🌱 Crop Advisory System", page_icon="🌱", layout="wide")

# -----------------------------
# LOAD DATA
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

weather_df, rules_df, sowing_df, districts, talukas, circles, crops = load_data()

@st.cache_data
def load_circlewise_data():
    url = "https://github.com/ASHISHSE/App_test/raw/main/Circlewise_Data_Matrix_Indicator_2024_v1.xlsx"
    return pd.read_excel(url)

circlewise_df = load_circlewise_data()

# -----------------------------
# FUNCTIONS
# -----------------------------
def get_circlewise_data(district, taluka, circle, sowing_date, current_date):
    df = circlewise_df.copy()
    df = df[(df["District"] == district) & (df["Taluka"] == taluka)]
    if circle and "Circle" in df.columns:
        df = df[df["Circle"] == circle]
    if df.empty:
        return pd.DataFrame()

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

    selected_cols = ["District", "Taluka", "Circle"]
    for col in df.columns:
        col_lower = str(col).lower()
        if col in selected_cols:
            continue
        for month in months:
            if month.lower() in col_lower and "2024" in col_lower:
                selected_cols.append(col)
                break

    if len(selected_cols) <= 3:
        return pd.DataFrame()
    return df[selected_cols]

def create_monthly_analysis(matrix_data):
    if matrix_data.empty:
        return None
    monthly_data = []
    months = set()
    for col in matrix_data.columns:
        for m in ['January','February','March','April','May','June','July','August','September','October','November','December']:
            if m in col:
                months.add(m)
    months = sorted(months, key=lambda x: datetime.strptime(x, "%B"))

    for month in months:
        month_data = {
            'Month': month,
            'NDVI_Value': None, 'NDVI_Category': None,
            'NDWI_Value': None, 'NDWI_Category': None,
            'MAI_Value': None, 'MAI_Category': None,
            'Indicator_1_Category': None, 'Indicator_2_Category': None, 'Indicator_3_Category': None
        }
        for col in matrix_data.columns:
            if month.lower() in col.lower():
                value = matrix_data[col].iloc[0] if not matrix_data[col].empty else None
                if 'ndvi' in col.lower() and 'cat' not in col.lower():
                    month_data['NDVI_Value'] = value
                elif 'ndvi' in col.lower() and 'cat' in col.lower():
                    month_data['NDVI_Category'] = value
                elif 'ndwi' in col.lower() and 'cat' not in col.lower():
                    month_data['NDWI_Value'] = value
                elif 'ndwi' in col.lower() and 'cat' in col.lower():
                    month_data['NDWI_Category'] = value
                elif 'mai' in col.lower() and 'cat' not in col.lower():
                    month_data['MAI_Value'] = value
                elif 'mai' in col.lower() and 'cat' in col.lower():
                    month_data['MAI_Category'] = value
                elif 'indicator-1' in col.lower():
                    month_data['Indicator_1_Category'] = value
                elif 'indicator-2' in col.lower():
                    month_data['Indicator_2_Category'] = value
                elif 'indicator-3' in col.lower():
                    month_data['Indicator_3_Category'] = value
        monthly_data.append(month_data)
    return pd.DataFrame(monthly_data)

def create_single_index_chart(monthly_df, index_col, index_name, line_color):
    if monthly_df is None or monthly_df.empty:
        return None
    monthly_df['Month_Num'] = monthly_df['Month'].apply(lambda x: datetime.strptime(x, '%B').month)
    monthly_df = monthly_df.sort_values('Month_Num')
    if monthly_df[index_col].isna().all():
        return None
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=monthly_df['Month'], y=monthly_df[index_col],
                             mode='lines+markers', name=index_name,
                             line=dict(color=line_color)))
    fig.update_layout(title=f"Monthly {index_name} Trend",
                      xaxis_title="Month", yaxis_title=f"{index_name} Value")
    return fig

# -----------------------------
# UI
# -----------------------------
st.markdown("### 🌱 Crop Advisory System – Data Matrix & Monthly Analysis")
col1, col2, col3 = st.columns(3)
with col1:
    district = st.selectbox("District *", [""] + districts)
    taluka_options = [""] + sorted(weather_df[weather_df["District"] == district]["Taluka"].dropna().unique().tolist()) if district else talukas
    taluka = st.selectbox("Taluka", taluka_options)
    circle_options = [""] + sorted(weather_df[weather_df["Taluka"] == taluka]["Circle"].dropna().unique().tolist()) if taluka else circles
    circle = st.selectbox("Circle", circle_options)
with col2:
    crop = st.selectbox("Crop Name *", [""] + crops)
    sowing_date = st.date_input("Sowing Date", value=date.today() - timedelta(days=30), format="DD/MM/YYYY")
    current_date = st.date_input("Current Date", value=date.today(), format="DD/MM/YYYY")
generate = st.button("🌱 Generate Advisory")

if generate:
    matrix_data = get_circlewise_data(district, taluka, circle, sowing_date, current_date)
    if not matrix_data.empty:
        monthly_df = create_monthly_analysis(matrix_data)
        tab1, tab2 = st.tabs(["📊 Data Matrix", "📈 Monthly Trends"])
        with tab1:
            st.dataframe(matrix_data, use_container_width=True)
        with tab2:
            if monthly_df is not None and not monthly_df.empty:
                st.subheader("📈 Monthly Trends (NDVI, NDWI, MAI)")
                ndvi_chart = create_single_index_chart(monthly_df, "NDVI_Value", "NDVI", "green")
                if ndvi_chart: st.plotly_chart(ndvi_chart, use_container_width=True)
                ndwi_chart = create_single_index_chart(monthly_df, "NDWI_Value", "NDWI", "blue")
                if ndwi_chart: st.plotly_chart(ndwi_chart, use_container_width=True)
                mai_chart = create_single_index_chart(monthly_df, "MAI_Value", "MAI", "orange")
                if mai_chart: st.plotly_chart(mai_chart, use_container_width=True)

                st.subheader("📊 Monthly Indicator Categories")
                st.dataframe(monthly_df[['Month', 'Indicator_1_Category', 'Indicator_2_Category', 'Indicator_3_Category']], use_container_width=True)
            else:
                st.info("No monthly data available.")
    else:
        st.warning("No data found for selected filters.")
