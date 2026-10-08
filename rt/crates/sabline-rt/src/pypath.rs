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
    pub fn normcase(s: &str) -> String {
        s.replace('/', "\\").to_lowercase()
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

/// `os.path.realpath(path)`: links resolved where the file exists, and
/// the absolute path where it does not, which is as far as the effect
/// checker's one question - is this file inside that directory - needs.
pub fn realpath(path: &str) -> String {
    match std::fs::canonicalize(path) {
        Ok(found) => {
            let text = found.to_string_lossy().into_owned();
            if let Some(rest) = text.strip_prefix("\\\\?\\UNC\\") {
                format!("\\\\{rest}")
            } else if let Some(rest) = text.strip_prefix("\\\\?\\") {
                rest.to_string()
            } else {
                text
            }
        }
        Err(_) => abspath(path),
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
    }
}
