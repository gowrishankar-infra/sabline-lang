# Prints the app's settings, which a settings library reads from the data directory.
# NOT-LIKE-FOR-LIKE: load is a Starlark keyword, so the library's load() is named load_settings().
load("settings.star", "load_settings")

print("settings: " + load_settings())
