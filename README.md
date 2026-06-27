# Alpha Mobile – AI Voice Assistant with Home Assistant Integration

Alpha Mobile is a Flask-based personal assistant that understands natural language commands, controls smart devices via Home Assistant, fetches weather, maintains a local bank account ledger, and even forwards responses to Discord. It leverages **DeepSeek** (via Selenium) as its AI backend for general queries.

---

## Features

- **Voice‑like Interaction** – Trigger commands with wake words (`hey alpha`, `alpha`, etc.).
- **Home Assistant Control** – Turn on/off lights, switches, climate, and read sensors.
- **Weather Reports** – Get current weather and forecast from your Home Assistant weather entity.
- **Local Bank Ledger** – Track income/expenses with persistent storage (JSON).  
  - Add or deduct amounts using phrases like *"deduct RM50 from bank account"* or *"deposit RM200"*.
- **Discord Forwarding** – Send any response to a Discord channel (optional).
- **DeepSeek AI Fallback** – For open‑ended questions, the assistant queries DeepSeek via a browser automation.
- **Device Management** – Add new devices on the fly via chat (e.g., `device kitchen fan, switch.kitchen_fan, switch`).
- **System Stats** – Endpoint to get CPU/RAM usage.
- **Open YouTube** – Opens YouTube in your default browser.

---

## Requirements

- Python 3.8+ (I use python 3.12)
- Chrome browser (for Selenium)
- Home Assistant instance with a Long‑Lived Access Token
- Discord Bot Token and Channel ID (if you want Discord forwarding)
- Internet connection (for DeepSeek)

---

## Installation

1. **Download The File**
   install the alpah.py and the index.html put the create a folder name templates and place the index.html into the folder that u created.

2. **Install dependencies**

bash
pip install flask requests selenium webdriver-manager psutil

3. **Set environment variables (or create a .env file)**
   
bash
export HA_TOKEN="your_home_assistant_long_lived_token"
export DISCORD_BOT_TOKEN="your_discord_bot_token"
export DISCORD_CHANNEL_ID="your_discord_channel_id"
# Optionally:
export HA_URL="http://your-ha-ip:8123"   # default is http://homeassistant.local:8123

4. **Run the app**

bash
python app.py
The server will start on http://0.0.0.0:5000.

5. **First‑time DeepSeek login**
   
When you send a query that reaches DeepSeek, a Chrome window will open.
Log in to your DeepSeek account manually in that window – the session will persist.

How to Use
Web Interface
Open http://localhost:5000 in your browser.

You’ll see a simple chat interface.

Type your commands in natural language.

Command Examples
Command	Action
hey alpha what's the weather?	Returns weather from Home Assistant.
turn on living room light	Controls a registered light.
deduct RM25 from bank account	Subtracts 25 from your balance.
deposit RM100	Adds 100 to your balance.
send it to discord (after any command)	Also forwards the response to Discord.
add new device	Shows the syntax for adding a device.
device fan, switch.fan, switch	Registers a new device called fan.
repeat hello	Repeats “hello”.
open youtube	Opens YouTube in your browser.
what is the capital of France?	Passes to DeepSeek AI.
Device Types
light, switch, climate, sensor – use the exact domain names from Home Assistant.

**API Endpoints**
GET / – Web UI.

POST /ask – Main endpoint for commands.
Request body: {"message": "your command"}
Returns JSON with response and optionally bank data.

GET /system_stats – Returns CPU and RAM usage.

GET /get_bank_data – Returns current balance and transaction history.

POST /reset_balance – Resets balance to a given amount. Body: {"amount": 100}.

**File Storage**
devices.json – Stores your registered devices.

bank_data.json – Stores your balance and transaction history.

These are created automatically.

**Troubleshooting**
DeepSeek not responding – Ensure Chrome is installed and you logged in when the browser opened.

Home Assistant connection fails – Verify HA_URL and HA_TOKEN.

Discord send fails – Check bot token and channel ID; ensure bot has permission to send messages in that channel.

Selenium driver issues – The webdriver-manager should handle ChromeDriver automatically. Make sure Chrome is up‑to‑date.


