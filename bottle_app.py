import glob
import time
import datetime
import RPi.GPIO as GPIO
from datetime import datetime, timedelta, timezone
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
    
    # Take samples over 3 seconds
    samples = []
    num_samples = 12  # One sample every 0.25 seconds for 3 seconds
    
    for _ in range(num_samples):
        time.sleep(0.25)
        state = GPIO.input(pin)
        samples.append(state != GPIO.HIGH)
    
    # Calculate the majority value
    is_on = sum(samples) > len(samples) / 2
    
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
        #press power button
        GPIO.output(17, GPIO.HIGH)
        time.sleep(1)
        #depress power button
        GPIO.output(17, GPIO.LOW)
        #press time up button
        GPIO.output(18, GPIO.HIGH)
        #sleeping for 5 sec's means it will increase to max time.
        time.sleep(5)
        #depress time up button
        GPIO.output(18, GPIO.LOW)
    else:
        #press power button to turn off
        GPIO.output(17, GPIO.HIGH)
        time.sleep(1)
        #depress power button.
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
    while datetime.now(timezone.utc) < target_time:
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
        'current_time': datetime.now(timezone.utc).isoformat()
    }

@app.route('/api/power', method='POST')
def toggle():
    power_status = read_power_status()
    toggle_power(not power_status["is_on"])
    # Get the new status immediately after toggling
    new_status = read_power_status()
    return {
        'success': True,
        'message': 'Power turned ON' if new_status["is_on"] else 'Power turned OFF',
        'power_status': new_status
    }

@app.route('/api/schedule', method='POST')
def set_schedule():
    global scheduled_time, schedule_thread
    
    data = request.json
    if not data or 'datetime' not in data:
        response.status = 400
        return {'error': 'Missing datetime parameter'}
    
    try:
        # Remove the 'Z' suffix and handle timezone
        target_time_str = data['datetime'].replace('Z', '+00:00')
        target_time = datetime.fromisoformat(target_time_str)
        
        # Get current time with timezone
        current_time = datetime.now(timezone.utc)
        
        if target_time <= current_time:
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
        if scheduled_time and scheduled_time > datetime.now(timezone.utc):
            schedule_thread = threading.Thread(target=schedule_power_on, args=(scheduled_time,))
            schedule_thread.start()
            
        app.run(host='0.0.0.0', port=8080)
    except KeyboardInterrupt:
        GPIO.cleanup()
        if schedule_thread and schedule_thread.is_alive():
            scheduled_time = None
            save_schedule(None)
            schedule_thread.join() 