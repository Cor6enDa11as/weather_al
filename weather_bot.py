#!/usr/bin/env python3
import os, requests, datetime, sys

# --- Настройки ---
LAT, LON = 52.12, 26.10
COHERE_KEY = os.getenv('COHERE_API_KEY')
GEMINI_KEY = os.getenv('GEMINI_API_KEY')
GROQ_KEY = os.getenv('GROQ_API_KEY')
MISTRAL_KEY = os.getenv('MISTRAL_API_KEY')
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

def get_wind_power(speed):
    if speed < 5: return "штиль 💨"
    if speed < 12: return "слабый 🍃"
    if speed < 29: return "умеренный 🌬️"
    if speed < 50: return "сильный 🌪️"
    return "ОЧЕНЬ СИЛЬНЫЙ ⚠️"

def get_weather_desc(code):
    codes = {0: "ясно", 1: "преимущественно ясно", 2: "переменная облачность", 3: "пасмурно", 45: "туман", 51: "легкая морось", 53: "морось", 55: "сильная морось", 61: "небольшой дождь", 63: "дождь", 65: "сильный дождь", 66: "ледяной дождь ⛸", 71: "снег", 75: "сильный снег ❄️", 80: "ливень", 95: "гроза"}
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
    if uv <= 2: return "Низкий (безопасно) ✅"
    if uv <= 5: return "Средний (нужен SPF) 🧴"
    return "Высокий (нужна защита) 👒"

def get_humidity_desc(h, temp):
    if h < 30: return "(сухо 🏜️)"
    if h > 70:
        if temp < 5: return "(сыро/пронизывающий холод ❄️)"
        return "(влажно/душно 💦)"
    return "(комфортно ✨)"

# --- Каскад ИИ агентов ---
def ask_ai_cascade(prompt_msg, system_preamble):
    if COHERE_KEY:
        try:
            res = requests.post("https://api.cohere.ai/v1/chat",
                                headers={"Authorization": f"Bearer {COHERE_KEY}"},
                                json={"message": prompt_msg, "model": "command-r-plus-08-2024", "preamble": system_preamble},
                                timeout=60).json()
            if 'text' in res: return res['text'].strip()
        except: pass
    if GEMINI_KEY:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
            payload = {"contents": [{"parts": [{"text": f"{system_preamble}\n\nData: {prompt_msg}"}]}]}
            res = requests.post(url, json=payload, timeout=90).json()
            if 'candidates' in res: return res['candidates'][0]['content']['parts'][0]['text'].strip()
        except: pass
    return "Аналитика временно недоступна."

