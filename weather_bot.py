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

    if 7 <= hour <= 19:
        # Дежурка (автоматическая)
        final_text = (
            f"#прогнозпогоды\n\n"
            f"📍 **ОПЕРАТИВНАЯ СВОДКА ПИНСК**\n\n"
            f"- 🌡️ Температура: {curr['temperature_2m']}°C\n"
            f"- 🧤 Ощущается как: {curr['apparent_temperature']}°C\n"
            f"- 💧 Влажность: {curr['relative_humidity_2m']}%\n"
            f"- 💨 Ветер: {curr['wind_speed_10m']} км/ч ({get_wind_dir(curr['wind_direction_10m'])})\n"
            f"- 🧲 Магнитный фон: {mag}\n\n"
            f"📊 Источник: ECMWF & ICON"
        )
    else:
        # Большой прогноз (ИИ)
        tomorrow_min, tomorrow_max = day['temperature_2m_min'][1], day['temperature_2m_max'][1]

        task = (
            f"Напиши сообщение СТРОГО по шаблону. Никаких приветствий. Никаких прочерков.\n"
            f"ДАННЫЕ: Температура {curr['temperature_2m']}°C (ощущается как {curr['apparent_temperature']}°C), "
            f"Влажность {curr['relative_humidity_2m']}%, Ветер {curr['wind_speed_10m']} км/ч, Магнитный фон {mag}.\n"
            f"ЗАВТРА: от {tomorrow_min}°C до {tomorrow_max}°C. Осадки: {day['precipitation_probability_max'][1]}%.\n\n"
            f"ШАБЛОН (заполни все пункты текстом):\n"
            f"#прогнозпогоды\n\n"
            f"1. Текущие данные:\n- 🌡️ Температура: {curr['temperature_2m']}°C (ощущается {curr['apparent_temperature']}°C)\n"
            f"- 💧 Влажность: {curr['relative_humidity_2m']}%\n- 💨 Ветер: {curr['wind_speed_10m']} км/ч\n- 🧲 Магнитный фон: {mag}\n\n"
            f"2. Итоги дня:\n(напиши 2-3 предложения о погоде сегодня)\n\n"
            f"3. Прогноз на ночь:\n(напиши прогноз, укажи температуру около {weather['hourly']['temperature_2m'][27]}°C)\n\n"
            f"4. Прогноз на завтра:\n- 🌡️ Температура: от {tomorrow_min} до {tomorrow_max}°C\n- ☔ Осадки: {day['precipitation_probability_max'][1]}%\n\n"
            f"Источник: ECMWF & ICON (DWD)"
        )

        models = ["google/gemini-2.0-flash-001", "qwen/qwen-2.5-72b-instruct"]
        api_key = os.getenv('OPENROUTER_API_KEY')
        final_text = ""

        system_msg = "Ты — бот-метеоролог Пинска. Твоя задача — копировать шаблон и заполнять его данными без пропусков. Запрещено использовать приветствия и прочерки."

        for model in models:
            try:
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "HTTP-Referer": "https://github.com/weather_al"},
                    json={"model": model, "messages": [{"role": "system", "content": system_msg}, {"role": "user", "content": task}], "temperature": 0.1},
                    timeout=60
                )
                if response.status_code == 200:
                    final_text = response.json()['choices'][0]['message']['content']
                    break
            except: continue

        if not final_text:
            final_text = f"#прогнозпогоды\n\n🌡️ Пинск: {curr['temperature_2m']}°C."

    # Отправка
    token, chat_id = os.getenv('TELEGRAM_TOKEN'), os.getenv('CHANNEL_ID')
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': final_text, 'parse_mode': 'Markdown'}
    resp = requests.post(url, json=payload)
    if resp.status_code != 200:
        payload.pop('parse_mode')
        requests.post(url, json=payload)

if __name__ == "__main__":
    main()
