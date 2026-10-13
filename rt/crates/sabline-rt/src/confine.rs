//! What the operating system is asked to enforce of a budget (9.0, M4):
//! `sabline/confine.py`'s policy, derived here.
//!
//! The budget is enforced by the interpreter, in the process that runs the
//! program. From 8.4 the Python package also asks the operating system to
//! hold the same budget, before the program's first statement; M4 is where
//! sabline-rt does, for its own runs.
//!
//! This module is the **derivation**, and nothing else: budget in, policy
//! document out, pure - it reads nothing of the machine, so the same budget
//! gives the same policy on every platform, and [`policy_sha256`] of it is
//! what a receipt records. The layers that apply it - Landlock, seccomp,
//! the macOS profile, the Windows job object, token and AppContainer - are
//! the platform modules beside this one, and they are the only places in
//! the crate with `unsafe` in them.
//!
//! The derivation is ported before any layer on purpose: the agreement gate
//! compares this document against `sabline/confine.py`'s for every budget it
//! has, under `--confine strict` and without it and under `--no-confine`
//! ([`policy_document`]), so the two runtimes are known to agree on *what*
//! the system is asked for before either asks the kernel for anything.
//!
//! [`FFI_WIDENS`] says what a granted Python module widens the policy to,
//! and under `--confine strict` (decisions/0006 e) a granted module widens
//! nothing. The table is compared with the package's, module for module
//! ([`table_document`]): a module added to one and not the other is a
//! difference on the commit that adds it, whether or not any budget names
//! it yet.

use std::collections::BTreeSet;

use crate::budget::{budget_from, Budget, BudgetError};
use crate::digest;
use crate::json::Json;

/// The schema of the policy document, as a receipt and `sabline doctor`
/// name it.
pub const POLICY_SCHEMA: &str = "sabline.os-policy/1";

/// The three levels a run's confinement reports, weakest first.
pub const LEVELS: [&str; 3] = ["none", "partial", "full"];

/// `full`: the operating system holds every file, network and process
/// limit of the budget.
pub const FULL: &str = "full";
/// `partial`: some of what the policy asked for is held, some is not.
pub const PARTIAL: &str = "partial";
/// `none`: nothing the policy asked for is held.
pub const NONE: &str = "none";

/// What a granted Python module widens the OS policy to: `fs` is any path,
/// `net` is any host, `all` is nothing enforced. A module that is not here
/// widens to `all` - what it needs is not known, and a run that worked
/// under 8.3.1 must not be refused - and the audit says so.
///
/// Sorted by module, because [`widens`] looks a module up by binary search
/// and [`table_document`] writes the table in this order.
pub const FFI_WIDENS: &[(&str, &[&str])] = &[
    ("abc", &[]),
    ("aiohttp", &["fs", "net"]),
    ("array", &[]),
    ("ast", &[]),
    ("asyncio", &["all"]),
    ("base64", &[]),
    ("binascii", &[]),
    ("bisect", &[]),
    ("builtins", &["all"]),
    ("bz2", &["fs"]),
    ("calendar", &[]),
    ("cmath", &[]),
    ("code", &["all"]),
    ("codecs", &["fs"]),
    ("collections", &[]),
    ("colorsys", &[]),
    ("concurrent", &["all"]),
    ("configparser", &["fs"]),
    ("copy", &[]),
    ("csv", &[]),
    ("ctypes", &["all"]),
    ("dataclasses", &[]),
    ("datetime", &[]),
    ("dbm", &["fs"]),
    ("decimal", &[]),
    ("difflib", &[]),
    ("email", &[]),
    ("enum", &[]),
    ("fileinput", &["fs"]),
    ("fnmatch", &[]),
    ("fractions", &[]),
    ("ftplib", &["net"]),
    ("functools", &[]),
    ("gc", &[]),
    ("glob", &["fs"]),
    ("gzip", &["fs"]),
    ("hashlib", &[]),
    ("heapq", &[]),
    ("hmac", &[]),
    ("html", &[]),
    ("http", &["net"]),
    ("httpx", &["fs", "net"]),
    ("imaplib", &["net"]),
    ("importlib", &["all"]),
    ("io", &["fs"]),
    ("ipaddress", &[]),
    ("itertools", &[]),
    ("json", &[]),
    ("keyword", &[]),
    ("logging", &["fs", "net"]),
    ("lzma", &["fs"]),
    ("math", &[]),
    ("multiprocessing", &["all"]),
    ("nt", &["all"]),
    ("numbers", &[]),
    ("operator", &[]),
    ("os", &["all"]),
    ("pathlib", &["fs"]),
    ("pdb", &["all"]),
    ("pickle", &["all"]),
    ("pkgutil", &["all"]),
    ("platform", &["all"]),
    ("poplib", &["net"]),
    ("posix", &["all"]),
    ("pprint", &[]),
    ("pty", &["all"]),
    ("random", &[]),
    ("re", &[]),
    ("reprlib", &[]),
    ("requests", &["fs", "net"]),
    ("runpy", &["all"]),
    ("secrets", &[]),
    ("select", &["net"]),
    ("selectors", &["net"]),
    ("shelve", &["all"]),
    ("shlex", &[]),
    ("shutil", &["fs"]),
    ("signal", &["all"]),
    ("site", &["all"]),
    ("smtplib", &["net"]),
    ("socket", &["net"]),
    ("sqlite3", &["fs"]),
    ("ssl", &["net"]),
    ("statistics", &[]),
    ("string", &[]),
    ("struct", &[]),
    ("subprocess", &["all"]),
    ("sys", &["all"]),
    ("tarfile", &["fs"]),
    ("tempfile", &["fs"]),
    ("textwrap", &[]),
    ("threading", &[]),
    ("time", &[]),
    ("tomllib", &[]),
    ("typing", &[]),
    ("unicodedata", &[]),
    ("urllib", &["net"]),
    ("urllib3", &["fs", "net"]),
    ("uuid", &[]),
    ("venv", &["all"]),
    ("webbrowser", &["all"]),
    ("winreg", &["all"]),
    ("xml", &["fs"]),
    ("xmlrpc", &["net"]),
    ("zipfile", &["fs"]),
    ("zipimport", &["all"]),
    ("zlib", &[]),
    ("zoneinfo", &[]),
];

