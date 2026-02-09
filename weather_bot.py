#!/usr/bin/env python3
import os, requests, datetime, sys

# --- Настройки ---
LAT, LON = 52.12, 26.10
COHERE_KEY = os.getenv('COHERE_API_KEY')
GEMINI_KEY = os.getenv('GEMINI_API_KEY')
TG_TOKEN = os.getenv('TELEGRAM_TOKEN')
CH_ID = os.getenv('CHANNEL_ID')

def log(message):
    now_pinsk = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
    timestamp = now_pinsk.strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")

# --- Функции пояснения ---
def get_wind_dir(deg):
    dirs = ["С ⬇️", "СВ ↙️", "В ⬅️", "ЮВ ↖️", "Ю ⬆️", "ЮЗ ↗️", "З ➡️", "СЗ ↘️"]
    return dirs[int((deg + 22.5) % 360 / 45)]

def get_wind_power(speed, gusts):
    # Умная чувствительность: если порывы значительно выше среднего
    diff = gusts - speed
    base = ""
    if speed < 5: base = "штиль 💨"
    elif speed < 12: base = "слабый 🍃"
    elif speed < 29: base = "умеренный 🌬️"
    elif speed < 50: base = "сильный 🌪️"
    else: base = "ОЧЕНЬ СИЛЬНЫЙ ⚠️"

    if diff > 15: return f"{base} (рваный характер ⚠️)"
    return base

def get_weather_desc(code):
    codes = {
        0: "ясно", 1: "преимущественно ясно", 2: "переменная облачность", 3: "пасмурно",
        45: "туман", 48: "туман с инеем", 51: "легкая морось", 53: "морось", 55: "сильная морось",
        61: "небольшой дождь", 63: "дождь", 65: "сильный дождь", 66: "ледяной дождь ⛸",
        71: "снег", 75: "сильный снег ❄️", 80: "ливень", 95: "гроза ⛈"
    }
    return codes.get(code, "осадки")

def get_pressure_desc(p):
    if p < 745: return "(пониженное 📉)"
    if p > 755: return "(повышенное 📈)"
    return "(норма)"

def get_g_desc(g_scale):
    try:
        g = int(g_scale)
        if g == 0: return "(спокойно)"
        if g == 1: return "(слабая буря 🟡)"
        if g == 2: return "(умеренная буря 🟠)"
        if g >= 3: return "(СИЛЬНЫЙ ШТОРМ 🚨)"
        return ""
    except: return ""

def get_aqi_desc(pm25):
    if pm25 < 12: return "(чистый)"
    if pm25 < 35: return "(приемлемый)"
    return "(грязный 😷)"

def get_uv_desc(uv):
    if uv <= 2: return "Низкий ✅"
    if uv <= 5: return "Средний 🧴"
    return "Высокий 🔴"

def get_humidity_desc(h, temp):
    if h < 30: return "(сухо 🏜️)"
    if h > 70:
        return "(сыро/пронизывающий холод ❄️)" if temp < 5 else "(влажно/душно 💦)"
    return "(комфортно ✨)"

def get_visibility_desc(v_m):
    v_km = v_m / 1000
    if v_km < 1: return f"{v_km} км (туман 🌫)"
    if v_km < 4: return f"{v_km} км (дымка 🌫)"
    return f"{v_km} км (чисто ✨)"

# --- Каскад ИИ ---
def ask_ai_cascade(prompt_msg, system_preamble):
    log(f"🧠 [AI LOG] Анализ векторов Gemini 3 Flash...")
    if GEMINI_KEY:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={GEMINI_KEY}"
            payload = {"contents": [{"parts": [{"text": f"{system_preamble}\n\nВЕКТОРНЫЕ ДАННЫЕ:\n{prompt_msg}"}]}]}
            res = requests.post(url, json=payload, timeout=90)
            if res.status_code == 200:
                return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        except Exception as e: log(f"❌ [AI LOG] Gemini error: {e}")

    if COHERE_KEY:
        try:
            res = requests.post("https://api.cohere.ai/v1/chat",
                                headers={"Authorization": f"Bearer {COHERE_KEY}"},
                                json={"message": prompt_msg, "model": "command-r-plus-08-2024", "preamble": system_preamble},
                                timeout=60)
            if res.status_code == 200: return res.json().get('text', '').strip()
        except: pass
    return "Аналитика сейчас недоступна."

