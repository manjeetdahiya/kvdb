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