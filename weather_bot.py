#!/usr/bin/env python3

import os, requests, datetime, json

# --- Настройки ---
LAT, LON = 52.12, 26.10

def get_wind_power(speed):
    if speed < 5: return "штиль 💨"
    if speed < 12: return "слабый 🍃"
    if speed < 29: return "умеренный 🌬️"
    if speed < 50: return "сильный 🌪️"
    return "ОЧЕНЬ СИЛЬНЫЙ ⚠️"

def get_weather_desc(code):
    codes = {0: "ясно ☀️", 1: "преимущественно ясно ✨", 2: "переменная облачность ⛅", 3: "пасмурно ☁️",
             51: "слабая морось 💧", 61: "небольшой дождь 🌦️", 71: "небольшой снег 🌨️", 73: "снег ❄️"}
    return codes.get(code, "без осадков")

def main():
    print("--- Запуск бота ---")

    # 1. Получаем время
    now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3)
    hour = now.hour
    print(f"Текущий час (МСК): {hour}")

    # 2. Данные погоды
    print("Запрос данных погоды...")
    w_url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&current=temperature_2m,relative_humidity_2m,apparent_temperature,surface_pressure,weather_code,wind_speed_10m,cloud_cover,uv_index&hourly=temperature_2m,weather_code,wind_speed_10m&daily=sunrise,sunset&timezone=auto"
    r = requests.get(w_url)
    r.raise_for_status()
    w = r.json()
    cur = w['current']

    # 3. История (кэш)
    history_file = 'weather_history.json'
    try:
        with open(history_file, 'r') as f: history = json.load(f)
        print("История загружена")
    except:
        history = {}
        print("История не найдена, создаем новую")

    msg = ""
    ai_prompt = ""

    # ЛОГИКА СВОДОК
    if 4 <= hour <= 8:
        history['morning_temp'] = cur['temperature_2m']
        msg = f"🌅 **УТРЕННЯЯ СВОДКА** #прогнозутро\n\n"
        ai_prompt = f"Ты метеоролог. Дай краткую аналитику (2 предложения) движения фронтов для Пинска. Сейчас: {get_weather_desc(cur['weather_code'])}, темп {cur['temperature_2m']}°C. Без цифр!"
    elif 13 <= hour <= 16:
        history['day_temp'] = cur['temperature_2m']
        msg = f"☀️ **ДНЕВНАЯ ДЕЖУРКА** #прогноз\n\n"
        prev = history.get('morning_temp', 'неизвестно')
        ai_prompt = f"Сравни кратко (1-2 фразы) текущую погоду ({cur['temperature_2m']}°C) с утренней ({prev}°C) в Пинске. Объясни причину физически. Без лишних знаков."
    else:
        msg = f"🌃 **ВЕЧЕРНЯЯ СВОДКА** #прогнозвечер\n\n"
        prev = history.get('day_temp', 'неизвестно')
        ai_prompt = f"Сравни кратко (1-2 фразы) вечер ({cur['temperature_2m']}°C) с днем ({prev}°C) в Пинске. Объясни физику изменений. Без лишних знаков."

    # Основной текст
    main_text = (f"🏙 **Пинск сейчас:**\n"
                 f"* 🌡 {cur['temperature_2m']}°C (ощущ. {cur['apparent_temperature']}°C)\n"
                 f"* 💨 {cur['wind_speed_10m']} км/ч ({get_wind_power(cur['wind_speed_10m'])})\n"
                 f"* 📈 Давление: {int(cur['surface_pressure'] * 0.750062)} мм\n"
                 f"* 💧 Влажность: {cur['relative_humidity_2m']}%\n")
    msg += main_text

    # 4. Запрос к ИИ
    print(f"Запрос к ИИ (OpenRouter)...")
    try:
        ai_res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"},
            json={"model": "google/gemini-2.0-flash-001", "messages": [{"role": "user", "content": ai_prompt}]},
            timeout=20
        )
        ai_text = ai_res.json()['choices'][0]['message']['content']
        msg += f"\n---\n👨‍🔬 **АНАЛИЗ:**\n{ai_text}"
        print("ИИ ответил успешно")
    except Exception as e:
        print(f"Ошибка ИИ: {e}")

    # 5. Сохранение истории
    with open(history_file, 'w') as f: json.dump(history, f)

    # 6. Отправка в Telegram
    print("Отправка в Telegram...")
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('CHANNEL_ID')

    t_url = f"https://api.telegram.org/bot{token}/sendMessage"
    final_res = requests.post(t_url, json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})

    if final_res.status_code == 200:
        print("✅ СООБЩЕНИЕ ОТПРАВЛЕНО!")
    else:
        print(f"❌ ОШИБКА TELEGRAM: {final_res.text}")

if __name__ == "__main__":
    main()
