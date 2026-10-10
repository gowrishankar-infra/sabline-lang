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

#[test]
fn a_request_that_does_not_read_is_refused_with_status_2() {
    let mut child = exec();
    child.stdin.take().unwrap().write_all(b"{\"allow\": \"io\"}\n").unwrap();
    let out = child.wait_with_output().unwrap();
    assert_eq!(out.status.code(), Some(2));
    assert!(String::from_utf8_lossy(&out.stderr).contains("no 'path'"));
}
