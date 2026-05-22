"""Sphinx configuration for the slurm-monitor documentation site."""

from importlib.metadata import metadata, version

_meta = metadata("slurm-monitor")

project = "slurm-monitor"
author = _meta.get("Author-email", "Matteo Spanio")
release = version("slurm-monitor")
version = release  # short X.Y; we keep it identical to the full release tag
copyright = "%Y, Matteo Spanio"

extensions = [
    "myst_parser",
    "sphinx_copybutton",
    "sphinx_design",
]

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
    "tasklist",
    "linkify",
]
myst_heading_anchors = 3

source_suffix = {".md": "markdown"}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "scripts"]

html_theme = "furo"
html_title = f"slurm-monitor {release}"
html_static_path = ["_static"]
html_theme_options = {
    "source_repository": "https://github.com/matteospanio/slurm-monitor",
    "source_branch": "master",
    "source_directory": "docs/",
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/matteospanio/slurm-monitor",
            "html": "",
            "class": "fa-brands fa-github",
        },
    ],
}

# sphinx-copybutton: skip the leading prompt characters when copying.
copybutton_prompt_text = r">>> |\.\.\. |\$ |# "
copybutton_prompt_is_regexp = True
