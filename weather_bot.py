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
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={GEMINI_KEY}"
            payload = {"contents": [{"parts": [{"text": f"{system_preamble}\n\nData: {prompt_msg}"}]}]}
            res = requests.post(url, json=payload, timeout=90).json()
            if 'candidates' in res: return res['candidates'][0]['content']['parts'][0]['text'].strip()
        except: pass
    if MISTRAL_KEY:
        try:
            res = requests.post("https://api.mistral.ai/v1/chat/completions",
                                headers={"Authorization": f"Bearer {MISTRAL_KEY}"},
                                json={"model": "mistral-large-latest",
                                      "messages": [{"role": "system", "content": system_preamble},
                                                   {"role": "user", "content": prompt_msg}]},
                                timeout=15).json()
            if 'choices' in res: return res['choices'][0]['message']['content'].strip()
        except: pass
    if GROQ_KEY:
        try:
            res = requests.post("https://api.groq.com/openai/v1/chat/completions",
                                headers={"Authorization": f"Bearer {GROQ_KEY}"},
                                json={"model": "llama-3.3-70b-versatile",
                                      "messages": [{"role": "system", "content": system_preamble},
                                                   {"role": "user", "content": prompt_msg}]},
                                timeout=15).json()
            if 'choices' in res: return res['choices'][0]['message']['content'].strip()
        except: pass
    return "Аналитика временно недоступна."

