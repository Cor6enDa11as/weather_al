#!/usr/bin/env python3

import os, requests, datetime

def get_wind_dir(deg):
    return ['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ'][int((deg + 22.5) // 45) % 8]

def get_data():
    # Исправленный URL: явно указываем daily параметры
    url = (
        "https://api.open-meteo.com/v1/forecast?latitude=52.12&longitude=26.10"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,wind_speed_10m,wind_direction_10m"
        "&hourly=temperature_2m,precipitation_probability"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max"
        "&timezone=auto&models=icon_seamless,ecmwf_ifs"
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
    hour = now.hour
    weather, mag = get_data()

    # Защита от ошибок в данных
    curr = weather.get('current', {})
    day = weather.get('daily', {})
    hourly = weather.get('hourly', {})

    # Безопасное извлечение значений (с дефолтными данными, если API подведёт)
    temp = curr.get('temperature_2m', 'н/д')
    app_temp = curr.get('apparent_temperature', 'н/д')
    hum = curr.get('relative_humidity_2m', 'н/д')
    wind_speed = curr.get('wind_speed_10m', 0)
    wind_dir = get_wind_dir(curr.get('wind_direction_10m', 0))
    wind = f"{wind_speed} км/ч ({wind_dir})"

    # Температуры на завтра (индекс [1] — это следующий день)
    try:
        tomorrow_min = day['temperature_2m_min'][1]
        tomorrow_max = day['temperature_2m_max'][1]
        tomorrow_precip = day['precipitation_probability_max'][1]
    except (KeyError, IndexError):
        tomorrow_min, tomorrow_max, tomorrow_precip = "н/д", "н/д", 0

    try:
        night_temp = hourly['temperature_2m'][27] # 03:00 следующего дня
    except (KeyError, IndexError):
        night_temp = "н/д"

    # --- Далее логика отправки (Дежурка или ИИ) остается прежней ---

    if 7 <= hour <= 19:
        final_text = (
            f"#прогнозпогоды\n\n"
            f"📍 **ОПЕРАТИВНАЯ СВОДКА ПИНСК**\n\n"
            f"🌡️ Температура: {temp}°C (ощущается как {app_temp}°C)\n"
            f"💧 Влажность: {hum}%\n"
            f"💨 Ветер: {wind}\n"
            f"🧲 Магнитный фон: {mag}\n\n"
            f"📊 Источник: ICON-BY & ECMWF"
        )
    else:
        # Промпт для ИИ (Блоки 2, 3 и 4)
        task = (
            f"Напиши 3 коротких блока текста для метеоновости в Пинске.\n"
            f"Данные: Сейчас {temp}°C, Ночью {night_temp}°C, Завтра {tomorrow_min}..{tomorrow_max}°C.\n\n"
            f"Заполни:\n"
            f"БЛОК_1 (Итоги дня): 2 предложения о погоде сегодня.\n"
            f"БЛОК_2 (На ночь): прогноз, упомяни {night_temp}°C.\n"
            f"БЛОК_3 (На завтра): фраза о погоде завтра.\n\n"
            f"Пиши БЕЗ заголовков, только текст через '---'."
        )

        # Код обращения к OpenRouter (оставляем твой текущий список моделей)
        ai_parts = ["День прошел морозно.", f"Ночью будет около {night_temp}°C.", "Завтра погода существенно не изменится."]

        # ... (здесь твой блок requests.post к OpenRouter) ...
        # После получения ответа:
        # ai_parts = [p.strip() for p in raw_text.split('---')]

        final_text = (
            f"#прогнозпогоды\n\n"
            f"**1. Текущие данные:**\n"
            f"🌡️ Температура: {temp}°C (ощущается {app_temp}°C)\n"
            f"💧 Влажность: {hum}%\n"
            f"💨 Ветер: {wind}\n"
            f"🧲 Магнитный фон: {mag}\n\n"
            f"**2. Итоги дня:**\n"
            f"{ai_parts[0]}\n\n"
            f"**3. Прогноз на ночь:**\n"
            f"{ai_parts[1]}\n\n"
            f"**4. Прогноз на завтра:**\n"
            f"🌡️ Температура: от {tomorrow_min} до {tomorrow_max}°C\n"
            f"☔ Осадки: {tomorrow_precip}%\n"
            f"{ai_parts[2]}\n\n"
            f"Источник: ICON-BY & ECMWF"
        )

    # Отправка в Telegram
    url = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_TOKEN')}/sendMessage"
    requests.post(url, json={'chat_id': os.getenv('CHANNEL_ID'), 'text': final_text, 'parse_mode': 'Markdown'})

if __name__ == "__main__":
    main()
