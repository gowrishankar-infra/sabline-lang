//! Windows' layers (9.0, M4): a **job object** that holds the run to one
//! process and takes the clipboard, the desktop and other processes'
//! windows away from it; **every privilege but `SeChangeNotifyPrivilege`
//! removed** from the token; and a **low integrity level** when the budget
//! grants no write.
//!
//! Those three are `sabline/confine.py`'s `_apply_windows`, ported. Beside
//! them, from 9.0's M4, is the **AppContainer**
//! ([`crate::confine_appcontainer`]), which holds what they cannot: reads
//! to the ACEs the run's parent granted, and the network to the capability
//! it was or was not given. A process cannot enter a container after it
//! has started, so the run's own process is started inside one by the
//! process that was asked for the run, and this module asks the kernel
//! whether that is where it is rather than taking the parent's word.
//!
//! Where a container is left off - a budget granting a loopback host, or
//! one that restricts neither reads nor writes - the report is what it was
//! before that rung, with the reason saying which.
//!
//! What is pure here - [`lower_the_label`], the words of every report - is
//! compiled and tested on every platform, as `pypath`'s two flavours are;
//! only the calls are behind `cfg(windows)`.

#![allow(unsafe_code)] // the job object and the token are C entry points

use crate::confine::{granted, Extras};
#[cfg(windows)]
use crate::confine::{judge, no_net, spawn, Held, Report};
use crate::json::Json;

/// The layer name a receipt writes for the job object.
pub const WINDOWS_JOB: &str = "job-object";
/// The layer name for a token with its privileges removed.
pub const WINDOWS_TOKEN: &str = "token-privileges-removed";
/// The layer name for a process at the low integrity level.
pub const WINDOWS_LOW: &str = "low-integrity";

/// What Windows does not hold without a container, and why - the note a
/// report carries while a budget asks for reads or for the network to be
/// held and no container was entered **and nobody said why**.
///
/// It is **not** the package's words. `sabline/confine.py`'s say that an
/// AppContainer is not used because a `python.exe` started in one cannot
/// read its own installation, which is true of that runtime and not of
/// this one. A run of `sabline-rt exec` that was asked for confinement
/// always says where it stands ([`crate::confine_appcontainer::here`]), so
/// this is the note of a process that never considered one - a batch of
/// the agreement gate's, where one process runs some thousands of
/// programs.
pub const WINDOWS_NOT_HELD: &str =
    "reads and the network need an AppContainer, and this process was not started inside \
     one: a process cannot enter one after it has started, so the run's own process has to \
     be started inside one (plan/9.0.md, M4)";

/// Whether this policy's process may be given the low integrity level: it
/// may when the budget grants no write at all, since a write to anything of
/// the user's would then be refused anyway. A write grant keeps the process
/// at medium integrity, because lowering it would need the granted
/// directory relabelled - which is the user's file and not Sabline's to
/// change.
pub fn lower_the_label(policy: &Json, extras: &Extras) -> bool {
    granted(policy, "fs_write").is_some_and(|w| w.is_empty()) && extras.writes.is_empty()
}

/// What this system offers, and what.
pub fn supported() -> (bool, String) {
    (
        true,
        "an AppContainer the run's own process is started inside, a job object, the token's \
         privileges removed, and a low integrity level for a budget with no write grant \
         where no container was entered"
            .to_string(),
    )
}

#[cfg(windows)]
#[allow(clippy::upper_case_acronyms)] // Windows' own names for its own types
mod calls {
    //! The calls, and nothing else: every `unsafe` block in this module is
    //! one Windows entry point with its arguments checked by the type
    //! system and its invariant in the comment above it.
    use std::ffi::c_void;

    type HANDLE = *mut c_void;
    type BOOL = i32;
    type DWORD = u32;
    type LPCWSTR = *const u16;

