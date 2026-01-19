#!/usr/bin/env python3
import os
import requests
import datetime

def get_wind_dir(deg):
    return ['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ'][int((deg + 22.5) // 45) % 8]

def get_data():
    print("--- 📡 Шаг 1: Сбор точных метеоданных (ECMWF/ICON) ---")
    url = (
        "https://api.open-meteo.com/v1/forecast?latitude=52.12&longitude=26.10"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,wind_speed_10m,wind_direction_10m"
        "&hourly=temperature_2m,precipitation_probability"
        "&daily=temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_probability_max"
        "&timezone=auto&models=best_match"
    )
    res = requests.get(url).json()
    try:
        kp_url = "https://services.swpc.noaa.gov/products/noaa-scales.json"
        kp_res = requests.get(kp_url, timeout=10).json()
        idx = int(kp_res['0'].get('rescale_value', 0))
        mag = "спокойный" if idx < 4 else "неспокойный" if idx == 4 else "буря! ⚠️"
    except: mag = "нет данных"
    return res, mag

def main():
    now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3)
    hour = now.hour
    weather, mag = get_data()
    curr, day = weather['current'], weather['daily']

    w_info = (
        f"Температура: {curr['temperature_2m']}°C (ощущается как {curr['apparent_temperature']}°C). "
        f"Влажность: {curr['relative_humidity_2m']}%. "
        f"Ветер: {curr['wind_speed_10m']} км/ч, направление {get_wind_dir(curr['wind_direction_10m'])}. "
        f"Осадки сейчас: {curr['precipitation']} мм."
    )

    if hour == 6:
        task = (f"УТРЕННИЙ ПРОГНОЗ. Данные: {w_info}. "
                f"День: {day['temperature_2m_min'][0]}°..{day['temperature_2m_max'][0]}°C. "
                f"Осадки: {day['precipitation_probability_max'][0]}%. Солнце: {day['sunrise'][0][-5:]}—{day['sunset'][0][-5:]}. "
                f"Магнитный фон: {mag}. Напиши прогноз и совет по одежде.")
    elif hour >= 20:
        task = (f"ВЕЧЕРНИЙ ПРОГНОЗ. Данные: {w_info}. "
                f"Ночь: {weather['hourly']['temperature_2m'][27]}°C. Завтра днем: {day['temperature_2m_max'][1]}°C. "
                f"Подведи итоги дня и дай прогноз на ночь.")
    else:
        task = f"ОПЕРАТИВНАЯ СВОДКА. Данные: {w_info}. Осадки ближайшие 2ч: {weather['hourly']['precipitation_probability'][1]}%."

    print("--- 🤖 Шаг 2: Анализ ИИ-агентом ---")
    models = [
        "meta-llama/llama-3.3-70b-instruct:free",
        "google/gemini-2.0-flash-exp:free",
        "qwen/qwen-2.5-72b-instruct:free"
    ]

    api_key = os.getenv('OPENROUTER_API_KEY')
    final_text = ""

    # Максимально жесткая инструкция по эмодзи
    system_msg = (
        "Ты — ведущий метеоролог Пинск.Инфо. Твой стиль: деловой, структурированный. "
        "ВАЖНОЕ ПРАВИЛО: Каждая строка должна начинаться с тематического эмодзи. "
        "ОБЯЗАТЕЛЬНО используй: 🌡️ (температура), 💨 (ветер), 💧 (влажность), 🌙 (ночь), ☀️ (день), 🧲 (фон). "
        "Текст должен быть красивым и наглядным. В конце добавь: '📊 Источник: ECMWF & ICON (DWD)'."
    )

    for model in models:
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "https://github.com/weather_al",
                    "X-Title": "Pinsk Weather AI"
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": task}
                    ],
                    "temperature": 0.7 # Добавим немного креативности для эмодзи
                }, timeout=35)

            if response.status_code == 200:
                final_text = response.json()['choices'][0]['message']['content']
                print(f"✅ Успех с {model}")
                break
        except: continue

    if not final_text:
        final_text = f"🌡️ Пинск: {curr['temperature_2m']}°C\n💨 Ветер: {curr['wind_speed_10m']} км/ч\n📊 Источник: Open-Meteo"

    print("--- 📲 Шаг 3: Отправка в Telegram ---")
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('CHANNEL_ID')
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {'chat_id': chat_id, 'text': final_text, 'parse_mode': 'Markdown'}
    resp = requests.post(url, json=payload)
    if resp.status_code != 200:
        payload.pop('parse_mode')
        requests.post(url, json=payload)

if __name__ == "__main__":
    main()
