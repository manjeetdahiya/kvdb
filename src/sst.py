import pickle
import itertools
from functools import lru_cache

import src.utils
from src.config import *

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
            for r in block_kv_records:
                bf.add(r[0])
            block_start_key = block_kv_records[0][0]
            self.write_block_data(f, block_data, block_start_key, blocks_bst_index)
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