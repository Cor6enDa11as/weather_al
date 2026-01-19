#!/usr/bin/env python3
import os
import requests
import datetime

def get_wind_dir(deg):
    return ['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ'][int((deg + 22.5) // 45) % 8]

def get_data():
    url = ("https://api.open-meteo.com/v1/forecast?latitude=52.12&longitude=26.10"
           "&current=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m"
           "&hourly=temperature_2m,precipitation_probability"
           "&daily=temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_probability_max"
           "&timezone=auto")
    res = requests.get(url).json()
    try:
        kp = requests.get("https://services.swpc.noaa.gov/products/noaa-scales.json").json()
        idx = int(kp['0'].get('rescale_value', 0))
        mag = "спокойный" if idx < 4 else "неспокойный" if idx == 4 else "магнитная буря!"
    except: mag = "нет данных"
    return res, mag

def main():
    now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3)
    hour = now.hour
    weather, mag = get_data()
    curr, day = weather['current'], weather['daily']

    # Расширенные данные для ИИ
    w_info = (f"Т: {curr['temperature_2m']}°C, Вл: {curr['relative_humidity_2m']}%, "
              f"Ветер: {curr['wind_speed_10m']}км/ч ({get_wind_dir(curr['wind_direction_10m'])})")

    if hour == 6:
        task = (f"Утренний пост для Пинска. Сейчас {w_info}. "
                f"Прогноз: {day['temperature_2m_min'][0]}..{day['temperature_2m_max'][0]}°C. "
                f"Осадки: {day['precipitation_probability_max'][0]}%. Солнце: {day['sunrise'][0][-5:]}—{day['sunset'][0][-5:]}. "
                f"Магнитный фон: {mag}. Опиши погоду на день и дай добрый совет по одежде.")
    elif hour >= 20:
        task = (f"Вечерний Пинск. Сейчас {w_info}. "
                f"Ночь: {weather['hourly']['temperature_2m'][27]}°C. "
                f"Завтра: {day['temperature_2m_max'][1]}°C. Подведи итоги дня, пожелай спокойной ночи.")
    else:
        task = f"Сводка в течение дня. {w_info}. Осадки в ближайшие 2ч: {weather['hourly']['precipitation_probability'][1]}%. Коротко о текущих изменениях."

    # Оставляем только те модели, которые работают стабильно
    models = [
        "meta-llama/llama-3.3-70b-instruct:free",
        "google/gemini-2.0-flash-exp:free",
        "qwen/qwen-2.5-72b-instruct:free"
    ]

    api_key = os.getenv('OPENROUTER_API_KEY')
    final_text = ""

    # Системная установка: просим писать содержательно, но без воды
    system_msg = ("Ты автор канала Пинск.Инфо. Пиши содержательно, используй много тематических эмодзи. "
                  "Текст должен быть уютным, но деловым. Структурируй по пунктам.")

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
                    ]
                }, timeout=30)
            if response.status_code == 200:
                final_text = response.json()['choices'][0]['message']['content']
                break
        except: continue

    if not final_text:
        final_text = f"🌡 Пинск сегодня: {curr['temperature_2m']}°C\n💨 Ветер: {curr['wind_speed_10m']}км/ч\n🧲 Фон: {mag}"

    requests.get(f"https://api.telegram.org/bot{os.getenv('TELEGRAM_TOKEN')}/sendMessage",
                 params={'chat_id': os.getenv('CHANNEL_ID'), 'text': final_text, 'parse_mode': 'Markdown'})

if __name__ == "__main__":
    main()
