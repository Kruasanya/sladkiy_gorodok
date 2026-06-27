\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{coursework}[2026/06/27 Coursework class]

\LoadClass[12pt,a4paper]{extreport}

\RequirePackage[T2A]{fontenc}
\RequirePackage[utf8]{inputenc}
\RequirePackage[english,russian]{babel}
\RequirePackage{geometry}
\RequirePackage{setspace}
\RequirePackage{indentfirst}
\RequirePackage{csquotes}
\RequirePackage{xcolor}
\RequirePackage{graphicx}
\RequirePackage{amsmath}
\RequirePackage{amssymb}
\RequirePackage{pgfplots}
\pgfplotsset{compat=1.18}
\RequirePackage{tikz}
\usetikzlibrary{arrows.meta,shapes.geometric,positioning,backgrounds,patterns,fit}
\RequirePackage{float}
\RequirePackage{booktabs}
\RequirePackage{longtable}
\RequirePackage{array}
\RequirePackage{enumitem}
\RequirePackage{hyperref}
\RequirePackage{pgffor}

\geometry{
  margin=2cm
}

\singlespacing
\setlength{\parindent}{1.25cm}
\setlength{\parskip}{0pt}

\hypersetup{
  colorlinks=true,
  linkcolor=black,
  citecolor=black,
  urlcolor=blue,
  pdfborder={0 0 0}
}

\setlist[itemize]{leftmargin=1.25cm}
\setlist[enumerate]{leftmargin=1.25cm}

\renewcommand{\contentsname}{Содержание}
\renewcommand{\bibname}{Список использованных источников}

% Строка "ФИО ........... подпись" с короткой линией для подписи справа.
\newcommand{\signatureline}[1]{%
  \noindent\makebox[0.62\linewidth][l]{#1}%
  \makebox[0.16\linewidth]{\hrulefill}\hspace{1em}%
  {\small подпись}\\[0.6cm]%
}

% #1 - название на русском
% #2 - название на английском
% #3 - блок студентов: одна или несколько строк \signatureline{Ф.И.О.}
% #4 - блок руководителя: \signatureline{должность, звание, Ф.И.О.}
% #5 - год
\newcommand{\courseworktitlepage}[5]{
  \begin{titlepage}
    \begin{center}
      Федеральное государственное автономное образовательное учреждение\\
      высшего образования «Национальный исследовательский университет\\
      «Высшая школа экономики»\\[1cm]

      Факультет компьютерных наук\\
      Магистерская программа «Финансовые технологии и анализ данных»\\[2.5cm]

      {\Large\bfseries КУРСОВАЯ РАБОТА}\\[2cm]
    \end{center}

    \noindent\textbf{На тему (рус.):} #1\\[0.6cm]
    \noindent\textbf{На тему (англ.):} #2

    \vspace{2.5cm}

    \noindent\textbf{Студент}\\[0.6cm]
    #3

    \vspace{1.5cm}

    \noindent\textbf{Руководитель КР}\\[0.6cm]
    #4

    \vfill

    \begin{center}
      Москва, #5
    \end{center}
  \end{titlepage}
}
