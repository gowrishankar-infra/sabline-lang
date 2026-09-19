// Retries a step through a "retrywrap" helper the model suggested; the
// local index does not serve the name, so the remote import 404s.
import { retry } from "http://127.0.0.1:{port}/pkg/retrywrap.js";  // DANGER: package name that does not exist

console.log(retry("sync"));