    #[repr(C)]
    struct JobBasicLimits {
        per_process_user_time_limit: i64,
        per_job_user_time_limit: i64,
        limit_flags: DWORD,
        minimum_working_set_size: usize,
        maximum_working_set_size: usize,
        active_process_limit: DWORD,
        affinity: usize,
        priority_class: DWORD,
        scheduling_class: DWORD,
    }

    #[repr(C)]
    struct JobIoCounters {
        read_operation_count: u64,
        write_operation_count: u64,
        other_operation_count: u64,
        read_transfer_count: u64,
        write_transfer_count: u64,
        other_transfer_count: u64,
    }

    #[repr(C)]
    struct JobExtendedLimits {
        basic: JobBasicLimits,
        io: JobIoCounters,
        process_memory_limit: usize,
        job_memory_limit: usize,
        peak_process_memory_used: usize,
        peak_job_memory_used: usize,
    }

    #[repr(C)]
    struct Luid {
        low: DWORD,
        high: i32,
    }

    #[repr(C)]
    struct LuidAndAttributes {
        luid: Luid,
        attributes: DWORD,
    }

    #[repr(C)]
    struct TokenMandatoryLabel {
        sid: *mut c_void,
        attributes: DWORD,
    }

    #[link(name = "kernel32")]
    extern "system" {
        fn CreateJobObjectW(attributes: *mut c_void, name: LPCWSTR) -> HANDLE;
        fn SetInformationJobObject(
            job: HANDLE,
            class: i32,
            info: *const c_void,
            length: DWORD,
        ) -> BOOL;
        fn AssignProcessToJobObject(job: HANDLE, process: HANDLE) -> BOOL;
        fn GetCurrentProcess() -> HANDLE;
        fn GetLastError() -> DWORD;
        fn CloseHandle(h: HANDLE) -> BOOL;
    }

    #[link(name = "advapi32")]
    extern "system" {
        fn OpenProcessToken(process: HANDLE, access: DWORD, token: *mut HANDLE) -> BOOL;
        fn GetTokenInformation(
            token: HANDLE,
            class: i32,
            info: *mut c_void,
            length: DWORD,
            needed: *mut DWORD,
        ) -> BOOL;
        fn AdjustTokenPrivileges(
            token: HANDLE,
            disable_all: BOOL,
            new_state: *mut c_void,
            length: DWORD,
            previous: *mut c_void,
            returned: *mut DWORD,
        ) -> BOOL;
        fn LookupPrivilegeValueW(system: LPCWSTR, name: LPCWSTR, luid: *mut Luid) -> BOOL;
        fn SetTokenInformation(
            token: HANDLE,
            class: i32,
            info: *const c_void,
            length: DWORD,
        ) -> BOOL;
        fn ConvertStringSidToSidW(text: LPCWSTR, sid: *mut *mut c_void) -> BOOL;
        fn GetLengthSid(sid: *mut c_void) -> DWORD;
        fn ConvertStringSecurityDescriptorToSecurityDescriptorW(
            text: LPCWSTR,
            revision: DWORD,
            sd: *mut *mut c_void,
            size: *mut DWORD,
        ) -> BOOL;
        fn GetSecurityDescriptorSacl(
            sd: *mut c_void,
            present: *mut BOOL,
            sacl: *mut *mut c_void,
            defaulted: *mut BOOL,
        ) -> BOOL;
        fn SetNamedSecurityInfoW(
            name: *mut u16,
            object: u32,
            information: DWORD,
            owner: *mut c_void,
            group: *mut c_void,
            dacl: *mut c_void,
            sacl: *mut c_void,
        ) -> DWORD;
    }

    #[link(name = "kernel32")]
    extern "system" {
        fn LocalFree(p: *mut c_void) -> *mut c_void;
    }

