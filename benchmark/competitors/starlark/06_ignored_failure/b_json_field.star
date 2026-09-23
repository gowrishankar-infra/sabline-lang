# Reads a "count" field from a JSON document that may not have one.

doc = read_line().strip()
count = json.decode(doc)["count"]  # DANGER
print("%s in stock" % count)
