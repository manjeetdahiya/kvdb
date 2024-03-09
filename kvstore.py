import pickle
import os, shutil
from functools import lru_cache
import itertools
import glob
import utils
from bloom_filter import BloomFilter

block_cache_size = 1024
max_memtable_size = 100_000
max_block_size = 1_000
bloom_filter_size = 100_000
bloom_filter_prob = 0.01

class KVStore:
    def __init__(self, path) -> None:
        self.memtable = MemTable()
        self.path = path
        # shutil.rmtree(path)
        if os.path.exists(path):
            self.ssts = self.load_sst_files()
        else:
            os.mkdir(path)
            self.ssts = []

    def get(self, k):
        rec = self.memtable.get(k)
        if rec:
            return rec
        for sst in reversed(self.ssts):
            rec = sst.get(k)
            if rec: return rec
        return None

    def set(self, k, v):
        self.memtable.add(k, v, 'SET')
        self.check_and_move_memtable_to_sst()

    def delete(self, k):
        self.memtable.add(k, 'DEL')
        self.check_and_move_memtable_to_sst()

    def check_and_move_memtable_to_sst(self):
        if self.memtable.size() < max_memtable_size:
            return
        self.move_memtable_to_sst()
        self.memtable = MemTable()
        
    def move_memtable_to_sst(self):
        if self.memtable.size() > 0:
            kv_records = self.memtable.get_sorted_kv_records()
            self.ssts.append(SST.create_from_kv_records(f'{self.path}/sst-{len(self.ssts)}.sst', kv_records))

    def load_sst_files(self):
        files = glob.glob(self.path+"/sst*.sst")
        files.sort(key=lambda f : int(f.replace('sst-', '').replace('.sst', '').replace(self.path, '').replace('/', '')))
        return [SST.create_from_path(file) for file in files]
    
    def close(self):
        self.move_memtable_to_sst()

    def get_iter(self):
        self.close()
        return self.merge_iters([sst.get_iter() for sst in self.ssts])
    
    def merge_iters(self, iters):
        all_iter_vals = [[pos, iter, next(iter)] for (pos, iter) in enumerate(iters)]
        while True:
            min_iter_vals = KVStore.min_multiple(all_iter_vals, key=lambda x : x[2][0])
            if len(min_iter_vals) == 0:
                return
            yield_record = min_iter_vals[-1][2]
            for (i, _, _) in min_iter_vals:
                try:
                    all_iter_vals[i][2] = next(all_iter_vals[i][1])
                except StopIteration:
                    all_iter_vals[i][2] = None
            yield yield_record
    
    @staticmethod
    def min_multiple(items, key):
        min_items = []
        for i in range(len(items)-1, 0, -1):
            if items[i][2] == None:
                continue
            if len(min_items) == 0:
                min_items.append(items[i])
            elif key(min_items[-1]) > key(items[i]):
                min_items = [items[i]]
            elif key(min_items[-1]) == key(items[i]):
                min_items.append(items[i])
        return min_items


class MemTable:
    def __init__(self) -> None:
        self.table = {}

    def size(self):
        return len(self.table)

    def add(self, k, v, op):
        self.table[k] = [k, v, op]

    def get(self, k):
        if k in self.table:
            if self.table[k][2] == 'SET':
                return self.table[k][1]
        return None
    
    def get_sorted_kv_records(self):
        return [r for _, r in sorted(self.table.items())]


