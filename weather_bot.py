#!/usr/bin/env python3
import os, requests, datetime, json

# --- Настройки Пинск ---
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

def get_pressure_desc(p):
    if p < 745: return "(пониженное 📉)"
    if p > 755: return "(повышенное 📈)"
    return "(норма)"

def get_kp_desc(kp):
    if kp == "нет данных" or kp is None: return ""
    if kp < 4: return "(спокойно)"
    if kp < 5: return "(небольшие возмущения)"
    if kp < 6: return "(слабая буря ⚠️)"
    return "(СИЛЬНАЯ БУРЯ 🌪️)"

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

def get_precipitation_info(hourly_data, start_hour):
    for i in range(start_hour, start_hour + 12):
        if i < len(hourly_data['precipitation']):
            prec_sum = hourly_data['precipitation'][i]
            code = hourly_data['weather_code'][i]
            if prec_sum >= 0.05:
                type_desc = get_weather_desc(code)
                if prec_sum < 1.0:
                    force = "" if "небольш" in type_desc else "небольшой "
                elif prec_sum < 5.0:
                    force = "умеренный "
                else:
                    force = "сильный "
                if code in [80, 81, 82]: force = "интенсивный "
                return f"{force}{type_desc} около {i%24:02d}:00".strip()
    return "не ожидаются"

def main():
    now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3)
    hour, current_date = now.hour, now.strftime("%d.%m.%Y")

    if 4 <= hour <= 13: period = "morning"
    elif 14 <= hour <= 20: period = "day"
    else: period = "evening"

    history_file = 'weather_history.json'
    try:
        with open(history_file, 'r') as f: history = json.load(f)
    except: history = {}

    run_key = f"{current_date}_{period}"
    if history.get('last_sent_key') == run_key:
        print(f"--- Пропуск: прогноз за {period} уже был отправлен сегодня ---")
        return

    current_kp, pm25 = "нет данных", "нет данных"
    try:
        w_res = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&current=temperature_2m,relative_humidity_2m,apparent_temperature,surface_pressure,weather_code,wind_speed_10m,cloud_cover,uv_index,precipitation&hourly=temperature_2m,weather_code,wind_speed_10m,precipitation,cloud_cover&daily=sunrise,sunset&timezone=auto", timeout=15)
        w = w_res.json()
        print(f"--- Данные получены: Temp {w['current']['temperature_2m']}°C ---")
    except Exception as e:
        print(f"--- Ошибка получения погоды: {e} ---"); return

    try:
        aq_res = requests.get(f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={LAT}&longitude={LON}&current=pm2_5", timeout=10)
        pm25 = aq_res.json()['current']['pm2_5']
    except: pass

    try:
        kp_res = requests.get("https://services.swpc.noaa.gov/products/noaa-estimated-planetary-k-index.json", timeout=10).json()
        current_kp = float(kp_res[-1][1])
    except: pass

    prec_forecast = get_precipitation_info(w['hourly'], hour)
    cur = w['current']
    press_mm = int(cur['surface_pressure'] * 0.750062)
    hum = cur['relative_humidity_2m']
    wind = cur['wind_speed_10m']
    clouds = cur['cloud_cover']

    current_data = {'t': cur['temperature_2m'], 'p': press_mm, 'h': hum, 'w': wind, 'c': clouds, 'kp': current_kp, 'pr': prec_forecast}
    weather_context = f"Темп: {cur['temperature_2m']}°C, Давл: {press_mm}мм, Влаж: {hum}%, Ветер: {wind}км/ч, Обл: {clouds}%, Кп: {current_kp}, Осадки: {prec_forecast}"
    msg, ai_prompt = "", ""

    if period == "morning":
        history['m'] = current_data
        msg = (f"#прогнозутро\n\n🏙 Пинск сейчас:\n🌡 Температура: {cur['temperature_2m']}°C (ощущ. {cur['apparent_temperature']}°C)\n☁️ Облачность: {clouds}% ({get_weather_desc(cur['weather_code'])})\n💨 Ветер: {wind} км/ч ({get_wind_power(wind)})\n💧 Влажность: {hum}% {get_humidity_desc(hum)}\n🌧 Осадки: {prec_forecast}\n📈 Давление: {press_mm} мм рт. ст. {get_pressure_desc(press_mm)}\n🧲 Магнитный фон: {current_kp} Kp {get_kp_desc(current_kp)}\n🕒 Световой день: {w['daily']['sunrise'][0][-5:]} — {w['daily']['sunset'][0][-5:]}\n🍃 Воздух: {pm25} PM2.5 {get_aqi_desc(pm25)}\n")
        ai_prompt = f"Сегодня {current_date}. Текущие данные: {weather_context}. Ты метеоролог. Сейчас утро. Дай глубокую АНАЛИТИКУ движения воздушных масс (циклон/антициклон с названием, физические явления, данные бери в интернете) и как это повлияет на погоду предстоящего дня, чего ждать для Пинска. Кратко(1-3 предложения). Пиши сразу по существу, без вводных фраз и заголовков. Дай совет."
    elif period == "day":
        history['d'] = current_data
        m = history.get('m', {})
        history_str = f"Утро: Т:{m.get('t')}°C, Давл:{m.get('p')}мм, Влаж:{m.get('h')}%, Ветер:{m.get('w')}км/ч, Обл:{m.get('c')}%, Кп:{m.get('kp')}, Осадки:{m.get('pr')}"
        sunset = datetime.datetime.fromisoformat(w['daily']['sunset'][0])
        diff = sunset - now.replace(tzinfo=None)
        msg = (f"#прогноздень\n\n🏙 Пинск сейчас:\n🌡 Температура: {cur['temperature_2m']}°C (ощущ. {cur['apparent_temperature']}°C)\n☁️ Облачность: {clouds}%\n💨 Ветер: {wind} км/ч ({get_wind_power(wind)})\n💧 Влажность: {hum}% {get_humidity_desc(hum)}\n🌧 Осадки: {prec_forecast}\n🧲 Магнитный фон: {current_kp} Kp {get_kp_desc(current_kp)}\n📈 Давление: {press_mm} мм рт. ст. {get_pressure_desc(press_mm)}\n☀️ УФ-индекс: {cur['uv_index']} {get_uv_desc(cur['uv_index'])}\n🍃 Воздух: {pm25} PM2.5 {get_aqi_desc(pm25)}\n🌇 Закат: через {diff.seconds // 3600} ч. {(diff.seconds // 60) % 60} мин.\n")
        ai_prompt = f"Сегодня {current_date}. Ты метеоролог. Сейчас обеденное время. Данные сейчас: {weather_context} и утро ({history_str}). Расскажи как изменилась погода и как это ощущается, чего ждать к вечеру. Кратко 1-2 предложения. Пиши сразу по существу."
    else:
        d = history.get('d', history.get('m', {}))
        history_str = f"Днем: Т:{d.get('t')}°C, Давл:{d.get('p')}мм, Влаж:{d.get('h')}%, Ветер:{d.get('w')}км/ч, Обл:{d.get('c')}%, Кп:{d.get('kp')}, Осадки:{d.get('pr')}"
        night_temps = w['hourly']['temperature_2m'][hour:hour+9]
        msg = (f"#прогнозвечер\n\n🏙 Пинск сейчас:\n🌡 Температура: {cur['temperature_2m']}°C\n☁️ Облачность: {clouds}%\n💨 Ветер: {wind} км/ч\n💧 Влажность: {hum}% {get_humidity_desc(hum)}\n🌧 Осадки: {prec_forecast}\n📈 Давление: {press_mm} мм рт. ст. {get_pressure_desc(press_mm)}\n🍃 Воздух: {pm25} PM2.5 {get_aqi_desc(pm25)}\n\n🌒 Ночь\n🌡 От {min(night_temps)}°C до {max(night_temps)}°C\n☁️ Облачность ночью: {w['hourly']['cloud_cover'][hour+4]}%\n💨 Ветер: {w['hourly']['wind_speed_10m'][hour+4]} км/ч\n")
        ai_prompt = f"Сегодня {current_date}. Ты метеоролог. Сейчас вечер. Данные сейчас: {weather_context}и днем ({history_str}). Ночью будет {min(night_temps)}°C. Расскажи как изменилась погода и как это ощущается, чего ждать ночью.Кратко 1-2 предложения.Пиши сразу по существу."

    models = ["google/gemini-2.0-flash-001", "google/gemini-2.0-flash-lite-001"]
    for model in models:
        try:
            res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"}, json={"model": model, "messages": [{"role": "user", "content": ai_prompt}]}, timeout=40).json()
            if 'choices' in res:
                msg += f"\n\n{res['choices'][0]['message']['content'].strip()}"
                print(f"--- ИИ агент {model} сработал ---"); break
        except Exception as e: print(f"--- Ошибка ИИ {model}: {e} ---")

    tg_res = requests.post(f"https://api.telegram.org/bot{os.getenv('TELEGRAM_TOKEN')}/sendMessage", json={"chat_id": os.getenv('CHANNEL_ID'), "text": msg, "parse_mode": "Markdown"})
    if tg_res.status_code == 200:
        history['last_sent_key'] = run_key
        with open(history_file, 'w') as f: json.dump(history, f)
        print(f"--- Успех: Сообщение за {period} отправлено ---")
    else: print(f"--- Ошибка отправки в Telegram: {tg_res.status_code} ---")

if __name__ == "__main__":
    main()