# --- Основная логика ---
def main():
    log("🚀 Старт системы...")
    try:
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}"
               f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,surface_pressure,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m,cloud_cover,uv_index,visibility,dew_point_2m"
               f"&hourly=temperature_2m,surface_pressure,relative_humidity_2m,wind_speed_10m,wind_gusts_10m,precipitation,showers,snowfall,weather_code,visibility,soil_temperature_0cm"
               f"&daily=sunrise,sunset&past_days=3&timezone=auto")
        res = requests.get(url, timeout=15)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        log(f"❌ Ошибка Open-Meteo: {e}"); sys.exit(1)

    cur = data['current']
    h_data = data['hourly']
    daily = data['daily']
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
    hour = now.hour

    # --- РАСЧЕТ ДИНАМИКИ (ПАМЯТЬ 72 ЧАСА) ---
    # Индекс текущего часа в h_data с учетом past_days=3 (3*24 = 72)
    idx_now = hour + 72
    temp = cur['temperature_2m']
    press_now_mb = cur['surface_pressure']

    delta_temp_24h = round(temp - h_data['temperature_2m'][idx_now - 24], 1)
    delta_temp_48h = round(temp - h_data['temperature_2m'][idx_now - 48], 1)

    press_3h_ago = h_data['surface_pressure'][idx_now - 3]
    press_trend_val = round(press_now_mb - press_3h_ago, 1)
    p_trend_text = "интенсивное падение" if press_trend_val < -1.5 else "рост" if press_trend_val > 1.5 else "стабильное состояние"

    recent_rain = round(sum(h_data['precipitation'][idx_now - 24 : idx_now]), 1)

    # --- Логика осадков ---
    precip_info = "без осадков"
    for i in range(idx_now, idx_now + 12):
        if i < len(h_data['precipitation']):
            w_code_h = h_data['weather_code'][i]
            total_v = h_data['precipitation'][i] + h_data['showers'][i] + h_data['snowfall'][i]
            if total_v > 0.01 or w_code_h >= 51:
                p_time = f"{i % 24:02d}:00"
                p_type = get_weather_desc(w_code_h)
                if total_v < 0.2:
                    if any(word in p_type for word in ["морось", "гроза"]): prefix = "небольшая "
                    elif any(word in p_type for word in ["ясно", "пасмурно"]): prefix = ""
                    else: prefix = "небольшой "
                else: prefix = ""
                precip_info = f"{prefix}{p_type} ожидается около {p_time}"
                break

    # --- Магнитный фон ---
    kp_now, kp_future = 0.0, 0.0
    try:
        kp_res = requests.get("https://services.swpc.noaa.gov/products/noaa-scales.json", timeout=10).json()
        kp_now = float(kp_res['0']['mag_eff']['kp']) if '0' in kp_res else float(kp_res[0]['kp'])
        if '1' in kp_res: kp_future = float(kp_res['1']['mag_eff']['kp'])
    except: pass

    # --- Предупреждения ---
    danger_alerts = []
    gusts = cur.get('wind_gusts_10m', 0)
    w_code = cur['weather_code']
    soil_temp = h_data['soil_temperature_0cm'][idx_now]

    if gusts >= 90: danger_alerts.append("🚨 **КРАСНЫЙ УРОВЕНЬ:** Ураганный ветер! (90+ км/ч)")
    elif gusts >= 54: danger_alerts.append("🟠 **ОРАНЖЕВЫЙ УРОВЕНЬ:** Сильный ветер/порывы! (54+ км/ч)")

    max_kp = max(kp_now, kp_future)
    if max_kp >= 8: danger_alerts.append(f"🚨 **КРАСНЫЙ УРОВЕНЬ:** Экстремальный магнитный шторм! (Kp {max_kp})")
    elif max_kp >= 6: danger_alerts.append(f"🟠 **ОРАНЖЕВЫЙ УРОВЕНЬ:** Сильная магнитная буря! (Kp {max_kp})")

    if temp >= 35 or temp <= -35: danger_alerts.append(f"🚨 **КРАСНЫЙ УРОВЕНЬ:** Экстремальная температура! ({temp}°C)")
    elif temp >= 30 or temp <= -25: danger_alerts.append(f"🟠 **ОРАНЖЕВЫЙ УРОВЕНЬ:** Опасная температура! ({temp}°C)")

    if w_code in [66, 67]: danger_alerts.append("🟠 **ОРАНЖЕВЫЙ УРОВЕНЬ:** Сильный гололёд (ледяной дождь)!")
    elif temp < 1 and (soil_temp < 0 or max(h_data['temperature_2m'][idx_now-6:idx_now]) > 0):
        if sum(h_data['precipitation'][idx_now-6:idx_now]) > 0 or w_code >= 51:
            danger_alerts.append("🟠 **ОРАНЖЕВЫЙ УРОВЕНЬ:** Гололедица на дорогах! ⛸️")

    # --- ЛОГИКА ИИ: УТРО, ДЕНЬ, ВЕЧЕР ---
    ai_text = ""
    if 5 <= hour < 14: # УТРО
        tag, label = "🌅", "#прогнозутро"
        preamble = f"Ты — ведущий эксперт метеослужбы. Твой анализ базируется на динамике за 72 часа (изменение температуры: {delta_temp_24h}, тренд давления: {p_trend_text}). Твоя задача: утвердительно описать синоптический процесс. Оцени тип воздушной массы и её трансформацию. Используй показатели SoilTemp и Accumulated Precip для оценки состояния подстилающей поверхности. ПРАВИЛА: Говори уверенно, используй глаголы в утвердительной форме: «наблюдается», «обусловит», «сформирует», «произойдет». Полностью исключи слова «вероятно», «возможно», «может быть». Не используй цифры и имена собственные циклонов. Стиль: Сухой, профессиональный, бескомпромиссный. 2-3 предложения."
    elif 14 <= hour < 20: # ДЕНЬ (БЕЗ ИИ)
        tag, label = "🌤️", "#прогноздень"
    else: # ВЕЧЕР
        tag, label = "🌙", "#прогнозвечер"
        preamble = f"Ты — главный синоптик смены. Подведи итог суточного энергообмена. Твоя задача: на основе радиационного баланса и влажности четко определить характер предстоящей ночи и утра. Спрогнозируй тип конденсации (гололедица, иней, туман или роса), опираясь на физику остывания поверхности при текущей облачности. Укажи, как барический тренд ({press_trend_val}) изменит или закрепит текущий режим погоды завтра. ПРАВИЛА: Исключи любые сомнения. Вместо «может похолодать» пиши «выхолаживание усилится». Вместо «возможен туман» пиши «сформируется зона плотной конденсации». Не используй цифры. Стиль: Экспертный вердикт. 1-2 предложения."

    # Запуск ИИ только в нужные часы
    if (5 <= hour < 14) or (hour >= 20):
        log(f"🧠 Работа ИИ ({tag})...")
        ai_input = f"History_72h: TempDelta24h={delta_temp_24h}, PressTrend={p_trend_text}, AccumulatedRain={recent_rain}mm. Current: {cur}. SoilTemp: {soil_temp}. Alerts: {danger_alerts}."
        ai_text = ask_ai_cascade(ai_input, preamble)

    # --- Сборка сообщения ---
    press_now = int(press_now_mb * 0.750062)
    pm25 = 0.0
    try:
        aq_res = requests.get(f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={LAT}&longitude={LON}&current=pm2_5", timeout=10).json()
        pm25 = aq_res['current']['pm2_5']
    except: pass

    warning_block = "\n".join(danger_alerts) if danger_alerts else ""
    if warning_block: warning_block = f"\n{warning_block}\n"

    ai_section = f"\n📝 **СИНОПТИК:**\n{ai_text}" if ai_text else ""

    msg = (f"{tag} {label}\n\n🏙 **Пинск сейчас:**\n"
           f"🌡 Температура: {cur['temperature_2m']}°C (ощущ. {cur['apparent_temperature']}°C)\n"
           f"☁️ Облачность: {cur['cloud_cover']}% ({get_weather_desc(cur['weather_code'])})\n"
           f"🌧 Осадки: {precip_info}\n"
           f"💨 Ветер: {cur['wind_speed_10m']} км/ч (порывы {gusts} км/ч) {get_wind_dir(cur['wind_direction_10m'])} ({get_wind_power(cur['wind_speed_10m'])})\n"
           f"💧 Влажность: {cur['relative_humidity_2m']}% {get_humidity_desc(cur['relative_humidity_2m'], temp)}\n"
           f"📈 Давление: {press_now} мм рт. ст. {get_pressure_desc(press_now)}\n"
           f"🧲 Магнитный фон: {kp_now} Kp {get_kp_desc(kp_now)}\n"
           f"☀️ УФ-индекс: {cur['uv_index']} {get_uv_desc(cur['uv_index'])}\n"
           f"🕒 Световой день: {daily['sunrise'][3][-5:]} — {daily['sunset'][3][-5:]}\n"
           f"🍃 Воздух: {pm25} PM2.5 {get_aqi_desc(pm25)}\n"
           f"{warning_block}{ai_section}")

    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", json={"chat_id": CH_ID, "text": msg, "parse_mode": "Markdown"}, timeout=15)
        log("✅ Сводка отправлена!")
    except: pass

if __name__ == "__main__":
    main()
