#!/usr/bin/env python3
import os, requests, datetime, sys

# --- Настройки ---
LAT, LON = 52.12, 26.10
GEMINI_KEY = os.getenv('GEMINI_API_KEY')
COHERE_KEY = os.getenv('COHERE_API_KEY')
MISTRAL_KEY = os.getenv('MISTRAL_API_KEY')
GROQ_KEY = os.getenv('GROQ_API_KEY')
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

def get_precip_detailed(h_data, start_idx, hours_to_scan):
    start_h, end_h, p_type = None, None, "без осадков"
    max_prob = 0
    for i in range(start_idx, start_idx + hours_to_scan):
        prob = h_data['precipitation_probability'][i]
        prec = h_data['precipitation'][i]
        if prob > 20 or prec > 0.1:
            if start_h is None:
                start_h = i
                t = h_data['temperature_2m'][i]
                if t <= -1: p_type = "снег ❄️"
                elif -1 < t < 2: p_type = "мокрый снег 🌨"
                else: p_type = "дождь 🌧"
            end_h = i
            if prob > max_prob: max_prob = prob

    if start_h is not None:
        return f"{p_type} ({max_prob}%) {start_h%24:02d}:00 — {(end_h+1)%24:02d}:00"
    return "без осадков"

def get_geo_detailed(target_date=None):
    try:
        url = "https://services.swpc.noaa.gov/products/noaa-scales.json"
        res = requests.get(url, timeout=10).json()
        if not target_date:
            target_date = (datetime.datetime.utcnow() + datetime.timedelta(hours=3)).strftime('%Y-%m-%d')
        max_g = 0
        if isinstance(res, dict):
            for entry in res.values():
                if isinstance(entry, dict) and entry.get('DateStamp') == target_date:
                    g_info = entry.get('G')
                    if isinstance(g_info, dict):
                        val = g_info.get('Scale')
                        if val is not None:
                            try:
                                val_int = int(val)
                                if val_int > max_g: max_g = val_int
                            except: continue
        desc = get_g_desc(max_g)
        return f"G{max_g} {desc}", max_g
    except Exception as e:
        log(f"⚠️ NOAA Geo Error: {e}")
        return "G0 (нет данных)", 0

def get_pressure_desc(p):
    if p < 745: return "(пониженное 📉)"
    if p > 755: return "(повышенное 📈)"
    return "(норма)"

def get_g_desc(g_scale):
    try:
        g = int(g_scale)
        if g == 0: return "(спокойно ✨)"
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

# --- Каскад ИИ (Исправлено: Краткие логи без текста ответа, остановка при успехе) ---
def ask_ai_cascade(prompt_msg, system_preamble):
    models = [
        ("Gemini", "gemini"),
        ("Cohere", "cohere"),
        ("Mistral", "mistral"),
        ("Groq", "groq")
    ]

    for name, m_type in models:
        key = globals().get(f"{name.upper()}_KEY")
        if not key: continue

        try:
            log(f"🧠 [AI] Запрос: {name}...")

            if m_type == "gemini":
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={key}"
                payload = {"contents": [{"parts": [{"text": f"{system_preamble}\n\nДАННЫЕ:\n{prompt_msg}"}]}]}
                res = requests.post(url, json=payload, timeout=40)
                if res.status_code == 200:
                    data = res.json()
                    if 'candidates' in data and data['candidates']:
                        log(f"✅ [AI] {name}: OK")
                        return data['candidates'][0]['content']['parts'][0]['text'].strip()
                log(f"❌ [AI] {name} Error: {res.status_code}")

            elif m_type == "cohere":
                res = requests.post("https://api.cohere.ai/v1/chat",
                                    headers={"Authorization": f"Bearer {key}"},
                                    json={"message": prompt_msg, "model": "command-r-plus-08-2024", "preamble": system_preamble},
                                    timeout=40)
                if res.status_code == 200:
                    log(f"✅ [AI] {name}: OK")
                    return res.json().get('text', '').strip()
                log(f"❌ [AI] {name} Error: {res.status_code}")

            elif m_type == "mistral":
                res = requests.post("https://api.mistral.ai/v1/chat/completions",
                                    headers={"Authorization": f"Bearer {key}"},
                                    json={"model": "mistral-large-latest", "messages": [{"role": "system", "content": system_preamble}, {"role": "user", "content": prompt_msg}]},
                                    timeout=30)
                if res.status_code == 200:
                    log(f"✅ [AI] {name}: OK")
                    return res.json()['choices'][0]['message']['content'].strip()
                log(f"❌ [AI] {name} Error: {res.status_code}")

            elif m_type == "groq":
                res = requests.post("https://api.groq.com/openai/v1/chat/completions",
                                    headers={"Authorization": f"Bearer {key}"},
                                    json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "system", "content": system_preamble}, {"role": "user", "content": prompt_msg}]},
                                    timeout=30)
                if res.status_code == 200:
                    log(f"✅ [AI] {name}: OK")
                    return res.json()['choices'][0]['message']['content'].strip()
                log(f"❌ [AI] {name} Error: {res.status_code}")

        except Exception as e:
            log(f"⚠️ [AI] {name} Exception: {str(e)[:40]}")
            continue

    return "Аналитика сейчас недоступна."

