//! `os.path`, as CPython spells it, for the paths a check reports.
//!
//! The loader builds the name of every imported file with
//! `os.path.join(os.path.dirname(importer), path)`, and that string is
//! what an error's `file` and an E512 or E513 message say. So the port
//! cannot use `std::path`, which is free to spell a joined path its own
//! way: it copies `ntpath` on Windows and `posixpath` everywhere else,
//! function for function, from CPython. Both are compiled on every
//! platform and both are tested on every platform; `os_path` is the one
//! this platform's CPython uses. The supported CPythons agree on every
//! function here but one: 3.13 stopped calling a Windows path with a root
//! and no drive (`\x`) absolute. The only reader of `isabs` is the set of
//! files already read, where either answer finds the same file, so this
//! follows 3.13.
//!
//! Only what the loader and the effect checker call is here: `dirname`,
//! `basename`, `join`, `normcase`, `abspath` (for the set of files already
//! read) and `realpath` (for whether a function's file is in the shipped
//! standard library).

/// `ntpath`: the Windows flavour.
pub mod nt {
    const SEP: char = '\\';

    fn is_sep(c: char) -> bool {
        c == '\\' || c == '/'
    }

    /// `ntpath.splitroot(p)`: drive, root and the rest.
    pub fn splitroot(p: &str) -> (String, String, String) {
        let chars: Vec<char> = p.chars().collect();
        let norm: Vec<char> = chars.iter().map(|&c| if c == '/' { SEP } else { c }).collect();
        let take = |a: usize, b: usize| -> String {
            chars[a.min(chars.len())..b.min(chars.len())].iter().collect()
        };
        let find =
            |from: usize| -> Option<usize> { (from..norm.len()).find(|&i| norm[i] == SEP) };
        if norm.first() == Some(&SEP) {
            if norm.get(1) == Some(&SEP) {
                let head: String = norm.iter().take(8).collect::<String>().to_uppercase();
                let start = if head == "\\\\?\\UNC\\" { 8 } else { 2 };
                let Some(index) = find(start) else {
                    return (p.to_string(), String::new(), String::new());
                };
                let Some(index2) = find(index + 1) else {
                    return (p.to_string(), String::new(), String::new());
                };
                return (
                    take(0, index2),
                    take(index2, index2 + 1),
                    take(index2 + 1, chars.len()),
                );
            }
            return (String::new(), take(0, 1), take(1, chars.len()));
        }
        if norm.get(1) == Some(&':') {
            if norm.get(2) == Some(&SEP) {
                return (take(0, 2), take(2, 3), take(3, chars.len()));
            }
            return (take(0, 2), String::new(), take(2, chars.len()));
        }
        (String::new(), String::new(), p.to_string())
    }

    /// `ntpath.split(p)`: the head and the last component.
    pub fn split(p: &str) -> (String, String) {
        let (d, r, rest) = splitroot(p);
        let chars: Vec<char> = rest.chars().collect();
        let mut i = chars.len();
        while i > 0 && !is_sep(chars[i - 1]) {
            i -= 1;
        }
        let head: String = chars[..i].iter().collect();
        let tail: String = chars[i..].iter().collect();
        (format!("{d}{r}{}", head.trim_end_matches(is_sep)), tail)
    }

    /// `ntpath.dirname(p)`.
    pub fn dirname(p: &str) -> String {
        split(p).0
    }

    /// `ntpath.basename(p)`.
    pub fn basename(p: &str) -> String {
        split(p).1
    }

    /// `ntpath.join(a, b)`.
    pub fn join(a: &str, b: &str) -> String {
        let (mut rd, mut rr, mut rp) = splitroot(a);
        let (pd, pr, pp) = splitroot(b);
        let mut relative = true;
        if !pr.is_empty() {
            if !pd.is_empty() || rd.is_empty() {
                rd = pd;
            }
            rr = pr;
            rp = pp.clone();
            relative = false;
        } else if !pd.is_empty() && pd != rd {
            if pd.to_lowercase() != rd.to_lowercase() {
                rd = pd;
                rr = pr;
                rp = pp.clone();
                relative = false;
            } else {
                rd = pd;
            }
        }
        if relative {
            if rp.chars().last().is_some_and(|c| !is_sep(c)) {
                rp.push(SEP);
            }
            rp.push_str(&pp);
        }
        if !rp.is_empty()
            && rr.is_empty()
            && rd.chars().last().is_some_and(|c| c != ':' && !is_sep(c))
        {
            return format!("{rd}{SEP}{rp}");
        }
        format!("{rd}{rr}{rp}")
    }

