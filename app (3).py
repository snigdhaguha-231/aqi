"""
Urban Air Quality Intelligence Dashboard — v3 (aqi.in-style layout)
------------------------------------------------------------------------
Multi-city overview + comparison chart, a horizontal severity scale bar,
real weather (temperature/humidity/wind/pressure from the WAQI station
itself), a tomorrow's-forecast card, and a language switcher covering
English + 5 major Indian languages (Hindi, Bengali, Telugu, Marathi, Tamil).

Note on pollen data: there is no free, no-signup pollen API with real
coverage (Google Pollen, Ambee, BreezoMeter all require paid/billing
plans). Rather than fabricate numbers, the pollen card is shown but
clearly labeled as unavailable on the free tier.
"""

import streamlit as st
import requests
import numpy as np
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Urban Air Quality Intelligence", layout="wide")

WAQI_TOKEN = st.secrets.get("WAQI_TOKEN", "demo")

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
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


# ---------------------------------------------------------------------------
# LANGUAGE STRINGS
# ---------------------------------------------------------------------------
LANGUAGES = {
    "English": "en", "हिंदी": "hi", "বাংলা": "bn",
    "తెలుగు": "te", "मराठी": "mr", "தமிழ்": "ta",
}

UI = {
    "title": {"en": "Urban Air Quality Intelligence Dashboard", "hi": "शहरी वायु गुणवत्ता डैशबोर्ड",
              "bn": "শহুরে বায়ু মান ড্যাশবোর্ড", "te": "పట్టణ గాలి నాణ్యత డాష్‌బోర్డ్",
              "mr": "शहरी हवा गुणवत्ता डॅशबोर्ड", "ta": "நகர்ப்புற காற்று தர டாஷ்போர்டு"},
    "overview": {"en": "City overview", "hi": "शहरों का अवलोकन", "bn": "শহরের সংক্ষিপ্ত বিবরণ",
                 "te": "నగర అవలోకనం", "mr": "शहराचा आढावा", "ta": "நகர மேலோட்டம்"},
    "explore": {"en": "Explore a city in detail", "hi": "किसी शहर का विस्तार से अन्वेषण करें",
                "bn": "একটি শহর বিস্তারিতভাবে দেখুন", "te": "ఒక నగరాన్ని వివరంగా చూడండి",
                "mr": "एखाद्या शहराची सविस्तर माहिती पहा", "ta": "ஒரு நகரத்தை விரிவாக ஆராயுங்கள்"},
    "compare_title": {"en": "Compare cities", "hi": "शहरों की तुलना करें", "bn": "শহরগুলি তুলনা করুন",
                       "te": "నగరాలను పోల్చండి", "mr": "शहरांची तुलना करा", "ta": "நகரங்களை ஒப்பிடுக"},
    "select_cities": {"en": "Select cities to compare", "hi": "तुलना के लिए शहर चुनें",
                       "bn": "তুলনা করার জন্য শহর নির্বাচন করুন", "te": "పోల్చడానికి నగరాలను ఎంచుకోండి",
                       "mr": "तुलनेसाठी शहरे निवडा", "ta": "ஒப்பிட நகரங்களைத் தேர்ந்தெடுக்கவும்"},
    "current_aqi": {"en": "Current AQI", "hi": "वर्तमान एक्यूआई", "bn": "বর্তমান একিউআই",
                     "te": "ప్రస్తుత ఏక్యూఐ", "mr": "सध्याचा एक्यूआय", "ta": "தற்போதைய AQI"},
    "tomorrow": {"en": "Tomorrow's forecast", "hi": "कल का पूर्वानुमान", "bn": "আগামীকালের পূর্বাভাস",
                 "te": "రేపటి సూచన", "mr": "उद्याचा अंदाज", "ta": "நாளைய முன்னறிவிப்பு"},
    "advisory": {"en": "Health advisory", "hi": "स्वास्थ्य सलाह", "bn": "স্বাস্থ্য পরামর্শ",
                 "te": "ఆరోగ్య సలహా", "mr": "आरोग्य सल्ला", "ta": "சுகாதார அறிவுரை"},
    "temperature": {"en": "Temperature", "hi": "तापमान", "bn": "তাপমাত্রা", "te": "ఉష్ణోగ్రత",
                     "mr": "तापमान", "ta": "வெப்பநிலை"},
    "humidity": {"en": "Humidity", "hi": "नमी", "bn": "আর্দ্রতা", "te": "తేమ", "mr": "आर्द्रता", "ta": "ஈரப்பதம்"},
    "wind": {"en": "Wind", "hi": "हवा", "bn": "বাতাস", "te": "గాలి", "mr": "वारा", "ta": "காற்று"},
    "pressure": {"en": "Pressure", "hi": "दबाव", "bn": "চাপ", "te": "పీడనం", "mr": "दाब", "ta": "அழுத்தம்"},
    "pollen": {"en": "Pollen", "hi": "पराग", "bn": "পরাগ", "te": "పుప్పొడి", "mr": "परागकण", "ta": "மகரந்தம்"},
    "pollen_na": {"en": "Not available on free tier", "hi": "निःशुल्क योजना में उपलब्ध नहीं",
                  "bn": "ফ্রি প্ল্যানে উপলব্ধ নয়", "te": "ఉచిత ప్లాన్‌లో అందుబాటులో లేదు",
                  "mr": "मोफत योजनेत उपलब्ध नाही", "ta": "இலவச திட்டத்தில் கிடைக்கவில்லை"},
    "last_updated": {"en": "Last updated", "hi": "अंतिम अद्यतन", "bn": "সর্বশেষ আপডেট",
                      "te": "చివరిగా నవీకరించబడింది", "mr": "शेवटचे अद्यतन", "ta": "கடைசியாக புதுப்பிக்கப்பட்டது"},
    "language": {"en": "Language", "hi": "भाषा", "bn": "ভাষা", "te": "భాష", "mr": "भाषा", "ta": "மொழி"},
    "refresh": {"en": "🔄 Refresh now", "hi": "🔄 अभी ताज़ा करें", "bn": "🔄 এখনই রিফ্রেশ করুন",
                "te": "🔄 ఇప్పుడు రిఫ్రెష్ చేయండి", "mr": "🔄 आता रिफ्रेश करा", "ta": "🔄 இப்போது புதுப்பிக்கவும்"},
}

