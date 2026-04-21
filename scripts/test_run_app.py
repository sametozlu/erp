import subprocess
import time
import sys
import requests
import os

def test_app():
    print("Uygulama baslatiliyor...")
    env = os.environ.copy()
    env["FLASK_ENV"] = "development"
    env["DEBUG"] = "1"
    
    # Windows'ta 'py' veya 'python'
    cmd = ["py", "app.py"]
    
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    
    print("Waiting 15 seconds for startup...")
    time.sleep(15)
    
    # Process hala çalışıyor mu?
    ret = process.poll()
    if ret is None:
        print("SUCCESS: Uygulama calisiyor (PID: {}).".format(process.pid))
        # Test request
        try:
            print("Sending health check request...")
            r = requests.get("http://127.0.0.1:5000", timeout=5)
            print(f"Health Check Response: {r.status_code}")
        except Exception as e:
            print(f"Health Check Fail: {e}")
            
        print("Shutting down...")
        process.terminate()
        try:
            outs, errs = process.communicate(timeout=5)
            if outs:
                print("--- OUTPUT (Last 10 lines) ---")
                print('\n'.join(outs.splitlines()[-10:]))
            if errs:
                print("--- ERRORS ---")
                print(errs)
        except Exception:
            process.kill()
            print("Process killed.")
    else:
        print(f"FAILURE: Uygulama coktu (Exit Code: {ret})")
        outs, errs = process.communicate()
        print("--- STDOUT ---")
        print(outs)
        print("--- STDERR ---")
        print(errs)

if __name__ == "__main__":
    test_app()
