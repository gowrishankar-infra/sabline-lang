//! Linux's layers (9.0, M4): **Landlock** holds the file system to the
//! `fs:` grants and what the runtime itself reads; **seccomp-bpf** refuses
//! sockets when no `net` is granted, refuses starting a process, and
//! refuses ptrace, mount and the rest of [`DENIED_ALWAYS`].
//!
//! This is `sabline/confine.py`'s `_apply_linux`, ported: the same access
//! bits, the same plan, the same filter, the same words in the report. The
//! masks and the filter are compared with the package's by the agreement
//! gate ([`crate::confine::table_document`]), because a syscall number
//! typed wrong here is a hole that nothing else would find.
//!
//! **Every thread of the process is held.** Landlock holds the thread that
//! restricts itself and the threads it starts afterwards, not its
//! siblings, so a thread that was already running when the run began is a
//! thread the file-system layer does not cover. The run asks each such
//! thread to hold itself with the same ruleset ([`Hold`]), and counts what
//! is left: a thread it could not reach is a gap in the reason, and the
//! level is then `partial` and never `full`. seccomp needs none of that -
//! the filter is installed on every thread of the process at once (TSYNC).
//!
//! Nothing here can be undone. A ruleset entered is entered for the life
//! of the thread, which is why it is entered after the program has been
//! read and checked and before its first statement, and never in a process
//! that runs more than one program.

#![allow(unsafe_code)] // the layers are system calls; rt/README.md's rule

#[cfg(target_os = "linux")]
use std::os::raw::{c_char, c_int, c_long, c_void};

#[cfg(target_os = "linux")]
use crate::confine::{any_net, judge, Held, Report};
use crate::confine::{
    existing, granted, nearest_directory, no_net, spawn, tcp_ports, widened_to_any_host,
    Extras,
};
use crate::json::Json;

/// The layer name a receipt writes for Landlock, with the ABI after it.
pub const LANDLOCK: &str = "landlock";
/// The layer name a receipt writes for the seccomp filter.
pub const SECCOMP: &str = "seccomp";

// ---- Landlock ----------------------------------------------------------------

#[cfg(target_os = "linux")]
mod numbers {
    use super::{c_int, c_long};

    pub const SYS_CREATE_RULESET: c_long = 444;
    pub const SYS_ADD_RULE: c_long = 445;
    pub const SYS_RESTRICT_SELF: c_long = 446;
    pub const CREATE_RULESET_VERSION: c_long = 1;
    pub const RULE_PATH_BENEATH: c_long = 1;
    pub const RULE_NET_PORT: c_long = 2;
    pub const PR_SET_NO_NEW_PRIVS: c_int = 38;
}
#[cfg(target_os = "linux")]
use numbers::*;

const FS_EXECUTE: u64 = 1 << 0;
const FS_WRITE_FILE: u64 = 1 << 1;
const FS_READ_FILE: u64 = 1 << 2;
const FS_READ_DIR: u64 = 1 << 3;
const FS_REMOVE_DIR: u64 = 1 << 4;
const FS_REMOVE_FILE: u64 = 1 << 5;
const FS_MAKE_REG: u64 = 1 << 8;
/// char, dir, reg, sock, fifo, block and sym: bits 6 to 12.
const FS_MAKE_ALL: u64 = 0x1fc0;
/// ABI 2.
const FS_REFER: u64 = 1 << 13;
/// ABI 3.
const FS_TRUNCATE: u64 = 1 << 14;
/// ABI 4.
const NET_BIND_TCP: u64 = 1 << 0;
const NET_CONNECT_TCP: u64 = 1 << 1;

/// `O_PATH`, which opens a name without asking for permission on what it
/// names: the same number on the machines the filter has a table for, and
/// 0 where it is not known - as `getattr(os, "O_PATH", 0)` is in the
/// package.
#[cfg(all(target_os = "linux", any(target_arch = "x86_64", target_arch = "aarch64")))]
const O_PATH: c_int = 0o10000000;
#[cfg(all(target_os = "linux", not(any(target_arch = "x86_64", target_arch = "aarch64"))))]
const O_PATH: c_int = 0;
#[cfg(all(target_os = "linux", any(target_arch = "x86_64", target_arch = "aarch64")))]
const O_CLOEXEC: c_int = 0o2000000;
#[cfg(all(target_os = "linux", not(any(target_arch = "x86_64", target_arch = "aarch64"))))]
const O_CLOEXEC: c_int = 0;

#[cfg(target_os = "linux")]
#[repr(C)]
struct RulesetAttr {
    handled_access_fs: u64,
    handled_access_net: u64,
    scoped: u64,
}

#[cfg(target_os = "linux")]
#[repr(C, packed)]
struct PathBeneath {
    allowed_access: u64,
    parent_fd: i32,
}

#[cfg(target_os = "linux")]
#[repr(C)]
struct NetPort {
    allowed_access: u64,
    port: u64,
}

#[cfg(target_os = "linux")]
extern "C" {
    fn syscall(number: c_long, ...) -> c_long;
    fn prctl(option: c_int, ...) -> c_int;
    fn open(path: *const c_char, flags: c_int, ...) -> c_int;
    fn close(fd: c_int) -> c_int;
}

#[cfg(target_os = "linux")]
/// `errno` after a call that failed, as the standard library reads it.
fn errno() -> i32 {
    std::io::Error::last_os_error().raw_os_error().unwrap_or(0)
}

#[cfg(target_os = "linux")]
/// The Landlock ABI this kernel offers, or 0 for none.
pub fn landlock_abi() -> u32 {
    if !cfg!(target_os = "linux") {
        return 0;
    }
    // SAFETY: landlock_create_ruleset with a null attribute, a size of 0
    // and the VERSION flag asks the kernel for its ABI and changes nothing
    // about this thread; a kernel without Landlock answers ENOSYS, which is
    // a negative return and not a fault.
    // test: landlock_abi_is_a_version_and_restricts_nothing.
    let abi = unsafe {
        syscall(
            SYS_CREATE_RULESET,
            std::ptr::null::<c_void>(),
            0_usize,
            CREATE_RULESET_VERSION,
        )
    };
    if abi > 0 {
        u32::try_from(abi).unwrap_or(0)
    } else {
        0
    }
}

