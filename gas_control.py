"""Python interface for gas_control.ino. Requires: pip install pyserial"""
import time
import serial

class GasControl:
    def __init__(self, port='COM4', baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.ser = None

    def connect(self):
        self.ser = serial.Serial(self.port, self.baudrate, timeout=0.5)
        time.sleep(2.0)  # UNO resets when serial opens
        self.ser.reset_input_buffer()
        self.off()
        return self

    def command(self, text, expected=None):
        if not self.ser or not self.ser.is_open:
            raise RuntimeError('Not connected')
        self.ser.write(f'<{text}>'.encode('ascii'))
        self.ser.flush()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            line = self.ser.readline().decode('ascii', errors='replace').strip()
            if not line or line == 'DONE:OFF':
                continue
            if line.startswith('ERR:'):
                raise RuntimeError(f'Arduino: {line}')
            if expected is None or line == expected:
                return line
            raise RuntimeError(f'Unexpected Arduino reply: {line}; expected {expected}')
        raise TimeoutError('No Arduino acknowledgement')

    def off(self):
        return self.command('OFF', 'OK:OFF')

    def status(self):
        return self.command('STATUS')

    def start_purge(self, seconds):
        if isinstance(seconds, bool) or not isinstance(seconds, int) or not 1 <= seconds <= 600:
            raise ValueError('Duration must be an integer from 1 to 600 seconds')
        return self.command(f'PURGE:{seconds}', 'OK:ON')

    def purge(self, seconds):
        self.start_purge(seconds)
        try:
            time.sleep(seconds + 0.2)
            return self.status()
        finally:
            self.off()

    def disconnect(self):
        if self.ser and self.ser.is_open:
            try:
                self.off()
            finally:
                self.ser.close()

    def __enter__(self):
        return self.connect()

    def __exit__(self, *_):
        self.disconnect()
