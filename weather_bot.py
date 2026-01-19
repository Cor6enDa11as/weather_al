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
    # Настройка времени для Пинска (UTC+3)
    now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3)
    hour = now.hour
    weather, mag = get_data()

    curr = weather['current']
    day = weather['daily']
    w_info = (f"Т: {curr['temperature_2m']}°C, Вл: {curr['relative_humidity_2m']}%, "
              f"Ветер: {curr['wind_speed_10m']}км/ч ({get_wind_dir(curr['wind_direction_10m'])})")

    # Логика формирования задания для ИИ
    if hour == 6:
        task = (f"Данные: {w_info}. День: от {day['temperature_2m_min'][0]} до {day['temperature_2m_max'][0]}°C. "
                f"Осадки: {day['precipitation_probability_max'][0]}%. Световой день: {day['sunrise'][0][-5:]}-{day['sunset'][0][-5:]}. "
                f"Бури: {mag}. Напиши строгий утренний обзор и дай совет по одежде.")
    elif hour >= 20:
        task = (f"Данные: {w_info}. Прогноз на ночь: {weather['hourly']['temperature_2m'][27]}°C, "
                f"осадки ночью: {weather['hourly']['precipitation_probability'][27]}%. "
                f"Завтра: {day['temperature_2m_max'][1]}°C. Подведи итог дня и дай прогноз на ночь.")
    else:
        task = (f"Данные: {w_info}. Осадки ближайшие 2ч: {weather['hourly']['precipitation_probability'][1]}%. "
                f"Напиши текущую ситуацию кратко.")

    # Актуальный список работающих бесплатных моделей
    models = [
        "google/gemma-2-9b-it:free",
        "qwen/qwen-2.5-7b-instruct:free",
        "mistralai/mistral-7b-instruct:free",
        "meta-llama/llama-3.1-8b-instruct:free",
        "meta-llama/llama-3.2-3b-instruct:free"
    ]

    api_key = os.getenv('OPENROUTER_API_KEY')
    system_prompt = (
        "Ты — информационный бот Пинск.Инфо. Стиль: строгий, деловой монолог. "
        "Используй эмодзи: 🌡, 💨, 🌅, 🌇, ☂️, 🧲. Пиши только по делу, без приветствий."
    )

    final_text = ""
    # Попытка запроса к каждой модели из списка
    for model in models:
        try:
            print(f"Попытка запроса к модели: {model}...")
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "https://github.com/weather_al", # Обязательно для OpenRouter
                    "X-Title": "Pinsk Weather Bot"
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": task}
                    ]
                }, timeout=25)

            if response.status_code == 200:
                result = response.json()
                if 'choices' in result and len(result['choices']) > 0:
                    final_text = result['choices'][0]['message']['content']
                    print(f"Успешно получено от {model}")
                    break
            else:
                print(f"Модель {model} ответила ошибкой {response.status_code}: {response.text}")
        except Exception as e:
            print(f"Не удалось связаться с {model}: {e}")
            continue

    # Если ни одна модель не ответила, отправляем "сырые" данные (чтобы канал не пустовал)
    if not final_text:
        print("Критическая ошибка: ни одна модель ИИ не ответила.")
        final_text = (
            f"📍 **Пинск: Текущая сводка**\n\n"
            f"🌡 Температура: {curr['temperature_2m']}°C\n"
            f"💨 Ветер: {curr['wind_speed_10m']} км/ч\n"
            f"💧 Влажность: {curr['relative_humidity_2m']}%\n"
            f"⚠️ Сервис аналитики временно недоступен, приведены сухие данные."
        )

    # Отправка в Telegram
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('CHANNEL_ID')
    requests.get(f"https://api.telegram.org/bot{token}/sendMessage",
                 params={'chat_id': chat_id, 'text': final_text, 'parse_mode': 'Markdown'})

if __name__ == "__main__":
    main()
