.PHONY: all pdf clean

all: pdf

pdf:
	@if command -v latexmk >/dev/null 2>&1; then \
		latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex; \
	else \
		pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null && \
		pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null; \
	fi

clean:
	@if command -v latexmk >/dev/null 2>&1; then latexmk -C; fi
	@rm -f main.aux main.bbl main.blg main.fdb_latexmk main.fls main.log main.out main.toc
