import os
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from datetime import datetime
from zoneinfo import ZoneInfo
from streamlit_js_eval import get_geolocation

DATA_FILE = "visited_places.csv"

def get_thailand_time_str():
    return datetime.now(ZoneInfo("Asia/Bangkok")).strftime("%Y-%m-%d %I:%M:%S %p")

def clean_province_name(province_str):
    if not province_str or pd.isna(province_str):
        return "Unknown"
    cleaned = str(province_str).replace("จังหวัด", "").strip()
    return cleaned if cleaned else "Unknown"

def load_data():
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        if "Date Visited" in df.columns and "Last Visited" not in df.columns:
            df.rename(columns={"Date Visited": "Last Visited"}, inplace=True)
        if "Last Visited" not in df.columns:
            df["Last Visited"] = get_thailand_time_str()
        else:
            def fix_timestamp(val):
                if pd.isna(val):
                    return val
                val_str = str(val)
                for tz_str in ["+07:00", "+0700", "+07", "ICT", "UTC"]:
                    val_str = val_str.replace(tz_str, "").strip()
                try:
                    utc_dt = datetime.strptime(val_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("UTC"))
                    bkk_dt = utc_dt.astimezone(ZoneInfo("Asia/Bangkok"))
                    return bkk_dt.strftime("%Y-%m-%d %I:%M:%S %p")
                except Exception:
                    return val_str
            df["Last Visited"] = df["Last Visited"].apply(fix_timestamp)

        if "Visit Count" not in df.columns:
            df["Visit Count"] = 1
        if "Number of People" not in df.columns:
            df["Number of People"] = 1
        if "Companions" not in df.columns:
            df["Companions"] = "Solo"
        if "Province" not in df.columns:
            df["Province"] = "Unknown"
        else:
            df["Province"] = df["Province"].apply(clean_province_name)

        if "Notes" not in df.columns:
            df["Notes"] = ""
        else:
            df["Notes"] = df["Notes"].fillna("")

        # Ensure 'No.' column exists and is numbered 1, 2, 3...
        df["No."] = range(1, len(df) + 1)
        return df
    else:
        return pd.DataFrame(columns=[
            "No.", "Place Name", "Province", "Category", "Notes", "Last Visited", 
            "Visit Count", "Number of People", "Companions", "Latitude", "Longitude"
        ])

def save_all_data(df):
    df_to_save = df.copy()
    if "No." in df_to_save.columns:
        df_to_save["No."] = range(1, len(df_to_save) + 1)
    df_to_save.to_csv(DATA_FILE, index=False)

def geocode_place(place_name):
    try:
        geolocator = Nominatim(user_agent="travel_logger_app")
        location = geolocator.geocode(place_name, timeout=10, addressdetails=True)
        if location:
            address = location.raw.get("address", {})
            raw_province = address.get("state") or address.get("province") or "Unknown"
            return location.latitude, location.longitude, clean_province_name(raw_province)
    except Exception:
        pass
    return None, None, "Unknown"

def reverse_geocode(lat, lon):
    try:
        geolocator = Nominatim(user_agent="travel_logger_app")
        location = geolocator.reverse((lat, lon), timeout=10)
        if location and location.raw.get("address"):
            address = location.raw["address"]
            name = (
                address.get("facility") or address.get("office") or address.get("amenity") or
                address.get("tourism") or address.get("building") or address.get("leisure") or
                address.get("shop") or address.get("road") or location.address.split(",")[0]
            )
            raw_province = address.get("state") or address.get("province") or "Unknown"
            return name, clean_province_name(raw_province)
    except Exception:
        pass
    return "", "Unknown"

def save_entry(place_name, province, category, notes, num_people, companions, lat=None, lon=None):
    df = load_data()
    clean_name = place_name.strip()
    clean_province = clean_province_name(province)
    now_str = get_thailand_time_str()
    companions_str = companions.strip() if companions.strip() else "Solo"

    existing_match = df[df["Place Name"].str.strip().str.lower() == clean_name.lower()]
    if (lat is None or lon is None) and not existing_match.empty:
        lat = existing_match.iloc[0]["Latitude"]
        lon = existing_match.iloc[0]["Longitude"]
        if clean_province == "Unknown":
            clean_province = clean_province_name(existing_match.iloc[0]["Province"])

    if lat is None or lon is None:
        lat, lon, detected_province = geocode_place(clean_name)
        if clean_province == "Unknown" and detected_province != "Unknown":
            clean_province = detected_province

    visit_number = len(existing_match) + 1

    new_entry = pd.DataFrame([{
        "No.": len(df) + 1,
        "Place Name": clean_name,
        "Province": clean_province,
        "Category": category,
        "Notes": notes if notes else "",
        "Last Visited": now_str,
        "Visit Count": visit_number,
        "Number of People": num_people,
        "Companions": companions_str,
        "Latitude": lat,
        "Longitude": lon
    }])

    df = pd.concat([df, new_entry], ignore_index=True)
    save_all_data(df)
    return lat, lon

