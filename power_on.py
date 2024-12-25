import RPi.GPIO as GPIO
import time

pin = 17
# Use Broadcom pin numbering
GPIO.setmode(GPIO.BCM)

# Set up GPIO pin 17 as an output
GPIO.setup(pin, GPIO.OUT)

# Set GPIO pin 17 to HIGH
GPIO.output(pin, GPIO.HIGH)
print(f"GPIO {pin} is HIGH")

# Keep the pin HIGH for 1 second
time.sleep(1)

# Set GPIO pin 17 to LOW
GPIO.output(pin, GPIO.LOW)
print(f"GPIO {pin} is LOW")

# Clean up GPIO on exit
GPIO.cleanup()