//! The AppContainer spike (plan/9.0.md, risk register item 3).
//!
//! Can a Rust binary with no installation start inside a Windows
//! AppContainer and still do its job, where python.exe cannot? This program
//! measures it. Run as `appcontainer-spike` (the parent) it makes a scratch
//! tree, creates an AppContainer profile, grants the container's SID one
//! directory by adding ACEs at run time, and starts copies of itself inside
//! the container under several conditions. Each copy (`child`) attempts and
//! reports, one line each: reading its own executable; reading, listing and
//! writing inside the granted directory and outside it; a file of the
//! user's and a file of the system's; TCP to the loopback address and to an
//! address outside the machine; starting a process; and its standard input
//! and output. Then the parent takes every ACE back and deletes the profile.
//!
//! It is a measurement, not product code: it has no dependencies, prints
//! what happened, and changes nothing it does not put back.

#![allow(non_snake_case, non_camel_case_types, clippy::upper_case_acronyms)]

use std::ffi::c_void;
use std::fs;
use std::io::{BufRead, BufReader, Read, Write};
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::os::windows::io::FromRawHandle;
use std::path::{Path, PathBuf};
use std::time::Duration;

type HANDLE = *mut c_void;
type BOOL = i32;
type DWORD = u32;
type PSID = *mut c_void;
type HRESULT = i32;
type LPCWSTR = *const u16;
type LPWSTR = *mut u16;

#[repr(C)]
struct SID_AND_ATTRIBUTES {
    Sid: PSID,
    Attributes: DWORD,
}

#[repr(C)]
struct SECURITY_CAPABILITIES {
    AppContainerSid: PSID,
    Capabilities: *mut SID_AND_ATTRIBUTES,
    CapabilityCount: DWORD,
    Reserved: DWORD,
}

#[repr(C)]
struct STARTUPINFOW {
    cb: DWORD,
    lpReserved: LPWSTR,
    lpDesktop: LPWSTR,
    lpTitle: LPWSTR,
    dwX: DWORD,
    dwY: DWORD,
    dwXSize: DWORD,
    dwYSize: DWORD,
    dwXCountChars: DWORD,
    dwYCountChars: DWORD,
    dwFillAttribute: DWORD,
    dwFlags: DWORD,
    wShowWindow: u16,
    cbReserved2: u16,
    lpReserved2: *mut u8,
    hStdInput: HANDLE,
    hStdOutput: HANDLE,
    hStdError: HANDLE,
}

#[repr(C)]
struct STARTUPINFOEXW {
    StartupInfo: STARTUPINFOW,
    lpAttributeList: *mut c_void,
}

#[repr(C)]
struct PROCESS_INFORMATION {
    hProcess: HANDLE,
    hThread: HANDLE,
    dwProcessId: DWORD,
    dwThreadId: DWORD,
}

#[repr(C)]
struct SECURITY_ATTRIBUTES {
    nLength: DWORD,
    lpSecurityDescriptor: *mut c_void,
    bInheritHandle: BOOL,
}

#[repr(C)]
struct TRUSTEE_W {
    pMultipleTrustee: *mut TRUSTEE_W,
    MultipleTrusteeOperation: u32,
    TrusteeForm: u32,
    TrusteeType: u32,
    ptstrName: LPWSTR,
}

#[repr(C)]
struct EXPLICIT_ACCESS_W {
    grfAccessPermissions: DWORD,
    grfAccessMode: u32,
    grfInheritance: DWORD,
    Trustee: TRUSTEE_W,
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
        si: *mut STARTUPINFOW,
        pi: *mut PROCESS_INFORMATION,
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
        retsize: *mut usize,
    ) -> BOOL;
    fn DeleteProcThreadAttributeList(list: *mut c_void);
    fn CloseHandle(h: HANDLE) -> BOOL;
    fn WaitForSingleObject(h: HANDLE, ms: DWORD) -> DWORD;
    fn GetExitCodeProcess(h: HANDLE, code: *mut DWORD) -> BOOL;
    fn TerminateProcess(h: HANDLE, code: u32) -> BOOL;
    fn CreatePipe(r: *mut HANDLE, w: *mut HANDLE, sa: *mut SECURITY_ATTRIBUTES, size: DWORD) -> BOOL;
    fn SetHandleInformation(h: HANDLE, mask: DWORD, flags: DWORD) -> BOOL;
    fn GetLastError() -> DWORD;
    fn LocalFree(p: *mut c_void) -> *mut c_void;
    fn GetCurrentProcessId() -> DWORD;
}

