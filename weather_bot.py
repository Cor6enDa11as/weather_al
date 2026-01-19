#!/usr/bin/env python3
import os
import requests
import datetime

def get_wind_dir(deg):
    return ['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ'][int((deg + 22.5) // 45) % 8]

def get_data():
    print("--- 📡 Шаг 1: Сбор точных метеоданных (ECMWF/ICON) ---")
    # Используем координаты Пинска и лучшие европейские модели
    url = (
        "https://api.open-meteo.com/v1/forecast?latitude=52.12&longitude=26.10"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,wind_speed_10m,wind_direction_10m"
        "&hourly=temperature_2m,precipitation_probability"
        "&daily=temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_probability_max"
        "&timezone=auto&models=best_match"
    )
    res = requests.get(url).json()

    try:
        # Данные по геомагнитной активности (Кп-индекс)
        kp_url = "https://services.swpc.noaa.gov/products/noaa-scales.json"
        kp_res = requests.get(kp_url, timeout=10).json()
        idx = int(kp_res['0'].get('rescale_value', 0))
        mag = "спокойный" if idx < 4 else "неспокойный" if idx == 4 else "магнитная буря! ⚠️"
    except:
        mag = "нет данных"

    print(f"Данные получены. Температура: {res['current']['temperature_2m']}°C")
    return res, mag

def main():
    # Настройка времени (Пинск UTC+3)
    now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3)
    hour = now.hour
    weather, mag = get_data()
    curr, day = weather['current'], weather['daily']

    # Сборка показателей для ИИ
    w_info = (
        f"Температура: {curr['temperature_2m']}°C (ощущается как {curr['apparent_temperature']}°C). "
        f"Влажность: {curr['relative_humidity_2m']}%. "
        f"Ветер: {curr['wind_speed_10m']} км/ч, направление {get_wind_dir(curr['wind_direction_10m'])}. "
        f"Осадки сейчас: {curr['precipitation']} мм."
    )

    # Темы в зависимости от времени суток
    if hour == 6:
        task = (
            f"УТРЕННИЙ ОБЗОР ПИНСКА. Текущие данные: {w_info}. "
            f"Прогноз на день: от {day['temperature_2m_min'][0]}°C до {day['temperature_2m_max'][0]}°C. "
            f"Вероятность осадков: {day['precipitation_probability_max'][0]}%. "
            f"Световой день: {day['sunrise'][0][-5:]} — {day['sunset'][0][-5:]}. "
            f"Геомагнитный фон: {mag}. Напиши подробный прогноз, дай совет по одежде и планам на день."
        )
    elif hour >= 20:
        task = (
            f"ВЕЧЕРНИЙ ИТОГ ПИНСКА. Текущие данные: {w_info}. "
            f"Температура ночью: {weather['hourly']['temperature_2m'][27]}°C. "
            f"Завтра днем ожидается до {day['temperature_2m_max'][1]}°C. "
            f"Подведи краткие итоги дня и дай прогноз на ночь."
        )
    else:
        task = (
            f"ОПЕРАТИВНАЯ СВОДКА. Текущие данные: {w_info}. "
            f"Осадки в ближайшие 2 часа: {weather['hourly']['precipitation_probability'][1]}%. "
            f"Кратко опиши текущую ситуацию на улицах города."
        )

    print("--- 🤖 Шаг 2: Анализ ИИ-агентом ---")
    models = [
        "meta-llama/llama-3.3-70b-instruct:free",
        "google/gemini-2.0-flash-exp:free",
        "qwen/qwen-2.5-72b-instruct:free"
    ]

    api_key = os.getenv('OPENROUTER_API_KEY')
    final_text = ""

    # Системная инструкция (Промпт)
    system_msg = (
        "Ты — ведущий метеоролог канала Пинск.Инфо. Твой стиль: профессиональный, но дружелюбный. "
        "ОБЯЗАТЕЛЬНО начни сообщение с заголовка и используй много эмодзи по теме (🌡️, 💨, 💧, ☀️, ☁️, ❄️, ☔, 🧲). "
        "В конце сообщения ОБЯЗАТЕЛЬНО добавь строчку: '📊 Источник: ECMWF & ICON (DWD)'."
        "Сделай текст структурированным, используй списки."
    )

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
                print(f"✅ Успешный ответ от {model}")
                break
            else:
                print(f"⚠️ Ошибка {model}: {response.status_code}")
        except Exception as e:
            print(f"❌ Ошибка соединения с {model}: {e}")
            continue

    if not final_text:
        final_text = f"🌡️ Пинск сейчас: {curr['temperature_2m']}°C\n💨 Ветер: {curr['wind_speed_10m']} км/ч\n🧲 Фон: {mag}\n📊 Источник: Open-Meteo"

    print("--- 📲 Шаг 3: Отправка в Telegram ---")
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('CHANNEL_ID')
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    # Попытка с Markdown
    payload = {'chat_id': chat_id, 'text': final_text, 'parse_mode': 'Markdown'}
    resp = requests.post(url, json=payload)

    if resp.status_code == 200:
        print("🚀 Сообщение успешно доставлено!")
    else:
        print(f"⚠️ Ошибка форматирования. Отправляю обычным текстом...")
        payload.pop('parse_mode')
        requests.post(url, json=payload)

if __name__ == "__main__":
    main()
