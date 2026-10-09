//! What 9.0's second M3 checkpoint changed in a run, held here as well as
//! by the agreement gate, which shows that the two runtimes agree and not
//! what they agree on: a library's function value under a name, how a
//! function value prints, the size limit, and a budget's file grants.

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