CATEGORY_LABELS = {
    "Good": {"en": "Good", "hi": "अच्छी", "bn": "ভালো", "te": "మంచిది", "mr": "चांगली", "ta": "நல்லது"},
    "Satisfactory": {"en": "Satisfactory", "hi": "संतोषजनक", "bn": "সন্তোষজনক", "te": "సంతృప్తికరం",
                      "mr": "समाधानकारक", "ta": "திருப்திகரமானது"},
    "Moderate": {"en": "Moderate", "hi": "मध्यम", "bn": "মাঝারি", "te": "మధ్యస్తం", "mr": "मध्यम", "ta": "மிதமானது"},
    "Poor": {"en": "Poor", "hi": "खराब", "bn": "খারাপ", "te": "పేలవం", "mr": "वाईट", "ta": "மோசமானது"},
    "Very Poor": {"en": "Very Poor", "hi": "बहुत खराब", "bn": "খুব খারাপ", "te": "చాలా పేలవం",
                   "mr": "खूप वाईट", "ta": "மிக மோசமானது"},
    "Severe": {"en": "Severe", "hi": "गंभीर", "bn": "গুরুতর", "te": "తీవ్రం", "mr": "गंभीर", "ta": "கடுமையானது"},
}

ADVISORY_TEMPLATES = {
    "bad": {  # Very Poor / Severe
        "en": "Avoid outdoor activity in {city}, especially for children, the elderly, and people with respiratory or heart conditions.",
        "hi": "{city} में बाहरी गतिविधियों से बचें, विशेष रूप से बच्चों, बुजुर्गों और श्वास या हृदय संबंधी समस्याओं वाले लोगों के लिए।",
        "bn": "{city}-এ বাইরের কার্যকলাপ এড়িয়ে চলুন, বিশেষ করে শিশু, বয়স্ক এবং শ্বাসকষ্ট বা হৃদরোগে আক্রান্ত ব্যক্তিদের জন্য।",
        "te": "{city}లో బహిరంగ కార్యకలాపాలను నివారించండి, ముఖ్యంగా పిల్లలు, వృద్ధులు మరియు శ్వాసకోశ లేదా గుండె సమస్యలు ఉన్నవారికి.",
        "mr": "{city} मध्ये बाहेरील क्रियाकलाप टाळा, विशेषतः लहान मुले, वृद्ध आणि श्वसन किंवा हृदयविकार असलेल्या लोकांसाठी.",
        "ta": "{city} இல் வெளிப்புற செயல்பாடுகளைத் தவிர்க்கவும், குறிப்பாக குழந்தைகள், முதியவர்கள் மற்றும் சுவாச அல்லது இதய பிரச்சனைகள் உள்ளவர்களுக்கு.",
    },
    "poor": {
        "en": "Sensitive groups in {city} should limit prolonged outdoor exertion.",
        "hi": "{city} में संवेदनशील समूहों को लंबे समय तक बाहरी परिश्रम सीमित करना चाहिए।",
        "bn": "{city}-এ সংবেদনশীল গোষ্ঠীর দীর্ঘ সময় বাইরে পরিশ্রম সীমিত করা উচিত।",
        "te": "{city}లో సున్నితమైన వర్గాలు ఎక్కువ సేపు బహిరంగ శ్రమను పరిమితం చేసుకోవాలి.",
        "mr": "{city} मधील संवेदनशील गटांनी दीर्घकाळ बाहेरील श्रम मर्यादित करावेत.",
        "ta": "{city} இல் உணர்திறன் கொண்ட குழுக்கள் நீண்ட நேர வெளிப்புற உழைப்பைக் கட்டுப்படுத்த வேண்டும்.",
    },
    "moderate": {
        "en": "Acceptable for most people in {city}, but sensitive individuals should take care.",
        "hi": "{city} में अधिकांश लोगों के लिए स्वीकार्य, लेकिन संवेदनशील व्यक्तियों को सावधानी बरतनी चाहिए।",
        "bn": "{city}-এ বেশিরভাগ মানুষের জন্য গ্রহণযোগ্য, তবে সংবেদনশীল ব্যক্তিদের সতর্ক থাকা উচিত।",
        "te": "{city}లో చాలామందికి ఆమోదయోగ్యం, కానీ సున్నితమైన వ్యక్తులు జాగ్రత్త వహించాలి.",
        "mr": "{city} मध्ये बहुतेक लोकांसाठी स्वीकार्य, पण संवेदनशील व्यक्तींनी काळजी घ्यावी.",
        "ta": "{city} இல் பெரும்பாலான மக்களுக்கு ஏற்றது, ஆனால் உணர்திறன் உள்ளவர்கள் கவனமாக இருக்க வேண்டும்.",
    },
    "good": {
        "en": "Great day to be outdoors in {city}.",
        "hi": "{city} में बाहर समय बिताने के लिए बढ़िया दिन है।",
        "bn": "{city}-এ বাইরে সময় কাটানোর জন্য দারুণ দিন।",
        "te": "{city}లో బయట గడపడానికి చక్కటి రోజు.",
        "mr": "{city} मध्ये बाहेर वेळ घालवण्यासाठी उत्तम दिवस आहे.",
        "ta": "{city} இல் வெளியே நேரம் செலவிட சிறந்த நாள்.",
    },
}


