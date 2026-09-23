# The embedding limit

This is a section of [EMBEDDING.md](../EMBEDDING.md), on a page of its own so that the embedding guide stays inside the size a page of the site may be. Where it says *above* or *below*, it means that guide.

Sabline embeds natively in one language and one only: Python. `import
sabline` runs the compiler and the program in your process, and the
three calls above return in microseconds to milliseconds - no process,
no serialization. From any other language the boundary is a process:
`sabline serve` (below) puts the same three calls behind a local HTTP
door, and the CrewAI and LangChain tools, being Python, stay on the
native library. The cost of the process boundary is real - a request to
the door pays HTTP framing and a JSON round trip, on the order of a
millisecond on loopback plus whatever the run itself takes, where the
in-process call pays neither - which is why an agent framework written
in Python should call the library, and why the door and the MCP server
keep a worker pool (above) so they do not also pay an interpreter
startup on every call. There is no in-process embedding for Node, Go or
Rust, and there will not be one until the compiler is something other
than a Python package; the process boundary is the supported way, and it is
the boundary the OS enforces, which is stronger than the language's.
