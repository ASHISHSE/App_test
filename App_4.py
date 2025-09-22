# crop_advisory_app_updated.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

# --- Page config: landscape / wide layout ---
st.set_page_config(page_title="Crop Advisory (Landscape)", layout="wide", initial_sidebar_state="expanded")


# --- Helpers: date parsing/formatting ---
DATE_FORMAT = "%d/%m/%Y"

def parse_date_ddmmyyyy(s: str):
    """Parse a string DD/MM/YYYY -> datetime.date. Returns None if invalid."""
    try:
        return datetime.strptime(s.strip(), DATE_FORMAT).date()
    except Exception:
        return None

def format_date_ddmmyyyy(d):
    if pd.isna(d):
        return ""
    if isinstance(d, (datetime, )):
        d = d.date()
    return d.strftime(DATE_FORMAT)


# --- Sample data generation (for quick testing) ---
def generate_sample_weather_data(start_date, end_date):
    """Generate sample weather dataframe with daily records for a few locations"""
    dates = pd.date_range(start_date, end_date, freq="D")
    rows = []
    districts = ["DistrictA", "DistrictB"]
    talukas = {"DistrictA": ["TalukaA1", "TalukaA2"], "DistrictB": ["TalukaB1"]}
    circles = {
        "TalukaA1": ["CircleA1a", "CircleA1b"],
        "TalukaA2": ["CircleA2a"],
        "TalukaB1": ["CircleB1a", "CircleB1b"]
    }
    for d in dates:
        for dist in districts:
            for tal in talukas[dist]:
                for cir in circles.get(tal, [np.nan]):
                    rows.append({
                        "date": d.date(),
                        "district": dist,
                        "taluka": tal,
                        "circle": cir,
                        "rainfall_mm": max(0, np.random.gamma(0.5, 4)),  # random rainfall
                        "tmax": 25 + np.random.randn() * 3,
                        "tmin": 15 + np.random.randn() * 2,
                        "max_rh": 70 + np.random.randn() * 10,
                        "min_rh": 40 + np.random.randn() * 8
                    })
    return pd.DataFrame(rows)

def generate_sample_rules():
    """Generate sample rules dataframe for growth stages and ideal water requirement"""
    data = [
        {"growth_stage": "Emergence", "min_DAS": 0, "max_DAS": 14, "Ideal_water_required_mm": 30},
        {"growth_stage": "Vegetative", "min_DAS": 15, "max_DAS": 45, "Ideal_water_required_mm": 80},
        {"growth_stage": "Reproductive", "min_DAS": 46, "max_DAS": 80, "Ideal_water_required_mm": 120},
        {"growth_stage": "Maturity", "min_DAS": 81, "max_DAS": 9999, "Ideal_water_required_mm": 60}
    ]
    return pd.DataFrame(data)


# --- Sidebar: data upload or sample data ---
st.sidebar.title("Data inputs")
weather_file = st.sidebar.file_uploader("Upload weather CSV (cols: date[dd/mm/yyyy] district taluka circle rainfall_mm tmax tmin max_rh min_rh)", type=["csv"])
rules_file = st.sidebar.file_uploader("Upload rules CSV (cols: growth_stage,min_DAS,max_DAS,Ideal_water_required_mm)", type=["csv"])

if weather_file is not None:
    # try read and coerce date format dd/mm/yyyy
    weather_df = pd.read_csv(weather_file)
    if 'date' in weather_df.columns:
        weather_df['date'] = weather_df['date'].astype(str).apply(lambda s: parse_date_ddmmyyyy(s) if isinstance(s, str) else pd.NaT)
    else:
        st.sidebar.error("Weather file must have a 'date' column (DD/MM/YYYY)")
        st.stop()
else:
    # create sample weather for past 180 days
    end = datetime.today().date()
    start = end - timedelta(days=180)
    weather_df = generate_sample_weather_data(start, end)
    st.sidebar.info("No weather CSV uploaded — using generated sample data for testing.")

if rules_file is not None:
    rules_df = pd.read_csv(rules_file)