class SST:
    def __init__(self, path):
        self.path = path
        self.sst_index = {'sst_blocks_index_start': 0, 'sst_blocks_index_len': 0, 'filter_start': 0, 'filter_len': 0}

    @staticmethod
    def create_from_kv_records(path, kv_records):
        sst = SST(path)
        sst.write(kv_records)
        return sst

    @staticmethod
    def create_from_path(path):
        sst = SST(path)
        sst.read_meta_block()
        sst._bf = sst.get_filter()
        return sst

    def get(self, k):
        if k not in self._bf:
            return None
        relevant_block_pos = self.find_relevant_block(k)
        if relevant_block_pos:
            sst_block_data = SST.read_block(self.path, relevant_block_pos)
            if k in sst_block_data:
                if sst_block_data[k][2] == 'SET':
                    return sst_block_data[k][1]
        return None
    
    def find_relevant_block(self, k):
        blocks_bst_index = self.get_blocks_bst_index()
        start_idx, end_idx = 0, len(blocks_bst_index) - 1
        while True:
            if k < blocks_bst_index[start_idx][0]:
                return None
            if blocks_bst_index[start_idx][0] == k:
                return blocks_bst_index[start_idx][1]
            if blocks_bst_index[end_idx][0] == k:
                return blocks_bst_index[end_idx][1]
            if end_idx == start_idx:
                return blocks_bst_index[start_idx][1]
            if end_idx - 1 == start_idx:
                if k < blocks_bst_index[end_idx][0]:
                    return blocks_bst_index[start_idx][1]
                else:
                    return blocks_bst_index[end_idx][1]
            mid_idx = (start_idx + end_idx) // 2
            if k < blocks_bst_index[mid_idx][0]:
                end_idx = mid_idx
            else:
                start_idx = mid_idx
    
    @staticmethod
    @lru_cache(maxsize=block_cache_size)
    def read_block(path, pos):
        with open(path, "rb") as f:
            f.seek(pos[0])
            d = f.read(pos[1])
            return pickle.loads(d)
    
    def write(self, kv_records):
        bf = BloomFilter(max_elements=bloom_filter_size, error_rate=bloom_filter_prob)
        blocks_bst_index = []
        f = open(self.path, "wb")
        for block_kv_records in itertools.batched(kv_records, max_block_size):
            block_data = {r[0]: r for r in block_kv_records}
            block_start_key = block_kv_records[0][0]
            self.write_block_data(f, block_data, block_start_key, blocks_bst_index)
        for rec in kv_records:
            bf.add(rec[0])
        self.write_index_filter_and_meta_blocks(f, bf, blocks_bst_index)
        f.close()
        self._bf = self.get_filter()

    def write_block_data(self, f, block_data, block_start_key, blocks_bst_index):
        d = pickle.dumps(block_data)
        blocks_bst_index.append((block_start_key, (f.tell(), len(d))))
        f.write(d)

    def write_index_filter_and_meta_blocks(self, f, bf, blocks_bst_index):
        d = pickle.dumps(bf)
        self.sst_index['filter_start'] = f.tell()
        self.sst_index['filter_len'] = len(d)
        f.write(d)
        d = pickle.dumps(blocks_bst_index)
        self.sst_index['sst_blocks_index_start'] = f.tell()
        self.sst_index['sst_blocks_index_len'] = len(d)
        f.write(d)
        utils.write_int(f, self.sst_index['sst_blocks_index_start'])
        utils.write_int(f, self.sst_index['sst_blocks_index_len'])
        utils.write_int(f, self.sst_index['filter_start'])
        utils.write_int(f, self.sst_index['filter_len'])

    def read_meta_block(self):
        with open(self.path, "rb") as f:
            f.seek(-8*4, 2)
            self.sst_index['sst_blocks_index_start'] = utils.read_int(f)
            self.sst_index['sst_blocks_index_len'] = utils.read_int(f)
            self.sst_index['filter_start'] = utils.read_int(f)
            self.sst_index['filter_len'] = utils.read_int(f)

    def get_filter(self):
        with open(self.path, "rb") as f:
            f.seek(self.sst_index['filter_start'])
            d_filter = f.read(self.sst_index['filter_len'])
            bf = pickle.loads(d_filter)
            return bf

    def get_blocks_bst_index(self):
        return SST.read_block(self.path, (self.sst_index['sst_blocks_index_start'], self.sst_index['sst_blocks_index_len']))
    
    def get_iter(self):
        blocks_bst_index = self.get_blocks_bst_index()
        for (_, block_pos) in blocks_bst_index:
            block_data = SST.read_block(self.path, block_pos)
            for k in sorted(block_data.keys()):
                yield block_data[k]
