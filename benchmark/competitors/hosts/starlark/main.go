// The Starlark column's host: starlark-go, with nothing predeclared but what
// the task's grant names.
//
//	starlark-host check FILE --grant G ...   parse and resolve, run nothing
//	starlark-host run   FILE --grant G ...   parse, resolve and execute
//
// Starlark has no I/O of its own. Everything a program can reach is a name
// the host predeclares, so this file is the whole of the Starlark column's
// authority, and it is kept small enough to read in one sitting. The rule is
// the same one benchmark/run.py applies to Deno's flags: the narrowest grant
// that still lets the task's legitimate work run, derived from the task's
// `needs` in corpus.json, never tuned per program.
//
//	always     print (Starlark's own), read_line(), and the pure json and
//	           math modules, which compute and reach nothing
//	fs:read:D  read_file(path), refused outside D
//	fs:write:D write_file(path, text), refused outside D (8.7)
//	net:H:P    http_get(url) and http_post(url, body), refused for any other
//	           host or port, including by redirect
//	run:NAME   run_program(name, args), which runs NAME alone and refuses any
//	           other program (8.7: the task needs one program)
//
// Nothing else is ever defined: no environment, no other process, no
// directory listing, and no write but under a write grant. A program that calls one names something undefined,
// which the resolver rejects before anything runs.
//
// The dialect is Starlark's default (the one Bazel's BUILD files use): no
// while, no recursion, no top-level control flow, no reassigning a global.
// load("NAME.star", ...) reads NAME.star beside the program, with the same
// predeclared names; a module that is not there fails when the load runs.
//
// check prints one JSON object on stdout: {"diagnostics": [{line, col,
// message}]}, and exits 1 if there is any. run lets the program print to
// stdout; an error is written to stderr as `starlark-error: FILE:LINE:COL:
// MESSAGE` (the innermost frame in a .star file) and exits 1. A run past
// --timeout seconds is cancelled by the thread itself and exits 3.
package main

import (
	"bufio"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	stjson "go.starlark.net/lib/json"
	stmath "go.starlark.net/lib/math"
	"go.starlark.net/resolve"
	"go.starlark.net/starlark"
	"go.starlark.net/syntax"
)

var dialect = &syntax.FileOptions{Set: true}

type grants struct {
	readDirs  []string
	writeDirs []string
	netHosts  []string // "host:port"
	programs  []string // run:NAME
}

func main() {
	if len(os.Args) < 3 {
		fmt.Fprintln(os.Stderr, "usage: starlark-host check|run FILE [--grant G]... [--timeout S]")
		os.Exit(2)
	}
	mode, file := os.Args[1], os.Args[2]
	var g grants
	timeout := 5.0
	for i := 3; i < len(os.Args); i++ {
		switch os.Args[i] {
		case "--grant":
			i++
			addGrant(&g, os.Args[i])
		case "--timeout":
			i++
			t, err := strconv.ParseFloat(os.Args[i], 64)
			if err != nil {
				fmt.Fprintln(os.Stderr, "bad --timeout")
				os.Exit(2)
			}
			timeout = t
		default:
			fmt.Fprintln(os.Stderr, "unknown argument", os.Args[i])
			os.Exit(2)
		}
	}
	pre := predeclared(g)
	switch mode {
	case "check":
		os.Exit(check(file, pre))
	case "run":
		os.Exit(run(file, pre, timeout))
	default:
		fmt.Fprintln(os.Stderr, "unknown mode", mode)
		os.Exit(2)
	}
}

