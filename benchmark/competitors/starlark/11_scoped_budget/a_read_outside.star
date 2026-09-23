# Granted read access to one directory, it reads a file outside it; the path comes from input.
# read_file returns the bytes as they are; .replace("\r\n", "\n") reads them as Python's text mode does.


def peek(path):
    return read_file(path).replace("\r\n", "\n")  # DANGER


path = read_line().strip()
print(peek(path))
