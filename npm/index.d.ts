export type Effect = "io" | "fs" | "net" | "clock" | "rand" | "ffi";

export interface Problem {
  code: string;
  message: string;
  line: number;
  file: string | null;
  fixes: string[];
}

export interface CheckResult {
  ok: boolean;
  problems: Problem[];
  proven: string[];
  runtime_checked: string[];
}

export interface AuditFunction {
  name: string;
  effects: Effect[];
  can_fail: boolean;
  requires: string[];
  ensures: string[];
  status: string;
}

export interface AuditResult {
  schema: "sabline.audit/1";
  sabline_version: string;
  ok: boolean;
  problems: Problem[];
  effects: Effect[];
  functions: AuditFunction[];
  proven_share: number | null;
  safe_command: string;
  warnings: string[];
}

export interface RunResult {
  ok: boolean;
  output: string;
  logs: string;
  problems: Problem[];
  refusedEffect: Effect | null;
  exitCode: number;
}

export interface RunOptions {
  allow?: Effect[];
  stdin?: string;
  args?: string[];
}

export function check(source: string): Promise<CheckResult>;
export function audit(source: string): Promise<AuditResult>;
export function run(source: string, options?: RunOptions): Promise<RunResult>;
export function card(): Promise<string>;