    /// `ntpath.normcase(s)`: separators made `\`, and lower case.
    ///
    /// CPython 3.13 lowercases with the system's `LCMapStringEx`, one
    /// character for one: no final-sigma rule, and `İ` left alone where
    /// `str.lower()` writes two characters. So it is done here character by
    /// character, keeping a character whose lower case is not one
    /// character. The system's table is older than Unicode's, and about
    /// four hundred letters it does not lower (`ẞ`, Cherokee, some Greek)
    /// this lowers anyway; safe Rust cannot ask the system, so a path with
    /// one of them is a known difference, and the gate's corpus holds none.
    pub fn normcase(s: &str) -> String {
        s.chars()
            .map(|c| if c == '/' { '\\' } else { c })
            .map(|c| {
                let mut lower = c.to_lowercase();
                match (lower.next(), lower.next()) {
                    (Some(one), None) => one,
                    _ => c,
                }
            })
            .collect()
    }

    /// `ntpath.isabs(s)`, as CPython 3.13 has it.
    pub fn isabs(s: &str) -> bool {
        let head: String = s.chars().take(3).collect::<String>().replace('/', "\\");
        head.chars().skip(1).take(2).collect::<String>() == ":\\" || head.starts_with("\\\\")
    }

    /// `ntpath.normpath(path)`.
    pub fn normpath(path: &str) -> String {
        let path = path.replace('/', "\\");
        let (drive, root, rest) = splitroot(&path);
        let prefix = format!("{drive}{root}");
        let mut comps: Vec<String> = rest.split(SEP).map(str::to_string).collect();
        let mut i = 0;
        while i < comps.len() {
            if comps[i].is_empty() || comps[i] == "." {
                comps.remove(i);
            } else if comps[i] == ".." {
                if i > 0 && comps[i - 1] != ".." {
                    comps.drain(i - 1..=i);
                    i -= 1;
                } else if i == 0 && !root.is_empty() {
                    comps.remove(i);
                } else {
                    i += 1;
                }
            } else {
                i += 1;
            }
        }
        if prefix.is_empty() && comps.is_empty() {
            comps.push(".".to_string());
        }
        format!("{prefix}{}", comps.join("\\"))
    }

    /// `ntpath.abspath(path)`, against `cwd`.
    pub fn abspath(path: &str, cwd: &str) -> String {
        if isabs(path) {
            normpath(path)
        } else {
            normpath(&join(cwd, path))
        }
    }

    /// `ntpath.relpath(path, start)`, against `cwd`: `None` where CPython
    /// raises `ValueError`, because the two are on different drives. Each
    /// part is compared as `normcase` has it, so `C:\A` is `c:\a`.
    pub fn relpath(path: &str, start: &str, cwd: &str) -> Option<String> {
        let (start_drive, _, start_rest) = splitroot(&abspath(&normpath(start), cwd));
        let (path_drive, _, path_rest) = splitroot(&abspath(&normpath(path), cwd));
        if normcase(&start_drive) != normcase(&path_drive) {
            return None;
        }
        let parts = |rest: &str| -> Vec<String> {
            if rest.is_empty() {
                Vec::new()
            } else {
                rest.split(SEP).map(str::to_string).collect()
            }
        };
        let (start_list, path_list) = (parts(&start_rest), parts(&path_rest));
        let shared = start_list
            .iter()
            .zip(&path_list)
            .take_while(|(a, b)| normcase(a) == normcase(b))
            .count();
        let mut rel = vec!["..".to_string(); start_list.len() - shared];
        rel.extend(path_list[shared..].iter().cloned());
        Some(if rel.is_empty() { ".".to_string() } else { rel.join("\\") })
    }

    /// What `ntpath.realpath` asks of the system.
    pub trait Disk {
        /// `_getfinalpathname(path)`: the path the system holds the file
        /// under, `\\?\` and all, or the Windows error code it gave.
        fn final_path(&self, path: &str) -> Result<String, i32>;
        /// `os.readlink(path)`, or the error code.
        fn readlink(&self, path: &str) -> Result<String, i32>;
        /// `os.path.islink(path)`.
        fn is_link(&self, path: &str) -> bool;
    }

