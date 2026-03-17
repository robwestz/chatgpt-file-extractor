"""
Parser for ChatGPT output — extracts file paths and content from pasted text.

Handles common ChatGPT output formats:
  1. ```filename.py\n...code...\n```
  2. **path/to/file.py**\n```python\n...code...\n```
  3. ## path/to/file.py\n```\n...code...\n```
  4. 📄 path/to/file.py\n```\n...code...\n```
  5. File: path/to/file.py\n```\n...code...\n```
  6. ### `path/to/file.py`\n```\n...code...\n```
  7. Emoji header lines like "🧠 SYSTEM_PROMPT.md"
  8. Emoji + folder/file: "⚙️ source_material/seeds.txt"
"""

import re
from dataclasses import dataclass


@dataclass
class ExtractedFile:
    path: str
    content: str


# File extensions we recognize
FILE_EXTENSIONS = (
    '.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.scss',
    '.json', '.yaml', '.yml', '.toml', '.xml', '.csv',
    '.md', '.txt', '.rst', '.log',
    '.sh', '.bash', '.bat', '.ps1', '.cmd',
    '.sql', '.graphql', '.gql',
    '.env', '.gitignore', '.dockerignore',
    '.cfg', '.ini', '.conf',
    '.r', '.R', '.jl', '.go', '.rs', '.java', '.kt', '.swift',
    '.c', '.cpp', '.h', '.hpp', '.cs',
    '.rb', '.php', '.pl', '.lua',
    '.dockerfile', '.tf', '.hcl',
    '.ipynb', '.lock',
)

# Matches tree-drawing characters
TREE_CHARS_RE = re.compile(r'[│├└─┬┤┼]')

# Regex: code fence
CODE_FENCE_RE = re.compile(r'^```(\w*)\s*$')

# Regex: content header — emoji prefix + optional bold/backtick/hashes + filepath
# Must NOT contain tree-drawing characters
CONTENT_HEADER_RE = re.compile(
    r'^[\s]*'
    r'(?:[#]{1,4}\s+)?'                                                    # optional ### headers
    r'(?:[*]{2})?'                                                           # optional bold **
    r'(?:[`])?'                                                              # optional backtick
    r'(?:[\U0001F300-\U0001FAD6\u2600-\u27BF\u2702-\u27B0\uFE0F]\s*)*'     # optional emoji(s)
    r'(?:File:\s*|Fil:\s*)?'                                                 # optional "File:" prefix
    r'([\w./_-]+\.[a-zA-Z0-9]{1,10})'                                       # the actual file path
    r'(?:[`])?'                                                              # optional closing backtick
    r'(?:[*]{2})?'                                                           # optional closing bold
    r'\s*$',
    re.UNICODE
)


def is_tree_line(line: str) -> bool:
    """Check if a line is part of a tree/folder diagram."""
    return bool(TREE_CHARS_RE.search(line))


def extract_content_header(line: str) -> str | None:
    """
    Extract a file path from a content header line.
    Returns None for tree-diagram lines.
    """
    if is_tree_line(line):
        return None

    m = CONTENT_HEADER_RE.match(line)
    if m:
        return m.group(1)
    return None


def looks_like_filepath(s: str) -> bool:
    """Check if a string looks like a file path."""
    s = s.strip().strip('*`#').strip()
    s = re.sub(r'^[\U0001F300-\U0001FAD6\u2600-\u27BF\u2702-\u27B0\uFE0F]\s*', '', s, flags=re.UNICODE)
    s = re.sub(r'^(?:File:|Fil:)\s*', '', s, flags=re.IGNORECASE)
    s = s.strip()
    return any(s.endswith(ext) for ext in FILE_EXTENSIONS)


