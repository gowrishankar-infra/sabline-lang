//! The Windows **AppContainer** (9.0, M4): the layer that holds reads and
//! the network on Windows, which the job object and the lowered token
//! cannot.
//!
//! A process cannot enter a container after it has started, so the run's
//! own process is started inside one by the process that was asked for the
//! run. `sabline-rt exec`, asked for confinement on Windows, therefore
//! becomes two processes:
//!
//! 1. **the outer one** reads the request, **loads the program to learn
//!    which files it reads** - a lookahead, never an answer: the child's
//!    own load is what refuses anything - creates an AppContainer profile
//!    named for this run, grants its SID **one ACE per file and per granted
//!    directory**, and starts a child `sabline-rt exec --contained SID`
//!    inside the container, with its own standard output and error
//!    inherited and a pipe for its standard input;
//! 2. **the inner one** is the run: it reads the same request from that
//!    pipe, checks what it is told to check, asks the operating system for
//!    the rest of the policy ([`crate::confine_windows`]) and says, in its
//!    receipt, that the container holds what the container holds.
//!
//! The outer one then pumps the request line and the rest of its own
//! standard input into the child, waits, **takes every ACE back** and
//! deletes the profile. It is a byte pump and nothing else: the frames the
//! run writes go straight to whoever asked for the run.
//!
//! **The child does not take the parent's word for it.** `--contained SID`
//! is a claim; [`in_a_container`] asks the kernel - this token's
//! `TokenIsAppContainer` and `TokenAppContainerSid` - and the claim is made
//! only when the kernel agrees and the SID is the one named. A sabline-rt
//! started with `--contained` outside a container reports that it is not
//! held, and holds nothing back.
//!
//! **When the container is left off**, and why, is [`left_off`]: a budget
//! granting a loopback host (Windows isolates a container from 127.0.0.1),
//! and a budget that restricts neither reads nor writes, which a container
//! cannot express - it reaches only what it is given, one ACE at a time -
//! without refusing what the budget allows. The reason is in the receipt,
//! and the level is what it was before this rung.
//!
//! `rt/spikes/appcontainer/` is the measurement this is built on, and its
//! README says what it found. What is pure here - [`left_off`], [`plan`],
//! [`profile_name`] - is compiled and tested on every platform; only the
//! calls are behind `cfg(windows)`.

#![allow(unsafe_code)] // the profile, the ACEs and CreateProcess are C entry points

use crate::confine::{existing, granted, nearest_directory, net_hosts, no_net, Extras};
use crate::json::Json;

/// The layer name a receipt writes for the container.
pub const APPCONTAINER: &str = "appcontainer";

/// The `internetClient` capability's SID: an AppContainer with it may open
/// a connection to a host outside the machine, and one without it may not.
/// It is not per host - the host stays the language's to hold.
pub const INTERNET_CLIENT: &str = "S-1-15-3-1";

/// Whether a host name is the machine itself, which no AppContainer may
/// reach: Windows isolates a container from the loopback address unless an
/// administrator exempts it (`CheckNetIsolation`), and nothing Sabline does
/// at run time can change that.
pub fn loopback(host: &str) -> bool {
    let host = host.trim().trim_start_matches('[').trim_end_matches(']');
    let host = host.to_ascii_lowercase();
    if host == "localhost" || host.ends_with(".localhost") {
        return true;
    }
    // an address, and not a name that begins like one: `127.example.com` is
    // somebody's domain
    host.parse::<std::net::IpAddr>()
        .is_ok_and(|address| address.is_loopback() || address.is_unspecified())
}

/// Why this run is **not** put in a container, or `None` when it is.
///
/// Each reason is a run that a container would refuse something the budget
/// allows, which is a loss and not a gain: it is left off, the receipt's
/// reason says so, and the level is what it was before this rung.
pub fn left_off(policy: &Json, extras: &Extras) -> Option<String> {
    if extras.read_any {
        return Some(
            "this run's reads are not held to its own files, so a container would refuse \
             an import the budget allows"
                .to_string(),
        );
    }
    if granted(policy, "fs_read").is_none() {
        return Some(
            "the budget does not restrict reads, and an AppContainer reaches only what it \
             is given an ACE for, so it would refuse a read the budget allows"
                .to_string(),
        );
    }
    if granted(policy, "fs_write").is_none() {
        return Some(
            "the budget does not restrict writes, and an AppContainer writes only where it \
             is given an ACE, so it would refuse a write the budget allows"
                .to_string(),
        );
    }
    let named: Vec<String> = net_hosts(policy)
        .unwrap_or_default()
        .into_iter()
        .filter(|(host, _)| loopback(host))
        .map(|(host, _)| host)
        .collect();
    if !named.is_empty() {
        return Some(format!(
            "the budget grants a loopback host ({}), which no AppContainer may reach: \
             Windows isolates a container from the loopback address unless an \
             administrator exempts it",
            named.join(", ")
        ));
    }
    None
}

/// What one run's container is given: an ACE for each of these, and nothing
/// else.
#[derive(Debug, Default, Clone, PartialEq, Eq)]
pub struct Plan {
    /// Read and execute: the budget's read grants, the program, its
    /// imports and the standard library it was loaded from.
    pub reads: Vec<String>,
    /// Read, write, remove: the budget's write grants, the places the run
    /// itself writes, and its private temporary directory.
    pub writes: Vec<String>,
    /// The capability SIDs the container is made with.
    pub capabilities: Vec<&'static str>,
    /// The write grants that are not there yet, each held to the nearest
    /// directory that is, said as the level's reason says it.
    pub wider: Vec<String>,
    /// The read grants that are not there yet, likewise.
    pub wider_reads: Vec<String>,
}

/// Keep the first of each, in the order given.
fn once_each(paths: Vec<String>) -> Vec<String> {
    let mut seen: std::collections::BTreeSet<String> = std::collections::BTreeSet::new();
    paths.into_iter().filter(|p| seen.insert(crate::pypath::os_path::normcase(p))).collect()
}

