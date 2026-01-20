#!/usr/bin/env python3

import os, requests, datetime

def get_wind_dir(deg):
    return ['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ'][int((deg + 22.5) // 45) % 8]

def get_data():
    url = (
        "https://api.open-meteo.com/v1/forecast?latitude=52.12&longitude=26.10"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,surface_pressure,precipitation,wind_speed_10m,wind_direction_10m"
        "&hourly=temperature_2m,precipitation_probability"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max"
        "&timezone=auto&models=icon_seamless"
    )
    res = requests.get(url).json()
    try:
        kp_res = requests.get("https://services.swpc.noaa.gov/products/noaa-scales.json", timeout=10).json()
        idx = int(kp_res['0'].get('rescale_value', 0))
        mag = f"{idx} (спокойный)" if idx < 4 else f"{idx} (неспокойный)" if idx == 4 else f"{idx} (буря! ⚠️)"
    except: mag = "нет данных"
    return res, mag

def main():
    now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3)
    hour, weekday = now.hour, now.weekday()
    weather, mag = get_data()

    curr = weather.get('current', {})
    day = weather.get('daily', {})

    # Сбор данных
    temp = curr.get('temperature_2m')
    app_temp = curr.get('apparent_temperature')
    press = curr.get('surface_pressure')
    hum = curr.get('relative_humidity_2m')
    wind = f"{curr.get('wind_speed_10m')} км/ч ({get_wind_dir(curr.get('wind_direction_10m', 0))})"

    t_min, t_max = day['temperature_2m_min'][1], day['temperature_2m_max'][1]
    night_temp = weather['hourly']['temperature_2m'][27] # прогноз на 3 часа ночи

    # Формируем задание для ИИ (Аналитика)
    is_sunday = (weekday == 6 and hour >= 20)
    week_data = ""
    if is_sunday:
        week_data = "ПРОГНОЗ НА НЕДЕЛЮ (макс. темп): " + ", ".join([f"{day['temperature_2m_max'][i]}°C" for i in range(1, 7)])

    prompt = (
        f"Ты — ведущий синоптик Пинск.Инфо. Сделай глубокую аналитику на основе данных:\n"
        f"Температура {temp}°C (ощущается как {app_temp}°C), влажность {hum}%, давление {press} гПа, ветер {wind}, магнитный фон {mag}.\n"
        f"Ночь: {night_temp}°C. Завтра: {t_min}..{t_max}°C.\n"
        f"{week_data}\n"
        f"ЗАДАЧА: Объясни метеоситуацию (циклоны, антициклоны, влияние на здоровье). Говори как профи. "
        f"Используй много тематических эмодзи 🛰️, 🌡️, 🧲, 🌬️. Обязательно упомяни ощущаемую температуру и магнитный фон."
    )

    ai_analysis = "Аналитические данные обновляются..."
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"},
            json={
                "model": "google/gemini-2.0-flash-001",
                "messages": [{"role": "system", "content": "Ты эксперт-метеоролог. Пиши аналитику без приветствий."}, {"role": "user", "content": prompt}],
                "temperature": 0.7
            }, timeout=45)
        if response.status_code == 200:
            ai_analysis = response.json()['choices'][0]['message']['content'].strip()
    except: pass

    # СБОРКА ИТОГОВОГО СООБЩЕНИЯ
    header = "📅 ГЛАВНЫЙ ПРОГНОЗ НЕДЕЛИ" if is_sunday else "🛰️ МЕТЕОРОЛОГИЧЕСКАЯ ОБСТАНОВКА"

    message = (
        f"© MY NEWS ©\n"
        f"#прогнозпогоды\n\n"
        f"**{header}**\n\n"
        f"**1. Текущие показатели:**\n"
        f"🌡️ Температура: {temp}°C\n"
        f"🧤 Ощущается как: {app_temp}°C\n"
        f"💧 Влажность: {hum}%\n"
        f"💨 Ветер: {wind}\n"
        f"🧲 Магнитный фон: {mag}\n\n"
        f"**2. Прогноз на ближайшее время:**\n"
        f"🌙 Ночью: около {night_temp}°C\n"
        f"☀️ Завтра днем: от {t_min}° до {t_max}°C\n"
        f"☔ Вероятность осадков: {day['precipitation_probability_max'][1]}%\n\n"
        f"**3. Аналитика синоптика:**\n"
        f"{ai_analysis}\n\n"
        f"Источник: ICON-BY & ECMWF"
    )

    # Отправка
    url = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_TOKEN')}/sendMessage"
    requests.post(url, json={'chat_id': os.getenv('CHANNEL_ID'), 'text': message, 'parse_mode': 'Markdown'})

if __name__ == "__main__":
    main()
