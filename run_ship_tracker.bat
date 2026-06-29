@echo off
REM Ship Tracker - Windows Task Scheduler Batch File

cd /d C:\Users\user\Downloads
python ship_tracker.py

REM Optional: Log the run
echo [%date% %time%] Ship tracker ran >> ship_tracker.log
