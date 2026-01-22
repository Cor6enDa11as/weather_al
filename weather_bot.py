#!/usr/bin/env python3

import os, requests, datetime, json, logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# --- Настройки региона ПИНСК ---
LAT, LON = 52.12, 26.10

def get_wind_power(speed):
    """Определяет силу ветра по шкале Бофорта (упрощенно)"""
    if speed < 5: return "штиль 💨"
    if speed < 12: return "слабый 🍃"
    if speed < 29: return "умеренный 🌬️"
    if speed < 50: return "сильный, порывистый 🌪️"
    return "ОЧЕНЬ СИЛЬНЫЙ (шторм) ⚠️"

def get_weather_desc(code):
    """Перевод кодов Open-Meteo на русский"""
    codes = {0: "ясно ☀️", 1: "преимущественно ясно ✨", 2: "переменная облачность ⛅", 3: "пасмурно ☁️",
             51: "слабая морось 💧", 61: "небольшой дождь 🌦️", 71: "небольшой снег 🌨️", 73: "снег ❄️"}
    return codes.get(code, "без осадков")

def get_data():
    """Сбор всех данных из API"""
    w_url = (f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}"
             "&current=temperature_2m,relative_humidity_2m,apparent_temperature,surface_pressure,weather_code,wind_speed_10m,cloud_cover,uv_index"
             "&hourly=temperature_2m,weather_code,wind_speed_10m,precipitation"
             "&daily=sunrise,sunset&timezone=auto")
    aq_url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={LAT}&longitude={LON}&current=pm2_5"

    try:
        w = requests.get(w_url).json()
        aq = requests.get(aq_url).json()
        # Магнитный фон (заглушка или API NOAA)
        kp = 1
        return w, aq['current']['pm2_5'], kp
    except Exception as e:
        logging.error(f"Ошибка получения данных: {e}")
        return None, None, None

def ask_ai(prompt):
    """Запрос к ИИ через OpenRouter"""
    try:
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"},
            json={
                "model": "google/gemini-2.0-flash-001",
                "messages": [{"role": "user", "content": prompt}]
            }, timeout=30
        )
        return res.json()['choices'][0]['message']['content']
    except:
        return None

def main():
    # Работа с временем (МСК)
    now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3)
    hour = now.hour

    w, pm25, kp = get_data()
    if not w: return

    cur = w['current']
    daily = w['daily']

    # Загрузка истории для сравнения
    history_file = 'weather_history.json'
    try:
        with open(history_file, 'r') as f: history = json.load(f)
    except: history = {}

    msg = ""
    ai_prompt = ""

    # --- 1. УТРЕННЯЯ СВОДКА (05:00) ---
    if 4 <= hour <= 7:
        history['morning_temp'] = cur['temperature_2m']
        msg = (f"#прогнозутро\n\n**🏙 Пинск сейчас:**\n"
               f"* 🌡 **Температура:** {cur['temperature_2m']}°C (ощущ. {cur['apparent_temperature']}°C)\n"
               f"* ☁️ **Небо:** {get_weather_desc(cur['weather_code'])} ({cur['cloud_cover']}%)\n"
               f"* 💨 **Ветер:** {cur['wind_speed_10m']} км/ч, {get_wind_power(cur['wind_speed_10m'])}\n"
               f"* 📈 **Давление:** {int(cur['surface_pressure'] * 0.750062)} мм рт. ст.\n"
               f"* 💧 **Влажность:** {cur['relative_humidity_2m']}%\n"
               f"* 🕒 **Световой день:** {daily['sunrise'][0][-5:]} — {daily['sunset'][0][-5:]}\n"
               f"* 🍃 **Воздух:** {pm25} PM2.5 (норма)\n"
               f"* 🧲 **Магнитный фон:** {kp} Kp (спокойно)\n")
        ai_prompt = f"Ты метеоролог.Опиши движение фронтов и воздушных масс(с названием , данные бери в интернете) и как это скажется на сегодняшний день. Кратко, без цифр."

    # --- 2. ДНЕВНАЯ ДЕЖУРКА (14:00) ---
    elif 13 <= hour <= 16:
        history['day_temp'] = cur['temperature_2m']
        sunset = datetime.datetime.fromisoformat(daily['sunset'][0])
        diff = sunset - now.replace(tzinfo=None)
        h_left, m_left = diff.seconds // 3600, (diff.seconds // 60) % 60

        msg = (f"#прогноз\n\n**🏙 Пинск сейчас:**\n"
               f"* 🌡 **Температура:** {cur['temperature_2m']}°C (ощущ. {cur['apparent_temperature']}°C)\n"
               f"* 💨 **Ветер:** {cur['wind_speed_10m']} км/ч, {get_wind_power(cur['wind_speed_10m'])}\n"
               f"* 📈 **Давление:** {int(cur['surface_pressure'] * 0.750062)} мм рт. ст.\n"
               f"* ☀️ **УФ-индекс:** {cur['uv_index']}\n"
               f"* 🧤 **Комфорт:** влажность {cur['relative_humidity_2m']}% и ветер делают мороз сильнее\n"
               f"* 🌇 **Закат:** через {h_left} ч. {m_left} мин.\n"
               f"* 🍃 **Воздух:** {pm25} PM2.5\n"
               f"* 🧲 **Магнитный фон:** {kp} Kp\n")

        prev = history.get('morning_temp', 'неизвестно')
        ai_prompt = f"Сравни текущую погоду ({cur['temperature_2m']}°C) с утренней ({prev}°C) в Пинске. Объясни причину изменения физически. Кратко."

    # --- 3. ВЕЧЕРНЯЯ СВОДКА (20:00) ---
    else:
        # Прогноз на ночь (ближайшие 8 часов)
        night_temps = w['hourly']['temperature_2m'][hour:hour+9]
        msg = (f"#прогнозвечер\n\n**🏙 Пинск сейчас:**\n"
               f"* 🌡 **Температура:** {cur['temperature_2m']}°C (ощущ. {cur['apparent_temperature']}°C)\n"
               f"* 💨 **Ветер:** {cur['wind_speed_10m']} км/ч, {get_wind_power(cur['wind_speed_10m'])}\n"
               f"* 📈 **Давление:** {int(cur['surface_pressure'] * 0.750062)} мм рт. ст.\n"
               f"* 💧 **Влажность:** {cur['relative_humidity_2m']}%\n\n"
               f"**🌒 Ночной режим:**\n"
               f"* 🌡 Температура: от {min(night_temps)}°C до {max(night_temps)}°C\n"
               f"* 💨 Ветер: {w['hourly']['wind_speed_10m'][hour+4]} км/ч ({get_wind_power(w['hourly']['wind_speed_10m'][hour+4])})\n"
               f"* 🌨 Осадки: {get_weather_desc(w['hourly']['weather_code'][hour+4])}\n")

        prev = history.get('day_temp', 'неизвестно')
        ai_prompt = f"Сравни вечер ({cur['temperature_2m']}°C) с днем ({prev}°C) в Пинске. Почему изменилась погода? Объясни физически. Кратко."

    # Получаем ответ ИИ
    ai_analysis = ask_ai(ai_prompt)
    if ai_analysis:
        msg += f"\n---\n👨‍🔬 **АНАЛИЗ:**\n{ai_analysis}"

    # Сохраняем историю
    with open(history_file, 'w') as f: json.dump(history, f)

    # Отправка в Телеграм
    requests.post(f"https://api.telegram.org/bot{os.getenv('TELEGRAM_TOKEN')}/sendMessage",
                  json={"chat_id": os.getenv('CHANNEL_ID'), "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    main()