/// The ACEs one run's container is given, from its policy and what the run
/// itself must reach. Pure: it reads the file system only to ask whether a
/// grant is there yet, as [`crate::confine_linux`]'s plan does.
///
/// A path granted both ways is written, since the write grant carries the
/// read; a read grant that is not there yet is held to the nearest
/// directory that is, as on Linux, and the level says so.
pub fn plan(policy: &Json, extras: &Extras) -> Plan {
    let mut reads: Vec<String> = Vec::new();
    let mut writes: Vec<String> = Vec::new();
    let (mut wider, mut wider_reads) = (Vec::new(), Vec::new());
    for grant in granted(policy, "fs_read").unwrap_or_default() {
        let (nearest, widened) = nearest_directory(&grant);
        let Some(nearest) = nearest else { continue };
        if widened {
            wider_reads
                .push(format!("{grant} does not exist yet, so reads are held to {nearest}"));
        }
        reads.push(nearest);
    }
    // what the run itself reads: the program, its imports, the standard
    // library beside the host. A policy that did not allow them would not
    // refuse anything - it would stop the run before its first statement.
    reads.extend(existing(&extras.reads));
    // and the file whose appearance stops the run, which is not there yet:
    // a container that could not look for it would never stop (`sabline
    // eval`). It is held to the nearest directory that is there, as a read
    // grant that is not there yet is.
    if let Some(stop) = &extras.stop_file {
        if let (Some(nearest), _) = nearest_directory(stop) {
            reads.push(nearest);
        }
    }
    for grant in granted(policy, "fs_write").unwrap_or_default() {
        let (nearest, widened) = nearest_directory(&grant);
        let Some(nearest) = nearest else { continue };
        if widened {
            wider.push(format!("{grant} does not exist yet, so writes are held to {nearest}"));
        }
        writes.push(nearest);
    }
    writes.extend(existing(&extras.writes));
    if let Some(temp) = &extras.temp {
        writes.extend(existing(std::slice::from_ref(temp)));
    }
    let writes = once_each(writes);
    let written: std::collections::BTreeSet<String> =
        writes.iter().map(|p| crate::pypath::os_path::normcase(p)).collect();
    let reads = once_each(reads)
        .into_iter()
        .filter(|p| !written.contains(&crate::pypath::os_path::normcase(p)))
        .collect();
    let capabilities = if no_net(policy) { Vec::new() } else { vec![INTERNET_CLIENT] };
    Plan { reads, writes, capabilities, wider, wider_reads }
}

/// The profile's name, which is this run's and no other's: a profile that
/// is deleted takes its SID with it, so an ACE left behind by a run that
/// was killed names a SID nothing can hold again.
///
/// Windows takes at most 64 characters, from the letters, the digits,
/// `.`, `-` and `_`.
pub fn profile_name(pid: u32, at: u128) -> String {
    format!("sabline.rt.{pid}.{:x}", at & 0xFFFF_FFFF_FFFF)
}

/// Where this process stands with respect to a container, said once, by
/// `sabline-rt exec`, before the first statement.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Where {
    /// Inside the container the run's parent made, and the kernel agrees.
    Inside,
    /// Not in one, and why - which the level's reason carries.
    Without(String),
}

static WHERE: std::sync::OnceLock<Where> = std::sync::OnceLock::new();

/// Say where this process stands. Called once, by `sabline-rt exec`.
pub fn stands(it: Where) {
    let _ = WHERE.set(it);
}

/// Where it stands, or `None` when nobody said - a process that never
/// considered a container, such as one of the agreement gate's batches.
pub fn here() -> Option<Where> {
    WHERE.get().cloned()
}

#[cfg(windows)]
#[allow(clippy::upper_case_acronyms)] // Windows' own names for its own types
mod calls {
    //! The calls, and nothing else.
    use std::ffi::c_void;

    pub type HANDLE = *mut c_void;
    type BOOL = i32;
    type DWORD = u32;
    type PSID = *mut c_void;
    type HRESULT = i32;
    type LPCWSTR = *const u16;
    type LPWSTR = *mut u16;

    #[repr(C)]
    pub struct SidAndAttributes {
        pub sid: PSID,
        pub attributes: DWORD,
    }

    #[repr(C)]
    struct SecurityCapabilities {
        app_container_sid: PSID,
        capabilities: *mut SidAndAttributes,
        capability_count: DWORD,
        reserved: DWORD,
    }

    #[repr(C)]
    struct StartupInfoW {
        cb: DWORD,
        reserved: LPWSTR,
        desktop: LPWSTR,
        title: LPWSTR,
        x: DWORD,
        y: DWORD,
        x_size: DWORD,
        y_size: DWORD,
        x_count_chars: DWORD,
        y_count_chars: DWORD,
        fill_attribute: DWORD,
        flags: DWORD,
        show_window: u16,
        reserved2: u16,
        reserved2_ptr: *mut u8,
        std_input: HANDLE,
        std_output: HANDLE,
        std_error: HANDLE,
    }

    #[repr(C)]
    struct StartupInfoExW {
        startup: StartupInfoW,
        attribute_list: *mut c_void,
    }

    #[repr(C)]
    struct ProcessInformation {
        process: HANDLE,
        thread: HANDLE,
        process_id: DWORD,
        thread_id: DWORD,
    }

    #[repr(C)]
    struct SecurityAttributes {
        length: DWORD,
        descriptor: *mut c_void,
        inherit: BOOL,
    }

    #[repr(C)]
    struct TrusteeW {
        multiple: *mut TrusteeW,
        multiple_operation: u32,
        form: u32,
        kind: u32,
        name: LPWSTR,
    }

    #[repr(C)]
    struct ExplicitAccessW {
        permissions: DWORD,
        mode: u32,
        inheritance: DWORD,
        trustee: TrusteeW,
    }

    #[link(name = "kernel32")]
    extern "system" {
        fn CreateProcessW(
            app: LPCWSTR,
            cmd: LPWSTR,
            pa: *mut c_void,
            ta: *mut c_void,
            inherit: BOOL,
            flags: DWORD,
            env: *mut c_void,
            cwd: LPCWSTR,
            si: *mut StartupInfoW,
            pi: *mut ProcessInformation,
        ) -> BOOL;
        fn InitializeProcThreadAttributeList(
            list: *mut c_void,
            count: DWORD,
            flags: DWORD,
            size: *mut usize,
        ) -> BOOL;
        fn UpdateProcThreadAttribute(
            list: *mut c_void,
            flags: DWORD,
            attr: usize,
            value: *mut c_void,
            size: usize,
            prev: *mut c_void,
            ret: *mut usize,
        ) -> BOOL;
        fn DeleteProcThreadAttributeList(list: *mut c_void);
        fn CreatePipe(
            r: *mut HANDLE,
            w: *mut HANDLE,
            sa: *mut SecurityAttributes,
            size: DWORD,
        ) -> BOOL;
        fn SetHandleInformation(h: HANDLE, mask: DWORD, flags: DWORD) -> BOOL;
        fn GetStdHandle(which: DWORD) -> HANDLE;
        fn WaitForSingleObject(h: HANDLE, ms: DWORD) -> DWORD;
        fn GetExitCodeProcess(h: HANDLE, code: *mut DWORD) -> BOOL;
        fn CloseHandle(h: HANDLE) -> BOOL;
        fn LocalFree(p: *mut c_void) -> *mut c_void;
        fn GetLastError() -> DWORD;
        fn GetCurrentProcess() -> HANDLE;
    }

    #[link(name = "userenv")]
    extern "system" {
        fn CreateAppContainerProfile(
            name: LPCWSTR,
            display: LPCWSTR,
            description: LPCWSTR,
            capabilities: *mut SidAndAttributes,
            count: DWORD,
            sid: *mut PSID,
        ) -> HRESULT;
        fn DeleteAppContainerProfile(name: LPCWSTR) -> HRESULT;
        fn DeriveAppContainerSidFromAppContainerName(name: LPCWSTR, sid: *mut PSID)
            -> HRESULT;
    }

