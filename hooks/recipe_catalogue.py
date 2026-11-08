"""Build the recipe catalogue and tag navigation from published recipe files."""
import hashlib
import json
import posixpath
import re
import unicodedata
from collections import defaultdict
from urllib.parse import quote

from mkdocs.structure.files import File
from mkdocs.utils.meta import get_data


def sort_key(text):
    return unicodedata.normalize("NFKD", text).casefold()


def initial(title):
    plain = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    first = plain[:1].upper()
    return first if first in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" and first else "#"


def tag_path(tag):
    slug = re.sub(r"[^a-z0-9]+", "-", sort_key(tag).encode("ascii", "ignore").decode()).strip("-")
    digest = hashlib.sha256(tag.encode()).hexdigest()[:8]
    return f"tags/{slug or 'tag'}-{digest}.md"


def recipe_link(recipe, page_path):
    label = recipe["title"].replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
    target = posixpath.relpath(recipe["path"], posixpath.dirname(page_path) or ".")
    return f"- [{label}](<{quote(target, safe='/')}>)"


def catalogue(recipes, page_path, title):
    grouped = defaultdict(list)
    for recipe in recipes:
        grouped[initial(recipe["title"])].append(recipe)
    lines = [f"# {title}", "", f"{len(recipes)} recipe{'s' if len(recipes) != 1 else ''}", ""]
    if not recipes:
        return "\n".join(lines + ["No recipes yet.", ""])
    letters = sorted(grouped, key=lambda letter: (letter == "#", letter))
    jumps = " ".join(
        f'<a href="#letter-{letter.lower()}">{letter}</a>' if letter in grouped
        else f'<span aria-disabled="true">{letter}</span>'
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    )
    if "#" in grouped:
        jumps += ' <a href="#letter-other">#</a>'
    lines += [f'<nav class="recipe-alphabet" aria-label="Recipe alphabet">{jumps}</nav>', ""]
    for letter in letters:
        anchor = letter.lower() if letter != "#" else "other"
        lines += [f"## {letter} {{ #letter-{anchor} }}", ""]
        lines.extend(recipe_link(recipe, page_path) for recipe in grouped[letter])
        lines.append("")
    return "\n".join(lines)


def on_files(files, config):
    # Give changed styles a new URL so browsers never keep an old colour palette.
    stylesheet = files.get_file_from_path("stylesheets/dark-kitchen.css")
    if stylesheet is not None:
        css = stylesheet.content_string
        digest = hashlib.sha256(css.encode()).hexdigest()[:12]
        css_path = f"stylesheets/dark-kitchen-{digest}.css"
        files.append(File.generated(config, css_path, content=css))
        config["extra_css"] = [css_path]
    recipes = []
    for file in files.documentation_pages():
        if not file.src_uri.startswith("recipes/") or posixpath.basename(file.src_uri) == "index.md":
            continue
        if not file.inclusion.is_included():
            continue
        body, metadata = get_data(file.content_string)
        heading = re.search(r"^#\s+(.+?)\s*#*\s*$", body, re.MULTILINE)
        title = str(metadata.get("title") or (heading.group(1) if heading else posixpath.basename(file.src_uri).rsplit(".", 1)[0].replace("-", " "))).strip()
        tags = metadata.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        if not isinstance(tags, list):
            raise ValueError(f"{file.src_uri}: tags must be a list of tag names")
        recipes.append({"title": title, "path": file.src_uri, "tags": sorted({str(tag).strip() for tag in tags if str(tag).strip()}, key=sort_key)})
    recipes.sort(key=lambda recipe: (sort_key(recipe["title"]), recipe["path"]))

    files.append(File.generated(config, "all-recipes.md", content=catalogue(recipes, "all-recipes.md", "All recipes")))
    tagged = defaultdict(list)
    for recipe in recipes:
        for tag in recipe["tags"]:
            tagged[tag].append(recipe)
    tag_nav = [{"All tags": "tags.md"}]
    for tag in sorted(tagged, key=sort_key):
        path = tag_path(tag)
        content = "---\ntitle: " + json.dumps(tag) + "\n---\n\n# Recipes by tag\n\n<!-- material/tags " + json.dumps({"include": [tag]}) + " -->\n"
        files.append(File.generated(config, path, content=content))
        tag_nav.append({tag: path})
    config["nav"] = [{"Home": "index.md"}, {"All recipes": "all-recipes.md"}, {"Tags": tag_nav}]
    return files
