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


def merge_files(include_dirs, include_files, py_output, js_output, yaml_output):
    with open(py_output, "w", encoding="utf-8") as py_out, \
         open(js_output, "w", encoding="utf-8") as js_out, \
         open(yaml_output, "w", encoding="utf-8") as yaml_out:

        # Сначала отдельные файлы (.env и т.п.)
        for filepath in include_files:
            if os.path.exists(filepath):
                ext = os.path.splitext(filepath)[1]
                target = None
                if ext == ".py":
                    target = py_out
                elif ext in (".js", ".jsx", ".ts", ".tsx"):
                    target = js_out
                elif ext in (".yml", ".yaml") or filepath.endswith(".env"):
                    target = yaml_out

                if target:
                    target.write(f"\n\n# --- {filepath} ---\n\n")
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as infile:
                        target.write(infile.read())

        # Потом папки рекурсивно
        for root_folder in include_dirs:
            for foldername, dirnames, filenames in os.walk(root_folder):
                # фильтруем папки
                dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]

                for filename in filenames:
                    ext = os.path.splitext(filename)[1]

                    # Пропускаем бинарники
                    if ext in EXCLUDE_EXTENSIONS:
                        continue

                    filepath = os.path.join(foldername, filename)

                    # Python
                    if ext == ".py":
                        py_out.write(f"\n\n# --- {filepath} ---\n\n")
                        with open(filepath, "r", encoding="utf-8", errors="ignore") as infile:
                            py_out.write(infile.read())

                    # JS / TS
                    elif ext in (".js", ".jsx", ".ts", ".tsx"):
                        js_out.write(f"\n\n// --- {filepath} ---\n\n")
                        with open(filepath, "r", encoding="utf-8", errors="ignore") as infile:
                            js_out.write(infile.read())

                    # YAML
                    elif ext in (".yml", ".yaml"):
                        yaml_out.write(f"\n\n# --- {filepath} ---\n\n")
                        with open(filepath, "r", encoding="utf-8", errors="ignore") as infile:
                            yaml_out.write(infile.read())


if __name__ == "__main__":
    merge_files(INCLUDE_DIRS, INCLUDE_FILES, PYTHON_OUTPUT, JS_OUTPUT, YAML_OUTPUT)
    print(f"✅ Python собран в {PYTHON_OUTPUT}")
    print(f"✅ JS/TS собран в {JS_OUTPUT}")
    print(f"✅ YAML/.env собраны в {YAML_OUTPUT}")
