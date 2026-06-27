\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{coursework}[2026/06/27 Coursework class]

\LoadClass[14pt,a4paper]{extreport}

\RequirePackage[T2A]{fontenc}
\RequirePackage[utf8]{inputenc}
\RequirePackage[english,russian]{babel}
\RequirePackage{geometry}
\RequirePackage{setspace}
\RequirePackage{indentfirst}
\RequirePackage{csquotes}
\RequirePackage{xcolor}
\RequirePackage{graphicx}
\RequirePackage{float}
\RequirePackage{booktabs}
\RequirePackage{longtable}
\RequirePackage{array}
\RequirePackage{enumitem}
\RequirePackage{hyperref}

\geometry{
  left=30mm,
  right=15mm,
  top=20mm,
  bottom=20mm
}

\onehalfspacing
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

\newcommand{\courseworktitlepage}[6]{
  \begin{titlepage}
    \begin{center}
      #1\\
      #2\\[3cm]

      {\bfseries КУРСОВАЯ РАБОТА}\\[0.5cm]
      по теме:\\[0.3cm]
      {\bfseries #3}\\[3cm]
    \end{center}

    \begin{flushright}
      Выполнил: #4\\
      Руководитель: #5
    \end{flushright}

    \vfill

    \begin{center}
      #6
    \end{center}
  \end{titlepage}
}
