#!/usr/bin/env python3

import os, requests, datetime, logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_weather_desc(code):
    codes = {
        0: "ясно", 1: "преимущественно ясно", 2: "переменная облачность", 3: "пасмурно",
        51: "легкая морось", 53: "умеренная морось", 55: "плотная морось",
        61: "небольшой дождь", 63: "дождь", 65: "сильный дождь",
        71: "небольшой снег", 73: "снег", 75: "сильный снегопад",
        77: "снежные зерна", 80: "ливневый дождь", 81: "сильный ливень",
        85: "ливневый снег", 86: "сильный ливневый снег", 95: "гроза"
    }
    return codes.get(code, "без осадков")

def get_aqi_status(pm25):
    if pm25 <= 10: return "Идеально чистый"
    if pm25 <= 25: return "Чистый (норма)"
    if pm25 <= 50: return "Умеренно загрязненный"
    return "Загрязненный (смог) ⚠️"

def get_mag_status(kp):
    if kp < 4: return "Штиль (спокойно)"
    if kp == 4: return "Неустойчивый (слабая вспышка)"
    return f"Магнитная буря (уровень G{kp-4}) ⚠️"

def get_weather_data():
    url = (
        "https://api.open-meteo.com/v1/forecast?latitude=52.12&longitude=26.10"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,surface_pressure,precipitation,cloud_cover,wind_speed_10m,wind_direction_10m,weather_code"
        "&hourly=temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,cloud_cover"
        "&daily=temperature_2m_max,temperature_2m_min,sunrise,sunset"
        "&timezone=auto&models=icon_seamless"
    )
    aq_url = "https://air-quality-api.open-meteo.com/v1/air-quality?latitude=52.12&longitude=26.10&current=pm2_5"
    try:
        w = requests.get(url).json()
        aq = requests.get(aq_url).json()
        kp_res = requests.get("https://services.swpc.noaa.gov/products/noaa-scales.json", timeout=10).json()
        kp = int(kp_res['0'].get('rescale_value', 0))
    except: kp, aq = 0, {'current': {'pm2_5': 0}}
    return w, aq.get('current', {}).get('pm2_5', 0), kp