/// What a granted module widens the policy to, and whether the table knows
/// it: `(widens, known)`. A module the table does not name widens to
/// `all`, and `known` is false.
pub fn widens(module: &str) -> (&'static [&'static str], bool) {
    match FFI_WIDENS.binary_search_by(|(name, _)| (*name).cmp(module)) {
        Ok(at) => (FFI_WIDENS[at].1, true),
        Err(_) => (&["all"], false),
    }
}

/// The OS policy of a budget: what the operating system is asked to hold
/// for a run under it.
///
/// Pure - it reads nothing of the machine - so the same budget gives the
/// same policy, and [`policy_sha256`] of it is what a receipt records. The
/// Python package derives the same document (`sabline/confine.py`'s
/// `os_policy`) and the agreement gate compares the two for every budget it
/// has.
///
/// `strict` is `--confine strict` (decisions/0006 e): a granted `ffi`
/// module widens nothing - `widened_by` is empty, and no module changes
/// `fs_read`, `fs_write`, `net` or `spawn` - and the document says
/// `"strict": true`, so its digest is not that of a policy derived without
/// it.
///
/// ```text
/// fs_read, fs_write   the resolved paths that direction may touch, or
///                     null for any path; [] for none of the user's
/// net                 "none", "any", or {"hosts": [[host, port], ...]}
/// spawn               false: no process is started, whatever the budget
/// widened_by          the granted ffi modules that widened it, and to what
/// enforced            false when nothing is asked of the system:
///                     --no-confine, or a module that widens to "all"
/// ```
pub fn os_policy(b: &Budget, confine: bool, strict: bool) -> Json {
    // `None` is "any path"; a set, because the Python package writes
    // `sorted(set(...))` and a budget may grant the same path twice.
    let mut fs_read: Option<BTreeSet<String>> = Some(BTreeSet::new());
    let mut fs_write: Option<BTreeSet<String>> = Some(BTreeSet::new());
    if b.effects.contains("fs") {
        match &b.fs {
            None => {
                fs_read = None;
                fs_write = None;
            }
            Some(grants) => {
                for (kind, prefix) in grants {
                    let side = if kind == "read" { &mut fs_read } else { &mut fs_write };
                    match prefix {
                        None => *side = None,
                        Some(path) => {
                            if let Some(paths) = side.as_mut() {
                                paths.insert(path.clone());
                            }
                        }
                    }
                }
            }
        }
    }
    // "none", "any", or the hosts, sorted by host and then by port - a
    // grant with no port sorting as port 0, as the package's key does, and
    // the sort stable, so two grants on one host keep the budget's order.
    let mut net = Net::None;
    if b.effects.contains("net") {
        net = match &b.net {
            None => Net::Any,
            Some(grants) => {
                let mut hosts: Vec<(String, Option<u32>)> = grants.clone();
                hosts.sort_by(|a, b| (&a.0, a.1.unwrap_or(0)).cmp(&(&b.0, b.1.unwrap_or(0))));
                Net::Hosts(hosts)
            }
        };
    }
    let mut spawn = false;
    let mut enforced = confine;
    let mut widened: Vec<Json> = Vec::new();
    if b.effects.contains("ffi") && !strict {
        // plain `ffi` grants any module, and the policy names it `*`
        let listed: Vec<&str> = match &b.modules {
            None => vec!["*"],
            Some(m) => m.iter().map(String::as_str).collect(),
        };
        for module in listed {
            let (widens_to, known) = widens(module);
            if !known {
                widened.push(Json::obj([
                    ("module", Json::text(module.to_string())),
                    ("widens", Json::List(vec![Json::text("all")])),
                    ("known", Json::Bool(false)),
                ]));
            } else if !widens_to.is_empty() {
                widened.push(Json::obj([
                    ("module", Json::text(module.to_string())),
                    ("widens", Json::List(widens_to.iter().map(|w| Json::text(*w)).collect())),
                    ("known", Json::Bool(true)),
                ]));
            }
            if widens_to.contains(&"fs") {
                fs_read = None;
                fs_write = None;
            }
            if widens_to.contains(&"net") {
                net = Net::Any;
            }
            if widens_to.contains(&"all") {
                fs_read = None;
                fs_write = None;
                net = Net::Any;
                spawn = true;
                enforced = false;
            }
        }
    }
    let paths = |side: &Option<BTreeSet<String>>| match side {
        None => Json::Null,
        Some(set) => Json::List(set.iter().map(|p| Json::text(p.clone())).collect()),
    };
    let mut system = vec![
        Json::text("interpreter"),
        Json::text("standard-library"),
        Json::text("program"),
        Json::text("private-temp"),
    ];
    if !matches!(net, Net::None) {
        system.push(Json::text("dns"));
        system.push(Json::text("tls-roots"));
    }
    let mut fields = vec![
        ("schema", Json::text(POLICY_SCHEMA)),
        ("enforced", Json::Bool(enforced)),
        ("fs_read", paths(&fs_read)),
        ("fs_write", paths(&fs_write)),
        ("net", net.json()),
        ("spawn", Json::Bool(spawn)),
        ("widened_by", Json::List(widened)),
        ("system", Json::List(system)),
    ];
    if strict {
        fields.push(("strict", Json::Bool(true)));
    }
    Json::Obj(fields.into_iter().map(|(k, v)| (k.to_string(), v)).collect())
}

/// The `net` field of a policy, before it becomes JSON.
enum Net {
    None,
    Any,
    Hosts(Vec<(String, Option<u32>)>),
}

impl Net {
    fn json(&self) -> Json {
        match self {
            Net::None => Json::text("none"),
            Net::Any => Json::text("any"),
            Net::Hosts(hosts) => Json::obj([(
                "hosts",
                Json::List(
                    hosts
                        .iter()
                        .map(|(h, p)| {
                            Json::List(vec![
                                Json::text(h.clone()),
                                p.map_or(Json::Null, |p| Json::Int(i64::from(p))),
                            ])
                        })
                        .collect(),
                ),
            )]),
        }
    }
}

/// The digest a receipt records: sha256 of the policy as canonical JSON.
pub fn policy_sha256(policy: &Json) -> String {
    digest::hex(&digest::sha256(policy.canonical().as_bytes()))
}

