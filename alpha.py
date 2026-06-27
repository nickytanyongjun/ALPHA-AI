from flask import Flask, render_template, request, jsonify
import requests
import datetime
import webbrowser
import json
import os
import time
import re
import psutil
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

app = Flask(__name__)

# =========================================================
# CONFIG (all secrets come from environment variables)
# =========================================================

HOME_ASSISTANT_URL = os.environ.get("HA_URL", "http://homeassistant.local:8123")
HA_TOKEN = os.environ.get("HA_TOKEN")          # MUST be set
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")      # MUST be set
DISCORD_CHANNEL_ID = os.environ.get("DISCORD_CHANNEL_ID")    # MUST be set

if not HA_TOKEN:
    raise RuntimeError("HA_TOKEN environment variable not set")
if not DISCORD_BOT_TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN environment variable not set")
if not DISCORD_CHANNEL_ID:
    raise RuntimeError("DISCORD_CHANNEL_ID environment variable not set")

WAKE_WORDS = [
    "hey alpha",
    "alpha",
    "alfa",
    "elsa",
    "alf"
]

DEVICE_FILE = "devices.json"
BANK_DATA_FILE = "bank_data.json"

# =========================================================
# PERSISTENT FINANCIAL STORAGE LOGIC
# =========================================================

def load_bank_data():
    if not os.path.exists(BANK_DATA_FILE):
        initial_structure = {"balance": 0.00, "history": []}
        with open(BANK_DATA_FILE, "w") as f:
            json.dump(initial_structure, f)
        return initial_structure
    try:
        with open(BANK_DATA_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"balance": 0.00, "history": []}

def save_bank_data(data):
    try:
        with open(BANK_DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print("Error saving bank datasets:", e)

# =========================================================
# DEVICE DATABASE
# =========================================================

def load_devices():
    if not os.path.exists(DEVICE_FILE):
        with open(DEVICE_FILE, "w") as f:
            json.dump({}, f)
    with open(DEVICE_FILE, "r") as f:
        return json.load(f)

def save_devices(devices):
    with open(DEVICE_FILE, "w") as f:
        json.dump(devices, f, indent=4)

devices = load_devices()

def add_device(name, entity_id, device_type):
    devices[name] = {
        "entity_id": entity_id,
        "type": device_type
    }
    save_devices(devices)

# =========================================================
# HOME ASSISTANT
# =========================================================

def ha_request(method, endpoint, data=None):
    url = f"{HOME_ASSISTANT_URL}{endpoint}"
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=10)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data, timeout=10)
        else:
            return None
        return response
    except Exception as e:
        print("Home Assistant Error:", e)
        return None

# =========================================================
# WEATHER
# =========================================================

def get_weather():
    entity_id = "weather.forecast_home"
    response = ha_request("GET", f"/api/states/{entity_id}")
    if not response:
        return "Home Assistant connection failed."
    if response.status_code != 200:
        return "Weather fetch failed."

    data = response.json()
    condition = data.get("state", "unknown").replace("_", " ").title()
    attrs = data.get("attributes", {})
    temperature = attrs.get("temperature", "N/A")
    humidity = attrs.get("humidity", "N/A")
    wind_speed = attrs.get("wind_speed", "N/A")
    forecast = attrs.get("forecast", [])

    if forecast:
        high = forecast[0].get("temperature", "N/A")
        low = forecast[0].get("templow", "N/A")
    else:
        high = "N/A"
        low = "N/A"

    return (
        f"The weather is currently {condition}. "
        f"The temperature is {temperature} degrees. "
        f"Today's high is {high} and low is {low}. "
        f"Humidity is {humidity} percent "
        f"with wind speed of {wind_speed} kilometers per hour."
    )

# =========================================================
# SENSOR
# =========================================================

def get_sensor(entity_id):
    response = ha_request("GET", f"/api/states/{entity_id}")
    if not response or response.status_code != 200:
        return None
    data = response.json()
    state = data.get("state")
    unit = data.get("attributes", {}).get("unit_of_measurement", "")
    return f"{state}{unit}"

# =========================================================
# DEVICE CONTROL
# =========================================================

def control_device(entity_id, domain, action):
    endpoint = f"/api/services/{domain}/{action}"
    data = {"entity_id": entity_id}
    response = ha_request("POST", endpoint, data)
    if response and response.status_code == 200:
        print(f"{action}: {entity_id}")
        return True
    return False

# =========================================================
# CLIMATE
# =========================================================

