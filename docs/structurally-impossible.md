# What cannot occur in a Velaris program

Some weaknesses cannot be written in Velaris at all: the language has no
way to express them. Each class below is one of those, with the condition
under which that holds. [`check_impossible.py`](../check_impossible.py) holds
a program that tries each, and fails if one gets through; a class without a
test there is not on this page, and it checks that too.

"Cannot occur" is about the program's text and what the runtime does with
it. It is not about the host: a granted `ffi` module can do whatever that
module can do (THREAT_MODEL.md), which is why most rows end with the grant
that would undo them.

| Class | Why it cannot occur | Unless |
|---|---|---|
| CWE-78, OS command injection | No builtin starts a process or takes a command line. A call to `system`, `shell`, `exec`, `spawn` or `popen` does not compile; reaching `subprocess` or `os.system` through `py` is refused at run time without an `ffi` grant naming that module (E310, E311). | the budget grants `ffi` for a module that starts processes - `ffi:subprocess`, `ffi:os`, or plain `ffi`. The audit names the module and warns. |
| CWE-95, eval injection, and CWE-94, code injection | No builtin runs text as code. `import` takes a string written in the source, read when compiling; an import of a variable or of an expression does not parse. A text that holds a program is only ever text. | the budget grants `ffi` for a module that evaluates code, such as `builtins` or `runpy`. |
| CWE-502, deserialization of untrusted data | The JSON builtins give back Text, Int, Float or Bool; a document that names a class gives back that name as text, and nothing is constructed. Reaching `pickle` or a YAML loader through `py_json` is refused without an `ffi` grant naming it. | the budget grants `ffi` for a module that deserializes objects. |
| CWE-200, by one route: a secret in a path or a file | A value from `env()` or `read_file_secret()` is a `Secret`, and `read_file`, `write_file` and `file_exists` refuse one as a path or as content (E560) - including a path joined with one. So a secret cannot become a file name, which error messages and refusals quote, or a file's content. | the program declassifies it: `declassify` is an effect the operator grants, and the audit lists each one with its reason. A secret that arrives another way is ordinary text (THREAT_MODEL.md). |
| CWE-117, log injection | From 8.3 the `log` builtin, which every function of `stdlib/log.vel` calls, writes each call as one line: a line feed, a carriage return, an escape, a NUL and every other control character but tab are written as escapes, so no value can end a line of the log, start one, or move a terminal's cursor over one. | the text goes to standard output with `print`, which is the program's output and is not escaped; or a reader treats the escape sequences themselves as meaningful. |

## Not structurally impossible

| Class | Why not |
|---|---|
| CWE-89, SQL injection | `stdlib/db.vel`'s `run(conn, sql)` takes a query as one text with no parameters, and its `count(conn, table)` writes a table name into the query with `format`. The language cannot tell SQL from any other text, so a program that builds a query from input can be injected. Parameterized queries in `db.vel` change `run`'s signature, which is a break (STABILITY.md), and are left for 9.0. Until then, do not pass input into a query, and do not grant `ffi:sqlite3` to code you have not read. |
