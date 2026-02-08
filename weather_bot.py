#!/usr/bin/env python3
import os, requests, datetime, sys

# --- Настройки ---
LAT, LON = 52.12, 26.10
COHERE_KEY = os.getenv('COHERE_API_KEY')
GEMINI_KEY = os.getenv('GEMINI_API_KEY')
TG_TOKEN = os.getenv('TELEGRAM_TOKEN')
CH_ID = os.getenv('CHANNEL_ID')

def log(message):
    now_pinsk = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
    timestamp = now_pinsk.strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")

# --- Функции пояснения (Расширенные) ---
def get_wind_dir(deg):
    dirs = ["С ⬇️", "СВ ↙️", "В ⬅️", "ЮВ ↖️", "Ю ⬆️", "ЮЗ ↗️", "З ➡️", "СЗ ↘️"]
    return dirs[int((deg + 22.5) % 360 / 45)]

def get_weather_desc(code):
    codes = {
        0: "ясно", 1: "преимущественно ясно", 2: "переменная облачность", 3: "пасмурно",
        45: "туман", 48: "туман с инеем",
        51: "легкая морось", 53: "морось", 55: "плотная морось",
        61: "небольшой дождь", 63: "умеренный дождь", 65: "сильный дождь",
        66: "ледяной дождь ⛸", 67: "сильный ледяной дождь ⛸",
        71: "небольшой снег", 73: "снег", 75: "сильный снег ❄️",
        77: "снежные зерна", 80: "ливневый дождь", 81: "сильный ливень", 82: "экстремальный ливень",
        85: "небольшой снежный ливень", 86: "сильный снежный ливень",
        95: "дождь с грозой ⛈", 96: "гроза со слабым градом", 99: "сильная гроза с градом ⛈⚠️"
    }
    return codes.get(code, "осадки")

def get_pressure_desc(p):
    if p < 745: return "(пониженное 📉)"
    if p > 755: return "(повышенное 📈)"
    return "(норма)"

def get_humidity_desc(h, temp):
    if h < 30: return "(сухо 🏜️)"
    if h > 75:
        return "(сыро/пронизывающий холод ❄️)" if temp < 5 else "(влажно/душно 💦)"
    return "(комфортно ✨)"

# --- Каскад ИИ агентов с детальным логированием ---
def ask_ai_cascade(prompt_msg, system_preamble):
    if COHERE_KEY:
        try:
            log("🤖 Запрос к Cohere...")
            res = requests.post("https://api.cohere.ai/v1/chat",
                                headers={"Authorization": f"Bearer {COHERE_KEY}"},
                                json={"message": prompt_msg, "model": "command-r-plus-08-2024", "preamble": system_preamble},
                                timeout=40)
            data = res.json()
            if res.status_code == 200 and 'text' in data:
                log("✅ Cohere отработал успешно.")
                return data['text'].strip()
            log(f"⚠️ Cohere отклонил: {data.get('message', 'ошибка API')}")
        except Exception as e:
            log(f"❌ Ошибка Cohere: {e}")

    if GEMINI_KEY:
        try:
            log("🤖 Запрос к Gemini...")
            url = f"https://generativelanguage.googleapis.com/v1/models/gemini-3-flash:generateContent?key={GEMINI_KEY}"
            payload = {"contents": [{"parts": [{"text": f"{system_preamble}\n\nДанные: {prompt_msg}"}]}]}
            res = requests.post(url, json=payload, timeout=90)
            data = res.json()
            if res.status_code == 200 and 'candidates' in data:
                log("✅ Gemini отработал успешно.")
                return data['candidates'][0]['content']['parts'][0]['text'].strip()
            log(f"⚠️ Gemini отклонил: {data.get('error', {}).get('message', 'ошибка API')}")
        except Exception as e:
            log(f"❌ Ошибка Gemini: {e}")

    return "Аналитика сейчас недоступна."

