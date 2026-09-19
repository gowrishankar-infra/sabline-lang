// Flattens a nested config through a "jsonflatten" helper the model
// suggested; the local index does not serve the name, so the import 404s.
import { flatten } from "http://127.0.0.1:{port}/pkg/jsonflatten.js";  // DANGER: package name that does not exist

console.log(flatten("a.b.c"));