# Page Config
st.set_page_config(page_title="Visited Places Log", page_icon="📍", layout="wide")
st.title("📍 Visited Places Log & Map")
st.write("Record and visualize all the amazing places you have visited on an interactive map.")

col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("Add / Log a Place")
    
    loc = get_geolocation()
    current_lat, current_lon = None, None
    autofilled_name = ""
    autofilled_province = ""

    if loc and 'coords' in loc:
        current_lat = loc['coords']['latitude']
        current_lon = loc['coords']['longitude']
        st.success(f"GPS Acquired: {current_lat:.4f}, {current_lon:.4f}")
        autofilled_name, autofilled_province = reverse_geocode(current_lat, current_lon)

    with st.form("add_place_form", clear_on_submit=True):
        place_name = st.text_input(
            "Place Name*", 
            value=autofilled_name, 
            placeholder="e.g., Rayong Beach (Auto-detected if GPS enabled)"
        )
        province = st.text_input(
            "Province", 
            value=autofilled_province, 
            placeholder="e.g., Rayong, Pathum Thani"
        )
        category = st.selectbox("Category", ["Beach", "Building", "Forest", "Restaurant", "Park", "Museum", "Cafe", "Other"])
        
        col_num, col_comp = st.columns([1, 2])
        with col_num:
            num_people = st.number_input("Number of People", min_value=1, value=1, step=1)
        with col_comp:
            companions = st.text_input("Who went with you?", placeholder="e.g., Alice, Bob (Leave empty for Solo)")
            
        notes = st.text_area("Notes / Memories", placeholder="e.g., Had great seafood, sunset was amazing!")
        use_gps = st.checkbox("Use current GPS coordinates", value=bool(current_lat))

        submitted = st.form_submit_button("📌 Record Place")

        if submitted:
            if not place_name.strip():
                st.error("Please enter a place name before saving.")
            else:
                lat_to_save = current_lat if use_gps else None
                lon_to_save = current_lon if use_gps else None

                lat, lon = save_entry(
                    place_name, province, category, notes, num_people, companions,
                    lat=lat_to_save, lon=lon_to_save
                )

                if lat and lon:
                    st.success(f"Logged '{place_name}' successfully!")
                else:
                    st.warning(f"Logged '{place_name}', but couldn't locate it on the map.")

with col_right:
    data = load_data()
    st.subheader("🗺️ Map View")
    map_data = data.dropna(subset=["Latitude", "Longitude"])

    if use_gps and current_lat is not None and current_lon is not None:
        center_lat, center_lon = current_lat, current_lon
        zoom_level = 13
    elif not map_data.empty:
        center_lat = map_data["Latitude"].mean()
        center_lon = map_data["Longitude"].mean()
        zoom_level = 6
    else:
        center_lat, center_lon = 13.73671, 100.52318
        zoom_level = 6

    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_level)

    unique_map_places = map_data.groupby("Place Name").agg({
        "Latitude": "first",
        "Longitude": "first",
        "Province": "first",
        "Category": "last",
        "Notes": "last",
        "Last Visited": "last",
        "Number of People": "sum",
        "Visit Count": "count"
    }).reset_index()

    for _, row in unique_map_places.iterrows():
        popup_text = (
            f"<b>{row['Place Name']}</b> ({row['Province']})<br>"
            f"<i>Total Visits Recorded:</i> {row['Visit Count']}<br>"
            f"<i>Latest Visit:</i> {row['Last Visited']}<br>"
            f"<i>Category:</i> {row['Category']}<br>"
            f"<i>Latest Notes:</i> {row['Notes']}"
        )
        folium.Marker(
            location=[row["Latitude"], row["Longitude"]],
            popup=folium.Popup(popup_text, max_width=250),
            tooltip=f"{row['Place Name']}, {row['Province']}",
            icon=folium.Icon(color="blue", icon="info-sign")
        ).add_to(m)

    if use_gps and current_lat is not None and current_lon is not None:
        folium.Marker(
            location=[current_lat, current_lon],
            popup="📍 You are here (Current GPS)",
            tooltip="Current GPS Location",
            icon=folium.Icon(color="red", icon="user", prefix="fa")
        ).add_to(m)

    st_folium(m, width="100%", height=400, key=f"visited_map_{use_gps}_{current_lat}_{current_lon}")

