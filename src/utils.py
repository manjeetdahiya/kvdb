def write_int(file_handle, value):
    raw_bytes = [bytes(b, 'utf-8') for b in hex(value)[2:]]
    assert(len(raw_bytes) <= 8)
    padded_bytes = [b'0']*(8-len(raw_bytes)) + raw_bytes
    for byte in padded_bytes:
        file_handle.write(byte)

def read_int(file_handle):
    raw_bytes = [file_handle.read(1) for _ in range(8)]
    return int(b''.join(raw_bytes), 16)
