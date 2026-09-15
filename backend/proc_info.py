import psutil

try:
    p = psutil.Process(71547)
    print(p.cmdline())
except Exception as e:
    print(e)
    
try:
    p = psutil.Process(71550)
    print(p.cmdline())
except Exception as e:
    print(e)
