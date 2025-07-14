
import time  as tz
from datetime import  time, datetime
tz.sleep(1)

cuz_now = datetime.now().time()
s = time(7, 30)    
e = time(9,13)


if s <= cuz_now <= e:
    print("ok")
else:
    print("not ok")

print(cuz_now)
print(s)
print(e)