    const PREFIX: &str = "\\\\?\\";
    const UNC_PREFIX: &str = "\\\\?\\UNC\\";

    /// `ntpath.realpath(path)`, not strict, against `cwd`: the file the
    /// system finds, as much of the path as exists resolved and the rest
    /// joined on.
    ///
    /// One difference, which only an unusual system reaches: CPython
    /// raises for an error code outside its list of codes that mean "stop
    /// resolving here" (a missing file, a missing directory, a bad name and
    /// thirteen more), and this treats every code as one of those.
    pub fn realpath(path: &str, cwd: &str, disk: &dyn Disk) -> String {
        let mut path = normpath(path);
        if normcase(&path) == "nul" {
            return "\\\\.\\NUL".to_string();
        }
        let had_prefix = path.starts_with(PREFIX);
        if !had_prefix && !isabs(&path) {
            path = join(cwd, &path);
        }
        if path.contains('\0') {
            // gh-106242: the system cannot be asked, so the path is the
            // answer, made absolute above
            return normpath(&path);
        }
        let initial = match disk.final_path(&path) {
            Ok(found) => {
                path = found;
                0
            }
            Err(code) => {
                path = final_path_nonstrict(&path, disk);
                code
            }
        };
        if !had_prefix && path.starts_with(PREFIX) {
            let spath = match path.strip_prefix(UNC_PREFIX) {
                Some(rest) => format!("\\\\{rest}"),
                None => path[PREFIX.len()..].to_string(),
            };
            // the plain form only where it names the same file, or where
            // the system cannot find it for the same reason as before
            match disk.final_path(&spath) {
                Ok(found) if found == path => path = spath,
                Ok(_) => {}
                Err(code) if code == initial => path = spath,
                Err(_) => {}
            }
        }
        path
    }

    /// `_getfinalpathname_nonstrict`: as much of the path as the system
    /// finds, and the rest joined on.
    fn final_path_nonstrict(path: &str, disk: &dyn Disk) -> String {
        let mut path = path.to_string();
        let mut tail = String::new();
        while !path.is_empty() {
            if let Ok(found) = disk.final_path(&path) {
                return if tail.is_empty() { found } else { join(&found, &tail) };
            }
            let new_path = readlink_deep(&path, disk);
            if new_path != path {
                return if tail.is_empty() { new_path } else { join(&new_path, &tail) };
            }
            let (head, name) = split(&path);
            if !head.is_empty() && name.is_empty() {
                return format!("{head}{tail}");
            }
            tail = if tail.is_empty() { name } else { join(&name, &tail) };
            path = head;
        }
        tail
    }

    /// `_readlink_deep`: follow links until one does not read.
    fn readlink_deep(path: &str, disk: &dyn Disk) -> String {
        let mut path = path.to_string();
        let mut seen = std::collections::HashSet::new();
        while seen.insert(normcase(&path)) {
            let old = path.clone();
            match disk.readlink(&path) {
                Ok(target) => {
                    path = target;
                    if !isabs(&path) {
                        if !disk.is_link(&old) {
                            path = old;
                            break;
                        }
                        path = normpath(&join(&dirname(&old), &path));
                    }
                }
                Err(_) => break,
            }
        }
        path
    }
}

/// `posixpath`: everywhere but Windows.
pub mod posix {
    /// `posixpath.dirname(p)`.
    pub fn dirname(p: &str) -> String {
        let i = p.rfind('/').map_or(0, |i| i + 1);
        let head = &p[..i];
        if !head.is_empty() && head.chars().any(|c| c != '/') {
            head.trim_end_matches('/').to_string()
        } else {
            head.to_string()
        }
    }

    /// `posixpath.basename(p)`.
    pub fn basename(p: &str) -> String {
        let i = p.rfind('/').map_or(0, |i| i + 1);
        p[i..].to_string()
    }

    /// `posixpath.join(a, b)`.
    pub fn join(a: &str, b: &str) -> String {
        if b.starts_with('/') {
            b.to_string()
        } else if a.is_empty() || a.ends_with('/') {
            format!("{a}{b}")
        } else {
            format!("{a}/{b}")
        }
    }

    /// `posixpath.normcase(s)`: the path itself.
    pub fn normcase(s: &str) -> String {
        s.to_string()
    }

    /// `posixpath.isabs(s)`.
    pub fn isabs(s: &str) -> bool {
        s.starts_with('/')
    }