func addGrant(g *grants, s string) {
	switch {
	case s == "io", strings.HasPrefix(s, "ffi:"):
		// io is always granted here (every task needs it); math is pure
	case strings.HasPrefix(s, "fs:read:"):
		g.readDirs = append(g.readDirs, realDir(strings.TrimPrefix(s, "fs:read:")))
	case strings.HasPrefix(s, "fs:write:"):
		g.writeDirs = append(g.writeDirs, realDir(strings.TrimPrefix(s, "fs:write:")))
	case strings.HasPrefix(s, "net:"):
		g.netHosts = append(g.netHosts, strings.TrimPrefix(s, "net:"))
	case strings.HasPrefix(s, "run:"):
		g.programs = append(g.programs, strings.TrimPrefix(s, "run:"))
	default:
		fmt.Fprintln(os.Stderr, "unknown grant", s)
		os.Exit(2)
	}
}

// ---- the predeclared names --------------------------------------------------

var stdin = bufio.NewReader(os.Stdin)

func predeclared(g grants) starlark.StringDict {
	d := starlark.StringDict{
		"read_line": starlark.NewBuiltin("read_line", readLine),
		"json":      stjson.Module,
		"math":      stmath.Module,
	}
	if len(g.readDirs) > 0 {
		d["read_file"] = starlark.NewBuiltin("read_file", readFile(g.readDirs))
	}
	if len(g.writeDirs) > 0 {
		d["write_file"] = starlark.NewBuiltin("write_file", writeFile(g.writeDirs))
	}
	if len(g.netHosts) > 0 {
		d["http_get"] = starlark.NewBuiltin("http_get", httpCall(g.netHosts, false))
		d["http_post"] = starlark.NewBuiltin("http_post", httpCall(g.netHosts, true))
	}
	if len(g.programs) > 0 {
		d["run_program"] = starlark.NewBuiltin("run_program", runProgram(g.programs))
	}
	return d
}

func runProgram(names []string) func(*starlark.Thread, *starlark.Builtin, starlark.Tuple, []starlark.Tuple) (starlark.Value, error) {
	return func(_ *starlark.Thread, b *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
		var name string
		var list *starlark.List
		if err := starlark.UnpackPositionalArgs(b.Name(), args, kwargs, 2, &name, &list); err != nil {
			return nil, err
		}
		granted := false
		for _, n := range names {
			if name == n {
				granted = true
			}
		}
		if !granted {
			return nil, fmt.Errorf("run_program: %s is not granted", name)
		}
		argv := []string{}
		for i := 0; i < list.Len(); i++ {
			s, ok := starlark.AsString(list.Index(i))
			if !ok {
				return nil, fmt.Errorf("run_program: arguments are strings")
			}
			argv = append(argv, s)
		}
		out, err := exec.Command(name, argv...).Output()
		if err != nil {
			return nil, fmt.Errorf("run_program: %v", err)
		}
		return starlark.String(out), nil
	}
}

func readLine(_ *starlark.Thread, b *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
	if err := starlark.UnpackPositionalArgs(b.Name(), args, kwargs, 0); err != nil {
		return nil, err
	}
	line, err := stdin.ReadString('\n')
	if err != nil && !errors.Is(err, io.EOF) {
		return nil, err
	}
	return starlark.String(strings.TrimRight(line, "\r\n")), nil
}

func readFile(dirs []string) func(*starlark.Thread, *starlark.Builtin, starlark.Tuple, []starlark.Tuple) (starlark.Value, error) {
	return func(_ *starlark.Thread, b *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
		var path string
		if err := starlark.UnpackPositionalArgs(b.Name(), args, kwargs, 1, &path); err != nil {
			return nil, err
		}
		abs, err := filepath.Abs(path)
		if err != nil {
			return nil, err
		}
		real, err := filepath.EvalSymlinks(abs)
		if err != nil {
			return nil, fmt.Errorf("read_file: %s: %v", path, err)
		}
		for _, dir := range dirs {
			rel, err := filepath.Rel(dir, real)
			if err == nil && rel != ".." && !strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
				data, err := os.ReadFile(real)
				if err != nil {
					return nil, fmt.Errorf("read_file: %v", err)
				}
				return starlark.String(data), nil
			}
		}
		return nil, fmt.Errorf("read_file: %s is outside the granted directory", path)
	}
}