def main():
    log("🚀 [Belgidromet Log] Сбор данных (72ч архив + прогноз)...")
    try:
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}"
               f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,surface_pressure,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m,cloud_cover,uv_index,visibility,dew_point_2m"
               f"&hourly=temperature_2m,surface_pressure,relative_humidity_2m,wind_speed_10m,wind_gusts_10m,precipitation,precipitation_probability,weather_code,visibility,dew_point_2m,soil_temperature_0cm,cloud_cover"
               f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max,sunrise,sunset&past_days=3&timezone=auto")
        data = requests.get(url, timeout=15).json()
    except Exception as e: log(f"❌ API Error: {e}"); sys.exit(1)

    cur, h_data, d_data = data['current'], data['hourly'], data['daily']
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
    hour, dow, idx_now = now.hour, now.weekday(), 72 + now.hour

    # --- Подготовка Векторов (72ч под капотом) ---
    p_now = cur['surface_pressure']
    p_72h = h_data['surface_pressure'][idx_now - 72]
    p_trend = "Rapidly Falling" if p_now - p_72h < -10 else "Rising" if p_now - p_72h > 10 else "Stable"

    t_delta_72 = round(cur['temperature_2m'] - h_data['temperature_2m'][idx_now - 72], 1)
    hum_trend = "Increasing Moisture" if cur['relative_humidity_2m'] - h_data['relative_humidity_2m'][idx_now - 72] > 20 else "Stable"

    precip_72h = sum(h_data['precipitation'][idx_now-72:idx_now])
    soil_status = "Oversaturated" if precip_72h > 15 else "Dry"

    dew_spread = abs(cur['temperature_2m'] - cur['dew_point_2m'])
    fog_risk = "High Fog/Ice Risk" if dew_spread < 2 else "Low Risk"

    # Магнитный фон (G-Scale NOAA)
    g_now = 0
    try:
        g_res = requests.get("https://services.swpc.noaa.gov/products/noaa-scales.json", timeout=10).json()
        g_now = int(g_res['0']['G']['Scale'])
    except: log("⚠️ [Belgidromet Log] G-Scale API error.")

    # Воздух
    pm25 = 0.0
    try:
        aq_res = requests.get(f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={LAT}&longitude={LON}&current=pm2_5", timeout=10).json()
        pm25 = aq_res['current']['pm2_5']
    except: pass

    # --- Сборка уровней опасности ---
    danger_alerts = []
    gusts = cur.get('wind_gusts_10m', 0)
    if gusts >= 90: danger_alerts.append("🚨 **КРАСНЫЙ УРОВЕНЬ:** Ураган! (90+ км/ч)")
    elif gusts >= 54: danger_alerts.append("🟠 **ОРАНЖЕВЫЙ УРОВЕНЬ:** Сильный ветер! (54+ км/ч)")

    if g_now >= 3: danger_alerts.append(f"🚨 **КРАСНЫЙ УРОВЕНЬ:** Сильный шторм! (Scale G{g_now})")
    elif g_now >= 2: danger_alerts.append(f"🟠 **ОРАНЖЕВЫЙ УРОВЕНЬ:** Умеренная буря! (Scale G{g_now})")

    if cur['temperature_2m'] >= 30 or cur['temperature_2m'] <= -25: danger_alerts.append("🟠 **ОРАНЖЕВЫЙ УРОВЕНЬ:** Опасная температура!")
    if cur['weather_code'] in [66, 67] or (cur['temperature_2m'] < 1 and h_data['soil_temperature_0cm'][idx_now] < 0 and sum(h_data['precipitation'][idx_now-6:idx_now]) > 0):
        danger_alerts.append("🟠 **ОРАНЖЕВЫЙ УРОВЕНЬ:** Гололедица! ⛸️")

    # --- Универсальные Промты ---
    ai_text = ""
    common_rules = "Запрещено: «вероятно», «возможно», «может быть». Используй термины циклон/антициклон. Адаптируй советы под сезон. Максимум 3 предложения."

    if 5 <= hour < 14:
        tag, label = "🌅", "#прогнозутро"
        preamble = f"Ты — метеоролог-профи. Дай четкий план на день. {common_rules}"
    elif hour >= 20 or hour < 5:
        tag, label = "🌙", "#прогнозвечер"
        preamble = f"Ты — ночной синоптик. Оцени сон и утро (G-Scale, туман, гололед). {common_rules}"
    else: tag, label, preamble = "🌤️", "#прогноздень", None

    if preamble:
        vectors = f"P_Trend_72h: {p_trend}, T_Delta_72h: {t_delta_72}, Soil: {soil_status}, Hum_Trend: {hum_trend}, Fog_Risk: {fog_risk}, G_Scale: {g_now}, AQI: {pm25}."
        ai_text = ask_ai_cascade(vectors, preamble)

    # Осадки (ближайшие 12ч)
    precip_info = "без осадков"
    for i in range(idx_now, idx_now + 12):
        if h_data['precipitation'][i] > 0.01 or h_data['precipitation_probability'][i] > 5:
            precip_info = f"{get_weather_desc(h_data['weather_code'][i])} около {i % 24:02d}:00"
            break

    # Сборка сообщения
    press_mm = int(cur['surface_pressure'] * 0.750062)
    warning_block = ("\n" + "\n".join(danger_alerts) + "\n") if danger_alerts else ""

    msg = (f"{tag} {label}\n\n🏙 **Пинск сейчас:**\n"
           f"🌡 Температура: {cur['temperature_2m']}°C (ощущ. {cur['apparent_temperature']}°C)\n"
           f"☁️ Облачность: {cur['cloud_cover']}% ({get_weather_desc(cur['weather_code'])})\n"
           f"🌧 Осадки: {precip_info}\n"
           f"💨 Ветер: {cur['wind_speed_10m']} км/ч (порывы {gusts} км/ч) {get_wind_dir(cur['wind_direction_10m'])} ({get_wind_power(cur['wind_speed_10m'], gusts)})\n"
           f"💧 Влажность: {cur['relative_humidity_2m']}% {get_humidity_desc(cur['relative_humidity_2m'], cur['temperature_2m'])}\n"
           f"📈 Давление: {press_mm} мм {get_pressure_desc(press_mm)}\n"
           f"🧲 Магнитный фон: G{g_now} {get_g_desc(g_now)}\n"
           f"☀️ УФ-индекс: {cur['uv_index']} {get_uv_desc(cur['uv_index'])}\n"
           f"✨ Видимость: {get_visibility_desc(cur['visibility'])}\n"
           f"🕒 Световой день: {d_data['sunrise'][3][-5:]} — {d_data['sunset'][3][-5:]}\n"
           f"🍃 Воздух: {pm25} PM2.5 {get_aqi_desc(pm25)}\n"
           f"{warning_block}\n📝 **Аналитика:**\n{ai_text}")

    requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", json={"chat_id": CH_ID, "text": msg, "parse_mode": "Markdown"})

    # --- СТРАТЕГИЯ НА 3 ДНЯ (СР и ВС) ---
    if hour >= 20 and dow in [2, 6]:
        day_blocks = []
        for i in range(4, 7):
            idx = i * 24
            d_name = (now + datetime.timedelta(days=i-3)).strftime('%a, %d.%m').replace('Mon','Пн').replace('Tue','Вт').replace('Wed','Ср').replace('Thu','Чт').replace('Fri','Пт').replace('Sat','Сб').replace('Sun','Вс')
            block = (f"📅 **{d_name}**\n🌡 {d_data['temperature_2m_min'][i]}..{d_data['temperature_2m_max'][i]}°C\n"
                     f"🌧 {get_weather_desc(h_data['weather_code'][idx+12])}\n💨 Порывы: {d_data['wind_gusts_10m_max'][i]} км/ч")
            day_blocks.append(block)

        strat_preamble = f"Ты — главный климатолог. Выяви сюжет на 3 дня на основе векторов последних 72 часов. {common_rules}"
        strat_ai = ask_ai_cascade(f"Future: {day_blocks}, History_Vect: {p_trend}, {t_delta_72}", strat_preamble)

        final_strat = "🗓 #прогноз3дня\n🔭 **АНАЛИЗ НА 3 ДНЯ**\n\n" + "\n\n".join(day_blocks) + f"\n\n🏛 **СТРАТЕГИЯ:**\n{strat_ai}"
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", json={"chat_id": CH_ID, "text": final_strat, "parse_mode": "Markdown"})

if __name__ == "__main__":
    main()
