import os, shutil

from kvdb.sst import SST
from kvdb.config import *

class SSTLevels:
    def __init__(self, path) -> None:
        self.path = path
        self.counter = 0
        if os.path.exists(path):
            shutil.rmtree(path)
            # self.load_ssts()
        # else:
        os.mkdir(path)
        self.leveled_ssts = [[], [], [], [], []]

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
        return self.merge_iters([sst for level in self.leveled_ssts for sst in level])

    def load_ssts(self):
        assert(0)

    def merge_iters(self, iters):
        all_iter_vals = [[pos, iter, next(iter)] for (pos, iter) in enumerate(iters)]
        # for (pos, iter) in enumerate(iters):
        #     try:
        #         all_iter_vals.append([pos, iter, next(iter)])
        #     except StopIteration:
        #         all_iter_vals.append([pos, iter, None])

        while True:
            min_iter_vals = SSTLevels.min_multiple(all_iter_vals, key=lambda x : x[2][0])
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
                
                
    # def load_sst_files(self):
    #     files = glob.glob(self.path+"/sst*.sst")
    #     files.sort(key=lambda f : int(f.replace('sst-', '').replace('.sst', '').replace(self.path, '').replace('/', '')))
    #     return [SST.create_from_path(file) for file in files]