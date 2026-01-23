#!/usr/bin/env python3

import os, requests, datetime, json

# --- Настройки ---
LAT, LON = 52.12, 26.10

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

def get_pressure_desc(hpa):
    mmhg = int(hpa * 0.750062)
    if mmhg < 745: return f"{mmhg} мм (низкое) 📉"
    if mmhg > 760: return f"{mmhg} мм (высокое) 📈"
    return f"{mmhg} мм (норма) 🆗"

def get_aqi_desc(pm25):
    if pm25 < 12: return f"{pm25} PM2.5 (чистый воздух) 🌲"
    if pm25 < 35: return f"{pm25} PM2.5 (средне) 💨"
    return f"{pm25} PM2.5 (загрязнение!) ⚠️"

def get_uv_desc(uv):
    if uv < 3: return f"{uv} (низкий) ✅"
    if uv < 6: return f"{uv} (средний) 🧴"
    return f"{uv} (высокий!) 👒"

def get_precipitation_info(hourly_data, start_hour):
    """Ищет ближайшие осадки и формирует строку: тип, сила, время"""
    for i in range(start_hour, start_hour + 12):
        if i < len(hourly_data['precipitation']):
            prec_sum = hourly_data['precipitation'][i]
            if prec_sum > 0.1:
                code = hourly_data['weather_code'][i]
                type_desc = get_weather_desc(code)

                # Определение силы
                if prec_sum < 1.0: force = "небольшой"
                elif prec_sum < 5.0: force = "умеренный"
                else: force = "сильный"

                # Корректировка для ливней и метели
                if code in [80, 81, 82]: force = "интенсивный"
                if code in [71, 73, 75, 85, 86] and hourly_data['wind_speed_10m'][i] > 20:
                    type_desc = "метель"

                time = i % 24
                return f"{force} {type_desc} около {time:02d}:00"
    return "не ожидаются"

def get_kp_desc(kp):
    if kp < 4: return f"{kp} Kp (спокойно) ✅"
    if kp < 5: return f"{kp} Kp (возмущения) ⚠️"
    return f"{kp} Kp (МАГНИТНАЯ БУРЯ) 🆘"