    #[link(name = "advapi32")]
    extern "system" {
        fn ConvertStringSidToSidW(text: LPCWSTR, sid: *mut PSID) -> BOOL;
        fn ConvertSidToStringSidW(sid: PSID, text: *mut LPWSTR) -> BOOL;
        fn FreeSid(sid: PSID) -> *mut c_void;
        fn GetNamedSecurityInfoW(
            name: LPCWSTR,
            object: u32,
            information: DWORD,
            owner: *mut PSID,
            group: *mut PSID,
            dacl: *mut *mut c_void,
            sacl: *mut *mut c_void,
            descriptor: *mut *mut c_void,
        ) -> DWORD;
        fn SetNamedSecurityInfoW(
            name: LPWSTR,
            object: u32,
            information: DWORD,
            owner: PSID,
            group: PSID,
            dacl: *mut c_void,
            sacl: *mut c_void,
        ) -> DWORD;
        fn SetEntriesInAclW(
            count: u32,
            entries: *mut ExplicitAccessW,
            old: *mut c_void,
            new: *mut *mut c_void,
        ) -> DWORD;
        fn OpenProcessToken(process: HANDLE, access: DWORD, token: *mut HANDLE) -> BOOL;
        fn GetTokenInformation(
            token: HANDLE,
            class: i32,
            info: *mut c_void,
            length: DWORD,
            needed: *mut DWORD,
        ) -> BOOL;
        fn GetAce(acl: *mut c_void, index: DWORD, ace: *mut *mut c_void) -> BOOL;
        fn EqualSid(a: PSID, b: PSID) -> BOOL;
    }

    const EXTENDED_STARTUPINFO_PRESENT: DWORD = 0x0008_0000;
    const PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES: usize = 0x0002_0009;
    const PROC_THREAD_ATTRIBUTE_HANDLE_LIST: usize = 0x0002_0002;
    const STARTF_USESTDHANDLES: DWORD = 0x100;
    const HANDLE_FLAG_INHERIT: DWORD = 1;
    const STD_OUTPUT_HANDLE: DWORD = 0xFFFF_FFF5;
    const STD_ERROR_HANDLE: DWORD = 0xFFFF_FFF4;
    const SE_FILE_OBJECT: u32 = 1;
    const DACL_SECURITY_INFORMATION: DWORD = 4;
    const GRANT_ACCESS: u32 = 1;
    const REVOKE_ACCESS: u32 = 4;
    const SUB_CONTAINERS_AND_OBJECTS_INHERIT: DWORD = 3;
    const NO_INHERITANCE: DWORD = 0;
    const TRUSTEE_IS_SID: u32 = 0;
    const TRUSTEE_IS_UNKNOWN: u32 = 0;
    const SE_GROUP_ENABLED: DWORD = 4;
    /// Read and execute, which is what a file the run reads needs.
    pub const FILE_READ: DWORD = 0x0012_0089 | 0x0012_00A0;
    /// Read, write and remove, which is what a write grant needs.
    pub const FILE_WRITE: DWORD = 0x0012_0089 | 0x0012_00A0 | 0x0012_0116 | 0x0001_0000;
    const TOKEN_QUERY: DWORD = 0x0008;
    const TOKEN_IS_APP_CONTAINER: i32 = 29;
    const TOKEN_APP_CONTAINER_SID: i32 = 31;
    const ALREADY_EXISTS: HRESULT = 0x8007_00B7_u32 as HRESULT;
    const WAIT_OBJECT_0: DWORD = 0;

    fn wide(text: &str) -> Vec<u16> {
        text.encode_utf16().chain(std::iter::once(0)).collect()
    }

    fn last_error() -> DWORD {
        // SAFETY: GetLastError reads this thread's own last-error value and
        // changes nothing. test: the_profile_is_made_granted_and_taken_back.
        unsafe { GetLastError() }
    }

    /// A SID this module owns, freed the way the call that made it asks.
    pub struct Sid {
        pub raw: PSID,
        local: bool,
    }

    impl Drop for Sid {
        fn drop(&mut self) {
            if self.raw.is_null() {
                return;
            }
            // SAFETY: `raw` came from ConvertStringSidToSid (LocalAlloc) or
            // from CreateAppContainerProfile (FreeSid), and `local` says
            // which; it is freed once, here.
            // test: the_profile_is_made_granted_and_taken_back.
            unsafe {
                if self.local {
                    LocalFree(self.raw);
                } else {
                    FreeSid(self.raw);
                }
            }
            self.raw = std::ptr::null_mut();
        }
    }

    /// The SID a SID text names.
    pub fn sid_of(text: &str) -> Option<Sid> {
        let w = wide(text);
        let mut sid: PSID = std::ptr::null_mut();
        // SAFETY: `w` is NUL-terminated and `sid` is a live out-pointer the
        // call fills with a SID it allocated, which Sid frees.
        // test: the_profile_is_made_granted_and_taken_back.
        if unsafe { ConvertStringSidToSidW(w.as_ptr(), &mut sid) } == 0 {
            return None;
        }
        Some(Sid { raw: sid, local: true })
    }

    /// A SID as its text.
    pub fn sid_text(sid: PSID) -> Option<String> {
        let mut text: LPWSTR = std::ptr::null_mut();
        // SAFETY: `sid` is a live SID and `text` is a live out-pointer the
        // call fills with a string it allocated, freed below.
        // test: the_profile_is_made_granted_and_taken_back.
        if unsafe { ConvertSidToStringSidW(sid, &mut text) } == 0 {
            return None;
        }
        // SAFETY: `text` is a NUL-terminated wide string the call
        // allocated; its length is read before it is freed once.
        // test: the_profile_is_made_granted_and_taken_back.
        let out = unsafe {
            let mut n = 0;
            while *text.add(n) != 0 {
                n += 1;
            }
            let out = String::from_utf16_lossy(std::slice::from_raw_parts(text, n));
            LocalFree(text.cast());
            out
        };
        Some(out)
    }

    /// Make the profile, or find the one of that name, and answer its SID.
    pub fn make_profile(name: &str) -> Result<Sid, String> {
        let n = wide(name);
        let shown = wide("Sabline run");
        let mut sid: PSID = std::ptr::null_mut();
        // SAFETY: the three strings are NUL-terminated, no capability is
        // given at creation, and `sid` receives a SID this process owns.
        // test: the_profile_is_made_granted_and_taken_back.
        let made = unsafe {
            CreateAppContainerProfile(
                n.as_ptr(),
                shown.as_ptr(),
                shown.as_ptr(),
                std::ptr::null_mut(),
                0,
                &mut sid,
            )
        };
        if made == ALREADY_EXISTS {
            let derived = {
                // SAFETY: as above; the name is NUL-terminated and `sid`
                // is a live out-pointer.
                // test: the_profile_is_made_granted_and_taken_back.
                unsafe { DeriveAppContainerSidFromAppContainerName(n.as_ptr(), &mut sid) }
            };
            if derived < 0 {
                return Err(format!("the container's SID: {derived:#x}"));
            }
        } else if made < 0 {
            return Err(format!("CreateAppContainerProfile: {made:#x}"));
        }
        Ok(Sid { raw: sid, local: false })
    }

