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

THAI_PROVINCES = [
    "Unknown", "กรุงเทพมหานคร", "กระบี่", "กาญจนบุรี", "กาฬสินธุ์", "กำแพงเพชร",
    "ขอนแก่น", "จันทบุรี", "ฉะเชิงเทรา", "ชลบุรี", "ชัยนาท", "ชัยภูมิ", "ชุมพร",
    "เชียงราย", "เชียงใหม่", "ตรัง", "ตราด", "ตาก", "นครนายก", "นครปฐม",
    "นครพนม", "นครราชสีมา", "นครศรีธรรมราช", "นครสวรรค์", "นนทบุรี", "นราธิวาส",
    "น่าน", "บึงกาฬ", "บุรีรัมย์", "ปทุมธานี", "ประจวบคีรีขันธ์", "ปราจีนบุรี",
    "ปัตตานี", "พะเยา", "พระนครศรีอยุธยา", "พังงา", "พัทลุง", "พิจิตร",
    "พิษณุโลก", "เพชรบุรี", "เพชรบูรณ์", "แพร่", "ภูเก็ต", "มหาสารคาม",
    "มุกดาหาร", "แม่ฮ่องสอน", "ยโสธร", "ยะลา", "ร้อยเอ็ด", "ระนอง", "ระยอง",
    "ราชบุรี", "ลพบุรี", "ลำปาง", "ลำพูน", "เลย", "ศรีสะเกษ", "สกลนคร",
    "สงขลา", "สตูล", "สมุทรปราการ", "สมุทรสงคราม", "สมุทรสาคร", "สระแก้ว",
    "สระบุรี", "สิงห์บุรี", "สุโขทัย", "สุพรรณบุรี", "สุราษฎร์ธานี", "สุรินทร์",
    "หนองคาย", "หนองบัวลำภู", "อ่างทอง", "อำนาจเจริญ", "อุดรธานี", "อุตรดิตถ์",
    "อุทัยธานี", "อุบลราชธานี"
]

CATEGORIES = [
    "Accomodation", "Beach", "Building", "Forest", "Historic", "Island", "Restaurant",
    "Park", "Mountain", "Museum", "Cafe", "Temple", "Theater", "Other"
]

def get_thailand_time_str():
    return datetime.now(ZoneInfo("Asia/Bangkok")).strftime("%Y-%m-%d %I:%M:%S %p")

def clean_province_name(province_str):
    if not province_str or pd.isna(province_str):
        return "Unknown"
    cleaned = str(province_str).replace("จังหวัด", "").strip()
    return cleaned if cleaned else "Unknown"

def assign_location_numbers(df):
    group_cols = ["Place Name", "Province", "Category", "Latitude", "Longitude"]
    if all(col in df.columns for col in group_cols):
        df["No."] = df.groupby(group_cols, sort=False).ngroup() + 1
    else:
        df["No."] = range(1, len(df) + 1)
    return df

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
        if "Rating" not in df.columns:
            df["Rating"] = 5
        if "Province" not in df.columns:
            df["Province"] = "Unknown"
        else:
            df["Province"] = df["Province"].apply(clean_province_name)
        if "Notes" not in df.columns:
            df["Notes"] = ""
        else:
            df["Notes"] = df["Notes"].fillna("")
            
        df = assign_location_numbers(df)
        return df
    else:
        return pd.DataFrame(columns=[
            "No.", "Place Name", "Province", "Category", "Rating", "Notes", 
            "Last Visited", "Visit Count", "Number of People", "Companions", "Latitude", "Longitude"
        ])

def save_all_data(df):
    df_to_save = df.copy()
    df_to_save = assign_location_numbers(df_to_save)
    df_to_save.to_csv(DATA_FILE, index=False)

@st.cache_data(ttl=86400)
def geocode_place(place_name):
    if not place_name or not place_name.strip():
        return None, None, "Unknown"
    try:
        geolocator = Nominatim(user_agent="travel_logger_app_v3")
        location = geolocator.geocode(place_name.strip(), timeout=5, addressdetails=True)
        if location:
            address = location.raw.get("address", {})
            raw_province = address.get("state") or address.get("province") or "Unknown"
            return location.latitude, location.longitude, clean_province_name(raw_province)
    except Exception:
        pass
    return None, None, "Unknown"

