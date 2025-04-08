[main]
log_level = INFO
log_output = /var/log/ser2sock.log
use_ssl = false

[device]
type = serial
device = /dev/ttyAMA0
baudrate = 115200
rtscts = false