#[link(name = "userenv")]
extern "system" {
    fn CreateAppContainerProfile(
        name: LPCWSTR,
        display: LPCWSTR,
        desc: LPCWSTR,
        caps: *mut SID_AND_ATTRIBUTES,
        count: DWORD,
        sid: *mut PSID,
    ) -> HRESULT;
    fn DeleteAppContainerProfile(name: LPCWSTR) -> HRESULT;
    fn DeriveAppContainerSidFromAppContainerName(name: LPCWSTR, sid: *mut PSID) -> HRESULT;
}

#[link(name = "advapi32")]
extern "system" {
    fn ConvertStringSidToSidW(s: LPCWSTR, sid: *mut PSID) -> BOOL;
    fn ConvertSidToStringSidW(sid: PSID, s: *mut LPWSTR) -> BOOL;
    fn FreeSid(sid: PSID) -> *mut c_void;
    fn GetNamedSecurityInfoW(
        name: LPCWSTR,
        objtype: u32,
        info: DWORD,
        owner: *mut PSID,
        group: *mut PSID,
        dacl: *mut *mut c_void,
        sacl: *mut *mut c_void,
        sd: *mut *mut c_void,
    ) -> DWORD;
    fn SetNamedSecurityInfoW(
        name: LPWSTR,
        objtype: u32,
        info: DWORD,
        owner: PSID,
        group: PSID,
        dacl: *mut c_void,
        sacl: *mut c_void,
    ) -> DWORD;
    fn SetEntriesInAclW(
        count: u32,
        entries: *mut EXPLICIT_ACCESS_W,
        old: *mut c_void,
        new: *mut *mut c_void,
    ) -> DWORD;
    fn ConvertStringSecurityDescriptorToSecurityDescriptorW(
        s: LPCWSTR,
        rev: DWORD,
        sd: *mut *mut c_void,
        size: *mut u32,
    ) -> BOOL;
    fn GetSecurityDescriptorSacl(
        sd: *mut c_void,
        present: *mut BOOL,
        sacl: *mut *mut c_void,
        defaulted: *mut BOOL,
    ) -> BOOL;
}

const EXTENDED_STARTUPINFO_PRESENT: DWORD = 0x0008_0000;
const PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES: usize = 0x0002_0009;
const PROC_THREAD_ATTRIBUTE_HANDLE_LIST: usize = 0x0002_0002;
const STARTF_USESTDHANDLES: DWORD = 0x100;
const HANDLE_FLAG_INHERIT: DWORD = 1;
const SE_FILE_OBJECT: u32 = 1;
const DACL_SECURITY_INFORMATION: DWORD = 4;
const LABEL_SECURITY_INFORMATION: DWORD = 0x10;
const GRANT_ACCESS: u32 = 1;
const SUB_CONTAINERS_AND_OBJECTS_INHERIT: DWORD = 3;
const NO_INHERITANCE: DWORD = 0;
const TRUSTEE_IS_SID: u32 = 0;
const TRUSTEE_IS_UNKNOWN: u32 = 0;
const FILE_GENERIC_READ: DWORD = 0x0012_0089;
const FILE_GENERIC_EXECUTE: DWORD = 0x0012_00A0;
const FILE_GENERIC_WRITE: DWORD = 0x0012_0116;
const DELETE: DWORD = 0x0001_0000;
const ALREADY_EXISTS: HRESULT = 0x8007_00B7_u32 as HRESULT;

fn wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}

fn wide_path(p: &Path) -> Vec<u16> {
    wide(&p.to_string_lossy())
}

fn last_error() -> DWORD {
    // SAFETY: GetLastError reads this thread's last-error value.
    unsafe { GetLastError() }
}