/// Whether the policy asks the system to hold anything at all.
fn enforced(policy: &Json) -> bool {
    field(policy, "enforced") == Some(&Json::Bool(true))
}

fn field<'a>(policy: &'a Json, name: &str) -> Option<&'a Json> {
    match policy {
        Json::Obj(fields) => fields.get(name),
        _ => None,
    }
}

/// The things this policy asks the system to hold: `fs_read`, `fs_write`,
/// `net`, `spawn`, in that order - empty when nothing is asked.
pub fn restricted(policy: &Json) -> Vec<&'static str> {
    if !enforced(policy) {
        return Vec::new();
    }
    let mut asks = Vec::new();
    if field(policy, "fs_read") != Some(&Json::Null) {
        asks.push("fs_read");
    }
    if field(policy, "fs_write") != Some(&Json::Null) {
        asks.push("fs_write");
    }
    if field(policy, "net") != Some(&Json::Str("any".to_string())) {
        asks.push("net");
    }
    if field(policy, "spawn") != Some(&Json::Bool(true)) {
        asks.push("spawn");
    }
    asks
}

/// Why nothing is asked of the operating system, for a policy that is not
/// enforced: the reason a receipt's `confinement_reason` carries when the
/// level is `none` before anything is applied.
pub fn why_not_enforced(policy: &Json) -> String {
    let mut names = Vec::new();
    if let Some(Json::List(widened)) = field(policy, "widened_by") {
        for entry in widened {
            let widens_all = matches!(field(entry, "widens"),
                Some(Json::List(items)) if items.iter().any(|w| w == &Json::Str("all".to_string())));
            if !widens_all {
                continue;
            }
            let module = match field(entry, "module") {
                Some(Json::Str(m)) => m.clone(),
                _ => continue,
            };
            let said =
                if module == "*" { "plain ffi".to_string() } else { format!("ffi:{module}") };
            let known = field(entry, "known") != Some(&Json::Bool(false));
            names.push(if known {
                said
            } else {
                format!("{said} (not in the table of modules, so what it needs is not known)")
            });
        }
    }
    if names.is_empty() {
        return "--no-confine: the budget is the only boundary".to_string();
    }
    format!(
        "{} widens the OS policy to nothing enforced: a granted module that can start a \
         process or load code is the operating system as this user",
        names.join(", ")
    )
}

// ---- what was applied, and what it held --------------------------------------

/// What the operating system was asked for and what it held: the level, why
/// it is that level, the layers applied, the policy's digest and the
/// platform - what a receipt's `run_parameters` records and what
/// `--require-confinement` is held to.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Report {
    /// `full`, `partial` or `none`: what was applied and held, never what
    /// was asked for.
    pub level: &'static str,
    /// Why it is that level - each gap, in the order the policy asks.
    pub reason: String,
    /// The layers that were applied, as a receipt writes them.
    pub layers: Vec<String>,
    /// sha256 of the policy as canonical JSON.
    pub policy_sha256: String,
    /// `linux`, `macos`, `windows`, or this build's own name.
    pub platform: &'static str,
}

impl Report {
    /// The four fields a receipt's `run_parameters` carries.
    pub fn fields(&self) -> Vec<(&'static str, Json)> {
        vec![
            ("confinement", Json::text(self.level)),
            ("confinement_reason", Json::text(self.reason.clone())),
            (
                "confinement_layers",
                Json::List(self.layers.iter().map(|l| Json::text(l.clone())).collect()),
            ),
            ("os_policy_sha256", Json::text(self.policy_sha256.clone())),
        ]
    }
}

/// A report with one more thing said of it: something the layers
/// themselves cannot know, such as where a relayed call is made
/// ([`relayed_elsewhere`]).
///
/// A report at `full` becomes `partial`, because what is said is a gap -
/// the same rule [`judge`] holds for a note of its own. A report at
/// `partial` or `none` keeps its level and says this beside its reason.
pub fn also_said(done: &Report, said: &str) -> Report {
    let mut out = done.clone();
    out.reason = if out.reason.is_empty() {
        said.to_string()
    } else {
        format!("{}; {said}", out.reason)
    };
    if out.level == FULL {
        out.level = PARTIAL;
    }
    out
}

/// The report of a run the operating system was not asked to hold.
pub fn unconfined(policy: &Json, reason: &str) -> Report {
    Report {
        level: NONE,
        reason: reason.to_string(),
        layers: Vec::new(),
        policy_sha256: policy_sha256(policy),
        platform: platform(),
    }
}

/// What a platform's layers answered for one thing the policy asks.
///
/// Each `why` is the reason **without** a prefix: `sabline/confine.py`
/// writes the same three answers as the strings `"yes"`, `"partly: why"`
/// and `"no: why"` and takes what follows the first colon for the reason,
/// which is what [`judge`] does with these.
pub enum Held {
    /// The system holds it.
    Yes,
    /// It holds part of it, and this is what it does not.
    Partly(String),
    /// It does not hold it, and this is why.
    No(String),
}

impl Held {
    fn said(&self) -> &str {
        match self {
            Held::Yes => "",
            Held::Partly(why) | Held::No(why) => why,
        }
    }
}