def t(key, lang):
    return UI[key].get(lang, UI[key]["en"])


def category_label(category, lang):
    return CATEGORY_LABELS[category].get(lang, category)


def generate_advisory(city, category, lang):
    if category in ("Very Poor", "Severe"):
        template = ADVISORY_TEMPLATES["bad"]
    elif category == "Poor":
        template = ADVISORY_TEMPLATES["poor"]
    elif category == "Moderate":
        template = ADVISORY_TEMPLATES["moderate"]
    else:
        template = ADVISORY_TEMPLATES["good"]
    return template.get(lang, template["en"]).format(city=city)


# ---------------------------------------------------------------------------
# DATA
# ---------------------------------------------------------------------------
@st.cache_data(ttl=180)
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


def get_tomorrow_forecast(data):
    """Prefer WAQI's own forecast.daily.pm25 for tomorrow's date; fall back
    to a simple linear trend over whatever forecast points exist."""
    forecast_daily = data.get("forecast", {}).get("daily", {}).get("pm25", [])
    if not forecast_daily:
        return None
    tomorrow_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    for entry in forecast_daily:
        if entry.get("day") == tomorrow_str:
            return entry.get("avg")
    # fall back: second entry if present, else trend over averages
    if len(forecast_daily) > 1:
        return forecast_daily[1].get("avg")
    return simple_forecast([e.get("avg") for e in forecast_daily])


def get_weather(data):
    iaqi = data.get("iaqi", {})
    return {
        "temperature": iaqi.get("t", {}).get("v"),
        "humidity": iaqi.get("h", {}).get("v"),
        "wind": iaqi.get("w", {}).get("v"),
        "pressure": iaqi.get("p", {}).get("v"),
    }