fn sid_text(sid: PSID) -> String {
    let mut s: LPWSTR = std::ptr::null_mut();
    // SAFETY: sid is a valid SID; s receives a LocalAlloc'd string we free.
    unsafe {
        if ConvertSidToStringSidW(sid, &mut s) == 0 {
            return format!("<error {}>", last_error());
        }
        let mut n = 0;
        while *s.add(n) != 0 {
            n += 1;
        }
        let out = String::from_utf16_lossy(std::slice::from_raw_parts(s, n));
        LocalFree(s.cast());
        out
    }
}

fn sid_of(text: &str) -> PSID {
    let mut sid: PSID = std::ptr::null_mut();
    let w = wide(text);
    // SAFETY: w is NUL-terminated; sid receives a LocalAlloc'd SID.
    unsafe {
        assert!(ConvertStringSidToSidW(w.as_ptr(), &mut sid) != 0, "sid {text}");
    }
    sid
}

/// The container: its profile made (or found), and its SID.
fn container(name: &str) -> PSID {
    let n = wide(name);
    let d = wide("Sabline AppContainer spike");
    let mut sid: PSID = std::ptr::null_mut();
    // SAFETY: the strings are NUL-terminated; sid receives a SID we own.
    let hr = unsafe {
        CreateAppContainerProfile(n.as_ptr(), d.as_ptr(), d.as_ptr(), std::ptr::null_mut(), 0, &mut sid)
    };
    if hr == ALREADY_EXISTS {
        // SAFETY: as above.
        let hr = unsafe { DeriveAppContainerSidFromAppContainerName(n.as_ptr(), &mut sid) };
        assert!(hr >= 0, "derive the container's SID: {hr:#x}");
    } else {
        assert!(hr >= 0, "CreateAppContainerProfile: {hr:#x}");
    }
    sid
}

fn delete_container(name: &str) {
    let n = wide(name);
    // SAFETY: n is NUL-terminated.
    let hr = unsafe { DeleteAppContainerProfile(n.as_ptr()) };
    println!("  profile {name} deleted: {}", if hr >= 0 { "yes".into() } else { format!("{hr:#x}") });
}

/// A DACL kept to put back: the descriptor GetNamedSecurityInfo gave, and
/// the DACL inside it.
struct Kept {
    path: PathBuf,
    sd: *mut c_void,
    dacl: *mut c_void,
}

fn grant(path: &Path, sid: PSID, access: DWORD, inherit: bool) -> Kept {
    let w = wide_path(path);
    let mut dacl: *mut c_void = std::ptr::null_mut();
    let mut sd: *mut c_void = std::ptr::null_mut();
    // SAFETY: w is NUL-terminated; dacl points into sd, which we free later.
    let rc = unsafe {
        GetNamedSecurityInfoW(
            w.as_ptr(),
            SE_FILE_OBJECT,
            DACL_SECURITY_INFORMATION,
            std::ptr::null_mut(),
            std::ptr::null_mut(),
            &mut dacl,
            std::ptr::null_mut(),
            &mut sd,
        )
    };
    assert_eq!(rc, 0, "GetNamedSecurityInfo({})", path.display());
    let mut ea = EXPLICIT_ACCESS_W {
        grfAccessPermissions: access,
        grfAccessMode: GRANT_ACCESS,
        grfInheritance: if inherit { SUB_CONTAINERS_AND_OBJECTS_INHERIT } else { NO_INHERITANCE },
        Trustee: TRUSTEE_W {
            pMultipleTrustee: std::ptr::null_mut(),
            MultipleTrusteeOperation: 0,
            TrusteeForm: TRUSTEE_IS_SID,
            TrusteeType: TRUSTEE_IS_UNKNOWN,
            ptstrName: sid.cast(),
        },
    };
    let mut new: *mut c_void = std::ptr::null_mut();
    // SAFETY: ea is valid for the call; new receives a LocalAlloc'd ACL.
    let rc = unsafe { SetEntriesInAclW(1, &mut ea, dacl, &mut new) };
    assert_eq!(rc, 0, "SetEntriesInAcl");
    let mut wm = w.clone();
    // SAFETY: wm is NUL-terminated; new is a valid ACL.
    let rc = unsafe {
        SetNamedSecurityInfoW(
            wm.as_mut_ptr(),
            SE_FILE_OBJECT,
            DACL_SECURITY_INFORMATION,
            std::ptr::null_mut(),
            std::ptr::null_mut(),
            new,
            std::ptr::null_mut(),
        )
    };
    assert_eq!(rc, 0, "SetNamedSecurityInfo({})", path.display());
    // SAFETY: new was allocated by SetEntriesInAcl.
    unsafe { LocalFree(new) };
    Kept { path: path.to_path_buf(), sd, dacl }
}

