import schedule
import time
import subprocess

def run_AT_manager():
    subprocess.run(["/venv/bin/python", "./Manager-AT.py"])

def run_data_gatherer():
    subprocess.run(["/venv/bin/python", "./MarketData.py"])

# Schedule jobs
schedule.every().hour.at(":01").do(run_AT_manager)
schedule.every().hour.at(":05").do(run_data_gatherer)

while True:
    schedule.run_pending()
    time.sleep(1)