def control_climate(entity_id, mode):
    endpoint = "/api/services/climate/set_hvac_mode"
    data = {"entity_id": entity_id, "hvac_mode": mode}
    response = ha_request("POST", endpoint, data)
    if response and response.status_code == 200:
        return True
    return False

# =========================================================
# DEEPSEEK CORE VIA SELENIUM
# =========================================================

driver = None
deepseek_initialized = False

def init_deepseek_browser():
    global driver, deepseek_initialized
    if deepseek_initialized:
        return
        
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get("https://chat.deepseek.com")
        print("====================================================")
        print("NOTICE: Please complete your DeepSeek login in the open Chrome window.")
        print("====================================================")
        deepseek_initialized = True
    except Exception as e:
        print("Failed to initialize Selenium automated agent workflow:", e)

def ask_deepseek(prompt):
    global driver
    try:
        if not driver:
            init_deepseek_browser()

        textbox = driver.find_element(By.TAG_NAME, "textarea")
        textbox.clear()
        final_prompt = f"(Answer it as short as possible but still understandable)User question: {prompt}"
        textbox.send_keys(final_prompt)
        textbox.send_keys(Keys.ENTER)
        
        time.sleep(5)
        responses = driver.find_elements(By.CSS_SELECTOR, ".ds-markdown")
        if responses:
            return responses[-1].text
        return "No response found."
    except Exception as e:
        return f"DeepSeek Error: {str(e)}"

# =========================================================
# DISCORD HIGH-SPEED API TRANSMITTER (NO OVERHEAD)
# =========================================================

def send_discord_message(message_text):
    """ Sends text directly to your Discord channel via their high-speed REST API. """
    url = f"https://discord.com/api/v10/channels/{DISCORD_CHANNEL_ID}/messages"
    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "content": message_text
    }
    try:
        print("[DISCORD ENGINE] Routing response payload directly via HTTP...")
        res = requests.post(url, headers=headers, json=payload, timeout=5)
        if res.status_code in [200, 201]:
            print("[SUCCESS] Dispatched payload to Discord channel pipeline successfully.")
            return True
        else:
            print(f"[API ERROR] Discord returned unexpected response code: {res.status_code}")
            return False
    except Exception as e:
        print(f"[CRITICAL FAILURE] Unable to reach Discord server architecture: {e}")
        return False

# =========================================================
# ROUTES & INTERCEPTORS
# =========================================================

@app.before_request
def setup_services():
    if request.endpoint and request.endpoint in ['index', 'ask']:
        init_deepseek_browser()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/system_stats', methods=['GET'])
def system_stats():
    cpu = psutil.cpu_percent(interval=0.1)
    ram = psutil.virtual_memory().percent
    return jsonify({
        "cpu": cpu,
        "ram": ram
    })

@app.route('/reset_balance', methods=['POST'])
def reset_balance():
    amount = request.json.get("amount", 0.0)
    bank_data = load_bank_data()
    bank_data["balance"] = float(amount)
    
    now_str = datetime.datetime.now().strftime("%d %b %H:%M")
    bank_data["history"].insert(0, {"date": now_str, "desc": f"Salary Initialized: RM{amount:.2f}"})
    save_bank_data(bank_data)
    return jsonify(bank_data)

@app.route('/get_bank_data', methods=['GET'])
def get_bank_data():
    return jsonify(load_bank_data())

# =========================================================
# ASK ENDPOINT
# =========================================================

