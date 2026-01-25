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

def get_precipitation_info(hourly_data, start_hour):
    for i in range(start_hour, start_hour + 12):
        if i < len(hourly_data['precipitation']):
            prec_sum = hourly_data['precipitation'][i]
            code = hourly_data['weather_code'][i]
            if prec_sum >= 0.05: # Порог 0.05 мм
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

    # ПЕРИОДЫ ДЛЯ ЗАЩИТЫ ОТ ДУБЛЕЙ
    if 4 <= hour <= 11: period = "morning"
    elif 12 <= hour <= 17: period = "day"
    else: period = "evening"

    history_file = 'weather_history.json'
    try:
        with open(history_file, 'r') as f: history = json.load(f)
    except: history = {}

    run_key = f"{current_date}_{period}"
    if history.get('last_sent_key') == run_key:
        print(f"--- Пропуск: прогноз за {period} уже был отправлен сегодня ---")
        return

    # 1. СБОР ДАННЫХ И ЛОГИ ОШИБОК
    try:
        w = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&current=temperature_2m,apparent_temperature,surface_pressure,weather_code,wind_speed_10m,cloud_cover,uv_index,precipitation&hourly=temperature_2m,weather_code,wind_speed_10m,precipitation,cloud_cover&daily=sunrise,sunset&timezone=auto").json()
        aq = requests.get(f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={LAT}&longitude={LON}&current=pm2_5").json()
        kp_res = requests.get("https://services.swpc.noaa.gov/products/noaa-estimated-planetary-k-index.json").json()
        current_kp = float(kp_res[-1][1])
        print(f"--- Данные получены: Temp {w['current']['temperature_2m']}°C, Kp {current_kp}, PM2.5 {aq['current']['pm2_5']} ---")
    except Exception as e:
        print(f"--- Ошибка получения данных: {e} ---")
        return

    prec_forecast = get_precipitation_info(w['hourly'], hour)
    cur = w['current']
    weather_context = f"Темп: {cur['temperature_2m']}°C, Давление: {int(cur['surface_pressure'] * 0.750062)} мм, Осадки: {prec_forecast}"
    msg, ai_prompt = "", ""

    # ТВОИ ПРОМПТЫ И СООБЩЕНИЯ
    if period == "morning":
        history['morning_temp'] = cur['temperature_2m']
        msg = (f"#прогнозутро\n\n🏙 Пинск сейчас:\n🌡 Температура: {cur['temperature_2m']}°C (ощущ. {cur['apparent_temperature']}°C)\n☁️ Облачность: {cur['cloud_cover']}% ({get_weather_desc(cur['weather_code'])})\n💨 Ветер: {cur['wind_speed_10m']} км/ч ({get_wind_power(cur['wind_speed_10m'])})\n🌧 Осадки: {prec_forecast}\n📈 Давление: {int(cur['surface_pressure'] * 0.750062)} мм\n🧲 Магнитный фон: {current_kp} Kp\n🕒 Световой день: {w['daily']['sunrise'][0][-5:]} — {w['daily']['sunset'][0][-5:]}\n🍃 Воздух: {aq['current']['pm2_5']} PM2.5\n")
        ai_prompt = f"Сегодня {current_date}. Текущие данные: {weather_context}. Ты метеоролог. Сейчас утро. Дай глубокую АНАЛИТИКУ движения воздушных масс (циклон/антициклон с названием, физические явления, данные бери в интернете) и как это повлияет на погоду предстоящего дня, чего ждать для Пинска. Кратко(1-3 предложения). Пиши сразу по существу, без вводных фраз и заголовков. Дай совет."
    elif period == "day":
        history['day_temp'] = cur['temperature_2m']
        sunset = datetime.datetime.fromisoformat(w['daily']['sunset'][0])
        diff = sunset - now.replace(tzinfo=None)
        msg = (f"#прогноздень\n\n🏙 Пинск сейчас:\n🌡 Температура: {cur['temperature_2m']}°C (ощущ. {cur['apparent_temperature']}°C)\n☁️ Облачность: {cur['cloud_cover']}%\n💨 Ветер: {cur['wind_speed_10m']} км/ч ({get_wind_power(cur['wind_speed_10m'])})\n🌧 Осадки: {prec_forecast}\n🧲 Магнитный фон: {current_kp} Kp\n📈 Давление: {int(cur['surface_pressure'] * 0.750062)} мм\n☀️ УФ-индекс: {cur['uv_index']}\n🍃 Воздух: {aq['current']['pm2_5']} PM2.5\n🌇 Закат: через {diff.seconds // 3600} ч. {(diff.seconds // 60) % 60} мин.\n")
        ai_prompt = f"Сегодня {current_date}. Ты метеоролог. Сейчас обеденное время в Пинске. Текущие данные ({cur['temperature_2m']}°C) и утренние ({history.get('morning_temp','?') }°C) в Пинске. Расскажи как изменилась погода и как это ощущается, чего ждать к вечеру. Кратко 1-2 предложения. Если нет каких-то данных просто сообщи. Пиши сразу по существу, без вводных фраз и заголовков. Не пиши очевидные и банальные вещи."
    else:
        night_temps = w['hourly']['temperature_2m'][hour:hour+9]
        msg = (f"#прогнозвечер\n\n🏙 Пинск сейчас:\n🌡 Температура: {cur['temperature_2m']}°C\n☁️ Облачность: {cur['cloud_cover']}%\n💨 Ветер: {cur['wind_speed_10m']} км/ч ({get_wind_power(cur['wind_speed_10m'])})\n🌧 Осадки: {prec_forecast}\n📈 Давление: {int(cur['surface_pressure'] * 0.750062)} мм\n🍃 Воздух: {aq['current']['pm2_5']} PM2.5\n\n🌒 Ночь\n🌡 От {min(night_temps)}°C до {max(night_temps)}°C\n☁️ Облачность ночью: {w['hourly']['cloud_cover'][hour+4]}%\n💨 Ветер: {w['hourly']['wind_speed_10m'][hour+4]} км/ч\n")
        ai_prompt = f"Сегодня {current_date}. Ты метеоролог. Сейчас вечер в Пинске. Данные вечер ({cur['temperature_2m']}°C) и день ({history.get('day_temp','?') }°C). Расскажи как изменилась погода, как это ощущается и чего ждать ночью. Кратко 1-2 предложения. Если нет каких-то данных просто сообщи. Пиши сразу по существу, без вводных фраз и заголовков. Не пиши очевидные вещи."

    # 2. ИИ АГЕНТЫ И ЛОГИ
    models = ["google/gemini-2.0-flash-001", "google/gemini-2.0-flash-lite-001"]
    for model in models:
        try:
            res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"}, json={"model": model, "messages": [{"role": "user", "content": ai_prompt}]}, timeout=40).json()
            if 'choices' in res:
                msg += f"\n\n{res['choices'][0]['message']['content'].strip()}"
                print(f"--- ИИ агент {model} сработал ---")
                break
            else:
                print(f"--- Ошибка ИИ {model}: {res.get('error','неизвестно')} ---")
        except Exception as e:
            print(f"--- Ошибка ИИ {model}: {e} ---")

    # 3. ОТПРАВКА И ЛОГИ
    tg_res = requests.post(f"https://api.telegram.org/bot{os.getenv('TELEGRAM_TOKEN')}/sendMessage", json={"chat_id": os.getenv('CHANNEL_ID'), "text": msg, "parse_mode": "Markdown"})
    if tg_res.status_code == 200:
        history['last_sent_key'] = run_key
        with open(history_file, 'w') as f: json.dump(history, f)
        print(f"--- Успех: Сообщение за {period} отправлено ---")
    else:
        print(f"--- Ошибка отправки в Telegram: {tg_res.status_code}, Текст: {tg_res.text} ---")

if __name__ == "__main__":
    main()
