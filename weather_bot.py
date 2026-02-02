#!/usr/bin/env python3

import os, requests, datetime, json, feedparser
from bs4 import BeautifulSoup

# --- Настройки Пинск ---
LAT, LON = 52.12, 26.10

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
        0: "ясно", 1: "преимущественно ясно", 2: "переменная облачность",
        3: "пасмурно", 45: "туман", 51: "легкая морось", 53: "морось",
        55: "сильная морось", 61: "небольшой дождь", 63: "дождь",
        65: "сильный дождь", 66: "ледяной дождь", 67: "сильный ледяной дождь",
        71: "небольшой снег", 73: "снег", 75: "сильный снег",
        77: "снежные зерна", 80: "слабый ливень", 81: "ливень",
        82: "сильный ливень", 85: "небольшой снегопад", 86: "сильный снегопад",
        95: "гроза", 96: "гроза с градом", 99: "сильная гроза с градом"
    }
    return codes.get(code, "осадки")

def get_pressure_desc(p):
    if p < 745: return "(пониженное 📉)"
    if p > 755: return "(повышенное 📈)"
    return "(норма)"

def get_kp_desc(kp):
    if kp == "нет данных" or kp is None: return ""
    try:
        k = float(kp)
        if k < 4: return "(спокойно)"
        if k < 5: return "(небольшие возмущения)"
        if k < 6: return "(слабая буря ⚠️)"
        return "(СИЛЬНАЯ БУРЯ 🌪️)"
    except: return ""

def get_aqi_desc(pm25):
    if pm25 == "нет данных" or pm25 is None: return ""
    if pm25 < 12: return "(чистый)"
    if pm25 < 35: return "(приемлемый)"
    if pm25 < 55: return "(нездоровый для чувствительных)"
    return "(грязный 😷)"

def get_uv_desc(uv):
    if uv is None: return ""
    if uv < 3: return "(низкий, безопасно)"
    if uv < 6: return "(умеренный, нужна защита 🧴)"
    if uv < 8: return "(высокий! будьте в тени ⛱️)"
    return "(ОПАСНЫЙ! избегайте солнца ⛔)"

def get_humidity_desc(h):
    if h < 30: return "(сухо 🏜️)"
    if h < 60: return "(комфортно ✨)"
    if h < 80: return "(влажно 💧)"
    return "(сыро 🌧️)"

def get_precipitation_info(hourly_data, start_hour, hours_to_check=12):
    for i in range(start_hour, start_hour + hours_to_check):
        if i < len(hourly_data['precipitation']):
            prec_sum = hourly_data['precipitation'][i]
            code = hourly_data['weather_code'][i]
            if prec_sum >= 0.05:
                type_desc = get_weather_desc(code)
                force = "небольшой " if "небольш" not in type_desc else ""
                if prec_sum >= 1.0: force = "умеренный "
                if prec_sum >= 5.0: force = "сильный "
                return f"{force}{type_desc} около {i%24:02d}:00".strip()
    return "не ожидаются"

def get_belhydromet_context():
    synoptic_3days, storm_msg = "Данные Белгидромета недоступны.", ""
    try:
        print("--- Получение данных Белгидромета... ---")
        m_feed = feedparser.parse("https://pogoda.by/rss/meteo/")
        if m_feed.entries:
            synoptic_3days = BeautifulSoup(m_feed.entries[0].description, "html.parser").get_text().strip()
            print("✅ Сводка РБ получена")
        s_feed = feedparser.parse("https://pogoda.by/rss/storm/")
        if s_feed.entries:
            storm_msg = f"{s_feed.entries[0].title}. {s_feed.entries[0].description}"
            print(f"⚠️ Штормовое получено: {storm_msg[:40]}...")
    except Exception as e:
        print(f"❌ Ошибка Белгидромета: {e}")
    return synoptic_3days, storm_msg

