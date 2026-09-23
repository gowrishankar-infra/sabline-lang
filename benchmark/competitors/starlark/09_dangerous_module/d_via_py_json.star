# Reaches subprocess's equivalent, run_command, through the JSON-shaped call, with the command arriving as a JSON document.


def run_spec(spec):
    return run_command(*json.decode(spec))  # DANGER


print(run_spec('["echo spawned-child-ran"]'))
