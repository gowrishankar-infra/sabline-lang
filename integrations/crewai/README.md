# Sabline tools for CrewAI

Run code your agents write, in a box.

```python
from crewai import Agent
from sabline_tool import SablineAuditTool, SablineRunTool

analyst = Agent(
    role="Data analyst",
    goal="Total the expenses in the CSV and report the largest",
    tools=[SablineAuditTool(), SablineRunTool(allow=["io"])],
)
```

The `allow` list takes the full budget grammar and passes it through
unchanged - `["io", "env", "fs:read:./data", "net:api.example.com:443@100"]`
grants exactly those paths, hosts and counts (SPEC.md 7.1).
`SablineRunTool(allow=["io"])` means anything the agent writes can
print and nothing else - not read a file, reach the network, or call
Python - whatever the code claims. The budget is chosen by you, the
crew's author, not by the agent. A refusal stops the program and the
tool reports which effect was refused. `SablineRunTool()` with no
`allow` is the same `io`, which is also what `sabline.run` and the
command line give a run that asks for nothing (sabline-lang 5.0).

`SablineAuditTool` tells the agent (and you) what a program can touch
and how much of its promises were proven before running, in the
versioned `sabline.audit/1` format.

Install the compiler once: `pip install sabline-lang z3-solver`.

Not a security boundary: `allow=["ffi"]` grants everything Python can
do. It is a real guard for the ordinary case of running a script a
model wrote.

Sabline: https://github.com/gowrishankar-infra/sabline-lang