/// The level, from what each thing the policy restricts was answered.
///
/// `held` says, for each of [`restricted`]'s names, whether the system
/// holds it; a name it does not answer is not held. `notes` are the things
/// that are true of the whole run whatever it asked for - a deprecated
/// layer, a thread the layer does not cover - and they are part of the
/// reason at every level but `full`.
pub fn judge(
    policy: &Json,
    held: &[(&str, Held)],
    layers: &[String],
    notes: &[String],
) -> Report {
    if !enforced(policy) {
        return unconfined(policy, &why_not_enforced(policy));
    }
    let not_held = Held::No("not held".to_string());
    let answer = |what: &str| -> &Held {
        held.iter().find(|(name, _)| *name == what).map(|(_, a)| a).unwrap_or(&not_held)
    };
    let asks = restricted(policy);
    let mut gaps: Vec<String> = Vec::new();
    let mut any_held = false;
    for what in &asks {
        let said = answer(what);
        if matches!(said, Held::Yes | Held::Partly(_)) {
            any_held = true;
        }
        if !matches!(said, Held::Yes) {
            gaps.push(format!("{what}: {}", said.said().trim()));
        }
    }
    gaps.extend(notes.iter().cloned());
    let report = |level: &'static str, reason: String, layers: &[String]| Report {
        level,
        reason,
        layers: layers.to_vec(),
        policy_sha256: policy_sha256(policy),
        platform: platform(),
    };
    if !any_held {
        let reason =
            if gaps.is_empty() { "nothing was applied".to_string() } else { gaps.join("; ") };
        return report(NONE, reason, layers);
    }
    let strict = if field(policy, "strict") == Some(&Json::Bool(true)) {
        "; under --confine strict no granted module widened the policy"
    } else {
        ""
    };
    if !gaps.is_empty() {
        return report(PARTIAL, gaps.join("; ") + strict, layers);
    }
    report(
        FULL,
        "the operating system holds every file, network and process limit of this budget"
            .to_string()
            + strict,
        layers,
    )
}

/// `linux`, `macos`, `windows`, or this build's own name for its system.
///
/// Rust's own name for each of the three is already the word a receipt
/// writes, so there is nothing here to map. `sabline/confine.py`'s
/// `_platform` has to map, because CPython calls two of them `darwin` and
/// `win32`.
pub fn platform() -> &'static str {
    std::env::consts::OS
}

// ---- the paths a policy is applied to ----------------------------------------

/// Every path that is there, resolved, each once and in the order given:
/// `sabline/confine.py`'s `_existing`.
pub fn existing(paths: &[String]) -> Vec<String> {
    let mut seen: BTreeSet<String> = BTreeSet::new();
    let mut out = Vec::new();
    for p in paths {
        if p.is_empty() {
            continue;
        }
        let real = crate::pypath::realpath(p);
        if seen.insert(real.clone()) && crate::pypath::exists(&real) {
            out.push(real);
        }
    }
    out
}

/// `(the path when it exists, else the nearest directory above it that
/// does; whether that is wider than the path)`: a write grant may name a
/// file or a directory not made yet, and a read grant may name a file the
/// program is about to write and read back.
pub fn nearest_directory(path: &str) -> (Option<String>, bool) {
    let mut p = crate::pypath::realpath(path);
    if crate::pypath::exists(&p) {
        return (Some(p), false);
    }
    loop {
        let parent = crate::pypath::os_path::dirname(&p);
        if parent == p {
            return (None, true);
        }
        p = parent;
        if std::path::Path::new(&p).is_dir() {
            return (Some(p), true);
        }
    }
}

/// The TCP ports a net policy allows, when every grant names one; else
/// `None`, and TCP is not held by port.
pub fn tcp_ports(policy: &Json) -> Option<Vec<u32>> {
    let hosts = match field(policy, "net") {
        Some(Json::Obj(fields)) => match fields.get("hosts") {
            Some(Json::List(hosts)) => hosts.clone(),
            _ => return None,
        },
        _ => return None,
    };
    let mut ports: BTreeSet<u32> = BTreeSet::from([53]);
    for pair in &hosts {
        match pair {
            Json::List(hp) if hp.len() == 2 => match &hp[1] {
                Json::Int(p) => ports.insert(u32::try_from(*p).unwrap_or(0)),
                _ => return None,
            },
            _ => return None,
        };
    }
    Some(ports.into_iter().collect())
}

/// The hosts a net policy allows, with each one's port, in the order the
/// document holds them; `None` when it names no host list - `none` or
/// `any`.
pub fn net_hosts(policy: &Json) -> Option<Vec<(String, Option<u32>)>> {
    let Some(Json::Obj(fields)) = field(policy, "net") else { return None };
    let Some(Json::List(hosts)) = fields.get("hosts") else { return None };
    Some(
        hosts
            .iter()
            .filter_map(|pair| match pair {
                Json::List(hp) if hp.len() == 2 => match (&hp[0], &hp[1]) {
                    (Json::Str(host), Json::Int(port)) => {
                        Some((host.clone(), u32::try_from(*port).ok()))
                    }
                    (Json::Str(host), _) => Some((host.clone(), None)),
                    _ => None,
                },
                _ => None,
            })
            .collect(),
    )
}

/// The paths a policy's `fs_read` or `fs_write` names, in the order the
/// document holds them; `None` for any path.
pub fn granted(policy: &Json, which: &str) -> Option<Vec<String>> {
    match field(policy, which) {
        Some(Json::List(paths)) => Some(
            paths
                .iter()
                .filter_map(|p| match p {
                    Json::Str(s) => Some(s.clone()),
                    _ => None,
                })
                .collect(),
        ),
        _ => None,
    }
}

/// Whether the policy's `net` is `none` - no host at all.
pub fn no_net(policy: &Json) -> bool {
    field(policy, "net") == Some(&Json::Str("none".to_string()))
}

/// Whether the policy's `net` is `any` - every host.
pub fn any_net(policy: &Json) -> bool {
    field(policy, "net") == Some(&Json::Str("any".to_string()))
}

/// Whether the policy lets a process be started: always false while it is
/// enforced, since no budget grants it.
pub fn spawn(policy: &Json) -> bool {
    field(policy, "spawn") == Some(&Json::Bool(true))
}

/// Whether a granted Python module widened the policy to any host, which
/// keeps every socket family: it may need one.
pub fn widened_to_any_host(policy: &Json) -> bool {
    match field(policy, "widened_by") {
        Some(Json::List(entries)) => entries.iter().any(|e| {
            matches!(field(e, "widens"),
                Some(Json::List(items)) if items.iter().any(|w| w == &Json::Str("net".to_string())))
        }),
        _ => false,
    }
}

// ---- applying it ---------------------------------------------------------------

