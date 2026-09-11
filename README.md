# SW Architecture Blog — Setup

This is a Jekyll scaffold for a GitHub Pages blog on embedded systems software architecture.

## First-time setup

1. Create a GitHub repository.
   - For a root-domain site: name it `<your-github-username>.github.io`, keep `baseurl: ""` and `url: "https://<your-github-username>.github.io"` in `_config.yml`.
   - For a project site (e.g. `sw-architecture-blog`): set `baseurl: "/sw-architecture-blog"` and `url: "https://<your-github-username>.github.io"` in `_config.yml`.
2. Push all files in this folder to the repository's `main` branch.
3. In the repo on GitHub: **Settings → Pages → Source** → select branch `main`, folder `/ (root)`.
4. Wait a minute or two — the site will be published at the URL shown on that Settings page.

## Local preview (optional but recommended before pushing)

```bash
bundle install
bundle exec jekyll serve
# open http://localhost:4000
```

## Writing a new post

Add a file to `_posts/` named `YYYY-MM-DD-short-title.md` — this exact format is required by Jekyll for a file to be picked up as a post at all, and the date also drives the URL and sort order. Front matter looks like:

```yaml
---
layout: post
title: "Your Title Here"
categories: [Firmware]
tags: [bootloader, flashing]
---
```

See `_posts/2026-08-29-garbage-collection-friend-or-enemy.md` for a full example.

See `PLAN.md` for the full roadmap and content backlog.
