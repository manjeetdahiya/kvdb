import glob

from kvdb.memtable import MemTable
from kvdb.sst import SST
from kvdb.sst_levels import SSTLevels
from kvdb.config import *

class KVStore:
    def __init__(self, path) -> None:
        self.memtable = MemTable()
        self.path = path
        self.sst_levels = SSTLevels(path)

    def get(self, k):
        rec = self.memtable.get(k)
        if rec:
            return rec
        return self.sst_levels.get(k)

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
            self.sst_levels.create_and_add_sst(kv_records)
    
    def get_iter(self):
        return self.sst_levels.get_iter()

    def close(self):
        self.move_memtable_to_sst()