/// What this run itself must be able to reach, beyond the budget's grants.
#[derive(Default)]
pub struct Extras {
    /// The files the run itself reads: the program, its imports, the
    /// standard library it was loaded from. A receipt digests them when the
    /// run has ended, so a policy that did not allow them would drop
    /// subjects from the receipt rather than refuse anything.
    pub reads: Vec<String>,
    /// The places the run itself writes.
    pub writes: Vec<String>,
    /// The run's private temporary directory, which the policy must let it
    /// write, or `None`.
    pub temp: Option<String>,
    /// Leave reads unheld: a pool with no import root, where an import may
    /// name any file the process can read.
    pub read_any: bool,
    /// The file whose appearance stops the run (`sabline eval`), which the
    /// run must be able to *look for* even though it is outside every
    /// grant. Landlock governs opening and not `stat`, and a lowered token
    /// stops neither, so only the Windows AppContainer has to be told
    /// (9.0, M4): a container that could not look for it would never stop.
    pub stop_file: Option<String>,
}

/// What the host asked of the operating system for one run (M4).
///
/// The host asks, because the host is what knows: the command line read the
/// flags, the library took the arguments, a pool holds its own. A run the
/// host said nothing about is not confined and its receipt says nothing was
/// asked - which is every run of the agreement gate's own batches, where
/// one process runs some thousands of programs and a policy applied for the
/// first would hold the rest.
#[derive(Clone, Default, Debug)]
pub struct Asked {
    /// Whether to confine at all: `false` is `--no-confine`.
    pub on: bool,
    /// `--confine strict`: no granted `ffi` module widens the policy.
    pub strict: bool,
    /// `--require-confinement`: `full`, `partial`, or nothing.
    pub require: Option<String>,
    /// What the run itself reads beyond the budget's grants, beyond the
    /// program's own files - a pool's `--confine-reads`, its import root.
    pub reads: Vec<String>,
    /// What the run itself writes beyond the budget's grants.
    pub writes: Vec<String>,
    /// The run's private temporary directory, when the host made one.
    pub temp: Option<String>,
    /// Leave reads unheld: a pool with no import root. No host sets it -
    /// sabline-rt reads and checks the program before it asks for
    /// anything, so its reads are always held to the program's own files -
    /// and it is here because the policy's rule for it is the package's.
    pub read_any: bool,
    /// The level the process that started this one is held to, or `None`
    /// when it is held to nothing.
    ///
    /// It matters because a call to the network, a granted Python module
    /// or a tool is made **there** and not here ([`crate::interp::RELAYED`]):
    /// what bounds that work is what confines that process, so a run whose
    /// budget grants one of them says so rather than claiming a boundary
    /// around work outside it. A pool's worker is confined and a command
    /// line's own process is not.
    pub host: Option<String>,
}

/// What a relayed run has to say about the process its calls are made in,
/// or `None` when it has nothing to say: the budget grants none of the
/// three, or the host is confined too.
///
/// This is the one thing a run through sabline-rt cannot hold itself, and
/// it is a note rather than a silence because a receipt that said `full`
/// for a budget granting `net` would be claiming a boundary around a
/// connection opened in another process (plan/9.0.md, M4: the confined
/// host, and the network's own port).
pub fn relayed_elsewhere(budget: &Budget, host: Option<&str>) -> Option<String> {
    let relayed: Vec<&str> = ["net", "ffi", "tool"]
        .into_iter()
        .filter(|effect| budget.effects.contains(*effect))
        .collect();
    if relayed.is_empty() {
        return None;
    }
    if matches!(host, Some(level) if level != NONE) {
        return None;
    }
    let what = match relayed.as_slice() {
        [one] => format!("a call to {}", named(one)),
        many => {
            let names: Vec<String> = many.iter().map(|e| named(e).to_string()).collect();
            format!("a call to {}", names.join(", "))
        }
    };
    Some(format!(
        "{what} is made in the process that started this one, which is held to \
         nothing, so this policy does not bound it"
    ))
}

fn named(effect: &str) -> &'static str {
    match effect {
        "net" => "the network",
        "ffi" => "a granted Python module",
        _ => "a tool",
    }
}

/// The levels `--require-confinement` takes.
pub const REQUIRE_WORDS: [&str; 2] = [FULL, PARTIAL];

/// Refuse the run - E326 - when `--require-confinement` asked for a level
/// that `report` is below.
///
/// The level is the one already applied, never a prediction: the run stops
/// before its first statement, and its receipt records the level it got.
pub fn require(wanted: Option<&str>, report: Option<&Report>) -> Option<crate::SablineError> {
    let wanted = wanted?;
    let got = report.map_or(NONE, |r| r.level);
    let rank = |level: &str| LEVELS.iter().position(|l| *l == level);
    if let (Some(got_at), Some(wanted_at)) = (rank(got), rank(wanted)) {
        if got_at >= wanted_at {
            return None;
        }
    }
    let reason = report.map_or_else(
        || "nothing was asked of the operating system".to_string(),
        |r| r.reason.clone(),
    );
    Some(crate::SablineError::with_fixes(
        "E326",
        format!(
            "this run asks for confinement at least {wanted}, and the \
             operating system gave it {got}: {reason}"
        ),
        0,
        &[
            "run it where the operating system can hold its budget, or \
             narrow the budget to what this one can hold",
            "--confine strict keeps a granted Python module from widening \
             the policy, which raises the level a budget with ffi gets",
            "--require-confinement partial accepts a partial level; sabline \
             audit FILE says what this machine gives the program's budget, \
             and why",
        ],
    ))
}

/// Ask the operating system to hold this process to `policy`, and say what
/// it did.
///
/// It cannot be undone, and it is applied once: a second call reports the
/// first, as `sabline/confine.py`'s `apply` does.
pub fn apply(policy: &Json, extras: &Extras) -> Report {
    if let Some(done) = APPLIED.get() {
        return done.clone();
    }
    let done = if !enforced(policy) {
        judge(policy, &[], &[], &[])
    } else {
        #[cfg(target_os = "linux")]
        {
            crate::confine_linux::apply(policy, extras)
        }
        #[cfg(target_os = "macos")]
        {
            crate::confine_macos::apply(policy, extras)
        }
        #[cfg(windows)]
        {
            crate::confine_windows::apply(policy, extras)
        }
        #[cfg(not(any(target_os = "linux", target_os = "macos", windows)))]
        {
            let _ = extras;
            Report {
                level: NONE,
                reason: format!("nothing is known for {}", std::env::consts::OS),
                layers: Vec::new(),
                policy_sha256: policy_sha256(policy),
                platform: platform(),
            }
        }
    };
    let _ = APPLIED.set(done.clone());
    done
}