def main():
    now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3)
    hour, current_date_str = now.hour, now.strftime("%d %B")
    current_date_key = now.strftime("%d.%m.%Y")
    period = "morning" if 4 <= hour <= 11 else "day" if 12 <= hour <= 17 else "evening"

    history_file = 'weather_history.json'
    try:
        with open(history_file, 'r') as f: history = json.load(f)
    except: history = {}

    run_key = f"{current_date_key}_{period}"
    if history.get('last_sent_key') == run_key:
        print(f"--- Пропуск: {period} уже отправлен ---")
        return

    # 1. Основная погода и воздух
    try:
        print(f"--- Запрос данных Пинск ({period})... ---")
        w_res = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&current=temperature_2m,relative_humidity_2m,apparent_temperature,surface_pressure,weather_code,wind_speed_10m,wind_direction_10m,cloud_cover,uv_index,precipitation&hourly=temperature_2m,weather_code,wind_speed_10m,precipitation,cloud_cover&daily=sunrise,sunset&timezone=auto", timeout=15)
        w = w_res.json()
        aq_res = requests.get(f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={LAT}&longitude={LON}&current=pm2_5", timeout=10)
        pm25 = aq_res.json()['current']['pm2_5']
        print(f"✅ Погода и воздух: OK (PM2.5: {pm25})")
    except Exception as e:
        print(f"❌ Ошибка основных данных: {e}")
        return

    # 2. Кп-индекс (Двойной контур)
    current_kp = "нет данных"
    try:
        print("--- Запрос Kp-индекса (Основной: Open-Meteo)... ---")
        kp_res = requests.get("https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&hourly=magnetic_field_k_index", timeout=10)
        if kp_res.status_code == 200:
            current_kp = kp_res.json()['hourly']['magnetic_field_k_index'][0]
            print(f"✅ Kp получен (Open-Meteo): {current_kp}")
        else: raise Exception("Статус не 200")
    except:
        print("⚠️ Open-Meteo Kp недоступен. Пробую Запасной (NOAA)...")
        try:
            kp_res = requests.get("https://services.swpc.noaa.gov/products/noaa-estimated-planetary-k-index.json", timeout=10)
            kp_data = kp_res.json()
            current_kp = float(kp_data[-1][1])
            print(f"✅ Kp получен (NOAA): {current_kp}")
        except Exception as e:
            print(f"❌ Запасной Kp тоже упал: {e}")

    syn_3days, storm_raw = get_belhydromet_context()
    cur = w['current']
    press_mm = int(cur['surface_pressure'] * 0.750062)
    hum, wind, clouds = cur['relative_humidity_2m'], cur['wind_speed_10m'], cur['cloud_cover']
    wind_dir = get_wind_dir(cur['wind_direction_10m'])
    prec_forecast = get_precipitation_info(w['hourly'], hour)

    current_data = {'t': cur['temperature_2m'], 'p': press_mm, 'h': hum, 'w': wind, 'wd': wind_dir, 'c': clouds, 'kp': current_kp, 'pr': prec_forecast}
    weather_context = f"Темп: {cur['temperature_2m']}°C, Давл: {press_mm}мм, Влаж: {hum}%, Ветер: {wind}км/ч {wind_dir}, Обл: {clouds}%, Осадки: {prec_forecast}"

    role_info = "Ты — ведущий синоптик национальной метеослужбы. Твой стиль: научно-популярный, профессиональный. Используй профессиональные термины в своих прогнозах"

    if period == "morning":
        history['m'] = current_data
        msg = (f"#прогнозутро\n\n🏙 Пинск сейчас:\n🌡 Температура: {cur['temperature_2m']}°C (ощущ. {cur['apparent_temperature']}°C)\n☁️ Облачность: {clouds}% ({get_weather_desc(cur['weather_code'])})\n💨 Ветер: {wind} км/ч {wind_dir} ({get_wind_power(wind)})\n💧 Влажность: {hum}% {get_humidity_desc(hum)}\n🌧 Осадки: {prec_forecast}\n📈 Давление: {press_mm} мм рт. ст. {get_pressure_desc(press_mm)}\n🧲 Магнитный фон: {current_kp} Kp {get_kp_desc(current_kp)}\n🕒 Световой день: {w['daily']['sunrise'][0][-5:]} — {w['daily']['sunset'][0][-5:]}\n🍃 Воздух: {pm25} PM2.5 {get_aqi_desc(pm25)}\n")
        ai_prompt = f"{role_info} Сегодня {current_date_str}. Пинск: {weather_context}. Сводка РБ на 3 дня: {syn_3days}.Найди в сводке РБ данные на {current_date_str}.Проанализируй все данные. Определи барическую систему и её влияние и опиши физику ощущений для человека на улице. ПРАВИЛА: Штормовое предупреждение (если есть: {storm_raw}) вынеси ОТДЕЛЬНЫМ ПРЕДЛОЖЕНИЕМ В НАЧАЛО с ⚠️. Цифры не используй.Пиши кратко, 1-2 предложения кроме штормового предупреждения.Без вводных слов."
    elif period == "day":
        history['d'] = current_data
        m = history.get('m', {})
        history_str = f"Утро: Т:{m.get('t')}°C, Давл:{m.get('p')}мм, Влаж:{m.get('h')}%, Ветер:{m.get('w')}км/ч {m.get('wd')}"
        sunset = datetime.datetime.fromisoformat(w['daily']['sunset'][0]); diff = sunset - now.replace(tzinfo=None)
        msg = (f"#прогноздень\n\n🏙 Пинск сейчас:\n🌡 Температура: {cur['temperature_2m']}°C (ощущ. {cur['apparent_temperature']}°C)\n☁️ Облачность: {clouds}%\n💨 Ветер: {wind} км/ч {wind_dir} ({get_wind_power(wind)})\n💧 Влажность: {hum}% {get_humidity_desc(hum)}\n🌧 Осадки: {prec_forecast}\n🧲 Магнитный фон: {current_kp} Kp {get_kp_desc(current_kp)}\n📈 Давление: {press_mm} мм рт. ст. {get_pressure_desc(press_mm)}\n☀️ УФ-индекс: {cur['uv_index']} {get_uv_desc(cur['uv_index'])}\n🍃 Воздух: {pm25} PM2.5 {get_aqi_desc(pm25)}\n🌇 Закат: через {diff.seconds // 3600} ч. {(diff.seconds // 60) % 60} мин.\n")
        ai_prompt = f"{role_info} Сейчас обед {current_date_str}. Пинск: {weather_context}. Утром было: {history_str}. Сводка РБ: {syn_3days}.Проанализируй все данные. Расскажи есть или нет изменений в атмосфере по сравнению с утром (если есть то какие) на основе сводки РБ.Как изменились ощущения для человека за окном . ПРАВИЛА: Штормовое предупреждение (если есть: {storm_raw}) вынеси ОТДЕЛЬНЫМ ПРЕДЛОЖЕНИЕМ В НАЧАЛО с ⚠️. Цифры не используй.Пиши кратко, 1-2 предложения кроме штормового предупреждения.Без вводных слов."
    else:
        d = history.get('d', history.get('m', {}))
        history_str = f"Днем: Т:{d.get('t')}°C, Давл:{d.get('p')}мм, Влаж:{d.get('h')}%, Ветер:{d.get('w')}км/ч {d.get('wd')}"
        night_temps = w['hourly']['temperature_2m'][hour:hour+9]
        night_prec = get_precipitation_info(w['hourly'], hour, 9)
        msg = (f"#прогнозвечер\n\n🏙 Пинск сейчас:\n🌡 Температура: {cur['temperature_2m']}°C\n☁️ Облачность: {clouds}%\n💨 Ветер: {wind} км/ч {wind_dir} ({get_wind_power(wind)})\n💧 Влажность: {hum}% {get_humidity_desc(hum)}\n🌧 Осадки: {prec_forecast}\n📈 Давление: {press_mm} мм рт. ст. {get_pressure_desc(press_mm)}\n🍃 Воздух: {pm25} PM2.5 {get_aqi_desc(pm25)}\n\n🌒 Ночь\n🌡 От {min(night_temps)}°C до {max(night_temps)}°C\n🌧 Осадки ночью: {night_prec}\n")
        ai_prompt = f"{role_info} Вечер {current_date_str}. Пинск: {weather_context}. Днем было: {history_str}. Ночью: {min(night_temps)}°C, осадки: {night_prec}. Сводка РБ: {syn_3days}.Проанализируй данные. Подведи итог дня: совпала ли погода с прогнозом Белгидромета?  Расскажи какие изменения в атмосфере ночью (если есть то какие) на основе сводки РБ.Как будет ощущаться погода ночью для человека на улице. ПРАВИЛА: Штормовое предупреждение (если есть: {storm_raw}) вынеси ОТДЕЛЬНЫМ ПРЕДЛОЖЕНИЕМ В НАЧАЛО с ⚠️. Цифры не используй.Пиши кратко, 1-2 предложения кроме штормового предупреждения.Без вводных слов."

    # Каскад ИИ
    ai_success = False
    print("--- Запуск каскада ИИ... ---")
    for api in ["groq", "mistral", "cohere"]:
        try:
            if api == "groq":
                print("🤖 Пробую Groq (llama-3.3-70b-specdec)...")
                res = requests.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}"}, json={"model": "llama-3.3-70b-specdec", "messages": [{"role": "user", "content": ai_prompt}]}, timeout=25).json()
                content = res['choices'][0]['message']['content'].strip()
            elif api == "mistral":
                print("🤖 Пробую Mistral...")
                res = requests.post("https://api.mistral.ai/v1/chat/completions", headers={"Authorization": f"Bearer {os.getenv('MISTRAL_API_KEY')}"}, json={"model": "mistral-small-latest", "messages": [{"role": "user", "content": ai_prompt}]}, timeout=25).json()
                content = res['choices'][0]['message']['content'].strip()
            elif api == "cohere":
                print("🤖 Пробую Cohere...")
                res = requests.post("https://api.cohere.ai/v1/chat", headers={"Authorization": f"Bearer {os.getenv('COHERE_API_KEY')}", "Content-Type": "application/json"}, json={"message": ai_prompt, "model": "command-r-plus"}, timeout=25).json()
                content = res['text'].strip()

            msg += f"\n\n{content}"
            ai_success = True
            print(f"✅ Агент {api} OK")
            break
        except Exception as e:
            print(f"⚠️ Агент {api} ошибка: {e}")
            continue

    print("--- Отправка в Telegram... ---")
    tg_res = requests.post(f"https://api.telegram.org/bot{os.getenv('TELEGRAM_TOKEN')}/sendMessage", json={"chat_id": os.getenv('CHANNEL_ID'), "text": msg, "parse_mode": "Markdown"})
    if tg_res.status_code == 200:
        print("✅ Успешно доставлено")
        history['last_sent_key'] = run_key
        with open(history_file, 'w') as f: json.dump(history, f)
    else:
        print(f"❌ Ошибка Telegram: {tg_res.text}")

if __name__ == "__main__":
    main()