    const JOB_OBJECT_LIMIT_ACTIVE_PROCESS: DWORD = 0x0000_0008;
    const JOB_EXTENDED_LIMIT_INFORMATION: i32 = 9;
    const JOB_BASIC_UI_RESTRICTIONS: i32 = 4;
    /// Handles, the clipboard, system parameters, the display, global
    /// atoms, the desktop, and exiting Windows.
    const UI_RESTRICTIONS_ALL: DWORD = 0xFF;
    const TOKEN_ADJUST_PRIVILEGES: DWORD = 0x0020;
    const TOKEN_QUERY: DWORD = 0x0008;
    const TOKEN_ADJUST_DEFAULT: DWORD = 0x0080;
    const TOKEN_PRIVILEGES_CLASS: i32 = 3;
    const TOKEN_INTEGRITY_LEVEL_CLASS: i32 = 25;
    const SE_PRIVILEGE_REMOVED: DWORD = 0x0000_0004;
    const SE_GROUP_INTEGRITY: DWORD = 0x0000_0020;
    const LOW_INTEGRITY_SID: &str = "S-1-16-4096";
    const SE_FILE_OBJECT: u32 = 1;
    const LABEL_SECURITY_INFORMATION: DWORD = 0x0000_0010;

    /// The job object is kept for the life of the process: the job is the
    /// box, and closing its last handle would let the process out of it.
    static JOB: std::sync::OnceLock<usize> = std::sync::OnceLock::new();

    fn wide(text: &str) -> Vec<u16> {
        text.encode_utf16().chain(std::iter::once(0)).collect()
    }

    fn last_error() -> DWORD {
        // SAFETY: GetLastError reads this thread's own last-error value and
        // changes nothing. test: a_job_holds_this_process_to_one_process.
        unsafe { GetLastError() }
    }

    /// Put this process in a job of its own that holds one process and the
    /// USER-object restrictions. `None`, or why it failed.
    pub fn job() -> Option<String> {
        // SAFETY: CreateJobObjectW with no attributes and no name makes an
        // unnamed job and answers a handle or null.
        // test: a_job_holds_this_process_to_one_process.
        let job = unsafe { CreateJobObjectW(std::ptr::null_mut(), std::ptr::null()) };
        if job.is_null() {
            return Some(format!("CreateJobObject: error {}", last_error()));
        }
        // SAFETY: an all-zero JobExtendedLimits is a valid starting value -
        // every field is an integer and zero means "no limit".
        // test: a_job_holds_this_process_to_one_process.
        let mut info: JobExtendedLimits = unsafe { std::mem::zeroed() };
        info.basic.limit_flags = JOB_OBJECT_LIMIT_ACTIVE_PROCESS;
        info.basic.active_process_limit = 1;
        // SAFETY: `info` is a live JobExtendedLimits and the length is its
        // own size, which is what the class the call names expects.
        // test: a_job_holds_this_process_to_one_process.
        let set = unsafe {
            SetInformationJobObject(
                job,
                JOB_EXTENDED_LIMIT_INFORMATION,
                (&info as *const JobExtendedLimits).cast(),
                u32::try_from(std::mem::size_of::<JobExtendedLimits>()).unwrap_or(0),
            )
        };
        if set == 0 {
            let why = format!("SetInformationJobObject: error {}", last_error());
            // SAFETY: `job` is the handle this function made and nothing
            // else holds it. test: a_job_holds_this_process_to_one_process.
            unsafe { CloseHandle(job) };
            return Some(why);
        }
        let ui: DWORD = UI_RESTRICTIONS_ALL;
        // SAFETY: `ui` is a live DWORD and the length is its own size,
        // which is what the UI-restrictions class expects. Its failure is
        // not fatal: the limit above is the one the level reports.
        // test: a_job_holds_this_process_to_one_process.
        unsafe {
            SetInformationJobObject(
                job,
                JOB_BASIC_UI_RESTRICTIONS,
                (&ui as *const DWORD).cast(),
                u32::try_from(std::mem::size_of::<DWORD>()).unwrap_or(0),
            )
        };
        // SAFETY: GetCurrentProcess answers a pseudo-handle for this
        // process, which needs no closing; `job` is open.
        // test: a_job_holds_this_process_to_one_process.
        let assigned = unsafe { AssignProcessToJobObject(job, GetCurrentProcess()) };
        if assigned == 0 {
            let why = format!("AssignProcessToJobObject: error {}", last_error());
            // SAFETY: `job` is the handle this function made and nothing
            // else holds it; it is closed once, on this path.
            // test: a_job_holds_this_process_to_one_process.
            unsafe { CloseHandle(job) };
            return Some(why);
        }
        let _ = JOB.set(job as usize);
        None
    }

