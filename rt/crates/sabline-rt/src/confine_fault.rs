//! The fault-injection hook (9.0, M4), `SABLINE_FAULT_INJECT`: **the
//! honesty test**, and the one thing that must not be weakened to pass.
//!
//! Once the confinement has been applied - or not, under `--no-confine` -
//! the runtime itself, in Rust and not from Sabline, attempts one effect no
//! budget was consulted about. Under confinement the operating system
//! refuses it and the run ends with **E319** naming the layers; where
//! `ENFORCES` says the thing is not held, it goes through and the run says
//! so on the error channel and carries on; and under `--no-confine` it
//! always goes through.
//!
//! A program cannot set it: it is read from the environment the process was
//! started with, and each of these is something the person who set it could
//! do themselves. `sabline/confine.py`'s `inject_fault` is the same hook in
//! the Python runtime, with the same words, so `check_confine.py` asks both
//! runtimes the same question and expects the same answer.
//!
//! The faults: `read:PATH`, `write:PATH`, `connect:HOST:PORT`, `spawn`,
//! `spawn-breakaway` (Windows: a process asked to leave the job),
//! `signal:PID`, `mount:SOURCE:TARGET` (Linux: a bind mount) and
//! `unix-socket` (a Unix-domain socket made).
//!
//! # The `fault-inject` feature
//!
//! Three of those attempts are C calls - a Unix socket made, `kill(pid,
//! 0)`, a bind mount - and one more thing here stands a layer down:
//! [`NO_LANDLOCK_ENV`], which makes this runtime behave as a kernel with
//! no Landlock would, so that the path a machine nobody has would take is
//! measured on an ordinary one. A variable that turns a layer off in a
//! released binary is a variable that turns confinement off, which
//! `check_self_budget.py` exists to refuse, so **both are behind the
//! `fault-inject` feature, which is off by default**: a released crate
//! carries neither, and the suites that measure the confinement build with
//! it (`cargo build --release --features fault-inject`). The attempts that
//! need no C call - a file read, a file written, a connection, a process
//! started - are what the person who set the variable could do themselves,
//! and they are here in every build. `check_rt.py` holds the feature's
//! shape (9.0, M4; the maintainer's answer of 2026-10-13).

#![cfg_attr(feature = "fault-inject", allow(unsafe_code))]

use crate::confine::{Report, NONE};
use crate::SablineError;

/// The variable the hook is read from.
pub const FAULT_ENV: &str = "SABLINE_FAULT_INJECT";

/// The variable that makes this runtime behave as a kernel with no
/// Landlock would: the ruleset is not built, the layer reports *no: this
/// kernel has no Landlock*, seccomp-bpf is applied as ever, and the level
/// is what such a machine gives. Behind the `fault-inject` feature, so a
/// released binary has no way to stand a layer down.
pub const NO_LANDLOCK_ENV: &str = "SABLINE_FAULT_NO_LANDLOCK";

/// Whether Landlock is to be treated as absent on this run (the leg that
/// has no machine: plan/9.0.md, M4). Always false without the
/// `fault-inject` feature.
#[cfg(feature = "fault-inject")]
pub fn landlock_absent() -> bool {
    std::env::var(NO_LANDLOCK_ENV).is_ok_and(|said| !said.is_empty() && said != "0")
}

/// Whether Landlock is to be treated as absent on this run: never, in a
/// build without the `fault-inject` feature.
#[cfg(not(feature = "fault-inject"))]
pub fn landlock_absent() -> bool {
    false
}

/// What a fault whose calls this build does not carry says, in place of
/// attempting one.
#[cfg(not(feature = "fault-inject"))]
const NOT_BUILT: &str = "this sabline-rt was built without its fault-injection calls (the \
                         fault-inject feature), so the attempt was not made";

/// What one attempt ended as.
pub enum Tried {
    /// Nothing was asked of the hook.
    NotAsked,
    /// The variable names no fault; this is what to say on stderr.
    NoSuchFault(String),
    /// It went through: this is what to say on stderr.
    WentThrough(String),
    /// It was refused by the operating system, and the run ends here.
    Refused(SablineError),
    /// It failed, and not by confinement, which is none: what to say.
    FailedUnconfined(String),
}

