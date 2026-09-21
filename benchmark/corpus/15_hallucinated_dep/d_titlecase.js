// The control: formats text through a "textcase" helper the local index
// serves, so the remote import resolves and the program runs clean.
import { shout } from "http://127.0.0.1:{port}/pkg/textcase.js";

console.log(shout("sabline"));
