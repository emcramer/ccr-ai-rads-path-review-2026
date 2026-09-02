# Fonts

IBM Plex Sans and IBM Plex Serif, required by `figures/ink_style_guide.md` §2. They are
kept in the project rather than installed system-wide, so the figure renders identically on
any machine without changing a user's font library.

Source: https://github.com/IBM/plex, release 1.1.0. Licence: SIL Open Font License 1.1.

`trends.plotting.style` registers these with matplotlib at import time. If they are missing,
the build fails rather than silently substituting Georgia and Arial — the style guide is
explicit that substitution must not be silent.
