# Path relative to the justfile's location
TOOLS_PATH := "tools"


# Executing "just" without arguments is listing all recipes
list-recipes:
    @just --list --unsorted

# RPI: Checking about logger application is already running on Raspberry Pi device
check:
    @uv run --quiet --project "{{TOOLS_PATH}}" python "{{TOOLS_PATH}}"/main.py --rpi-check-logger

# RPI: Killing running logger application on Raspberry Pi device
stop:
    @uv run --quiet --project "{{TOOLS_PATH}}" python "{{TOOLS_PATH}}"/main.py --rpi-kill-logger

# RPI: Starting logger application on Raspberry Pi device (first it will kill already running logger app) 
start:
    @uv run --quiet --project "{{TOOLS_PATH}}" python "{{TOOLS_PATH}}"/main.py --rpi-run-logger

# RPI: Copying logger application to Raspberry Pi device and then starting application
sync:
    @uv run --quiet --project "{{TOOLS_PATH}}" python "{{TOOLS_PATH}}"/main.py --rpi-copy-code

# RPI: Live stream from Raspberry Pi device tmux session
tmux:
    @uv run --quiet --project "{{TOOLS_PATH}}" python "{{TOOLS_PATH}}"/main.py --rpi-tmux

# Check linting with ruff
ruff:
    @uv run --quiet ruff check
