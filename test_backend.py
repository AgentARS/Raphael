import subprocess
import time
import urllib.request
import os

os.chdir("backend")
p = subprocess.Popen(["uvicorn", "main:app", "--port", "8002"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(2)
try:
    urllib.request.urlopen("http://127.0.0.1:8002/api/tasks", timeout=2)
    print("Request succeeded")
except Exception as e:
    print("Request failed:", e)

time.sleep(1)
p.terminate()
outs, errs = p.communicate()
print("STDOUT:")
print(outs.decode())
print("STDERR:")
print(errs.decode())
