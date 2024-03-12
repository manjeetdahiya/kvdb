from kvdb import kvstore
path = 'zzztest'

d = kvstore.KVStore(path)

import time
import random
count = 3_000
arr = [i for i in range(count)]
random.shuffle(arr)

start_write = time.time()
for i in arr:
    d.set(i, f'val{i}')
d.close()
print('write', time.time() - start_write)

d = kvstore.KVStore(path)

# count = 100000
# print(d.get(2_999_999))

start_read = time.time()
a = []
for i in range(count):
    val = d.get(i)
    a.append(val)
    assert(val)
    # print(d.get(i))
print('read', time.time() - start_read)


# for i in d.ssts[0].get_iter():
#     print(i)


# for i in d.get_iter():
#     print(i)
# print(next(i))
# print(next(i))
# print(next(i))
# print(next(i))