import os
import requests
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time
import json

# --- НАСТРОЙКИ ---
# ID вашей таблицы Google Sheets
SPREADSHEET_ID = "18G-knN3JXYjMQCL02qrl8nyJ3QOzT7jX94gvODMxw-4" 
# Название листа, куда будет писаться история
WORKSHEET_NAME = "RUB_TJS_daily"
# -----------------

def get_rub_rates_for_date(target_date_str: str) -> tuple[Dict[str, float], str]:
    """
    Парсит курсы безналичной продажи RUB/TJS для заданной даты.
    Возвращает:
      - словарь {название_банка: курс}
      - строку даты/времени, полученную с сайта (или пустую строку)
    Если данные за указанную дату отсутствуют – возвращает ({}, "").
    """
    url = "https://nbt.tj/ru/kurs/kurs_kommer_bank.php"
    params = {"currency": "RUB", "date": target_date_str}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        resp.encoding = "utf-8"
    except requests.RequestException as e:
        print(f"❌ Ошибка запроса для {target_date_str}: {e}")
        return {}, ""

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if not table:
        print(f"⚠️ Таблица не найдена для {target_date_str}")
        return {}, ""

    header_row = table.find("tr")
    if not header_row:
        return {}, ""
    headers = [th.get_text(strip=True) for th in header_row.find_all("th")]

    try:
        col_bank = headers.index("Кредитные финансовые организации")
        col_sell_noncash = headers.index("Безналичные продажа")
        col_date = headers.index("Дата")
    except ValueError as e:
        print(f"❌ Ошибка заголовков: {e}")
        return {}, ""

    result = {}
    datetime_value = ""
    rows = table.find_all("tr")[1:]
    target_date_obj = datetime.strptime(target_date_str, '%Y-%m-%d').date()

    for row in rows:
        cells = row.find_all("td")
        if len(cells) <= max(col_bank, col_sell_noncash, col_date):
            continue

        raw_datetime = cells[col_date].get_text(strip=True)
        try:
            actual_date_obj = datetime.strptime(raw_datetime.split()[0], '%d.%m.%Y').date()
        except (ValueError, IndexError):
            continue

        # Проверка: совпадает ли дата на сайте с запрашиваемой
        if actual_date_obj != target_date_obj:
            print(f"⚠️ Данные за {target_date_str} отсутствуют. Сайт вернул {actual_date_obj}")
            return {}, ""  # данные не за ту дату

        bank = cells[col_bank].get_text(strip=True)
        sell_raw = cells[col_sell_noncash].get_text(strip=True)
        try:
            sell = float(sell_raw) if sell_raw and sell_raw != "0.0000" else None
        except ValueError:
            sell = None

        if sell is not None:
            result[bank] = sell
            if not datetime_value:
                datetime_value = raw_datetime

    return result, datetime_value

def save_to_gsheet(bank_rates):
    """Сохраняет данные в Google Sheets."""
    if not bank_rates:
        print("Нет данных для сохранения")
        return

    # --- АВТОРИЗАЦИЯ ЧЕРЕЗ СЕРВИСНЫЙ АККАУНТ (БЕЗ УЧАСТИЯ ЧЕЛОВЕКА) ---
    # Данные для входа хранятся в секретах GitHub (настроим позже)
    creds_json = os.environ.get("GOOGLE_CREDS")
    if not creds_json:
        print("Ошибка: Не найдены учетные данные Google")
        return
        
    creds_dict = json.loads(creds_json)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    # ------------------------------------------------------------

    sh = client.open_by_key(SPREADSHEET_ID)
    try:
        ws = sh.worksheet(WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=WORKSHEET_NAME, rows=1000, cols=4)
        ws.append_row(["datetime_request", "date_rate", "bank", "sell_rate"])

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date_rate_str = datetime.now().strftime("%Y-%m-%d")
    rows_to_add = []

    for bank, rate in bank_rates.items():
        rows_to_add.append([now_str, date_rate_str, bank, rate])
    
    if rows_to_add:
        ws.append_rows(rows_to_add, value_input_option="USER_ENTERED")
        print(f"Сохранено {len(rows_to_add)} записей")

if __name__ == "__main__":
    print(f"Запуск в {datetime.now()}")
    rates = get_rub_rates()
    save_to_gsheet(rates)