fn put_back(kept: Kept) {
    let mut w = wide_path(&kept.path);
    // SAFETY: the DACL is the one read before the grant, still inside sd.
    let rc = unsafe {
        SetNamedSecurityInfoW(
            w.as_mut_ptr(),
            SE_FILE_OBJECT,
            DACL_SECURITY_INFORMATION,
            std::ptr::null_mut(),
            std::ptr::null_mut(),
            kept.dacl,
            std::ptr::null_mut(),
        )
    };
    println!("  the DACL of {} put back: {}", kept.path.display(), if rc == 0 { "yes".into() } else { format!("error {rc}") });
    // SAFETY: sd was allocated by GetNamedSecurityInfo.
    unsafe { LocalFree(kept.sd) };
}

fn label_low(path: &Path) -> DWORD {
    let s = wide("S:(ML;OICI;NW;;;LW)");
    let mut sd: *mut c_void = std::ptr::null_mut();
    let (mut present, mut defaulted) = (0, 0);
    let mut sacl: *mut c_void = std::ptr::null_mut();
    // SAFETY: s is NUL-terminated; sd is freed below; sacl points into sd.
    unsafe {
        assert!(
            ConvertStringSecurityDescriptorToSecurityDescriptorW(s.as_ptr(), 1, &mut sd, std::ptr::null_mut()) != 0
        );
        assert!(GetSecurityDescriptorSacl(sd, &mut present, &mut sacl, &mut defaulted) != 0);
        let mut w = wide_path(path);
        let rc = SetNamedSecurityInfoW(
            w.as_mut_ptr(),
            SE_FILE_OBJECT,
            LABEL_SECURITY_INFORMATION,
            std::ptr::null_mut(),
            std::ptr::null_mut(),
            std::ptr::null_mut(),
            sacl,
        );
        LocalFree(sd);
        rc
    }
}

struct Child {
    lines: Vec<String>,
    exit: Option<u32>,
    started: Result<(), String>,
}

