//! What 9.0's second M3 checkpoint changed in a run, held here as well as
//! by the agreement gate, which shows that the two runtimes agree and not
//! what they agree on: a library's function value under a name, how a
//! function value prints, the size limit, and a budget's file grants; and
//! from the third, a file that is not UTF-8, a lone surrogate written, and
//! the file a broken promise names.

use std::fs;
use std::path::PathBuf;

use sabline_rt::budget::Budget;
use sabline_rt::checker::check_types;
use sabline_rt::effects::check_effects;
use sabline_rt::interp::{Io, Runtime, Stop};
use sabline_rt::loader::load_program;
use sabline_rt::text::Text;

/// A fresh directory holding `files`, and the path of the first.
fn written(name: &str, files: &[(&str, &str)]) -> (PathBuf, String) {
    let dir =
        std::env::temp_dir().join(format!("sabline-rt-runs-{name}-{}", std::process::id()));
    let _ = fs::remove_dir_all(&dir);
    fs::create_dir_all(&dir).unwrap();
    for (file, text) in files {
        fs::write(dir.join(file), text).unwrap();
    }
    let first = dir.join(files[0].0).to_string_lossy().into_owned();
    (dir, first)
}

/// What a program printed, and how it stopped, under `budget`.
fn run(path: &str, budget: &str, size_limit: Option<u64>) -> (String, Result<(), Stop>) {
    let loaded = load_program(path, env!("CARGO_MANIFEST_DIR")).expect("it loads");
    let mut problems = Vec::new();
    check_effects(&loaded.funcs, env!("CARGO_MANIFEST_DIR"), &mut problems);
    check_types(&loaded.funcs, &loaded.records, &mut problems).expect("it checks");
    assert!(problems.is_empty(), "{problems:?}");
    let io = Io::new("", vec![Text::from("a")]);
    let mut rt =
        Runtime::new(&loaded.funcs, &loaded.records, Budget::parse(budget).unwrap(), io);
    if let Some(n) = size_limit {
        rt = rt.with_size_limit(n);
    }
    let stopped = rt.interpret();
    (std::mem::take(&mut rt.io.stdout).done().to_string_lossy(), stopped)
}

#[test]
fn a_library_s_function_value_under_a_name_runs_as_it_does_flat() {
    let lib = "fn above(xs: List of Int, floor: Int) -> Bool {\n\
               \x20   return all_of(xs, fn(x: Int) -> Bool { return x > floor })\n}\n";
    for (case, import, call) in [
        ("named", "import \"lib.vel\" as lib\n", "lib.above"),
        ("flat", "import \"lib.vel\"\n", "above"),
    ] {
        let main = format!(
            "{import}fn main() uses io {{\n    print({call}([3, 4], 2))\n    print({call}([1], 2))\n}}\n"
        );
        let (dir, path) = written(case, &[("main.vel", &main), ("lib.vel", lib)]);
        let loaded = load_program(&path, env!("CARGO_MANIFEST_DIR")).unwrap();
        let lifted: Vec<&str> =
            loaded.funcs.iter().map(|f| f.name.as_str()).filter(|n| n.contains('#')).collect();
        assert_eq!(lifted, if case == "named" { vec!["lib.fn#1"] } else { vec!["fn#1"] });
        let (out, stopped) = run(&path, "io", None);
        assert_eq!(out, "true\nfalse\n", "{case}");
        assert!(stopped.is_ok());
        let _ = fs::remove_dir_all(dir);
    }
}