st.divider()

st.subheader("📋 Memory Log")
if not data.empty:
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric("Unique Places", data["Place Name"].nunique())
    m_col2.metric("Provinces Visited", data["Province"].nunique())
    m_col3.metric("Total Visit Records", len(data))
    m_col4.metric("Mapped Locations", unique_map_places["Place Name"].nunique() if not unique_map_places.empty else 0)

    COLUMN_ORDER = [
        "No.", "Place Name", "Province", "Category", "Notes", "Last Visited", 
        "Visit Count", "Number of People", "Companions", "Latitude", "Longitude"
    ]

    col_sort_field, col_sort_dir = st.columns([2, 1])
    with col_sort_field:
        sort_by_col = st.selectbox("Sort table by:", COLUMN_ORDER, index=0)
    with col_sort_dir:
        sort_ascending = st.radio("Direction:", ["Ascending", "Descending"], horizontal=True) == "Ascending"

    sorted_data = data.sort_values(by=sort_by_col, ascending=sort_ascending)

    column_config = {
        "No.": st.column_config.NumberColumn("No.", min_value=1, step=1, disabled=True),
        "Notes": st.column_config.TextColumn("Notes"),
        "Category": st.column_config.SelectboxColumn(
            "Category",
            options=["Beach", "Building", "Forest", "Restaurant", "Park", "Museum", "Cafe", "Other"],
            required=True
        ),
        "Visit Count": st.column_config.NumberColumn("Visit Count", min_value=1, step=1),
        "Number of People": st.column_config.NumberColumn("Number of People", min_value=1, step=1),
        "Latitude": st.column_config.NumberColumn("Latitude", format="%.6f"),
        "Longitude": st.column_config.NumberColumn("Longitude", format="%.6f"),
    }

    edited_df = st.data_editor(
        sorted_data,
        num_rows="dynamic",
        column_config=column_config,
        column_order=COLUMN_ORDER,
        use_container_width=True,
        hide_index=True,
        key=f"editor_{sort_by_col}_{sort_ascending}"
    )

    col_save, col_export = st.columns([1, 3])
    with col_save:
        if st.button("💾 Save Changes", type="primary"):
            save_all_data(edited_df)
            st.success("Changes saved successfully!")
            st.rerun()

    with col_export:
        csv_data = edited_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export Log as CSV",
            data=csv_data,
            file_name="my_visited_places.csv",
            mime="text/csv"
        )

    st.markdown("### 👥 View Visit Details & Companions per Location")
    
    unique_places = sorted(edited_df["Place Name"].dropna().unique())
    selected_place = st.selectbox("Select a place to inspect visits:", unique_places)

    if selected_place:
        place_visits = edited_df[edited_df["Place Name"] == selected_place].sort_values(by="Last Visited", ascending=False)
        
        if len(place_visits) > 1:
            visit_options = [
                f"Visit #{row['Visit Count']} - {row['Last Visited']} ({row['Number of People']} people: {row['Companions']})"
                for _, row in place_visits.iterrows()
            ]
            selected_visit_label = st.selectbox("Select specific visit record:", visit_options)
            
            selected_index = visit_options.index(selected_visit_label)
            chosen_visit = place_visits.iloc[selected_index]
        else:
            chosen_visit = place_visits.iloc[0]

        st.info(
            f"📍 **{chosen_visit['Place Name']}** ({chosen_visit['Province']})\n\n"
            f"🗓️ **Date:** {chosen_visit['Last Visited']}\n\n"
            f"👥 **Group Size:** {chosen_visit['Number of People']} person(s) (**Companions:** {chosen_visit['Companions']})\n\n"
            f"📝 **Notes:** {chosen_visit['Notes'] if pd.notna(chosen_visit['Notes']) and chosen_visit['Notes'] else 'No notes added'}"
        )