/// What a Landlock ruleset for a policy handles and allows.
pub struct Plan {
    /// The file-system rights the ruleset handles; what it handles and does
    /// not allow beneath some path is refused.
    pub handled: u64,
    /// Each path and the rights allowed beneath it.
    pub rules: Vec<(String, u64)>,
    /// The write grants that are not there yet, each held to the nearest
    /// directory that is, said as the level's reason says it.
    pub wider: Vec<String>,
    /// The read grants that are not there yet, likewise.
    pub wider_reads: Vec<String>,
    /// Whether reads are held at all.
    pub hold_reads: bool,
    /// The network rights the ruleset handles (ABI 4 and later).
    pub net_handled: u64,
    /// The TCP ports it allows a connection to.
    pub net_rules: Vec<u32>,
    /// Landlock ABI 6's scopes, which are not asked for: the seccomp filter
    /// already refuses an abstract Unix socket and a signal to another
    /// process, and a kernel before 6.15 refuses a signal between two
    /// threads of one process that restricted themselves separately.
    pub scoped: u64,
}

/// What a plan for this policy and ABI handles, with no path in it:
/// `(handled, net_handled, net_rules, hold_reads)`. The paths are this
/// machine's; these four are not, which is what the agreement gate
/// compares.
pub fn plan_masks(policy: &Json, abi: u32) -> (u64, u64, Vec<u32>, bool) {
    let plan = plan(policy, abi, &Extras::default());
    (plan.handled, plan.net_handled, plan.net_rules, plan.hold_reads)
}

/// What Landlock is asked to handle and to allow, for this policy.
pub fn plan(policy: &Json, abi: u32, extras: &Extras) -> Plan {
    let write_all = FS_WRITE_FILE
        | FS_REMOVE_DIR
        | FS_REMOVE_FILE
        | FS_MAKE_ALL
        | if abi >= 2 { FS_REFER } else { 0 }
        | if abi >= 3 { FS_TRUNCATE } else { 0 };
    let write_grant = FS_WRITE_FILE | FS_MAKE_REG | if abi >= 3 { FS_TRUNCATE } else { 0 };
    let read_all = FS_READ_FILE | FS_READ_DIR;
    let mut handled = if spawn(policy) { 0 } else { FS_EXECUTE };
    let mut rules: Vec<(String, u64)> = Vec::new();
    let mut wider: Vec<String> = Vec::new();
    let mut wider_reads: Vec<String> = Vec::new();
    let reads = granted(policy, "fs_read");
    let writes = granted(policy, "fs_write");
    let hold_reads = reads.is_some() && !extras.read_any;
    if hold_reads {
        handled |= read_all;
        for place in runtime_reads(!no_net(policy)) {
            rules.push((place, read_all));
        }
        for place in existing(&extras.reads) {
            rules.push((place, read_all));
        }
        for grant in reads.as_deref().unwrap_or(&[]) {
            // a program may read back what it has just written: a granted
            // path that is not there yet is held to the nearest directory
            // that is, as a write grant is, and the level says so
            let (nearest, widened) = nearest_directory(grant);
            let Some(nearest) = nearest else { continue };
            if widened {
                wider_reads.push(format!(
                    "{grant} does not exist yet, so reads are held to {nearest}"
                ));
            }
            rules.push((nearest, read_all));
        }
    }
    if let Some(writes) = writes.as_deref() {
        handled |= write_all;
        for grant in writes {
            let (nearest, widened) = nearest_directory(grant);
            let Some(nearest) = nearest else { continue };
            if widened {
                wider.push(format!(
                    "{grant} does not exist yet, so writes are held to {nearest}"
                ));
            }
            rules.push((nearest, write_grant));
        }
        for place in existing(&extras.writes) {
            rules.push((place, write_grant));
        }
        if crate::pypath::exists("/dev/null") {
            rules.push(("/dev/null".to_string(), FS_WRITE_FILE));
        }
    }
    if let Some(temp) = &extras.temp {
        rules.push((temp.clone(), write_all | read_all));
    }
    let mut net_handled = 0;
    let mut net_rules = Vec::new();
    if abi >= 4 && no_net(policy) {
        net_handled = NET_BIND_TCP | NET_CONNECT_TCP;
    } else if abi >= 4 {
        if let Some(ports) = tcp_ports(policy) {
            net_handled = NET_BIND_TCP | NET_CONNECT_TCP;
            net_rules = ports;
        }
    }
    Plan { handled, rules, wider, wider_reads, hold_reads, net_handled, net_rules, scoped: 0 }
}

