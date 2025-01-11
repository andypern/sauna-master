from bottle import route, run, template, static_file, post, request, response, Bottle, TEMPLATE_PATH
import os
import json
import time
import datetime
import RPi.GPIO as GPIO
import glob
import threading
from datetime import datetime, timedelta
import logging

app = Bottle()

# Constants
SCHEDULE_FILE = "sauna_schedule.json"
INCREASE_TIME_MINUTES = 60  # 60 minutes when increasing time
scheduled_time = None
schedule_thread = None
STATUS_FILE = "sauna_status.json"
MAX_RUNTIME_MINUTES = 60

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Function to save schedule to JSON
def save_schedule(scheduled_time):
    schedule_data = {
        "scheduled_time": scheduled_time.isoformat() if scheduled_time else None
    }
    with open(SCHEDULE_FILE, 'w') as f:
        json.dump(schedule_data, f)

# Function to load schedule from JSON
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

def schedule_power_on(target_time):
    global scheduled_time
    current_time = datetime.now(target_time.tzinfo)
    while current_time < target_time:
        time.sleep(1)
        current_time = datetime.now(target_time.tzinfo)
        # Check if schedule was cancelled
        current_schedule = load_schedule()
        if current_schedule != target_time:
            return
    
    if load_schedule() == target_time:  # Final check before triggering
        new_status = toggle_power(turn_on=True)  # Explicitly turn on
        save_status(power_on=new_status["is_on"])  # Save the new status
        scheduled_time = None
        save_schedule(None)  # Clear the schedule after execution

# Modified increase_time function
def increase_sauna_time():
    GPIO.setup(18, GPIO.OUT)
    GPIO.output(18, GPIO.HIGH)
    time.sleep(5)
    GPIO.output(18, GPIO.LOW)
    
    # Update the last_update time
    save_status(power_on=True)
    return True

# GPIO setup
GPIO.setmode(GPIO.BCM)
GPIO.setup(25, GPIO.IN)

def read_power_status():
    pin = 25
    #GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    
    # Take samples over 3 seconds
    samples = []
    num_samples = 12  # One sample every 0.25 seconds for 3 seconds
    
    for _ in range(num_samples):
        time.sleep(0.25)
        state = GPIO.input(pin)
        samples.append(state != GPIO.HIGH)
    
    # Calculate the majority value
    is_on = sum(samples) > len(samples) / 2
    
    logging.debug(f"Power status read: samples={samples}, is_on={is_on}")
    
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


def toggle_power(turn_on=None):
    GPIO.setup(17, GPIO.OUT)
    
    # Always toggle pin 17
    GPIO.output(17, GPIO.HIGH)
    time.sleep(1)
    GPIO.output(17, GPIO.LOW)
    
    # Only handle pin 18 if explicitly turning power on
    if turn_on:
        GPIO.setup(18, GPIO.OUT)
        GPIO.output(18, GPIO.HIGH)
        time.sleep(5)
        GPIO.output(18, GPIO.LOW)
    
    # Give time for power state to settle
    time.sleep(0.5)
    
    # Read the new power status
    new_status = read_power_status()
    
    return new_status

def save_status(power_on=None):
    try:
        # Load existing status
        try:
            with open(STATUS_FILE, 'r') as f:
                status = json.load(f)
                logging.debug(f"Loaded existing status: {status}")
        except (FileNotFoundError, json.JSONDecodeError):
            status = {"power": "off", "last_update": None}
            logging.debug("No existing status file, creating default status")
        
        # Update status
        if power_on is not None:
            old_power = status["power"]
            status["power"] = "on" if power_on else "off"
            if power_on:  # Only update timestamp when turning on
                status["last_update"] = datetime.now().isoformat()
            logging.debug(f"Updating status: power changed from {old_power} to {status['power']}")
        
        # Save updated status
        with open(STATUS_FILE, 'w') as f:
            json.dump(status, f)
            logging.debug(f"Saved status to file: {status}")
            
    except Exception as e:
        logging.error(f"Error saving status: {e}")
        raise

def load_status():
    try:
        with open(STATUS_FILE, 'r') as f:
            status = json.load(f)
            logging.debug(f"Loaded status from file: {status}")
            return status
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.warning(f"Could not load status file: {e}")
        return {"power": "off", "last_update": None}

def calculate_time_info():
    status = load_status()
    if status["power"] == "off" or not status["last_update"]:
        return 0, 0
    
    last_update = datetime.fromisoformat(status["last_update"])
    running_for = int((datetime.now() - last_update).total_seconds())
    time_remaining = max(0, (MAX_RUNTIME_MINUTES * 60) - running_for)
    
    return running_for, time_remaining

# Web routes
@app.route('/')
def index():
    return template('simple.html')

@app.route('/simple')
def simple():
    return template('simple.html')

@app.route('/old')
def simple():
    return template('index.html')

