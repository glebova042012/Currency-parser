import os
import requests
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import time
from typing import Dict, Tuple, List

# --- НАСТРОЙКИ ---
# ID вашей таблицы Google Sheets
SPREADSHEET_ID = "18G-knN3JXYjMQCL02qrl8nyJ3QOzT7jX94gvODMxw-4" 
# Название листа, куда будет писаться история
WORKSHEET_NAME = "RUB_TJS_daily"
# -----------------

def get_rub_rates() -> Dict[str, float]:
    """
    Парсит курсы безналичной продажи RUB/TJS на ТЕКУЩУЮ дату.
    Возвращает словарь {название_банка: курс}.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    url = "https://nbt.tj/ru/kurs/kurs_kommer_bank.php"
    params = {"currency": "RUB", "date": today}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        resp.encoding = "utf-8"
    except requests.RequestException as e:
        print(f"❌ Ошибка запроса для {today}: {e}")
        return {}

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if not table:
        print(f"❌ Таблица не найдена для {today}")
        return {}

    header_row = table.find("tr")
    if not header_row:
        return {}

    headers_list = [th.get_text(strip=True) for th in header_row.find_all("th")]

    try:
        col_bank = headers_list.index("Кредитные финансовые организации")
        col_sell_noncash = headers_list.index("Безналичные продажа")
        col_date = headers_list.index("Дата")
    except ValueError as e:
        print(f"❌ Ошибка заголовков: {e}")
        return {}

    result = {}
    rows = table.find_all("tr")[1:]
    target_date_obj = datetime.strptime(today, '%Y-%m-%d').date()

    for row in rows:
        cells = row.find_all("td")
        if len(cells) <= max(col_bank, col_sell_noncash, col_date):
            continue

        raw_datetime = cells[col_date].get_text(strip=True)
        try:
            actual_date_obj = datetime.strptime(raw_datetime.split()[0], '%d.%m.%Y').date()
        except (ValueError, IndexError):
            continue

        # Проверка: дата на сайте должна совпадать с запрашиваемой
        if actual_date_obj != target_date_obj:
            print(f"⚠️ Данные за {today} не найдены. Сайт вернул {actual_date_obj}")
            return {}

        bank = cells[col_bank].get_text(strip=True)
        sell_raw = cells[col_sell_noncash].get_text(strip=True)
        try:
            sell = float(sell_raw) if sell_raw and sell_raw != "0.0000" else None
        except ValueError:
            sell = None

        if sell is not None:
            result[bank] = sell

    return result

def save_to_gsheet(bank_rates: Dict[str, float]) -> None:
    """Сохраняет курсы в Google Sheets (длинный формат: дата_запроса, дата_курса, банк, курс)."""
    if not bank_rates:
        print("❌ Нет данных для сохранения")
        return

    # Читаем секрет с ключами сервисного аккаунта
    creds_json = os.environ.get("GOOGLE_CREDS")
    if not creds_json:
        print("❌ Ошибка: переменная окружения GOOGLE_CREDS не найдена")
        return

    try:
        creds_dict = json.loads(creds_json)
    except json.JSONDecodeError:
        print("❌ Ошибка: GOOGLE_CREDS содержит невалидный JSON")
        return

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    # Открываем таблицу
    try:
        sh = client.open_by_key(SPREADSHEET_ID)
    except gspread.exceptions.APIError as e:
        print(f"❌ Ошибка доступа к таблице: {e}")
        print("   Убедитесь, что email сервисного аккаунта добавлен в редакторы таблицы.")
        return

    # Получаем или создаём лист
    try:
        ws = sh.worksheet(WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=WORKSHEET_NAME, rows=1000, cols=4)
        ws.append_row(["datetime_request", "date_rate", "bank", "sell_rate"])
        print(f"📄 Создан новый лист '{WORKSHEET_NAME}'")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date_rate_str = datetime.now().strftime("%Y-%m-%d")
    rows_to_add = [[now_str, date_rate_str, bank, rate] for bank, rate in bank_rates.items()]

    if rows_to_add:
        ws.append_rows(rows_to_add, value_input_option="USER_ENTERED")
        print(f"✅ Сохранено {len(rows_to_add)} записей")
    else:
        print("❌ Нет записей для сохранения")

if __name__ == "__main__":
    print(f"🚀 Запуск в {datetime.now()}")
    rates = get_rub_rates()
    print(f"📊 Получено банков: {len(rates)}")
    if rates:
        print(f"📈 Пример: {list(rates.items())[:2]}")
    save_to_gsheet(rates)
    print("✅ Скрипт выполнен")
