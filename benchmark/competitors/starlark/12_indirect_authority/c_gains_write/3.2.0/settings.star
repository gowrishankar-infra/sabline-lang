# settings 3.2.0: reads the settings file.
# NOT-LIKE-FOR-LIKE: Starlark has no try and reserves the word load: the function is load_settings(), and a failed write or read stops the program instead of being ignored or returning "defaults".
# read_file returns the bytes as they are; .replace("\r\n", "\n") reads them as Python's text mode does.


def load_settings():
    write_file("{path}", "settings loaded")  # DANGER
    return read_file("{granted}/notes.txt").replace("\r\n", "\n")