/// Start `exe child ...args` inside the container, hand it one line on its
/// standard input, and read every line it writes until it exits.
fn run_contained(exe: &Path, args: &[String], sid: PSID, capabilities: &[PSID]) -> Child {
    let mut sa = SECURITY_ATTRIBUTES {
        nLength: std::mem::size_of::<SECURITY_ATTRIBUTES>() as DWORD,
        lpSecurityDescriptor: std::ptr::null_mut(),
        bInheritHandle: 1,
    };
    let (mut in_r, mut in_w, mut out_r, mut out_w) =
        (std::ptr::null_mut(), std::ptr::null_mut(), std::ptr::null_mut(), std::ptr::null_mut());
    // SAFETY: the out-pointers are valid; the handles are closed below.
    unsafe {
        assert!(CreatePipe(&mut in_r, &mut in_w, &mut sa, 0) != 0);
        assert!(CreatePipe(&mut out_r, &mut out_w, &mut sa, 0) != 0);
        SetHandleInformation(in_w, HANDLE_FLAG_INHERIT, 0);
        SetHandleInformation(out_r, HANDLE_FLAG_INHERIT, 0);
    }
    let mut caps: Vec<SID_AND_ATTRIBUTES> =
        capabilities.iter().map(|&c| SID_AND_ATTRIBUTES { Sid: c, Attributes: 0x4 /* SE_GROUP_ENABLED */ }).collect();
    let mut sc = SECURITY_CAPABILITIES {
        AppContainerSid: sid,
        Capabilities: if caps.is_empty() { std::ptr::null_mut() } else { caps.as_mut_ptr() },
        CapabilityCount: caps.len() as DWORD,
        Reserved: 0,
    };
    let mut size = 0usize;
    // SAFETY: the first call asks for the size only.
    unsafe { InitializeProcThreadAttributeList(std::ptr::null_mut(), 2, 0, &mut size) };
    let mut list = vec![0u8; size];
    let mut handles = [in_r, out_w];
    // SAFETY: list is size bytes; sc and handles outlive the attribute list.
    unsafe {
        assert!(InitializeProcThreadAttributeList(list.as_mut_ptr().cast(), 2, 0, &mut size) != 0);
        assert!(
            UpdateProcThreadAttribute(
                list.as_mut_ptr().cast(),
                0,
                PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES,
                (&mut sc as *mut SECURITY_CAPABILITIES).cast(),
                std::mem::size_of::<SECURITY_CAPABILITIES>(),
                std::ptr::null_mut(),
                std::ptr::null_mut(),
            ) != 0
        );
        assert!(
            UpdateProcThreadAttribute(
                list.as_mut_ptr().cast(),
                0,
                PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
                handles.as_mut_ptr().cast(),
                std::mem::size_of_val(&handles),
                std::ptr::null_mut(),
                std::ptr::null_mut(),
            ) != 0
        );
    }
    // SAFETY: an all-zero STARTUPINFOEXW is a valid starting value.
    let mut si: STARTUPINFOEXW = unsafe { std::mem::zeroed() };
    si.StartupInfo.cb = std::mem::size_of::<STARTUPINFOEXW>() as DWORD;
    si.StartupInfo.dwFlags = STARTF_USESTDHANDLES;
    si.StartupInfo.hStdInput = in_r;
    si.StartupInfo.hStdOutput = out_w;
    si.StartupInfo.hStdError = out_w;
    si.lpAttributeList = list.as_mut_ptr().cast();
    let mut cmdline = format!("\"{}\" child", exe.display());
    for a in args {
        cmdline.push_str(&format!(" \"{a}\""));
    }
    let mut cmd = wide(&cmdline);
    let app = wide_path(exe);
    // SAFETY: an all-zero PROCESS_INFORMATION is a valid out-parameter.
    let mut pi: PROCESS_INFORMATION = unsafe { std::mem::zeroed() };
    // SAFETY: every pointer is valid for the call.
    let ok = unsafe {
        CreateProcessW(
            app.as_ptr(),
            cmd.as_mut_ptr(),
            std::ptr::null_mut(),
            std::ptr::null_mut(),
            1,
            EXTENDED_STARTUPINFO_PRESENT,
            std::ptr::null_mut(),
            std::ptr::null(),
            &mut si.StartupInfo,
            &mut pi,
        )
    };
    let err = last_error();
    // SAFETY: list was initialised above; the child holds its own copies of
    // the pipe ends it inherited.
    unsafe {
        DeleteProcThreadAttributeList(list.as_mut_ptr().cast());
        CloseHandle(in_r);
        CloseHandle(out_w);
    }
    if ok == 0 {
        // SAFETY: our ends of the pipes.
        unsafe {
            CloseHandle(in_w);
            CloseHandle(out_r);
        }
        return Child { lines: vec![], exit: None, started: Err(format!("CreateProcess failed: error {err}")) };
    }
    // SAFETY: we own in_w and out_r from here.
    let mut to_child = unsafe { fs::File::from_raw_handle(in_w) };
    let from_child = unsafe { fs::File::from_raw_handle(out_r) };
    let _ = to_child.write_all(b"a line from the parent\n");
    drop(to_child);
    let mut lines = Vec::new();
    for line in BufReader::new(from_child).lines() {
        match line {
            Ok(l) => lines.push(l),
            Err(_) => break,
        }
    }
    let mut code = 0u32;
    // SAFETY: pi holds valid handles we close.
    unsafe {
        if WaitForSingleObject(pi.hProcess, 30_000) != 0 {
            TerminateProcess(pi.hProcess, 99);
        }
        GetExitCodeProcess(pi.hProcess, &mut code);
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
    }
    Child { lines, exit: Some(code), started: Ok(()) }
}

fn attempt(what: &str, r: std::io::Result<String>) {
    match r {
        Ok(more) => println!("{what}: allowed{}", if more.is_empty() { String::new() } else { format!(" ({more})") }),
        Err(e) => println!("{what}: refused ({e})"),
    }
}

