import glob
import os

from kvdb.sst import SST
from kvdb.config import *

class SSTLevels:
    def __init__(self, path) -> None:
        self.path = path
        self.counter = 0
        self.leveled_ssts = [[] for _ in range(max_depth)]
        if os.path.exists(path):
            self.load_ssts()
        else:
            os.mkdir(path)
    
    def create_and_add_sst(self, kv_records_iter, y=max_depth-1):
        x = len(self.leveled_ssts[y])
        sst = SST.create_from_kv_records(f'{self.path}/sst-{y}-{x}-{self.counter}.sst', kv_records_iter)
        self.counter += 1
        self.leveled_ssts[y].append(sst)
        if len(self.leveled_ssts[y]) > max_size_per_level and y != 0:
            self.compact_level_and_move_to_next_level(y)

    def compact_level_and_move_to_next_level(self, y):
        assert(y != 0)
        merged_iter = self.merge_iters([sst.get_iter() for sst in self.leveled_ssts[y]])
        self.create_and_add_sst(merged_iter, y-1)
        for sst in self.leveled_ssts[y]:
            os.remove(sst.path)
        self.leveled_ssts[y] = []

    def get(self, k):
        for level in reversed(self.leveled_ssts):
            for sst in reversed(level):
                rec = sst.get(k)
                if rec: 
                    return rec
                
    def get_iter(self):
        return self.merge_iters([sst.get_iter() for level in self.leveled_ssts for sst in level])
    
    @staticmethod
    def get_indices_from_filename(filename, path):
        num_strs = filename.replace(path, '').replace('/', '').replace('sst-', '').replace('.sst', '').split('-')
        y = int(num_strs[0])
        x = int(num_strs[1])
        counter = int(num_strs[2])
        return (x, y, counter)

    def load_ssts(self):
        filenames = glob.glob(self.path+"/sst*.sst")
        filenames.sort(key=lambda fn : SSTLevels.get_indices_from_filename(fn, self.path))
        for filename in filenames:
            sst = SST.create_from_path(filename)
            (x, y, counter) = SSTLevels.get_indices_from_filename(filename, self.path)
            self.counter = max(self.counter, counter+1)
            assert(x == len(self.leveled_ssts[y]))
            self.leveled_ssts[y].append(sst)

    def merge_iters(self, iters):
        all_iter_vals = [[pos, iter, next(iter)] for (pos, iter) in enumerate(iters)]
        while True:
            min_iter_vals = SSTLevels.min_multiple(all_iter_vals, key=lambda x : x[2][0])
            if len(min_iter_vals) == 0:
                return
            # TODO: skip DEL ops
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

    def print_sst_contents(self):
        for level in reversed(self.leveled_ssts):
            for sst in reversed(level):
                print('SST: ', sst.path)
                for rec in sst.get_iter():
                    print(rec)

    def clear(self):
        for level in self.leveled_ssts:
            for sst in level:
                os.remove(sst.path)
        self.leveled_ssts = [[] for _ in range(max_depth)]