    /// `posixpath.normpath(path)`.
    pub fn normpath(path: &str) -> String {
        if path.is_empty() {
            return ".".to_string();
        }
        let mut initial = usize::from(path.starts_with('/'));
        if initial == 1 && path.starts_with("//") && !path.starts_with("///") {
            initial = 2;
        }
        let mut comps: Vec<&str> = Vec::new();
        for comp in path.split('/') {
            if comp.is_empty() || comp == "." {
                continue;
            }
            if comp != ".."
                || (initial == 0 && comps.is_empty())
                || comps.last() == Some(&"..")
            {
                comps.push(comp);
            } else if !comps.is_empty() {
                comps.pop();
            }
        }
        let joined = format!("{}{}", "/".repeat(initial), comps.join("/"));
        if joined.is_empty() {
            ".".to_string()
        } else {
            joined
        }
    }

    /// `posixpath.abspath(path)`, against `cwd`.
    pub fn abspath(path: &str, cwd: &str) -> String {
        if isabs(path) {
            normpath(path)
        } else {
            normpath(&join(cwd, path))
        }
    }

    /// `posixpath.relpath(path, start)`, against `cwd`. It never fails:
    /// `Option` only so that it reads as `nt::relpath` does.
    pub fn relpath(path: &str, start: &str, cwd: &str) -> Option<String> {
        let parts = |p: &str| -> Vec<String> {
            abspath(p, cwd).split('/').filter(|x| !x.is_empty()).map(str::to_string).collect()
        };
        let (start_list, path_list) = (parts(start), parts(path));
        let shared = start_list.iter().zip(&path_list).take_while(|(a, b)| a == b).count();
        let mut rel = vec!["..".to_string(); start_list.len() - shared];
        rel.extend(path_list[shared..].iter().cloned());
        Some(if rel.is_empty() { ".".to_string() } else { rel.join("/") })
    }

    /// What `posixpath.realpath` asks of the system.
    pub trait Disk {
        /// Whether `os.lstat(path)` says a symbolic link; `None` when
        /// `lstat` fails.
        fn is_link(&self, path: &str) -> Option<bool>;
        /// `os.readlink(path)`; `None` when it fails.
        fn readlink(&self, path: &str) -> Option<String>;
    }

    /// `posixpath.realpath(path)`, not strict, against `cwd`, as CPython
    /// 3.13 walks it: a component at a time, each link replaced by what it
    /// points to, and a component that does not exist kept as written.
    /// CPython 3.10 and 3.12 walk recursively and reach the same path for
    /// every input but a loop of links, which neither corpus holds.
    pub fn realpath(filename: &str, cwd: &str, disk: &dyn Disk) -> String {
        // the parts still to resolve, last first; None marks a link whose
        // target has just been resolved, with the link under it
        let mut rest: Vec<Option<String>> =
            filename.split('/').rev().map(|s| Some(s.to_string())).collect();
        let mut part_count = rest.len();
        let mut path =
            if filename.starts_with('/') { "/".to_string() } else { cwd.to_string() };
        let mut seen: std::collections::HashMap<String, Option<String>> =
            std::collections::HashMap::new();
        while part_count > 0 {
            let name = match rest.pop() {
                Some(Some(name)) => name,
                Some(None) => {
                    // a link's target is resolved: remember where it led
                    if let Some(Some(link)) = rest.pop() {
                        seen.insert(link, Some(path.clone()));
                    }
                    continue;
                }
                None => break,
            };
            part_count -= 1;
            if name.is_empty() || name == "." {
                continue;
            }
            if name == ".." {
                path = match path.rfind('/') {
                    Some(0) | None => "/".to_string(),
                    Some(i) => path[..i].to_string(),
                };
                continue;
            }
            let newpath =
                if path == "/" { format!("/{name}") } else { format!("{path}/{name}") };
            if disk.is_link(&newpath) != Some(true) {
                path = newpath;
                continue;
            }
            if let Some(cached) = seen.get(&newpath) {
                // resolved before, or a loop: CPython keeps the link's own
                // path for a loop when it is not strict
                path = cached.clone().unwrap_or(newpath);
                continue;
            }
            let Some(target) = disk.readlink(&newpath) else {
                path = newpath;
                continue;
            };
            if target.starts_with('/') {
                path = "/".to_string();
            }
            seen.insert(newpath.clone(), None);
            rest.push(Some(newpath));
            rest.push(None);
            let parts: Vec<&str> = target.split('/').collect();
            part_count += parts.len();
            rest.extend(parts.into_iter().rev().map(|p| Some(p.to_string())));
        }
        path
    }
}

