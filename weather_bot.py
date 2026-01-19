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
    now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3)
    hour = now.hour
    weather, mag = get_data()

    curr = weather['current']
    day = weather['daily']
    w_info = (f"Т: {curr['temperature_2m']}°C, Вл: {curr['relative_humidity_2m']}%, "
              f"Ветер: {curr['wind_speed_10m']}км/ч ({get_wind_dir(curr['wind_direction_10m'])})")

    if hour == 6:
        task = (f"Данные: {w_info}. День: {day['temperature_2m_min'][0]}..{day['temperature_2m_max'][0]}°C. "
                f"Осадки: {day['precipitation_probability_max'][0]}%. Солнце: {day['sunrise'][0][-5:]}-{day['sunset'][0][-5:]}. "
                f"Бури: {mag}. Сделай утренний обзор и дай совет по одежде.")
    elif hour >= 20:
        task = (f"Данные: {w_info}. Ночь: {weather['hourly']['temperature_2m'][27]}°C. "
                f"Завтра: {day['temperature_2m_max'][1]}°C. Подведи итог дня.")
    else:
        task = (f"Данные: {w_info}. Осадки ближайшие 2ч: {weather['hourly']['precipitation_probability'][1]}%. "
                f"Краткая сводка ситуации.")

    # САМЫЙ АКТУАЛЬНЫЙ СПИСОК БЕСПЛАТНЫХ МОДЕЛЕЙ
    models = [
        "google/gemini-2.0-flash-exp:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "deepseek/deepseek-chat:free",
        "qwen/qwen-2.5-72b-instruct:free",
        "mistralai/mistral-7b-instruct:free"
    ]

    api_key = os.getenv('OPENROUTER_API_KEY')
    system_prompt = "Ты Пинск.Инфо. Стиль: строгий, деловой. Используй эмодзи: 🌡, 💨, 🌅, 🌇, ☂️, 🧲."

    final_text = ""
    for model in models:
        try:
            print(f"Запрос к {model}...")
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "https://github.com/weather_al",
                    "X-Title": "Pinsk Weather Bot",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": task}
                    ]
                }, timeout=30)

            if response.status_code == 200:
                result = response.json()
                if 'choices' in result:
                    final_text = result['choices'][0]['message']['content']
                    print(f"Успех с моделью {model}!")
                    break
            else:
                print(f"Ошибка {model}: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Сбой {model}: {e}")
            continue

    if not final_text:
        final_text = (f"🌡 **Пинск: {curr['temperature_2m']}°C**\n"
                      f"💨 Ветер: {curr['wind_speed_10m']} км/ч\n"
                      f"💧 Влажность: {curr['relative_humidity_2m']}%\n"
                      f"🧲 Бури: {mag}\n\n"
                      "⚠️ Аналитика временно недоступна (OpenRouter Busy).")

    requests.get(f"https://api.telegram.org/bot{os.getenv('TELEGRAM_TOKEN')}/sendMessage",
                 params={'chat_id': os.getenv('CHANNEL_ID'), 'text': final_text, 'parse_mode': 'Markdown'})

if __name__ == "__main__":
    main()
