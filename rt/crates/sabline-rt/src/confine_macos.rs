//! macOS's layer (9.0, M4): a **sandbox profile**, in the language
//! `sandbox-exec` reads, applied to this process with `sandbox_init`.
//!
//! This is `sabline/confine.py`'s `_apply_macos`, ported, and it holds the
//! same three things and leaves the same one out: writes, the network and
//! starting a process are held; reads are refused under the home directory
//! and `/Volumes` and nowhere else, so a read grant is `partly` held and a
//! run on macOS is `partial` at best. [`profile`] is pure and the
//! agreement gate compares it with the package's for a fixed set of
//! policies, paths and all, because a profile is a text and a text is
//! comparable.
//!
//! **The later of two rules that match wins**, which is why each denial
//! follows `allow default` and what is allowed again follows its denial.
//! The one subtlety is the read denial: a later `allow file-read*` does
//! *not* take back a `deny file-read-data`, because the rule for the one
//! operation beats the rule for the family whichever comes last - so what
//! stays readable is written into the denial itself, as `require-not`.
//!
//! Apple has deprecated both `sandbox-exec` and `sandbox_init`. The layer
//! says so in every report it makes, as the package's does, and the day it
//! stops working the level says `none` with the reason the system gave.

#![allow(unsafe_code)] // sandbox_init is a C entry point; rt/README.md's rule

#[cfg(target_os = "macos")]
use std::os::raw::{c_char, c_int};

#[cfg(target_os = "macos")]
use crate::confine::{any_net, Held, Report};
use crate::confine::{existing, granted, nearest_directory, no_net, spawn, Extras};
use crate::json::Json;

/// The layer name a receipt writes for the sandbox profile.
pub const MAC_SANDBOX: &str = "sandbox-profile";

/// What every report on macOS says, whatever it held.
pub const DEPRECATED: &str = "sandbox profiles are deprecated by Apple (sandbox-exec and \
                              sandbox_init both), and may stop working in a later macOS";

/// One text, as the profile language quotes it.
fn quoted(text: &str) -> String {
    format!("\"{}\"", text.replace('\\', "\\\\").replace('"', "\\\""))
}

/// The sandbox profile of a policy, in the language `sandbox-exec` reads.
///
/// `home`, `cwd` and `runtime_reads` are the machine's answers, handed in
/// rather than read here, so that the profile is a pure function of them
/// and the agreement gate can compare it against the package's for the
/// same inputs on any platform.
pub fn profile(
    policy: &Json,
    extras: &Extras,
    home: &str,
    cwd: &str,
    runtime_reads: &[String],
) -> String {
    let mut lines = vec!["(version 1)".to_string(), "(allow default)".to_string()];
    if no_net(policy) {
        lines.push("(deny network*)".to_string());
    }
    if !spawn(policy) {
        lines.push("(deny process-fork)".to_string());
        lines.push("(deny process-exec)".to_string());
    }
    if let Some(writes) = granted(policy, "fs_write") {
        let mut places = vec![
            r#"(literal "/dev/null")"#.to_string(),
            r#"(literal "/dev/dtracehelper")"#.to_string(),
        ];
        let asked: Vec<String> = writes
            .iter()
            .chain(extras.writes.iter())
            .chain(extras.temp.iter())
            .cloned()
            .collect();
        for grant in &asked {
            if let (Some(place), _) = nearest_directory(grant) {
                places.push(format!("(subpath {})", quoted(&place)));
            }
        }
        lines.push("(deny file-write*)".to_string());
        lines.push(format!("(allow file-write* {})", places.join(" ")));
    }
    if let Some(reads) = granted(policy, "fs_read") {
        if !extras.read_any {
            // a read grant is named whether or not it is there yet: a
            // program may read back what it has just written
            let mut allowed: Vec<String> = runtime_reads.to_vec();
            let also: Vec<String> =
                extras.reads.iter().chain(extras.temp.iter()).cloned().collect();
            allowed.extend(existing(&also));
            allowed.extend(reads.iter().map(|g| crate::pypath::realpath(g)));
            // getcwd() opens the working directory, and failing that reads
            // each directory above it, so those directories themselves -
            // the names in them, not the files - stay readable: a relative
            // path cannot be resolved otherwise
            let mut above: Vec<String> = Vec::new();
            let mut step = crate::pypath::realpath(cwd);
            while !above.contains(&step) {
                above.push(step.clone());
                step = crate::pypath::os_path::dirname(&step);
            }
            let mut kept: Vec<String> = allowed
                .iter()
                .map(|p| {
                    let kind =
                        if std::path::Path::new(p).is_file() { "literal" } else { "subpath" };
                    format!("(require-not ({kind} {}))", quoted(p))
                })
                .collect();
            kept.extend(
                above.iter().map(|p| format!("(require-not (literal {}))", quoted(p))),
            );
            lines.push(format!(
                "(deny file-read-data (require-all (require-any (subpath {}) (subpath \
                 \"/Volumes\")) {}))",
                quoted(home),
                kept.join(" ")
            ));
        }
    }
    lines.join("\n")
}

