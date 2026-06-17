
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Testing imports...")
try:
    from app.main import app
    print("✅ Successfully imported app.main!")
except Exception as e:
    print(f"❌ Error importing: {e}")
    import traceback
    traceback.print_exc()