/// What the fault reads as in a message, or `None` when it names none.
fn what(kind: &str, rest: &str) -> Option<String> {
    Some(match kind {
        "read" => format!("a read of {rest}"),
        "write" => format!("a write to {rest}"),
        "connect" => format!("a connection to {rest}"),
        "spawn" => "starting a process".to_string(),
        "spawn-breakaway" => "starting a process outside the job".to_string(),
        "signal" => format!("a signal to process {rest}"),
        "mount" => format!("a bind mount {rest}"),
        "unix-socket" => "a Unix-domain socket".to_string(),
        _ => return None,
    })
}

/// Attempt the one effect the environment names, and say what happened.
///
/// `confinement` is what was applied to this process, or `None` when
/// nothing was asked.
pub fn inject(confinement: Option<&Report>) -> Tried {
    let Ok(asked) = std::env::var(FAULT_ENV) else { return Tried::NotAsked };
    if asked.is_empty() {
        return Tried::NotAsked;
    }
    let (kind, rest) = match asked.split_once(':') {
        Some((k, r)) => (k, r),
        None => (asked.as_str(), ""),
    };
    let Some(what) = what(kind, rest) else {
        return Tried::NoSuchFault(format!(
            "sabline: {FAULT_ENV}={asked:?} names no fault; it is read:PATH, write:PATH, \
             connect:HOST:PORT, spawn, spawn-breakaway, signal:PID, mount:SOURCE:TARGET or \
             unix-socket"
        ));
    };
    let level = confinement.map_or(NONE, |c| c.level);
    match attempt(kind, rest) {
        Ok(()) => Tried::WentThrough(format!(
            "sabline: fault injection: {what} succeeded; confinement: {level}"
        )),
        Err(S(Skipped(said))) => Tried::NoSuchFault(said),
        Err(F(Failed(said))) => {
            if level != NONE {
                let layers = confinement.map_or(String::new(), |c| c.layers.join(", "));
                return Tried::Refused(SablineError::with_fixes(
                    "E319",
                    format!(
                        "the runtime itself attempted {what}, outside this run's budget, and \
                         the operating system refused it ({said}); confinement: {level}, by \
                         {layers}"
                    ),
                    0,
                    &[&format!(
                        "this is the fault-injection hook ({FAULT_ENV}); unset it to run the \
                         program"
                    )],
                ));
            }
            Tried::FailedUnconfined(format!(
                "sabline: fault injection: {what} failed, and not by confinement, which is \
                 none: {said}"
            ))
        }
    }
}

/// The attempt failed, and this says how - as Python's
/// `f"{type(e).__name__}: {e}"` says it, since `check_confine.py` reads
/// both runtimes' words.
struct Failed(String);

/// The attempt was not made on this platform, and this says why.
struct Skipped(String);

enum Stop {
    Failed(Failed),
    Skipped(Skipped),
}

use Stop::{Failed as F, Skipped as S};

impl From<Failed> for Stop {
    fn from(f: Failed) -> Stop {
        F(f)
    }
}

impl From<Skipped> for Stop {
    fn from(s: Skipped) -> Stop {
        S(s)
    }
}

fn said(e: &std::io::Error) -> Failed {
    Failed(format!("OSError: {e}"))
}

fn attempt(kind: &str, rest: &str) -> Result<(), Stop> {
    match kind {
        "read" => read(rest),
        "write" => write(rest),
        "connect" => connect(rest),
        "signal" => signal(rest),
        "unix-socket" => unix_socket(),
        "mount" => mount(rest),
        _ => spawn(kind == "spawn-breakaway"),
    }
}

fn read(path: &str) -> Result<(), Stop> {
    use std::io::Read;
    let file = std::fs::File::open(path).map_err(|e| F(said(&e)))?;
    // one byte, or none because the file is empty: either is a read the
    // operating system let through
    let mut one = Vec::new();
    match file.take(1).read_to_end(&mut one) {
        Ok(_) => Ok(()),
        Err(e) => Err(F(said(&e))),
    }
}

