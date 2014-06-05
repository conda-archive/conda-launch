@echo off
set PYTHONPATH=%~dp0\..;%PYTHONPATH%
python -m ipyapp.client %*