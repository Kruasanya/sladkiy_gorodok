\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{HSEUniversity_ru}
\LoadClass[12pt]{article}
\def\@@ptsize{14pt}
\RequirePackage{kvoptions}
\RequirePackage[a4paper, total={6.5in, 10in}]{geometry}

\RequirePackage[utf8]{inputenc}  
\RequirePackage{csquotes}
\RequirePackage[T2A]{fontenc}

\RequirePackage[main=russian, english]{babel}
\RequirePackage[style=ieee,backend=biber,bibencoding=utf8,babel=other,language=auto,autolang=langname,maxbibnames=99,sorting=none]{biblatex} 

\RequirePackage{xcolor}

\RequirePackage{graphicx}
\RequirePackage{hyphenat}
\hyphenation{ма-те-ма-ти-ка вос-ста-нав-ли-вать}

\RequirePackage{amsmath}
\RequirePackage{amsfonts}
\RequirePackage{amssymb}
\RequirePackage{physics}
\RequirePackage{cancel}

\RequirePackage{hyperref}

\def\@facultyString{UNKNOWN FACULTY}
\def\@typeString{UNKNOWN WORK TYPE}
\def\@specName{UNKNOWN SPECIALIZATION}
\def\@specCode{00.00.00.UNKNOWN SPECIALIZATION}

\newif\ifIsPractice
\IsPracticefalse
\newif\ifHasReviewer
\HasReviewerfalse
\newif\ifHasCompany
\HasCompanyfalse

\DeclareDefaultOption{%
  \PackageWarningNoLine{\@currname}{%
    Unknown option `\CurrentOption'\MessageBreak
    is passed to class `report'%
  }%
  \expandafter\PassOptionToClass
  \expandafter{\CurrentOption}{report}%
}
\ProcessKeyvalOptions*

\def\@typeString{Курсовая работа}
\def\@facultyString{Факультет компьютерных наук}
\def\@specName{Физика}
\def\@specCode{03.03.02 Физика}
\def\@year{\the\year{}}
\def\@supervisorTitle{}
\def\@supervisorAcademic{}
\def\@supervisorName{I.I.~Ivanov}
\def\@reviewerTitle{}
\def\@reviewerName{I.I.~Ivanov}
\def\@abstract{TODO}
\def\@companyReviewerTitle{company reviewer title}
\def\@companyReviewerName{I.I.~Ivanov}
\def\@group{Unknown-00-0}


\newcommand{\Group}[1]{\def\@group{#1}}
\newcommand{\Year}[1]{\def\@year{#1}}
\newcommand{\supervisor}[3]{
  \def\@supervisorTitle{#1}
  \def\@supervisorAcademic{#2}
  \def\@supervisorName{#3}
}
\def\@titleRu{}
\def\@titleEn{}
\def\@students{}
\def\@program{}
\newcommand{\TitleRu}[1]{\def\@titleRu{#1}}
\newcommand{\TitleEn}[1]{\def\@titleEn{#1}}
\newcommand{\Program}[1]{\def\@program{#1}}
\newcommand{\Faculty}[1]{\def\@facultyString{#1}}
\newcommand{\WorkType}[1]{\def\@typeString{#1}}

\newcommand{\AddStudent}[1]{%
  \g@addto@macro\@students{%
    #1\\[1mm]
    \rule{0.6\textwidth}{0.4pt}\\[1mm]
    {\footnotesize (Ф.И.О., подпись)}\\[6mm]
  }%
}

\newcommand{\@supervisorDescr}{%
  \def\@descr{}%
  \def\@sep{}%
  \ifx\@supervisorTitle\@empty\else
    \edef\@descr{\@descr\@sep\@supervisorTitle}%
    \def\@sep{, }%
  \fi
  \ifx\@supervisorAcademic\@empty\else
    \edef\@descr{\@descr\@sep\@supervisorAcademic}%
    \def\@sep{, }%
  \fi
  \ifx\@supervisorName\@empty\else
    \edef\@descr{\@descr\@sep\@supervisorName}%
  \fi
  \nohyphens{\@descr}%
}
\newcommand{\reviewer}[2]{
  \def\@reviewerTitle{#1}
  \def\@reviewerName{#2}
  \HasReviewertrue
}
\newcommand{\company}[2]{
  \def\@companyReviewerTitle{#1}
  \def\@companyReviewerName{#2}
  \HasCompanytrue
}
\newcommand{\Abstract}[1]{
  \def\@abstract{#1}
}

\newcommand{\UnivercityString}{
  Федеральное государственное автономное образовательное учреждение\\
  высшего образования «Национальный исследовательский университет\\
  «Высшая школа экономики»
}

\newcommand\KRTitle{
  \UnivercityString

  \vspace{8mm}

  \@facultyString\\
  \@program

  \vfill
  \vfill

  \textbf{\MakeUppercase{\@typeString}}

  \vfill
  \vfill

  \begin{flushleft}
    На тему (рус): \nohyphens{\@titleRu}

    \vspace{4mm}
    На тему (англ.): \nohyphens{\@titleEn}
  \end{flushleft}

  \vfill
  \vfill

  \begin{flushleft}
    Студент

    \vspace{6mm}
    \@students

    \vspace{4mm}

    Руководитель КР

    \vspace{6mm}
    \@supervisorDescr\\[1mm]
    \rule{0.6\textwidth}{0.4pt}\\[1mm]
    {\footnotesize (должность, звание, Ф.И.О, подпись)}
  \end{flushleft}

  \vfill
  \vfill
  \vfill

  Москва, \@year{}

  \newpage
}

\renewcommand{\maketitle}{
  {
    \thispagestyle{empty}

    \centering
    \KRTitle
  }
  \newpage
}




