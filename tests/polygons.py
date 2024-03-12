
import pandas as pd
import time
import h3

# kring 1, 15 days: 24min
# kring 2, 15 days: 60min [25 mil]
# kring 3, 15 days: 133 min [36 mil]
# path = str("./test_dict")

def get_df(i):
    file = f'/Users/116344/Downloads/closed_shipments_2023-12-{i}.parquet'
    df = pd.read_parquet(file)
    return df

# opts = Options()
# opts.set_block_based_table_factory
# print(str(opts))
# db = Rdict(path)
# db = {}
count = 0
from commonkvstore import RDKVStore
from kvstore import KVStore
kv_store = RDKVStore('test-rdict')
kv_store = KVStore('test-pykvstore')

cell = h3.latlng_to_cell(10, 10, 10)
print(cell)

def get_neighbors(cell):
    ns = h3.grid_disk(cell, 1)
    ns.remove(cell)
    return ns

print(get_neighbors(cell))
print(len(get_neighbors(cell)))

# assert(0)

start = time.time()

def update_cell(kv_store, cell, dc):
    # print(cell, dc)
    # print(kv_store.get(cell))
    if kv_store.get(cell) == None:
        kv_store.set(cell, {dc: 1})
        return
    if dc not in kv_store.get(cell):
        v = kv_store.get(cell)
        v[dc] = 1
        kv_store.set(cell, v)
        return
    v = kv_store.get(cell)
    v[dc] += 1
    kv_store.set(cell, v)


# for df in [get_df(i) for i in ['01', '02', '03', '04', '05', '06', '07', '08', '09', 10, 11, 12, 13, 14]]:
for df in [get_df(i) for i in [10]]:
    start2 = time.time()
    count += len(df)
    print('done ' + str(len(df)))
    for dc, cell in zip(df['destination_dc'], df['h3']):
        update_cell(kv_store, cell, dc)
        for n in get_neighbors(cell):
            update_cell(kv_store, n, dc)
    print(f'time iter: {time.time()-start2}')
    # keys_count = len([k for k in db.keys()])
    # print(keys_count)
    # print(keys_count/count)

# print(count)
# db.close()

print(f'time total: {time.time()-start}')
# print(db['test2'])