/// The flavour this platform's CPython uses.
#[cfg(windows)]
pub use nt as os_path;
/// The flavour this platform's CPython uses.
#[cfg(not(windows))]
pub use posix as os_path;

/// `os.sep`.
pub const SEP: &str = if cfg!(windows) { "\\" } else { "/" };

/// The current directory, as `os.getcwd()` gives it.
pub fn getcwd() -> String {
    std::env::current_dir().map(|p| p.to_string_lossy().into_owned()).unwrap_or_default()
}

/// `os.path.abspath(path)`.
pub fn abspath(path: &str) -> String {
    os_path::abspath(path, &getcwd())
}

/// `os.path.relpath(path, start)`: `None` where CPython raises
/// `ValueError` (on Windows, two drives).
pub fn relpath(path: &str, start: &str) -> Option<String> {
    os_path::relpath(path, start, &getcwd())
}

/// The disk itself, as each flavour's `realpath` asks it.
pub struct RealDisk;

impl nt::Disk for RealDisk {
    fn final_path(&self, path: &str) -> Result<String, i32> {
        // std's canonicalize is GetFinalPathNameByHandleW on a handle opened
        // with FILE_FLAG_BACKUP_SEMANTICS, which is what _getfinalpathname
        // does; its error is the system's code
        std::fs::canonicalize(path)
            .map(|found| found.to_string_lossy().into_owned())
            .map_err(|e| e.raw_os_error().unwrap_or(-1))
    }

    fn readlink(&self, path: &str) -> Result<String, i32> {
        std::fs::read_link(path)
            .map(|found| found.to_string_lossy().into_owned())
            .map_err(|e| e.raw_os_error().unwrap_or(-1))
    }

    fn is_link(&self, path: &str) -> bool {
        std::fs::symlink_metadata(path).is_ok_and(|m| m.file_type().is_symlink())
    }
}

impl posix::Disk for RealDisk {
    fn is_link(&self, path: &str) -> Option<bool> {
        std::fs::symlink_metadata(path).ok().map(|m| m.file_type().is_symlink())
    }

    fn readlink(&self, path: &str) -> Option<String> {
        std::fs::read_link(path).ok().map(|found| found.to_string_lossy().into_owned())
    }
}

/// `os.path.realpath(path)`, not strict: links resolved as far as the
/// path exists, and the rest joined on, as this platform's CPython does
/// it. The budget's `fs:` grants (sabline-spec 5.1's resolution R) and the
/// effect checker's question - is this file inside the shipped standard
/// library - both read it.
pub fn realpath(path: &str) -> String {
    #[cfg(windows)]
    {
        nt::realpath(path, &getcwd(), &RealDisk)
    }
    #[cfg(not(windows))]
    {
        posix::realpath(path, &getcwd(), &RealDisk)
    }
}

/// `os.path.exists(path)`.
pub fn exists(path: &str) -> bool {
    std::path::Path::new(path).exists()
}

#[cfg(test)]
mod tests {
    use super::{nt, posix};

