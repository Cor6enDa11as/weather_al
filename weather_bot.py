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

# --- Функции пояснения (Твой Золотой Стандарт) ---
def get_wind_dir(deg):
    dirs = ["С ⬇️", "СВ ↙️", "В ⬅️", "ЮВ ↖️", "Ю ⬆️", "ЮЗ ↗️", "З ➡️", "СЗ ↘️"]
    return dirs[int((deg + 22.5) % 360 / 45)]

def get_wind_power(speed):
    if speed < 5: return "штиль 💨"
    if speed < 12: return "слабый 🍃"
    if speed < 29: return "умеренный 🌬️"
    if speed < 50: return "сильный 🌪️"
    return "ОЧЕНЬ СИЛЬНЫЙ ⚠️"

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

def get_kp_desc(kp):
    try:
        k = float(kp)
        if k < 3: return "(спокойно)"
        if k < 4: return "(слабые возмущения 🟡)"
        if k < 5: return "(небольшие возмущения 🟠)"
        return "(МАГНИТНАЯ БУРЯ ⚠️)"
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

# --- Каскад ИИ с Gemini на первом месте и подробными логами ---
def ask_ai_cascade(prompt_msg, system_preamble):
    log(f"🧠 [AI LOG] Формирование запроса. Данные: {prompt_msg[:100]}...")

    # 1. ПЕРВОЕ МЕСТО: Gemini
    if GEMINI_KEY:
        try:
            log("🤖 [AI LOG] Попытка №1: Gemini 3 Flash (Основной)...")
            url = f"https://generativelanguage.googleapis.com/v1/models/gemini-3-flash-preview:generateContent?key={GEMINI_KEY}"
            payload = {"contents": [{"parts": [{"text": f"{system_preamble}\n\nДанные: {prompt_msg}"}]}]}
            res = requests.post(url, json=payload, timeout=90)

            if res.status_code == 200:
                log("✅ [AI LOG] Gemini ответил успешно.")
                data = res.json()
                return data['candidates'][0]['content']['parts'][0]['text'].strip()
            else:
                log(f"⚠️ [AI LOG] Gemini отклонил запрос (Код: {res.status_code}). Текст: {res.text[:100]}")
        except Exception as e:
            log(f"❌ [AI LOG] Критическая ошибка Gemini: {e}")

    # 2. ВТОРОЕ МЕСТО: Cohere (Запасной)
    if COHERE_KEY:
        try:
            log("🤖 [AI LOG] Попытка №2: Cohere (Запасной)...")
            res = requests.post("https://api.cohere.ai/v1/chat",
                                headers={"Authorization": f"Bearer {COHERE_KEY}"},
                                json={"message": prompt_msg, "model": "command-r-plus-08-2024", "preamble": system_preamble},
                                timeout=60)
            if res.status_code == 200:
                log("✅ [AI LOG] Cohere выручил (ответ получен).")
                return res.json().get('text', '').strip()
            else:
                log(f"⚠️ [AI LOG] Cohere тоже не ответил (Код: {res.status_code})")
        except Exception as e:
            log(f"❌ [AI LOG] Ошибка Cohere: {e}")

    log("🚫 [AI LOG] Ни один ИИ-агент не смог обработать запрос.")
    return "Аналитика сейчас недоступна."