#[cfg(target_os = "linux")]
/// Build the ruleset and hold **this thread** - and the threads it starts
/// after - with it. `None`, or why it failed, and then nothing was applied.
pub fn restrict(plan: &Plan, abi: u32) -> Option<String> {
    let attr = RulesetAttr {
        handled_access_fs: plan.handled,
        handled_access_net: plan.net_handled,
        scoped: plan.scoped,
    };
    // the size names the prefix of the attribute this ABI reads: one field
    // before ABI 4, two from it
    let size: usize = if abi < 4 { 8 } else { 16 };
    // SAFETY: `attr` is a live RulesetAttr of three u64 and `size` is 8 or
    // 16, both inside it, which is what the kernel copies; the call makes a
    // descriptor and holds nothing yet.
    // test: a_ruleset_is_built_without_entering_it.
    let fd = unsafe {
        syscall(
            SYS_CREATE_RULESET,
            &attr as *const RulesetAttr as *const c_void,
            size,
            0_usize,
        )
    };
    if fd < 0 {
        return Some(format!("landlock_create_ruleset: errno {}", errno()));
    }
    let fd = fd as c_int;
    let mut failed = add_rules(fd, plan);
    if failed.is_none() {
        // no_new_privs first: landlock_restrict_self answers EPERM without it
        // SAFETY: prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) takes five scalars
        // and sets one bit of this process's own state.
        // test: no_new_privs_is_set_before_the_ruleset_is_entered.
        if unsafe { prctl(PR_SET_NO_NEW_PRIVS, 1_usize, 0_usize, 0_usize, 0_usize) } != 0 {
            failed = Some(format!("PR_SET_NO_NEW_PRIVS: errno {}", errno()));
        }
    }
    if failed.is_none() {
        // SAFETY: `fd` is a ruleset descriptor this function made and has
        // not closed; the call holds the calling thread to it, and cannot
        // be undone, which is what it is for.
        // test: no_new_privs_is_set_before_the_ruleset_is_entered.
        if unsafe { syscall(SYS_RESTRICT_SELF, fd as c_long, 0_usize) } != 0 {
            failed = Some(format!("landlock_restrict_self: errno {}", errno()));
        }
    }
    close_fd(fd);
    failed
}

#[cfg(target_os = "linux")]
fn close_fd(fd: c_int) {
    // SAFETY: `fd` came from a call in this module that answered a
    // descriptor, and is closed once, here.
    // test: a_ruleset_is_built_without_entering_it.
    unsafe { close(fd) };
}

#[cfg(target_os = "linux")]
/// Add every rule of the plan to the ruleset. `None`, or the first failure.
fn add_rules(fd: c_int, plan: &Plan) -> Option<String> {
    for (place, access) in &plan.rules {
        let mut name = place.clone().into_bytes();
        name.push(0);
        let parent = {
            // SAFETY: `name` holds this path's bytes with a NUL after them
            // and outlives the call, so the pointer is to a C string;
            // O_PATH asks for no permission on what the name names.
            // test: a_path_that_is_not_there_is_left_out_of_the_ruleset.
            unsafe { open(name.as_ptr() as *const c_char, O_PATH | O_CLOEXEC) }
        };
        if parent < 0 {
            continue; // gone, or not ours to open
        }
        let mut allowed = *access;
        if !std::path::Path::new(place).is_dir() {
            // a file takes the rights of a file and not of a directory
            allowed &= FS_EXECUTE | FS_WRITE_FILE | FS_READ_FILE | FS_TRUNCATE;
        }
        allowed &= plan.handled;
        if allowed == 0 {
            close_fd(parent);
            continue;
        }
        let rule = PathBeneath { allowed_access: allowed, parent_fd: parent };
        // SAFETY: `rule` is a live, packed landlock_path_beneath_attr whose
        // descriptor is open for the length of the call; the kernel copies
        // it and keeps no pointer into this process.
        // test: a_read_grant_is_in_the_ruleset_and_its_sibling_is_not.
        let added = unsafe {
            syscall(
                SYS_ADD_RULE,
                fd as c_long,
                RULE_PATH_BENEATH,
                &rule as *const PathBeneath as *const c_void,
                0_usize,
            )
        };
        close_fd(parent);
        if added != 0 {
            return Some(format!("landlock_add_rule({place}): errno {}", errno()));
        }
    }
    for port in &plan.net_rules {
        let rule = NetPort { allowed_access: NET_CONNECT_TCP, port: u64::from(*port) };
        // SAFETY: `rule` is a live landlock_net_port_attr of two u64, which
        // the kernel copies; a port rule is only ever added from ABI 4,
        // where the kernel knows the rule type.
        // test: a_port_rule_is_added_only_from_abi_four.
        let added = unsafe {
            syscall(
                SYS_ADD_RULE,
                fd as c_long,
                RULE_NET_PORT,
                &rule as *const NetPort as *const c_void,
                0_usize,
            )
        };
        if added != 0 {
            return Some(format!("landlock_add_rule(port {port}): errno {}", errno()));
        }
    }
    None
}

/// What sabline-rt itself must be able to read to keep running once the
/// policy is applied.
///
/// A runtime that is one static binary needs almost nothing: its image is
/// already mapped, it holds no interpreter and loads no library after the
/// program has been read. What is left is the few names it does ask the
/// kernel for - the thread list it counts, and the devices a seed and a
/// discarded output use. `sabline/confine.py`'s `interpreter_reads` is the
/// same list for a process that *is* a Python installation, which is why
/// that one is forty entries and this is four.
///
/// **Under a `net` grant the resolver's own names are here**, because from
/// 9.0's M4 an `http` request is made in this process and a host name has
/// to be turned into an address before a socket can go to it
/// ([`crate::net`]). `getaddrinfo` is glibc's, and glibc loads its name
/// service modules when it is first asked - so the loader's cache and the
/// library directories are needed as well as `/etc/hosts` and
/// `/etc/resolv.conf`. Without them a name does not resolve and a run is
/// refused a host its budget grants, which the Linux leg of
/// `check_confine.py` is what found.
///
/// The TLS roots are **not** here: the bytes of an `https` exchange are
/// still the host's, and this process opens no TLS connection. They belong
/// here on the day it does (plan/9.0.md, M5).
///
/// It is still narrower than `interpreter_reads`, which grants the library
/// directories to every run because a Python process cannot start without
/// them: here they are granted only to a run whose budget grants the
/// network.
pub fn runtime_reads(net: bool) -> Vec<String> {
    let mut places = vec![
        "/proc/self".to_string(),
        "/dev/null".to_string(),
        "/dev/urandom".to_string(),
        "/dev/random".to_string(),
    ];
    if net {
        places.extend(
            [
                // what glibc's resolver reads
                "/etc/resolv.conf",
                "/etc/hosts",
                "/etc/nsswitch.conf",
                "/etc/gai.conf",
                "/etc/host.conf",
                "/etc/services",
                "/etc/protocols",
                "/run/systemd/resolve",
                "/run/resolvconf",
                "/mnt/wsl/resolv.conf",
                "/var/run/nscd",
                // and what it needs to load its name service modules
                "/etc/ld.so.cache",
                "/etc/ld.so.conf",
                "/etc/ld.so.conf.d",
                "/lib",
                "/lib64",
                "/usr/lib",
                "/usr/lib64",
                "/usr/local/lib",
            ]
            .map(str::to_string),
        );
    }
    existing(&places)
}

