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
        0: "ясно ☀️", 1: "преимущественно ясно ✨", 2: "переменная облачность ⛅",
        3: "пасмурно ☁️", 45: "туман 🌫️", 61: "небольшой дождь 🌧️",
        71: "небольшой снег 🌨️", 95: "гроза ⛈️"
    }
    return codes.get(code, "без осадков")

def get_precipitation_info(hourly_data, start_hour):
    """Ищет время ближайших осадков на 12 часов вперед"""
    for i in range(start_hour, start_hour + 12):
        if i < len(hourly_data['precipitation']):
            prec = hourly_data['precipitation'][i]
            if prec > 0.1:
                time = i % 24
                return f"{prec} мм в {time:02d}:00"
    return "не ожидаются"

def get_kp_desc(kp):
    """Расшифровка индекса магнитной активности"""
    if kp < 4: return f"{kp} Kp (спокойно) ✅"
    if kp < 5: return f"{kp} Kp (небольшие возмущения) ⚠️"
    return f"{kp} Kp (МАГНИТНАЯ БУРЯ) 🆘"

def main():
    # 1. Время (МСК)
    now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3)
    hour = now.hour

    # 2. Сбор данных (Погода + Воздух + Магнитный фон)
    w_url = (f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}"
             "&current=temperature_2m,apparent_temperature,surface_pressure,weather_code,wind_speed_10m,cloud_cover,uv_index,precipitation"
             "&hourly=temperature_2m,weather_code,wind_speed_10m,precipitation,cloud_cover"
             "&daily=sunrise,sunset&timezone=auto")
    aq_url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={LAT}&longitude={LON}&current=pm2_5"
    kp_url = "https://services.swpc.noaa.gov/products/noaa-estimated-planetary-k-index-1-minute.json"

    w = requests.get(w_url).json()
    aq = requests.get(aq_url).json()
    try:
        kp_res = requests.get(kp_url).json()
        current_kp = float(kp_res[-1][1])
    except:
        current_kp = 1.0

    cur = w['current']

    # 3. История для сравнения
    history_file = 'weather_history.json'
    try:
        with open(history_file, 'r') as f: history = json.load(f)
    except: history = {}

    prec_forecast = get_precipitation_info(w['hourly'], hour)
    msg = ""
    ai_prompt = ""

    # --- УТРЕННЯЯ СВОДКА (05:00) ---
    if 4 <= hour <= 8:
        history['morning_temp'] = cur['temperature_2m']
        msg = (f"🌅 #прогнозутро\n\n"
               f"**🏙 Пинск сейчас:**\n"
               f"* 🌡 **Температура:** {cur['temperature_2m']}°C (ощущ. {cur['apparent_temperature']}°C)\n"
               f"* ☁️ **Облачность:** {cur['cloud_cover']}% ({get_weather_desc(cur['weather_code'])})\n"
               f"* 💨 **Ветер:** {cur['wind_speed_10m']} км/ч ({get_wind_power(cur['wind_speed_10m'])})\n"
               f"* 🌧 **Осадки:** {prec_forecast}\n"
               f"* 📈 **Давление:** {int(cur['surface_pressure'] * 0.750062)} мм\n"
               f"* 🧲 **Магнитный фон:** {get_kp_desc(current_kp)}\n"
               f"* 🕒 **Световой день:** {w['daily']['sunrise'][0][-5:]} — {w['daily']['sunset'][0][-5:]}\n"
               f"* 🍃 **Воздух:** {aq['current']['pm2_5']} PM2.5\n")
        ai_prompt = f"Ты метеоролог. Дай глубокую АНАЛИТИКУ движения воздушных масс (циклон,антициклон с названием , физические явления, данные бери в интернете) и как это повлияет на погоду предстоящего дня для Пинска. Без цифр, кратко."

    # --- ДНЕВНАЯ ДЕЖУРКА (14:00) ---
    elif 13 <= hour <= 16:
        history['day_temp'] = cur['temperature_2m']
        sunset = datetime.datetime.fromisoformat(w['daily']['sunset'][0])
        diff = sunset - now.replace(tzinfo=None)
        msg = (f"☀️ #прогноздень\n\n"
               f"**🏙 Пинск сейчас:**\n"
               f"* 🌡 **Температура:** {cur['temperature_2m']}°C (ощущ. {cur['apparent_temperature']}°C)\n"
               f"* ☁️ **Облачность:** {cur['cloud_cover']}%\n"
               f"* 💨 **Ветер:** {cur['wind_speed_10m']} км/ч ({get_wind_power(cur['wind_speed_10m'])})\n"
               f"* 🌧 **Осадки:** {prec_forecast}\n"
               f"* 🧲 **Магнитный фон:** {get_kp_desc(current_kp)}\n"
               f"* 📈 **Давление:** {int(cur['surface_pressure'] * 0.750062)} мм\n"
               f"* ☀️ **УФ-индекс:** {cur['uv_index']}\n"
               f"* 🍃 **Воздух:** {aq['current']['pm2_5']} PM2.5\n"
               f"* 🌇 **Закат:** через {diff.seconds // 3600} ч. {(diff.seconds // 60) % 60} мин.\n")
        prev = history.get('morning_temp', 'неизвестно')
        ai_prompt = f"Сравни текущую погоду ({cur['temperature_2m']}°C) с утренней ({prev}°C) в Пинске. Объясни физику изменений (прогрев, облака, ветер,давление и т.д,магнитный фон если нужно) и как изменилась температура. Кратко."

    # --- ВЕЧЕРНЯЯ СВОДКА (20:00) ---
    else:
        night_temps = w['hourly']['temperature_2m'][hour:hour+9]
        msg = (f"🌃 #прогнозвечер\n\n"
               f"**🏙 Пинск сейчас:**\n"
               f"* 🌡 **Температура:** {cur['temperature_2m']}°C\n"
               f"* ☁️ **Облачность:** {cur['cloud_cover']}%\n"
               f"* 💨 **Ветер:** {cur['wind_speed_10m']} км/ч ({get_wind_power(cur['wind_speed_10m'])})\n"
               f"* 🌧 **Осадки:** {prec_forecast}\n"
               f"* 🧲 **Магнитный фон:** {get_kp_desc(current_kp)}\n\n"
               f"* 📈 **Давление:** {int(cur['surface_pressure'] * 0.750062)} мм\n"
               f"* 🍃 **Воздух:** {aq['current']['pm2_5']} PM2.5\n"
               f"**🌒 Ночь**\n"
               f"* 🌡 От {min(night_temps)}°C до {max(night_temps)}°C\n"
               f"* ☁️ Облачность ночью: {w['hourly']['cloud_cover'][hour+4]}%\n"
               f"* 💨 Ветер: {w['hourly']['wind_speed_10m'][hour+4]} км/ч ({get_wind_power(w['hourly']['wind_speed_10m'][hour+4])})\n")
        prev = history.get('day_temp', 'неизвестно')
        ai_prompt = f"Сравни вечер ({cur['temperature_2m']}°C) с днем ({prev}°C) в Пинске. Объясни физику изменений (прогрев, облака, ветер,давление и т.д ,магнитный фон если нужно) и как изменилась температура. Кратко."

    # 4. ИИ Анализ (OpenRouter)
    print(f"Запуск ИИ-агента с промптом: {ai_prompt[:50]}...")
    try:
        ai_res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"},
            json={"model": "google/gemini-2.0-flash-001", "messages": [{"role": "user", "content": ai_prompt}]},
            timeout=25
        ).json()
        ai_text = ai_res['choices'][0]['message']['content']
        # Исправление ошибки парсинга Telegram: убираем символы разметки из ответа ИИ
        ai_text = ai_text.replace('*', '').replace('_', '').replace('`', '')
        msg += f"\n---\n👨‍🔬 **АНАЛИЗ:**\n{ai_text}"
        print("ИИ-анализ успешно получен.")
    except Exception as e:
        print(f"Ошибка ИИ-агента: {e}")

    # 5. Финализация
    with open(history_file, 'w') as f: json.dump(history, f)
    print("Отправка сообщения в Telegram...")
    tg_res = requests.post(f"https://api.telegram.org/bot{os.getenv('TELEGRAM_TOKEN')}/sendMessage",
                  json={"chat_id": os.getenv('CHANNEL_ID'), "text": msg, "parse_mode": "Markdown"})
    if tg_res.status_code == 200:
        print("Сообщение успешно отправлено.")
    else:
        # Если Markdown все равно ломается, пробуем отправить чистым текстом
        requests.post(f"https://api.telegram.org/bot{os.getenv('TELEGRAM_TOKEN')}/sendMessage",
                      json={"chat_id": os.getenv('CHANNEL_ID'), "text": msg})
        print(f"Ошибка Markdown, отправлено обычным текстом: {tg_res.text}")

if __name__ == "__main__":
    main()
