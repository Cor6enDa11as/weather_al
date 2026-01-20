#!/usr/bin/env python3

import os, requests, datetime

def get_wind_dir(deg):
    return ['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ'][int((deg + 22.5) // 45) % 8]

def get_data():
    # Добавили давление (surface_pressure) для анализа циклонов
    url = (
        "https://api.open-meteo.com/v1/forecast?latitude=52.12&longitude=26.10"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,surface_pressure,precipitation,wind_speed_10m,wind_direction_10m"
        "&hourly=temperature_2m,precipitation_probability,cloud_cover"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max"
        "&timezone=auto&models=icon_seamless"
    )
    res = requests.get(url).json()
    try:
        kp_res = requests.get("https://services.swpc.noaa.gov/products/noaa-scales.json", timeout=10).json()
        idx = int(kp_res['0'].get('rescale_value', 0))
        mag = f"{idx} (спокойный)" if idx < 4 else f"{idx} (буря! ⚠️)"
    except: mag = "нет данных"
    return res, mag

def main():
    now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3)
    hour, weekday = now.hour, now.weekday() # 6 - это воскресенье
    weather, mag = get_data()

    curr = weather.get('current', {})
    day = weather.get('daily', {})

    temp = curr.get('temperature_2m', 'н/д')
    press = curr.get('surface_pressure', 760)

    # 1. ДЕЖУРКА (Днем)
    if 9 <= hour <= 19:
        msg = (f"#прогнозпогоды\n\n📍 **ОПЕРАТИВНАЯ СВОДКА ПИНСК**\n\n"
               f"🌡️ Температура: {temp}°C\n"
               f"💨 Ветер: {curr.get('wind_speed_10m')} км/ч\n"
               f"🧲 Магнитный фон: {mag}\n\n"
               f"📊 Источник: ICON-BY")

    # 2. АНАЛИТИЧЕСКИЙ ПРОГНОЗ (Утро/Вечер)
    else:
        # Собираем контекст для синоптика
        is_sunday_evening = (weekday == 6 and hour >= 20)

        # Данные на неделю для воскресенья
        week_summary = ""
        if is_sunday_evening:
            week_summary = "ПРОГНОЗ НА НЕДЕЛЮ: " + ", ".join([f"{day['temperature_2m_max'][i]}°C" for i in range(1, 7)])

        prompt = (
            f"Ты — ведущий синоптик Пинск.Инфо. Сделай краткую профессиональную аналитику.\n"
            f"ДАННЫЕ: Температура {temp}°C, Давление {press} гПа (норма 1013), Ветер {curr.get('wind_speed_10m')} км/ч.\n"
            f"{week_summary}\n"
            f"ЗАДАЧА: Объясни ситуацию (антициклон/циклон, влияние на Пинск). Говори профессионально, но понятно. "
            f"Используй 2-3 предложения. В конце добавь совет дня. Включи эмодзи 🛰️, 🌡️."
        )

        ai_analysis = "Атмосферное давление в норме, погода стабильна."
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"},
                json={
                    "model": "google/gemini-2.0-flash-001",
                    "messages": [{"role": "system", "content": "Ты профессиональный метеоролог аналитик."}, {"role": "user", "content": prompt}],
                    "temperature": 0.7
                }, timeout=40)
            if response.status_code == 200:
                ai_analysis = response.json()['choices'][0]['message']['content'].strip()
        except: pass

        title = "🛰️ АНАЛИТИЧЕСКИЙ ОБЗОР" if not is_sunday_evening else "📅 ГЛАВНЫЙ ПРОГНОЗ НЕДЕЛИ"

        msg = (
            f"© MY NEWS ©\n"
            f"#прогнозпогоды\n\n"
            f"**{title}**\n\n"
            f"**1. Текущие показатели:**\n"
            f"🌡️ Температура: {temp}°C (ощущается {curr.get('apparent_temperature')}°C)\n"
            f"💨 Ветер: {curr.get('wind_speed_10m')} км/ч\n"
            f"🧲 Магнитный фон: {mag}\n\n"
            f"**2. Аналитика синоптика:**\n"
            f"{ai_analysis}\n\n"
            f"**3. Завтра в Пинске:**\n"
            f"🌡️ от {day['temperature_2m_min'][1]}° до {day['temperature_2m_max'][1]}°C\n"
            f"☔ Осадки: {day['precipitation_probability_max'][1]}%\n\n"
            f"Источник: ICON-BY & ECMWF"
        )

    # Отправка
    url = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_TOKEN')}/sendMessage"
    requests.post(url, json={'chat_id': os.getenv('CHANNEL_ID'), 'text': msg, 'parse_mode': 'Markdown'})

if __name__ == "__main__":
    main()
