# kvdb

A tiny key-value store written in pure Python, built on a Log-Structured
Merge-tree (LSM-tree) design, like LevelDB.

## Features

- **MemTable**: writes go to an in-memory table, which is flushed to disk as a sorted file once it fills up.
- **SSTables**: immutable, sorted, block-based files on disk. Each one has a block index, a Bloom filter and a footer holding the metadata offsets.
- **Bloom filters**: skip SSTables that cannot contain a key, so most missed lookups avoid disk reads.
- **Block cache**: an LRU cache of recently read blocks.
- **Leveled compaction**: when a level holds too many SSTables, they are merged into a single SSTable on the next level up.
- **Persistence**: reopening a `KVStore` on the same directory reloads the existing SSTables.
- **Tombstones**: deletes are recorded as `DEL` markers.
- **Sorted iteration**: a k-way merge across all SSTables.

## Installation

```bash
git clone <repo-url>
cd kvdb
pip install -r requirements.txt   # bloom-filter
```

Requires Python 3.12 or later (uses `itertools.batched`).

## Usage

```python
from kvdb.kvstore import KVStore

db = KVStore("mydb")        # directory is created if missing

db.set("name", "kvdb")
print(db.get("name"))       # -> "kvdb"

db.delete("name")

for key, value, op in db.get_iter():   # records in sorted key order
    print(key, value, op)

db.close()                  # flush the memtable to disk
```

## Architecture

```
  set/delete                         get
      │                               │
      ▼                               ▼
  ┌──────────┐  flush when full   ┌──────────┐
  │ MemTable │ ─────────────────► │  Level 4 │  newest SSTs
  └──────────┘                    ├──────────┤
                                  │  Level 3 │
                                  │   ...    │  compaction moves
                                  │  Level 0 │  merged SSTs up
                                  └──────────┘  oldest SSTs
```

- **Write path**: `set`/`delete` update the memtable. At `max_memtable_size` entries it is sorted and written as a new SST in the deepest level.
- **Read path**: check the memtable first, then SSTs from newest to oldest. For each SST, the Bloom filter is checked, then a binary search over the block index finds the block, which is read and cached.
- **Compaction**: when a level exceeds `max_size_per_level` SSTs, they are merged with a k-way merge into one SST on the next level.

### SST file layout

```
[ data block ][ data block ] ... [ Bloom filter ][ block index ][ footer: 4 × 8-byte hex ints ]
```

## Configuration

Settings are in [`kvdb/config.py`](kvdb/config.py):

| Option | Default | Meaning |
|---|---|---|
| `max_memtable_size` | 10,000 | Entries before the memtable is flushed |
| `max_block_size` | 1,000 | Records per SST block |
| `block_cache_size` | 1,024 | Number of blocks held in the LRU cache |
| `bloom_filter_size` | 1,000,000 | Expected elements per Bloom filter |
| `bloom_filter_prob` | 0.01 | Bloom filter false-positive rate |
| `max_depth` | 5 | Number of levels |
| `max_size_per_level` | 5 | SSTs per level before compaction |

## Tests / benchmarks

```bash
python tests/test_sequential_rw.py
```

Writes and reads 1,000,000 shuffled keys and prints timings.

## Limitations

- No write-ahead log, so data still in the memtable is lost if the process crashes before `close()`.
- No concurrency control or thread safety.
- Tombstones are not yet dropped during compaction (see the `TODO` in `sst_levels.py`).
- Blocks use `pickle`, so SST files should only come from trusted sources.
- Keys must be mutually comparable.

## License

[MIT](LICENSE)
