#!/usr/bin/env python3

import os, requests, datetime, logging

# Настройка логов для отслеживания ИИ
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def get_wind_dir(deg):
    return ['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ'][int((deg + 22.5) // 45) % 8]

def get_weather_data():
    # Запрос погоды + качество воздуха
    url = (
        "https://api.open-meteo.com/v1/forecast?latitude=52.12&longitude=26.10"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,surface_pressure,precipitation,cloud_cover,wind_speed_10m,wind_direction_10m"
        "&hourly=temperature_2m,precipitation,cloud_cover&daily=temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_probability_max"
        "&timezone=auto&models=icon_seamless"
    )
    aq_url = "https://air-quality-api.open-meteo.com/v1/air-quality?latitude=52.12&longitude=26.10&current=pm2_5"

    try:
        weather = requests.get(url).json()
        aq = requests.get(aq_url).json()
        kp_res = requests.get("https://services.swpc.noaa.gov/products/noaa-scales.json", timeout=10).json()
        mag = kp_res['0'].get('rescale_value', 0)
    except:
        mag = 0
        aq = {'current': {'pm2_5': 0}}

    return weather, aq.get('current', {}).get('pm2_5', 0), mag

def main():
    # Время МСК (UTC+3)
    now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3)
    hour, weekday = now.hour, now.weekday()
    w, pm25, mag = get_weather_data()

    cur, day, hr = w['current'], w['daily'], w['hourly']

    # Поиск ближайших осадков на 12 часов вперед
    precip_time = "нет"
    for i in range(hour, hour + 12):
        if i < len(hr['precipitation']) and hr['precipitation'][i] > 0.1:
            precip_time = f"в {i%24:02d}:00"
            break

    # Сбор данных для аналитики
    data_str = (f"Пинск: {cur['temperature_2m']}°C (ощущ. {cur['apparent_temperature']}°C), "
                f"облачность {cur['cloud_cover']}%, осадки {precip_time}, влажность {cur['relative_humidity_2m']}%, "
                f"давление {cur['surface_pressure']}гПа, ветер {cur['wind_speed_10m']}км/ч, воздух PM2.5: {pm25}, "
                f"магнит {mag}, восход {day['sunrise'][1][-5:]}, закат {day['sunset'][1][-5:]}. "
                f"Завтра: {day['temperature_2m_min'][1]}..{day['temperature_2m_max'][1]}°C")

    # ЛОГИКА ВЫБОРА ФОРМАТА

    # 1. ДЕЖУРКА (#прогноз) - с 7:00 до 19:00 МСК
    if 7 <= hour <= 19:
        msg = (f"#прогноз\n\n"
               f"🌡️ **Температура:** {cur['temperature_2m']}°C (ощущается {cur['apparent_temperature']}°C)\n"
               f"☁️ **Облачность:** {cur['cloud_cover']}%\n"
               f"🌨️ **Осадки:** {precip_time}\n"
               f"💧 **Влажность:** {cur['relative_humidity_2m']}%\n"
               f"💨 **Ветер:** {cur['wind_speed_10m']} км/ч ({get_wind_dir(cur['wind_direction_10m'])})\n"
               f"🍃 **Воздух PM2.5:** {pm25}\n"
               f"🧲 **Магнитный фон:** {mag}\n\n"
               f"Источник: ICON-BY")

    # 2. АНАЛИТИКА (#прогнозутро, #прогнозвечер, #прогнознеделя)
    else:
        is_sun_evening = (weekday == 6 and hour >= 20)

        if hour == 5:
            tag = "#прогнозутро"
            prompt = f"Ты метеоролог-аналитик профи 👨‍🔬. Сейчас утро 🌅. На основе данных: {data_str} сделай краткую сводку на утро и день ☕🏙️. Вплети данные о темп., ощущаемой 🧤, облачности ☁️, осадках 🌨️, чистоте воздуха 🍃 и восходе ☀️. Выдай кратко сравнительный анализ глобальной метеообстановки в Беларуси 🇧🇾 и в частности на Палесье 🚣‍♂️. Объясни влияние на Пинск 📍. Используй много эмодзи, подставляй их в начало предложений подходящих по смыслу 🛰️🌡️☀️🍃."
        elif is_sun_evening:
            tag = "#прогнознеделя"
            week_data = ", ".join([f"{day['temperature_2m_max'][i]}°C" for i in range(1, 8)])
            prompt = f"Ты метеоролог-аналитик профи 👨‍🔬. Сегодня воскресенье 📅. На основе данных на 7 дней: {week_data} сделай краткую сводку по дням , выдай аналитику предстоящей недели для Пинска 📍. Опиши погодную тенденцию в Беларуси 🇧🇾 и как она отразится на Палесье 🚣‍♂️. Используй огромное количество эмодзи, подставляй их в начало предложений подходящих по смыслу 🛰️📉📈🧊☔🧤."
        else:
            tag = "#прогнозвечер"
            prompt = f"Ты метеоролог-аналитик профи 👨‍🔬. Сейчас вечер 🌙. На основе данных: {data_str} сделай краткую сводку на вечер, ночь и завтрашнее утро 🌌🌑🌅. Вплети данные о закате 🌇, влажности 💧, магнитном фоне 🧲 и чистоте воздуха 🍃. Выдай кратко сравнительный анализ глобальной метеообстановки в Беларуси 🇧🇾 и в частности на Палесье 🚣‍♂️. Расскажи, чего ждать жителям Пинска 📍 от ночного неба и завтрашнего рассвета. Используй максимально много эмодзи, подставляй их в начало предложений подходящих по смыслу 🌠🌡️🧲🌬️."

        logger.info(f"Запрос ИИ для {tag}")
        ai_text = "Аналитика временно недоступна."
        try:
            res = requests.post("https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"},
                json={"model": "google/gemini-2.0-flash-001", "messages": [{"role": "user", "content": prompt}], "temperature": 0.7}, timeout=45)
            ai_text = res.json()['choices'][0]['message']['content'].strip()
        except Exception as e:
            logger.error(f"AI Error: {e}")

        msg = f"{tag}\n\n{ai_text}\n\nИсточник: ICON-BY & ECMWF"

    # Отправка в Telegram
    requests.post(f"https://api.telegram.org/bot{os.getenv('TELEGRAM_TOKEN')}/sendMessage",
                  json={'chat_id': os.getenv('CHANNEL_ID'), 'text': msg, 'parse_mode': 'Markdown'})

if __name__ == "__main__":
    main()
