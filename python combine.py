import os

# Папки для сбора
INCLUDE_DIRS = [
    "backend/app",
    "frontend/src",
]

# Доп. одиночные файлы
INCLUDE_FILES = [".env"]

# Файлы-результаты
PYTHON_OUTPUT = "combined_python.py"
JS_OUTPUT = "combined_js.js"
YAML_OUTPUT = "configs.txt"

# Игнорируемые папки
EXCLUDE_DIRS = {"__pycache__", "node_modules", "migrations"}

# Игнорируемые расширения (бинарники/медиа)
EXCLUDE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico",
    ".pdf", ".exe", ".dll", ".zip", ".tar", ".gz",
    ".db", ".sqlite", ".mp3", ".mp4", ".avi", ".mov"
}

# Группы расширений
PY_EXT = {".py"}
JS_EXT = {".js", ".jsx", ".ts", ".tsx"}
YAML_EXT = {".yml", ".yaml"}
ENV_FILES = {".env"}  # именно по имени, не по расширению


def write_with_header(out, filepath, header_style):
    """Записывает файл с заголовком"""
    if header_style == "js":
        header = f"\n\n// --- {filepath} ---\n\n"
    else:
        header = f"\n\n# --- {filepath} ---\n\n"

    out.write(header)
    with open(filepath, "r", encoding="utf-8", errors="ignore") as infile:
        out.write(infile.read())


def merge_files(include_dirs, include_files, py_output, js_output, yaml_output):
    with open(py_output, "w", encoding="utf-8") as py_out, \
         open(js_output, "w", encoding="utf-8") as js_out, \
         open(yaml_output, "w", encoding="utf-8") as yaml_out:

        # Сначала отдельные файлы
        for filepath in include_files:
            if os.path.exists(filepath):
                name = os.path.basename(filepath)
                ext = os.path.splitext(filepath)[1]

                if ext in PY_EXT:
                    write_with_header(py_out, filepath, "py")
                elif ext in JS_EXT:
                    write_with_header(js_out, filepath, "js")
                elif ext in YAML_EXT or name in ENV_FILES:
                    write_with_header(yaml_out, filepath, "yaml")

        # Потом папки рекурсивно
        for root_folder in include_dirs:
            for foldername, dirnames, filenames in os.walk(root_folder):
                # фильтруем папки
                dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]

                for filename in filenames:
                    ext = os.path.splitext(filename)[1]
                    filepath = os.path.join(foldername, filename)

                    # Пропускаем бинарники
                    if ext in EXCLUDE_EXTENSIONS:
                        continue

                    if ext in PY_EXT:
                        write_with_header(py_out, filepath, "py")
                    elif ext in JS_EXT:
                        write_with_header(js_out, filepath, "js")
                    elif ext in YAML_EXT:
                        write_with_header(yaml_out, filepath, "yaml")


if __name__ == "__main__":
    merge_files(INCLUDE_DIRS, INCLUDE_FILES, PYTHON_OUTPUT, JS_OUTPUT, YAML_OUTPUT)
    print(f"✅ Python собран в {PYTHON_OUTPUT}")
    print(f"✅ JS/TS/JSX собран в {JS_OUTPUT}")
    print(f"✅ YAML/.env собраны в {YAML_OUTPUT}")