# API routes
@app.route('/api/status')
def get_status():
    response.content_type = 'application/json'
    logging.debug("Status request received")
    
    power_status = read_power_status()
    running_for, time_remaining = calculate_time_info()
    
    try:
        temperature = read_temp()
    except Exception as e:
        logging.error(f"Error reading temperature: {e}")
        temperature = 75.0
    
    # Load current schedule
    current_schedule = load_schedule()
    scheduled_time_str = current_schedule.isoformat() if current_schedule else None
    
    response_data = {
        'temperature': temperature,
        'power_status': power_status,
        'power_on_duration': running_for,
        'time_remaining': time_remaining,
        'current_time': datetime.now().isoformat(),
        'scheduled_time': scheduled_time_str
    }
    logging.debug(f"Status response: {response_data}")
    return json.dumps(response_data)

@app.route('/api/power', method='POST')
def power_control():
    response.content_type = 'application/json'
    try:
        data = request.json
        logging.debug(f"Power control request: {data}")
        
        if data and 'power' in data:
            current_status = read_power_status()
            desired_state = data['power']
            
            # Add detailed debug logging
            logging.debug(f"Desired state type: {type(desired_state)}, value: {desired_state}")
            logging.debug(f"Current state type: {type(current_status['is_on'])}, value: {current_status['is_on']}")
            
            # Ensure both values are boolean
            desired_state = bool(desired_state)
            current_is_on = bool(current_status["is_on"])
            
            # Check if desired state matches current state
            if desired_state == current_is_on:
                logging.debug("States match - no action needed")
                save_status(power_on=current_is_on)  # Added: Update status even if no change
                return json.dumps({
                    'success': True,
                    'message': f'Power already {"on" if desired_state else "off"}'
                })
            
            logging.debug(f"States don't match - toggling power to {desired_state}")
            new_status = toggle_power(turn_on=desired_state)
            logging.debug(f"New power status after toggle: {new_status}")
            
            # Save the new status with the actual read state, not the desired state
            save_status(power_on=new_status["is_on"])
            
            response_data = {
                'success': True,
                'message': f'Power turned {"on" if new_status["is_on"] else "off"} successfully'
            }
            
            logging.debug(f"Power control response: {response_data}")
            return json.dumps(response_data)
            
    except Exception as e:
        error_msg = f"Error in power control: {str(e)}"
        logging.error(error_msg)
        response.status = 500
        return json.dumps({'error': error_msg})

@app.route('/api/increase-time', method='POST')
def increase_time():
    response.content_type = 'application/json'
    if increase_sauna_time():
        return json.dumps({
            'success': True,
            'message': f'Time increased to {INCREASE_TIME_MINUTES} minutes'
        })
    else:
        response.status = 400
        return json.dumps({'error': 'Cannot increase time while sauna is off'})

@app.route('/api/schedule', method='POST')
def set_schedule():
    global scheduled_time, schedule_thread
    response.content_type = 'application/json'
    
    try:
        data = request.json
        if data and 'datetime' in data:
            # Convert to UTC and make timezone-aware
            scheduled_datetime = datetime.fromisoformat(data['datetime'].replace('Z', '+00:00'))
            current_time = datetime.now(scheduled_datetime.tzinfo)
            
            if scheduled_datetime <= current_time:
                response.status = 400
                return json.dumps({'error': 'Please select a future time'})
            
            scheduled_time = scheduled_datetime
            save_schedule(scheduled_datetime)
            
            # Start new schedule thread
            if schedule_thread and schedule_thread.is_alive():
                scheduled_time = None
                save_schedule(None)
                schedule_thread.join()
            
            schedule_thread = threading.Thread(target=schedule_power_on, args=(scheduled_datetime,))
            schedule_thread.start()
            
            return json.dumps({
                'success': True,
                'message': f'Sauna scheduled for {scheduled_datetime.isoformat()}'
            })
    except Exception as e:
        response.status = 500
        return json.dumps({'error': str(e)})

@app.route('/api/schedule', method='DELETE')
def cancel_schedule():
    global scheduled_time, schedule_thread
    response.content_type = 'application/json'
    
    try:
        scheduled_time = None
        save_schedule(None)
        return json.dumps({
            'success': True,
            'message': 'Schedule cancelled successfully'
        })
    except Exception as e:
        response.status = 500
        return json.dumps({'error': str(e)})

# Template path setup
TEMPLATE_PATH.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "views")))

if __name__ == '__main__':
    try:
        # Load any existing schedule on startup
        scheduled_time = load_schedule()
        if scheduled_time and scheduled_time > datetime.now(datetime.now().tzinfo):
            schedule_thread = threading.Thread(target=schedule_power_on, args=(scheduled_time,))
            schedule_thread.start()
        
        run(app, host='0.0.0.0', port=8080, debug=True)
    finally:
        GPIO.cleanup()
        if schedule_thread and schedule_thread.is_alive():
            scheduled_time = None
            save_schedule(None)
            schedule_thread.join()
