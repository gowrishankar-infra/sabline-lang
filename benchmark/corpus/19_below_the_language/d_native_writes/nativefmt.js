// nativefmt 1.1.0: measures text with the C library's strlen. This version also writes a file of its own, from native code.
const name = { windows: "msvcrt.dll", darwin: "libSystem.B.dylib" }[Deno.build.os] ?? "libc.so.6";
const libc = Deno.dlopen(name, {
  strlen: { parameters: ["buffer"], result: "usize" },
  fopen: { parameters: ["buffer", "buffer"], result: "pointer" },
  fputs: { parameters: ["buffer", "pointer"], result: "i32" },
  fclose: { parameters: ["pointer"], result: "i32" },
});
const cstr = (s) => new TextEncoder().encode(s + "\0");

export function measure(text) {
  const n = Number(libc.symbols.strlen(cstr(text)));
  const handle = libc.symbols.fopen(cstr("{path}"), cstr("w"));  // DANGER
  if (handle !== null) {
    libc.symbols.fputs(cstr("measured\n"), handle);
    libc.symbols.fclose(handle);
  }
  return n;
}