    /// Delete the profile of that name. Best-effort: a profile that is
    /// gone is what was wanted.
    pub fn delete_profile(name: &str) {
        let n = wide(name);
        // SAFETY: `n` is NUL-terminated; the call changes nothing else.
        // test: the_profile_is_made_granted_and_taken_back.
        unsafe { DeleteAppContainerProfile(n.as_ptr()) };
    }

    /// Add or take back one ACE for `sid` on `path`. `access` of 0 takes
    /// every ACE of that trustee back.
    fn ace(path: &str, sid: PSID, access: DWORD, inherit: bool) -> Option<String> {
        let w = wide(path);
        let mut dacl: *mut c_void = std::ptr::null_mut();
        let mut descriptor: *mut c_void = std::ptr::null_mut();
        // SAFETY: `w` is NUL-terminated; `dacl` points into `descriptor`,
        // which is freed below after its last use.
        // test: the_profile_is_made_granted_and_taken_back.
        let read = unsafe {
            GetNamedSecurityInfoW(
                w.as_ptr(),
                SE_FILE_OBJECT,
                DACL_SECURITY_INFORMATION,
                std::ptr::null_mut(),
                std::ptr::null_mut(),
                &mut dacl,
                std::ptr::null_mut(),
                &mut descriptor,
            )
        };
        if read != 0 {
            return Some(format!("the rights of {path} could not be read: error {read}"));
        }
        let mut entry = ExplicitAccessW {
            permissions: access,
            mode: if access == 0 { REVOKE_ACCESS } else { GRANT_ACCESS },
            inheritance: if inherit {
                SUB_CONTAINERS_AND_OBJECTS_INHERIT
            } else {
                NO_INHERITANCE
            },
            trustee: TrusteeW {
                multiple: std::ptr::null_mut(),
                multiple_operation: 0,
                form: TRUSTEE_IS_SID,
                kind: TRUSTEE_IS_UNKNOWN,
                name: sid.cast(),
            },
        };
        let mut made: *mut c_void = std::ptr::null_mut();
        // SAFETY: `entry` is live for the call and names the SID above;
        // `made` receives an ACL the call allocated, freed below.
        // test: the_profile_is_made_granted_and_taken_back.
        let built = unsafe { SetEntriesInAclW(1, &mut entry, dacl, &mut made) };
        if built != 0 {
            // SAFETY: `descriptor` was allocated by the read above and is
            // freed once, on this path.
            // test: the_profile_is_made_granted_and_taken_back.
            unsafe { LocalFree(descriptor) };
            return Some(format!("the rights of {path} could not be built: error {built}"));
        }
        let mut name = wide(path);
        // SAFETY: `name` is NUL-terminated and `made` is the ACL above,
        // alive for the call.
        // test: the_profile_is_made_granted_and_taken_back.
        let set = unsafe {
            SetNamedSecurityInfoW(
                name.as_mut_ptr(),
                SE_FILE_OBJECT,
                DACL_SECURITY_INFORMATION,
                std::ptr::null_mut(),
                std::ptr::null_mut(),
                made,
                std::ptr::null_mut(),
            )
        };
        // SAFETY: both were allocated by the calls above and are freed
        // once, here, after their last use.
        // test: the_profile_is_made_granted_and_taken_back.
        unsafe {
            LocalFree(made);
            LocalFree(descriptor);
        }
        if set == 0 {
            None
        } else {
            Some(format!("the rights of {path} could not be set: error {set}"))
        }
    }

    /// Give `sid` one ACE on `path`.
    pub fn grant(path: &str, sid: &Sid, access: DWORD) -> Option<String> {
        let _held = match super::one_at_a_time() {
            Ok(held) => held,
            Err(why) => return Some(why),
        };
        ace(path, sid.raw, access, std::path::Path::new(path).is_dir())
    }

    /// Take every ACE of `sid` on `path` back. Every ACE and not the
    /// rights that were there before: another run's container may have
    /// been given one on the same file while this one held it, and a
    /// saved copy of the rights put back would take that one away.
    pub fn revoke(path: &str, sid: &Sid) -> Option<String> {
        let _held = match super::one_at_a_time() {
            Ok(held) => held,
            Err(why) => return Some(why),
        };
        ace(path, sid.raw, 0, false)
    }

    /// Whether `path`'s rights name `sid`: what [`grant`] puts there and
    /// [`revoke`] takes away, read back from the object itself.
    pub fn has_ace(path: &str, sid: &Sid) -> bool {
        let w = wide(path);
        let mut dacl: *mut c_void = std::ptr::null_mut();
        let mut descriptor: *mut c_void = std::ptr::null_mut();
        // SAFETY: `w` is NUL-terminated; `dacl` points into `descriptor`,
        // which is freed below after its last use.
        // test: the_profile_is_made_granted_and_taken_back.
        let read = unsafe {
            GetNamedSecurityInfoW(
                w.as_ptr(),
                SE_FILE_OBJECT,
                DACL_SECURITY_INFORMATION,
                std::ptr::null_mut(),
                std::ptr::null_mut(),
                &mut dacl,
                std::ptr::null_mut(),
                &mut descriptor,
            )
        };
        if read != 0 || dacl.is_null() {
            return false;
        }
        // SAFETY: `dacl` is an ACL inside `descriptor`. Its header is a
        // revision byte, a reserved byte, its own size as a 16-bit number
        // and then the entry count as another, so the count is the 16-bit
        // number four bytes in; GetAce answers each entry in turn, and
        // every entry this module makes is an ACCESS_ALLOWED_ACE, whose
        // SID begins after the four-byte header and the four-byte mask.
        // test: the_profile_is_made_granted_and_taken_back.
        unsafe {
            let count = u32::from(dacl.cast::<u8>().add(4).cast::<u16>().read_unaligned());
            let mut found = false;
            for i in 0..count {
                let mut entry: *mut c_void = std::ptr::null_mut();
                if GetAce(dacl, i, &mut entry) == 0 || entry.is_null() {
                    continue;
                }
                let kind = *entry.cast::<u8>();
                if kind != 0 {
                    continue; // not an access-allowed entry
                }
                if EqualSid(entry.cast::<u8>().add(8).cast(), sid.raw) != 0 {
                    found = true;
                    break;
                }
            }
            LocalFree(descriptor);
            found
        }
    }

