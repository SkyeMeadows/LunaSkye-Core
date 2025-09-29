import schedule
import time
import subprocess

def run_AT_manager():
    subprocess.run(["/home/skye/programs/.venv/bin/python", "/home/skye/programs/Manager-AT.py"])

def run_data_gatherer():
    subprocess.run(["/home/skye/programs/.venv/bin/python", "/home/skye/programs/MarketData.py"])

# Schedule jobs
schedule.every().hour.at(":01").do(run_AT_manager)
schedule.every().hour.at(":05").do(run_data_gatherer)

while True:
    schedule.run_pending()
    time.sleep(1)
