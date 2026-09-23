# Parses the input as JSON without handling the parse failing.

doc = read_line().strip()
name = json.decode(doc)["name"]  # DANGER
print("hello, " + name)