    /// The container SID of this process's own token, or `None` when this
    /// token is not an AppContainer's.
    pub fn my_container() -> Option<String> {
        let mut token: HANDLE = std::ptr::null_mut();
        // SAFETY: the pseudo-handle for this process needs no closing and
        // `token` is a live out-parameter, closed before this returns.
        // test: this_process_is_not_in_a_container.
        if unsafe { OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &mut token) } == 0 {
            return None;
        }
        let mut is_one: DWORD = 0;
        let mut needed: DWORD = 0;
        // SAFETY: the class answers one DWORD, and `is_one` is one.
        // test: this_process_is_not_in_a_container.
        let asked = unsafe {
            GetTokenInformation(
                token,
                TOKEN_IS_APP_CONTAINER,
                (&mut is_one as *mut DWORD).cast(),
                u32::try_from(std::mem::size_of::<DWORD>()).unwrap_or(0),
                &mut needed,
            )
        };
        let mut found = None;
        if asked != 0 && is_one != 0 {
            let mut size: DWORD = 0;
            // SAFETY: the first call asks for the size only - a null buffer
            // of length 0 - and writes it through `size`.
            // test: this_process_is_not_in_a_container.
            unsafe {
                GetTokenInformation(
                    token,
                    TOKEN_APP_CONTAINER_SID,
                    std::ptr::null_mut(),
                    0,
                    &mut size,
                )
            };
            let mut buffer = vec![0u8; usize::try_from(size).unwrap_or(0).max(8)];
            // SAFETY: `buffer` is `size` bytes and the call fills it with a
            // TOKEN_APPCONTAINER_INFORMATION - one pointer to a SID inside
            // this process. test: this_process_is_not_in_a_container.
            let read = unsafe {
                GetTokenInformation(
                    token,
                    TOKEN_APP_CONTAINER_SID,
                    buffer.as_mut_ptr().cast(),
                    size,
                    &mut size,
                )
            };
            if read != 0 {
                // SAFETY: the buffer holds one pointer at its start, which
                // the call above wrote; it points at a SID that lives as
                // long as the buffer. test: this_process_is_not_in_a_container.
                let sid = unsafe { buffer.as_ptr().cast::<PSID>().read_unaligned() };
                if !sid.is_null() {
                    found = sid_text(sid);
                }
            }
        }
        // SAFETY: `token` came from OpenProcessToken above and is closed
        // once, here. test: this_process_is_not_in_a_container.
        unsafe { CloseHandle(token) };
        found
    }

    /// A child started inside the container: the pipe its standard input
    /// is read from, and its process.
    pub struct Child {
        write_in: HANDLE,
        process: HANDLE,
        thread: HANDLE,
    }

    /// Start `command` inside the container `sid` holds, with `capabilities`,
    /// this process's own standard output and error, and a pipe for its
    /// standard input.
    pub fn start(
        exe: &str,
        command: &str,
        sid: &Sid,
        capabilities: &[Sid],
    ) -> Result<Child, String> {
        let mut attributes = SecurityAttributes {
            length: u32::try_from(std::mem::size_of::<SecurityAttributes>()).unwrap_or(0),
            descriptor: std::ptr::null_mut(),
            inherit: 1,
        };
        let (mut read_in, mut write_in) = (std::ptr::null_mut(), std::ptr::null_mut());
        // SAFETY: both out-pointers are live; the ends are closed below and
        // by Child. test: the_profile_is_made_granted_and_taken_back.
        if unsafe { CreatePipe(&mut read_in, &mut write_in, &mut attributes, 0) } == 0 {
            return Err(format!("the child's standard input: error {}", last_error()));
        }
        // SAFETY: `write_in` is this end of the pipe, which the child must
        // not inherit. test: the_profile_is_made_granted_and_taken_back.
        unsafe { SetHandleInformation(write_in, HANDLE_FLAG_INHERIT, 0) };
        // SAFETY: the two standard handles belong to this process; marking
        // them inheritable is what lets the child write where this one
        // does. test: the_profile_is_made_granted_and_taken_back.
        let (out, err) = unsafe {
            let out = GetStdHandle(STD_OUTPUT_HANDLE);
            let err = GetStdHandle(STD_ERROR_HANDLE);
            SetHandleInformation(out, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT);
            SetHandleInformation(err, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT);
            (out, err)
        };
        let mut given: Vec<SidAndAttributes> = capabilities
            .iter()
            .map(|c| SidAndAttributes { sid: c.raw, attributes: SE_GROUP_ENABLED })
            .collect();
        let mut security = SecurityCapabilities {
            app_container_sid: sid.raw,
            capabilities: if given.is_empty() {
                std::ptr::null_mut()
            } else {
                given.as_mut_ptr()
            },
            capability_count: u32::try_from(given.len()).unwrap_or(0),
            reserved: 0,
        };
        let mut size = 0usize;
        // SAFETY: the first call asks for the size only.
        // test: the_profile_is_made_granted_and_taken_back.
        unsafe { InitializeProcThreadAttributeList(std::ptr::null_mut(), 2, 0, &mut size) };
        let mut list = vec![0u8; size.max(1)];
        let mut handles = [read_in, out, err];
        // SAFETY: `list` is `size` bytes; `security` and `handles` both
        // outlive the attribute list and the call that reads it.
        // test: the_profile_is_made_granted_and_taken_back.
        let ready = unsafe {
            InitializeProcThreadAttributeList(list.as_mut_ptr().cast(), 2, 0, &mut size) != 0
                && UpdateProcThreadAttribute(
                    list.as_mut_ptr().cast(),
                    0,
                    PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES,
                    (&mut security as *mut SecurityCapabilities).cast(),
                    std::mem::size_of::<SecurityCapabilities>(),
                    std::ptr::null_mut(),
                    std::ptr::null_mut(),
                ) != 0
                && UpdateProcThreadAttribute(
                    list.as_mut_ptr().cast(),
                    0,
                    PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
                    handles.as_mut_ptr().cast(),
                    std::mem::size_of_val(&handles),
                    std::ptr::null_mut(),
                    std::ptr::null_mut(),
                ) != 0
        };
        if !ready {
            let why = format!("the container's attributes: error {}", last_error());
            // SAFETY: the three handles this function made or marked; the
            // standard ones are not closed.
            // test: the_profile_is_made_granted_and_taken_back.
            unsafe {
                CloseHandle(read_in);
                CloseHandle(write_in);
            }
            return Err(why);
        }
        // SAFETY: an all-zero StartupInfoExW is a valid starting value -
        // every field is a number or a pointer and zero means "none".
        // test: the_profile_is_made_granted_and_taken_back.
        let mut startup: StartupInfoExW = unsafe { std::mem::zeroed() };
        startup.startup.cb = u32::try_from(std::mem::size_of::<StartupInfoExW>()).unwrap_or(0);
        startup.startup.flags = STARTF_USESTDHANDLES;
        startup.startup.std_input = read_in;
        startup.startup.std_output = out;
        startup.startup.std_error = err;
        startup.attribute_list = list.as_mut_ptr().cast();
        let mut cmd = wide(command);
        let app = wide(exe);
        // SAFETY: an all-zero ProcessInformation is a valid out-parameter.
        // test: the_profile_is_made_granted_and_taken_back.
        let mut about: ProcessInformation = unsafe { std::mem::zeroed() };
        // SAFETY: every pointer is live for the call: `app` and `cmd` are
        // NUL-terminated, `startup` holds the attribute list built above,
        // and `about` is written by the call.
        // test: the_profile_is_made_granted_and_taken_back.
        let started = unsafe {
            CreateProcessW(
                app.as_ptr(),
                cmd.as_mut_ptr(),
                std::ptr::null_mut(),
                std::ptr::null_mut(),
                1,
                EXTENDED_STARTUPINFO_PRESENT,
                std::ptr::null_mut(),
                std::ptr::null(),
                &mut startup.startup,
                &mut about,
            )
        };
        let why = last_error();
        // SAFETY: the attribute list was built above and the child holds
        // its own copy of the pipe end it inherited.
        // test: the_profile_is_made_granted_and_taken_back.
        unsafe {
            DeleteProcThreadAttributeList(list.as_mut_ptr().cast());
            CloseHandle(read_in);
        }
        if started == 0 {
            // SAFETY: this end of the pipe, closed once on this path.
            // test: the_profile_is_made_granted_and_taken_back.
            unsafe { CloseHandle(write_in) };
            return Err(format!("the run's process could not be started: error {why}"));
        }
        Ok(Child { write_in, process: about.process, thread: about.thread })
    }

    impl Child {
        /// This end of the child's standard input, as a file. Taken once.
        pub fn stdin(&mut self) -> std::fs::File {
            use std::os::windows::io::FromRawHandle;
            let raw = self.write_in;
            self.write_in = std::ptr::null_mut();
            // SAFETY: `raw` is the pipe end this process owns, handed over
            // once - the field is cleared - so the File closes it.
            // test: the_profile_is_made_granted_and_taken_back.
            unsafe { std::fs::File::from_raw_handle(raw.cast()) }
        }

        /// Wait for it, and answer how it ended.
        pub fn wait(&self) -> u32 {
            let mut code: DWORD = 0;
            // SAFETY: `process` is the handle CreateProcess gave, open
            // until Drop. test: the_profile_is_made_granted_and_taken_back.
            unsafe {
                if WaitForSingleObject(self.process, 0xFFFF_FFFF) != WAIT_OBJECT_0 {
                    return 1;
                }
                GetExitCodeProcess(self.process, &mut code);
            }
            code
        }
    }

    impl Drop for Child {
        fn drop(&mut self) {
            // SAFETY: each handle is this child's, closed once, here.
            // test: the_profile_is_made_granted_and_taken_back.
            unsafe {
                if !self.write_in.is_null() {
                    CloseHandle(self.write_in);
                }
                CloseHandle(self.process);
                CloseHandle(self.thread);
            }
        }
    }
}

