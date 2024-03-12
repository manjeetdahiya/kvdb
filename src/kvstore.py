import os, shutil
import glob
from bloom_filter import BloomFilter

from src.memtable import MemTable
from src.sst import SST


class KVStore:
    def __init__(self, path) -> None:
        self.memtable = MemTable()
        self.path = path
        # shutil.rmtree(path)
        self.sst_counter = 0        
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
        if len(self.ssts) > 10:
            self.compact_ssts()
        self.memtable = MemTable()
        
    def move_memtable_to_sst(self):
        if self.memtable.size() > 0:
            kv_records = self.memtable.get_sorted_kv_records()
            sst = SST.create_from_kv_records(f'{self.path}/sst-{self.sst_counter}.sst', kv_records)
            self.ssts.append(sst)
            self.sst_counter += 1

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
        all_iter_vals = []
        for (pos, iter) in enumerate(iters):
            try:
                all_iter_vals.append([pos, iter, next(iter)])
            except StopIteration:
                all_iter_vals.append([pos, iter, None])

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
    
    def compact_ssts(self):
        # print('start compaction')
        iter_merged = self.get_iter()
        self.sst_counter += 100
        sst_merged = SST.create_from_kv_records(f'{self.path}/sst-{self.sst_counter}.sst', iter_merged)
        self.sst_counter += 1
        for sst in self.ssts:
            os.remove(sst.path)
        self.ssts = [sst_merged]

    @staticmethod
    def min_multiple(items, key):
        min_items = []
        for i in range(len(items)-1, -1, -1):
            if items[i][2] == None:
                continue
            if len(min_items) == 0:
                min_items.append(items[i])
            elif key(min_items[-1]) > key(items[i]):
                min_items = [items[i]]
            elif key(min_items[-1]) == key(items[i]):
                min_items.append(items[i])
        return min_items
