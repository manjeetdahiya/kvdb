from rocksdict import Rdict, Options

class RDKVStore:
    def __init__(self, path) -> None:
        self.db = Rdict(path)

    def get(self, k):
        if k in self.db:
            return self.db[k]
        return None

    def set(self, k, v):
        self.db[k] = v
