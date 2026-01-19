#!/usr/bin/env python3
import os
import requests
import datetime

def get_wind_dir(deg):
    sectors = ['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ']
    idx = int((deg + 22.5) // 45) % 8
    return sectors[idx]

def get_data():
    url = (
        "https://api.open-meteo.com/v1/forecast?latitude=52.12&longitude=26.10"
        "&current=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m"
        "&hourly=temperature_2m,precipitation_probability"
        "&daily=temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_probability_max"
        "&timezone=auto"
    )
    res = requests.get(url).json()

    try:
        kp_res = requests.get("https://services.swpc.noaa.gov/products/noaa-scales.json").json()
        idx = int(kp_res['0'].get('rescale_value', 0))
        mag = "спокойная" if idx < 4 else "повышенный фон" if idx == 4 else "магнитная буря"
    except:
        mag = "нет данных"

    return res, mag

def main():
    # Пинск (UTC+3)
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
    hour = now.hour
    weather, mag = get_data()

    curr = weather['current']
    day = weather['daily']
    w_info = (f"Т: {curr['temperature_2m']}°C, Влажность: {curr['relative_humidity_2m']}%, "
              f"Ветер: {curr['wind_speed_10m']}км/ч ({get_wind_dir(curr['wind_direction_10m'])})")

    # Определяем режим (Утро 6:00, Вечер 20:00, остальное — оперативка)
    if hour == 6:
        task = (f"Данные: {w_info}. День: от {day['temperature_2m_min'][0]} до {day['temperature_2m_max'][0]}°C. "
                f"Осадки: {day['precipitation_probability_max'][0]}%. Световой день: {day['sunrise'][0][-5:]}-{day['sunset'][0][-5:]}. "
                f"Бури: {mag}. Напиши утренний обзор и дай совет по одежде.")
    elif hour == 20:
        task = (f"Данные: {w_info}. Прогноз на ночь: {weather['hourly']['temperature_2m'][27]}°C, "
                f"осадки ночью: {weather['hourly']['precipitation_probability'][27]}%. "
                f"Завтра: {day['temperature_2m_max'][1]}°C. Подведи итог дня и дай прогноз на ночь.")
    else:
        task = (f"Данные: {w_info}. Осадки ближайшие 2ч: {weather['hourly']['precipitation_probability'][1]}%. "
                f"Напиши текущую ситуацию кратко.")

    # Список актуальных бесплатных моделей OpenRouter
    models = [
        "google/gemma-2-9b-it:free",
        "mistralai/mistral-7b-instruct:free",
        "qwen/qwen-2.5-7b-instruct:free",
        "meta-llama/llama-3.1-8b-instruct:free",
        "microsoft/phi-3-mini-128k-instruct:free"
    ]

    api_key = os.getenv('OPENROUTER_API_KEY')
    system_prompt = (
        "Ты — Пинск.Инфо. Стиль: строгий, деловой, информативный. "
        "Используй эмодзи в начале строк: 🌡 Т, 💨 Ветер, 🌅/🌇 Солнце, ☂️ Осадки, 🧲 Бури."
    )

    final_text = "Ошибка формирования отчета."

    for model in models:
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": task}
                    ]
                }, timeout=15)
            if response.status_code == 200:
                final_text = response.json()['choices'][0]['message']['content']
                break # Если получили ответ, выходим из цикла
        except:
            continue

    # Отправка в Telegram
    requests.get(f"https://api.telegram.org/bot{os.getenv('TELEGRAM_TOKEN')}/sendMessage",
                 params={'chat_id': os.getenv('CHANNEL_ID'), 'text': final_text, 'parse_mode': 'Markdown'})

if __name__ == "__main__":
    main()