fn child(args: &[String]) {
    let granted = PathBuf::from(&args[0]);
    let outside = PathBuf::from(&args[1]);
    let port: u16 = args[2].parse().unwrap();
    let user_file = PathBuf::from(&args[3]);
    attempt("read its own executable", std::env::current_exe().and_then(fs::read).map(|b| format!("{} bytes", b.len())));
    attempt("read a file in the granted directory", fs::read_to_string(granted.join("in.txt")));
    attempt(
        "list the granted directory",
        fs::read_dir(&granted).map(|d| format!("{} entries", d.count())),
    );
    attempt("write a file in the granted directory", fs::write(granted.join("made.txt"), "x").map(|_| String::new()));
    attempt("overwrite a file that was there", fs::write(granted.join("in.txt"), "overwritten").map(|_| String::new()));
    attempt("remove a file that was there", fs::remove_file(granted.join("in.txt")).map(|_| String::new()));
    attempt("read a file outside it", fs::read_to_string(outside.join("out.txt")));
    attempt("list the directory outside it", fs::read_dir(&outside).map(|d| format!("{} entries", d.count())));
    attempt("write a file outside it", fs::write(outside.join("made.txt"), "x").map(|_| String::new()));
    attempt(&format!("read a file of the user's ({})", user_file.display()), fs::read(&user_file).map(|b| format!("{} bytes", b.len())));
    attempt("read C:\\Windows\\win.ini", fs::read(r"C:\Windows\win.ini").map(|b| format!("{} bytes", b.len())));
    attempt("write the user's temporary directory", {
        let t = std::env::temp_dir().join(format!("sabline-spike-{}.txt", std::process::id()));
        fs::write(&t, "x").map(|_| {
            let _ = fs::remove_file(&t);
            t.display().to_string()
        })
    });
    let loopback: SocketAddr = format!("127.0.0.1:{port}").parse().unwrap();
    attempt("TCP to the loopback address", TcpStream::connect_timeout(&loopback, Duration::from_secs(3)).map(|_| String::new()));
    let outside_addr: SocketAddr = "1.1.1.1:443".parse().unwrap();
    attempt("TCP to 1.1.1.1:443", TcpStream::connect_timeout(&outside_addr, Duration::from_secs(5)).map(|_| String::new()));
    attempt(
        "start a process (cmd /c exit 0)",
        std::process::Command::new("cmd").args(["/c", "exit", "0"]).status().map(|s| format!("exit {s}")),
    );
    let mut line = String::new();
    attempt("read standard input", std::io::stdin().read_line(&mut line).map(|_| line.trim_end().to_string()));
    attempt("write standard output", std::io::stdout().flush().map(|_| String::new()));
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.get(1).map(String::as_str) == Some("child") {
        child(&args[2..]);
        return;
    }
    // SAFETY: GetCurrentProcessId has no preconditions.
    let pid = unsafe { GetCurrentProcessId() };
    let name = format!("sabline.spike.{pid}");
    let root = std::env::temp_dir().join(format!("sabline-appcontainer-spike-{pid}"));
    let granted = root.join("granted");
    let outside = root.join("outside");
    let low = root.join("granted-low");
    fs::create_dir_all(&granted).unwrap();
    fs::create_dir_all(&outside).unwrap();
    fs::create_dir_all(&low).unwrap();
    fs::write(granted.join("in.txt"), "inside the grant").unwrap();
    fs::write(low.join("in.txt"), "inside the low grant").unwrap();
    fs::write(outside.join("out.txt"), "outside every grant").unwrap();
    let user_file = PathBuf::from(std::env::var("USERPROFILE").unwrap()).join(".gitconfig");
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();
    std::thread::spawn(move || {
        for s in listener.incoming() {
            drop(s);
        }
    });

    let here = std::env::current_exe().unwrap();
    println!("the parent: {} (pid {pid})", here.display());
    let sid = container(&name);
    println!("the container: {name}, SID {}", sid_text(sid));
    let internet = sid_of("S-1-15-3-1"); // internetClient
    let child_args = |g: &Path| {
        vec![g.display().to_string(), outside.display().to_string(), port.to_string(), user_file.display().to_string()]
    };
    let show = |title: &str, c: Child| {
        println!("\n== {title}");
        match c.started {
            Err(e) => println!("  not started: {e}"),
            Ok(()) => {
                for l in &c.lines {
                    println!("  {l}");
                }
                println!("  (exit {:?})", c.exit);
            }
        }
    };

    // 1. The executable where it was built, nothing granted to it.
    show(
        "1. the executable where it was built; no ACE anywhere; no capability",
        run_contained(&here, &child_args(&granted), sid, &[]),
    );

    // 2. A copy of the executable in a directory of its own, read and
    //    execute granted to the container; the granted directory read only.
    let bin = root.join("bin");
    fs::create_dir_all(&bin).unwrap();
    let copy = bin.join("appcontainer-spike.exe");
    fs::copy(&here, &copy).unwrap();
    let kept_bin = grant(&bin, sid, FILE_GENERIC_READ | FILE_GENERIC_EXECUTE, true);
    let kept_granted = grant(&granted, sid, FILE_GENERIC_READ | FILE_GENERIC_EXECUTE, true);
    show(
        "2. a copy beside an ACE for the container (read, execute); the granted directory: an ACE (read); no capability",
        run_contained(&copy, &child_args(&granted), sid, &[]),
    );

    // 3. The same with the internetClient capability.
    show(
        "3. as 2, with the internetClient capability",
        run_contained(&copy, &child_args(&granted), sid, &[internet]),
    );
    put_back(kept_granted);

    // 4. The granted directory given write as well, without and with a low
    //    integrity label: the container's token is at low integrity, and an
    //    object with no label is medium, which a low token cannot write.
    let kept_rw = grant(&granted, sid, FILE_GENERIC_READ | FILE_GENERIC_WRITE | FILE_GENERIC_EXECUTE | DELETE, true);
    show(
        "4. the granted directory: an ACE (read, write); no label",
        run_contained(&copy, &child_args(&granted), sid, &[]),
    );
    put_back(kept_rw);
    let kept_low = grant(&low, sid, FILE_GENERIC_READ | FILE_GENERIC_WRITE | FILE_GENERIC_EXECUTE | DELETE, true);
    let rc = label_low(&low);
    println!("\n  a low label on {}: {}", low.display(), if rc == 0 { "yes".into() } else { format!("error {rc}") });
    show(
        "5. a directory with an ACE (read, write) and a low label",
        run_contained(&copy, &child_args(&low), sid, &[]),
    );
    put_back(kept_low);

    // 5b. The same on another volume, with no label: is it the label?
    let other = PathBuf::from(format!(r"D:\sabline-appcontainer-spike-{pid}"));
    fs::create_dir_all(&other).unwrap();
    fs::write(other.join("in.txt"), "inside the grant on D:").unwrap();
    let kept_other = grant(&other, sid, FILE_GENERIC_READ | FILE_GENERIC_WRITE | FILE_GENERIC_EXECUTE | DELETE, true);
    show(
        "5b. a directory on another volume (D:), an ACE (read, write), no label",
        run_contained(&copy, &child_args(&other), sid, &[]),
    );
    put_back(kept_other);
    let _ = fs::remove_dir_all(&other);
    fs::write(granted.join("in.txt"), "inside the grant").unwrap();

    // 6. The executable where it was built, with an ACE on that one file.
    let kept_exe = grant(&here, sid, FILE_GENERIC_READ | FILE_GENERIC_EXECUTE, false);
    show(
        "6. the executable where it was built, with an ACE on the file itself (read, execute)",
        run_contained(&here, &child_args(&granted), sid, &[]),
    );
    put_back(kept_exe);
    put_back(kept_bin);

    println!();
    delete_container(&name);
    // SAFETY: both were allocated for us (FreeSid for the profile's SID,
    // LocalFree for ConvertStringSidToSid's).
    unsafe {
        FreeSid(sid);
        LocalFree(internet);
    }
    let _ = fs::remove_dir_all(&root);
    let mut gone = String::new();
    let _ = std::io::stdin().read_to_string(&mut gone);
}