def parse_tree(text: str) -> dict[str, str]:
    """
    Parse a file tree diagram and build filename -> full path mapping.
    Handles standard tree output like:
        project-root/
        ├── prompts/
        │   └── lexe_builder/
        │       ├── SYSTEM_PROMPT.md
    """
    paths = {}
    lines = text.split('\n')

    # Find tree block (lines containing tree chars)
    tree_lines = []
    in_tree = False
    for line in lines:
        if is_tree_line(line):
            in_tree = True
            tree_lines.append(line)
        elif in_tree:
            # Check if continuation (indented line or folder line)
            if line.strip().endswith('/') and line.strip():
                tree_lines.append(line)
            else:
                in_tree = False

    if not tree_lines:
        return paths

    # Parse tree: use position of the name to determine depth
    folder_stack: list[tuple[int, str]] = []

    for line in tree_lines:
        # Remove tree drawing chars to get the name
        cleaned = re.sub(r'^[\s│├└─┬┤┼\s]*(?:──\s+)?', '', line)
        name = cleaned.strip()
        if not name:
            continue

        # Determine indentation: position where the name starts in original line
        name_start = line.find(name[0]) if name else 0

        is_folder = name.endswith('/')
        name = name.rstrip('/')

        # Pop folders deeper or at same level
        while folder_stack and folder_stack[-1][0] >= name_start:
            folder_stack.pop()

        if is_folder:
            folder_stack.append((name_start, name))
        else:
            folder_parts = [f[1] for f in folder_stack]
            full_path = '/'.join(folder_parts + [name])
            paths[name] = full_path

    return paths


def parse(text: str) -> list[ExtractedFile]:
    """
    Parse pasted ChatGPT output and extract files with correct paths.

    Two-phase approach:
    1. Parse tree diagram (if present) to build filename->path mapping
    2. Find content headers (emoji + filename) and collect their content
    """
    lines = text.split('\n')
    files: list[ExtractedFile] = []
    n = len(lines)

    # Phase 1: Build path mapping from tree diagram
    tree_paths = parse_tree(text)

    # Phase 2: Find content blocks
    i = 0
    while i < n:
        line = lines[i]

        # Skip tree diagram lines
        if is_tree_line(line):
            i += 1
            continue

        # Check for content header
        path = extract_content_header(line)
        if path:
            # Resolve full path using tree mapping
            full_path = _resolve_with_tree(path, tree_paths)

            # Look ahead: skip empty lines, then check for code fence
            j = i + 1
            while j < n and lines[j].strip() == '':
                j += 1

            if j < n and CODE_FENCE_RE.match(lines[j]):
                # Code fence follows: collect until closing fence
                j += 1  # skip opening ```
                content_lines = []
                while j < n and not CODE_FENCE_RE.match(lines[j]):
                    content_lines.append(lines[j])
                    j += 1
                if j < n:
                    j += 1  # skip closing ```

                files.append(ExtractedFile(path=full_path, content='\n'.join(content_lines)))
                i = j
                continue

            # No code fence: collect plain content until next header or section boundary
            j = i + 1
            content_lines = []
            while j < n:
                # Stop at next content header
                if extract_content_header(lines[j]):
                    break
                # Stop at tree lines
                if is_tree_line(lines[j]):
                    break
                content_lines.append(lines[j])
                j += 1

            # Trim leading/trailing blank lines
            while content_lines and content_lines[0].strip() == '':
                content_lines.pop(0)
            while content_lines and content_lines[-1].strip() == '':
                content_lines.pop()

            if content_lines:
                files.append(ExtractedFile(path=full_path, content='\n'.join(content_lines)))

            i = j
            continue

        # Check for standalone code fence (```python etc.) that might have a path hint
        fence_match = CODE_FENCE_RE.match(line)
        if fence_match:
            # Check line before the fence for a path
            k = i - 1
            while k >= 0 and lines[k].strip() == '':
                k -= 1

            fence_lang = line.strip()[3:].strip()
            prev_path = None

            if k >= 0:
                prev_path = extract_content_header(lines[k])

            if looks_like_filepath(fence_lang):
                prev_path = fence_lang

            # Collect the code block
            j = i + 1
            content_lines = []
            while j < n and not CODE_FENCE_RE.match(lines[j]):
                content_lines.append(lines[j])
                j += 1
            if j < n:
                j += 1

            if prev_path and not any(f.path == prev_path or f.path.endswith('/' + prev_path) for f in files):
                full_path = _resolve_with_tree(prev_path, tree_paths)
                files.append(ExtractedFile(path=full_path, content='\n'.join(content_lines)))

            i = j
            continue

        i += 1

    # Deduplicate: keep last occurrence of each path
    seen = {}
    for f in files:
        seen[f.path] = f
    return list(seen.values())


def _resolve_with_tree(path: str, tree_paths: dict[str, str]) -> str:
    """Resolve a filename/path using the tree mapping."""
    # Extract just the filename for lookup
    filename = path.split('/')[-1] if '/' in path else path

    # Always try tree mapping first (it has the most complete paths)
    if filename in tree_paths:
        return tree_paths[filename]

    # Fall back to path as given
    return path
