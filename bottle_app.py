import glob
import time
import datetime
import RPi.GPIO as GPIO
from datetime import datetime, timedelta
import threading
import json
import os
from bottle import Bottle, response, request, template, static_file

# Constants
SCHEDULE_FILE = "sauna_schedule.json"
app = Bottle()

# Reuse your existing GPIO and temperature functions
def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(25, GPIO.IN)

def read_power_status():
    pin = 25
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    time.sleep(0.5)
    state = GPIO.input(pin)
    is_on = state != GPIO.HIGH
    return {
        "text": "POWER=ON" if is_on else "POWER=OFF",
        "is_on": is_on
    }

def read_temp_raw():
    base_dir = '/sys/bus/w1/devices/'
    device_folder = glob.glob(base_dir + '28*')[0]
    device_file = device_folder + '/w1_slave'
    with open(device_file, 'r') as f:
        lines = f.readlines()
    return lines

def read_temp():
    lines = read_temp_raw()
    while lines[0].strip()[-3:] != 'YES':
        time.sleep(0.2)
        lines = read_temp_raw()
    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos + 2:]
        temp_c = float(temp_string) / 1000.0
        temp_f = temp_c * 9.0 / 5.0 + 32.0
        return temp_f

def toggle_power(turn_on=True):
    GPIO.setup(17, GPIO.OUT)
    GPIO.setup(18, GPIO.OUT)

    if turn_on:
        GPIO.output(17, GPIO.HIGH)
        time.sleep(1)
        GPIO.output(17, GPIO.LOW)
        GPIO.output(18, GPIO.HIGH)
        time.sleep(5)
        GPIO.output(18, GPIO.LOW)
    else:
        GPIO.output(17, GPIO.HIGH)
        time.sleep(1)
        GPIO.output(17, GPIO.LOW)

# Schedule functions
def save_schedule(scheduled_time):
    schedule_data = {
        "scheduled_time": scheduled_time.isoformat() if scheduled_time else None
    }
    with open(SCHEDULE_FILE, 'w') as f:
        json.dump(schedule_data, f)

def load_schedule():
    try:
        if os.path.exists(SCHEDULE_FILE):
            with open(SCHEDULE_FILE, 'r') as f:
                schedule_data = json.load(f)
                if schedule_data["scheduled_time"]:
                    return datetime.fromisoformat(schedule_data["scheduled_time"])
    except Exception as e:
        print(f"Error loading schedule: {e}")
    return None

# Global variables
scheduled_time = None
schedule_thread = None

def schedule_power_on(target_time):
    global scheduled_time
    while datetime.now(datetime.now().tzinfo) < target_time:
        time.sleep(1)
        current_schedule = load_schedule()
        if current_schedule != target_time:
            return
    
    if load_schedule() == target_time:
        toggle_power()
        scheduled_time = None
        save_schedule(None)

# API Routes
@app.route('/')
def home():
    return template('index.html')

@app.route('/api/status')
def get_status():
    temperature = read_temp()
    power_status = read_power_status()
    current_schedule = load_schedule()
    
    return {
        'temperature': round(temperature, 1),
        'power_status': power_status,
        'scheduled_time': current_schedule.isoformat() if current_schedule else None,
        'current_time': datetime.now(datetime.now().tzinfo).isoformat()
    }

@app.route('/api/power', method='POST')
def toggle():
    power_status = read_power_status()
    toggle_power(not power_status["is_on"])
    return {'success': True}

@app.route('/api/schedule', method='POST')
def set_schedule():
    global scheduled_time, schedule_thread
    
    data = request.json
    if not data or 'datetime' not in data:
        response.status = 400
        return {'error': 'Missing datetime parameter'}
    
    try:
        target_time = datetime.fromisoformat(data['datetime'])
        if target_time <= datetime.now(datetime.now().tzinfo):
            response.status = 400
            return {'error': 'Please select a future time'}
        
        scheduled_time = target_time
        save_schedule(target_time)
        schedule_thread = threading.Thread(target=schedule_power_on, args=(target_time,))
        schedule_thread.start()
        
        return {'success': True, 'scheduled_time': target_time.isoformat()}
    except Exception as e:
        response.status = 400
        return {'error': str(e)}

@app.route('/api/schedule', method='DELETE')
def cancel_schedule():
    global scheduled_time
    scheduled_time = None
    save_schedule(None)
    return {'success': True}

@app.route('/static/<filename>')
def serve_static(filename):
    return static_file(filename, root='./static')

if __name__ == '__main__':
    try:
        setup_gpio()
        # Load saved schedule on startup
        scheduled_time = load_schedule()
        if scheduled_time and scheduled_time > datetime.now(datetime.now().tzinfo):
            schedule_thread = threading.Thread(target=schedule_power_on, args=(scheduled_time,))
            schedule_thread.start()
            
        app.run(host='0.0.0.0', port=8080)
    except KeyboardInterrupt:
        GPIO.cleanup()
        if schedule_thread and schedule_thread.is_alive():
            scheduled_time = None
            save_schedule(None)
            schedule_thread.join() 