    #[test]
    fn ntpath_matches_cpython() {
        // Every row was read from CPython 3.13's ntpath.
        assert_eq!(nt::dirname(r"D:\x\examples\a.vel"), r"D:\x\examples");
        assert_eq!(nt::dirname("examples/a.vel"), "examples");
        assert_eq!(nt::dirname("a.vel"), "");
        assert_eq!(nt::dirname(r"D:\a.vel"), r"D:\");
        assert_eq!(nt::dirname(r"D:\x\\a.vel"), r"D:\x");
        assert_eq!(nt::basename(r"D:\x\examples\a.vel"), "a.vel");
        assert_eq!(nt::basename("lib/util.vel"), "util.vel");
        assert_eq!(nt::join(r"D:\x\examples", "std.vel"), r"D:\x\examples\std.vel");
        assert_eq!(nt::join(r"D:\x\examples", "lib/util.vel"), r"D:\x\examples\lib/util.vel");
        assert_eq!(nt::join("examples", "../stdlib/std.vel"), r"examples\../stdlib/std.vel");
        assert_eq!(nt::join(r"D:\x", r"\abs.vel"), r"D:\abs.vel");
        assert_eq!(nt::join(r"D:\x", r"C:\abs.vel"), r"C:\abs.vel");
        assert_eq!(nt::join(r"D:\x", "C:rel.vel"), "C:rel.vel");
        assert_eq!(nt::join("D:", "rel.vel"), "D:rel.vel");
        assert_eq!(nt::join(r"D:\x\", "a.vel"), r"D:\x\a.vel");
        assert_eq!(nt::join(r"\\srv\share", "a.vel"), r"\\srv\share\a.vel");
        assert_eq!(nt::normcase("D:/X/A.VEL"), r"d:\x\a.vel");
        assert_eq!(nt::normpath(r"D:\x\..\y\.\a.vel"), r"D:\y\a.vel");
        assert_eq!(nt::normpath("a/../../b"), r"..\b");
        assert_eq!(nt::normpath(""), ".");
        assert_eq!(nt::abspath("a.vel", r"D:\w"), r"D:\w\a.vel");
        assert_eq!(nt::abspath(r"D:\w\..\a.vel", r"C:\q"), r"D:\a.vel");
        assert!(nt::isabs(r"D:\a"));
        assert!(!nt::isabs("D:a"));
        assert!(!nt::isabs("a"));
        let rel = |p: &str, start: &str| nt::relpath(p, start, r"C:\w");
        assert_eq!(rel(r"C:\a\B\c.vel", r"c:\A\b").as_deref(), Some("c.vel"));
        assert_eq!(rel(r"C:\a\x.vel", r"C:\a\b\c").as_deref(), Some(r"..\..\x.vel"));
        assert_eq!(rel(r"C:\a", r"C:\a").as_deref(), Some("."));
        assert_eq!(rel("x.vel", r"C:\w").as_deref(), Some("x.vel"));
        assert_eq!(rel(r"D:\a", r"C:\a"), None, "ValueError: on mount 'D:', start on 'C:'");
    }

    #[test]
    fn posixpath_matches_cpython() {
        // Every row was read from CPython 3.13's posixpath.
        assert_eq!(posix::dirname("/x/examples/a.vel"), "/x/examples");
        assert_eq!(posix::dirname("a.vel"), "");
        assert_eq!(posix::dirname("/a.vel"), "/");
        assert_eq!(posix::dirname("//a.vel"), "//");
        assert_eq!(posix::dirname("/x//a.vel"), "/x");
        assert_eq!(posix::basename("/x/lib/util.vel"), "util.vel");
        assert_eq!(posix::join("/x/examples", "std.vel"), "/x/examples/std.vel");
        assert_eq!(posix::join("/x/examples/", "std.vel"), "/x/examples/std.vel");
        assert_eq!(posix::join("/x", "/abs.vel"), "/abs.vel");
        assert_eq!(posix::join("", "a.vel"), "a.vel");
        assert_eq!(posix::normpath("/x/../y/./a.vel"), "/y/a.vel");
        assert_eq!(posix::normpath("a/../../b"), "../b");
        assert_eq!(posix::normpath("//x"), "//x");
        assert_eq!(posix::normpath("///x"), "/x");
        assert_eq!(posix::abspath("a.vel", "/w"), "/w/a.vel");
        let rel = |p: &str, start: &str| posix::relpath(p, start, "/w");
        assert_eq!(rel("/a/b/c.vel", "/a/x/y").as_deref(), Some("../../b/c.vel"));
        assert_eq!(rel("/a", "/a").as_deref(), Some("."));
        assert_eq!(rel("/", "/a/b").as_deref(), Some("../.."));
        assert_eq!(rel("x.vel", "/w").as_deref(), Some("x.vel"));
    }

    /// A disk of directories and links, the one CPython was given with
    /// `os.lstat` and `os.readlink` patched to read it.
    struct PosixFake;

    const LINKS: &[(&str, &str)] = &[
        ("/var", "private/var"),
        ("/a/l", "/b"),
        ("/a/loop", "loop2"),
        ("/a/loop2", "loop"),
        ("/a/up", "../c"),
        ("/a/rel", "sub/x"),
        ("/a/chain", "l/deeper"),
    ];
    const DIRS: &[&str] =
        &["/", "/private", "/private/var", "/b", "/a", "/c", "/a/sub", "/b/deeper"];

    impl posix::Disk for PosixFake {
        fn is_link(&self, path: &str) -> Option<bool> {
            if LINKS.iter().any(|(l, _)| *l == path) {
                Some(true)
            } else if DIRS.contains(&path) {
                Some(false)
            } else {
                None
            }
        }

        fn readlink(&self, path: &str) -> Option<String> {
            LINKS.iter().find(|(l, _)| *l == path).map(|(_, t)| t.to_string())
        }
    }

    #[test]
    fn posix_realpath_matches_cpython() {
        // Every row is CPython 3.13's posixpath.realpath over this disk,
        // with the working directory /a/sub.
        let rows = [
            ("/var/folders/x", "/private/var/folders/x"),
            ("var/x", "/a/sub/var/x"),
            ("/a/l/q", "/b/q"),
            ("/a/up/z", "/c/z"),
            ("/a/rel/../k", "/a/sub/k"),
            ("/a/loop/z", "/a/loop/z"),
            ("/a/chain/m", "/b/deeper/m"),
            ("../../..", "/"),
            ("/nonexistent/./y/../z", "/nonexistent/z"),
            ("x/../../y", "/a/y"),
            ("/a//sub/", "/a/sub"),
            ("", "/a/sub"),
            ("/a/l/../..", "/"),
            ("./a", "/a/sub/a"),
        ];
        for (given, want) in rows {
            assert_eq!(posix::realpath(given, "/a/sub", &PosixFake), want, "{given:?}");
        }
    }

    /// A Windows disk: what exists, and one junction the system resolves
    /// on its own - the fake CPython was given as `_getfinalpathname`.
    struct NtFake;

    const EXIST: &[&str] =
        &["c:\\", "c:\\w", "c:\\w\\data", "c:\\real", "c:\\real\\in", "d:\\"];

    impl nt::Disk for NtFake {
        fn final_path(&self, path: &str) -> Result<String, i32> {
            let q = path.strip_prefix("\\\\?\\").unwrap_or(path).to_lowercase();
            let mut low = q.trim_end_matches('\\').to_string();
            if low.is_empty() {
                low = q.clone();
            }
            if low.ends_with(':') {
                low.push('\\');
            }
            let junction = "c:\\w\\j";
            if low == junction || low.starts_with(&format!("{junction}\\")) {
                low = format!("c:\\real{}", &low[junction.len()..]);
            }
            if EXIST.contains(&low.as_str()) {
                let mut out = low[..1].to_uppercase();
                out.push_str(&low[1..]);
                return Ok(format!("\\\\?\\{out}"));
            }
            Err(if EXIST.contains(&nt::dirname(&low).as_str()) { 2 } else { 3 })
        }

        fn readlink(&self, _path: &str) -> Result<String, i32> {
            Err(4390)
        }

        fn is_link(&self, _path: &str) -> bool {
            false
        }
    }

    #[test]
    fn nt_realpath_matches_cpython() {
        // Every row is CPython 3.13's ntpath.realpath over this disk, with
        // the working directory C:\w. `..\up` keeps its `..` because this
        // fake, unlike the system, does not read one.
        let rows = [
            (r"data", r"C:\w\data"),
            (r"data\new\x.txt", r"C:\w\data\new\x.txt"),
            (r".\with a space", r"C:\w\with a space"),
            (r"..\up", r"C:\w\..\up"),
            (r"C:\real\in\f", r"C:\real\in\f"),
            (r"j\in\f", r"C:\real\in\f"),
            (r"j\nope\f", r"C:\real\nope\f"),
            (r"D:\x\y", r"D:\x\y"),
            (r"nul", r"\\.\NUL"),
            (r"C:/w/data/./a/../b", r"C:\w\data\b"),
            (r"\rooted\x", r"C:\rooted\x"),
            (r"q:\no\such", r"q:\no\such"),
        ];
        for (given, want) in rows {
            assert_eq!(nt::realpath(given, r"C:\w", &NtFake), want, "{given:?}");
        }
        assert_eq!(nt::realpath("a\0b", r"C:\w", &NtFake), "C:\\w\\a\0b");
    }

    #[test]
    fn nt_normcase_lowers_one_character_for_one() {
        // CPython 3.13 on Windows, LCMapStringEx: no final sigma, and a
        // capital I with a dot stays itself
        assert_eq!(nt::normcase("C:/ΑΣ ΑΣ/\u{130}x/CAFÉ"), "c:\\ασ ασ\\\u{130}x\\café");
    }
}