#[test]
fn a_function_value_prints_as_its_name() {
    let main = "fn double(x: Int) -> Int {\n    return x * 2\n}\n\
                fn main() uses io {\n    let n = 3\n\
                \x20   let g = fn(x: Int) -> Int { return x + n }\n\
                \x20   print(double)\n    print(g)\n    print([double, g])\n}\n";
    let (dir, path) = written("prints", &[("main.vel", main)]);
    let (out, stopped) = run(&path, "io", None);
    assert_eq!(out, "fn double\nfn fn#1\n[fn double, fn fn#1]\n");
    assert!(stopped.is_ok());
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn the_size_limit_stops_the_operation_that_passes_it() {
    let main = "fn main() uses io {\n    let s = \"ab\"\n    while true {\n\
                \x20       s = s + s\n        print(length(s))\n    }\n}\n";
    let (dir, path) = written("size", &[("main.vel", main)]);
    // 4 and then 8 made by `+`, and each printed length counted as the
    // text print writes: 4 + 1 + 8 + 1 = 14; the next `+` makes 16 (30),
    // its length is two more (32), and the `+` after it 32 more
    let (out, stopped) = run(&path, "io", Some(20));
    assert_eq!(out, "4\n8\n");
    assert!(matches!(stopped, Err(Stop::Size(4))), "{stopped:?}");
    let (out, stopped) = run(&path, "io", Some(31));
    assert_eq!(out, "4\n8\n", "the print that passes it writes nothing");
    assert!(matches!(stopped, Err(Stop::Size(5))), "{stopped:?}");
    let (out, stopped) = run(&path, "io", Some(32));
    assert_eq!(out, "4\n8\n16\n", "exactly at it is not past it");
    assert!(matches!(stopped, Err(Stop::Size(4))), "{stopped:?}");
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn a_file_outside_the_grant_is_e313_and_inside_it_is_read() {
    let (dir, _) = written("fs", &[("a.txt", "inside\r\nthere")]);
    let data = dir.to_string_lossy().replace('\\', "/");
    let main = format!(
        "fn main() uses io, fs {{\n    check read_file(\"{data}/a.txt\") {{\n\
         \x20       ok t {{\n            print(split(t, \"\\n\"))\n        }}\n\
         \x20       fail w {{\n            print(w)\n        }}\n    }}\n\
         \x20   print(file_exists(\"{data}/../elsewhere.txt\"))\n}}\n"
    );
    fs::write(dir.join("main.vel"), &main).unwrap();
    let path = dir.join("main.vel").to_string_lossy().into_owned();
    let (out, stopped) = run(&path, &format!("io,fs:read:{data}"), None);
    assert_eq!(out, "[inside, there]\n");
    match stopped {
        Err(Stop::Error(e)) => {
            assert_eq!(e.code, "E313");
            assert!(e
                .message
                .to_string_lossy()
                .contains("which this run's fs grants do not cover"));
        }
        other => panic!("{other:?}"),
    }
    let _ = fs::remove_dir_all(dir);
}

/// The error a run stopped with, as (code, the file's name, line).
fn stopped_at(stopped: Result<(), Stop>) -> (&'static str, String, u32) {
    match stopped {
        Err(Stop::Error(e)) => {
            let file = e.file.unwrap_or_default();
            let name = std::path::Path::new(&file)
                .file_name()
                .map(|n| n.to_string_lossy().into_owned())
                .unwrap_or_default();
            (e.code, name, e.line)
        }
        other => panic!("{other:?}"),
    }
}

#[test]
fn a_file_that_is_not_utf8_is_a_failure_the_program_handles() {
    let (dir, _) = written("not-utf8", &[("a.txt", "")]);
    let data = dir.to_string_lossy().replace('\\', "/");
    let main = format!(
        "fn main() uses io, fs {{\n    check read_file(\"{data}/bad.txt\") {{\n\
         \x20       ok t {{\n            print(t)\n        }}\n\
         \x20       fail w {{\n            print(w)\n        }}\n    }}\n\
         \x20   print(\"on\")\n}}\n"
    );
    fs::write(dir.join("main.vel"), &main).unwrap();
    let path = dir.join("main.vel").to_string_lossy().into_owned();
    for raw in [&b"caf\xe9"[..], b"ab\xe2\x82", b"\xed\xa0\x80"] {
        fs::write(dir.join("bad.txt"), raw).unwrap();
        let (out, stopped) = run(&path, "io,fs", None);
        assert_eq!(
            out,
            format!("cannot read file '{data}/bad.txt': it is not UTF-8 text\non\n")
        );
        assert!(stopped.is_ok(), "{stopped:?}");
    }
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn a_lone_surrogate_is_e608_and_nothing_is_written() {
    let (dir, _) = written("surrogate", &[("kept.txt", "kept")]);
    let data = dir.to_string_lossy().replace('\\', "/");
    for target in ["kept.txt", "new.txt"] {
        let main = format!(
            r#"fn half() -> Text or fail {{
    return try json_get("[\"\\ud800\"]", "0")
}}
fn main() uses io, fs {{
    check half() {{
        ok t {{
            write_file("{data}/{target}", "a" + t)
            print("WROTE IT")
        }}
        fail w {{
            print(w)
        }}
    }}
}}
"#
        );
        fs::write(dir.join("main.vel"), &main).unwrap();
        let path = dir.join("main.vel").to_string_lossy().into_owned();
        let (out, stopped) = run(&path, "io,fs", None);
        assert_eq!(out, "");
        match stopped {
            Err(Stop::Error(e)) => {
                assert_eq!(e.code, "E608");
                assert_eq!(
                    e.message.to_string_lossy(),
                    format!(
                        "could not write '{data}/{target}': the text holds a lone \
                         surrogate, which is not UTF-8"
                    )
                );
            }
            other => panic!("{other:?}"),
        }
    }
    assert_eq!(fs::read(dir.join("kept.txt")).unwrap(), b"kept");
    assert!(!dir.join("new.txt").exists());
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn a_promise_names_the_file_it_is_written_in() {
    let lib = "fn half(x: Int) -> Int\n    requires x > 0\n{\n    return x / 2\n}\n\
               fn negated(x: Int) -> Int\n    ensures result < 0\n{\n    return x\n}\n\
               fn third(xs: List of Int) -> Int\n    requires get(xs, 2) > 0\n{\n\
               \x20   return get(xs, 2)\n}\n\
               fn call_with(f: fn(Int) -> Int, x: Int) -> Int {\n    return f(x)\n}\n";
    for (case, import, p) in [("promise-flat", "", ""), ("promise-named", " as lib", "lib.")] {
        for (call, want) in [
            ("half(0 - 4)", ("E600", 2)),
            ("negated(1)", ("E601", 7)),
            ("third([1])", ("E602", 12)),
        ] {
            let main = format!(
                "import \"lib.vel\"{import}\nfn main() uses io {{\n    print({p}{call})\n}}\n"
            );
            let (dir, path) = written(case, &[("main.vel", &main), ("lib.vel", lib)]);
            let (_, stopped) = run(&path, "io", None);
            assert_eq!(stopped_at(stopped), (want.0, "lib.vel".to_string(), want.1), "{call}");
            let _ = fs::remove_dir_all(dir);
        }
    }
    // the program's own promise, broken when the library calls it back
    let main = "import \"lib.vel\" as lib\n\
                fn positive_only(x: Int) -> Int\n    requires x > 0\n{\n    return x\n}\n\
                fn main() uses io {\n    print(lib.call_with(positive_only, 0 - 2))\n}\n";
    let (dir, path) = written("called-back", &[("main.vel", main), ("lib.vel", lib)]);
    let (_, stopped) = run(&path, "io", None);
    assert_eq!(stopped_at(stopped), ("E600", "main.vel".to_string(), 3));
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn what_is_written_out_is_counted_before_it_is_made() {
    // forty levels, each a list of two of the one below: 82 items made,
    // and 2^40 copies of the text when written out - a terabyte. Every way
    // of writing it out stops at its line under the run document's limit,
    // before anything is made (9.0, M3: the maintainer's decision)
    let mut laughs = String::from("    let a0 = [\"ha\"]\n");
    for k in 1..=40 {
        laughs.push_str(&format!("    let a{k} = [a{}, a{}]\n", k - 1, k - 1));
    }
    for (case, line) in [
        ("print", "print(a40)"),
        ("log", "log(a40)"),
        ("to-text", "let t = to_text(a40)"),
        ("format", "let t = format(\"{}\", a40)"),
        ("plus", "let t = \"x\" + to_text(a40)"),
        ("json-of", "let t = json_of(a40)"),
    ] {
        let main =
            format!("fn main() uses io {{\n{laughs}    {line}\n    print(\"after\")\n}}\n");
        let (dir, path) = written(&format!("laughs-{case}"), &[("main.vel", &main)]);
        let (out, stopped) = run(&path, "io", Some(4_194_304));
        assert_eq!(out, "", "{case}");
        assert!(matches!(stopped, Err(Stop::Size(43))), "{case}: {stopped:?}");
        let _ = fs::remove_dir_all(dir);
    }
    // a broken promise's message names the value: counted first too
    let main = format!(
        "fn short(xs: {}Text) -> Int\n    requires length(xs) > 2\n{{\n    return 0\n}}\n\
         fn main() uses io {{\n{laughs}    print(short(a40))\n}}\n",
        "List of ".repeat(41)
    );
    let (dir, path) = written("laughs-promise", &[("main.vel", &main)]);
    let (_, stopped) = run(&path, "io", Some(4_194_304));
    assert!(matches!(stopped, Err(Stop::Size(2))), "{stopped:?}");
    let _ = fs::remove_dir_all(dir);
}
