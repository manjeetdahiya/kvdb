from kvstore import KVStore

d = KVStore(path='test')

import time
import random
count = 1_000_000
# count = 1

# arr = [i for i in range(count)]
# random.shuffle(arr)

# start_write = time.time()
# for i in arr:
#     d.set(i, f'val{i}')

# d.close()
# print('write', time.time() - start_write)

# count = 100
# d.get(51)

# start_read = time.time()
# a = []
# for i in range(count):
#     a.append(d.get(i))
# print('read', time.time() - start_read)
# print(a[:200])



for i in d.get_iter():
    print(i)
