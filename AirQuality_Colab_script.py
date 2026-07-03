"""
Urban Air Quality Intelligence — script version of the Colab notebook
------------------------------------------------------------------------
This is the SAME logic as AirQuality_Colab.ipynb, converted to a plain
.py file for the GitHub repo (notebooks aren't valid Python scripts on
their own, so this is what makes the same code reviewable/runnable
outside Jupyter).

IMPORTANT — where this can actually run:
- The map/chart rendering (display(), fig.show(), ipywidgets) needs a
  notebook environment (Jupyter, JupyterLab, or Google Colab). Running
  this in a plain terminal will execute the logic but will NOT show the
  map/chart/dropdown visually.
- If you want a real terminal/production script, use the deployed
  Streamlit version (app.py) instead — that's built for a browser, not
  a notebook kernel.

To run this file itself in a notebook environment:
    1. Open Jupyter/JupyterLab/Colab
    2. Either paste this file's content into cells, or run:
       %run AirQuality_Colab_script.py
    3. First install dependencies (run once, in a notebook cell or terminal):
       pip install requests pandas numpy folium ipywidgets anthropic plotly
"""

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
WAQI_TOKEN = "PASTE_YOUR_TOKEN_HERE"
ANTHROPIC_API_KEY = ""  # optional, only needed for call_llm_advisory()

CITIES = ["Delhi", "Mumbai", "Kolkata", "Bengaluru", "Chennai", "Hyderabad", "Pune"]

# ---------------------------------------------------------------------------
# DATA FETCHING + COLOR SYSTEM
# ---------------------------------------------------------------------------
import requests

def fetch_aqi(city: str):
    url = f"https://api.waqi.info/feed/{city}/?token={WAQI_TOKEN}"
    r = requests.get(url, timeout=10)
    data = r.json()
    if data.get("status") != "ok":
        print(f"Could not fetch data for {city}: {data.get('data')}")
        return None
    return data["data"]

# One color per category, reused for the card, gauge, map marker, and advisory box
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


# ---------------------------------------------------------------------------
# FORECAST
# ---------------------------------------------------------------------------
import numpy as np

