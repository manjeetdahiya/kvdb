import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))


from kvdb import kvstore
from tests import commonkvstore

path = 'zzztest'
path = 'zzztest-dd'

d = kvstore.KVStore(path)
# d = commonkvstore.RDKVStore(path)

import time
import random
count = 1_000_000
# count = 10_0
arr = [i for i in range(count)]
random.shuffle(arr)

start_write = time.time()
for i in arr:
    d.set(i, f'val{i}')
d.close()

print('write', time.time() - start_write)
# assert(0)
# d = kvstore.KVStore(path)

# count = 100000
# print(d.get(2_999_999))

start_read = time.time()
a = []
for i in range(count):
    if i == 40:
        pass
    val = d.get(i)
    a.append(val)
    if val == None:
        print(i)
        assert(val)
print('read', time.time() - start_read)


# for i in d.ssts[0].get_iter():
#     print(i)


# for i in d.get_iter():
#     print(i)
# print(next(i))
# print(next(i))
# print(next(i))
# print(next(i))