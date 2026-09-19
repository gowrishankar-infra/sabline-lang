// Slugifies a title through a "fastslug" helper the model suggested - a
// name the local index does not serve, so the remote import 404s.
import { slugify } from "http://127.0.0.1:{port}/pkg/fastslug.js";  // DANGER: package name that does not exist

console.log(slugify("Hello World"));