def main():
    now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3)
    hour, weekday = now.hour, now.weekday()
    w, pm25, kp = get_weather_data()
    cur, day, hr = w['current'], w['daily'], w['hourly']

    precip_info = "не ожидаются"
    for i in range(hour, hour + 12):
        if i < len(hr['precipitation']) and hr['precipitation'][i] > 0.1:
            precip_info = f"{get_weather_desc(hr['weather_code'][i])} в {i%24:02d}:00"
            break

    timeline = ""
    for h in [0, 3, 6, 9]:
        idx = h + 24 if hour > 20 else h
        if idx < len(hr['temperature_2m']):
            t = hr['temperature_2m'][idx]
            app = hr['apparent_temperature'][idx]
            wind = hr['wind_speed_10m'][idx]
            cloud = hr['cloud_cover'][idx]
            desc = get_weather_desc(hr['weather_code'][idx])
            timeline += f"{h:02d}:00({t}°C, ощущ.{app}°C, ветер {wind}км/ч, облачность {cloud}%, {desc}), "

    air_status = get_aqi_status(pm25)
    mag_status = get_mag_status(kp)

    data_str = (f"Пинск сейчас: {cur['temperature_2m']}°C (ощущ. {cur['apparent_temperature']}°C). "
                f"Облачность {cur['cloud_cover']}%, осадки: {precip_info}. "
                f"Воздух: {air_status} (PM2.5: {pm25}). Магнитный фон: {mag_status}. "
                f"Таймлайн ночи/утра: {timeline} "
                f"Закат {day['sunset'][1][-5:]}. Завтра: {day['temperature_2m_min'][1]}..{day['temperature_2m_max'][1]}°C")

    if 7 <= hour <= 19:
        msg = (f"#прогноз\n\n"
               f"🌡️ **Температура:** {cur['temperature_2m']}°C (ощущ. {cur['apparent_temperature']}°C)\n"
               f"☁️ **Облачность:** {cur['cloud_cover']}%\n"
               f"🌨️ **Осадки:** {precip_info}\n"
               f"🍃 **Воздух:** {air_status}\n"
               f"🧲 **Магнитный фон:** {mag_status}\n"
               f"💨 **Ветер:** {cur['wind_speed_10m']} км/ч\n\n"
               f"Источник: ICON-BY")
    else:
        is_sun_evening = (weekday == 6 and hour >= 20)
        tag = "#прогнозутро" if hour == 5 else ("#прогнознеделя" if is_sun_evening else "#прогнозвечер")

        model_name = "google/gemini-2.0-flash-001"
        prompts = {
            "#прогнозутро": f"Ты метеоролог-аналитик профи 👨‍🔬. Сейчас утро 🌅. На основе данных: {data_str} сделай КРАТКУЮ сводку на утро и день в одном формате и укажи все данные(температуры,осадки,ветер,облачность). Данные о темп. (реальной и ощущаемой 🧤), осадках (тип/время) 🌨️, качестве воздуха 🍃 и восходе. Кратко объясни глобальный фон: какие воздушные массы (циклоны/антициклоны и их название) влияют на Пинск и Палесье и какие изменения принесёт 🇧🇾🚣‍♂️.Стиль:кратко, без воды,всегда указывай числовые значения и расшифровки для сводки, эмодзи вставляй в начало, походящие по смыслу 🛰️📉🧊☔🌀☀️🌡️🧲🌨️🧤☁️💨🇧🇾🌅🌬️.",
            "#прогнозвечер": f"Ты метеоролог-аналитик профи 👨‍🔬. Сейчас вечер 🌙. На основе данных: {data_str} сделай КРАТКУЮ сводку на вечер, ночь и утро в одном формате и укажи все данные(температуры,осадки,ветер,облачность). Кратко объясни  какие воздушные массы (циклоны/антициклоныи их название) влияют на Пинск и Палесье и какие изменения принесёт 🌀☀️. Стиль: кратко,без воды,всегда указывай числовые значения и расшифровки для сводки, эмодзи вставляй в начало, походящие по смыслу 🌠🛰️📉🧊☔🌀☀️🌡️🧲🌨️🧤☁️💨🇧🇾🌅.",
            "#прогнознеделя": f"Ты метеоролог-аналитик профи 👨‍🔬. Воскресенье 📅. На основе данных на неделю: {day['temperature_2m_max']} сделай КРАТКУЮ сводку на каждый день недели в одном формате и укажи все данные(температуры,осадки,ветер,облачность). Сделай СЖАТУЮ аналитику. Опиши смену воздушных масс, циклоны/антициклоны (и их название) и их влияние на Палесье и какие изменения принесёт 🇧🇾.Стиль:кратко, без воды, всегда указывай числовые значения и расшифровки для сводки,эмодзи вставляй в начало, походящие по смыслу 🛰️📉🧊☔🌀☀️🌡️🧲🌨️🧤☁️💨🇧🇾🌅."
        }

        logger.info(f"ЗАПУСК ИИ: {model_name} для тега {tag}")
        ai_text = "Аналитика недоступна."
        try:
            res = requests.post("https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"},
                json={"model": model_name, "messages": [{"role": "user", "content": prompts[tag]}], "temperature": 0.7}, timeout=45)
            if res.status_code == 200:
                ai_text = res.json()['choices'][0]['message']['content'].strip()
                logger.info(f"ИИ СРАБОТАЛ УСПЕШНО [{model_name}]")
        except Exception as e: logger.error(f"Ошибка ИИ: {e}")

        ai_text_safe = ai_text.replace("_", "\\_").replace("[", "\\[").replace("`", "\\`")
        msg = f"{tag}\n\n{ai_text_safe}\n\nИсточник: ICON-BY & ECMWF"

    try:
        payload = {'chat_id': os.getenv('CHANNEL_ID'), 'text': msg, 'parse_mode': 'Markdown'}
        tg_res = requests.post(f"https://api.telegram.org/bot{os.getenv('TELEGRAM_TOKEN')}/sendMessage", json=payload)
        if tg_res.status_code != 200:
            payload.pop('parse_mode')
            requests.post(f"https://api.telegram.org/bot{os.getenv('TELEGRAM_TOKEN')}/sendMessage", json=payload)
    except Exception as e: logger.error(f"Send Error: {e}")

if __name__ == "__main__":
    main()