# ---------------------------------------------------------------------------
# UI COMPONENTS
# ---------------------------------------------------------------------------
def mini_card(city, aqi, category, color, weather, lang):
    temp = weather["temperature"]
    temp_str = f"{temp}°C" if temp is not None else "—"
    st.markdown(f"""
    <div style="
        border-radius: 14px; padding: 16px 18px;
        background: linear-gradient(135deg, {color}22, {color}08);
        border: 1px solid {color}55; text-align: left;">
      <div style="font-size:13px; color:#666; text-transform:uppercase; letter-spacing:0.5px;">{city}</div>
      <div style="font-size:32px; font-weight:700; color:{color};">{aqi}</div>
      <div style="font-size:13px; font-weight:600; color:{color};">{category_label(category, lang)}</div>
      <div style="font-size:12px; color:#888; margin-top:4px;">🌡️ {temp_str}</div>
    </div>
    """, unsafe_allow_html=True)


def scale_bar(aqi, lang):
    marker_pct = min(max(aqi, 0), 500) / 500 * 100
    segments = "".join(
        f'<div style="flex:{weight}; background:{color};"></div>'
        for weight, color in [(50, "#4CAF50"), (50, "#8BC34A"), (100, "#FFC107"),
                               (100, "#FF9800"), (100, "#F44336"), (100, "#9C27B0")]
    )
    st.markdown(f"""
    <div style="max-width:480px; margin-top:6px;">
      <div style="position:relative; height:22px;">
        <div style="position:absolute; left:{marker_pct}%; top:-16px; transform:translateX(-50%);
                    font-size:14px;">▼</div>
      </div>
      <div style="display:flex; height:12px; border-radius:6px; overflow:hidden;">{segments}</div>
      <div style="display:flex; justify-content:space-between; font-size:10px; color:#888; margin-top:3px;">
        <span>0</span><span>50</span><span>100</span><span>200</span><span>300</span><span>400</span><span>500</span>
      </div>
    </div>
    """, unsafe_allow_html=True)


def weather_row(weather, lang):
    cols = st.columns(4)
    items = [
        ("🌡️", t("temperature", lang), f"{weather['temperature']}°C" if weather["temperature"] is not None else "—"),
        ("💧", t("humidity", lang), f"{weather['humidity']}%" if weather["humidity"] is not None else "—"),
        ("🌬️", t("wind", lang), f"{weather['wind']} m/s" if weather["wind"] is not None else "—"),
        ("🔽", t("pressure", lang), f"{weather['pressure']} hPa" if weather["pressure"] is not None else "—"),
    ]
    for col, (icon, label, value) in zip(cols, items):
        with col:
            st.markdown(f"""
            <div style="text-align:center; padding:10px; border-radius:10px; background:#f5f5f5;">
              <div style="font-size:20px;">{icon}</div>
              <div style="font-size:11px; color:#777;">{label}</div>
              <div style="font-size:15px; font-weight:600;">{value}</div>
            </div>
            """, unsafe_allow_html=True)


def pollen_card(lang):
    st.markdown(f"""
    <div style="padding:10px; border-radius:10px; background:#f5f5f5; text-align:center; opacity:0.6;">
      <div style="font-size:20px;">🌼</div>
      <div style="font-size:11px; color:#777;">{t("pollen", lang)}</div>
      <div style="font-size:12px; font-weight:600;">{t("pollen_na", lang)}</div>
    </div>
    """, unsafe_allow_html=True)


def tomorrow_card(tomorrow_aqi, lang):
    if tomorrow_aqi is None:
        return
    category, color = aqi_category(tomorrow_aqi)
    st.markdown(f"""
    <div style="
        border-radius: 14px; padding: 16px 18px; margin-top:10px;
        background: linear-gradient(135deg, {color}18, {color}05);
        border: 1px dashed {color}77;">
      <div style="font-size:13px; color:#666;">{t("tomorrow", lang)}</div>
      <div style="font-size:28px; font-weight:700; color:{color};">{tomorrow_aqi}</div>
      <div style="font-size:13px; font-weight:600; color:{color};">{category_label(category, lang)}</div>
    </div>
    """, unsafe_allow_html=True)