// ---- seccomp-bpf -------------------------------------------------------------

const AUDIT_ARCH_X86_64: u32 = 0xC000_003E;
const AUDIT_ARCH_AARCH64: u32 = 0xC000_00B7;
#[cfg(target_os = "linux")]
const SECCOMP_SET_MODE_FILTER: usize = 1;
#[cfg(target_os = "linux")]
const SECCOMP_FILTER_FLAG_TSYNC: usize = 1;
const RET_KILL_PROCESS: u32 = 0x8000_0000;
const RET_ALLOW: u32 = 0x7FFF_0000;
const RET_ERRNO: u32 = 0x0005_0000;
const EPERM: u32 = 1;
const ENOSYS: u32 = 38;
const CLONE_THREAD: u32 = 0x0001_0000;
const X32_BIT: u32 = 0x4000_0000;
const AF_INET: u32 = 2;
const AF_INET6: u32 = 10;
const AF_NETLINK: u32 = 16;
const TIOCSTI: u32 = 0x5412;
const TIOCLINUX: u32 = 0x541C;

/// The system calls the filter answers, by name, on x86_64. Sorted by
/// name, because [`number`] looks one up by binary search. The numbers are
/// `sabline/confine.py`'s `_SYSCALLS`, and the agreement gate compares the
/// whole filter rather than this table, so a number typed wrong here is a
/// difference and not a hole.
#[rustfmt::skip]
pub const SYSCALLS_X86_64: &[(&str, u32)] = &[
    ("accept", 43), ("accept4", 288), ("acct", 163), ("add_key", 248), ("adjtimex", 159),
    ("bind", 49), ("bpf", 321), ("chroot", 161), ("clock_adjtime", 305),
    ("clock_settime", 227), ("clone", 56), ("clone3", 435), ("connect", 42),
    ("delete_module", 176), ("execve", 59), ("execveat", 322), ("finit_module", 313),
    ("fork", 57), ("fsconfig", 431), ("fsmount", 432), ("fsopen", 430), ("fspick", 433),
    ("init_module", 175), ("io_uring_enter", 426), ("io_uring_register", 427),
    ("io_uring_setup", 425), ("ioctl", 16), ("kexec_file_load", 320), ("kexec_load", 246),
    ("keyctl", 250), ("kill", 62), ("listen", 50), ("mount", 165), ("mount_setattr", 442),
    ("move_mount", 429), ("name_to_handle_at", 303), ("open_by_handle_at", 304),
    ("open_tree", 428), ("perf_event_open", 298), ("personality", 135), ("pidfd_getfd", 438),
    ("pidfd_send_signal", 424), ("pivot_root", 155), ("process_madvise", 440),
    ("process_vm_readv", 310), ("process_vm_writev", 311), ("ptrace", 101), ("quotactl", 179),
    ("reboot", 169), ("request_key", 249), ("rt_sigqueueinfo", 129),
    ("rt_tgsigqueueinfo", 297), ("setns", 308), ("settimeofday", 164), ("socket", 41),
    ("socketpair", 53), ("swapoff", 168), ("swapon", 167), ("tgkill", 234), ("tkill", 200),
    ("umount2", 166), ("unshare", 272), ("userfaultfd", 323), ("vfork", 58),
];

/// The same table for aarch64, which has no `fork` and no `vfork`.
#[rustfmt::skip]
pub const SYSCALLS_AARCH64: &[(&str, u32)] = &[
    ("accept", 202), ("accept4", 242), ("acct", 89), ("add_key", 217), ("adjtimex", 171),
    ("bind", 200), ("bpf", 280), ("chroot", 51), ("clock_adjtime", 266),
    ("clock_settime", 112), ("clone", 220), ("clone3", 435), ("connect", 203),
    ("delete_module", 106), ("execve", 221), ("execveat", 281), ("finit_module", 273),
    ("fsconfig", 431), ("fsmount", 432), ("fsopen", 430), ("fspick", 433),
    ("init_module", 105), ("io_uring_enter", 426), ("io_uring_register", 427),
    ("io_uring_setup", 425), ("ioctl", 29), ("kexec_file_load", 294), ("kexec_load", 104),
    ("keyctl", 219), ("kill", 129), ("listen", 201), ("mount", 40), ("mount_setattr", 442),
    ("move_mount", 429), ("name_to_handle_at", 264), ("open_by_handle_at", 265),
    ("open_tree", 428), ("perf_event_open", 241), ("personality", 92), ("pidfd_getfd", 438),
    ("pidfd_send_signal", 424), ("pivot_root", 41), ("process_madvise", 440),
    ("process_vm_readv", 270), ("process_vm_writev", 271), ("ptrace", 117), ("quotactl", 60),
    ("reboot", 142), ("request_key", 218), ("rt_sigqueueinfo", 138),
    ("rt_tgsigqueueinfo", 240), ("setns", 268), ("settimeofday", 170), ("socket", 198),
    ("socketpair", 199), ("swapoff", 225), ("swapon", 224), ("tgkill", 131), ("tkill", 130),
    ("umount2", 39), ("unshare", 97), ("userfaultfd", 282),
];

/// The system calls refused when a budget grants no `net`.
pub const DENIED_WITHOUT_NET: &[&str] =
    &["socket", "socketpair", "connect", "bind", "listen", "accept", "accept4"];

/// The system calls refused because no budget grants starting a process.
pub const DENIED_WITHOUT_SPAWN: &[&str] = &["execve", "execveat", "fork", "vfork"];

/// The system calls refused whatever the budget grants: reaching into
/// another process, changing the machine, loading code into the kernel.
#[rustfmt::skip]
pub const DENIED_ALWAYS: &[&str] = &[
    "ptrace", "personality", "pivot_root", "adjtimex", "chroot", "acct", "settimeofday",
    "mount", "umount2", "swapon", "swapoff", "reboot", "init_module", "delete_module",
    "quotactl", "clock_settime", "kexec_load", "add_key", "request_key", "keyctl", "unshare",
    "perf_event_open", "name_to_handle_at", "open_by_handle_at", "clock_adjtime", "setns",
    "process_vm_readv", "process_vm_writev", "finit_module", "kexec_file_load", "bpf",
    "userfaultfd", "io_uring_setup", "io_uring_enter", "io_uring_register", "open_tree",
    "move_mount", "fsopen", "fsconfig", "fsmount", "fspick", "pidfd_getfd",
    "process_madvise", "mount_setattr", "tkill", "pidfd_send_signal",
];

/// The table for one machine name, or `None` when there is none.
pub fn syscalls(arch: &str) -> Option<&'static [(&'static str, u32)]> {
    match arch {
        "x86_64" => Some(SYSCALLS_X86_64),
        "aarch64" => Some(SYSCALLS_AARCH64),
        _ => None,
    }
}

fn number(table: &[(&str, u32)], name: &str) -> Option<u32> {
    table.binary_search_by(|(n, _)| (*n).cmp(name)).ok().map(|at| table[at].1)
}

/// One BPF instruction, as the kernel reads it.
#[repr(C)]
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Filter {
    /// The operation.
    pub code: u16,
    /// Where to jump when the test is true.
    pub jt: u8,
    /// Where to jump when it is false.
    pub jf: u8,
    /// The operand.
    pub k: u32,
}

#[cfg(target_os = "linux")]
#[repr(C)]
struct Fprog {
    len: u16,
    filter: *const Filter,
}

/// The machine name seccomp's tables know this process as, or `None`.
pub fn seccomp_arch() -> Option<&'static str> {
    if !cfg!(target_os = "linux")
        || cfg!(target_endian = "big")
        || std::mem::size_of::<usize>() != 8
    {
        return None;
    }
    match std::env::consts::ARCH {
        "x86_64" => Some("x86_64"),
        "aarch64" => Some("aarch64"),
        _ => None,
    }
}

/// The BPF program for a policy: anything it does not name is allowed, and
/// what it names answers EPERM, so the run can say which layer refused.
///
/// `pid` is the one process a signal may be sent to - this one, and nothing
/// else. Pure, and compared with `sabline/confine.py`'s `seccomp_program`
/// by the agreement gate.
pub fn seccomp_program(policy: &Json, arch: &str, pid: u32) -> Vec<Filter> {
    const LD: u16 = 0x20;
    const JEQ: u16 = 0x15;
    const JGE: u16 = 0x35;
    const JSET: u16 = 0x45;
    const RET: u16 = 0x06;
    const NR: u32 = 0;
    const ARCH: u32 = 4;
    const ARG0_LO: u32 = 16;
    const ARG0_HI: u32 = 20;
    const ARG1_LO: u32 = 24;
    let Some(table) = syscalls(arch) else { return Vec::new() };
    let audit = if arch == "x86_64" { AUDIT_ARCH_X86_64 } else { AUDIT_ARCH_AARCH64 };
    let eperm = RET_ERRNO | EPERM;
    let enosys = RET_ERRNO | ENOSYS;
    let at = |code: u16, jt: u8, jf: u8, k: u32| Filter { code, jt, jf, k };
    let mut prog = vec![
        at(LD, 0, 0, ARCH),
        at(JEQ, 1, 0, audit),
        at(RET, 0, 0, RET_KILL_PROCESS),
        at(LD, 0, 0, NR),
    ];
    if arch == "x86_64" {
        // the x32 numbers name other calls
        prog.extend([at(JGE, 0, 1, X32_BIT), at(RET, 0, 0, enosys)]);
    }
    let mut denied: Vec<&str> = DENIED_ALWAYS.to_vec();
    if no_net(policy) {
        denied.extend_from_slice(DENIED_WITHOUT_NET);
    }
    if !spawn(policy) {
        denied.extend_from_slice(DENIED_WITHOUT_SPAWN);
    }
    for name in denied {
        if let Some(n) = number(table, name) {
            prog.extend([at(JEQ, 0, 1, n), at(RET, 0, 0, eperm)]);
        }
    }
    if !spawn(policy) {
        // a thread is a clone with CLONE_THREAD; a process is one without.
        // clone3 hides its flags behind a pointer a filter cannot read, so
        // it is answered "no such call" and libc falls back to clone.
        let clone3 = number(table, "clone3").unwrap_or(0);
        let clone = number(table, "clone").unwrap_or(0);
        prog.extend([
            at(JEQ, 0, 1, clone3),
            at(RET, 0, 0, enosys),
            at(JEQ, 0, 4, clone),
            at(LD, 0, 0, ARG0_LO),
            at(JSET, 1, 0, CLONE_THREAD),
            at(RET, 0, 0, eperm),
            at(RET, 0, 0, RET_ALLOW),
        ]);
    }
    if !no_net(policy) && !widened_to_any_host(policy) {
        // a net grant is for the internet: IPv4, IPv6, and the netlink
        // socket the resolver asks about addresses. Not a Unix socket,
        // which is how a process reaches the container runtime or the
        // session bus and which Landlock does not hold. A granted Python
        // module that widens the policy to any host keeps every family: it
        // may need one.
        let socket = number(table, "socket").unwrap_or(0);
        let socketpair = number(table, "socketpair").unwrap_or(0);
        prog.extend([
            at(JEQ, 0, 6, socket),
            at(LD, 0, 0, ARG0_LO),
            at(JEQ, 2, 0, AF_INET),
            at(JEQ, 1, 0, AF_INET6),
            at(JEQ, 0, 1, AF_NETLINK),
            at(RET, 0, 0, RET_ALLOW),
            at(RET, 0, 0, eperm),
            at(JEQ, 0, 1, socketpair),
            at(RET, 0, 0, eperm),
        ]);
    }
    // input pushed into the controlling terminal is typed at the shell that
    // started this process once it ends: TIOCSTI, and TIOCLINUX's paste
    let ioctl = number(table, "ioctl").unwrap_or(0);
    prog.extend([
        at(JEQ, 0, 5, ioctl),
        at(LD, 0, 0, ARG1_LO),
        at(JEQ, 1, 0, TIOCSTI),
        at(JEQ, 0, 1, TIOCLINUX),
        at(RET, 0, 0, eperm),
        at(LD, 0, 0, NR),
    ]);
    // a signal to this process only: abort() and raise() are tgkill(own pid)
    for name in ["kill", "tgkill", "rt_sigqueueinfo", "rt_tgsigqueueinfo"] {
        let n = number(table, name).unwrap_or(0);
        prog.extend([
            at(JEQ, 0, 6, n),
            at(LD, 0, 0, ARG0_HI),
            at(JEQ, 0, 3, 0),
            at(LD, 0, 0, ARG0_LO),
            at(JEQ, 0, 1, pid),
            at(RET, 0, 0, RET_ALLOW),
            at(RET, 0, 0, eperm),
            at(LD, 0, 0, NR),
        ]);
    }
    prog.push(at(RET, 0, 0, RET_ALLOW));
    prog
}

/// The filter as the agreement gate compares it: each instruction as four
/// numbers.
pub fn filter_document(prog: &[Filter]) -> Json {
    Json::List(
        prog.iter()
            .map(|f| {
                Json::List(vec![
                    Json::Int(i64::from(f.code)),
                    Json::Int(i64::from(f.jt)),
                    Json::Int(i64::from(f.jf)),
                    Json::Int(i64::from(f.k)),
                ])
            })
            .collect(),
    )
}

#[cfg(target_os = "linux")]
/// Install the filter on every thread of this process (TSYNC). `None`, or
/// why it failed.
fn seccomp_apply(policy: &Json) -> Option<String> {
    let Some(arch) = seccomp_arch() else {
        return Some("seccomp: no system call table for this machine".to_string());
    };
    let prog = seccomp_program(policy, arch, std::process::id());
    let Ok(len) = u16::try_from(prog.len()) else {
        return Some("seccomp: the filter is longer than a filter may be".to_string());
    };
    let fprog = Fprog { len, filter: prog.as_ptr() };
    // SAFETY: prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) takes five scalars and
    // sets one bit of this process's own state; the kernel requires it
    // before an unprivileged process may install a filter.
    // test: no_new_privs_is_set_before_the_ruleset_is_entered.
    if unsafe { prctl(PR_SET_NO_NEW_PRIVS, 1_usize, 0_usize, 0_usize, 0_usize) } != 0 {
        return Some(format!("PR_SET_NO_NEW_PRIVS: errno {}", errno()));
    }
    let number: c_long = if arch == "x86_64" { 317 } else { 277 };
    // SAFETY: `fprog` points at `prog`, which is alive for the whole call
    // and holds exactly `len` instructions; the kernel copies the program
    // and keeps no pointer into this process. TSYNC installs it on every
    // thread, which is what the layer claims.
    // test: the_filter_refuses_a_socket_with_no_net_grant.
    let done = unsafe {
        syscall(
            number,
            SECCOMP_SET_MODE_FILTER,
            SECCOMP_FILTER_FLAG_TSYNC,
            &fprog as *const Fprog as *const c_void,
        )
    };
    drop(prog);
    if done != 0 {
        return Some(format!("seccomp(SET_MODE_FILTER): errno {}", errno()));
    }
    None
}

// ---- holding the threads that were already running ---------------------------

#[cfg(target_os = "linux")]
/// Ask every thread of this process that was already running to hold
/// itself with the same ruleset, and answer how many did.
///
/// Landlock holds the thread that enters a ruleset and the threads it
/// starts afterwards, never a sibling that was already running, so a
/// thread that was there first has to enter the same ruleset itself: the
/// call holds whoever makes it, and nobody can make it for another.
fn hold_others(plan: &std::sync::Arc<Plan>, abi: u32) -> usize {
    let plan = plan.clone();
    crate::confine::ask_other_threads(std::sync::Arc::new(move || restrict(&plan, abi)))
}

#[cfg(target_os = "linux")]
/// How many threads this process has, as the kernel lists them.
pub fn thread_count() -> usize {
    match std::fs::read_dir("/proc/self/task") {
        Ok(entries) => entries.count().max(1),
        Err(_) => 1,
    }
}

// ---- applying it -------------------------------------------------------------

#[cfg(target_os = "linux")]
/// What this system offers, and what.
pub fn supported() -> (bool, String) {
    let abi = landlock_abi();
    let arch = seccomp_arch();
    if abi == 0 && arch.is_none() {
        return (false, "this kernel offers no Landlock and no seccomp table".to_string());
    }
    let landlock =
        if abi > 0 { format!("Landlock ABI {abi}") } else { "no Landlock".to_string() };
    let seccomp = match arch {
        Some(arch) => format!(", seccomp-bpf ({arch})"),
        None => ", no seccomp table for this machine".to_string(),
    };
    (true, landlock + &seccomp)
}

#[cfg(target_os = "linux")]
/// Set one answer, replacing an earlier one for the same thing.
fn set(held: &mut Vec<(&'static str, Held)>, what: &'static str, answer: Held) {
    if let Some(at) = held.iter().position(|(name, _)| *name == what) {
        held[at] = (what, answer);
    } else {
        held.push((what, answer));
    }
}

#[cfg(target_os = "linux")]
/// Ask Landlock and seccomp to hold this process to `policy`, and say what
/// they did.
///
/// Every thread that was already running when the run began is asked to
/// hold itself with the same ruleset ([`hold_others`]); a thread left over
/// is a gap in the reason, and the level is then `partial` and never
/// `full`.
pub fn apply(policy: &Json, extras: &Extras) -> Report {
    let mut held: Vec<(&'static str, Held)> = Vec::new();
    let mut layers: Vec<String> = Vec::new();
    let mut notes: Vec<String> = Vec::new();
    // SABLINE_FAULT_NO_LANDLOCK, behind the `fault-inject` feature, makes
    // this run take the path a kernel with no Landlock would (9.0, M4):
    // the ruleset is not built, this layer says so, and seccomp-bpf is
    // applied as ever. It is how the leg that has no machine is measured
    // on an ordinary runner, and a released binary cannot do it.
    let abi = if crate::confine_fault::landlock_absent() { 0 } else { landlock_abi() };
    // the plan is built before anything is held: every path it must read to
    // decide, it reads first
    let made = if abi > 0 { Some(plan(policy, abi, extras)) } else { None };
    let hold_reads = made.as_ref().is_some_and(|p| p.hold_reads);
    let wider = made.as_ref().map(|p| p.wider.clone()).unwrap_or_default();
    let wider_reads = made.as_ref().map(|p| p.wider_reads.clone()).unwrap_or_default();
    let net_handled = made.as_ref().map_or(0, |p| p.net_handled);
    let net_rules = made.as_ref().map(|p| p.net_rules.clone()).unwrap_or_default();
    let landlock_failed = match made {
        None => Some("this kernel has no Landlock".to_string()),
        Some(plan) => {
            let failed = restrict(&plan, abi);
            if failed.is_none() {
                layers.push(format!("{LANDLOCK}-abi{abi}"));
                let covered = 1 + hold_others(&std::sync::Arc::new(plan), abi);
                // a thread that has ended stays listed until the kernel has
                // reaped it, so one on its way out is given a moment to go
                // before it is counted as a thread Landlock does not hold
                let mut waited = 0;
                while thread_count() > covered && waited < 40 {
                    std::thread::sleep(std::time::Duration::from_millis(5));
                    waited += 1;
                }
                let unheld = thread_count().saturating_sub(covered);
                if unheld > 0 {
                    notes.push(format!(
                        "{unheld} thread(s) started before confinement are not held by \
                         Landlock"
                    ));
                }
            }
            failed
        }
    };
    let landlock_there = landlock_failed.is_none();
    if landlock_there {
        if granted(policy, "fs_read").is_some() {
            set(
                &mut held,
                "fs_read",
                if !hold_reads {
                    Held::No(
                        "this pool has no import_root, and an import may name any .vel \
                         file, so reads are not held"
                            .to_string(),
                    )
                } else if wider_reads.is_empty() {
                    Held::Yes
                } else {
                    Held::Partly(wider_reads.join("; "))
                },
            );
        }
        if granted(policy, "fs_write").is_some() {
            set(
                &mut held,
                "fs_write",
                if abi < 3 {
                    Held::Partly(format!("Landlock ABI {abi} cannot hold truncation"))
                } else if wider.is_empty() {
                    Held::Yes
                } else {
                    Held::Partly(wider.join("; "))
                },
            );
        }
    } else {
        let why = landlock_failed.clone().unwrap_or_default();
        for what in ["fs_read", "fs_write"] {
            set(&mut held, what, Held::No(why.clone()));
        }
    }
    match seccomp_apply(policy) {
        None => {
            layers.push(SECCOMP.to_string());
            if !spawn(policy) {
                set(&mut held, "spawn", Held::Yes);
            }
            if no_net(policy) {
                set(&mut held, "net", Held::Yes);
            }
        }
        Some(why) => {
            if !spawn(policy) {
                set(
                    &mut held,
                    "spawn",
                    if landlock_there {
                        Held::Partly(format!("Landlock refuses execute, and {why}"))
                    } else {
                        Held::No(why.clone())
                    },
                );
            }
            if no_net(policy) {
                set(
                    &mut held,
                    "net",
                    if landlock_there && net_handled != 0 {
                        Held::Partly(format!("Landlock refuses TCP only, and {why}"))
                    } else {
                        Held::No(why.clone())
                    },
                );
            }
        }
    }
    if !no_net(policy) && !any_net(policy) {
        set(
            &mut held,
            "net",
            if landlock_there && !net_rules.is_empty() {
                Held::Partly(format!(
                    "the kernel holds TCP to the granted ports ({}); the host is held by \
                     the language alone",
                    net_rules.iter().map(u32::to_string).collect::<Vec<_>>().join(", ")
                ))
            } else {
                Held::No(
                    "the kernel cannot hold a host; it is held by the language alone"
                        .to_string(),
                )
            },
        );
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
    #[cfg(target_os = "linux")]
    fn landlock_abi_is_a_version_and_restricts_nothing() {
        let abi = landlock_abi();
        assert!(abi < 100, "an ABI of {abi} is not a Landlock version");
        // asking for the ABI holds nothing: what this process could read
        // before the call it can read after it
        assert!(std::path::Path::new(env!("CARGO_MANIFEST_DIR")).is_dir());
    }

    #[test]
    fn the_filter_refuses_a_socket_with_no_net_grant() {
        let prog = seccomp_program(&policy_of("io"), "x86_64", 1);
        let socket = number(SYSCALLS_X86_64, "socket").expect("socket");
        assert!(prog.iter().any(|f| f.code == 0x15 && f.k == socket));
        // and tests it once, for its family, under a net grant
        let granted = seccomp_program(&policy_of("net"), "x86_64", 1);
        let tested: Vec<&Filter> =
            granted.iter().filter(|f| f.code == 0x15 && f.k == socket).collect();
        assert_eq!(tested.len(), 1);
    }

    #[test]
    fn the_filter_starts_by_refusing_another_machine() {
        let prog = seccomp_program(&policy_of("io"), "aarch64", 1);
        assert_eq!(prog[0], Filter { code: 0x20, jt: 0, jf: 0, k: 4 });
        assert_eq!(prog[1].k, AUDIT_ARCH_AARCH64);
        assert_eq!(prog[2].k, RET_KILL_PROCESS);
    }

    #[test]
    fn a_machine_with_no_table_has_no_filter() {
        assert!(seccomp_program(&policy_of("io"), "riscv64", 1).is_empty());
        assert!(syscalls("riscv64").is_none());
    }

    #[test]
    fn the_filter_names_this_process_and_no_other_for_a_signal() {
        let prog = seccomp_program(&policy_of("io"), "x86_64", 4242);
        assert!(prog.iter().any(|f| f.code == 0x15 && f.k == 4242));
        let other = seccomp_program(&policy_of("io"), "x86_64", 4243);
        assert_ne!(prog, other, "the pid is in the filter");
    }

    #[test]
    fn the_syscall_tables_are_sorted_and_hold_every_name_the_filter_asks_for() {
        for table in [SYSCALLS_X86_64, SYSCALLS_AARCH64] {
            for pair in table.windows(2) {
                assert!(pair[0].0 < pair[1].0, "{} is not before {}", pair[0].0, pair[1].0);
            }
            for name in DENIED_ALWAYS.iter().chain(DENIED_WITHOUT_NET) {
                assert!(number(table, name).is_some(), "{name} is not in the table");
            }
            for name in ["clone", "clone3", "ioctl", "kill", "tgkill", "socket"] {
                assert!(number(table, name).is_some(), "{name} is not in the table");
            }
        }
        // aarch64 has no fork and no vfork, and the filter leaves them out
        assert!(number(SYSCALLS_AARCH64, "fork").is_none());
        assert!(number(SYSCALLS_X86_64, "fork").is_some());
    }

    #[test]
    fn a_port_rule_is_added_only_from_abi_four() {
        let policy = policy_of("net:a.example:443");
        assert_eq!(plan_masks(&policy, 3).2, Vec::<u32>::new());
        assert_eq!(plan_masks(&policy, 4).2, vec![53, 443]);
        // a grant with no port cannot be held by port
        assert_eq!(plan_masks(&policy_of("net:a.example"), 4).2, Vec::<u32>::new());
    }

    #[test]
    fn a_path_that_is_not_there_is_left_out_of_the_ruleset() {
        let made = plan(&policy_of("fs:read:/nowhere/at/all"), 4, &Extras::default());
        assert!(
            made.rules.iter().all(|(p, _)| p != "/nowhere/at/all"),
            "a path that is not there was added to the ruleset"
        );
        assert!(!made.wider_reads.is_empty(), "the level must say reads were widened");
    }

    #[test]
    fn what_a_budget_handles_grows_with_what_it_grants() {
        let (handled_io, net_io, _, holds_reads) = plan_masks(&policy_of("io"), 4);
        assert!(handled_io & FS_EXECUTE != 0, "execute is handled: no budget grants spawn");
        assert!(handled_io & FS_READ_FILE != 0 && handled_io & FS_WRITE_FILE != 0);
        assert_eq!(net_io, NET_BIND_TCP | NET_CONNECT_TCP);
        assert!(holds_reads);
        // plain fs asks for nothing of the file system, so nothing of it is
        // handled and only execute is left
        assert_eq!(plan_masks(&policy_of("fs"), 4).0, FS_EXECUTE);
    }

    #[test]
    fn no_new_privs_is_set_before_the_ruleset_is_entered() {
        // the order is what the kernel requires: without no_new_privs,
        // landlock_restrict_self answers EPERM. This is the test the SAFETY
        // comments on those two calls name.
        let source = include_str!("confine_linux.rs");
        let privs = source.find("PR_SET_NO_NEW_PRIVS, 1_usize").expect("the prctl call");
        let enter = source.find("SYS_RESTRICT_SELF, fd").expect("restrict_self");
        assert!(privs < enter, "no_new_privs must be set before restrict_self");
    }

    #[test]
    #[cfg(target_os = "linux")]
    fn a_ruleset_is_built_without_entering_it() {
        // the rules are built and the paths opened without restricting this
        // test's own thread, which cannot be undone and would hold the rest
        // of the suite
        let abi = landlock_abi();
        if abi == 0 {
            return; // no Landlock here: the CI leg without one, and Windows
        }
        let made = plan(&policy_of("io"), abi, &Extras::default());
        assert!(made.handled != 0);
        assert!(made.rules.iter().any(|(p, _)| p.starts_with("/proc/")));
    }

    #[test]
    fn a_read_grant_is_in_the_ruleset_and_its_sibling_is_not() {
        // the escape test proper is check_confine.py, which runs a program
        // and reads a file it was not granted; here the plan is held to
        // naming the grant and nothing beside it
        let dir = std::env::temp_dir();
        let grant = crate::pypath::realpath(&dir.to_string_lossy());
        let made =
            plan(&policy_of(&format!("fs:read:{}", dir.display())), 4, &Extras::default());
        assert!(
            made.rules.iter().any(|(p, a)| *p == grant && a & FS_READ_FILE != 0),
            "the granted directory is not in the ruleset"
        );
        let sibling = crate::pypath::os_path::dirname(&grant);
        assert!(
            made.rules.iter().all(|(p, _)| *p != sibling),
            "the directory above the grant is in the ruleset"
        );
    }
}