def simple_forecast(history_values):
    if len(history_values) < 2:
        return history_values[-1] if history_values else None
    x = np.arange(len(history_values))
    y = np.array(history_values, dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    return max(0, round(slope * len(history_values) + intercept, 1))


# ---------------------------------------------------------------------------
# HEALTH ADVISORY (rule-based; call_llm_advisory() below is the optional upgrade)
# ---------------------------------------------------------------------------
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
# VISUAL OUTPUT — card, gauge, map, forecast chart
# (requires a notebook environment for display() to render anything)
# ---------------------------------------------------------------------------
import folium
import plotly.graph_objects as go
from IPython.display import display, HTML


def hex_to_rgba(hex_color: str, alpha: float) -> str:
    """Plotly rejects 8-digit hex (hex+alpha) in chart color fields, so
    convert to rgba() wherever a translucent Plotly fill is needed."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def styled_card(city, aqi, category, color, last_updated):
    html = f"""
    <div style="
        font-family: 'Segoe UI', Arial, sans-serif;
        max-width: 480px;
        border-radius: 16px;
        padding: 24px 28px;
        background: linear-gradient(135deg, {color}22, {color}08);
        border: 1px solid {color}55;
        box-shadow: 0 4px 14px rgba(0,0,0,0.08);
        margin-bottom: 12px;">
      <div style="font-size: 14px; color: #666; letter-spacing: 0.5px; text-transform: uppercase;">
        {city}
      </div>
      <div style="display:flex; align-items:baseline; gap:12px; margin-top:4px;">
        <span style="font-size: 48px; font-weight: 700; color:{color};">{aqi}</span>
        <span style="font-size: 18px; font-weight: 600; color:{color};
                     background:{color}22; padding:4px 12px; border-radius:20px;">
          {category}
        </span>
      </div>
      <div style="font-size: 12px; color: #999; margin-top: 8px;">
        Last updated: {last_updated}
      </div>
    </div>
    """
    display(HTML(html))


def styled_advisory(text, color):
    html = f"""
    <div style="
        font-family: 'Segoe UI', Arial, sans-serif;
        max-width: 480px;
        border-left: 5px solid {color};
        background: {color}10;
        padding: 14px 18px;
        border-radius: 8px;
        font-size: 14px;
        color: #333;
        margin-top: 8px;">
      <b>Health advisory:</b> {text}
    </div>
    """
    display(HTML(html))


def aqi_gauge(aqi, category, color):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=aqi,
        number={"font": {"size": 36, "color": color}},
        title={"text": category, "font": {"size": 16}},
        gauge={
            "axis": {"range": [0, 500], "tickwidth": 1},
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
    fig.update_layout(height=260, margin=dict(l=20, r=20, t=40, b=10))
    fig.show()


def forecast_chart(city, forecast_daily, color):
    if not forecast_daily:
        print("No multi-day forecast available for this city from the API.")
        return
    days = [d["day"] for d in forecast_daily]
    avg = [d["avg"] for d in forecast_daily]
    fig = go.Figure(go.Scatter(
        x=days, y=avg, mode="lines+markers",
        line=dict(color=color, width=3, shape="spline"),
        marker=dict(size=8, color=color),
        fill="tozeroy", fillcolor=hex_to_rgba(color, 0.15),
    ))
    fig.update_layout(
        title=f"{city} — PM2.5 forecast (avg)",
        height=280, margin=dict(l=30, r=20, t=50, b=30),
        plot_bgcolor="white", yaxis_title="PM2.5",
    )
    fig.show()


def clean_map(city, aqi, category, color, lat, lon):
    m = folium.Map(location=[lat, lon], zoom_start=10, tiles="CartoDB positron")
    folium.Circle(
        location=[lat, lon], radius=3000, color=color, weight=1,
        fill=True, fill_color=color, fill_opacity=0.15,
    ).add_to(m)
    folium.Marker(
        location=[lat, lon],
        icon=folium.DivIcon(html=f"""
            <div style="
                background:{color};
                color:white;
                border-radius:50%;
                width:46px; height:46px;
                display:flex; align-items:center; justify-content:center;
                font-weight:bold; font-size:14px;
                box-shadow: 0 2px 6px rgba(0,0,0,0.3);
                border: 2px solid white;">
                {aqi}
            </div>"""),
        popup=f"{city}: AQI {aqi} ({category})",
    ).add_to(m)
    display(m)


def show_city_report(city, use_llm=False):
    data = fetch_aqi(city)
    if data is None:
        return
    aqi = data["aqi"]
    category, color = aqi_category(aqi)
    lat, lon = data["city"]["geo"]
    last_updated = data.get("time", {}).get("s", "N/A")

    styled_card(city, aqi, category, color, last_updated)
    aqi_gauge(aqi, category, color)
    clean_map(city, aqi, category, color, lat, lon)

    forecast_daily = data.get("forecast", {}).get("daily", {}).get("pm25", [])
    forecast_chart(city, forecast_daily, color)

    if use_llm and ANTHROPIC_API_KEY:
        advisory = call_llm_advisory(city, aqi, category)
    else:
        advisory = generate_advisory(city, aqi, category)
    styled_advisory(advisory, color)


# ---------------------------------------------------------------------------
# INTERACTIVE DROPDOWN (notebook-only — needs ipywidgets)
# ---------------------------------------------------------------------------
def launch_dropdown():
    import ipywidgets as widgets
    from IPython.display import clear_output

    dropdown = widgets.Dropdown(options=CITIES, description="City:",
                                 style={"description_width": "initial"})
    output = widgets.Output()

    def on_change(change):
        if change["type"] == "change" and change["name"] == "value":
            with output:
                clear_output(wait=True)
                show_city_report(change["new"])

    dropdown.observe(on_change, names="value")
    display(dropdown, output)

    with output:
        show_city_report(dropdown.value)


if __name__ == "__main__":
    # Running this file directly (e.g. `python AirQuality_Colab_script.py` in a
    # plain terminal) will fetch and print data, but display()/fig.show() need
    # a notebook kernel to actually render anything visually.
    show_city_report("Delhi")
    launch_dropdown()