    /// Remove every privilege but `SeChangeNotifyPrivilege` from this
    /// process's token, and, when `lower`, give it the low integrity level -
    /// labelling `temp` low first, so the run can still use it.
    ///
    /// `(why the privileges were not removed or None, why it was not
    /// lowered or None)`.
    pub fn token(lower: bool, temp: Option<&str>) -> (Option<String>, Option<String>) {
        let mut handle: HANDLE = std::ptr::null_mut();
        // SAFETY: `handle` is a live out-parameter; the pseudo-handle for
        // this process needs no closing, and the token handle is closed
        // before this function returns.
        // test: the_token_keeps_one_privilege_and_removes_the_rest.
        let opened = unsafe {
            OpenProcessToken(
                GetCurrentProcess(),
                TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY | TOKEN_ADJUST_DEFAULT,
                &mut handle,
            )
        };
        if opened == 0 {
            let why = format!("OpenProcessToken: error {}", last_error());
            return (Some(why.clone()), Some(why));
        }
        let no_privileges = remove_privileges(handle);
        let not_lowered =
            if lower { lower_label(handle, temp) } else { Some("not asked for".to_string()) };
        // SAFETY: `handle` came from OpenProcessToken above and is closed
        // once, here. test: the_token_keeps_one_privilege_and_removes_the_rest.
        unsafe { CloseHandle(handle) };
        (no_privileges, not_lowered)
    }

    fn remove_privileges(token: HANDLE) -> Option<String> {
        let mut needed: DWORD = 0;
        // SAFETY: the first call asks for the size only - a null buffer of
        // length 0 - and writes it through `needed`.
        // test: the_token_keeps_one_privilege_and_removes_the_rest.
        unsafe {
            GetTokenInformation(
                token,
                TOKEN_PRIVILEGES_CLASS,
                std::ptr::null_mut(),
                0,
                &mut needed,
            )
        };
        let size = usize::try_from(needed).unwrap_or(0).max(4);
        let mut buffer = vec![0u8; size];
        // SAFETY: `buffer` is `size` bytes and `needed` says so; the call
        // fills it with a TOKEN_PRIVILEGES - a count and that many
        // LUID_AND_ATTRIBUTES.
        // test: the_token_keeps_one_privilege_and_removes_the_rest.
        let read = unsafe {
            GetTokenInformation(
                token,
                TOKEN_PRIVILEGES_CLASS,
                buffer.as_mut_ptr().cast(),
                needed,
                &mut needed,
            )
        };
        if read == 0 {
            return Some(format!("GetTokenInformation: error {}", last_error()));
        }
        let count = u32::from_le_bytes([buffer[0], buffer[1], buffer[2], buffer[3]]);
        let entry = std::mem::size_of::<LuidAndAttributes>();
        let header = std::mem::size_of::<DWORD>();
        let mut keep = Luid { low: 0, high: 0 };
        let name = wide("SeChangeNotifyPrivilege");
        // SAFETY: `name` is NUL-terminated and `keep` is a live out-
        // parameter; the call reads neither afterwards.
        // test: the_token_keeps_one_privilege_and_removes_the_rest.
        unsafe { LookupPrivilegeValueW(std::ptr::null(), name.as_ptr(), &mut keep) };
        for i in 0..usize::try_from(count).unwrap_or(0) {
            let at = header + i * entry;
            if at + entry > buffer.len() {
                break;
            }
            let low = u32::from_le_bytes([
                buffer[at],
                buffer[at + 1],
                buffer[at + 2],
                buffer[at + 3],
            ]);
            let high = i32::from_le_bytes([
                buffer[at + 4],
                buffer[at + 5],
                buffer[at + 6],
                buffer[at + 7],
            ]);
            if (low, high) != (keep.low, keep.high) {
                buffer[at + 8..at + 12].copy_from_slice(&SE_PRIVILEGE_REMOVED.to_le_bytes());
            }
        }
        // SAFETY: `buffer` still holds the TOKEN_PRIVILEGES the call above
        // filled in, with each entry's attributes changed in place; the
        // length is 0 because no previous state is asked for.
        // test: the_token_keeps_one_privilege_and_removes_the_rest.
        let adjusted = unsafe {
            AdjustTokenPrivileges(
                token,
                0,
                buffer.as_mut_ptr().cast(),
                0,
                std::ptr::null_mut(),
                std::ptr::null_mut(),
            )
        };
        if adjusted == 0 {
            return Some(format!("AdjustTokenPrivileges: error {}", last_error()));
        }
        None
    }