fn write(path: &str) -> Result<(), Stop> {
    std::fs::write(path, "written by the fault-injection hook").map_err(|e| F(said(&e)))
}

fn connect(rest: &str) -> Result<(), Stop> {
    let (host, port) = rest
        .rsplit_once(':')
        .ok_or_else(|| F(Failed("ValueError: a connection is named HOST:PORT".to_string())))?;
    let port: u16 = port
        .parse()
        .map_err(|_| F(Failed(format!("ValueError: invalid literal for int(): '{port}'"))))?;
    // the name is resolved first, as `create_connection` resolves it, and a
    // name that cannot be resolved is a failure like any other
    let mut addresses =
        std::net::ToSocketAddrs::to_socket_addrs(&(host, port)).map_err(|e| F(said(&e)))?;
    let address = addresses
        .next()
        .ok_or_else(|| F(Failed(format!("OSError: {host} resolves to no address"))))?;
    std::net::TcpStream::connect_timeout(&address, std::time::Duration::from_secs(5))
        .map(|_| ())
        .map_err(|e| F(said(&e)))
}

fn spawn(breakaway: bool) -> Result<(), Stop> {
    let exe = std::env::current_exe().map_err(|e| F(said(&e)))?;
    let mut command = std::process::Command::new(exe);
    command.arg("--version");
    #[cfg(windows)]
    if breakaway {
        // CREATE_BREAKAWAY_FROM_JOB, which a job that allows no breakaway
        // refuses
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x0100_0000);
    }
    #[cfg(not(windows))]
    if breakaway {
        return Err(S(Skipped(
            "sabline: fault injection: starting a process outside the job is not attempted \
             here, which has no job objects"
                .to_string(),
        )));
    }
    let done = command.output().map_err(|e| F(said(&e)))?;
    if done.status.success() {
        Ok(())
    } else {
        Err(F(Failed(format!(
            "OSError: it started and exited {}",
            done.status.code().unwrap_or(-1)
        ))))
    }
}

#[cfg(all(unix, feature = "fault-inject"))]
mod calls {
    use std::os::raw::{c_char, c_int, c_ulong, c_void};

    extern "C" {
        pub fn socket(domain: c_int, kind: c_int, protocol: c_int) -> c_int;
        pub fn close(fd: c_int) -> c_int;
        pub fn kill(pid: c_int, signal: c_int) -> c_int;
        pub fn mount(
            source: *const c_char,
            target: *const c_char,
            kind: *const c_char,
            flags: c_ulong,
            data: *const c_void,
        ) -> c_int;
    }
}

#[cfg(all(unix, feature = "fault-inject"))]
fn unix_socket() -> Result<(), Stop> {
    const AF_UNIX: std::os::raw::c_int = 1;
    const SOCK_STREAM: std::os::raw::c_int = 1;
    // SAFETY: socket() takes three integers and answers a descriptor or -1;
    // the descriptor is closed at once, here, and nothing else is passed.
    // test: a_unix_socket_is_made_and_closed_or_refused.
    let fd = unsafe { calls::socket(AF_UNIX, SOCK_STREAM, 0) };
    if fd < 0 {
        return Err(F(said(&std::io::Error::last_os_error())));
    }
    // SAFETY: `fd` is the descriptor the call above answered, closed once.
    // test: a_unix_socket_is_made_and_closed_or_refused.
    unsafe { calls::close(fd) };
    Ok(())
}

#[cfg(any(not(unix), not(feature = "fault-inject")))]
fn unix_socket() -> Result<(), Stop> {
    Err(S(Skipped(format!(
        "sabline: fault injection: a Unix-domain socket is not attempted {}",
        not_here("on Windows")
    ))))
}