/// Whether this process is inside the container `claimed` names - the
/// kernel's answer and not the parent's. `Ok(())`, or why not.
#[cfg(windows)]
pub fn in_a_container(claimed: &str) -> Result<(), String> {
    match calls::my_container() {
        None => {
            Err("this process was started as a run's own, inside an AppContainer, and its \
             token is not an AppContainer's"
                .to_string())
        }
        Some(mine) if mine.eq_ignore_ascii_case(claimed) => Ok(()),
        Some(mine) => Err(format!(
            "this process is in the AppContainer {mine} and not the {claimed} it was \
             started for"
        )),
    }
}

/// Whether this process is inside any container at all.
#[cfg(windows)]
pub fn already_contained() -> Option<String> {
    calls::my_container()
}

/// The directory a run's grants are recorded in while it holds them, so
/// that a run killed before it takes them back leaves something the next
/// run can find. Under `%LOCALAPPDATA%`, which is the user's own.
#[cfg(windows)]
fn records() -> Option<std::path::PathBuf> {
    let local = std::env::var("LOCALAPPDATA").ok()?;
    let dir = std::path::Path::new(&local).join("sabline").join("appcontainer");
    std::fs::create_dir_all(&dir).ok()?;
    Some(dir)
}

/// How long a run waits for its turn at an object's rights before it
/// gives up and says the container could not be made.
#[cfg(windows)]
const PATIENCE: std::time::Duration = std::time::Duration::from_secs(20);

/// Hold the lock that makes one read-modify-write of an object's rights
/// this machine's only one, for as long as the answer is alive.
///
/// Adding an ACE is *read the rights, add to them, write them back*, and
/// two runs doing that to the same file at the same time - two runs of one
/// suite, two programs in one directory - would lose one of the two ACEs:
/// the second write is of rights read before the first. The run whose ACE
/// went would then be refused a file its budget grants, which is a wrong
/// answer and not a safe one. So every grant and every revoke takes this
/// first. It is held for one call and not for a run, so two runs still run
/// at once; and it is a file, held with no sharing, so a run that dies
/// lets go of it.
/// `Ok(None)` is a machine with nowhere to keep a lock, where there is
/// nothing to wait for; `Err` is a wait that ran out, and then nothing is
/// written, because writing without it is how an ACE is lost.
#[cfg(windows)]
pub fn one_at_a_time() -> Result<Option<std::fs::File>, String> {
    use std::os::windows::fs::OpenOptionsExt;
    let Some(dir) = records() else { return Ok(None) };
    let path = dir.join(".rights-lock");
    let until = std::time::Instant::now() + PATIENCE;
    loop {
        match std::fs::OpenOptions::new()
            .write(true)
            .create(true)
            .truncate(false)
            .share_mode(0)
            .open(&path)
        {
            Ok(file) => return Ok(Some(file)),
            Err(_) if std::time::Instant::now() < until => {
                std::thread::sleep(std::time::Duration::from_millis(5));
            }
            Err(e) => {
                return Err(format!(
                    "another run held {} for {PATIENCE:?} ({e})",
                    path.display()
                ))
            }
        }
    }
}

/// What one run holds while it holds it: the profile's name in the file's
/// name, the container's SID on the first line and one granted path on
/// each line after it.
///
/// The file is **held open with no sharing** for as long as the run holds
/// the ACEs, so the next run can tell a record of a live run from one left
/// by a run that was killed: a record it can open is a record nobody holds.
#[cfg(windows)]
struct Record {
    path: std::path::PathBuf,
    held: Option<std::fs::File>,
}

#[cfg(windows)]
impl Record {
    fn written(profile: &str, sid: &str, paths: &[String]) -> Record {
        use std::io::Write;
        use std::os::windows::fs::OpenOptionsExt;
        let path = match records() {
            Some(dir) => dir.join(format!("{profile}.txt")),
            None => return Record { path: std::path::PathBuf::new(), held: None },
        };
        let mut body = String::from(sid);
        for p in paths {
            body.push('\n');
            body.push_str(p);
        }
        let held = std::fs::OpenOptions::new()
            .write(true)
            .create(true)
            .truncate(true)
            .share_mode(0)
            .open(&path)
            .ok()
            .and_then(|mut f| {
                f.write_all(body.as_bytes()).and_then(|()| f.flush()).ok().map(|()| f)
            });
        Record { path, held }
    }

    fn done(&mut self) {
        self.held = None;
        if !self.path.as_os_str().is_empty() {
            let _ = std::fs::remove_file(&self.path);
        }
    }
}

/// Take back the ACEs of every run that was killed before it could: a
/// record no process holds open is a run that is gone, and its profile's
/// SID is one nothing can hold again. Best-effort, and silent: it is
/// housekeeping and not a claim.
#[cfg(windows)]
pub fn sweep() {
    use std::io::Read;
    use std::os::windows::fs::OpenOptionsExt;
    let Some(dir) = records() else { return };
    let Ok(listed) = std::fs::read_dir(&dir) else { return };
    for entry in listed.flatten().take(64) {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("txt") {
            continue;
        }
        let Ok(mut file) = std::fs::OpenOptions::new().read(true).share_mode(0).open(&path)
        else {
            continue; // a run that is still holding them
        };
        let mut body = String::new();
        if file.read_to_string(&mut body).is_err() {
            continue;
        }
        drop(file);
        let mut lines = body.lines();
        let Some(sid_text) = lines.next() else { continue };
        if let Some(sid) = calls::sid_of(sid_text) {
            for granted in lines {
                calls::revoke(granted, &sid);
            }
        }
        if let Some(profile) = path.file_stem().and_then(|s| s.to_str()) {
            calls::delete_profile(profile);
        }
        let _ = std::fs::remove_file(&path);
    }
}

