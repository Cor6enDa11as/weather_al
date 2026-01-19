#!/usr/bin/env python3
import os
import requests
import datetime

import os, requests, datetime

def get_wind_dir(deg):
    return ['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ'][int((deg + 22.5) // 45) % 8]

def get_data():
    print("--- 📡 Шаг 1: Сбор метеоданных ---")
    url = ("https://api.open-meteo.com/v1/forecast?latitude=52.12&longitude=26.10"
           "&current=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m"
           "&hourly=temperature_2m,precipitation_probability"
           "&daily=temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_probability_max"
           "&timezone=auto")
    res = requests.get(url).json()
    try:
        kp = requests.get("https://services.swpc.noaa.gov/products/noaa-scales.json").json()
        idx = int(kp['0'].get('rescale_value', 0))
        mag = "спокойный" if idx < 4 else "неспокойный" if idx == 4 else "буря!"
    except: mag = "нет данных"
    print(f"Данные получены успешно. Магнитный фон: {mag}")
    return res, mag

def main():
    now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3)
    hour = now.hour
    weather, mag = get_data()
    curr, day = weather['current'], weather['daily']

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
        task = f"Сводка дня. {w_info}. Осадки ближайшие 2ч: {weather['hourly']['precipitation_probability'][1]}%. Коротко о текущих изменениях."

    print("--- 🤖 Шаг 2: Работа ИИ-агента ---")
    print(f"Отправляем промпт: {task}")

    models = [
        "meta-llama/llama-3.3-70b-instruct:free",
        "google/gemini-2.0-flash-exp:free",
        "qwen/qwen-2.5-72b-instruct:free"
    ]

    api_key = os.getenv('OPENROUTER_API_KEY')
    final_text = ""
    system_msg = ("Ты автор канала Пинск.Инфо. Пиши содержательно, используй тематические эмодзи. "
                  "Текст должен быть уютным, но деловым. Структурируй по пунктам.")

    for model in models:
        try:
            print(f"Запрос к модели: {model}...")
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
                }, timeout=35)

            if response.status_code == 200:
                final_text = response.json()['choices'][0]['message']['content']
                print(f"✅ Успешный ответ от {model}!")
                print(f"Текст от ИИ: {final_text[:100]}...") # Логируем начало текста
                break
            else:
                print(f"⚠️ Модель {model} отклонила запрос: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Ошибка соединения с {model}: {e}")
            continue

    if not final_text:
        print("🚨 Все ИИ-агенты недоступны. Используем резервный шаблон.")
        final_text = f"🌡 Пинск сегодня: {curr['temperature_2m']}°C\n💨 Ветер: {curr['wind_speed_10m']}км/ч\n🧲 Фон: {mag}"

    print("--- 📲 Шаг 3: Отправка в Telegram ---")
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('CHANNEL_ID')
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {'chat_id': chat_id, 'text': final_text, 'parse_mode': 'Markdown'}
    resp = requests.post(url, json=payload)

    if resp.status_code == 200:
        print("🚀 ГОТОВО: Сообщение в канале!")
    else:
        print(f"❌ ОШИБКА TELEGRAM: {resp.status_code} - {resp.text}")
        # Вторая попытка без Markdown на случай ошибок в символах
        payload.pop('parse_mode')
        requests.post(url, json=payload)

if __name__ == "__main__":
    main()
