#!/usr/bin/env python3

import os, requests, datetime, logging

# Настройка логов для отслеживания работы ИИ
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_wind_dir(deg):
    return ['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ'][int((deg + 22.5) // 45) % 8]

def get_data():
    url = (
        "https://api.open-meteo.com/v1/forecast?latitude=52.12&longitude=26.10"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,surface_pressure,wind_speed_10m,wind_direction_10m"
        "&hourly=temperature_2m"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max"
        "&timezone=auto&models=icon_seamless"
    )
    res = requests.get(url).json()
    try:
        kp_res = requests.get("https://services.swpc.noaa.gov/products/noaa-scales.json", timeout=10).json()
        idx = int(kp_res['0'].get('rescale_value', 0))
        mag = f"{idx} (спокойный)" if idx < 4 else f"{idx} (неспокойный) ⚠️"
    except: mag = "спокойный"
    return res, mag

def main():
    now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3)
    hour, weekday = now.hour, now.weekday()
    weather, mag = get_data()

    curr = weather.get('current', {})
    day = weather.get('daily', {})

    temp = curr.get('temperature_2m')
    app_temp = curr.get('apparent_temperature')
    press = curr.get('surface_pressure')
    hum = curr.get('relative_humidity_2m')
    wind = f"{curr.get('wind_speed_10m', 0)} км/ч ({get_wind_dir(curr.get('wind_direction_10m', 0))})"

    t_min, t_max = day['temperature_2m_min'][1], day['temperature_2m_max'][1]
    night_temp = weather['hourly']['temperature_2m'][27]

    # 1. ДЕЖУРКА (Днем: с 9:00 до 19:59)
    if 9 <= hour <= 19:
        final_message = (
            f"#прогнозпогоды\n\n"
            f"📍 **ОПЕРАТИВНАЯ СВОДКА**\n\n"
            f"🌡️ Температура: {temp}°C (ощущается как {app_temp}°C)\n"
            f"💧 Влажность: {hum}%\n"
            f"💨 Ветер: {wind}\n"
            f"🧲 Магнитный фон: {mag}\n\n"
            f"📊 Источник: ICON-BY"
        )

    # 2. АНАЛИТИКА ПО ТВОЕМУ ПРОМПТУ (Утро и Вечер)
    else:
        is_sunday = (weekday == 6 and hour >= 20)
        week_data = ""
        if is_sunday:
            temps_week = [f"{day['temperature_2m_max'][i]}°C" for i in range(1, 8)]
            week_data = f"ПРОГНОЗ НА НЕДЕЛЮ (днем): {', '.join(temps_week)}."

        # ПРИМЕНЕНИЕ ТВОЕГО ПРОМПТА
        prompt = (
            f"Ты метеоролог профи. Сделай аналитику на основе данных: "
            f"Темп {temp}°C (ощущается {app_temp}°C), влажность {hum}%, давление {press} гПа, ветер {wind}, магнитный фон {mag}. "
            f"Ночь: {night_temp}°C. Завтра: {t_min}..{t_max}°C. {week_data} "
            f"Объясни кратко глобальную метеоситуацию и наблюдаеммые явления,сделай краткий вывод, используй эмодзи подходящие по смыслу в прогнозе 🛰️, 🌡️, 🧲,🧤,💧,💨,🌙,☀️,☔️,❄️,📉"
        )

        logger.info(f"Запрос аналитики ИИ. Промпт: {prompt}")

        ai_analysis = "Аналитика подготавливается..."
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"},
                json={
                    "model": "google/gemini-2.0-flash-001",
                    "messages": [
                        {"role": "system", "content": "Ты профессиональный синоптик. Пиши только связный текст без списков и нумерации."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7
                }, timeout=45)
            if response.status_code == 200:
                ai_analysis = response.json()['choices'][0]['message']['content'].strip()
                logger.info(f"Ответ ИИ успешно получен.")
        except Exception as e:
            logger.error(f"Ошибка ИИ-агента: {e}")

        final_message = (
            f"#прогнозпогоды\n\n"
            f"{ai_analysis}\n\n"
            f"Источник: ICON-BY & ECMWF"
        )

    # Отправка в Telegram
    token, chat_id = os.getenv('TELEGRAM_TOKEN'), os.getenv('CHANNEL_ID')
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                  json={'chat_id': chat_id, 'text': final_message, 'parse_mode': 'Markdown'})

if __name__ == "__main__":
    main()