#[cfg(all(unix, feature = "fault-inject"))]
fn signal(rest: &str) -> Result<(), Stop> {
    let pid: i32 = rest
        .parse()
        .map_err(|_| F(Failed(format!("ValueError: invalid literal for int(): '{rest}'"))))?;
    // SAFETY: kill(pid, 0) takes two integers and sends no signal - it only
    // asks whether this process may signal that one.
    // test: a_signal_names_a_process_and_sends_nothing.
    if unsafe { calls::kill(pid, 0) } != 0 {
        return Err(F(said(&std::io::Error::last_os_error())));
    }
    Ok(())
}

#[cfg(any(not(unix), not(feature = "fault-inject")))]
fn signal(_rest: &str) -> Result<(), Stop> {
    // Windows has no signal to send: os.kill's 0 there is CTRL_C_EVENT,
    // which interrupts the console's every process
    Err(S(Skipped(format!(
        "sabline: fault injection: a signal to another process is not attempted {}",
        not_here("on Windows, which has no such signal")
    ))))
}

#[cfg(all(unix, feature = "fault-inject"))]
fn mount(rest: &str) -> Result<(), Stop> {
    const MS_BIND: std::os::raw::c_ulong = 4096;
    let (source, target) = match rest.split_once(':') {
        Some((s, t)) => (s, t),
        None => (rest, ""),
    };
    let mut from = source.as_bytes().to_vec();
    from.push(0);
    let mut to = target.as_bytes().to_vec();
    to.push(0);
    // SAFETY: `from` and `to` hold their paths with a NUL after them and
    // outlive the call, so both pointers are C strings; the type and the
    // data are null, which MS_BIND takes.
    // test: a_bind_mount_is_refused_and_says_so.
    let done = unsafe {
        calls::mount(
            from.as_ptr() as *const std::os::raw::c_char,
            to.as_ptr() as *const std::os::raw::c_char,
            std::ptr::null(),
            MS_BIND,
            std::ptr::null(),
        )
    };
    if done != 0 {
        return Err(F(said(&std::io::Error::last_os_error())));
    }
    Ok(())
}

#[cfg(any(not(unix), not(feature = "fault-inject")))]
fn mount(_rest: &str) -> Result<(), Stop> {
    Err(S(Skipped(format!(
        "sabline: fault injection: a bind mount is not attempted {}",
        not_here("on Windows")
    ))))
}

