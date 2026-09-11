# SW Architecture Blog — Plan & Roadmap

_Last updated: 2026-09-11_

## 1. Vision

An English-language blog hosted on GitHub Pages, documenting practical experience and self-study knowledge around embedded systems software architecture. Core domains: Security, Flashing, Communication, RTOS, AUTOSAR, Firmware, Debugging, AI, and Engineering Processes.

## 2. Tech Stack Decision

**Chosen: Jekyll**, using GitHub Pages' native build pipeline (no custom GitHub Actions build needed to start).

Why: zero-maintenance builds (GitHub builds Jekyll for you on push), Markdown-first authoring, mature theme ecosystem, easy migration path to a custom Actions-based build later if Jekyll's limits are ever hit.

## 3. Repository Structure (target)

```
repo-root/
├── _config.yml              # site config: title, description, theme, plugins
├── Gemfile                  # Ruby deps for local preview (github-pages gem)
├── index.md                 # home page / post listing
├── about.md                 # about the author / blog
├── _posts/
│   └── YYYY-MM-DD-title.md  # one file per post, Jekyll naming convention
├── _layouts/                # optional custom layouts (can start with theme defaults)
├── assets/
│   └── images/
├── categories.md            # optional: category overview page
└── .github/
    └── workflows/           # optional: only needed if you outgrow native Pages build
```

## 4. Content Taxonomy

Use Jekyll `categories` (one primary) + `tags` (freeform) front matter on every post:

- Security
- Flashing
- Communication
- RTOS
- AUTOSAR
- Firmware
- Debugging
- AI
- Engineering Processes

## 5. Setup Todos

- [ ] Create GitHub repository (`<username>.github.io` for a root-domain site, or any name + Pages enabled for a project site)
- [ ] Add Jekyll scaffold (`_config.yml`, `Gemfile`, `index.md`, `about.md`, `_posts/`)
- [ ] Pick and configure a theme (start with a supported GitHub Pages theme, e.g. `minima`, or a remote theme via `github-pages` gem)
- [ ] Enable GitHub Pages in repo settings (Source: `main` branch, `/ (root)`)
- [ ] Verify local preview works (`bundle exec jekyll serve`)
- [ ] Set up navigation (Home, About, Categories/Tags, maybe an RSS link — Jekyll feed plugin)
- [ ] Add a short author/about page
- [ ] Decide on a custom domain (optional) and configure `CNAME` if used
- [ ] Add a `categories` or `tags` index page so readers can browse by domain

## 6. Content Backlog (seed ideas per domain)

- **Firmware / Flashing:** Garbage collection vs. firmware flashing conflicts *(published)*; Bootloader design patterns for MCUs *(previously drafted, currently removed from `_posts/` — recoverable from git history if it should be restored as a separate post)*; secure vs. unsecure flashing flows; A/B / dual-bank update strategies
- **Security:** Secure Boot chain of trust; threat modeling for embedded products; common pitfalls in key storage on MCUs
- **Communication:** UDS/diagnostics over CAN; comparing CAN, LIN, SPI, UART trade-offs in real projects
- **RTOS:** Task priority design and priority inversion war stories; choosing between FreeRTOS/Zephyr/others
- **AUTOSAR:** Practical intro to AUTOSAR layers for developers coming from bare-metal/RTOS backgrounds
- **Debugging:** JTAG/SWD debugging workflows; debugging intermittent hardware-timing bugs
- **AI:** Where AI coding assistants actually help (and don't) in embedded/firmware work
- **Engineering Processes:** Code review practices for safety-relevant embedded code; branching/release strategies for firmware

## 7. Publishing Workflow Todos

- [ ] Draft posts as Markdown in `_posts/`, front matter with `title`, `date`, `categories`, `tags`
- [ ] Review/proofread pass before merge (English wording, technical accuracy)
- [ ] Push to `main` → GitHub Pages auto-builds and deploys
- [ ] (Later, optional) Add a simple GitHub Actions check that lints Markdown / checks broken links

## 8. Status

| Item | Status |
|---|---|
| Tech stack decided (Jekyll) | Done |
| Repo scaffold | Done, pushed to GitHub |
| First post: "Garbage Collection - friend or enemy" (Flashing) | Drafted, corrected, reviewed, and diagrammed — not yet committed/pushed |
| Earlier "Bootloader Design Patterns" post | Was committed, then removed from `_posts/` during editing — still recoverable from git history; decide whether to restore as its own post |
| GitHub repo created & Pages enabled | Done |