/// What sabline-rt itself must be able to read on macOS once the policy is
/// applied: the same four names Linux needs, less the ones macOS has no
/// `/proc` for.
pub fn runtime_reads(_net: bool) -> Vec<String> {
    existing(&["/dev/null".to_string(), "/dev/urandom".to_string(), "/dev/random".to_string()])
}

/// The home directory, as `os.path.realpath(os.path.expanduser("~"))`
/// gives it.
pub fn home() -> String {
    let said = std::env::var("HOME").unwrap_or_default();
    crate::pypath::realpath(if said.is_empty() { "/" } else { &said })
}

#[cfg(target_os = "macos")]
extern "C" {
    fn sandbox_init(profile: *const c_char, flags: u64, errorbuf: *mut *mut c_char) -> c_int;
}

/// Apply the profile to this process. `None`, or why it could not be.
#[cfg(target_os = "macos")]
fn sandbox(text: &str) -> Option<String> {
    let mut bytes = text.as_bytes().to_vec();
    bytes.push(0);
    let mut error: *mut c_char = std::ptr::null_mut();
    // SAFETY: `bytes` is the profile with a NUL after it and outlives the
    // call, so the first argument is a C string; `error` is a live pointer
    // the call may set to a message it owns, which is only read when the
    // call failed and is never freed - the process is about to run one
    // program and end.
    // test: a_profile_that_is_not_a_profile_is_a_reason_and_not_a_crash.
    let done = unsafe { sandbox_init(bytes.as_ptr() as *const c_char, 0, &mut error) };
    if done == 0 {
        return None;
    }
    let said = if error.is_null() {
        "failed".to_string()
    } else {
        // SAFETY: `error` was set by sandbox_init to a NUL-terminated
        // message it owns; it is read once, here, before anything else runs.
        // test: a_profile_that_is_not_a_profile_is_a_reason_and_not_a_crash.
        unsafe { std::ffi::CStr::from_ptr(error) }.to_string_lossy().into_owned()
    };
    Some(format!("sandbox_init: {said}"))
}

/// What this system offers, and what.
pub fn supported() -> (bool, String) {
    (true, "a sandbox profile (sandbox_init; deprecated by Apple)".to_string())
}

