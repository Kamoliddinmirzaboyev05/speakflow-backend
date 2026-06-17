
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import uvicorn
    print("Starting backend server...")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
