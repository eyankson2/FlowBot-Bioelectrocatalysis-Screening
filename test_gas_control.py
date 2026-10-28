"""Commissioning test. First run with 12 V and gas supply OFF."""
import time
from gas_control import GasControl

PORT = 'COM4'
with GasControl(PORT) as gas:
    print('Startup:', gas.status())
    input('Confirm solenoid 12 V supply and gas supply are OFF. Press Enter...')
    print('OFF:', gas.off())
    print('10-second command test:', gas.start_purge(10))
    for i in range(10):
        time.sleep(1)
        print(f'{i+1}s:', gas.status())
    print('Final OFF:', gas.off())
print('Disconnected. The Arduino has an independent purge timeout.')