@app.route('/ask', methods=['POST'])
def ask():
    global devices

    user_input = request.json.get("message", "").lower().strip()
    query = user_input

    # REMOVE WAKE WORDS
    for word in WAKE_WORDS:
        query = query.replace(word, "").strip()

    response_text = ""
    bank_updated = False
    send_externally = False

    # INTERCEPT EXTERNAL ROUTING REQUEST PHRASES
    if any(kw in query for kw in ["discord", "send it to discord"]):
        send_externally = True
        query = query.replace("and send it to discord", "").replace("send it to discord", "").replace("discord", "").strip()

    # =====================================================
    # SMART BANK ACCOUNT PARSING ENGINE
    # =====================================================
    if "bank account" in query:
        bank_updated = True
        bank_data = load_bank_data()
        
        numbers = re.findall(r"\d+\.?\d*", query)
        if numbers:
            amount_val = float(numbers[0])
            now_str = datetime.datetime.now().strftime("%d %b %H:%M")
            
            if any(kw in query for kw in ["deduct", "minus", "spend", "spent", "pay", "bought"]):
                bank_data["balance"] -= amount_val
                bank_data["history"].insert(0, {"date": now_str, "desc": f"-RM{amount_val:.2f}"})
                save_bank_data(bank_data)
                response_text = f"Acknowledged. Deducted RM{amount_val:.2f} from your bank account context state."
                
            elif any(kw in query for kw in ["add", "plus", "deposit", "received", "receive"]):
                bank_data["balance"] += amount_val
                bank_data["history"].insert(0, {"date": now_str, "desc": f"+RM{amount_val:.2f}"})
                save_bank_data(bank_data)
                response_text = f"Acknowledged. Deposited RM{amount_val:.2f} into your bank account context state."
            else:
                response_text = "I recognized the bank account query, but could not classify your transaction parameter intent (add/deduct)."
        else:
            response_text = "Transaction parameter missing. Please state the target ringgit numerical value clearly."

    # =====================================================
    # REPEAT
    # =====================================================
    elif "repeat" in query:
        parts = query.split("repeat", 1)
        response_text = parts[1].strip() if len(parts) > 1 else "Nothing to repeat."

    # =====================================================
    # TIME
    # =====================================================
    elif "time" in query:
        response_text = f"The time is {datetime.datetime.now().strftime('%H:%M')}"

    # =====================================================
    # OPEN YOUTUBE
    # =====================================================
    elif "open youtube" in query:
        webbrowser.open("https://youtube.com")
        response_text = "Opening YouTube"

    # =====================================================
    # Morning / Forecast
    # =====================================================
    elif any(kw in query for kw in ["morning", "good morning", "forcast", "weather"]):
        response_text = get_weather()

    # =====================================================
    # ADD NEW DEVICE
    # =====================================================
    elif "add new device" in query:
        response_text = (
            "Please send device details like this:\n\n"
            "device NAME, ENTITY_ID, TYPE\n\n"
            "Example:\n"
            "device kitchen fan, switch.kitchen_fan, switch"
        )

    # =====================================================
    # SAVE DEVICE
    # =====================================================
    elif query.startswith("device"):
        try:
            cleaned = query.replace("device", "", 1).strip()
            parts = cleaned.split(",")
            name = parts[0].strip()
            entity_id = parts[1].strip()
            device_type = parts[2].strip()

            if "," in entity_id:
                entity_id = [x.strip() for x in entity_id.split(",")]

            add_device(name, entity_id, device_type)
            devices = load_devices()
            response_text = f"{name} added successfully."
        except Exception as e:
            response_text = "Wrong format. Use: device NAME, ENTITY_ID, TYPE"

    # =====================================================
    # DEVICE CONTROL (FIXED DEVICE ORDER)
    # =====================================================
    elif any(device in query for device in devices):
        found = False
        for device_name, info in devices.items():
            if device_name in query:
                found = True
                entity_id = info["entity_id"]
                device_type = info["type"]

                if device_type == "sensor":
                    value = get_sensor(entity_id)
                    response_text = f"{device_name} is {value}" if value else "Sensor read failed"
                    break

                elif device_type in ["light", "switch"]:
                    if "off" in query:
                        success = control_device(entity_id, device_type, "turn_off")
                        response_text = f"Turning off {device_name}" if success else "Failed to turn off device"
                    elif "on" in query:
                        success = control_device(entity_id, device_type, "turn_on")
                        response_text = f"Turning on {device_name}" if success else "Failed to turn on device"
                    break

                elif device_type == "climate":
                    if "off" in query:
                        success = control_climate(entity_id, "off")
                        response_text = f"Turning off {device_name}" if success else "Failed to turn off climate"
                    elif "on" in query:
                        success = control_climate(entity_id, "cool")
                        response_text = f"Turning on {device_name}" if success else "Failed to turn on climate"
                    break
        if not found:
            response_text = "Device not found."

    # =====================================================
    # DEEPSEEK AI DEFAULT CORE
    # =====================================================
    else:
        response_text = ask_deepseek(query)

    # =====================================================
    # DISCORD OUTBOUND PIPELINE DISPATCH
    # =====================================================
    if send_externally:
        dispatched = send_discord_message(response_text)
        if dispatched:
            response_text += " Then I have sent it to Discord for you to see."
        else:
            response_text += " [Failed to dispatch message packet to your Discord Channel API]"

    ret_data = {"response": response_text}
    if bank_updated:
        ret_data["bank"] = load_bank_data()
    return jsonify(ret_data)

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )