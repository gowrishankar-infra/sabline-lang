# Web / registry / crawler rules: sourced reference

Retrieved 2026-09-25. Method: raw page fetch with curl (HTML stripped locally), GitHub source read with `gh api` / raw.githubusercontent.com, and WebSearch only to locate pages. Everything in quotation marks or `>` blocks is copied verbatim from the cited URL. Anything not verified is labelled **(from memory, not verified)** or **(third-party)**. "Inference" marks my reading, not the vendor's words.

Pages that were blocked or gone:
- `developer.x.com` card docs now 307-redirect to `https://docs.x.com/` (overview) and the pages no longer exist on docs.x.com (404). I used Wayback Machine snapshots of X's own pages (Feb 2026).
- `www.bing.com/webmasters/help/...` is a JS-only shell. I read the same article through Bing's own content API `https://www.bing.com/webmasters/api/help/htmlcontent?ArticleId=8c184ec0`.
- `searchengineland.com` returned 403. I used a Wayback snapshot (2026-09-04).
- `developers.facebook.com` returned HTTP 400 to curl. WebFetch returned a summary (see §6). Treat its wording as close to verbatim, not guaranteed.
- `crates.io/category_slugs` is an SPA (curl got 404). I used the crates.io API `https://crates.io/api/v1/category_slugs`.

---

## 1. Package / listing metadata limits

### 1a. GitHub repository

**Description max length: 350 characters. Not in GitHub Docs.**
- GitHub's REST OpenAPI description (`github/rest-api-description`, `api.github.com.json`, `POST /user/repos` and `PATCH /repos/{owner}/{repo}`) sets `description` to `{"description": "A short description of the repository.", "type": "string"}`. It has no `maxLength`.
- The 350 figure comes from the server's error when you exceed it. GitHub Desktop issue desktop/desktop#19465 (2024-10-29) is titled "Publishing a repository to an organization throws an incorrect error when the description exceeds 350 characters". A web search surfaced the error text "Description cannot be more than 350 characters" **(third-party wording, not verified against GitHub)**.

**Topics.** Source: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics
> When creating a topic:
> - Use lowercase letters, numbers, and hyphens.
> - Use 50 characters or less.
> - Add no more than 20 topics.

> Topic names are always public, even if you create the topic from within a private repository.

The REST API (`PUT /repos/{owner}/{repo}/topics`, `names`) adds: "**Note:** Topic `names` will be saved as lowercase."

The UI error "must start with a lowercase letter or number" is **(from memory, not verified)**.

### 1b. PyPI / Python core metadata

Core metadata spec, version 2.6 ("approved in May 2026"): https://packaging.python.org/en/latest/specifications/core-metadata/
- **Summary**: "A one-line summary of what the distribution does." Example: `Summary: A module for collecting votes from beagles.`
- **Keywords**: "A list of additional keywords, separated by commas, to be used to assist searching for the distribution in a larger catalog." Example: `Keywords: dog,puppy,voting,election`. The spec adds: "The specification previously showed keywords separated by spaces, but distutils and setuptools implemented it with commas."
- **Classifier (multiple use)**: "Each entry is a string giving a single classification value for the distribution. Classifiers are described in PEP 301, and the Python Package Index publishes a dynamic list of currently defined classifiers." It also says: "The use of License :: classifiers is deprecated as of Metadata 2.4, use License-Expression instead."

pyproject.toml spec: https://packaging.python.org/en/latest/specifications/pyproject-toml/
- `description`: "TOML type: string", "Corresponding core metadata field: Summary". Rule: "The summary description of the project in one line. Tools MAY error if this includes multiple lines."
- `keywords`: "TOML type: array of strings". Rule: "The keywords for the project."
- `classifiers`: "Trove classifiers which apply to the project."

**What PyPI actually enforces** (source code in pypi/warehouse `warehouse/forklift/metadata.py`, main, last commit 2026-05-23):
```python
_LENGTH_LIMITS = {
    "summary": 512,
}
...
f"{email_name!r} field must be {limit} characters or less.",
...
InvalidMetadata("classifier", f"{c!r} is not a valid classifier.")
... f"The classifier {classifier!r} has been deprecated, "
```
Warehouse parses uploads with `Metadata.from_email(content)` from `packaging`. The summary validator in pypa/packaging `src/packaging/metadata.py` is:
```python
def _process_summary(self, value: str) -> str:
    """Check the field contains no line breaks."""
    if _LINE_BOUNDARY_RE.search(value):
        raise self._invalid_metadata(f"{self.raw_name!r} must be a single line")
```
So in practice: **Summary must be 512 characters or fewer and a single line.** Unknown or deprecated classifiers are rejected. There is no length or count limit on keywords.

**Classifiers relevant to security, AI, and language tooling.** Each string below is in pypa/trove-classifiers main (release 2026.9.21.13):
- `Topic :: Security`
- `Topic :: Security :: Cryptography`
- `Topic :: Scientific/Engineering :: Artificial Intelligence`
- `Topic :: Software Development :: Compilers`
- `Topic :: Software Development :: Interpreters`
- `Topic :: Software Development :: Code Generators`
- `Topic :: Software Development :: Quality Assurance`
- `Topic :: Software Development :: Testing`
- `Topic :: Software Development :: Build Tools`
- `Environment :: Console`
- `Intended Audience :: Developers`
- `Operating System :: OS Independent`
- `Programming Language :: Rust`
- `Programming Language :: Python :: 3 :: Only`
- `Typing :: Typed`
- `Development Status :: 4 - Beta`
- `Development Status :: 5 - Production/Stable`

There is no MCP, agent, or LLM `Framework ::` classifier. A grep for "mcp", "agent", and "llm" finds only "Mail Transport Agents".

### 1c. npm package.json

Source: https://docs.npmjs.com/cli/v11/configuring-npm/package-json/
- description: "Put a description in it. It's a string. This helps people discover your package, as it's listed in `npm search`."
- keywords: "Put keywords in it. It's an array of strings. This helps people discover your package as it's listed in `npm search`."
- **No length or count limit is documented for either field.** The only documented length rule on the page is for `name`: "The name must be less than or equal to 214 characters. This includes the scope for scoped packages."

### 1d. crates.io / Cargo

Cargo manifest reference: https://doc.rust-lang.org/cargo/reference/manifest.html
- description: "The description is a short blurb about the package. crates.io will display this with your package. This should be plain text (not Markdown)." and "Note: crates.io requires the description to be set."
- keywords: "Note: crates.io allows a maximum of 5 keywords. Each keyword must be ASCII text, have at most 20 characters, start with an alphanumeric character, and only contain letters, numbers, `_`, `-` or `+`."
- categories: "Note: crates.io has a maximum of 5 categories. Each category should match one of the strings available at https://crates.io/category_slugs, and must match exactly."

**Server enforcement** (rust-lang/crates.io `src/controllers/krate/publish.rs`, main, last commit 2026-09-21):
```rust
const MAX_DESCRIPTION_LENGTH: usize = 1000;
... "The `description` is too long. A maximum of {MAX_DESCRIPTION_LENGTH} characters are currently allowed."
if keywords.len() > 5 { ... "expected at most 5 keywords per crate"
if keyword.len() > 20 { ... "keywords must have less than 20 characters"   // check is > 20, so 20 is allowed
if categories.len() > 5 { ... "expected at most 5 categories per crate"
"The following category slugs are not currently supported on crates.io: {unknown_categories}\n\nSee https://{domain}/category_slugs for a list of supported slugs."
"missing or empty metadata fields: {}. ..."   // description and (license or license-file) are required
```
- The description check uses Rust `str::len()`, which counts **UTF-8 bytes** (the message says "characters"). Inference: keep it ASCII or stay well under 1000.
- **An unknown category slug is a hard publish error.**
- The keyword charset check is `Keyword::valid_name`: first character ASCII alphanumeric, then only ASCII alphanumerics, `_`, `-`, or `+`.

**Valid category slugs.** There are 104 in total, from `https://crates.io/api/v1/category_slugs`. The ones that fit a language runtime or security tool:

| slug | crates.io description (verbatim) |
|---|---|
| `compilers` | Compiler implementations, including interpreters and transpilers. |
| `development-tools` | Crates that provide developer-facing features such as testing, debugging, linting, performance profiling, autocompletion, formatting, and more. |
| `command-line-utilities` | Applications to run at the command line. |
| `security` | Crates related to cybersecurity, penetration testing, code review, vulnerability research, and reverse engineering. |
| `artificial-intelligence` | Crates for machine learning, deep learning, large language models, AI agents, and related tooling. … |
| `parser-implementations` | Parsers implemented for particular formats or languages. |
| `development-tools::testing` | Crates to help you verify the correctness of your code. |
| `virtualization` | For the creation and management of virtual environments and resources of any form including containerization systems. |
| `wasm` | Crates for use when targeting WebAssembly, or for manipulating WebAssembly. |
| `cryptography` | Algorithms intended for securing data. |
| `authentication` | Crates to help with the process of confirming identities. |

`command-line-interface` is for crates that *help build* CLIs ("argument parsers, line-editing…"), not for CLI apps.

### 1e. VS Code Marketplace (extension package.json)

Source: https://code.visualstudio.com/api/references/extension-manifest (markdown source: microsoft/vscode-docs `api/references/extension-manifest.md`)
- `displayName`: "The display name for the extension used in the Marketplace. The display name must be unique to the Marketplace."
- `description`: "A short description of what your extension is and does." No length limit is documented.
- `categories`: "The categories you want to use for the extensions. Allowed values: [Programming Languages, Snippets, Linters, Themes, Debuggers, Formatters, Keymaps, SCM Providers, Other, Extension Packs, Language Packs, Data Science, Machine Learning, Visualization, Notebooks, Education, Testing]"
- Also on that page: "Use `Programming Languages` for general language features like syntax highlighting and code completions. The category `Language Packs` is reserved for display language extensions (for example, localized Bulgarian)."
- `keywords`: "An array of keywords to make it easier to find the extension. These are included with other extension Tags on the Marketplace. This list is currently limited to 30 keywords." Git blame shows this line was last changed in commit a3accb1 on 2025-05-27 ("Update extension manifest info").

Checks on the limit:
- **vsce does not enforce the 30 client-side.** I read vsce v4.0.0 `src/package.ts` and `src/validation.ts` and found no keyword-count check. vsce's `TagsProcessor` also *adds* auto-generated tags. For example, contributing `languageModelTools` adds `tools` and `language-model-tools`, and `modelContextServerCollections` adds `mcp`. Any enforcement happens on the Marketplace server.
- History: microsoft/vscode-discussions#426 (2023-01-25, Microsoft staff) said "We enabled the validation rule to reject any extensions with more than 10 keywords in the `package.json`." The error was "`You exceeded the number of allowed tags of 10.`" The post was then updated: "We turned off the tag validation for now… I suggest you to keep `keywords`/`tags` under 10". A commenter reported that auto-added tags counted toward the limit. Inference: the current documented limit is 30, but staying at 10 or fewer user keywords avoids the tag-count ambiguity.
- VS Code's own manifest schema lists more categories than the docs. microsoft/vscode `src/vs/platform/extensions/common/extensions.ts` has `EXTENSION_CATEGORIES = ['AI','Azure','Chat','Data Science','Debuggers','Extension Packs','Education','Formatters','Keymaps','Language Packs','Linters','Machine Learning','Notebooks','Programming Languages','SCM Providers','Snippets','Testing','Themes','Visualization','Other']`. So `AI` and `Chat` are valid in the editor's schema even though the docs page omits them.

### 1f. Official MCP Registry `server.json`

- The current schema version is set in the registry code (modelcontextprotocol/registry `pkg/model/constants.go`, main): `CurrentSchemaVersion = "2025-12-11"` and `CurrentSchemaURL = "https://static.modelcontextprotocol.io/schemas/" + CurrentSchemaVersion + "/server.schema.json"`. The latest registry release is v1.8.1 (2026-08-06).
- The published schema is https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json (fetched, HTTP 200). The repo draft is https://raw.githubusercontent.com/modelcontextprotocol/registry/main/docs/reference/server-json/draft/server.schema.json. Both define the same ServerDetail limits:

```json
"description": {
  "description": "Clear human-readable explanation of server functionality. Should focus on capabilities, not implementation details.",
  "example": "MCP server providing weather data and forecasts via OpenWeatherMap API",
  "maxLength": 100, "minLength": 1, "type": "string" },
"title": {
  "description": "Optional human-readable title or display name for the MCP server. MCP subregistries or clients MAY choose to use this for display purposes.",
  "example": "Weather API", "maxLength": 100, "minLength": 1, "type": "string" },
"name":    { "maxLength": 200, "minLength": 3, "pattern": "^[a-zA-Z0-9.-]+/[a-zA-Z0-9._-]+$" },
"version": { "maxLength": 255, "description": "... Version ranges are rejected (e.g., '^1.2.3', '~1.2.3', '>=1.2.3', '1.x', '1.*')." },
"required": ["name", "description", "version"]
```
- **The 100 is counted in Unicode code points, not bytes.** The registry validates with `github.com/santhosh-tekuri/jsonschema/v5 v5.3.1`. That library's `schema.go` uses `length := utf8.RuneCount([]byte(v))` before comparing against `MaxLength`.
- `_meta.io.modelcontextprotocol.registry/publisher-provided` has a size limit, from `internal/validators/validators.go`: "extension exceeds 4KB limit".

**Updating the description means publishing a new version.**
- FAQ (`docs/modelcontextprotocol-io/faq.mdx`): "### How do I update my server metadata? Submit a new `server.json` with a unique version string. Once published, version metadata is immutable (similar to npm)."
- Versioning (`docs/modelcontextprotocol-io/versioning.mdx`): "The version string **MUST** be unique for each publication of the server. Once published, the version string (and other metadata) cannot be changed."
- Server error (`internal/database/database.go`): `ErrInvalidVersion = errors.New("invalid version: cannot publish duplicate version")`
- The registry-only update pattern, also from versioning.mdx: "If you anticipate publishing a server multiple times _without_ changing the underlying package or remote URL — for example, to update other parts of the metadata — use semantic prerelease versions" (example `"version": "1.2.3-1"` with package `"version": "1.2.3"`).
- Its warning: "prerelease versions such as `1.2.3-1` are sorted before regular semantic versions such as `1.2.3`. Therefore, if you publish a prerelease version _after_ its corresponding regular version, the prerelease version will **not** be marked as "latest"."
- Inference: to fix the description of an already-published `X.Y.Z` so that it becomes "latest", publish a higher regular version. `X.Y.Z-1` will not become latest.
- Deleting: `mcp-publisher status --status deleted`. The FAQ adds: "Server metadata is never permanently removed from the registry."

### 1g. mcpb (MCP Bundle) manifest.json

Sources: modelcontextprotocol/mcpb `MANIFEST.md` ("Current version: `0.3`"), `schemas/mcpb-manifest-latest.schema.json` (manifest_version const "0.3"), `schemas/mcpb-manifest-v0.4.schema.json`, and `src/schemas/0.3.ts` / `0.4.ts`. Repo main was last committed 2026-04-22; the latest release is v2.1.2.
- Schema: `"description": {"type": "string"}` and `"long_description": {"type": "string"}`. Required fields: `["name","version","description","author","server"]`.
- zod: `description: z.string()`, `long_description: z.string().optional()`.
- **There is no length limit.** No `maxLength` appears in the latest or v0.4 JSON schema, and no `.max(` appears in the zod schemas.
- MANIFEST.md text:
  - "🌎 **description**: Brief description. This field is localizable."
  - "🌎 **long_description**: Detailed description for extension stores, markdown. This field is localizable."
  - "🌎 **keywords**: Search keywords. This field is localizable."
  - "🌎 **display_name**: Human-friendly name for UI display."

---

## 2. Google Scholar inclusion guidelines

Source (a single page; the sub-sections are anchors `#overview #content #crawl #indexing #troubleshooting #faq`): https://scholar.google.com/intl/en/scholar/inclusion.html

**Individual authors (Overview):**
> make sure that:
> - the full text of your paper is in a PDF file that ends with ".pdf",
> - the title of the paper appears in a large font on top of the first page,
> - the authors of the paper are listed right below the title on a separate line, and
> - there's a bibliography section titled, e.g., "References" or "Bibliography" at the end.
>
> That's it! Our search robots should normally find your paper and include it in Google Scholar within several weeks.

**Content: what counts; preprints and technical reports are explicitly in scope:**
> The content hosted on your website must consist primarily of scholarly articles - journal papers, conference papers, technical reports, or their drafts, dissertations, pre-prints, post-prints, or abstracts. Content such as news or magazine articles, book reviews, and editorials is not appropriate for Google Scholar. Documents larger than 5MB, such as books and long dissertations, should be uploaded to Google Book Search

**The abstract must be visible:**
> To be included, your website must make either the full text of the articles or their complete author-written abstracts freely available and easy to see when users click on your URLs in Google search results. Your website must not require users (or search robots) to sign in, install special software, accept disclaimers, dismiss popup or interstitial advertisements, click on links or buttons, or scroll down the page before they can read the entire abstract of the paper. Sites that show login pages, error pages, or bare bibliographic data without abstracts will not be considered for inclusion and may be removed from Google Scholar.

FAQ, on the abstract meta tag:
> Per content guidelines, the abstract needs to be visible to the user. Meta tags are only visible to the search robots, not to the user. You can display the abstract in any reasonable way, e.g., as a paragraph of text with a heading that says "Abstract".

**File format and size:**
> Your files need to be either in the HTML or in the PDF format. PDF files must have searchable text … Each file must not exceed 5MB in size.

**Browse interface:**
> We recommend that the URL of every article is reachable from the homepage by following at most ten simple HTML links. … If you're hosting a small collection of publications … list all articles on a single HTML page … and include links to their full text in the PDF format.

**Availability and redirects:**
> If you need to move your articles to new URLs, set up HTTP 301 redirects from the old location of each article to its new location. Do not redirect article URLs to the homepage

**Robots:**
> If your website uses a robots.txt file … then it must not block Google's search robots from accessing your articles or your browse URLs.

The page's example is `User-agent: Googlebot` / `Allow: /`.

**One paper per URL:**
> Place each article and each abstract in a separate HTML or PDF file. At this time, we're unable to effectively index multiple abstracts on the same webpage or multiple papers in the same PDF file. Likewise, we're unable to index different sections of the same paper in different files. Each paper must have its own unique URL in order for it to be included in Google Scholar.

**Supported meta tag schemes:**
> Google Scholar supports Highwire Press tags (e.g., citation_title), BE Press tags (e.g., bepress_citation_title), and PRISM tags (e.g., prism.title). Use Dublin Core tags (e.g., DC.title) as a last resort

**Title tag:**
> The title tag, e.g., citation_title or DC.title, must contain the title of the paper. … This tag is required for inclusion in Google Scholar.

**Author tag and name format:**
> The author tag, e.g., citation_author or DC.creator, must contain the authors (and only the actual authors) of the paper. … Author names can be listed either as "Smith, John" or as "John Smith". Put each author name in a separate tag and omit all affiliations, degrees, certifications, etc., from this field. At least one author tag is required for inclusion in Google Scholar.

**Date tag and format:**
> The publication date tag, e.g., citation_publication_date or DC.issued, must contain the date of publication, i.e., the date that would normally be cited in references to this paper from other papers. Don't use it for the date of entry into the repository - that should go into citation_online_date instead. Provide full dates in the "2010/5/12" format if available; or a year alone otherwise. This tag is required for inclusion in Google Scholar.

**Technical reports:**
> For theses, dissertations, and technical reports, provide the remaining bibliographic citation data in the following tags: citation_dissertation_institution, citation_technical_report_institution or DC.publisher for the name of the institution and citation_technical_report_number for the number of the technical report.

Journal and conference papers use: citation_journal_title or citation_conference_title, citation_issn, citation_isbn, citation_volume, citation_issue, citation_firstpage, citation_lastpage.

**citation_pdf_url must be in the same subdirectory:**
> please specify the locations of all full text versions using citation_pdf_url or DC.identifier tags. The content of the tag is the absolute URL of the PDF file; for security reasons, it must refer to a file in the same subdirectory as the HTML abstract.

> all PDF files will be processed as if they had no meta tags at all, unless they're linked from the corresponding HTML abstracts using citation_pdf_url or DC.identifier tags.

**Minimum three fields:**
> you need to provide at least three fields: (1) the title of the article, (2) the full name of at least the first author, and (3) the year of publication. Pages that don't provide any one of these three fields will be processed as if they had no meta tags at all.

**Escaping:**
> All tag values are HTML attributes, so you must escape special characters appropriately … you must still escape the quotes and the angle brackets.

**Tags the page does not mention.** A grep of the page shows no `citation_date`, no `citation_doi`, no `citation_arxiv_id`, and no schema.org. The only date tags named are `citation_publication_date` and `citation_online_date`. Tags outside that list are not documented by Scholar.

**PDF layout without meta tags (§2.a):**
> The title of the paper must be the largest chunk of text on top of the page. Either use font size of at least 24 pt. in PDF … Please use the same font for the entire title. Make sure that all other text on the page, in particular the name of the repository or the journal, is set in a smaller font than the title of the paper

> The authors of the paper must be listed right before or right after the title, in a slightly smaller font that is still larger than normal text. Either use a 16-23 pt. font in PDF … Use "Sentence case" as opposed to "Title Case" for section headings et. al., to avoid confusion with author names. Separate multiple author names with commas or semicolons and omit their affiliations, degrees, and certifications from the author line.

> If the paper is unpublished, include the full date of its present version on a line by itself, e.g., "August 12, 2009".

> Avoid use of Type 3 fonts in PDF files … If you're using LaTeX, consider switching to Type 1 fonts, e.g., \usepackage{times}, \usepackage{helvet}, or \usepackage{palatino}.

**References heading:**
> Mark the section of the paper that contains references to other works with a standard heading, such as "References" or "Bibliography", on a line just by itself. Individual references inside this section should be either numbered "1. - 2. - 3." or "[1] - [2] - [3]" in PDF, or put inside an "<ol>" list in HTML.

**Timing:**
> New papers are normally added several times a week; however, updates of papers that are already included usually take 6-9 months.

---

## 3. IndexNow

Sources: https://www.indexnow.org/documentation, https://www.indexnow.org/faq, https://www.indexnow.org/ , https://www.indexnow.org/searchengines.json

**Endpoints:**
- The documentation page gives `https://<searchengine>/indexnow?url=url-changed&key=your-key`.
- The FAQ says: "You may submit your request to only one of the following participating endpoints. Each endpoint sends your submission directly to its respective search engine, and your submission will be shared across all IndexNow-enabled search engines". It then lists:
  - IndexNow global: `https://api.indexnow.org/indexnow`
  - Amazon: `https://indexnow.amazonbot.amazon/indexnow`
  - Bing: `https://www.bing.com/indexnow`
  - Naver: `https://searchadvisor.naver.com/indexnow`
  - Seznam.cz: `https://search.seznam.cz/indexnow`
  - Yandex: `https://yandex.com/indexnow`
  - Yep: `https://indexnow.yep.com/indexnow`

**Participating engines:**
- The home page says: "has support from Microsoft Bing, Naver, Seznam.cz, Yandex, Yep."
- `searchengines.json` lists bing, yandex, seznam, naver, yep, internetarchive, and amazonbot.
- The documentation page states: "Search engines adopting the IndexNow protocol agree that submitted URLs will be automatically shared with all other participating search engines."

**Key rules.** The two pages differ slightly:
- Documentation: "Your-key should have a minimum of 8 and a maximum of 128 hexadecimal characters. The key can contain only the following characters: lowercase characters (a-z), uppercase characters (A-Z), numbers (0-9), and dashes (-)."
- FAQ: "Your key must be 8 to 128 characters long." and "Allowed characters: lowercase (a to z), uppercase (A to Z), numbers (0 to 9), and hyphens (-)."
- Inference: a 32-character lowercase hex key satisfies both readings.

**Key file:**
- "You must host a UTF-8 encoded text key file {your-key}.txt listing the key in the file at the root directory of your website."
- FAQ: "Save the file in UTF-8 encoding with the key as the filename, followed by .txt. Example if your key is abcd1234, create a file named abcd1234.txt with the contents abcd1234"
- FAQ troubleshooting: "File contents: The text inside must exactly match your API key".

**keyLocation (option 2):**
- "You can also host one to many UTF-8 encoded text key files in other locations within the same host and you must tell search engines the location of this text key file in each IndexNow notification by specifying the location using the keyLocation variable."
- "the location of a key file determines the set of URLs that can be included with this key. A key file located at http://example.com/catalog/key12457EDd.txt can include any URLs starting with http://example.com/catalog/ but cannot include URLs starting with http://example.com/help/."
- "It is strongly recommended that you use Option 1 and place your file key at the root directory of your web server."
- Subdomains: "Each subdomain is treated as a separate host, which means you must create and manage individual key files for each one."

**POST body:**
```
POST /indexnow HTTP/1.1
Content-Type: application/json; charset=utf-8
Host: <searchengine>
{
  "host": "www.example.com",
  "key": "<key>",
  "keyLocation": "https://www.example.com/myIndexNowKey63638.txt",   // optional
  "urlList": ["https://www.example.com/url1", "https://www.example.com/folder/url2"]
}
```

**Maximum URLs per request:**
- "You can submit up to 10,000 URLs per post, mixing http and https URLs if needed."
- FAQ: "Submitting more than this may cause the request to fail or return an HTTP 422 (Unprocessable Entity) response."
- URLs "must be URL-escaped and encoded and please make sure that your URLs follow the RFC-3986 standard for URIs."

**Response codes (documentation table):**

| Code | Meaning | Reason |
|---|---|---|
| 200 | OK | "URL submitted successfully" |
| 202 | Accepted | "URL received. IndexNow key validation pending." |
| 400 | Bad request | "Invalid format" |
| 403 | Forbidden | "In case of key not valid (e.g. key not found, file found but key not in the file)" |
| 422 | Unprocessable Entity | "In case of URLs which don't belong to the host or the key is not matching the schema in the protocol" |
| 429 | Too Many Requests | "Too Many Requests (potential Spam)" |

Also: "The HTTP 200 response code only indicates that the search engine has received your URL."

**Rate and "changed URLs only" rules (FAQ):**
- "IndexNow does not publicly disclose exact rate limits, as each participating search engine sets its own daily submission thresholds per site."
- "Submit only when content has changed. Do not resubmit unchanged URLs."
- "For frequently updated pages, it is best practice to wait at least 5 minutes between updates before resubmitting." The 429 section says "Wait at least 10 minutes before resubmitting the same URL, unless it has changed significantly."
- "IndexNow is intended for notifying search engines about recently added, updated, or deleted URLs. It is not designed for submitting every URL on your site at once." Exception: "If your entire site has been recently updated, such as after a migration or redesign, it is acceptable to submit all URLs using IndexNow."
- "Should I submit URLs that changed before I started using IndexNow? No." Instead: "Use sitemaps with accurate lastmod values to surface content updated before implementation."
- "Yes. You should submit redirected URLs and pages that return HTTP 404 or HTTP 410 status codes."
- "Every URL submitted through IndexNow counts toward your site's crawl quota."

**Bing's own guidance** (Bing Webmaster Guidelines, via `https://www.bing.com/webmasters/api/help/htmlcontent?ArticleId=30fba23a`): "Use IndexNow to notify Bing when: URLs are added / Content is updated / URLs are removed … Avoid batch submissions when possible. Streaming submissions provide faster updates, reduce server load, and improve indexing accuracy."

**Does Google use IndexNow?** There is no current Google statement.
- Google is not in IndexNow's participant lists (home page or searchengines.json).
- "IndexNow" does not appear on Google's "Build and submit a sitemap" or "Ask Google to recrawl your URLs" pages. The recrawl page lists only the URL Inspection tool and sitemaps.
- The only on-record Google statement was given to Search Engine Land on 2021-11-10 (archived: http://web.archive.org/web/20260904130159/https://searchengineland.com/google-is-testing-the-indexnow-protocol-for-sustainability-375932): "We're encouraged by work to make web crawling more efficient, and we will be testing the potential benefits of this protocol," a Google spokesperson added.
- I found no later Google announcement of adoption. **Status: unknown / not adopted as far as public Google docs show.**

---

## 4. robots.txt user-agent tokens

| Token | Vendor doc | Purpose (verbatim) | Obeys robots.txt? |
|---|---|---|---|
| `Googlebot` | https://developers.google.com/crawling/docs/crawlers-fetchers/google-common-crawlers (updated 2026-07-14); https://developers.google.com/search/docs/crawling-indexing/googlebot | "Crawling preferences addressed to the Googlebot user agent affect Google Search (including Discover and all Google Search features), as well as other products such as Google Images, Google Video, Google News, and Discover." | Yes: "Google's common crawlers … always obey robots.txt rules when crawling automatically." |
| `Google-Extended` | same page | "a standalone product token that web publishers can use to manage whether content Google crawls from their sites may be used for training future generations of Gemini models … and for grounding" / "Google-Extended does not impact a site's inclusion in Google Search nor is it used as a ranking signal" / "doesn't have a separate HTTP request user agent string" | Control token only |
| `bingbot` | Bing "Overview of Bing crawlers (user agents)" (ArticleId 8c184ec0) | "Bingbot is our standard crawler and handles most of our crawling needs each day." (UA contains `bingbot/2.0`; Bing also runs AdIdxBot, BingPreview, MicrosoftPreview, BingVideoPreview) | "Robots.txt files can be configured to tell Bing crawlers how to interact with your website." Bing guidelines: avoid "Blocking Bingbot in your robots.txt file"; "robots.txt controls crawl access, not indexing." |
| `OAI-SearchBot` | https://developers.openai.com/api/docs/bots (redirect from platform.openai.com/docs/bots) | "OAI-SearchBot is for search. OAI-SearchBot is used to surface websites in search results in ChatGPT's search features. Sites that are opted out of OAI-SearchBot will not be shown in ChatGPT search answers, though can still appear as navigational links." | Yes (it is a robots.txt tag); "it can take ~24 hours from a site's robots.txt update for our systems to adjust." |
| `GPTBot` | same | "It is used to crawl content that may be used in training our generative AI foundation models. Disallowing GPTBot indicates a site's content should not be used in training generative AI foundation models." | Yes |
| `ChatGPT-User` | same | "When users ask ChatGPT or a CustomGPT a question, it may visit a web page with a ChatGPT-User agent. … ChatGPT-User is not used for crawling the web in an automatic fashion. … ChatGPT-User is not used to determine whether content may appear in Search." | "Because these actions are initiated by a user, robots.txt rules may not apply." |
| `PerplexityBot` | https://docs.perplexity.ai/docs/resources/perplexity-crawlers (redirect from /guides/bots) | "PerplexityBot is designed to surface and link websites in search results on Perplexity. It is not used to crawl content for AI foundation models." | Yes ("we recommend allowing PerplexityBot in your site's robots.txt file"); changes take "up to 24 hours" |
| `Perplexity-User` | same | "Perplexity-User supports user actions within Perplexity. When users ask Perplexity a question, it might visit a web page … It is not used for web crawling or to collect content for training AI foundation models." | "Since a user requested the fetch, this fetcher generally ignores robots.txt rules." |
| `ClaudeBot` | https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler (dated April 7, 2026) | "ClaudeBot helps enhance the utility and safety of our generative AI models by collecting web content that could potentially contribute to their training. … When a site restricts ClaudeBot access, it signals that the site's future materials should be excluded from our AI model training datasets." | Yes, for all three Anthropic bots: "Anthropic's Bots respect "do not crawl" signals by honoring industry standard directives in robots.txt." They also support `Crawl-delay`. |
| `Claude-SearchBot` | same | "Claude-SearchBot navigates the web to improve search result quality for users. … Disabling Claude-SearchBot on your site prevents our system from indexing your content for search optimization" | Yes |
| `Claude-User` | same | "Claude-User supports Claude AI users. When individuals ask questions to Claude, it may access websites using a Claude-User agent. … Disabling Claude-User on your site prevents our system from retrieving your content in response to a user query" | Yes (same statement) |

Notes:
- **Perplexity-User hyphen.** In the table heading of Perplexity's page, the token is typed with U+2011 (non-breaking hyphen): "Perplexity‑User". Everywhere else on the page, and in the UA string, it uses ASCII `-`. Use the ASCII `Perplexity-User` in robots.txt.
- **Googlebot variants.** "both crawler types obey the same product token … you cannot selectively target either Googlebot Smartphone or Googlebot Desktop using robots.txt."
- **Googlebot fetch size.** "Googlebot crawls the first 2MB of a supported file type, and the first 64MB of a PDF file." Google Scholar's own limit is 5MB (§2).
- **Anthropic IP blocking.** "Alternate methods like blocking IP address(es) from which Anthropic Bots operates may not work correctly or persistently guarantee an opt-out".

---

## 5. Sitemaps

sitemaps.org protocol: https://www.sitemaps.org/protocol.html
- Encoding: "All data values in a Sitemap must be entity-escaped. The file itself must be UTF-8 encoded."
- `<loc>`: "This value must be less than 2,048 characters."
- `<lastmod>`: "The date of last modification of the page. This date should be in W3C Datetime format. This format allows you to omit the time portion, if desired, and use YYYY-MM-DD." It continues: "Note that the date must be set to the date the linked page was last modified, not when the sitemap is generated."
- Limits: "each Sitemap file that you provide must have no more than 50,000 URLs and must be no larger than 50MB (52,428,800 bytes). … the sitemap file once uncompressed must be no larger than 50MB." Also: "Sitemap index files may not list more than 50,000 Sitemaps and must be no larger than 50MB (52,428,800 bytes)".
- Location: "all URLs listed in the Sitemap must use the same protocol … and reside on the same host as the Sitemap." It also says: "Sitemap: http://www.example.com/sitemap.xml … This directive is independent of the user-agent line".
- `<changefreq>`: "Please note that the value of this tag is considered a hint and not a command."
- `<priority>`: "Valid values range from 0.0 to 1.0. … The default priority of a page is 0.5."

W3C Datetime (https://www.w3.org/TR/NOTE-datetime) allows these forms:
- `YYYY`
- `YYYY-MM`
- `YYYY-MM-DD`
- `YYYY-MM-DDThh:mmTZD`
- `YYYY-MM-DDThh:mm:ssTZD`
- `YYYY-MM-DDThh:mm:ss.sTZD`

"TZD = time zone designator (Z or +hh:mm or -hh:mm)".

Google, "Build and submit a sitemap": https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap (updated 2026-07-08)
- "Google ignores `<priority>` and `<changefreq>` values."
- "Google uses the `<lastmod>` value if it's consistently and verifiably (for example by comparing to the last modification of the page) accurate. The `<lastmod>` value should reflect the date and time of the last significant update to the page. For example, an update to the main content, the structured data, or links on the page is generally considered significant, however an update to the copyright date is not."
- "All formats limit a single sitemap to 50MB (uncompressed) or 50,000 URLs."
- "Use fully-qualified, absolute URLs in your sitemaps."
- "Keep in mind that submitting a sitemap is merely a hint".
- robots.txt: "You can specify multiple sitemap lines, and there's no limit to the number of sitemaps you can include in your robots.txt file."

Bing guidelines (ArticleId 30fba23a): "freshness signals like accurate lastmod values and HTTP validation headers such as ETags help Bing detect content changes more reliably."

---

## 6. OpenGraph, X cards, GitHub social preview

**OpenGraph** (https://ogp.me/):
- "The four required properties for every page are: og:title … og:type … og:image … og:url - The canonical URL of your object that will be used as its permanent ID in the graph".
- Optional properties include og:description ("A one to two sentence description of your object.") and og:site_name.
- "og:image:alt - … If the page specifies an og:image it should specify og:image:alt."
- "Any non-marked up webpage should be treated as og:type website."
- **ogp.me gives no image-size recommendation.**

Meta's own recommendation (https://developers.facebook.com/docs/sharing/webmasters/images/; curl got HTTP 400, so this is WebFetch's summarised extract, near-verbatim, not guaranteed):
- "Use images that are at least 1200 x 630 pixels for the best display on high resolution devices."
- "The minimum allowed image dimension is 200 x 200 pixels."
- "as close to 1.91:1 aspect ratio as possible"
- "must not exceed 8 MB"

**X summary_large_image.** X's own page is now removed; this is the Wayback snapshot of 2026-02-04, http://web.archive.org/web/20260204074639/https://developer.x.com/en/docs/x-for-websites/cards/overview/summary-card-with-large-image.
- `twitter:card` — "Must be set to a value of "summary_large_image"" (Required: Yes)
- `twitter:title` — Required: Yes
- `twitter:image`: "Images for this Card support an aspect ratio of 2:1 with minimum dimensions of 300x157 or maximum of 4096x4096 pixels. Images must be less than 5MB in size. JPG, PNG, WEBP and GIF formats are supported. Only the first frame of an animated GIF will be used. SVG is not supported."
- `twitter:image:alt`: "Maximum 420 characters."
- The Markup reference (snapshot 2026-02-01, …/cards/overview/markup) gives the OG fallbacks and length limits:
  - "twitter:title Title of content (max 70 characters)", falling back to og:title
  - "twitter:description Description of content (maximum 200 characters)", falling back to og:description
  - twitter:image falls back to og:image
  - "If an og:type, og:title and og:description exist in the markup but twitter:card is absent, then a summary card may be rendered."

**GitHub social preview** (https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview):
> Your image should be a PNG, JPG, or GIF file under 1 MB in size. For the best quality rendering, we recommend a size of at least 640 by 320 pixels (1280 by 640 pixels for best display).

On transparency: "We support PNG images with transparency. … If you aren't sure, we recommend using an image with a solid background."

Inference: one 1280×640 (2:1) PNG under 1 MB satisfies GitHub and X's 2:1. It is slightly off Meta's 1.91:1, which only means a small crop.

---

## 7. schema.org and Google structured data

schema.org is V30.1 (from the page footer).
- **SoftwareSourceCode** (https://schema.org/SoftwareSourceCode): "Computer programming source code. Example: Full (compile ready) solutions, code snippet samples, scripts, templates." Its own properties are:
  - `codeRepository` (URL): "Link to the repository where the un-compiled, human readable code and related code is located (SVN, GitHub, CodePlex)."
  - `codeSampleType`
  - `programmingLanguage` (ComputerLanguage or Text)
  - `runtimePlatform` (RuntimePlatform or Text)
  - `targetProduct` (SoftwareApplication)
- **SoftwareApplication** (https://schema.org/SoftwareApplication): "A software application." Its own properties include:
  - `applicationCategory`
  - `operatingSystem`
  - `softwareVersion`
  - `downloadUrl`
  - `installUrl`
  - `releaseNotes`
  - `softwareRequirements`
  - `featureList`
  - `screenshot`
  - `runtimePlatform`
  - `fileSize`
  - `permissions`
- **ScholarlyArticle** (https://schema.org/ScholarlyArticle): Thing > CreativeWork > Article > ScholarlyArticle, "A scholarly article."

**Google Software app** (https://developers.google.com/search/docs/appearance/structured-data/software-app, updated 2026-09-08).

Required properties:
- `name`
- `offers.price`: "If the app is available without payment, set offers.price to 0"
- "Rating or review: A rating or review of the app. You must include one of the following properties: aggregateRating … review"

Recommended properties:
- `applicationCategory`: "The value must be a supported app type". The list includes `DeveloperApplication` and `SecurityApplication`.
- `operatingSystem`

General structured data guidelines (https://developers.google.com/search/docs/appearance/structured-data/sd-policies, updated 2026-07-10):
- "Specify all required properties listed in the documentation for your specific rich result type. Items that are missing required properties are not eligible for rich results."
- "Don't mark up content that is not visible to readers of the page."
- "Don't mark up irrelevant or misleading content, such as fake reviews".

Intro to structured data (updated 2025-12-10):
- "Google uses structured data that it finds on the web to understand the content of the page".
- "You must include all the required properties for an object to be eligible for appearance in Google Search with enhanced display."
- "it is more important to supply fewer but complete and accurate recommended properties rather than trying to provide every possible recommended property with less complete, badly-formed, or inaccurate data."

**Confirmed: a SoftwareApplication block with no aggregateRating or review is not eligible for the Software App rich result.** Google's docs describe no penalty for that; the only consequence is no enhanced display. Adding ratings that aren't genuine and visible would breach the "fake reviews" and "not visible" rules. Inference: a small, accurate block is fine and still serves the "understand the content" purpose.

**SoftwareSourceCode is not a Google rich-result type.** It is absent from Google's "Feature guides" list, which includes "Software app" but no source-code type.

**Google's Article doc** (updated 2026-09-08): "Article objects must be based on one of the following schema.org types: Article, NewsArticle, BlogPosting" and "There are no required properties". ScholarlyArticle is not named there. Whether Google treats that subtype as Article is not stated.

**Google Scholar does not list schema.org.** It names only Highwire, BE Press, PRISM, and Dublin Core (§2). For Scholar, the `citation_*` meta tags are what matter; JSON-LD is supplementary.

---

## 8. llms.txt

Source: https://llmstxt.org/ (markdown at https://llmstxt.org/index.md). The page is now "The /llms.txt file, v2", Jeremy Howard. The changes page says "v2 (August 2026)".

**Purpose:**
> We propose adding a `/llms.txt` markdown file to websites to provide LLM-friendly content. The file can be placed at the site root, or at any path within it, covering the pages under that path. This file offers brief background information, guidance, and links to detailed markdown files.

> Agents are expected to view or search `llms.txt` to find the information they need, then follow the relevant links. The links in an llms.txt file should therefore point to LLM-friendly content … The file itself stays small enough to fit in context.

> robots.txt lets automated tools know what access to a site is considered acceptable … llms.txt information is instead used on demand, when an agent needs information about a topic while assisting a user.

**Format.** The file "contains the following sections as markdown, in the specific order":
- An optional byte-order mark (BOM)
- An H1 with the name of the project or site. This is the only required section
- A blockquote with a short summary of the project, containing key information necessary for understanding the rest of the file
- Zero or more markdown sections (e.g. paragraphs, lists, etc) of any type except headings …
- Zero or more markdown sections delimited by H2 headers, containing "file lists" of URLs where further detail is available. Each "file list" is a markdown list, containing a required markdown hyperlink `[name](url)`, then optionally a `:` and notes about the file.

Other rules:
- "A file covers the URLs under its path, and where more than one file applies, agents should use the most specific one."
- Markdown copies of pages go at the same URL with `.md` appended (`page.html.md`) or the extension replaced (`page.md`). "URLs without file names should append `index.html.md` or `index.md` instead."
- Discovery (new in v2): "`rel="alternate" type="text/markdown"` points to the markdown version of a page, and `rel="describedby"` points to the llms.txt file that covers it … as HTML `<link>` elements, or as an HTTP `Link:` response header."
- On the Optional section: "The "Optional" section is used, by convention, for secondary information: links an agent can skip when a shorter context is needed". The changes page says v2 dropped its mechanical meaning.