else:
    rules_df = generate_sample_rules()
    st.sidebar.info("No rules CSV uploaded — using sample rules.")


# Normalize weather_df: ensure required cols present
req_cols = {'date', 'district', 'taluka', 'circle', 'rainfall_mm', 'tmax', 'tmin', 'max_rh', 'min_rh'}
if not req_cols.issubset(set(weather_df.columns)):
    st.sidebar.error(f"Weather data missing columns. Required: {req_cols}")
    st.stop()

# Ensure date is datetime.date type
weather_df['date'] = pd.to_datetime(weather_df['date']).dt.date


# --- Main UI: landscape layout (two columns) ---
st.title("Crop Advisory — Landscape View")
st.markdown("Enter inputs (manual) on the left; results will appear on the right.")

left_col, right_col = st.columns([1, 2])  # landscape: bigger right area for results

with left_col:
    st.header("Manual Inputs")
    # Hierarchical dropdowns
    districts = sorted(weather_df['district'].dropna().unique())
    district = st.selectbox("Select District", options=["-- Select --"] + districts)
    taluka = None
    circle = None

    if district and district != "-- Select --":
        # talukas available for selected district
        taluka_options = sorted(weather_df.loc[weather_df['district'] == district, 'taluka'].dropna().unique())
        taluka = st.selectbox("Select Taluka", options=["-- Select --"] + taluka_options)
    else:
        taluka = st.selectbox("Select Taluka", options=["-- Select --"])

    if taluka and taluka != "-- Select --":
        circle_options = sorted(weather_df.loc[(weather_df['district'] == district) & (weather_df['taluka'] == taluka), 'circle'].dropna().unique())
        circle = st.selectbox("Select Circle (optional)", options=["-- Not selected --"] + circle_options)
    else:
        circle = st.selectbox("Select Circle (optional)", options=["-- Not selected --"])

    crop_name = st.text_input("Crop Name", value="Wheat")

    sowing_date_str = st.text_input("Sowing Date (DD/MM/YYYY)", value=datetime.today().strftime(DATE_FORMAT))
    sowing_date = parse_date_ddmmyyyy(sowing_date_str)
    if sowing_date is None:
        st.warning("Sowing Date not in DD/MM/YYYY format or invalid. Please correct.")
    current_date_str = st.text_input("Current Date (DD/MM/YYYY)", value=datetime.today().strftime(DATE_FORMAT))
    current_date = parse_date_ddmmyyyy(current_date_str)
    if current_date is None:
        st.warning("Current Date not in DD/MM/YYYY format or invalid. Please correct.")

    mode = st.radio("Mode", options=["Automatic (from data)", "Manual (override)"], index=0)

    st.markdown("---")
    st.caption("Notes:\n- If Circle is not selected, calculations are done at Taluka level.\n- If Taluka not selected, calculations are done at District level.")


# Determine aggregation level
def select_level_df(df, district, taluka, circle):
    """Return df filtered to the most-specific selected level following your fallback rules."""
    if circle and circle != "-- Not selected --" and circle in df['circle'].values:
        lvl_df = df[(df['district'] == district) & (df['taluka'] == taluka) & (df['circle'] == circle)]
        level = "circle"
    elif taluka and taluka != "-- Select --" and taluka in df['taluka'].values:
        lvl_df = df[(df['district'] == district) & (df['taluka'] == taluka)]
        level = "taluka"
    elif district and district != "-- Select --" and district in df['district'].values:
        lvl_df = df[df['district'] == district]
        level = "district"
    else:
        lvl_df = df.copy()
        level = "all"
    return lvl_df, level

# --- Compute DAS and weather aggregates ---
def compute_DAS(sowing_date, current_date):
    if sowing_date is None or current_date is None:
        return None
    das = (current_date - sowing_date).days
    if das < 0:
        return 0
    return das