def main():
    now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3)
    hour = now.hour
    current_date = now.strftime("%d.%m.%Y")

    w_url = (f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}"
             "&current=temperature_2m,apparent_temperature,surface_pressure,weather_code,wind_speed_10m,cloud_cover,uv_index,precipitation,rain,showers,snowfall"
             "&hourly=temperature_2m,weather_code,wind_speed_10m,precipitation,rain,showers,snowfall,cloud_cover"
             "&daily=sunrise,sunset&timezone=auto")
    aq_url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={LAT}&longitude={LON}&current=pm2_5"
    kp_url = "https://services.swpc.noaa.gov/products/noaa-estimated-planetary-k-index-1-minute.json"

    w = requests.get(w_url).json()
    aq = requests.get(aq_url).json()
    try:
        kp_res = requests.get(kp_url).json()
        current_kp = float(kp_res[-1][1])
    except: current_kp = 1.0

    cur = w['current']
    history_file = 'weather_history.json'
    try:
        with open(history_file, 'r') as f: history = json.load(f)
    except: history = {}

    prec_forecast = get_precipitation_info(w['hourly'], hour)
    weather_context = f"Темп: {cur['temperature_2m']}°C, Давление: {int(cur['surface_pressure'] * 0.750062)} мм, Осадки: {prec_forecast}"
    msg = ""
    ai_prompt = ""

    # --- УТРЕННЯЯ СВОДКА ---
    if 4 <= hour <= 9:
        history['morning_temp'] = cur['temperature_2m']
        msg = (f"#прогнозутро\n\n"
               f"🏙 Пинск сейчас:\n"
               f"🌡 Температура: {cur['temperature_2m']}°C (ощущ. {cur['apparent_temperature']}°C)\n"
               f"☁️ Облачность: {cur['cloud_cover']}% ({get_weather_desc(cur['weather_code'])})\n"
               f"💨 Ветер: {cur['wind_speed_10m']} км/ч ({get_wind_power(cur['wind_speed_10m'])})\n"
               f"🌧 Осадки: {prec_forecast}\n"
               f"📈 Давление: {get_pressure_desc(cur['surface_pressure'])}\n"
               f"🧲 Магнитный фон: {get_kp_desc(current_kp)}\n"
               f"🕒 Световой день: {w['daily']['sunrise'][0][-5:]} — {w['daily']['sunset'][0][-5:]}\n"
               f"🍃 Воздух: {get_aqi_desc(aq['current']['pm2_5'])}\n")
        ai_prompt = f"Сегодня {current_date}. Текущие данные: {weather_context}. Ты метеоролог. Сейчас утро. Дай глубокую АНАЛИТИКУ движения воздушных масс (циклон/антициклон с названием, физические явления, данные бери в интернете) и как это повлияет на погоду предстоящего дня, чего ждать для Пинска. Кратко(1-3 предложения). Пиши сразу по существу, без вводных фраз и заголовков. Дай совет."

    # --- ДНЕВНАЯ ДЕЖУРКА ---
    elif 13 <= hour <= 17:
        history['day_temp'] = cur['temperature_2m']
        sunset = datetime.datetime.fromisoformat(w['daily']['sunset'][0])
        diff = sunset - now.replace(tzinfo=None)
        msg = (f"#прогноздень\n\n"
               f"🏙 Пинск сейчас:\n"
               f"🌡 Температура: {cur['temperature_2m']}°C (ощущ. {cur['apparent_temperature']}°C)\n"
               f"☁️ Облачность: {cur['cloud_cover']}%\n"
               f"💨 Ветер: {cur['wind_speed_10m']} км/ч ({get_wind_power(cur['wind_speed_10m'])})\n"
               f"🌧 Осадки: {prec_forecast}\n"
               f"🧲 Магнитный фон: {get_kp_desc(current_kp)}\n"
               f"📈 Давление: {get_pressure_desc(cur['surface_pressure'])}\n"
               f"☀️ УФ-индекс: {get_uv_desc(cur['uv_index'])}\n"
               f"🍃 Воздух: {get_aqi_desc(aq['current']['pm2_5'])}\n"
               f"🌇 Закат: через {diff.seconds // 3600} ч. {(diff.seconds // 60) % 60} мин.\n")
        prev = history.get('morning_temp', 'неизвестно')
        ai_prompt = f"Сегодня {current_date}. Ты метеоролог. Сейчас обеденное время в Пинске. Текущие данные ({cur['temperature_2m']}°C) и утренние ({prev}°C) в Пинске. Расскажи как изменилась погода и как это ощущается, чего ждать к вечеру. Кратко 1-2 предложения. Если нет каких-то данных просто сообщи. Пиши сразу по существу, без вводных фраз и заголовков. Не пиши очевидные и банальные вещи."

    # --- ВЕЧЕРНЯЯ СВОДКА ---
    else:
        night_temps = w['hourly']['temperature_2m'][hour:hour+9]
        msg = (f"#прогнозвечер\n\n"
               f"🏙 Пинск сейчас:\n"
               f"🌡 Температура: {cur['temperature_2m']}°C\n"
               f"☁️ Облачность: {cur['cloud_cover']}%\n"
               f"💨 Ветер: {cur['wind_speed_10m']} км/ч ({get_wind_power(cur['wind_speed_10m'])})\n"
               f"🌧 Осадки: {prec_forecast}\n"
               f"🧲 Магнитный фон: {get_kp_desc(current_kp)}\n"
               f"📈 Давление: {get_pressure_desc(cur['surface_pressure'])}\n"
               f"🍃 Воздух: {get_aqi_desc(aq['current']['pm2_5'])}\n\n"
               f"🌒 Ночь\n"
               f"🌡 От {min(night_temps)}°C до {max(night_temps)}°C\n"
               f"☁️ Облачность ночью: {w['hourly']['cloud_cover'][hour+4]}%\n"
               f"💨 Ветер: {w['hourly']['wind_speed_10m'][hour+4]} км/ч ({get_wind_power(w['hourly']['wind_speed_10m'][hour+4])})\n")
        prev = history.get('day_temp', 'неизвестно')
        ai_prompt = f"Сегодня {current_date}. Ты метеоролог. Сейчас вечер в Пинске. Данные вечер ({cur['temperature_2m']}°C) и день ({prev}°C). Расскажи как изменилась погода, как это ощущается и чего ждать ночью. Кратко 1-2 предложения. Если нет каких-то данных просто сообщи. Пиши сразу по существу, без вводных фраз и заголовков. Не пиши очевидные вещи."

    # 4. ИИ Анализ
    models = ["google/gemini-2.0-flash-lite-preview-02-05:free", "qwen/qwen-2.5-7b-instruct:free", "google/gemini-2.0-flash-001"]
    for model in models:
        try:
            ai_res = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}", "HTTP-Referer": "https://github.com/weather_al"},
                json={"model": model, "messages": [{"role": "user", "content": ai_prompt}]},
                timeout=60
            ).json()
            if 'choices' in ai_res:
                ai_text = ai_res['choices'][0]['message']['content'].replace('*', '').replace('_', '').replace('`', '')
                msg += f"\n\n{ai_text}"
                break
        except: continue

    # 5. Финализация
    with open(history_file, 'w') as f: json.dump(history, f)
    requests.post(f"https://api.telegram.org/bot{os.getenv('TELEGRAM_TOKEN')}/sendMessage",
                  json={"chat_id": os.getenv('CHANNEL_ID'), "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    main()