# --- Основная логика ---
def main():
    log("🚀 Старт системы...")
    try:
        log("📡 Запрос метеоданных (включая ливни и снег)...")
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}"
               f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,surface_pressure,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m,cloud_cover,uv_index,visibility,dew_point_2m"
               f"&hourly=temperature_2m,surface_pressure,relative_humidity_2m,wind_speed_10m,wind_gusts_10m,precipitation,showers,snowfall,weather_code,visibility,soil_temperature_0cm"
               f"&daily=sunrise,sunset&past_days=3&timezone=auto")
        res = requests.get(url, timeout=15)
        res.raise_for_status()
        data = res.json()
        log("✅ Данные получены.")
    except Exception as e:
        log(f"❌ Ошибка Open-Meteo: {e}")
        sys.exit(1)

    cur = data['current']
    h_data = data['hourly']
    daily = data['daily']
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
    hour = now.hour

    # --- Сверхчувствительная логика осадков ---
    # --- Обновленная логика осадков с правильной грамматикой ---
    precip_info = "без осадков"
    for i in range(hour, hour + 12):
        if i < len(h_data['precipitation']):
            w_code_h = h_data['weather_code'][i]
            total_v = h_data['precipitation'][i] + h_data['showers'][i] + h_data['snowfall'][i]

            if total_v > 0.01 or w_code_h >= 51:
                p_time = f"{i % 24:02d}:00"
                p_type = get_weather_desc(w_code_h)

                # Согласование мужского и женского рода
                if total_v < 0.2:
                    # Проверяем слова женского рода
                    if any(word in p_type for word in ["морось", "гроза"]):
                        prefix = "небольшая "
                    # Если это "ясно" или "пасмурно", приставка не нужна
                    elif any(word in p_type for word in ["ясно", "пасмурно"]):
                        prefix = ""
                    else:
                        prefix = "небольшой "
                else:
                    prefix = ""

                precip_info = f"{prefix}{p_type} ожидается около {p_time}"
                break

    kp_now = 0.0
    kp_future = 0.0
    try:
        kp_res = requests.get("https://services.swpc.noaa.gov/products/noaa-scales.json", timeout=10).json()
        kp_now = float(kp_res['0']['mag_eff']['kp']) if '0' in kp_res else float(kp_res[0]['kp'])
        if '1' in kp_res: kp_future = float(kp_res['1']['mag_eff']['kp'])
        elif len(kp_res) > 1: kp_future = float(kp_res[1]['kp'])
    except: pass

    danger_alerts = []
    gusts = cur.get('wind_gusts_10m', 0)
    temp = cur['temperature_2m']
    w_code = cur['weather_code']
    soil_temp = h_data['soil_temperature_0cm'][hour]

    if gusts >= 90: danger_alerts.append("🚨 **КРАСНЫЙ УРОВЕНЬ:** Ураганный ветер! (90+ км/ч)")
    elif gusts >= 54: danger_alerts.append("🟠 **ОРАНЖЕВЫЙ УРОВЕНЬ:** Сильный ветер/порывы! (54+ км/ч)")

    max_kp = max(kp_now, kp_future)
    if max_kp >= 8: danger_alerts.append(f"🚨 **КРАСНЫЙ УРОВЕНЬ:** Экстремальный магнитный шторм! (Kp {max_kp})")
    elif max_kp >= 6: danger_alerts.append(f"🟠 **ОРАНЖЕВЫЙ УРОВЕНЬ:** Сильная магнитная буря! (Kp {max_kp})")
    elif kp_future >= 5 and kp_now < 5: danger_alerts.append(f"⚠️ **ВНИМАНИЕ:** Ожидается усиление магнитной бури в ближайшие 3ч!")

    if temp >= 35 or temp <= -35: danger_alerts.append(f"🚨 **КРАСНЫЙ УРОВЕНЬ:** Экстремальная температура! ({temp}°C)")
    elif temp >= 30 or temp <= -25: danger_alerts.append(f"🟠 **ОРАНЖЕВЫЙ УРОВЕНЬ:** Опасная температура! ({temp}°C)")

    # --- Улучшенный блок гололёда и гололедицы ---
    if w_code in [66, 67]:
        danger_alerts.append("🟠 **ОРАНЖЕВЫЙ УРОВЕНЬ:** Сильный гололёд (ледяной дождь)!")
    elif temp < 1 and (soil_temp < 0 or max(h_data['temperature_2m'][hour-6:hour]) > 0):
        if sum(h_data['precipitation'][hour-6:hour]) > 0 or w_code >= 51:
            danger_alerts.append("🟠 **ОРАНЖЕВЫЙ УРОВЕНЬ:** Гололедица на дорогах (скользко)! ⛸️")

    temp_8am = h_data['temperature_2m'][80]
    press_8am = int(h_data['surface_pressure'][80] * 0.750062)

    if 5 <= hour < 14:
        tag, label = "🌅", "#прогнозутро"
        preamble = "Ты — ведущий синоптик-аналитик Пинской метеослужбы. Тебе предоставлен массив данных. Твоя задача: проанализировать данные и определить доминирующую воздушную массу и какое она оказывает влияние. (Если текущая воздушная масса имеет имя, присвоенное Свободным университетом Берлина (немецкие метеорологи), используй его в анализе если знаешь на 100%).Исходя из данных напиши как будет меняться погода в ближайшее время(или не будет меняться), сделай акцент на сегодняшний день, опиши какие ощущения будут на улице.Предупреди о возможных резких изменениях погоды(если они есть). Используй профессиональные термины. ПРАВИЛА: Не используй цифры. Пиши строго и профессионально, 2-3 предложения. Сразу суть без приветствий."
    elif 14 <= hour < 20:
        tag, label = "🌤️", "#прогноздень"
        preamble = f"Ты — эксперт метеорологического мониторинга. Сравни текущие данные с утренними показателями. Утро ({temp_8am}°C, {press_8am}мм). Твоя задача: проанализировать данные и определить, подтверждается ли утренний прогноз или он изменился.Если текущая воздушная масса имеет имя, присвоенное Свободным университетом Берлина (немецкие метеорологи), используй его в анализе если знаешь на 100%. Опиши, изменились ли ощущения за окном по сравнению с утром. Предупреди о возможных резких изменениях погоды(если они есть). ПРАВИЛА: Не используй цифры. Пиши кратко и по делу, 1-2 предложения. Используй профессиональный язык. Избегай общих фраз."
    else:
        tag, label = "🌙", "#прогнозвечер"
        preamble = "Ты — дежурный синоптик ночной смены.Твоя задача: проанализировать данные  и на основе их рассказать о движение воздушных масс и погоде , определить какие изменения(или нет изменений) будут ночью.Если текущая воздушная масса имеет имя, присвоенное Свободным университетом Берлина (немецкие метеорологи), используй его в анализе если знаешь на 100%. Сделай акцент на том, какой будет погода утром и как она будет ощущаться (завтра утром). Предупреди о возможных резких изменениях погоды(если они есть).ПРАВИЛА: Не используй цифры. Используй профессиональный язык. Объем: 1-2 предложения."

    log("🧠 Работа ИИ (Cohere)...")
    # Добавляем дату и время для ИИ
    now_str = now.strftime('%d.%m.%Y %H:%M')
    ai_input = f"Date/Time: {now_str}. Current: {cur}. SoilTemp: {soil_temp}. Alerts: {danger_alerts}. Kp Forecast: {kp_future}."
    ai_text = ask_ai_cascade(ai_input, preamble)

    press_now = int(cur['surface_pressure'] * 0.750062)
    pm25 = 0.0
    try:
        aq_res = requests.get(f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={LAT}&longitude={LON}&current=pm2_5", timeout=10).json()
        pm25 = aq_res['current']['pm2_5']
    except: pass

    warning_block = "\n".join(danger_alerts) if danger_alerts else ""
    if warning_block: warning_block = f"\n{warning_block}\n"

    msg = (
        f"{tag} {label}\n\n"
        f"🏙 **Пинск сейчас:**\n"
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
        f"{warning_block}\n"
        f"📝 **СИНОПТИК:**\n{ai_text}"
    )

    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", json={"chat_id": CH_ID, "text": msg, "parse_mode": "Markdown"}, timeout=15)
        log("✅ Сводка отправлена!")
    except: pass

if __name__ == "__main__":
    main()