def main():
    log("🚀 Запуск основной логики...")
    try:
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}"
               f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,surface_pressure,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m,cloud_cover,uv_index,visibility,dew_point_2m"
               f"&hourly=temperature_2m,surface_pressure,relative_humidity_2m,precipitation,precipitation_probability,weather_code,soil_temperature_0cm"
               f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max,sunrise,sunset&past_days=3&timezone=auto")
        res = requests.get(url, timeout=15)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        log(f"❌ Ошибка Open-Meteo: {e}"); sys.exit(1)

    cur = data['current']
    h = data['hourly']
    d = data['daily']
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
    hour, dow = now.hour, now.weekday()
    idx_now = 72 + hour

    temp = cur['temperature_2m']
    delta_24 = round(temp - h['temperature_2m'][idx_now - 24], 1)
    recent_rain = round(sum(h['precipitation'][idx_now - 72 : idx_now]), 1)
    soil_temp = h['soil_temperature_0cm'][idx_now]
    press_now = int(cur['surface_pressure'] * 0.750062)

    future_data = []
    for i in range(1, 4):
        future_data.append(f"Через {i*24}ч: T={d['temperature_2m_max'][3+i]}C, Осадки={d['precipitation_sum'][3+i]}мм")

    precip_info = "без осадков"
    for i in range(idx_now, idx_now + 18):
        v = h['precipitation'][i]
        prob = h['precipitation_probability'][i]
        if v > 0.1 or prob > 20:
            p_time = f"{i % 24:02d}:00"
            p_desc = get_weather_desc(h['weather_code'][i])
            precip_info = f"{p_desc} ({prob}%) ожидается около {p_time}"
            break

    danger_alerts = []
    kp_val = 0
    try:
        kp_res = requests.get("https://services.swpc.noaa.gov/products/noaa-scales.json", timeout=10).json()
        kp_val = float(kp_res[0]['kp']) if isinstance(kp_res, list) else float(kp_res['0']['mag_eff']['kp'])
    except: pass

    if kp_val >= 6: danger_alerts.append(f"{'🔴 КРАСНЫЙ' if kp_val >= 8 else '🟠 ОРАНЖЕВЫЙ'} уровень: Магнитная буря (Kp {kp_val})! 🧲")

    gusts = cur.get('wind_gusts_10m', 0)
    if gusts >= 54: danger_alerts.append(f"{'🔴 КРАСНЫЙ' if gusts >= 90 else '🟠 ОРАНЖЕВЫЙ'} уровень: Ветер {gusts} км/ч! 🌬️")
    if temp >= 30 or temp <= -25: danger_alerts.append("🟠 ОРАНЖЕВЫЙ уровень: Опасная температура!")

    if cur['weather_code'] in [66, 67] or (temp < 1 and soil_temp < 0 and sum(h['precipitation'][idx_now-6:idx_now]) > 0):
        danger_alerts.append("🟠 ОРАНЖЕВЫЙ уровень: Гололедица! ⛸️")

    # --- ИИ Промты (ОБНОВЛЕННЫЕ) ---
    ai_text = ""
    common_context = f"История 72ч: осадков {recent_rain}мм, изм. темп. {delta_24}C. Будущее 72ч: {future_data}. Почва: {soil_temp}C. Давление: {press_now}мм. Магн.фон: {kp_val}Kp. УФ: {cur['uv_index']}."

    if 5 <= hour < 14:
        tag, label = "🌅", "#прогнозутро"
        preamble = ("Ты — ведущий эксперт метеослужбы. Твой анализ базируется на данных и динамике атмосферы.Твоя задача: утвердительно описать синоптический процесс дня и его влияние на погоду и самочувствие.Определи тип воздушной массы,её трансформацию и влияние.Укажи, как сочетание температуры, влажности и давления повлияет на тонус и концентрацию.Оцени состояние подстилающей поверхности (прогрев почвы или выхолаживание).Свяжи тренд давления с облачностью.ПРАВИЛА: Говори уверенно, используй глаголы: «наблюдается», «обусловит», «сформирует», «сохранится»,полностью исключи слова: «вероятно», «возможно», «может быть».Стиль: Сухой, профессиональный, понятный простому человеку.3-4 ёмких предложения.")
    elif hour >= 20:
        tag, label = "🌙", "#прогнозвечер"
        preamble = ("Ты — главный синоптик смены. Подведи итог суточного энергообмена. "
                    "Твоя задача: на основе радиационного баланса(облачность) и влажности определить характер ночи и утра.Спрогнозируй тип конденсации: при отрицательных температурах — гололедица или иней; при положительных — туман или роса.Оцени, как барический тренд(падение или рост давления) и ночное остывание изменят погоду и скажутся на качестве сна и самочувствии к утра.ПРАВИЛА:Экспертный вердикт понятный простому человеку.3-4 ёмких предложения.")
    else:
        tag, label = "🌤️", "#прогноздень"
        preamble = None

    if preamble:
        ai_text = ask_ai_cascade(f"{common_context} Текущее: {cur}", preamble)

    # --- Сборка сводки ---
    warning_block = "\n".join(danger_alerts) if danger_alerts else ""
    if warning_block: warning_block = f"\n{warning_block}\n"

    msg = (f"{tag} {label}\n\n🏙 **Пинск сейчас:**\n"
           f"🌡 **Температура:**\n{temp}°C (ощущ. {cur['apparent_temperature']}°C)\n\n"
           f"🌧 **Осадки:**\n{precip_info}\n\n"
           f"💨 **Ветер:**\n{cur['wind_speed_10m']} км/ч (порывы {gusts}) {get_wind_dir(cur['wind_direction_10m'])}\n\n"
           f"💧 **Влажность:**\n{cur['relative_humidity_2m']}% {get_humidity_desc(cur['relative_humidity_2m'], temp)}\n\n"
           f"📈 **Давление:**\n{press_now} мм {get_pressure_desc(press_now)}\n\n"
           f"☀️ **УФ-индекс:**\n{cur['uv_index']}\n\n"
           f"🕒 **День:**\n{d['sunrise'][3][-5:]} — {d['sunset'][3][-5:]}\n"
           f"{warning_block}"
           f"{'\n📝 **Аналитика:**\n'+{ai_text} if ai_text else ''}")

    requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", json={"chat_id": CH_ID, "text": msg, "parse_mode": "Markdown"})

    # --- СТРАТЕГИЯ (Вс/Ср Вечер) ---
    if hour >= 20 and dow in [2, 6]:
        log("🗓 Сборка стратегии...")
        blocks = []
        for i in range(4, 7):
            date_str = (now + datetime.timedelta(days=i-3)).strftime('%A, %d.%m').replace('Monday','Пн').replace('Tuesday','Вт').replace('Wednesday','Ср').replace('Thursday','Чт').replace('Friday','Пт').replace('Saturday','Сб').replace('Sunday','Вс')
            t_max, t_min = d['temperature_2m_max'][i], d['temperature_2m_min'][i]
            p_sum, p_prob = d['precipitation_sum'][i], d['precipitation_probability_max'][i]
            w_max, g_max = d['wind_speed_10m_max'][i], d['wind_gusts_10m_max'][i]
            day_alert = "ЗЕЛЕНЫЙ ✅"
            if g_max >= 54 or t_max >= 30: day_alert = "ОРАНЖЕВЫЙ 🟠"
            blocks.append(f"📅 **{date_str}**\n\n🌡 **Температура:**\n{t_min}..{t_max}°C\n\n🌧 **Осадки:**\n{p_sum} мм ({p_prob}%)\n\n🌬 **Ветер:**\n{w_max} км/ч (порывы {g_max})\n\n⚠️ **Уровень:**\n{day_alert}")

        strat_ai_prompt = ("Ты — руководитель аналитического центра метеорологии.Тебе нужно выявить «синоптический сюжет» на следующие 3 дня. Твоя задача: связать накопленные данные прошлого (влагозапас почвы, температурный фон) с грядущими изменениями.Объясни причину смены погоды.Оцени риски для инфраструктуры и комфорта людей (гололедные явления, тепловой стресс, порывистый ветер). Спрогнозируй нагрузку на сосуды при скачках давления или температурах. Оцени риск гипоксии.Если в данных есть Оранжевый или Красный уровень — добавь в аналитику с объяснения причины его возникновения.ПРАВИЛА: пиши как для серьезного СМИ: профессионально, доступно, без «воды».Исключи слова-паразиты и неопределенность.Стиль:Глубокая аналитика,но понятная обычному человеку. 3-4 ёмких предложения.")

        strat_ai_text = ask_ai_cascade(f"History: {recent_rain}mm. FutureData: {blocks}", strat_ai_prompt)

        strat_msg = "🗓 #прогноз3дня\n🔭 **3 дня**\n\n" + "\n---\n\n".join(blocks)
        strat_msg += f"\n\n🏛 **АНАЛИТИКА:**\n{strat_ai_text}"
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", json={"chat_id": CH_ID, "text": strat_msg, "parse_mode": "Markdown"})
        log("✅ Стратегия отправлена.")

if __name__ == "__main__":
    main()
