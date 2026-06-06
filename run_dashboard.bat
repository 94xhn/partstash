@echo off
REM Launch the PartStash dashboard from source on Windows.
cd /d "%~dp0"
python -m streamlit run app.py
