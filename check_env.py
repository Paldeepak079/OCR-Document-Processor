import sys
import subprocess

def check_import(module_name):
    try:
        __import__(module_name)
        print(f"[OK] {module_name} imported successfully.")
        return True
    except ImportError as e:
        print(f"[ERROR] Failed to import {module_name}: {e}")
        return False
    except OSError as e:
        print(f"[CRITICAL] OS Error importing {module_name}: {e}")
        print("This is likely due to missing system libraries (like Visual C++ Redistributable) or incompatible DLLs.")
        return False

def main():
    print("Checking environment...")
    print(f"Python version: {sys.version}")
    
    # Check critical libraries
    if not check_import("torch"):
        print("\nSUGGESTION: Please ensure you have the 'Visual C++ Redistributable' installed.")
        print("Download: https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist")
        sys.exit(1)
        
    if not check_import("transformers"):
        sys.exit(1)
        
    print("\nEnvironment check passed!")

if __name__ == "__main__":
    main()
