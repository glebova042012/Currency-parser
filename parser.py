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

def get_rub_rates():
    """Парсит курсы продажи RUB/TJS на СЕГОДНЯ."""
    today = datetime.now().strftime("%Y-%m-%d")
    url = "https://nbt.tj/ru/kurs/kurs_kommer_bank.php"
    params = {"currency": "RUB", "date": today}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        response.encoding = "utf-8"
    except Exception as e:
        print(f"Ошибка запроса: {e}")
        return {}

    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table")
    if not table:
        return {}
    # ... (Здесь вставьте ВЕСЬ ваш код ПАРСИНГА из ячейки 3, 
    # который возвращает словарь {bank: rate}) ...
    # Упрощенный пример возврата:
    return {"Банк А": 0.1234, "Банк Б": 0.5678}


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
