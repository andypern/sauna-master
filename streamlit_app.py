import streamlit as st
import glob
import time
import datetime
import RPi.GPIO as GPIO
from datetime import datetime, timedelta
import threading
import json
import os

# Constants
SCHEDULE_FILE = "sauna_schedule.json"

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

# Initialize GPIO
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
        GPIO.output(17, GPIO.LOW)  # Only turn off pin 17
        # Pin 18 is not manipulated when turning off

# Global variables
scheduled_time = None
schedule_thread = None

# Modified schedule_power_on function to handle file persistence
def schedule_power_on(target_time):
    global scheduled_time
    while datetime.now(datetime.now().tzinfo) < target_time:
        time.sleep(1)
        # Check if schedule was cancelled by checking the file
        current_schedule = load_schedule()
        if current_schedule != target_time:
            return
    
    if load_schedule() == target_time:  # Final check before triggering
        toggle_power()
        scheduled_time = None
        save_schedule(None)  # Clear the schedule after execution

# Streamlit UI
def main():
    st.title("Sauna Monitor")
    global scheduled_time, schedule_thread
    
    # Load saved schedule on startup
    if scheduled_time is None:
        scheduled_time = load_schedule()
        if scheduled_time and scheduled_time > datetime.now(datetime.now().tzinfo):
            schedule_thread = threading.Thread(target=schedule_power_on, args=(scheduled_time,))
            schedule_thread.start()
    
    # Initialize GPIO on startup
    setup_gpio()
    
    try:
        # Create columns for layout
        col1, col2 = st.columns(2)
        
        with col1:
            temperature = read_temp()
            st.metric("Temperature", f"{temperature:.1f}°F")
        
        with col2:
            power_status = read_power_status()
            st.metric("Power Status", power_status["text"])
        
        # Power control button
        if st.button("Turn On Power" if not power_status["is_on"] else "Turn Off Power"):
            if not power_status["is_on"]:
                toggle_power(turn_on=True)  # Turn on the power
                st.success("Power turned on!")
            else:
                toggle_power(turn_on=False)  # Turn off the power
                st.success("Power turned off!")
            st.rerun()

        # Add scheduler section
        st.subheader("Schedule Sauna")
        
        # Date and time picker
        col3, col4 = st.columns(2)
        with col3:
            date = st.date_input("Select Date", min_value=datetime.now().date())
        with col4:
            # Allow typing in the time picker
            time_str = st.time_input("Select Time", datetime.now().time(), format="HH:mm")

        # Combine date and time
        scheduled_datetime = datetime.combine(date, time_str)

        # Show current schedule if exists
        if scheduled_time:
            st.info(f"Sauna scheduled to turn on at: {scheduled_time.strftime('%Y-%m-%d %H:%M:%S')}")
            if st.button("Cancel Schedule"):
                scheduled_time = None
                save_schedule(None)  # Clear the saved schedule
                st.success("Schedule cancelled!")
                st.rerun()
        
        # Schedule button
        elif st.button("Schedule Power On"):
            if scheduled_datetime <= datetime.now(datetime.now().tzinfo):
                st.error("Please select a future time!")
            else:
                scheduled_time = scheduled_datetime
                save_schedule(scheduled_datetime)  # Save the schedule
                schedule_thread = threading.Thread(target=schedule_power_on, args=(scheduled_datetime,))
                schedule_thread.start()
                st.success(f"Sauna scheduled to turn on at {scheduled_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
                st.rerun()
        
        # Display current time
        st.text(f"Last updated: {datetime.now(datetime.now().tzinfo).strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Add a refresh button
        if st.button("Refresh Status"):
            st.experimental_rerun()  # Refresh the page to update power status and temperature
        
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
    finally:
        # Note: We don't cleanup GPIO here as it would run on every refresh
        pass

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        GPIO.cleanup()
        if schedule_thread and schedule_thread.is_alive():
            scheduled_time = None
            save_schedule(None)  # Clear the schedule on shutdown
            schedule_thread.join()