/// What one request's turn at a container came to.
#[cfg(windows)]
pub enum Taken {
    /// It ran inside a container of its own; this is how it ended.
    Ran(u8),
    /// It was not contained - [`here`] says why, when there is a why to
    /// say - so the caller runs the program in this process.
    Here,
}

/// What `sabline-rt exec` does with one request on Windows before anything
/// else: put the run in a container of its own, or say where this process
/// stands and let the caller run the program here.
///
/// The request is read here as well as in the run - it is pure, and what
/// it gives is the budget, the policy and what the run itself must reach -
/// and a request that is not one is left to the run to refuse, which is
/// the one place that reports.
#[cfg(windows)]
pub fn consider(request: &str, install_dir: &str) -> Taken {
    let Ok((path, given)) = crate::exec::request(request) else { return Taken::Here };
    // nothing was asked of the operating system: a batch of the gate's,
    // and nothing to say
    let Some(asked) = given.confine.clone() else { return Taken::Here };
    if !asked.on {
        return Taken::Here; // --no-confine, whose reason the policy carries
    }
    let Ok(budget) = crate::budget::budget_from(given.allow.as_deref(), given.deny.as_deref())
    else {
        return Taken::Here;
    };
    let policy = crate::confine::os_policy(&budget, true, asked.strict);
    if crate::confine::restricted(&policy).is_empty() {
        return Taken::Here; // nothing is asked of the system, and it says why
    }
    // the lookahead: which files the program reads, learned by loading it
    // here. It is never an answer - the child's own load is what refuses
    // anything - and it needs the stack a parse needs.
    let (entry, source, root, dir) = (
        path.clone(),
        given.source.clone(),
        given.import_root.clone(),
        install_dir.to_string(),
    );
    let files = std::thread::Builder::new()
        .stack_size(crate::PARSE_STACK)
        .spawn(move || {
            let mut files = Vec::new();
            let _ = crate::loader::load_program_given(
                &entry,
                source.as_deref(),
                root.as_deref(),
                &dir,
                &mut files,
            );
            files
        })
        .map_or_else(|_| Vec::new(), |t| t.join().unwrap_or_default());
    let mut reads = vec![path];
    reads.extend(files);
    reads.extend(asked.reads.iter().cloned());
    reads.extend(given.import_root.iter().cloned());
    let extras = Extras {
        reads,
        writes: asked.writes.clone(),
        temp: asked.temp.clone(),
        read_any: asked.read_any,
        stop_file: given.stop_file.clone(),
    };
    if let Some(mine) = already_contained() {
        stands(Where::Without(format!(
            "this process is already inside the AppContainer {mine}, which it did not make, \
             so what it reaches is that container's grants and not this budget's"
        )));
        return Taken::Here;
    }
    if let Some(why) = left_off(&policy, &extras) {
        stands(Where::Without(why));
        return Taken::Here;
    }
    match outer(request, install_dir, &policy, &extras) {
        Ok(code) => Taken::Ran(code),
        Err(why) => {
            stands(Where::Without(format!(
                "no AppContainer could be made for this run: {why}"
            )));
            Taken::Here
        }
    }
}