/// Ask the sandbox to hold this process to `policy`, and say what it did.
#[cfg(target_os = "macos")]
pub fn apply(policy: &Json, extras: &Extras) -> Report {
    use crate::confine::judge;

    let text = profile(
        policy,
        extras,
        &home(),
        &crate::pypath::getcwd(),
        &runtime_reads(!no_net(policy)),
    );
    let mut held: Vec<(&'static str, Held)> = Vec::new();
    if let Some(why) = sandbox(&text) {
        for what in crate::confine::restricted(policy) {
            held.push((what, Held::No(why.clone())));
        }
        return judge(policy, &held, &[], &[]);
    }
    if granted(policy, "fs_read").is_some() {
        held.push((
            "fs_read",
            if extras.read_any {
                Held::No("this pool has no import_root, so reads are not held".to_string())
            } else {
                Held::Partly(
                    "reads are refused under the home directory and /Volumes only, not \
                     held to exactly the grants"
                        .to_string(),
                )
            },
        ));
    }
    if let Some(writes) = granted(policy, "fs_write") {
        let wider: Vec<&String> = writes.iter().filter(|g| nearest_directory(g).1).collect();
        held.push((
            "fs_write",
            match wider.first() {
                None => Held::Yes,
                Some(g) => Held::Partly(format!(
                    "{g} does not exist yet, so writes are held to the nearest directory \
                     that does"
                )),
            },
        ));
    }
    if no_net(policy) {
        held.push(("net", Held::Yes));
    } else if !any_net(policy) {
        held.push((
            "net",
            Held::No(
                "the profile allows the network; the host is held by the language alone"
                    .to_string(),
            ),
        ));
    }
    if !spawn(policy) {
        held.push(("spawn", Held::Yes));
    }
    judge(policy, &held, &[MAC_SANDBOX.to_string()], &[DEPRECATED.to_string()])
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::budget::budget_from;
    use crate::confine::os_policy;

    fn policy_of(allow: &str) -> Json {
        os_policy(&budget_from(Some(allow), None).expect("a budget"), true, false)
    }

    fn profile_of(allow: &str) -> String {
        profile(&policy_of(allow), &Extras::default(), "/Users/x", "/Users/x/work", &[])
    }

    #[test]
    fn io_denies_the_network_processes_and_every_write() {
        let text = profile_of("io");
        assert!(text.starts_with("(version 1)\n(allow default)\n"));
        assert!(text.contains("(deny network*)"));
        assert!(text.contains("(deny process-fork)") && text.contains("(deny process-exec)"));
        assert!(text.contains("(deny file-write*)"));
        // and holds reads under the home directory and /Volumes, keeping
        // the working directory and each directory above it readable. The
        // profile resolves a path with `os.path`, as the package's does, so
        // what those names resolve to is this platform's answer - which is
        // why the gate compares the two runtimes' profiles rather than this
        // test comparing one against a path written out by hand.
        assert!(text.contains(r#"(subpath "/Users/x")"#));
        assert!(text.contains(r#"(subpath "/Volumes")"#));
        let mut step = crate::pypath::realpath("/Users/x/work");
        let mut seen = Vec::new();
        while !seen.contains(&step) {
            assert!(
                text.contains(&format!("(require-not (literal {}))", quoted(&step))),
                "{step} is not kept readable"
            );
            seen.push(step.clone());
            step = crate::pypath::os_path::dirname(&step);
        }
        assert!(seen.len() > 1, "the walk above the working directory stopped at once");
    }

    #[test]
    fn a_net_grant_leaves_the_network_alone() {
        assert!(!profile_of("net:a.example").contains("(deny network*)"));
        assert!(!profile_of("net").contains("(deny network*)"));
    }

    #[test]
    fn plain_fs_denies_no_read_and_no_write() {
        let text = profile_of("fs");
        assert!(!text.contains("file-write*"));
        assert!(!text.contains("file-read-data"));
    }

    #[test]
    fn a_pool_with_no_import_root_holds_no_read() {
        let extras = Extras { read_any: true, ..Extras::default() };
        let text = profile(&policy_of("io"), &extras, "/Users/x", "/Users/x", &[]);
        assert!(!text.contains("file-read-data"));
        assert!(text.contains("(deny file-write*)"));
    }

    #[test]
    fn a_quote_in_a_path_cannot_end_the_text_it_is_in() {
        assert_eq!(quoted(r#"/a "b"/c"#), r#""/a \"b\"/c""#);
        assert_eq!(quoted(r"/a\b"), r#""/a\\b""#);
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn a_profile_that_is_not_a_profile_is_a_reason_and_not_a_crash() {
        // the one call this module makes, asked something it must refuse:
        // the answer is a sentence, and this process is not held by it
        let why = sandbox("(this is not a profile");
        assert!(why.is_some(), "a profile that cannot be read was accepted");
        assert!(why.unwrap().starts_with("sandbox_init: "));
        assert!(std::fs::metadata("/dev/null").is_ok());
    }
}
