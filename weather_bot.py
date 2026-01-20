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
        "&timezone=auto&models=best_match"
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

    # 1. ТЕКСТ ДЛЯ ДЕЖУРКИ (БЕЗ ИИ)
    if 7 <= hour <= 19:
        final_text = (
            f"#прогнозпогоды\n\n"
            f"📍 **ОПЕРАТИВНАЯ СВОДКА ПИНСК**\n\n"
            f"🌡️ Температура: {curr['temperature_2m']}°C\n"
            f"🧤 Ощущается как: {curr['apparent_temperature']}°C\n"
            f"💧 Влажность: {curr['relative_humidity_2m']}%\n"
            f"💨 Ветер: {curr['wind_speed_10m']} км/ч ({get_wind_dir(curr['wind_direction_10m'])})\n"
            f"☔ Осадки: {curr['precipitation']} мм\n"
            f"🧲 Магнитный фон: {mag}\n\n"
            f"📊 Источник: ECMWF & ICON"
        )

    # 2. ТЕКСТ ДЛЯ БОЛЬШОГО ПРОГНОЗА (С ИИ)
    else:
        w_info = (
            f"Температура: {curr['temperature_2m']}°C (ощущается как {curr['apparent_temperature']}°C). "
            f"Влажность: {curr['relative_humidity_2m']}%. "
            f"Ветер: {curr['wind_speed_10m']} км/ч ({get_wind_dir(curr['wind_direction_10m'])}). "
            f"Магнитный фон: {mag}."
        )

        # Данные на завтра для ИИ
        tomorrow_min = day['temperature_2m_min'][1]
        tomorrow_max = day['temperature_2m_max'][1]

        task = (
            f"Напиши сообщение строго по образцу для данных: {w_info}. "
            f"Завтра: от {tomorrow_min}°C до {tomorrow_max}°C. Осадки: {day['precipitation_probability_max'][1]}%.\n\n"
            f"ОБРАЗЕЦ:\n#прогнозпогоды\n\n**1. Текущие данные:**\n- 🌡️ Температура: ...\n- 💧 Влажность: ...\n"
            f"- 💨 Ветер: ...\n- 🧲 Магнитный фон: ...\n\n**2. Итоги дня:**\n- ...\n\n"
            f"**3. Прогноз на ночь:**\n- ...\n\n**4. Прогноз на завтра:**\n- 🌡️ Температура: от {tomorrow_min} до {tomorrow_max}°C\n- ...\n\n"
            f"Источник: ECMWF & ICON (DWD)"
        )

        models = ["google/gemini-2.0-flash-001", "qwen/qwen-2.5-72b-instruct"]
        api_key = os.getenv('OPENROUTER_API_KEY')
        final_text = ""

        system_msg = (
            "Ты — метеоролог Пинск.Инфо. Пиши строго по формату. Не добавляй никаких приветствий или лишних фраз. "
            "Каждый пункт списка должен начинаться с эмодзи. В блоке 'Прогноз на завтра' обязательно используй цифры температур."
        )

        for model in models:
            try:
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "HTTP-Referer": "https://github.com/weather_al"},
                    json={"model": model, "messages": [{"role": "system", "content": system_msg}, {"role": "user", "content": task}], "temperature": 0.2},
                    timeout=60
                )
                if response.status_code == 200:
                    final_text = response.json()['choices'][0]['message']['content']
                    break
            except: continue

        if not final_text:
            final_text = f"#прогнозпогоды\n\n🌡️ Пинск: {curr['temperature_2m']}°C."

    # ОТПРАВКА
    token, chat_id = os.getenv('TELEGRAM_TOKEN'), os.getenv('CHANNEL_ID')
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': final_text, 'parse_mode': 'Markdown'}
    resp = requests.post(url, json=payload)
    if resp.status_code != 200:
        payload.pop('parse_mode')
        requests.post(url, json=payload)

if __name__ == "__main__":
    main()