def aggregate_weather_metrics(df_level, current_date, sowing_date):
    """Return a dict with rainfall last week, last month, rainfall over DAS, and averages for tmax/tmin/max_rh/min_rh over DAS."""
    results = {}
    if current_date is None:
        return results
    # last week: last 7 days including current_date
    d_end = current_date
    last_week_start = current_date - timedelta(days=6)
    last_month_start = current_date - timedelta(days=29)

    mask_week = (df_level['date'] >= last_week_start) & (df_level['date'] <= d_end)
    mask_month = (df_level['date'] >= last_month_start) & (df_level['date'] <= d_end)

    results['rainfall_last_week_mm'] = df_level.loc[mask_week, 'rainfall_mm'].sum()
    results['rainfall_last_month_mm'] = df_level.loc[mask_month, 'rainfall_mm'].sum()

    # DAS-based window: from sowing_date (inclusive) to current_date (inclusive)
    das = compute_DAS(sowing_date, current_date)
    results['DAS'] = das
    if das is None or das == 0:
        results['rainfall_DAS_mm'] = df_level.loc[df_level['date'] == current_date, 'rainfall_mm'].sum()
        # average metrics -> use last 1 day (current)
        mask_das = (df_level['date'] <= d_end) & (df_level['date'] >= d_end)
    else:
        start_das = current_date - timedelta(days=das)
        # Wait: if sowing_date is S and current_date is C, we want records S..C inclusive:
        start_das = sowing_date
        mask_das = (df_level['date'] >= start_das) & (df_level['date'] <= d_end)
        results['rainfall_DAS_mm'] = df_level.loc[mask_das, 'rainfall_mm'].sum()

    # average of the DAS window for tmax/tmin/max_rh/min_rh
    for col in ['tmax', 'tmin', 'max_rh', 'min_rh']:
        vals = df_level.loc[mask_das, col]
        results[f'{col}_avg_DAS'] = float(vals.mean()) if len(vals) > 0 else np.nan

    return results


# --- Sowing FN calculation ---
def sowing_FN(sowing_date):
    if sowing_date is None:
        return None
    day = sowing_date.day
    return "1FN" if 1 <= day <= 15 else "2FN"


# --- Growth stage assignment from rules_df using DAS ---
def assign_growth_stage(rules_df, das):
    """Find a matching rule row where min_DAS <= das <= max_DAS. Return row as dict or None."""
    if das is None:
        return None
    matched = rules_df[(rules_df['min_DAS'] <= das) & (rules_df['max_DAS'] >= das)]
    if matched.empty:
        return None
    # return first match
    row = matched.iloc[0].to_dict()
    return row


# --- Advisory generation comparing rainfall_DAS with Ideal water required ---
def generate_advisory(rainfall_DAS, ideal_required_mm, growth_stage_row):
    if growth_stage_row is None:
        return "No growth stage found in rules for current DAS; cannot compute advisory."
    if pd.isna(ideal_required_mm):
        return "Ideal water requirement missing in rules; cannot compute advisory."

    diff = rainfall_DAS - ideal_required_mm
    if diff >= 0:
        return f"Water sufficient for stage '{growth_stage_row['growth_stage']}'. Rainfall over DAS = {rainfall_DAS:.1f} mm meets/exceeds Ideal = {ideal_required_mm:.1f} mm."
    else:
        deficit = abs(diff)
        # Construct simple irrigation advice (you can extend rules to include irrigation scheduling)
        return (f"Water DEFICIT for stage '{growth_stage_row['growth_stage']}'. "
                f"Rainfall over DAS = {rainfall_DAS:.1f} mm, Ideal = {ideal_required_mm:.1f} mm → deficit {deficit:.1f} mm. "
                f"Recommend irrigation scheduling and monitoring soil moisture.")


