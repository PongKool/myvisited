import os
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from datetime import datetime
from streamlit_js_eval import get_geolocation

DATA_FILE = "visited_places.csv"

def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    else:
        return pd.DataFrame(columns=["Place Name", "Category", "Notes", "Date Visited", "Latitude", "Longitude"])

def geocode_place(place_name):
    try:
        geolocator = Nominatim(user_agent="travel_logger_app")
        location = geolocator.geocode(place_name, timeout=10)
        if location:
            return location.latitude, location.longitude
    except Exception:
        pass
    return None, None

def save_entry(place_name, category, notes, lat=None, lon=None):
    df = load_data()
    
    # Fall back to geocoding if coordinates were not captured via GPS
    if lat is None or lon is None:
        lat, lon = geocode_place(place_name)
        
    new_data = pd.DataFrame([{
        "Place Name": place_name,
        "Category": category,
        "Notes": notes,
        "Date Visited": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Latitude": lat,
        "Longitude": lon
    }])
    
    df = pd.concat([df, new_data], ignore_index=True)
    df.to_csv(DATA_FILE, index=False)
    return lat, lon

st.set_page_config(page_title="Visited Places Log", page_icon="📍", layout="wide")

st.title("📍 Visited Places Log & Map")
st.write("Record and visualize all the amazing places you have visited on an interactive map.")

col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("Add a New Place")
    
    # Live GPS fetcher button outside the form
    loc = get_geolocation()
    
    current_lat, current_lon = None, None
    if loc and 'coords' in loc:
        current_lat = loc['coords']['latitude']
        current_lon = loc['coords']['longitude']
        st.success(f"GPS Acquired: {current_lat:.4f}, {current_lon:.4f}")

    with st.form("add_place_form", clear_on_submit=True):
        place_name = st.text_input("Place Name*", placeholder="e.g., Rayong Beach")
        category = st.selectbox("Category", ["Beach", "Restaurant", "Park", "Museum", "Cafe", "Other"])
        notes = st.text_area("Notes / Memories", placeholder="e.g., Had great seafood, sunset was amazing!")
        
        # Option to force using fetched GPS
        use_gps = st.checkbox("Use current GPS coordinates", value=bool(current_lat))
        
        submitted = st.form_submit_button("📌 Record Place")

        if submitted:
            if not place_name.strip():
                st.error("Please enter a place name before saving.")
            else:
                lat_to_save = current_lat if use_gps else None
                lon_to_save = current_lon if use_gps else None
                
                lat, lon = save_entry(place_name, category, notes, lat=lat_to_save, lon=lon_to_save)
                
                if lat and lon:
                    st.success(f"Recorded '{place_name}' successfully!")
                else:
                    st.warning(f"Recorded '{place_name}', but couldn't locate it on the map.")

with col_right:
    data = load_data()
    st.subheader("🗺️ Map View")
    map_data = data.dropna(subset=["Latitude", "Longitude"])
    
    if not map_data.empty:
        center_lat = map_data["Latitude"].mean()
        center_lon = map_data["Longitude"].mean()
        m = folium.Map(location=[center_lat, center_lon], zoom_start=6)

        for _, row in map_data.iterrows():
            popup_text = f"<b>{row['Place Name']}</b><br><i>Category:</i> {row['Category']}<br><i>Notes:</i> {row['Notes']}"
            folium.Marker(
                location=[row["Latitude"], row["Longitude"]],
                popup=folium.Popup(popup_text, max_width=250),
                tooltip=row["Place Name"],
                icon=folium.Icon(color="blue", icon="info-sign")
            ).add_to(m)

        st_folium(m, width="100%", height=400)
    else:
        st.info("No places with valid map coordinates to display yet. Add a location above!")

st.divider()

st.subheader("📋 Memory Log")
if not data.empty:
    m_col1, m_col2 = st.columns(2)
    m_col1.metric("Total Places Visited", len(data))
    m_col2.metric("Mapped Locations", len(map_data))

    st.dataframe(
        data.sort_values(by="Date Visited", ascending=False),
        use_container_width=True,
        hide_index=True
    )
    
    csv_data = data.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Export Log as CSV",
        data=csv_data,
        file_name="my_visited_places.csv",
        mime="text/csv"
    )