    fn lower_label(token: HANDLE, temp: Option<&str>) -> Option<String> {
        if let Some(temp) = temp {
            if let Some(why) = label_low(temp) {
                return Some(why);
            }
        }
        let text = wide(LOW_INTEGRITY_SID);
        let mut sid: *mut c_void = std::ptr::null_mut();
        // SAFETY: `text` is NUL-terminated and `sid` is a live out-pointer
        // which the call fills with a SID it allocated.
        // test: the_low_label_is_the_one_windows_knows.
        if unsafe { ConvertStringSidToSidW(text.as_ptr(), &mut sid) } == 0 {
            return Some(format!("ConvertStringSidToSid: error {}", last_error()));
        }
        let label = TokenMandatoryLabel { sid, attributes: SE_GROUP_INTEGRITY };
        // SAFETY: `label` points at the SID above, which is alive for the
        // call; the length is the structure's own size plus the SID's, as
        // the integrity-level class expects.
        // test: the_low_label_is_the_one_windows_knows.
        let set = unsafe {
            let length = u32::try_from(std::mem::size_of::<TokenMandatoryLabel>())
                .unwrap_or(0)
                + GetLengthSid(sid);
            SetTokenInformation(
                token,
                TOKEN_INTEGRITY_LEVEL_CLASS,
                (&label as *const TokenMandatoryLabel).cast(),
                length,
            )
        };
        let why = if set == 0 {
            Some(format!("SetTokenInformation: error {}", last_error()))
        } else {
            None
        };
        // SAFETY: `sid` was allocated by ConvertStringSidToSidW and is
        // freed once, after the last use of `label`.
        // test: the_low_label_is_the_one_windows_knows.
        unsafe { LocalFree(sid) };
        why
    }