@st.cache_data(ttl=86400)
def reverse_geocode(lat, lon):
    if lat is None or lon is None:
        return "", "Unknown"
    try:
        geolocator = Nominatim(user_agent="travel_logger_app_v3")
        location = geolocator.reverse((lat, lon), timeout=5)
        if location and location.raw.get("address"):
            address = location.raw["address"]
            name = (address.get("facility") or address.get("office") or address.get("amenity") or 
                    address.get("tourism") or address.get("building") or address.get("leisure") or 
                    address.get("shop") or address.get("road") or location.address.split(",")[0])
            raw_province = address.get("state") or address.get("province") or "Unknown"
            return name, clean_province_name(raw_province)
    except Exception:
        pass
    return "", "Unknown"

def save_entry(place_name, province, category, rating, notes, num_people, companions, visit_datetime_str=None, lat=None, lon=None, auto_geocode=True):
    df = load_data()
    clean_name = place_name.strip()
    clean_province = clean_province_name(province)
    now_str = visit_datetime_str if visit_datetime_str else get_thailand_time_str()
    companions_str = companions.strip() if companions.strip() else "Solo"

    existing_match = df[df["Place Name"].str.strip().str.lower() == clean_name.lower()]

    if (lat is None or lon is None) and auto_geocode:
        if not existing_match.empty:
            lat = existing_match.iloc[0]["Latitude"]
            lon = existing_match.iloc[0]["Longitude"]
            if clean_province == "Unknown":
                clean_province = clean_province_name(existing_match.iloc[0]["Province"])
        else:
            lat, lon, detected_province = geocode_place(clean_name)
            if clean_province == "Unknown" and detected_province != "Unknown":
                clean_province = detected_province

    visit_number = len(existing_match) + 1
    new_entry = pd.DataFrame([{
        "No.": 1,
        "Place Name": clean_name,
        "Province": clean_province,
        "Category": category,
        "Rating": rating,
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

# Display pending toast messages after a rerun
if "toast_msg" in st.session_state:
    st.toast(st.session_state.toast_msg["text"], icon=st.session_state.toast_msg["icon"])
    del st.session_state.toast_msg

st.title("📍 Visited Places Log & Map")
st.write("Record and visualize all the amazing places you have visited on an interactive map.")

col_left, col_right = st.columns([1, 2])

# Session state initialization for manual map pin picking
if "manual_lat" not in st.session_state:
    st.session_state.manual_lat = None
    st.session_state.manual_lon = st.session_state.get("manual_lon", None)

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

    gps_mode = st.radio(
        "GPS Mode:",
        options=["Manual", "Use current GPS", "Look with GPS"],
        index=1 if current_lat else 0,
        horizontal=True,
        help="Manual: Click on map or select province to locate. Use current GPS: Auto-detect location. Look with GPS: Search coordinates for typed place name."
    )

    use_gps = (gps_mode == "Use current GPS")
    look_gps = (gps_mode == "Look with GPS")
    is_manual = (gps_mode == "Manual")

    clicked_lat = st.session_state.get("manual_lat")
    clicked_lon = st.session_state.get("manual_lon")

    default_name = ""
    default_province = "Unknown"

    if use_gps and autofilled_name:
        default_name = autofilled_name
        default_province = autofilled_province
    elif is_manual and clicked_lat and clicked_lon:
        picked_name, picked_prov = reverse_geocode(clicked_lat, clicked_lon)
        default_name = picked_name
        default_province = picked_prov
        st.info(f"📍 Location Picked on Map: ({clicked_lat:.4f}, {clicked_lon:.4f})")

    place_name = st.text_input(
        "Place Name*", 
        value=default_name, 
        placeholder="e.g., Click on the map to select or type manually"
    )

    manual_lat, manual_lon, detected_province = None, None, ""
    if place_name.strip():
        manual_lat, manual_lon, detected_province = geocode_place(place_name)
        if detected_province and detected_province != "Unknown":
            default_province = detected_province

    if look_gps and manual_lat and manual_lon:
        st.info(f"📍 Location Found: {detected_province} ({manual_lat:.4f}, {manual_lon:.4f})")

    prov_index = 0
    if default_province in THAI_PROVINCES:
        prov_index = THAI_PROVINCES.index(default_province)

    if is_manual:
        province = st.selectbox("Province", THAI_PROVINCES, index=prov_index)
    else:
        province = st.text_input("Province", value=default_province, placeholder="e.g., Rayong, Pathum Thani")

    category = st.selectbox("Category", CATEGORIES)
    rating = st.slider("Rating Score (0 - 10)", min_value=0, max_value=10, value=5, step=1)

    # --- Date & Time Handling ---
    now_bkk = datetime.now(ZoneInfo("Asia/Bangkok"))
    if use_gps:
        visit_date = now_bkk.date()
        visit_time = now_bkk.time()
        st.caption(f"🗓️ **Visit Date & Time:** Auto-set to current time ({now_bkk.strftime('%Y-%m-%d %I:%M:%S %p')})")
    else:
        col_date, col_time = st.columns(2)
        with col_date:
            visit_date = st.date_input("Visit Date", value=now_bkk.date())
        with col_time:
            visit_time = st.time_input("Visit Time", value=now_bkk.time())

    selected_datetime_str = datetime.combine(visit_date, visit_time).strftime("%Y-%m-%d %I:%M:%S %p")

    col_num, col_comp = st.columns([1, 2])
    with col_num:
        num_people = st.number_input("Number of People", min_value=1, value=1, step=1)
    with col_comp:
        companions = st.text_input("Who went with you?", placeholder="e.g., Alice, Bob (Leave empty for Solo)")

    notes = st.text_area("Notes / Memories", placeholder="e.g., Had great seafood, sunset was amazing!")

    if st.button("📌 Record Place", type="primary"):
        if not place_name.strip():
            st.error("Please enter a place name before saving.")
        else:
            if use_gps and current_lat:
                lat_to_save, lon_to_save = current_lat, current_lon
            elif look_gps and manual_lat:
                lat_to_save, lon_to_save = manual_lat, manual_lon
            elif is_manual and clicked_lat and clicked_lon:
                lat_to_save, lon_to_save = clicked_lat, clicked_lon
            else:
                lat_to_save, lon_to_save = None, None

            lat, lon = save_entry(
                place_name, province, category, rating, notes, num_people, companions,
                visit_datetime_str=selected_datetime_str,
                lat=lat_to_save,
                lon=lon_to_save,
                auto_geocode=not is_manual
            )

            if lat and lon:
                st.session_state.toast_msg = {
                    "text": f"📍 Logged '{place_name}' successfully!",
                    "icon": "✅"
                }
                st.session_state.manual_lat = None
                st.session_state.manual_lon = None
                st.rerun()
            else:
                st.session_state.toast_msg = {
                    "text": f"⚠️ Logged '{place_name}', but couldn't locate it on the map.",
                    "icon": "⚠️"
                }
                st.rerun()

with col_right:
    data = load_data()
    st.subheader("🗺️ Map View")

    map_data = data.dropna(subset=["Latitude", "Longitude"])

    if look_gps and manual_lat is not None and manual_lon is not None:
        center_lat, center_lon = manual_lat, manual_lon
        zoom_level = 13
    elif use_gps and current_lat is not None and current_lon is not None:
        center_lat, center_lon = current_lat, current_lon
        zoom_level = 13
    elif is_manual and clicked_lat is not None and clicked_lon is not None:
        center_lat, center_lon = clicked_lat, clicked_lon
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
        "Rating": "last",
        "Notes": "last",
        "Last Visited": "last",
        "Number of People": "sum",
        "Visit Count": "count"
    }).reset_index()

    for _, row in unique_map_places.iterrows():
        popup_text = (
            f"<b>{row['Place Name']}</b> ({row['Province']})<br>"
            f"<i>Rating:</i> ⭐ {row['Rating']} / 10<br>"
            f"<i>Total Visits Recorded:</i> {row['Visit Count']}<br>"
            f"<i>Latest Visit:</i> {row['Last Visited']}<br>"
            f"<i>Category:</i> {row['Category']}<br>"
            f"<i>Latest Notes:</i> {row['Notes']}"
        )
        folium.Marker(
            location=[row["Latitude"], row["Longitude"]],
            popup=folium.Popup(popup_text, max_width=250),
            tooltip=f"{row['Place Name']} ({row['Rating']}/10)",
            icon=folium.Icon(color="blue", icon="info-sign")
        ).add_to(m)

    if look_gps and manual_lat is not None and manual_lon is not None:
        folium.Marker(
            location=[manual_lat, manual_lon],
            popup=f"🔎 Found: {place_name}",
            tooltip=f"Look-up GPS Location ({place_name})",
            icon=folium.Icon(color="green", icon="search", prefix="fa")
        ).add_to(m)

    if use_gps and current_lat is not None and current_lon is not None:
        folium.Marker(
            location=[current_lat, current_lon],
            popup="📍 You are here (Current GPS)",
            tooltip="Current GPS Location",
            icon=folium.Icon(color="red", icon="user", prefix="fa")
        ).add_to(m)

    if is_manual and clicked_lat is not None and clicked_lon is not None:
        folium.Marker(
            location=[clicked_lat, clicked_lon],
            popup="📍 Selected Location",
            tooltip="Picked Location",
            icon=folium.Icon(color="purple", icon="map-pin", prefix="fa")
        ).add_to(m)

    map_output = st_folium(
        m, 
        width="100%", 
        height=400, 
        key=f"visited_map_{gps_mode}_{province}_{clicked_lat}_{clicked_lon}_{manual_lat}_{current_lat}"
    )

    if is_manual and map_output and map_output.get("last_clicked"):
        new_click = map_output["last_clicked"]
        if new_click["lat"] != clicked_lat or new_click["lng"] != clicked_lon:
            st.session_state.manual_lat = new_click["lat"]
            st.session_state.manual_lon = new_click["lng"]
            st.rerun()

st.divider()

st.subheader("📋 Memory Log")
if not data.empty:
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric("Unique Places", data["Place Name"].nunique())
    m_col2.metric("Provinces Visited", data["Province"].nunique())
    m_col3.metric("Total Visit Records", len(data))
    m_col4.metric("Mapped Locations", unique_map_places["Place Name"].nunique() if not unique_map_places.empty else 0)

    COLUMN_ORDER = [
        "No.", "Place Name", "Province", "Category", "Rating", "Notes", 
        "Last Visited", "Visit Count", "Number of People", "Companions", "Latitude", "Longitude"
    ]

    col_sort_field, col_sort_dir = st.columns([2, 1])
    with col_sort_field:
        sort_by_col = st.selectbox("Sort table by:", COLUMN_ORDER, index=0)
    with col_sort_dir:
        sort_ascending = st.radio("Direction:", ["Ascending", "Descending"], horizontal=True) == "Ascending"

    sorted_data = data.sort_values(by=sort_by_col, ascending=sort_ascending)

    column_config = {
        "No.": st.column_config.NumberColumn("No.", min_value=1, step=1, disabled=True),
        "Rating": st.column_config.NumberColumn("Rating", min_value=0, max_value=10, step=1, format="%d"),
        "Notes": st.column_config.TextColumn("Notes"),
        "Category": st.column_config.SelectboxColumn("Category", options=CATEGORIES, required=True),
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
            st.session_state.toast_msg = {"text": "Changes saved successfully!", "icon": "💾"}
            st.rerun()
    with col_export:
        csv_data = edited_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export Log as CSV",
            data=csv_data,
            file_name="my_visited_places.csv",
            mime="text/csv"
        )

    st.markdown("### 👥 View Visit Details & Companions")
    view_mode = st.radio("Inspect visits by:", ["By Location", "By Province", "By Rating Score"], horizontal=True)

    if view_mode == "By Location":
        unique_places = sorted(edited_df["Place Name"].dropna().unique())
        selected_place = st.selectbox("Select a place to inspect visits:", unique_places)
        if selected_place:
            place_visits = edited_df[edited_df["Place Name"] == selected_place].sort_values(by="Last Visited", ascending=False)
            if len(place_visits) > 1:
                visit_options = [
                    f"Visit #{row['Visit Count']} - {row['Last Visited']} (Rating: {row['Rating']}/10, {row['Number of People']} people: {row['Companions']})"
                    for _, row in place_visits.iterrows()
                ]
                selected_visit_label = st.selectbox("Select specific visit record:", visit_options)
                selected_index = visit_options.index(selected_visit_label)
                chosen_visit = place_visits.iloc[selected_index]
            else:
                chosen_visit = place_visits.iloc[0]

            st.info(
                f"📍 **{chosen_visit['Place Name']}** ({chosen_visit['Province']})\n\n"
                f"⭐ **Rating:** {chosen_visit['Rating']} / 10\n\n"
                f"🗓️ **Date:** {chosen_visit['Last Visited']}\n\n"
                f"👥 **Group Size:** {chosen_visit['Number of People']} person(s) (**Companions:** {chosen_visit['Companions']})\n\n"
                f"📝 **Notes:** {chosen_visit['Notes'] if pd.notna(chosen_visit['Notes']) and chosen_visit['Notes'] else 'No notes added'}"
            )

    elif view_mode == "By Province":
        unique_provinces = sorted(edited_df["Province"].dropna().unique())
        selected_province = st.selectbox("Select a province to inspect visits:", unique_provinces)
        if selected_province:
            prov_visits = edited_df[edited_df["Province"] == selected_province].sort_values(by="Last Visited", ascending=False)
            st.success(f"Found **{len(prov_visits)}** visit record(s) in **{selected_province}** across **{prov_visits['Place Name'].nunique()}** unique place(s).")
            visit_options = [
                f"{row['Place Name']} - Visit #{row['Visit Count']} on {row['Last Visited']} (Rating: {row['Rating']}/10, {row['Number of People']} people: {row['Companions']})"
                for _, row in prov_visits.iterrows()
            ]
            selected_visit_label = st.selectbox("Select specific visit record in this province:", visit_options)
            selected_index = visit_options.index(selected_visit_label)
            chosen_visit = prov_visits.iloc[selected_index]

            st.info(
                f"📍 **{chosen_visit['Place Name']}** ({chosen_visit['Province']})\n\n"
                f"🏷️ **Category:** {chosen_visit['Category']}\n\n"
                f"⭐ **Rating:** {chosen_visit['Rating']} / 10\n\n"
                f"🗓️ **Date:** {chosen_visit['Last Visited']}\n\n"
                f"👥 **Group Size:** {chosen_visit['Number of People']} person(s) (**Companions:** {chosen_visit['Companions']})\n\n"
                f"📝 **Notes:** {chosen_visit['Notes'] if pd.notna(chosen_visit['Notes']) and chosen_visit['Notes'] else 'No notes added'}"
            )

    else:  # By Rating Score
        unique_ratings = sorted(edited_df["Rating"].dropna().unique(), reverse=True)
        selected_rating = st.selectbox("Select a rating score to inspect visits:", unique_ratings, format_func=lambda r: f"⭐ {r} / 10")
        if selected_rating is not None:
            score_visits = edited_df[edited_df["Rating"] == selected_rating].sort_values(by="Last Visited", ascending=False)
            st.success(f"Found **{len(score_visits)}** visit record(s) rated **{selected_rating}/10** across **{score_visits['Place Name'].nunique()}** place(s).")
            visit_options = [
                f"{row['Place Name']} ({row['Province']}) - Visit #{row['Visit Count']} on {row['Last Visited']} ({row['Number of People']} people: {row['Companions']})"
                for _, row in score_visits.iterrows()
            ]
            selected_visit_label = st.selectbox("Select specific visit record with this score:", visit_options)
            selected_index = visit_options.index(selected_visit_label)
            chosen_visit = score_visits.iloc[selected_index]

            st.info(
                f"📍 **{chosen_visit['Place Name']}** ({chosen_visit['Province']})\n\n"
                f"🏷️ **Category:** {chosen_visit['Category']}\n\n"
                f"⭐ **Rating:** {chosen_visit['Rating']} / 10\n\n"
                f"🗓️ **Date:** {chosen_visit['Last Visited']}\n\n"
                f"👥 **Group Size:** {chosen_visit['Number of People']} person(s) (**Companions:** {chosen_visit['Companions']})\n\n"
                f"📝 **Notes:** {chosen_visit['Notes'] if pd.notna(chosen_visit['Notes']) and chosen_visit['Notes'] else 'No notes added'}"
            )
