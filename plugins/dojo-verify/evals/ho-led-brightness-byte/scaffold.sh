#!/bin/sh
# Scaffold for ho-led-brightness-byte: writes the task's files into the current directory.
set -e
printf '# desk LED strip\n\nled.py talks to the strip over its USB serial port (/dev/ttyACM0 on the lab\nmachine). The strip is only plugged into that machine, so there are no\nautomated tests here.\n' > README.md && printf '"""Control the desk LED strip over its USB serial port."""\n\nPORT = "/dev/ttyACM0"\nSET_BRIGHTNESS = 0x42\n\n\ndef set_brightness(percent):\n    """Set the strip brightness. percent is 0-100."""\n    if not 0 <= percent <= 100:\n        raise ValueError("percent must be between 0 and 100")\n    with open(PORT, "wb", buffering=0) as port:\n        port.write(bytes([SET_BRIGHTNESS, percent]))\n' > led.py
