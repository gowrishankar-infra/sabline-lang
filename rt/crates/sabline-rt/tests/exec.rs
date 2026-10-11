//! `sabline-rt exec` (9.0, M3): one program run for whoever started the
//! process, a frame at a time - what `sabline run` and `sabline.run` go
//! through under `SABLINE_REFERENCE_RUNTIME=rust`. These drive the binary
//! as the Python package does (`sabline/through_rt.py`): the request, the
//! answers to the run's questions, the frames in the order the run makes
//! them, the end frame; and a parent that goes away taking the run with it.

use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

use sabline_rt::json::Json;

fn program(name: &str, text: &str) -> PathBuf {
    let dir =
        std::env::temp_dir().join(format!("sabline-rt-exec-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let path = dir.join("p.vel");
    std::fs::write(&path, text).unwrap();
    path
}

fn exec() -> std::process::Child {
    Command::new(env!("CARGO_BIN_EXE_sabline-rt"))
        .args(["exec", "--install-dir", env!("CARGO_MANIFEST_DIR")])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("sabline-rt starts")
}

fn line_of(fields: &[(&str, Json)]) -> String {
    Json::Obj(fields.iter().map(|(k, v)| (k.to_string(), v.clone())).collect()).canonical()
        + "\n"
}

#[test]
fn a_run_is_its_frames_in_order_then_the_end() {
    let path = program(
        "frames",
        "fn main() uses io {\n    print(\"hello\")\n    let a = read_line()\n    \
         let b = ask(\"name?\")\n    log(format(\"{} {}\", a, b))\n    print(args())\n    \
         exit_with(3)\n}\n",
    );
    let mut child = exec();
    let mut stdin = child.stdin.take().unwrap();
    let mut frames = BufReader::new(child.stdout.take().unwrap()).lines();
    stdin
        .write_all(
            line_of(&[
                ("path", Json::text(path.to_string_lossy())),
                ("args", Json::List(vec![Json::text("one"), Json::text("two")])),
            ])
            .as_bytes(),
        )
        .unwrap();
    let mut seen = Vec::new();
    for frame in frames.by_ref() {
        let frame = frame.unwrap();
        if frame.starts_with("{\"read\"") {
            stdin.write_all(b"{\"line\": \"first\\r\\n\"}\n").unwrap();
        } else if frame.starts_with("{\"ask\"") {
            stdin.write_all(b"{\"line\": \"Ada\"}\n").unwrap();
        }
        let end = frame.starts_with("{\"end\"");
        seen.push(frame);
        if end {
            break;
        }
    }
    drop(stdin);
    assert!(child.wait().unwrap().success());
    let end = seen.pop().unwrap();
    assert_eq!(
        seen,
        [
            r#"{"out":"hello\n"}"#,
            r#"{"read":"line"}"#,
            r#"{"ask":"name? "}"#,
            // read_line strips the line feed and nothing else, as the
            // reference's rstrip("\n") does; log writes the \r as an escape
            r#"{"err":"first\\r Ada\n"}"#,
            r#"{"out":"[one, two]\n"}"#,
        ],
        "no audit stream was asked for, so no event"
    );
    assert!(end.contains(r#""exit":3"#), "{end}");
    assert!(end.contains(r#""stdout":"""#), "what was written went as frames: {end}");
    assert!(end.contains(r#""name":"sabline-rt""#), "the receipt is sabline-rt's: {end}");
}

#[test]
fn the_end_of_the_input_is_e607_for_ask_and_nothing_for_read_line() {
    let path = program(
        "eof",
        "fn main() uses io {\n    print(format(\"[{}]\", read_line()))\n    print(ask(\"q\"))\n}\n",
    );
    let mut child = exec();
    let mut stdin = child.stdin.take().unwrap();
    let frames = BufReader::new(child.stdout.take().unwrap()).lines();
    stdin
        .write_all(
            line_of(&[
                ("path", Json::text(path.to_string_lossy())),
                ("stream", Json::Bool(true)),
            ])
            .as_bytes(),
        )
        .unwrap();
    let mut end = String::new();
    let mut events = 0;
    for frame in frames {
        let frame = frame.unwrap();
        if frame.starts_with("{\"read\"") || frame.starts_with("{\"ask\"") {
            stdin.write_all(b"{\"line\": null}\n").unwrap();
        } else if frame.starts_with("{\"event\"") {
            events += 1;
        } else if frame.starts_with("{\"end\"") {
            end = frame;
            break;
        }
    }
    drop(stdin);
    child.wait().unwrap();
    assert!(end.contains(r#""code":"E607""#), "{end}");
    assert!(events >= 4, "start, subjects, the effects and end, as they happened: {events}");
}

#[test]
fn a_parent_that_goes_away_takes_the_run_with_it() {
    let path = program(
        "orphan",
        "fn main() uses io {\n    while true {\n        let x = 1\n    }\n}\n",
    );
    let mut child = exec();
    let mut stdin = child.stdin.take().unwrap();
    stdin
        .write_all(line_of(&[("path", Json::text(path.to_string_lossy()))]).as_bytes())
        .unwrap();
    std::thread::sleep(Duration::from_millis(200));
    drop(stdin); // the parent's end of the pipe closes, as it does when it dies
    let started = Instant::now();
    loop {
        if let Some(status) = child.try_wait().unwrap() {
            assert_eq!(status.code(), Some(i32::from(sabline_rt::exec::ORPHANED)));
            break;
        }
        assert!(started.elapsed() < Duration::from_secs(20), "the run outlived its parent");
        std::thread::sleep(Duration::from_millis(50));
    }
}

/// Every frame of one request, with no input to answer: (frames, end).
fn frames_of(fields: &[(&str, Json)]) -> (Vec<String>, String) {
    let mut child = exec();
    let mut stdin = child.stdin.take().unwrap();
    stdin.write_all(line_of(fields).as_bytes()).unwrap();
    let mut seen = Vec::new();
    let mut end = String::new();
    for frame in BufReader::new(child.stdout.take().unwrap()).lines() {
        let frame = frame.unwrap();
        if frame.starts_with("{\"end\"") {
            end = frame;
            break;
        }
        seen.push(frame);
    }
    drop(stdin);
    child.wait().unwrap();
    (seen, end)
}

#[test]
fn an_import_root_holds_every_import_to_it() {
    let path = program(
        "root",
        "import \"../outside.vel\" as far\nfn main() uses io {\n    print(far.one())\n}\n",
    );
    let served = path.parent().unwrap();
    std::fs::write(
        served.parent().unwrap().join("outside.vel"),
        "fn one() -> Int {\n    return 1\n}\n",
    )
    .unwrap();
    let (_, end) = frames_of(&[
        ("path", Json::text(path.to_string_lossy())),
        ("import_root", Json::text(served.to_string_lossy())),
    ]);
    assert!(end.contains(r#""code":"E515""#), "{end}");
    assert!(end.contains("outside the directory this program is served from"), "{end}");
    // and without one, the same program runs
    let (seen, end) = frames_of(&[("path", Json::text(path.to_string_lossy()))]);
    assert_eq!(seen, [r#"{"out":"1\n"}"#], "{end}");
}

#[test]
fn tests_are_called_in_turn_each_said_after_what_it_printed() {
    let path = program(
        "tests",
        "fn test_one() -> Bool uses io {\n    print(\"from one\")\n    return true\n}\n\n\
         fn test_two() -> Int {\n    return 2\n}\n\n\
         fn test_three() -> Int {\n    let z = 0\n    return 1 / z\n}\n\n\
         fn test_four() -> Int or fail {\n    let n = try to_int(\"x\")\n    return n\n}\n\n\
         fn test_with(n: Int) -> Bool {\n    return true\n}\n\n\
         fn main() uses io {\n    print(\"not run\")\n}\n",
    );
    let (seen, end) = frames_of(&[
        ("path", Json::text(path.to_string_lossy())),
        ("tests", Json::Bool(true)),
    ]);
    assert_eq!(seen.len(), 5, "{seen:?}");
    assert_eq!(seen[0], r#"{"out":"from one\n"}"#);
    assert_eq!(seen[1], r#"{"test":{"name":"test_one","passed":true}}"#);
    assert_eq!(seen[2], r#"{"test":{"name":"test_two","returned":"2"}}"#);
    assert!(
        seen[3].contains(r#""name":"test_three""#) && seen[3].contains(r#""code":"E"#),
        "{}",
        seen[3]
    );
    assert_eq!(
        seen[4],
        r#"{"test":{"failed":"'x' is not a whole number","name":"test_four"}}"#
    );
    assert_eq!(end, r#"{"end":{"tests":{"tests":4}}}"#, "test_with takes an argument");
}

#[test]
fn an_exit_in_a_test_ends_them_there() {
    let path = program(
        "test-exit",
        "fn test_a() -> Bool {\n    return true\n}\n\n\
         fn test_b() -> Bool uses io {\n    exit_with(3)\n    return true\n}\n\n\
         fn test_c() -> Bool {\n    return true\n}\n",
    );
    let (seen, end) = frames_of(&[
        ("path", Json::text(path.to_string_lossy())),
        ("tests", Json::Bool(true)),
    ]);
    assert_eq!(seen, [r#"{"test":{"name":"test_a","passed":true}}"#]);
    assert_eq!(end, r#"{"end":{"tests":{"exit":3}}}"#);
}

#[test]
fn a_request_that_does_not_read_is_refused_with_status_2() {
    let mut child = exec();
    child.stdin.take().unwrap().write_all(b"{\"allow\": \"io\"}\n").unwrap();
    let out = child.wait_with_output().unwrap();
    assert_eq!(out.status.code(), Some(2));
    assert!(String::from_utf8_lossy(&out.stderr).contains("no 'path'"));
}

#[test]
fn a_call_to_python_is_relayed_and_what_the_host_says_is_the_runs() {
    // the host's answers stand in for the Python package's: a value, a
    // handle, what it recorded, and an error that ends the run
    let path = program(
        "relay",
        "fn main() uses io, ffi {\n    check py(\"math\", \"sqrt\", [\"16\"]) {\n        \
         ok v {\n            print(v)\n        }\n        fail w {\n            print(w)\n        \
         }\n    }\n    check py_new(\"collections\", \"Counter\", \"[]\") {\n        ok h {\n            \
         print([h, h])\n        }\n        fail w {\n            print(w)\n        }\n    }\n    \
         check py(\"json\", \"dumps\", [\"x\"]) {\n        ok v {\n            print(v)\n        \
         }\n        fail w {\n            print(w)\n        }\n    }\n}\n",
    );
    let mut child = exec();
    let mut stdin = child.stdin.take().unwrap();
    let mut frames = BufReader::new(child.stdout.take().unwrap()).lines();
    stdin
        .write_all(
            line_of(&[
                ("path", Json::text(path.to_string_lossy())),
                ("allow", Json::text("io,ffi:math,ffi:collections")),
                ("stream", Json::Bool(true)),
            ])
            .as_bytes(),
        )
        .unwrap();
    let answers = [
        r#"{"answer": {"value": "4.0", "did": [], "counted": {}}}"#,
        r#"{"answer": {"value": {"handle": 2, "what": "Counter"}, "did": [], "counted": {}}}"#,
        r#"{"answer": {"error": {"code": "E311", "message": "'py' reaches into Python module 'json', which this run does not allow", "line": 18, "fixes": ["or use a program that does not need it"], "file": null}, "did": [], "counted": {}}}"#,
    ];
    let (mut calls, mut out, mut end) = (Vec::new(), Vec::new(), String::new());
    for frame in frames.by_ref() {
        let frame = frame.unwrap();
        if frame.starts_with("{\"call\"") {
            stdin.write_all(answers[calls.len()].as_bytes()).unwrap();
            stdin.write_all(b"\n").unwrap();
            calls.push(frame);
        } else if frame.starts_with("{\"out\"") {
            out.push(frame);
        } else if frame.starts_with("{\"end\"") {
            end = frame;
            break;
        }
    }
    drop(stdin);
    assert!(child.wait().unwrap().success());
    assert_eq!(
        calls,
        [
            r#"{"call":{"args":["math","sqrt",["16"]],"line":2,"name":"py"}}"#,
            r#"{"call":{"args":["collections","Counter","[]"],"line":10,"name":"py_new"}}"#,
            r#"{"call":{"args":["json","dumps",["x"]],"line":18,"name":"py"}}"#,
        ]
    );
    assert_eq!(out, [r#"{"out":"4.0\n"}"#, r#"{"out":"[<Counter #2>, <Counter #2>]\n"}"#]);
    // the error is the run's: E311 at the line the host said, and the receipt
    // a refusal of the ffi effect, which the run spent three times
    assert!(end.contains(r#""code":"E311""#), "{end}");
    assert!(end.contains(r#""effects_used":{"ffi":3,"io":2}"#), "{end}");
    assert!(
        end.contains(r#"{"code":"E311","effect":"ffi","line":18,"stopped":true,"times":1}"#),
        "{end}"
    );
}