/// Why one of the three C calls was not attempted: the platform, or a
/// build that does not carry them.
#[cfg(any(not(unix), not(feature = "fault-inject")))]
fn not_here(platform: &str) -> String {
    #[cfg(feature = "fault-inject")]
    {
        platform.to_string()
    }
    #[cfg(not(feature = "fault-inject"))]
    {
        let _ = platform;
        NOT_BUILT.to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_fault_that_is_not_one_is_said_and_not_attempted() {
        match inject_named("nosuchfault", "", None) {
            Tried::NoSuchFault(said) => assert!(said.contains("names no fault")),
            _ => panic!("a fault nobody named was attempted"),
        }
    }

    /// `inject`, for a fault named here rather than in the environment: a
    /// test cannot set a variable for the process it is in without changing
    /// it for every other test running beside it.
    fn inject_named(kind: &str, rest: &str, confinement: Option<&Report>) -> Tried {
        let Some(what) = what(kind, rest) else {
            return Tried::NoSuchFault(format!("{kind} names no fault"));
        };
        let level = confinement.map_or(NONE, |c| c.level);
        match attempt(kind, rest) {
            Ok(()) => Tried::WentThrough(format!("{what} succeeded; confinement: {level}")),
            Err(S(Skipped(said))) => Tried::NoSuchFault(said),
            Err(F(Failed(said))) if level == NONE => Tried::FailedUnconfined(said),
            Err(F(Failed(said))) => Tried::Refused(SablineError::with_fixes(
                "E319",
                format!("the runtime itself attempted {what}: {said}"),
                0,
                &[],
            )),
        }
    }

    #[test]
    fn a_read_of_a_file_that_is_not_there_fails_and_is_not_confinement() {
        let gone = std::env::temp_dir().join("sabline-no-such-file-at-all");
        let _ = std::fs::remove_file(&gone);
        match inject_named("read", &gone.to_string_lossy(), None) {
            Tried::FailedUnconfined(said) => assert!(said.starts_with("OSError: ")),
            _ => panic!("a file that is not there was read"),
        }
    }

    #[test]
    fn a_read_of_a_file_that_is_there_goes_through_when_nothing_holds_it() {
        // this test's own source, which nothing has been asked to hold
        let here = concat!(env!("CARGO_MANIFEST_DIR"), "/src/confine_fault.rs");
        match inject_named("read", here, None) {
            Tried::WentThrough(said) => assert!(said.contains("succeeded")),
            _ => panic!("a file this process can read was refused"),
        }
    }

    #[test]
    fn a_write_outside_any_grant_goes_through_when_nothing_holds_it() {
        let to = std::env::temp_dir().join(format!("sabline-fault-{}", std::process::id()));
        match inject_named("write", &to.to_string_lossy(), None) {
            Tried::WentThrough(_) => {}
            _ => panic!("a write this process can make was refused"),
        }
        assert_eq!(
            std::fs::read_to_string(&to).unwrap_or_default(),
            "written by the fault-injection hook"
        );
        let _ = std::fs::remove_file(&to);
    }

    #[test]
    fn a_connection_that_names_no_port_is_a_failure_and_not_a_crash() {
        match inject_named("connect", "nowhere", None) {
            Tried::FailedUnconfined(said) => assert!(said.contains("HOST:PORT")),
            _ => panic!("a connection with no port was attempted"),
        }
    }

    #[test]
    fn starting_a_process_goes_through_when_no_job_holds_it() {
        // The process started is this binary with --version, as the package
        // starts `python -c pass`: something that ends at once and does
        // nothing. Here the binary is the test harness, which does not take
        // --version and exits 101, so what is held is that a process was
        // started at all - "it started and exited N" is the hook's own
        // words for that. A job object that refuses to start one is
        // check_confine.py's case, in a process the job holds.
        match inject_named("spawn", "", None) {
            Tried::WentThrough(_) => {}
            Tried::FailedUnconfined(said) => assert!(
                said.contains("it started and exited"),
                "a process could not be started at all: {said}"
            ),
            _ => panic!("starting a process was not attempted"),
        }
    }

    #[cfg(all(unix, feature = "fault-inject"))]
    #[test]
    fn a_unix_socket_is_made_and_closed_or_refused() {
        match inject_named("unix-socket", "", None) {
            Tried::WentThrough(_) => {}
            Tried::FailedUnconfined(said) => assert!(said.starts_with("OSError: ")),
            _ => panic!("a Unix socket was neither made nor refused"),
        }
    }

    #[cfg(all(unix, feature = "fault-inject"))]
    #[test]
    fn a_signal_names_a_process_and_sends_nothing() {
        let me = std::process::id() as i32;
        match inject_named("signal", &me.to_string(), None) {
            Tried::WentThrough(_) => {}
            Tried::FailedUnconfined(said) => assert!(said.starts_with("OSError: ")),
            _ => panic!("a signal to this process was neither allowed nor refused"),
        }
        // and a pid that is not a number is a failure, not a crash
        match inject_named("signal", "not-a-pid", None) {
            Tried::FailedUnconfined(said) => assert!(said.contains("invalid literal")),
            _ => panic!("a pid that is not a number was signalled"),
        }
    }

    #[cfg(all(unix, feature = "fault-inject"))]
    #[test]
    fn a_bind_mount_is_refused_and_says_so() {
        // an ordinary user may not mount anything, confined or not
        match inject_named("mount", "/tmp:/tmp", None) {
            Tried::FailedUnconfined(said) => assert!(said.starts_with("OSError: ")),
            _ => panic!("an ordinary user mounted something"),
        }
    }

    #[cfg(any(not(unix), not(feature = "fault-inject")))]
    #[test]
    fn what_this_build_cannot_attempt_is_said_and_not_pretended() {
        for kind in ["signal", "unix-socket", "mount"] {
            match inject_named(kind, "1", None) {
                Tried::NoSuchFault(said) => assert!(said.contains("not attempted")),
                _ => panic!("{kind} was attempted on Windows"),
            }
        }
    }
}