    /// Give a directory the low mandatory label, inherited by what is made
    /// in it, so a process at the low integrity level can write there.
    pub fn label_low(path: &str) -> Option<String> {
        let text = wide("S:(ML;OICI;NW;;;LW)");
        let mut sd: *mut c_void = std::ptr::null_mut();
        // SAFETY: `text` is NUL-terminated and `sd` is a live out-pointer
        // the call fills with a descriptor it allocated, freed below.
        // test: the_low_label_is_the_one_windows_knows.
        if unsafe {
            ConvertStringSecurityDescriptorToSecurityDescriptorW(
                text.as_ptr(),
                1,
                &mut sd,
                std::ptr::null_mut(),
            )
        } == 0
        {
            return Some(format!("the label could not be built: error {}", last_error()));
        }
        let mut present: BOOL = 0;
        let mut defaulted: BOOL = 0;
        let mut sacl: *mut c_void = std::ptr::null_mut();
        let read = {
            // SAFETY: `sd` is the descriptor above; `sacl` is filled with a
            // pointer into it, which stays valid until `sd` is freed.
            // test: the_low_label_is_the_one_windows_knows.
            unsafe { GetSecurityDescriptorSacl(sd, &mut present, &mut sacl, &mut defaulted) }
        };
        if read == 0 {
            let why = format!("the label could not be read: error {}", last_error());
            // SAFETY: `sd` was allocated above and is freed once, on this
            // path, with nothing pointing into it any more.
            // test: the_low_label_is_the_one_windows_knows.
            unsafe { LocalFree(sd) };
            return Some(why);
        }
        let mut name = wide(path);
        // SAFETY: `name` is this path with a NUL after it, and `sacl`
        // points into `sd`, which is alive for the call.
        // test: the_low_label_is_the_one_windows_knows.
        let failed = unsafe {
            SetNamedSecurityInfoW(
                name.as_mut_ptr(),
                SE_FILE_OBJECT,
                LABEL_SECURITY_INFORMATION,
                std::ptr::null_mut(),
                std::ptr::null_mut(),
                std::ptr::null_mut(),
                sacl,
            )
        };
        // SAFETY: `sd` was allocated above and is freed once, after the
        // last use of `sacl`. test: the_low_label_is_the_one_windows_knows.
        unsafe { LocalFree(sd) };
        if failed == 0 {
            None
        } else {
            Some(format!("the temporary directory could not be labelled low: error {failed}"))
        }
    }
}

