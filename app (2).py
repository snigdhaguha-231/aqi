"""
Urban Air Quality Intelligence Dashboard — Streamlit Cloud version
---------------------------------------------------------------------
A multi-city dashboard: overview cards for every tracked city, plus a
detail panel (gauge, map, forecast, AI advisory) for whichever city
you select.

Deploy for free at https://share.streamlit.io — see README.md.
"""

import streamlit as st
import requests
import numpy as np
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Urban Air Quality Intelligence", layout="wide")

WAQI_TOKEN = st.secrets.get("WAQI_TOKEN", "demo")
ANTHROPIC_API_KEY = st.secrets.get("ANTHROPIC_API_KEY", "")

CITIES = ["Delhi", "Mumbai", "Kolkata", "Bengaluru", "Chennai", "Hyderabad", "Pune"]

AQI_BANDS = [
    (50, "Good", "#4CAF50"),
    (100, "Satisfactory", "#8BC34A"),
    (200, "Moderate", "#FFC107"),
    (300, "Poor", "#FF9800"),
    (400, "Very Poor", "#F44336"),
    (99999, "Severe", "#9C27B0"),
]


def aqi_category(aqi: float):
    for threshold, label, hexcolor in AQI_BANDS:
        if aqi <= threshold:
            return label, hexcolor
    return "Severe", "#9C27B0"