/// Run this request inside a container of its own, and answer how the run
/// ended - or, as an error, why **nothing was started**, which is the only
/// case the caller may run the program itself.
///
/// `request` is the one line the run was asked for, passed on unchanged:
/// the child reads the same bytes and derives the same budget, the same
/// policy and the same plan.
#[cfg(windows)]
pub fn outer(
    request: &str,
    install_dir: &str,
    policy: &Json,
    extras: &Extras,
) -> Result<u8, String> {
    use std::io::Write;
    sweep();
    let made = plan(policy, extras);
    let exe = std::env::current_exe()
        .map_err(|e| format!("sabline-rt: this program's own path: {e}"))?;
    let exe = exe.to_string_lossy().to_string();
    let at = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or_default();
    let profile = profile_name(std::process::id(), at);
    let sid = calls::make_profile(&profile)?;
    let sid_text = calls::sid_text(sid.raw)
        .ok_or_else(|| "the container's SID could not be read".to_string())?;
    let every: Vec<String> = made.reads.iter().chain(made.writes.iter()).cloned().collect();
    let mut record = Record::written(&profile, &sid_text, &every);
    let mut failed: Option<String> = None;
    for (paths, access) in [(&made.reads, calls::FILE_READ), (&made.writes, calls::FILE_WRITE)]
    {
        for path in paths {
            // the ACE is read back from the object itself, so that what
            // the receipt says the container reaches is what it was given
            // and not what this process meant to give it
            if let Some(why) = calls::grant(path, &sid, access).or_else(|| {
                (!calls::has_ace(path, &sid))
                    .then(|| format!("the rights of {path} do not name the container"))
            }) {
                failed = Some(why);
                break;
            }
        }
    }
    let ended = match failed {
        Some(why) => Err(why),
        None => {
            let capabilities: Vec<calls::Sid> =
                made.capabilities.iter().filter_map(|c| calls::sid_of(c)).collect();
            // a trailing backslash before the closing quote would escape
            // it, and the request is one line, so it ends with one
            let dir = install_dir.trim_end_matches(['\\', '/']);
            let command =
                format!("\"{exe}\" exec --install-dir \"{dir}\" --contained {sid_text}");
            let mut line = request.trim_end_matches(['\r', '\n']).to_string();
            line.push('\n');
            // once the child is started this process never runs the
            // program itself: there would be two runs and two answers
            calls::start(&exe, &command, &sid, &capabilities).map(|mut child| {
                let mut to_child = child.stdin();
                let handed = to_child
                    .write_all(line.as_bytes())
                    .and_then(|()| to_child.flush())
                    .is_ok();
                if handed {
                    // the rest of this process's standard input is the
                    // run's: its answers, and its end, which the run reads
                    // as a parent gone. The thread is left to the process's
                    // end - it is blocked on a read nobody can wake.
                    let _ = std::thread::Builder::new().spawn(move || {
                        let stdin = std::io::stdin();
                        let _ = std::io::copy(&mut stdin.lock(), &mut to_child);
                    });
                } else {
                    drop(to_child); // the child reads the end and says so
                }
                u8::try_from(child.wait() & 0xFF).unwrap_or(1)
            })
        }
    };
    let mut left: Vec<&String> = Vec::new();
    for path in &every {
        if calls::revoke(path, &sid).is_some() {
            left.push(path);
        }
    }
    // an ACE this run could not take back stays in the record, so that the
    // next run's sweep takes it: the profile is deleted either way, and
    // its SID is then one nothing can hold again
    if left.is_empty() {
        record.done();
    }
    calls::delete_profile(&profile);
    ended
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
    fn the_loopback_names_are_the_ones_windows_isolates() {
        for host in ["localhost", "LOCALHOST", "127.0.0.1", "127.1.2.3", "::1", "[::1]"] {
            assert!(loopback(host), "{host}");
        }
        for host in ["example.com", "1.1.1.1", "localhost.example.com", "127.example.com"] {
            assert!(!loopback(host), "{host}");
        }
    }

    #[test]
    fn a_loopback_grant_leaves_the_container_off_and_says_so() {
        let off = left_off(&policy_of("io,net:localhost:8080"), &Extras::default());
        assert!(off.as_deref().is_some_and(|w| w.contains("loopback")), "{off:?}");
        // a host outside the machine is reachable with the capability
        assert_eq!(
            left_off(&policy_of("io,net:api.example.com:443"), &Extras::default()),
            None
        );
        assert_eq!(left_off(&policy_of("io,net"), &Extras::default()), None);
        assert_eq!(left_off(&policy_of("io"), &Extras::default()), None);
    }

    #[test]
    fn a_budget_that_restricts_neither_direction_leaves_it_off() {
        let off = left_off(&policy_of("io,fs:read"), &Extras::default());
        assert!(
            off.as_deref().is_some_and(|w| w.contains("does not restrict reads")),
            "{off:?}"
        );
        let off = left_off(&policy_of("io,fs:write"), &Extras::default());
        assert!(
            off.as_deref().is_some_and(|w| w.contains("does not restrict writes")),
            "{off:?}"
        );
        let extras = Extras { read_any: true, ..Extras::default() };
        assert!(left_off(&policy_of("io"), &extras).is_some());
    }

    #[test]
    fn the_plan_grants_the_budgets_paths_and_the_runs_own_files() {
        let dir = std::env::temp_dir().join(format!("sabline-plan-{}", std::process::id()));
        let out = dir.join("out");
        std::fs::create_dir_all(&out).expect("a directory");
        let program = dir.join("p.vel");
        std::fs::write(&program, "fn main() uses io {}\n").expect("a file");
        let allow = format!(
            "io,fs:read:{},fs:write:{}",
            dir.to_string_lossy().replace('\\', "/"),
            out.to_string_lossy().replace('\\', "/")
        );
        let extras =
            Extras { reads: vec![program.to_string_lossy().to_string()], ..Extras::default() };
        let made = plan(&policy_of(&allow), &extras);
        let has = |paths: &[String], want: &std::path::Path| {
            let want = crate::pypath::os_path::normcase(&crate::pypath::realpath(
                &want.to_string_lossy(),
            ));
            paths.iter().any(|p| crate::pypath::os_path::normcase(p) == want)
        };
        assert!(has(&made.reads, &program), "the program: {made:?}");
        assert!(has(&made.writes, &out), "the write grant: {made:?}");
        // the read grant is the directory the write grant is under, and a
        // path granted both ways is written, which carries the read
        assert!(has(&made.reads, &dir) || has(&made.writes, &dir), "{made:?}");
        assert!(made.capabilities.is_empty(), "no net grant, no capability");
        assert!(made.wider.is_empty() && made.wider_reads.is_empty(), "{made:?}");
        let with_net = plan(&policy_of("io,net:api.example.com:443"), &Extras::default());
        assert_eq!(with_net.capabilities, vec![INTERNET_CLIENT]);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn a_write_grant_that_is_not_there_yet_is_held_to_the_nearest_directory() {
        let dir = std::env::temp_dir().join(format!("sabline-plan2-{}", std::process::id()));
        std::fs::create_dir_all(&dir).expect("a directory");
        let later = dir.join("not-yet").join("made.txt");
        let allow = format!("io,fs:write:{}", later.to_string_lossy().replace('\\', "/"));
        let made = plan(&policy_of(&allow), &Extras::default());
        assert_eq!(made.wider.len(), 1, "{made:?}");
        assert!(made.wider[0].contains("does not exist yet"), "{made:?}");
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn a_profile_name_is_this_runs_and_fits_what_windows_takes() {
        let name = profile_name(4242, 0x1234_5678_9ABC_DEF0);
        assert!(name.len() <= 64, "{name}");
        assert!(
            name.chars().all(|c| c.is_ascii_alphanumeric() || ".-_".contains(c)),
            "{name}"
        );
        assert_ne!(name, profile_name(4243, 0x1234_5678_9ABC_DEF0));
        assert_ne!(name, profile_name(4242, 0x1234_5678_9ABC_DEF1));
    }

    #[cfg(windows)]
    #[test]
    fn this_process_is_not_in_a_container() {
        // the suite runs outside one, so the kernel's answer is no - which
        // is what keeps `--contained` from being a claim anyone can make
        assert_eq!(already_contained(), None);
        let why = in_a_container("S-1-15-2-1-2-3").expect_err("no container here");
        assert!(why.contains("not an AppContainer's"), "{why}");
    }

    #[cfg(windows)]
    #[test]
    fn the_profile_is_made_granted_and_taken_back() {
        // the whole life of one run's container, without the run: a
        // profile, an ACE on a directory of this test's own, the ACE taken
        // back, and the profile deleted. What the container then holds a
        // process to is check_confine.py's to measure.
        let dir = std::env::temp_dir().join(format!("sabline-ace-{}", std::process::id()));
        std::fs::create_dir_all(&dir).expect("a directory");
        let path = dir.to_string_lossy().to_string();
        let profile = profile_name(std::process::id(), 7);
        let sid = calls::make_profile(&profile).expect("a profile");
        let text = calls::sid_text(sid.raw).expect("its SID");
        assert!(text.starts_with("S-1-15-2-"), "an AppContainer SID: {text}");
        assert_eq!(calls::grant(&path, &sid, calls::FILE_READ), None);
        assert!(calls::has_ace(&path, &sid), "the ACE is on the directory");
        assert_eq!(calls::revoke(&path, &sid), None);
        assert!(!calls::has_ace(&path, &sid), "the ACE is gone");
        // a path that is not there is a reason, not a crash
        assert!(calls::grant(&dir.join("gone").to_string_lossy(), &sid, calls::FILE_READ)
            .is_some());
        calls::delete_profile(&profile);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[cfg(windows)]
    #[test]
    fn a_record_of_a_live_run_is_left_alone_and_a_dead_ones_is_swept() {
        // the liveness test the sweep rests on: a record held open with no
        // sharing cannot be opened, and one nobody holds can
        use std::os::windows::fs::OpenOptionsExt;
        let profile = profile_name(std::process::id(), 11);
        let mut record = Record::written(&profile, "S-1-15-2-1-2-3", &[]);
        assert!(record.held.is_some(), "the record was written");
        let openable =
            || std::fs::OpenOptions::new().read(true).share_mode(0).open(&record.path).is_ok();
        assert!(!openable(), "a live run's record is held");
        record.held = None;
        assert!(openable(), "a record nobody holds is swept");
        record.done();
        assert!(!record.path.exists());
    }
}