/// A ruleset a thread can enter by calling this, answering `None` when it
/// did and why not when it did not.
///
/// It is an `Arc` rather than a reference because it crosses from the run's
/// thread to the threads that were already running, which hold themselves
/// (Landlock holds a thread and the threads it starts, never a sibling).
pub type HoldMe = std::sync::Arc<dyn Fn() -> Option<String> + Send + Sync>;

/// How the run asks the threads that were already running to hold
/// themselves: it is handed what to run, and answers how many of them ran
/// it without a failure.
pub type HoldOthers = Box<dyn Fn(HoldMe) -> usize + Send + Sync>;

static OTHERS: std::sync::OnceLock<HoldOthers> = std::sync::OnceLock::new();

/// Say how the threads that were already running are asked to hold
/// themselves. `sabline-rt exec` says it once, before the run begins; a
/// process that does not is a process where the run's thread is the only
/// one, and then there is nothing to ask.
pub fn other_threads_hold_themselves(how: HoldOthers) {
    let _ = OTHERS.set(how);
}

/// Ask them, and answer how many held themselves - 0 where nothing said
/// how, which is a process with one thread in it.
pub fn ask_other_threads(hold_me: HoldMe) -> usize {
    OTHERS.get().map_or(0, |how| how(hold_me))
}

static SETTLED: std::sync::OnceLock<Box<dyn Fn() + Send + Sync>> = std::sync::OnceLock::new();

/// Say what to do once this run's confinement is settled - applied, or
/// decided against - whatever the platform and whether or not any other
/// thread had to hold itself.
///
/// `sabline-rt exec` says it once: the thread that writes the frames waits
/// for this before it starts the thread that reads the answers, so that
/// Landlock holds that one too, and a platform whose layers hold the whole
/// process at once - Windows, macOS - must still let it through. Without
/// it a run that relays a call would wait for an answer nobody could write
/// (the trap this cost a session's hour).
pub fn when_settled(then: Box<dyn Fn() + Send + Sync>) {
    let _ = SETTLED.set(then);
}

/// Say that it is settled. Called once a run, from the one place that
/// knows - whichever way the confinement went.
pub fn now_settled() {
    if let Some(then) = SETTLED.get() {
        then();
    }
}

/// What was applied to this process, or `None` when nothing was asked.
pub fn current() -> Option<Report> {
    APPLIED.get().cloned()
}

static APPLIED: std::sync::OnceLock<Report> = std::sync::OnceLock::new();

/// What this system offers, and what, for a report of the machine.
pub fn supported() -> (bool, String) {
    #[cfg(target_os = "linux")]
    {
        crate::confine_linux::supported()
    }
    #[cfg(target_os = "macos")]
    {
        crate::confine_macos::supported()
    }
    #[cfg(windows)]
    {
        crate::confine_windows::supported()
    }
    #[cfg(not(any(target_os = "linux", target_os = "macos", windows)))]
    {
        (false, format!("nothing is known for {}", std::env::consts::OS))
    }
}

/// The header of the framed stream `os-policy --list` writes.
pub const POLICY_BATCH_HEADER: &str = "sabline.os-policy-batch/1";

/// One budget's policies, as the agreement gate compares them: the policy
/// under each of the three ways a run asks for one, with its digest, what
/// it asks the system to hold, and - when it asks for nothing - why.
///
/// A budget the parser refuses has no policy, and the document says so:
/// the budget row of the gate is what holds the refusal's words, and this
/// row would only say them twice.
pub fn policy_document(allow: Option<&str>, deny: Option<&str>) -> Json {
    let b = match budget_from(allow, deny) {
        Err(BudgetError(_)) => {
            return Json::obj([("valid", Json::Bool(false))]);
        }
        Ok(b) => b,
    };
    let one = |confine: bool, strict: bool| {
        let policy = os_policy(&b, confine, strict);
        let digest = policy_sha256(&policy);
        let asks = restricted(&policy);
        let why =
            if enforced(&policy) { Json::Null } else { Json::text(why_not_enforced(&policy)) };
        Json::obj([
            ("policy", policy),
            ("sha256", Json::text(digest)),
            ("restricted", Json::List(asks.into_iter().map(Json::text).collect())),
            ("not_enforced", why),
        ])
    };
    Json::obj([
        ("valid", Json::Bool(true)),
        ("default", one(true, false)),
        ("strict", one(true, true)),
        ("no_confine", one(false, false)),
    ])
}

/// The schema of the document [`enforces_document`] writes.
pub const ENFORCES_SCHEMA: &str = "sabline.os-enforces/1";

/// The systems [`ENFORCES_HELD`]'s three words are in the order of.
pub const ENFORCES_SYSTEMS: [&str; 3] = ["linux", "macos", "windows"];