def hex_to_rgba(hex_color: str, alpha: float) -> str:
    """Plotly's color validator rejects 8-digit hex (hex+alpha), so anywhere
    we need a translucent fill for a Plotly chart, convert to rgba() instead.
    Plain HTML/CSS (the styled cards) can still use hex+alpha directly."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


# ---------------------------------------------------------------------------
# DATA
# ---------------------------------------------------------------------------
@st.cache_data(ttl=600)
def fetch_aqi(city: str):
    url = f"https://api.waqi.info/feed/{city}/?token={WAQI_TOKEN}"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
    except requests.RequestException:
        return None
    if data.get("status") != "ok":
        return None
    return data["data"]


def simple_forecast(history_values):
    if len(history_values) < 2:
        return history_values[-1] if history_values else None
    x = np.arange(len(history_values))
    y = np.array(history_values, dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    return max(0, round(slope * len(history_values) + intercept, 1))


def generate_advisory(city, aqi, category):
    if category in ("Very Poor", "Severe"):
        return (f"Avoid outdoor activity in {city}, especially for children, the "
                 f"elderly, and people with respiratory or heart conditions.")
    if category == "Poor":
        return f"Sensitive groups in {city} should limit prolonged outdoor exertion."
    if category == "Moderate":
        return f"Acceptable for most people in {city}, but sensitive individuals should take care."
    return f"Great day to be outdoors in {city}."


def call_llm_advisory(city, aqi, category):
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = (f"Write a single-sentence public health advisory (under 30 words) for "
              f"citizens of {city}, India. Current AQI is {aqi} ({category}). "
              f"Be practical and calm, not alarmist.")
    msg = client.messages.create(
        model="claude-sonnet-4-6", max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


# ---------------------------------------------------------------------------
# STYLE HELPERS
# ---------------------------------------------------------------------------
def mini_card(city, aqi, category, color):
    st.markdown(f"""
    <div style="
        border-radius: 14px;
        padding: 16px 18px;
        background: linear-gradient(135deg, {color}22, {color}08);
        border: 1px solid {color}55;
        text-align: left;">
      <div style="font-size:13px; color:#666; text-transform:uppercase; letter-spacing:0.5px;">{city}</div>
      <div style="font-size:32px; font-weight:700; color:{color};">{aqi}</div>
      <div style="font-size:13px; font-weight:600; color:{color};">{category}</div>
    </div>
    """, unsafe_allow_html=True)


def advisory_box(text, color):
    st.markdown(f"""
    <div style="
        border-left: 5px solid {color};
        background: {color}10;
        padding: 14px 18px;
        border-radius: 8px;
        font-size: 14px; color:#333; margin-top: 10px;">
      <b>Health advisory:</b> {text}
    </div>
    """, unsafe_allow_html=True)


def aqi_gauge(aqi, category, color):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=aqi,
        number={"font": {"size": 34, "color": color}},
        title={"text": category, "font": {"size": 15}},
        gauge={
            "axis": {"range": [0, 500]},
            "bar": {"color": color, "thickness": 0.3},
            "steps": [
                {"range": [0, 50], "color": "rgba(76,175,80,0.2)"},
                {"range": [50, 100], "color": "rgba(139,195,74,0.2)"},
                {"range": [100, 200], "color": "rgba(255,193,7,0.2)"},
                {"range": [200, 300], "color": "rgba(255,152,0,0.2)"},
                {"range": [300, 400], "color": "rgba(244,67,54,0.2)"},
                {"range": [400, 500], "color": "rgba(156,39,176,0.2)"},
            ],
        },
    ))
    fig.update_layout(height=240, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig, use_container_width=True)


def forecast_chart(city, forecast_daily, color):
    if not forecast_daily:
        st.info("No multi-day forecast available for this city from the API.")
        return
    days = [d["day"] for d in forecast_daily]
    avg = [d["avg"] for d in forecast_daily]
    fig = go.Figure(go.Scatter(
        x=days, y=avg, mode="lines+markers",
        line=dict(color=color, width=3, shape="spline"),
        marker=dict(size=7, color=color),
        fill="tozeroy", fillcolor=hex_to_rgba(color, 0.15),
    ))
    fig.update_layout(
        title=f"{city} — PM2.5 forecast (avg)",
        height=280, margin=dict(l=30, r=20, t=50, b=30),
        plot_bgcolor="white", yaxis_title="PM2.5",
    )
    st.plotly_chart(fig, use_container_width=True)


def clean_map(city, aqi, category, color, lat, lon):
    m = folium.Map(location=[lat, lon], zoom_start=10, tiles="CartoDB positron")
    folium.Circle(
        location=[lat, lon], radius=3000, color=color, weight=1,
        fill=True, fill_color=color, fill_opacity=0.15,
    ).add_to(m)
    folium.Marker(
        location=[lat, lon],
        icon=folium.DivIcon(html=f"""
            <div style="background:{color}; color:white; border-radius:50%;
                        width:46px; height:46px; display:flex; align-items:center;
                        justify-content:center; font-weight:bold; font-size:14px;
                        box-shadow:0 2px 6px rgba(0,0,0,0.3); border:2px solid white;">
                {aqi}
            </div>"""),
        popup=f"{city}: AQI {aqi} ({category})",
    ).add_to(m)
    st_folium(m, width=None, height=380, use_container_width=True)


# ---------------------------------------------------------------------------
# LAYOUT
# ---------------------------------------------------------------------------
st.title("🌆 Urban Air Quality Intelligence Dashboard")
st.caption("Live AQI monitoring + forecast + AI health advisory — Smart Cities Hackathon Prototype")

st.subheader("City overview")
overview_cols = st.columns(len(CITIES))
city_data_cache = {}
for i, city in enumerate(CITIES):
    d = fetch_aqi(city)
    city_data_cache[city] = d
    with overview_cols[i]:
        if d:
            cat, col = aqi_category(d["aqi"])
            mini_card(city, d["aqi"], cat, col)
        else:
            st.markdown(f"<div style='padding:16px;color:#999;'>{city}<br>no data</div>", unsafe_allow_html=True)

st.divider()

selected_city = st.selectbox("Explore a city in detail", CITIES)

data = city_data_cache.get(selected_city) or fetch_aqi(selected_city)

if data is None:
    st.error("Could not fetch live data for this city. Check your WAQI_TOKEN in secrets.")
else:
    aqi = data["aqi"]
    category, color = aqi_category(aqi)
    lat, lon = data["city"]["geo"]

    left, right = st.columns([1, 1.4])
    with left:
        aqi_gauge(aqi, category, color)
        st.caption(f"Last updated: {data.get('time', {}).get('s', 'N/A')}")
    with right:
        clean_map(selected_city, aqi, category, color, lat, lon)

    forecast_daily = data.get("forecast", {}).get("daily", {}).get("pm25", [])
    forecast_chart(selected_city, forecast_daily, color)

    advisory = generate_advisory(selected_city, aqi, category)
    advisory_box(advisory, color)
