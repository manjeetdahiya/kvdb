import pickle
import os, shutil
from rbloom import Bloom
from functools import lru_cache
import itertools
from hashlib import sha256

import utils

def hash_func(obj):
    h = sha256(pickle.dumps(obj)).digest()
    return int.from_bytes(h[:16], "big") - 2**127

block_cache_size = 1024
max_memtable_size = 10_000
max_block_size = 100

class KVStore:
    def __init__(self, path) -> None:
        self.memtable = MemTable()
        self.path = path
        shutil.rmtree(path)
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
        kv_records = self.memtable.get_sorted_kv_records()
        sst = SST(f'{self.path}/sst-{len(self.ssts)}.sst', kv_records)
        self.ssts.append(sst)
        self.memtable = MemTable()


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
    def __init__(self, path, kv_records) -> None:
        self.path = path
        self.sst_index = {'sst_blocks_index_start': 0, 'sst_blocks_index_len': 0, 'filter_start': 0, 'filter_len': 0}
        self.write_sst(kv_records)
        self._bf = self.get_filter()

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
            if end_idx - start_idx <= 1 or blocks_bst_index[start_idx][0] == k:
                return blocks_bst_index[start_idx][1]
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
    
    def write_sst(self, kv_records):
        bf = Bloom(max_memtable_size * max_block_size, 0.01, hash_func)
        blocks_bst_index = []
        f = open(self.path, "wb")
        for block_kv_records in itertools.batched(kv_records, max_block_size):
            block_data = {r[0]: r for r in block_kv_records}
            bf.update([r[0] for r in block_kv_records])
            block_start_key = block_kv_records[0][0]
            self.write_block_data(f, block_data, block_start_key, blocks_bst_index)

        self.write_index_filter_and_meta_blocks(f, bf, blocks_bst_index)
        f.close()

    def write_block_data(self, f, block_data, block_start_key, blocks_bst_index):
        d = pickle.dumps(block_data)
        blocks_bst_index.append((block_start_key, (f.tell(), len(d))))
        f.write(d)

    def write_index_filter_and_meta_blocks(self, f, bf, blocks_bst_index):
        d = pickle.dumps(bf.save_bytes())
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
            bf = Bloom(max_memtable_size * max_block_size, 0.01)
            bf.load_bytes(d_filter, hash_func)
            return bf

    def get_blocks_bst_index(self):
        return SST.read_block(self.path, (self.sst_index['sst_blocks_index_start'], self.sst_index['sst_blocks_index_len']))