# --- Run calculations and display on right area ---
with right_col:
    st.header("Results / Advisory")

    if None in (sowing_date, current_date):
        st.warning("Please enter valid Sowing Date and Current Date in DD/MM/YYYY format to compute advisory.")
    else:
        # filter weather at selected level
        df_level, level = select_level_df(weather_df, district if district and district != "-- Select --" else None,
                                          taluka if taluka and taluka != "-- Select --" else None,
                                          circle if circle and circle != "-- Not selected --" else None)

        st.subheader(f"Aggregation level: {level}")
        st.caption(f"Records considered: {len(df_level)}")

        # compute metrics
        metrics = aggregate_weather_metrics(df_level, current_date, sowing_date)
        das = metrics.get('DAS', 0)

        # Sowing FN
        sfn = sowing_FN(sowing_date)

        # assign growth stage via rules
        growth_stage_row = assign_growth_stage(rules_df, das)
        ideal_water = None
        if growth_stage_row is not None:
            ideal_water = growth_stage_row.get('Ideal_water_required_mm', np.nan)

        # advisory
        rainfall_DAS = metrics.get('rainfall_DAS_mm', 0.0)
        advisory = generate_advisory(rainfall_DAS, ideal_water if ideal_water is not None else np.nan, growth_stage_row)

        # Display summary metrics in a horizontal card-like view
        cols = st.columns(4)
        cols[0].metric("Sowing Date", format_date_ddmmyyyy(sowing_date))
        cols[1].metric("Current Date", format_date_ddmmyyyy(current_date))
        cols[2].metric("DAS", das)
        cols[3].metric("Sowing FN", sfn)

        st.markdown("### Weather aggregates")
        agg_cols = st.columns(4)
        agg_cols[0].write(f"Rainfall — Last week (7d): **{metrics.get('rainfall_last_week_mm', 0.0):.1f} mm**")
        agg_cols[1].write(f"Rainfall — Last month (30d): **{metrics.get('rainfall_last_month_mm', 0.0):.1f} mm**")
        agg_cols[2].write(f"Rainfall — Over DAS ({das} days): **{rainfall_DAS:.1f} mm**")
        agg_cols[3].write(f"Growth stage: **{growth_stage_row['growth_stage'] if growth_stage_row is not None else 'Not found'}**")

        st.markdown("#### Temperature & RH averages over DAS window")
        tcols = st.columns(4)
        tcols[0].write(f"Tmax avg (DAS): **{metrics.get('tmax_avg_DAS', np.nan):.2f} °C**")
        tcols[1].write(f"Tmin avg (DAS): **{metrics.get('tmin_avg_DAS', np.nan):.2f} °C**")
        tcols[2].write(f"Max RH avg (DAS): **{metrics.get('max_rh_avg_DAS', np.nan):.1f} %**")
        tcols[3].write(f"Min RH avg (DAS): **{metrics.get('min_rh_avg_DAS', np.nan):.1f} %**")

        st.markdown("### Advisory")
        st.info(advisory)

        # Also show a detail table of the recent days used in computation
        with st.expander("Show weather records used (DAS window)"):
            # mask for DAS window
            if das == 0:
                mask_das = (df_level['date'] == current_date)
            else:
                mask_das = (df_level['date'] >= sowing_date) & (df_level['date'] <= current_date)
            st.dataframe(df_level.loc[mask_das].sort_values('date').reset_index(drop=True))

        # save/print quick summary
        st.markdown("---")
        st.write("**Quick summary report:**")
        st.write({
            "Crop": crop_name,
            "Aggregation level": level,
            "Sowing_FN": sfn,
            "DAS": das,
            "Rainfall_DAS_mm": round(rainfall_DAS, 1),
            "Ideal_water_required_mm": round(float(ideal_water) if ideal_water is not None else np.nan, 1) if ideal_water is not None else None,
            "Advisory": advisory
        })

        # Optionally offer download of summary as CSV/JSON
        if st.button("Download summary CSV"):
            summary_df = pd.DataFrame([{
                "crop": crop_name,
                "district": district,
                "taluka": taluka,
                "circle": circle,
                "sowing_date": format_date_ddmmyyyy(sowing_date),
                "current_date": format_date_ddmmyyyy(current_date),
                "DAS": das,
                "sowing_FN": sfn,
                "rainfall_DAS_mm": rainfall_DAS,
                "ideal_water_required_mm": ideal_water,
                "advisory": advisory
            }])
            st.download_button("Click to download CSV", data=summary_df.to_csv(index=False).encode('utf-8'),
                               file_name="crop_advisory_summary.csv", mime="text/csv")