def main():
    log("🚀 [Belgidromet Log] Запуск...")
    try:
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}"
               f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,surface_pressure,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m,cloud_cover,uv_index,visibility,dew_point_2m"
               f"&hourly=temperature_2m,surface_pressure,relative_humidity_2m,wind_speed_10m,wind_gusts_10m,precipitation,precipitation_probability,weather_code,visibility,dew_point_2m,soil_temperature_0cm"
               f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max,sunrise,sunset&past_days=3&timezone=auto")
        data = requests.get(url, timeout=15).json()
        log("📡 [Belgidromet Log] Данные Open-Meteo получены.")
    except Exception as e: log(f"❌ [Belgidromet Log] Ошибка API: {e}"); sys.exit(1)

    cur, h_data, d_data = data['current'], data['hourly'], data['daily']
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
    hour, dow, idx_now = now.hour, now.weekday(), 72 + now.hour

    temp = cur['temperature_2m']
    press_now_mm = int(cur['surface_pressure'] * 0.750062)
    soil_temp = h_data['soil_temperature_0cm'][idx_now]

    # Динамика и Осадки (0.01 мм)
    delta_24 = round(temp - h_data['temperature_2m'][idx_now - 24], 1)
    recent_rain = round(sum(h_data['precipitation'][idx_now - 24 : idx_now]), 1)

    precip_info = "без осадков"
    for i in range(idx_now, idx_now + 12):
        v, prob = h_data['precipitation'][i], h_data['precipitation_probability'][i]
        if v > 0.01 or prob > 5:
            precip_info = f"{get_weather_desc(h_data['weather_code'][i])} ({prob}%) около {i % 24:02d}:00"
            break

    # Магнитный фон и Воздух
    kp_now = 0.0
    try:
        kp_res = requests.get("https://services.swpc.noaa.gov/products/noaa-scales.json", timeout=10).json()
        kp_now = float(kp_res['0']['mag_eff']['kp']) if '0' in kp_res else float(kp_res[0]['kp'])
    except: log("⚠️ [Belgidromet Log] Kp API error.")

    pm25 = 0.0
    try:
        aq_res = requests.get(f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={LAT}&longitude={LON}&current=pm2_5", timeout=10).json()
        pm25 = aq_res['current']['pm2_5']
    except: pass

    # Предупреждения (Оранж и Красный)
    danger_alerts = []
    gusts = cur.get('wind_gusts_10m', 0)
    if gusts >= 90: danger_alerts.append("🚨 **КРАСНЫЙ УРОВЕНЬ:** Ураган! (90+ км/ч)")
    elif gusts >= 54: danger_alerts.append("🟠 **ОРАНЖЕВЫЙ УРОВЕНЬ:** Сильный ветер! (54+ км/ч)")
    if kp_now >= 8: danger_alerts.append(f"🚨 **КРАСНЫЙ УРОВЕНЬ:** Экстремальный шторм! (Kp {kp_now})")
    elif kp_now >= 6: danger_alerts.append(f"🟠 **ОРАНЖЕВЫЙ УРОВЕНЬ:** Магнитная буря! (Kp {kp_now})")
    if temp >= 30 or temp <= -25: danger_alerts.append(f"🟠 **ОРАНЖЕВЫЙ УРОВЕНЬ:** Опасная температура! ({temp}°C)")
    if cur['weather_code'] in [66, 67] or (temp < 1 and soil_temp < 0 and sum(h_data['precipitation'][idx_now-6:idx_now]) > 0):
        danger_alerts.append("🟠 **ОРАНЖЕВЫЙ УРОВЕНЬ:** Гололедица! ⛸️")

    # Промты (Упрощенные и понятные)
    ai_text = ""
    if 5 <= hour < 14:
        tag, label = "🌅", "#прогнозутро"
        preamble = "Ты — метеоролог-практик. Твоя задача: просто и четко объяснить погоду на день. Используй конкретику, например: «на нашу территорию сместился циклон/антициклон». Объясни, как это повлияет на людей: будет ли скользко из-за замерзшей земли, будет ли голова тяжелой из-за давления. Говори прямо и уверенно. ПРАВИЛА: Используй глаголы: «наблюдается», «принесет», «сформирует». Запрещено: «вероятно», «возможно», «может быть». 3 предложения."
    elif hour >= 20 or hour < 5:
        tag, label = "🌙", "#прогнозвечер"
        preamble = "Ты — старший синоптик. Расскажи, чего ждать от ночи и утра. Если влажно и холодно — предупреди про туман или гололед на дорогах. Если давление скачет — предупреди, что сон может быть неспокойным. Обязательно используй формулировки типа «на нашу территорию сместился циклон/антициклон». ПРАВИЛА: Четкий экспертный вердикт без сомнений. Исключи: «может», «скорее всего». 3 предложения."
    else: tag, label, preamble = "🌤️", "#прогноздень", None

    if preamble:
        ai_input = f"History: Delta24h={delta_24}, Precip72h={recent_rain}mm. Current: Temp={temp}, Hum={cur['relative_humidity_2m']}, Press={press_now_mm}, Soil={soil_temp}, UV={cur['uv_index']}, Wind={cur['wind_speed_10m']}, Gusts={gusts}."
        ai_text = ask_ai_cascade(ai_input, preamble)

    # Сборка сообщения
    warning_block = ("\n" + "\n".join(danger_alerts) + "\n") if danger_alerts else ""
    ai_section = f"\n📝 **АНАЛИТИКА:**\n{ai_text}" if ai_text else ""

    msg = (f"{tag} {label}\n\n🏙 **Пинск сейчас:**\n"
           f"🌡 Температура: {temp}°C (ощущ. {cur['apparent_temperature']}°C)\n"
           f"☁️ Облачность: {cur['cloud_cover']}% ({get_weather_desc(cur['weather_code'])})\n"
           f"🌧 Осадки: {precip_info}\n"
           f"💨 Ветер: {cur['wind_speed_10m']} км/ч (порывы {gusts} км/ч) {get_wind_dir(cur['wind_direction_10m'])} ({get_wind_power(cur['wind_speed_10m'])})\n"
           f"💧 Влажность: {cur['relative_humidity_2m']}% {get_humidity_desc(cur['relative_humidity_2m'], temp)}\n"
           f"📈 Давление: {press_now_mm} мм {get_pressure_desc(press_now_mm)}\n"
           f"🧲 Магнитный фон: {kp_now} Kp {get_kp_desc(kp_now)}\n"
           f"☀️ УФ-индекс: {cur['uv_index']} {get_uv_desc(cur['uv_index'])}\n"
           f"✨ Видимость: {get_visibility_desc(cur['visibility'])}\n"
           f"🕒 Световой день: {d_data['sunrise'][3][-5:]} — {d_data['sunset'][3][-5:]}\n"
           f"🍃 Воздух: {pm25} PM2.5 {get_aqi_desc(pm25)}\n"
           f"{warning_block}{ai_section}")

    t_res = requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", json={"chat_id": CH_ID, "text": msg, "parse_mode": "Markdown"})
    if t_res.status_code == 200: log("✅ [Belgidromet Log] Сводка отправлена.")

    # --- СТРАТЕГИЯ НА 3 ДНЯ (СР и ВС вечер) ---
    if hour >= 20 or hour < 5 and dow in [2, 6]:
        log("🗓 [Belgidromet Log] Формирование прогноза на 3 дня...")
        day_blocks = []
        for i in range(4, 7):
            idx = i * 24
            d_name = (now + datetime.timedelta(days=i-3)).strftime('%a, %d.%m').replace('Mon','Пн').replace('Tue','Вт').replace('Wed','Ср').replace('Thu','Чт').replace('Fri','Пт').replace('Sat','Сб').replace('Sun','Вс')
            t_max, t_min = d_data['temperature_2m_max'][i], d_data['temperature_2m_min'][i]
            p_sum, p_prob = d_data['precipitation_sum'][i], d_data['precipitation_probability_max'][i]
            press_d = int(h_data['surface_pressure'][idx + 12] * 0.750062)

            p_text = f"{get_weather_desc(h_data['weather_code'][idx + 12])} ({p_prob}%)" if p_sum > 0.01 or p_prob > 10 else "без осадков"

            block = (f"📅 **{d_name}**\n"
                     f"🌡 Темп: {t_min}..{t_max}°C\n"
                     f"🌧 Осадки: {p_text}\n"
                     f"💨 Ветер: {d_data['wind_speed_10m_max'][i]} км/ч {get_wind_dir(h_data['wind_direction_10m'][idx+12])}\n"
                     f"📈 Давление: {press_d} мм {get_pressure_desc(press_d)}")
            day_blocks.append(block)

        strat_ai = ask_ai_cascade(f"Future: {day_blocks}", "Ты — метеоролог. Выяви сюжет на 3 дня. Напиши 3 предложения о перемещении циклонов/антициклонов и рисках для здоровья (давление, гололед). Понятно и уверенно.")

        final_strat = "🗓 #прогноз3дня\n🔭 **АНАЛИЗ НА 3 ДНЯ**\n\n" + "\n\n".join(day_blocks) + f"\n\n🏛 **СТРАТЕГИЯ:**\n{strat_ai}"
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", json={"chat_id": CH_ID, "text": final_strat, "parse_mode": "Markdown"})
        log("✅ [Belgidromet Log] Стратегия отправлена.")

if __name__ == "__main__":
    main()
