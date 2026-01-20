#!/usr/bin/env python3

import os, requests, datetime

def get_wind_dir(deg):
    return ['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ'][int((deg + 22.5) // 45) % 8]

def get_data():
    url = (
        "https://api.open-meteo.com/v1/forecast?latitude=52.12&longitude=26.10"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,wind_speed_10m,wind_direction_10m"
        "&hourly=temperature_2m,precipitation_probability"
        "&daily=temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_probability_max"
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
    curr, day = weather['current'], weather['daily']

    # БАЗОВЫЕ ПЕРЕМЕННЫЕ
    temp = curr['temperature_2m']
    app_temp = curr['apparent_temperature']
    hum = curr['relative_humidity_2m']
    wind = f"{curr['wind_speed_10m']} км/ч ({get_wind_dir(curr['wind_direction_10m'])})"
    tomorrow_min = day['temperature_2m_min'][1]
    tomorrow_max = day['temperature_2m_max'][1]
    night_temp = weather['hourly']['temperature_2m'][27]

    # 1. ДЕЖУРКА (7:00 - 19:59)
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

    # 2. БОЛЬШОЙ ПРОГНОЗ (Утро/Вечер)
    else:
        # Просим ИИ заполнить только смысловые части
        task = (
            f"Напиши 3 коротких блока текста для метеосводки в Пинске.\n"
            f"Данные: Сейчас {temp}°C, Ночью {night_temp}°C, Завтра {tomorrow_min}..{tomorrow_max}°C.\n\n"
            f"Нужно заполнить:\n"
            f"БЛОК_1 (Итоги дня): 2 предложения о том, какая погода была сегодня.\n"
            f"БЛОК_2 (На ночь): прогноз на ночь, упомяни мороз {night_temp}°C.\n"
            f"БЛОК_3 (На завтра): одна фраза о характере погоды завтра.\n\n"
            f"Пиши БЕЗ заголовков, просто текст через разделитель '---'."
        )

        models = ["google/gemini-2.0-flash-001", "qwen/qwen-2.5-72b-instruct"]
        ai_parts = ["Погода была стабильной.", "Ожидается морозная ночь.", "Завтра будет ясно."] # Заглушка

        for model in models:
            try:
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"},
                    json={
                        "model": model,
                        "messages": [{"role": "system", "content": "Ты помощник метеоролога. Пиши кратко, только текст."}, {"role": "user", "content": task}],
                        "temperature": 0.1
                    }, timeout=45
                )
                if response.status_code == 200:
                    raw_text = response.json()['choices'][0]['message']['content']
                    if '---' in raw_text:
                        ai_parts = [p.strip() for p in raw_text.split('---')]
                    break
            except: continue

        # Собираем финальное сообщение программно - ИИ НЕ МОЖЕТ ЭТО СЛОМАТЬ
        final_text = (
            f"#прогнозпогоды\n\n"
            f"**1. Текущие данные:**\n"
            f"🌡️ Температура: {temp}°C (ощущается {app_temp}°C)\n"
            f"💧 Влажность: {hum}%\n"
            f"💨 Ветер: {wind}\n"
            f"🧲 Магнитный фон: {mag}\n\n"
            f"**2. Итоги дня:**\n"
            f"{ai_parts[0] if len(ai_parts)>0 else 'Погода была морозной.'}\n\n"
            f"**3. Прогноз на ночь:**\n"
            f"{ai_parts[1] if len(ai_parts)>1 else f'Температура опустится до {night_temp}°C.'}\n\n"
            f"**4. Прогноз на завтра:**\n"
            f"🌡️ Температура: от {tomorrow_min} до {tomorrow_max}°C\n"
            f"☔ Осадки: {day['precipitation_probability_max'][1]}%\n"
            f"{ai_parts[2] if len(ai_parts)>2 else 'Ожидается облачная погода.'}\n\n"
            f"Источник: ICON-BY & ECMWF"
        )

    # Отправка
    url = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_TOKEN')}/sendMessage"
    requests.post(url, json={'chat_id': os.getenv('CHANNEL_ID'), 'text': final_text, 'parse_mode': 'Markdown'})

if __name__ == "__main__":
    main()