def main():
    log("🚀 Сбор данных...")
    try:
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}"
               f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,surface_pressure,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m,cloud_cover,uv_index,visibility,dew_point_2m"
               f"&hourly=temperature_2m,surface_pressure,relative_humidity_2m,wind_speed_10m,wind_direction_10m,wind_gusts_10m,precipitation,precipitation_probability,weather_code,visibility,dew_point_2m,soil_temperature_0cm,cloud_cover"
               f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max,sunrise,sunset&past_days=3&timezone=auto")
        data = requests.get(url, timeout=15).json()
    except Exception as e: log(f"❌ API Error: {e}"); sys.exit(1)

    cur, h_data, d_data = data['current'], data['hourly'], data['daily']
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
    hour, dow, idx_now = now.hour, now.weekday(), 72 + now.hour

    past_72h = {"t_delta": round(cur['temperature_2m'] - h_data['temperature_2m'][idx_now - 72], 1), "precip_sum": round(sum(h_data['precipitation'][idx_now-72:idx_now]), 1)}
    geo_info, g_max = get_geo_detailed()

    pm25 = 0.0
    try:
        aq_res = requests.get(f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={LAT}&longitude={LON}&current=pm2_5", timeout=10).json()
        pm25 = aq_res['current']['pm2_5']
    except: pass

    danger_alerts = []
    gusts = cur.get('wind_gusts_10m', 0)
    if gusts >= 54: danger_alerts.append(f"🟠 **ОРАНЖЕВЫЙ УРОВЕНЬ:** Ветер {gusts} км/ч!")
    if g_max >= 2: danger_alerts.append(f"🟠 **ОРАНЖЕВЫЙ УРОВЕНЬ:** Буря Scale G{g_max}!")
    if cur['temperature_2m'] < 1 and h_data['soil_temperature_0cm'][idx_now] < 0 and sum(h_data['precipitation'][idx_now-6:idx_now]) > 0:
        danger_alerts.append("🟠 **ОРАНЖЕВЫЙ УРОВЕНЬ:** Гололедица! ⛸️")

    precip_info = get_precip_detailed(h_data, idx_now, 24)
    common_rules = "Запрещено: «вероятно», «возможно», «может быть»,приветствие..3-4 предложения без цифр."
    ai_text, tag, label, preamble = "", "🌤️", "#прогноздень", None

    if 5 <= hour < 14:
        tag, label = "🌅", "#прогнозутро"
        preamble = f"Ты — метеоролог-профи на телевидении.Проанализируй массив данных и на их основе расскажи своим телезрителям какая сегодня будет погода и почему. {common_rules}"
    elif hour >= 20 or hour < 5:
        tag, label = "🌙", "#прогнозвечер"
        preamble = f"Ты — метеоролог-профи на телевидении.Проанализируй массив данных и на их основе расскажи телезрителям какая погода будет ночью и ранним утром и почему {common_rules}"

    if preamble:
        ai_payload = f"PAST: {past_72h} | CUR: T={cur['temperature_2m']}, Soil={h_data['soil_temperature_0cm'][idx_now]}, G={g_max}"
        ai_text = ask_ai_cascade(ai_payload, preamble)

    press_mm = int(cur['surface_pressure'] * 0.750062)
    warning_block = ("\n" + "\n".join(danger_alerts) + "\n") if danger_alerts else ""
    ai_section = f"\n📝 **Аналитика:**\n{ai_text}" if ai_text else ""

    msg = (f"{tag} {label}\n\n🏙 **Пинск сейчас:**\n"
           f"🌡 Температура: {cur['temperature_2m']}°C (ощущ. {cur['apparent_temperature']}°C)\n"
           f"📊 Экстремумы: {d_data['temperature_2m_min'][3]}..{d_data['temperature_2m_max'][3]}°C\n"
           f"☁️ Облачность: {cur['cloud_cover']}% ({get_weather_desc(cur['weather_code'])})\n"
           f"🌧 Осадки: {precip_info}\n"
           f"💨 Ветер: {cur['wind_speed_10m']} км/ч (порывы {gusts} км/ч) {get_wind_dir(cur['wind_direction_10m'])} ({get_wind_power(cur['wind_speed_10m'], gusts)})\n"
           f"💧 Влажность: {cur['relative_humidity_2m']}% {get_humidity_desc(cur['relative_humidity_2m'], cur['temperature_2m'])}\n"
           f"📈 Давление: {press_mm} мм {get_pressure_desc(press_mm)}\n"
           f"🧲 Магнитный фон: {geo_info}\n"
           f"☀️ УФ-индекс: {cur['uv_index']} {get_uv_desc(cur['uv_index'])}\n"
           f"✨ Видимость: {get_visibility_desc(cur['visibility'])}\n"
           f"🕒 Световой день: {d_data['sunrise'][3][-5:]} — {d_data['sunset'][3][-5:]}\n"
           f"🍃 Воздух: {pm25} PM2.5 {get_aqi_desc(pm25)}\n"
           f"{warning_block}{ai_section}")

    requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", json={"chat_id": CH_ID, "text": msg, "parse_mode": "Markdown"})

    if hour >= 20 and dow in [2, 6]:
        day_blocks = []
        for i in range(4, 7):
            idx = i * 24
            mid = idx + 12
            target_dt = now + datetime.timedelta(days=i-3)
            d_name = target_dt.strftime('%a, %d.%m').replace('Mon','Понедельник').replace('Tue','Вторник').replace('Wed','Среда').replace('Thu','Четверг').replace('Fri','Пятница').replace('Sat','Суббота').replace('Sun','Воскресение')
            p_detailed = get_precip_detailed(h_data, idx, 24)
            p_mm_day = int(h_data['surface_pressure'][mid] * 0.750062)
            geo_day, _ = get_geo_detailed(target_dt.strftime('%Y-%m-%d'))
            day_temp_min = d_data['temperature_2m_min'][i]

            # Добавлено пояснение силы ветра для 3-х дневной сводки
            wind_p_desc = get_wind_power(d_data['wind_speed_10m_max'][i], d_data['wind_gusts_10m_max'][i])

            block = (f"📅 **{d_name}**\n"
                     f"🌡 Температура: {day_temp_min}..{d_data['temperature_2m_max'][i]}°C\n"
                     f"☁️ Облачность: {h_data['cloud_cover'][mid]}% ({get_weather_desc(h_data['weather_code'][mid])})\n"
                     f"🌧 Осадки: {p_detailed}\n"
                     f"💨 Ветер: {d_data['wind_speed_10m_max'][i]} км/ч (порывы {d_data['wind_gusts_10m_max'][i]} км/ч) {get_wind_dir(h_data['wind_direction_10m'][mid])} ({wind_p_desc})\n"
                     f"💧 Влажность: {h_data['relative_humidity_2m'][mid]}% {get_humidity_desc(h_data['relative_humidity_2m'][mid], day_temp_min)}\n"
                     f"📈 Давление: {p_mm_day} мм {get_pressure_desc(p_mm_day)}\n"
                     f"🧲 Магнитный фон: {geo_day}\n"
                     f"✨ Видимость: {get_visibility_desc(h_data['visibility'][mid])}\n"
                     f"🕒 Световой день: {d_data['sunrise'][i][-5:]} — {d_data['sunset'][i][-5:]}")
            day_blocks.append(block)

        strat_preamble = f"Ты — метеоролог-профи на телевидении.Проанализируй массив данных и на их основе расскажи телезрителям какая погода их ждёт ближайшие 3 дня(подробно по дням) и почему. {common_rules}"
        strat_ai = ask_ai_cascade(f"Future: {day_blocks}", strat_preamble)
        final_strat = "🗓 #прогноз3дня\n🔭 **Прогноз на 3 дня**\n\n" + "\n\n".join(day_blocks) + f"\n\n🏛 **Аналитика:**\n{strat_ai}"
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", json={"chat_id": CH_ID, "text": final_strat, "parse_mode": "Markdown"})

if __name__ == "__main__":
    main()
