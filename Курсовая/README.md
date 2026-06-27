# Курсовая работа в LaTeX

## Сборка

После установки BasicTeX и пакетов из инструкции:

```bash
cd "/Users/pavelesipenok/Documents/New project/sladkiy_gorodok/Курсовая"
latexmk -pdf -interaction=nonstopmode main.tex
open main.pdf
```

Если терминал не видит `pdflatex`, выполнить:

```bash
eval "$(/usr/libexec/path_helper)"
```

## Структура

- `main.tex` - основной файл.
- `coursework.cls` - локальный класс оформления.
- `references.bib` - библиография.
- `parts/` - главы и приложения.

## Важно

Автоматическая установка BasicTeX из Codex не завершилась, потому что установщик запросил пароль администратора через `sudo`. Нужно выполнить `brew install --cask basictex` вручную в обычном терминале macOS.

После установки в новом окне терминала нужно проверить:

```bash
which pdflatex
which latexmk
which biber
```

Если `latexmk` или `biber` не найдены, поставить пакеты:

```bash
sudo tlmgr update --self
sudo tlmgr install latexmk biber biblatex biblatex-gost csquotes hyphenat kvoptions babel-russian babel-english xcolor wrapfig float geometry
sudo tlmgr install collection-latexextra collection-langcyrillic collection-bibtexextra collection-fontsrecommended
```
