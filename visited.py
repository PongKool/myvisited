import os
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from datetime import datetime

# File path to save data locally
DATA_FILE = "visited_places.csv"

# Function to load existing data
def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    else:
        return pd.DataFrame(columns=["Place Name", "Category", "Notes", "Date Visited", "Latitude", "Longitude"])

# Function to get coordinates from a place name
def geocode_place(place_name):
    try:
        geolocator = Nominatim(user_agent="travel_logger_app")
        location = geolocator.geocode(place_name, timeout=10)
        if location:
            return location.latitude, location.longitude
    except Exception:
        pass
    return None, None

# Function to save new entry
def save_entry(place_name, category, notes, lat=None, lon=None):
    df = load_data()
    
    # Geocode if coordinates were not provided manually
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

# App Title & UI Setup
st.set_page_config(page_title="Visited Places Log", page_icon="📍", layout="wide")

st.title("📍 Visited Places Log & Map")
st.write("Record and visualize all the amazing places you have visited on an interactive map.")

# Main Layout: Form on Left, Map/Log on Right
col_left, col_right = st.columns([1, 2])

with col_left:
    with st.form("add_place_form", clear_on_submit=True):
        st.subheader("Add a New Place")
        
        place_name = st.text_input("Place Name*", placeholder="e.g., Rayong Beach")
        category = st.selectbox("Category", ["Beach", "Restaurant", "Park", "Museum", "Cafe", "Other"])
        notes = st.text_area("Notes / Memories", placeholder="e.g., Had great seafood, sunset was amazing!")
        
        submitted = st.form_submit_button("📌 Record Place")

        if submitted:
            if not place_name.strip():
                st.error("Please enter a place name before saving.")
            else:
                lat, lon = save_entry(place_name, category, notes)
                if lat and lon:
                    st.success(f"Recorded '{place_name}' successfully with map location!")
                else:
                    st.warning(f"Recorded '{place_name}', but couldn't locate it automatically on the map.")

with col_right:
    data = load_data()

    # Map Section
    st.subheader("🗺️ Map View")
    
    # Filter valid coordinates
    map_data = data.dropna(subset=["Latitude", "Longitude"])
    
    if not map_data.empty:
        # Center map on the average location of all visited places
        center_lat = map_data["Latitude"].mean()
        center_lon = map_data["Longitude"].mean()
        m = folium.Map(location=[center_lat, center_lon], zoom_start=6)

        # Add markers for each place
        for _, row in map_data.iterrows():
            popup_text = f"<b>{row['Place Name']}</b><br><i>Category:</i> {row['Category']}<br><i>Notes:</i> {row['Notes']}"
            folium.Marker(
                location=[row["Latitude"], row["Longitude"]],
                popup=folium.Popup(popup_text, max_width=250),
                tooltip=row["Place Name"],
                icon=folium.Icon(color="blue", icon="info-sign")
            ).add_to(m)

        # Render map in Streamlit
        st_folium(m, width="100%", height=400)
    else:
        st.info("No places with valid map coordinates to display yet. Add a recognizable place name above!")

st.divider()

# Log Table & Export
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
