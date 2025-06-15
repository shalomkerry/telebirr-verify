import re
import json
import time
import requests
from bs4 import BeautifulSoup

USED_RECEIPTS_FILE = "used_receipts.json"
RECEIPT_EXPIRY_SECONDS = 172800  # 48 hours

def _load_used():
    try:
        with open(USED_RECEIPTS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def _save_used(data):
    with open(USED_RECEIPTS_FILE, "w") as f:
        json.dump(data, f)

def _mark_used(rid):
    used = _load_used()
    used[rid] = time.time()
    _save_used(used)

def _is_used(rid):
    used = _load_used()
    return rid in used and time.time() - used[rid] < RECEIPT_EXPIRY_SECONDS

def _normalize_name(name):
    return re.sub(r'\s+', '', name).lower()

def _extract_id(message):
    clean = " ".join(message.strip().split())
    match = re.search(r'receipt/([A-Z0-9]+)', clean)
    if match:
        return match.group(1)
    match = re.search(r'transaction number is ([A-Z0-9]+)', clean, re.IGNORECASE)
    if match:
        return match.group(1)
    return None

def _fetch_html(rid):
    url = f"https://transactioninfo.ethiotelecom.et/receipt/{rid}"
    res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
    res.raise_for_status()
    return res.text

def _parse(html):
    soup = BeautifulSoup(html, "html.parser")
    data = {}

    # Extract labeled fields
    for row in soup.find_all("tr"):
        tds = row.find_all("td")
        if len(tds) == 2:
            label = tds[0].get_text(strip=True)
            value = tds[1].get_text(strip=True)

            if "ከፋይ ስም" in label:
                data['payer_name'] = value
            elif "ቴሌብር ቁ" in label:
                data['payer_number'] = value
            elif "ተቀባይ ስም" in label:
                data['receiver_name'] = value
            elif "አካውንት ቁጥር" in label:
                data['receiver_account'] = value
            elif "ዘዴ" in label:
                data['payment_mode'] = value
            elif "ምክንያት" in label:
                data['payment_reason'] = value
            elif "መንገድ" in label:
                data['payment_channel'] = value
            elif "ሁኔታ" in label:
                data['status'] = value

    # Extract receipt metadata
    try:
        table = soup.find_all('table')[4]
        values = table.find_all('tr')[2].find_all('td')
        data['receipt_number'] = values[0].get_text(strip=True)
        data['payment_date'] = values[1].get_text(strip=True)
        data['amount'] = values[2].get_text(strip=True).replace("Birr", "").strip()
    except Exception:
        pass

    return data

def verify_telebirr_transaction(message, expected_amount, expected_receiver, expected_receiver_number=None, return_data=False):
    """
    Verifies a Telebirr transaction receipt.
    Returns: (bool, message) or (bool, message, data) if return_data=True
    """
    data = {}
    errors = []

    rid = _extract_id(message)
    if not rid or not re.match(r'^[A-Z0-9]{8,20}$', rid):
        msg = "Invalid or missing transaction ID"
        return (False, msg, data) if return_data else (False, msg)

    if _is_used(rid):
        msg = "This receipt has already been verified"
        return (False, msg, data) if return_data else (False, msg)

    try:
        html = _fetch_html(rid)
        data = _parse(html)
    except requests.exceptions.Timeout:
        msg = "Network timeout while connecting to receipt page"
        return (False, msg, data) if return_data else (False, msg)
    except Exception:
        msg = "Unable to fetch or parse receipt"
        return (False, msg, data) if return_data else (False, msg)

    try:
        amt = float(data.get("amount", "0").replace(",", ""))
    except:
        msg = "Invalid amount format"
        return (False, msg, data) if return_data else (False, msg)

    if data.get("status", "").lower() != "completed":
        errors.append("Transaction not completed")

    if expected_amount>amt :
        errors.append(f"Amount mismatch. Expected {expected_amount}, got {amt}")

    actual_receiver = data.get("receiver_name", "")
    if _normalize_name(expected_receiver) not in _normalize_name(actual_receiver):
        errors.append("Receiver name mismatch")

    if expected_receiver_number:
        acct = data.get("receiver_account", "")
        if expected_receiver_number not in acct:
            errors.append("Receiver account number mismatch")

    if errors:
        return (False, "; ".join(errors), data) if return_data else (False, "; ".join(errors))

    _mark_used(rid)
    return (True, "Receipt verified successfully", data) if return_data else (True, "Receipt verified successfully")