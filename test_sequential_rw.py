from kvstore import KVStore

d = KVStore(path='test')

import time
import random
count = 1000_000

arr = [i for i in range(count)]
random.shuffle(arr)

start_write = time.time()
for i in arr:
    d.set(i, f'val{i}')

print('write', time.time() - start_write)

# count = 100
start_read = time.time()
a = []
for i in range(count):
    a.append(d.get(i))
    # print(i, d.get(i))
print('read', time.time() - start_read)