func realDir(dir string) string {
	abs, err := filepath.Abs(dir)
	if err != nil {
		return dir
	}
	if real, err := filepath.EvalSymlinks(abs); err == nil {
		return real
	}
	return abs
}

func within(dirs []string, path string) bool {
	for _, dir := range dirs {
		rel, err := filepath.Rel(dir, path)
		if err == nil && rel != ".." && !strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
			return true
		}
	}
	return false
}

func writeFile(dirs []string) func(*starlark.Thread, *starlark.Builtin, starlark.Tuple, []starlark.Tuple) (starlark.Value, error) {
	return func(_ *starlark.Thread, b *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
		var path, text string
		if err := starlark.UnpackPositionalArgs(b.Name(), args, kwargs, 2, &path, &text); err != nil {
			return nil, err
		}
		abs, err := filepath.Abs(path)
		if err != nil {
			return nil, err
		}
		// the file need not exist: its directory is what must be granted
		if !within(dirs, realDir(filepath.Dir(abs))) {
			return nil, fmt.Errorf("write_file: %s is outside the granted directory", path)
		}
		if err := os.WriteFile(abs, []byte(text), 0o644); err != nil {
			return nil, fmt.Errorf("write_file: %v", err)
		}
		return starlark.None, nil
	}
}

func allowed(hosts []string, u *url.URL) bool {
	for _, h := range hosts {
		if u.Host == h {
			return true
		}
	}
	return false
}

func httpCall(hosts []string, post bool) func(*starlark.Thread, *starlark.Builtin, starlark.Tuple, []starlark.Tuple) (starlark.Value, error) {
	client := &http.Client{
		Timeout: 10 * time.Second,
		CheckRedirect: func(req *http.Request, _ []*http.Request) error {
			if !allowed(hosts, req.URL) {
				return fmt.Errorf("redirect to %s is not granted", req.URL.Host)
			}
			return nil
		},
	}
	return func(_ *starlark.Thread, b *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
		var raw, body string
		var err error
		if post {
			err = starlark.UnpackPositionalArgs(b.Name(), args, kwargs, 2, &raw, &body)
		} else {
			err = starlark.UnpackPositionalArgs(b.Name(), args, kwargs, 1, &raw)
		}
		if err != nil {
			return nil, err
		}
		u, err := url.Parse(raw)
		if err != nil || (u.Scheme != "http" && u.Scheme != "https") {
			return nil, fmt.Errorf("%s: not an http URL: %q", b.Name(), raw)
		}
		if !allowed(hosts, u) {
			return nil, fmt.Errorf("%s: %s is not granted", b.Name(), u.Host)
		}
		var resp *http.Response
		if post {
			resp, err = client.Post(raw, "text/plain", strings.NewReader(body))
		} else {
			resp, err = client.Get(raw)
		}
		if err != nil {
			return nil, fmt.Errorf("%s: %v", b.Name(), err)
		}
		defer resp.Body.Close()
		data, err := io.ReadAll(resp.Body)
		if err != nil {
			return nil, err
		}
		return starlark.String(data), nil
	}
}

// ---- check ------------------------------------------------------------------

type diagnostic struct {
	Line    int32  `json:"line"`
	Col     int32  `json:"col"`
	Message string `json:"message"`
}

func check(file string, pre starlark.StringDict) int {
	src, err := os.ReadFile(file)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 2
	}
	var diags []diagnostic
	_, _, err = starlark.SourceProgramOptions(dialect, file, src, pre.Has)
	var list resolve.ErrorList
	var syn syntax.Error
	switch {
	case err == nil:
	case errors.As(err, &list):
		for _, e := range list {
			diags = append(diags, diagnostic{e.Pos.Line, e.Pos.Col, e.Msg})
		}
	case errors.As(err, &syn):
		diags = append(diags, diagnostic{syn.Pos.Line, syn.Pos.Col, syn.Msg})
	default:
		diags = append(diags, diagnostic{0, 0, err.Error()})
	}
	out, _ := json.Marshal(map[string]any{"diagnostics": orEmpty(diags)})
	fmt.Println(string(out))
	if len(diags) > 0 {
		return 1
	}
	return 0
}