/// **sabline-rt's own answer** to `sabline/confine.py`'s `ENFORCES_HELD`:
/// for each row of that module's `ENFORCES`, how much of it the kernel
/// holds for a run **this runtime** makes, one word per system, and the
/// reason where that is not the word the package's own runtime gives.
///
/// The rows are the package's, in the package's order, and the prose
/// stays there: a second copy of it would be two places to keep one fact.
/// What is here is the one thing that differs, which is **how much**, and
/// it differs on Windows alone - the run's own process is started inside
/// an AppContainer ([`crate::confine_appcontainer`]), which a running
/// `python.exe` cannot enter.
///
/// `check_confine.py`'s `table_cases` holds this table to the package's:
/// the rows and their order are the same, no cell is weaker, every cell
/// that differs carries a reason, and `docs/os-enforces.md` prints them.
pub const ENFORCES_HELD: &[(&str, [&str; 3], &str)] = &[
    (
        "no `fs` granted",
        ["yes", "partly", "yes"],
        "windows: the run's own process is started inside an AppContainer with an ACE for \
         nothing but the files it reads, so a read or a write of anything of the user's is \
         refused by the kernel and not only a write",
    ),
    (
        "`fs:read:DIR`",
        ["yes", "partly", "yes"],
        "windows: the container is given one ACE for DIR, resolved, and one for each file \
         the run itself reads; a read of anything else of the user's is refused",
    ),
    (
        "`fs:write:DIR`",
        ["yes", "yes", "yes"],
        "windows: the container is given an ACE for DIR that carries write and delete, and \
         the integrity level is not lowered, because the ACE is what holds the write",
    ),
    ("`fs`, `fs:read`, `fs:write` with no path", ["no", "no", "no"], ""),
    ("a credential location under a broad grant (E318)", ["no", "no", "no"], ""),
    (
        "no `net` granted",
        ["yes", "yes", "yes"],
        "windows: the container is made with no capability, so a socket to anything outside \
         the machine is refused with WSAEACCES",
    ),
    (
        "`net:HOST`, `net:HOST:PORT`",
        ["partly", "partly", "partly"],
        "windows: the container is made with internetClient, which admits every host, so \
         the host is held by the language alone, as on Linux and macOS",
    ),
    ("`net` with no host", ["no", "no", "no"], ""),
    ("`@N` counts", ["no", "no", "no"], ""),
    ("`io`", ["no", "no", "no"], ""),
    ("`env`", ["no", "no", "no"], ""),
    ("`clock`, `rand`, `declassify`", ["no", "no", "no"], ""),
    ("`tool`", ["no", "no", "no"], ""),
    ("starting a process (never a budget item)", ["yes", "yes", "yes"], ""),
    ("the rest of the deny-list (never a budget item)", ["yes", "partly", "partly"], ""),
    ("`ffi:MODULE`", ["no", "no", "no"], ""),
    (
        "`ffi:MODULE` under `--confine strict`",
        ["yes", "partly", "yes"],
        "windows: under strict the policy is the budget's own grants, and the container \
         holds a module's own calls - native code, ctypes - as it holds the runtime's",
    ),
    (
        "`--require-confinement full` or `partial` (never a budget item)",
        ["yes", "yes", "yes"],
        "",
    ),
    ("time and memory limits", ["yes", "partly", "yes"], ""),
];

/// [`ENFORCES_HELD`] as one document, for `sabline-rt os-policy
/// --enforces`, which `check_confine.py` reads.
pub fn enforces_document() -> Json {
    Json::obj([
        ("schema", Json::text(ENFORCES_SCHEMA)),
        ("systems", Json::List(ENFORCES_SYSTEMS.iter().map(|s| Json::text(*s)).collect())),
        (
            "rows",
            Json::List(
                ENFORCES_HELD
                    .iter()
                    .map(|(row, held, why)| {
                        Json::obj([
                            ("row", Json::text(*row)),
                            (
                                "held",
                                Json::List(held.iter().map(|h| Json::text(*h)).collect()),
                            ),
                            ("why", Json::text(*why)),
                        ])
                    })
                    .collect(),
            ),
        ),
    ])
}

/// The budgets the confinement tables are written for (M4). None of them
/// names a path, so nothing in the three layers' documents is this
/// machine's: a budget with an `fs:` path would resolve it against the
/// working directory and the documents would differ from one checkout to
/// the next. What paths do to a policy is compared by the OS policies' own
/// row of the gate, over every budget it has.
pub const TABLE_BUDGETS: &[&str] = &[
    "",
    "io",
    "fs",
    "fs:read",
    "fs:write",
    "fs:read,fs:write",
    "net",
    "net:a.example",
    "net:a.example:443",
    "net:a.example:443,net:b.example:80",
    "io,net:a.example:443",
    "io,ffi:math",
    "io,ffi:io",
    "io,ffi:socket",
    "io,ffi:requests",
    "io,ffi:os",
    "io,ffi",
    "io,ffi:nosuchmodule",
];

/// The machine's answers the macOS profile is written against, so that the
/// profile is the same text in both runtimes wherever it is made. They are
/// names no machine has, so that "is this a file" answers the same
/// everywhere.
pub const TABLE_HOME: &str = "/h";
/// The working directory the table's profiles are written against.
pub const TABLE_CWD: &str = "/h/w";
/// What the table's profiles are told the runtime itself reads.
pub const TABLE_INTERPRETER: &[&str] = &["/i/lib", "/i/dev/null"];

/// The confinement tables, as one document: [`FFI_WIDENS`] module for
/// module, and for each of [`TABLE_BUDGETS`] the three layers' own
/// derivations - the seccomp filter for each machine, the Landlock masks
/// for each ABI, and the macOS profile.
///
/// The Python package writes the same document (`sabline check-dump
/// --confinement-tables`) and the agreement gate compares the two on every
/// platform, so a system call number, an access bit or a line of the
/// profile typed wrong in one runtime is a difference on the commit that
/// types it. None of it is behaviour - what the kernel then does is
/// `check_confine.py`'s - and all of it is what the kernel is asked for.
pub fn table_document() -> Json {
    let mut cases: std::collections::BTreeMap<String, Json> =
        std::collections::BTreeMap::new();
    let interpreter: Vec<String> =
        TABLE_INTERPRETER.iter().map(|p| (*p).to_string()).collect();
    for text in TABLE_BUDGETS {
        let budget = budget_from(Some(text), None).expect("a budget of the table");
        for (mode, strict) in [("default", false), ("strict", true)] {
            let policy = os_policy(&budget, true, strict);
            let seccomp = Json::Obj(
                ["x86_64", "aarch64"]
                    .into_iter()
                    .map(|arch| {
                        (
                            arch.to_string(),
                            crate::confine_linux::filter_document(
                                &crate::confine_linux::seccomp_program(&policy, arch, 1),
                            ),
                        )
                    })
                    .collect(),
            );
            let landlock = Json::Obj(
                (1..=4u32)
                    .map(|abi| {
                        let (handled, net_handled, net_rules, hold_reads) =
                            crate::confine_linux::plan_masks(&policy, abi);
                        (
                            abi.to_string(),
                            Json::obj([
                                ("handled", Json::Int(handled as i64)),
                                ("net_handled", Json::Int(net_handled as i64)),
                                (
                                    "net_rules",
                                    Json::List(
                                        net_rules
                                            .into_iter()
                                            .map(|p| Json::Int(i64::from(p)))
                                            .collect(),
                                    ),
                                ),
                                ("hold_reads", Json::Bool(hold_reads)),
                            ]),
                        )
                    })
                    .collect(),
            );
            let profile = crate::confine_macos::profile(
                &policy,
                &Extras::default(),
                TABLE_HOME,
                TABLE_CWD,
                &interpreter,
            );
            cases.insert(
                format!("{text}|{mode}"),
                Json::obj([
                    ("seccomp", seccomp),
                    ("landlock", landlock),
                    ("macos_profile", Json::text(profile)),
                ]),
            );
        }
    }
    Json::obj([
        ("schema", Json::text("sabline.confinement-tables/1")),
        (
            "ffi_widens",
            Json::Obj(
                FFI_WIDENS
                    .iter()
                    .map(|(module, widens)| {
                        (
                            (*module).to_string(),
                            Json::List(widens.iter().map(|w| Json::text(*w)).collect()),
                        )
                    })
                    .collect(),
            ),
        ),
        ("cases", Json::Obj(cases)),
    ])
}

