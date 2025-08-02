# Path relative to the justfile's location
TOOLS_PATH := "tools"

# Test of uv
copy:
    @uv run --project "{{TOOLS_PATH}}" python "{{TOOLS_PATH}}"/main.py