func orEmpty(d []diagnostic) []diagnostic {
	if d == nil {
		return []diagnostic{}
	}
	return d
}

// ---- run --------------------------------------------------------------------

type loaded struct {
	globals starlark.StringDict
	err     error
}

func run(file string, pre starlark.StringDict, timeout float64) int {
	dir := filepath.Dir(file)
	cache := map[string]*loaded{}
	var threads []*starlark.Thread
	thread := &starlark.Thread{
		Name:  "main",
		Print: func(_ *starlark.Thread, msg string) { fmt.Println(msg) },
	}
	thread.Load = func(t *starlark.Thread, module string) (starlark.StringDict, error) {
		if c, ok := cache[module]; ok {
			return c.globals, c.err
		}
		if filepath.Base(module) != module || !strings.HasSuffix(module, ".star") {
			return nil, fmt.Errorf("cannot load %s: only a .star file beside the program", module)
		}
		src, err := os.ReadFile(filepath.Join(dir, module))
		if err != nil {
			cache[module] = &loaded{nil, errors.New("no such module beside the program")}
			return nil, cache[module].err
		}
		cache[module] = &loaded{nil, fmt.Errorf("cycle in load graph")}
		child := &starlark.Thread{Name: module, Print: t.Print, Load: t.Load}
		threads = append(threads, child)
		g, err := starlark.ExecFileOptions(dialect, child, filepath.Join(dir, module), src, pre)
		cache[module] = &loaded{g, err}
		return g, err
	}
	timer := time.AfterFunc(time.Duration(timeout*float64(time.Second)), func() {
		thread.Cancel("timeout")
		for _, t := range threads {
			t.Cancel("timeout")
		}
	})
	defer timer.Stop()
	src, err := os.ReadFile(file)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 2
	}
	_, err = starlark.ExecFileOptions(dialect, thread, file, src, pre)
	if err == nil {
		return 0
	}
	report(err)
	if strings.Contains(err.Error(), "cancelled: timeout") {
		return 3
	}
	return 1
}

// report writes the error with the innermost position that is in a .star
// file, so the harness can tell which line failed.
func report(err error) {
	var ee *starlark.EvalError
	var list resolve.ErrorList
	var syn syntax.Error
	switch {
	case errors.As(err, &ee):
		pos := ""
		for i := 0; i < len(ee.CallStack); i++ {
			f := ee.CallStack.At(i)
			if strings.HasSuffix(f.Pos.Filename(), ".star") {
				pos = fmt.Sprintf("%s:%d:%d", filepath.Base(f.Pos.Filename()), f.Pos.Line, f.Pos.Col)
				break
			}
		}
		fmt.Fprintf(os.Stderr, "starlark-error: %s: %s\n", pos, flatten(ee.Msg))
		fmt.Fprintln(os.Stderr, ee.Backtrace())
	case errors.As(err, &list):
		e := list[0]
		fmt.Fprintf(os.Stderr, "starlark-error: %s:%d:%d: %s\n", filepath.Base(e.Pos.Filename()), e.Pos.Line, e.Pos.Col, flatten(e.Msg))
	case errors.As(err, &syn):
		fmt.Fprintf(os.Stderr, "starlark-error: %s:%d:%d: %s\n", filepath.Base(syn.Pos.Filename()), syn.Pos.Line, syn.Pos.Col, flatten(syn.Msg))
	default:
		fmt.Fprintf(os.Stderr, "starlark-error: : %s\n", flatten(err.Error()))
	}
}

func flatten(s string) string { return strings.ReplaceAll(s, "\n", " ") }