#[cfg(test)]
mod tests {
    use super::*;

    fn policy_of(allow: &str) -> Json {
        os_policy(&budget_from(Some(allow), None).expect("a budget"), true, false)
    }

    #[test]
    fn io_asks_for_no_file_and_no_network() {
        let policy = policy_of("io");
        assert_eq!(field(&policy, "fs_read"), Some(&Json::List(Vec::new())));
        assert_eq!(field(&policy, "fs_write"), Some(&Json::List(Vec::new())));
        assert_eq!(field(&policy, "net"), Some(&Json::Str("none".to_string())));
        assert_eq!(field(&policy, "spawn"), Some(&Json::Bool(false)));
        assert_eq!(restricted(&policy), vec!["fs_read", "fs_write", "net", "spawn"]);
    }

    #[test]
    fn a_read_grant_names_a_path_and_a_write_grant_does_not() {
        let policy = policy_of("fs:read:.");
        match field(&policy, "fs_read") {
            Some(Json::List(paths)) => assert_eq!(paths.len(), 1),
            other => panic!("fs_read is {other:?}"),
        }
        assert_eq!(field(&policy, "fs_write"), Some(&Json::List(Vec::new())));
    }

    #[test]
    fn plain_fs_asks_for_nothing_of_the_file_system() {
        let policy = policy_of("fs");
        assert_eq!(field(&policy, "fs_read"), Some(&Json::Null));
        assert_eq!(field(&policy, "fs_write"), Some(&Json::Null));
        assert_eq!(restricted(&policy), vec!["net", "spawn"]);
    }

    #[test]
    fn a_module_that_widens_to_all_turns_the_layer_off() {
        let policy = policy_of("io,ffi:os");
        assert_eq!(field(&policy, "enforced"), Some(&Json::Bool(false)));
        assert_eq!(field(&policy, "spawn"), Some(&Json::Bool(true)));
        assert!(restricted(&policy).is_empty());
        assert!(why_not_enforced(&policy).starts_with("ffi:os widens the OS policy"));
    }

    #[test]
    fn a_module_the_table_does_not_name_widens_to_all_and_says_so() {
        let policy = policy_of("io,ffi:nosuchmodule");
        assert_eq!(field(&policy, "enforced"), Some(&Json::Bool(false)));
        assert!(why_not_enforced(&policy).contains("not in the table of modules"));
    }

    #[test]
    fn strict_lets_no_module_widen_anything() {
        let b = budget_from(Some("io,ffi:os"), None).expect("a budget");
        let policy = os_policy(&b, true, true);
        assert_eq!(field(&policy, "enforced"), Some(&Json::Bool(true)));
        assert_eq!(field(&policy, "spawn"), Some(&Json::Bool(false)));
        assert_eq!(field(&policy, "widened_by"), Some(&Json::List(Vec::new())));
        assert_eq!(field(&policy, "strict"), Some(&Json::Bool(true)));
        assert_eq!(restricted(&policy), vec!["fs_read", "fs_write", "net", "spawn"]);
    }

    #[test]
    fn strict_changes_the_digest_of_the_same_budget() {
        let b = budget_from(Some("io"), None).expect("a budget");
        assert_ne!(
            policy_sha256(&os_policy(&b, true, false)),
            policy_sha256(&os_policy(&b, true, true))
        );
    }

    #[test]
    fn no_confine_asks_for_nothing_and_says_which_boundary_is_left() {
        let b = budget_from(Some("io"), None).expect("a budget");
        let policy = os_policy(&b, false, false);
        assert_eq!(field(&policy, "enforced"), Some(&Json::Bool(false)));
        assert!(restricted(&policy).is_empty());
        assert_eq!(why_not_enforced(&policy), "--no-confine: the budget is the only boundary");
    }

    #[test]
    fn a_net_grant_sorts_its_hosts_and_asks_for_dns_and_the_roots() {
        let policy = policy_of("net:b.example:443,net:a.example,net:a.example:80");
        let hosts = match field(&policy, "net") {
            Some(Json::Obj(fields)) => fields.get("hosts").cloned(),
            other => panic!("net is {other:?}"),
        };
        assert_eq!(
            hosts.map(|h| h.canonical()),
            Some(r#"[["a.example",null],["a.example",80],["b.example",443]]"#.to_string())
        );
        let system = field(&policy, "system").expect("system").canonical();
        assert!(system.contains("dns") && system.contains("tls-roots"));
    }

    #[test]
    fn the_table_knows_a_module_it_names_and_not_one_it_does_not() {
        assert_eq!(widens("os"), (&["all"][..], true));
        assert_eq!(widens("math"), (&[][..], true));
        assert_eq!(widens("nosuchmodule"), (&["all"][..], false));
    }

    #[test]
    fn the_ffi_table_is_sorted_so_a_lookup_finds_every_module() {
        for pair in FFI_WIDENS.windows(2) {
            assert!(pair[0].0 < pair[1].0, "{} is not before {}", pair[0].0, pair[1].0);
        }
        for (module, _) in FFI_WIDENS {
            assert!(widens(module).1, "{module} is in the table and was not found");
        }
    }

    #[test]
    fn a_refused_budget_has_no_policy() {
        assert_eq!(
            policy_document(Some("nosucheffect"), None).canonical(),
            r#"{"valid":false}"#
        );
    }
}