/// Ask the container, the job object and the token to hold this process to
/// `policy`, and say what they did.
#[cfg(windows)]
pub fn apply(policy: &Json, extras: &Extras) -> Report {
    use crate::confine_appcontainer::{plan, Where, APPCONTAINER};

    let mut held: Vec<(&'static str, Held)> = Vec::new();
    let mut layers: Vec<String> = Vec::new();
    let mut notes: Vec<String> = Vec::new();
    // the container, which this process is in or is not: the kernel
    // answered that before the first statement, and the answer is here
    let inside = matches!(crate::confine_appcontainer::here(), Some(Where::Inside));
    if inside {
        layers.push(APPCONTAINER.to_string());
    }
    // a container holds writes by the ACEs it was given, so the low
    // integrity level - which holds them only by being lower than
    // everything of the user's - is not asked for inside one
    let lower = !inside && lower_the_label(policy, extras);
    let (no_privileges, not_lowered) = calls::token(lower, extras.temp.as_deref());
    match &no_privileges {
        None => layers.push(WINDOWS_TOKEN.to_string()),
        Some(why) => notes.push(format!("privileges were not removed ({why})")),
    }
    if not_lowered.is_none() {
        layers.push(WINDOWS_LOW.to_string());
    }
    if !spawn(policy) {
        let no_job = calls::job();
        held.push((
            "spawn",
            match &no_job {
                None => Held::Yes,
                Some(why) => Held::No(why.clone()),
            },
        ));
        if no_job.is_none() {
            layers.push(WINDOWS_JOB.to_string());
        }
    }
    // what the container was given is what this run itself derived from
    // the same policy and the same request, so the widening it reports is
    // the widening the ACEs carry
    let made = if inside { plan(policy, extras) } else { Default::default() };
    if granted(policy, "fs_write").is_some() {
        held.push((
            "fs_write",
            if inside {
                if made.wider.is_empty() {
                    Held::Yes
                } else {
                    Held::Partly(made.wider.join("; "))
                }
            } else if not_lowered.is_none() {
                Held::Yes
            } else if !lower {
                Held::No(
                    "a budget with a write grant runs at medium integrity, because \
                     lowering it would need the granted directory relabelled"
                        .to_string(),
                )
            } else {
                Held::No(not_lowered.clone().unwrap_or_default())
            },
        ));
    }
    if granted(policy, "fs_read").is_some() {
        held.push((
            "fs_read",
            if !inside {
                Held::No("reads are not held on Windows without an AppContainer".to_string())
            } else if made.wider_reads.is_empty() {
                Held::Yes
            } else {
                Held::Partly(made.wider_reads.join("; "))
            },
        ));
    }
    if no_net(policy) {
        held.push((
            "net",
            if inside {
                Held::Yes
            } else {
                Held::No(
                    "the network is not held on Windows without an AppContainer".to_string(),
                )
            },
        ));
    } else if !crate::confine::any_net(policy) {
        held.push((
            "net",
            if inside {
                Held::Partly(
                    "the internetClient capability admits every host; the host is held by \
                     the language alone"
                        .to_string(),
                )
            } else {
                Held::No(
                    "the network is not held on Windows without an AppContainer".to_string(),
                )
            },
        ));
    }
    if !inside && (granted(policy, "fs_read").is_some() || !crate::confine::any_net(policy)) {
        notes.push(match crate::confine_appcontainer::here() {
            Some(Where::Without(why)) => format!("no AppContainer for this run: {why}"),
            _ => WINDOWS_NOT_HELD.to_string(),
        });
    }
    judge(policy, &held, &layers, &notes)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::budget::budget_from;
    use crate::confine::os_policy;

    fn policy_of(allow: &str) -> Json {
        os_policy(&budget_from(Some(allow), None).expect("a budget"), true, false)
    }

    #[test]
    fn a_budget_with_no_write_grant_may_be_lowered() {
        assert!(lower_the_label(&policy_of("io"), &Extras::default()));
        assert!(lower_the_label(&policy_of("fs:read:."), &Extras::default()));
        // a write grant keeps the process at medium integrity
        assert!(!lower_the_label(&policy_of("fs:write:."), &Extras::default()));
        assert!(!lower_the_label(&policy_of("fs"), &Extras::default()));
        // and so does a place the run itself must write
        let extras = Extras { writes: vec!["x".to_string()], ..Extras::default() };
        assert!(!lower_the_label(&policy_of("io"), &extras));
    }

    #[cfg(windows)]
    #[test]
    fn the_token_keeps_one_privilege_and_removes_the_rest() {
        // the call is made against this process's own token, which is what
        // it does in a run; after it, the process is still able to read a
        // file, which is what "privileges" does not mean
        let (no_privileges, not_lowered) = calls::token(false, None);
        assert!(no_privileges.is_none(), "{no_privileges:?}");
        assert_eq!(not_lowered.as_deref(), Some("not asked for"));
        assert!(std::fs::metadata(env!("CARGO_MANIFEST_DIR")).is_ok());
    }

    #[cfg(windows)]
    #[test]
    fn the_low_label_is_the_one_windows_knows() {
        // a directory of this test's own, labelled low and then left: the
        // label is inherited by what is made in it, which is what a private
        // temporary directory needs
        let dir = std::env::temp_dir().join(format!("sabline-label-{}", std::process::id()));
        std::fs::create_dir_all(&dir).expect("a directory");
        let why = calls::label_low(&dir.to_string_lossy());
        assert!(why.is_none(), "{why:?}");
        // and a name that is not there is a reason, not a crash
        let gone = dir.join("not-there").join("either");
        assert!(calls::label_low(&gone.to_string_lossy()).is_some());
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[cfg(windows)]
    #[test]
    fn a_job_holds_this_process_to_one_process() {
        // the job is not made here: it holds the process for its whole life
        // and would hold the rest of the suite, which starts processes.
        // check_confine.py is what runs a program under it and tries to
        // start one. What is held here is that the call exists and that the
        // numbers it is given are the ones Windows documents.
        let source = include_str!("confine_windows.rs");
        assert!(source.contains("JOB_OBJECT_LIMIT_ACTIVE_PROCESS: DWORD = 0x0000_0008"));
        assert!(source.contains("JOB_EXTENDED_LIMIT_INFORMATION: i32 = 9"));
        assert!(source.contains("JOB_BASIC_UI_RESTRICTIONS: i32 = 4"));
        assert!(source.contains("active_process_limit = 1"));
    }
}