def advisory_box(text, color, lang):
    st.markdown(f"""
    <div style="
        border-left: 5px solid {color}; background: {color}10;
        padding: 14px 18px; border-radius: 8px; font-size: 14px;
        color:#333; margin-top: 10px;">
      <b>{t("advisory", lang)}:</b> {text}
    </div>
    """, unsafe_allow_html=True)


def aqi_gauge(aqi, category, color, lang):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=aqi,
        number={"font": {"size": 34, "color": color}},
        title={"text": category_label(category, lang), "font": {"size": 15}},
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
    fig.update_layout(height=230, margin=dict(l=10, r=10, t=40, b=10))
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
    fig.update_layout(title=f"{city} — PM2.5 forecast (avg)", height=260,
                       margin=dict(l=30, r=20, t=50, b=30), plot_bgcolor="white", yaxis_title="PM2.5")
    st.plotly_chart(fig, use_container_width=True)


def clean_map(city, aqi, category, color, lat, lon):
    m = folium.Map(location=[lat, lon], zoom_start=10, tiles="CartoDB positron")
    folium.Circle(location=[lat, lon], radius=3000, color=color, weight=1,
                  fill=True, fill_color=color, fill_opacity=0.15).add_to(m)
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
    st_folium(m, width=None, height=340, use_container_width=True)


def comparison_chart(cities, city_data_cache, lang):
    rows = [(c, city_data_cache[c]["aqi"]) for c in cities if city_data_cache.get(c)]
    if not rows:
        return
    rows.sort(key=lambda r: r[1], reverse=True)
    names = [r[0] for r in rows]
    values = [r[1] for r in rows]
    colors = [aqi_category(v)[1] for v in values]
    fig = go.Figure(go.Bar(x=names, y=values, marker_color=colors, text=values, textposition="outside"))
    fig.update_layout(height=320, margin=dict(l=20, r=20, t=20, b=20), plot_bgcolor="white", yaxis_title="AQI")
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# LAYOUT
# ---------------------------------------------------------------------------
top_left, top_right = st.columns([4, 1.3])
with top_right:
    lang_name = st.selectbox(" ", list(LANGUAGES.keys()), label_visibility="collapsed")
    lang = LANGUAGES[lang_name]

with top_left:
    st.title("🌆 " + t("title", lang))

refresh_col = st.columns([1, 5])[0]
with refresh_col:
    if st.button(t("refresh", lang)):
        fetch_aqi.clear()
        st.rerun()

st.subheader(t("overview", lang))
overview_cols = st.columns(len(CITIES))
city_data_cache = {}
for i, city in enumerate(CITIES):
    d = fetch_aqi(city)
    city_data_cache[city] = d
    with overview_cols[i]:
        if d:
            cat, col = aqi_category(d["aqi"])
            mini_card(city, d["aqi"], cat, col, get_weather(d), lang)
        else:
            st.markdown(f"<div style='padding:16px;color:#999;'>{city}<br>—</div>", unsafe_allow_html=True)

st.divider()

# ---- Comparison ----
st.subheader(t("compare_title", lang))
compare_cities = st.multiselect(t("select_cities", lang), CITIES, default=CITIES)
comparison_chart(compare_cities, city_data_cache, lang)

st.divider()

# ---- Detail panel ----
selected_city = st.selectbox(t("explore", lang), CITIES)
data = city_data_cache.get(selected_city) or fetch_aqi(selected_city)

if data is None:
    st.error("Could not fetch live data for this city. Check your WAQI_TOKEN in secrets.")
else:
    aqi = data["aqi"]
    category, color = aqi_category(aqi)
    lat, lon = data["city"]["geo"]
    weather = get_weather(data)

    left, right = st.columns([1, 1.4])
    with left:
        aqi_gauge(aqi, category, color, lang)
        scale_bar(aqi, lang)
        st.caption(f"{t('last_updated', lang)}: {data.get('time', {}).get('s', 'N/A')}")
    with right:
        clean_map(selected_city, aqi, category, color, lat, lon)

    st.markdown("<br>", unsafe_allow_html=True)
    weather_cols = st.columns([4, 1])
    with weather_cols[0]:
        weather_row(weather, lang)
    with weather_cols[1]:
        pollen_card(lang)

    tomorrow_aqi = get_tomorrow_forecast(data)
    tomorrow_card(tomorrow_aqi, lang)

    forecast_daily = data.get("forecast", {}).get("daily", {}).get("pm25", [])
    forecast_chart(selected_city, forecast_daily, color)

    advisory = generate_advisory(selected_city, category, lang)
    advisory_box(advisory, color, lang)
