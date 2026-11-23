# Build the Rocq (Coq) development, extract the verified core to OCaml and build the CLI.
# Coq 8.x ships coq_makefile; Rocq 9 replaced it by `rocq makefile`.
COQMAKEFILE ?= $(shell command -v coq_makefile 2>/dev/null || echo rocq makefile)

all: Makefile.coq
	mkdir -p extracted
	$(MAKE) -f Makefile.coq

Makefile.coq: _CoqProject
	$(COQMAKEFILE) -f _CoqProject -o Makefile.coq

# The command-line mutator: extracted core + glue (cli/main.ml).
# The rule types are made abstract in the interface main.ml is compiled against: the
# extracted records carry no proof, so OCaml code must not be able to build a rule.
# Only the rules exported by Registry.v (with their theorems) can be used.
cli: all
	cp extracted/valscope_core.ml extracted/valscope_core.mli cli/
	perl -0pi -e 's/^type (prule|qrule|vrule|prule_in|qrule_in|vrule_in) =\s*\{.*?\}/type $$1  (* abstract: only the proved rules *)/gms' cli/valscope_core.mli
	@if grep -Eq '^type (prule|qrule|vrule|prule_in|qrule_in|vrule_in) =' cli/valscope_core.mli; then echo "rule types not abstract"; exit 1; fi
	@for t in prule qrule vrule prule_in qrule_in; do \
	  grep -q "^type $$t  (\* abstract" cli/valscope_core.mli || { echo "rule type $$t missing from the interface"; exit 1; }; done
	cd cli && ocamlfind ocamlopt -w -a valscope_core.mli valscope_core.ml main.ml -o valscope_mutate

# A rule forged in OCaml must not compile against the interface.
check-abstract: cli
	@cd cli && for f in forge_rule forge_rule_in forge_vrule_in; do \
	  if ocamlfind ocamlopt -w -a -c $$f.ml 2>/dev/null; then \
	    echo "FAIL  $$f.ml could build a rule record"; rm -f $$f.cm* $$f.o; exit 1; fi; done; \
	echo "ok    OCaml code cannot build a rule (rule types are abstract)"

# End-to-end test: SQL text -> mutants -> SQL text (needs python3 with sqlglot).
test: cli check-abstract lint
	python3 bridge/test_bridge.py

# static check of the glue code (undefined names, unused imports); skipped without pyflakes
lint:
	@if python3 -m pyflakes --version >/dev/null 2>&1; then python3 -m pyflakes bridge/*.py scripts/*.py; \
	 else echo "pyflakes not installed: lint skipped"; fi

clean:
	@if [ -f Makefile.coq ]; then $(MAKE) -f Makefile.coq cleanall; fi
	rm -f Makefile.coq Makefile.coq.conf extracted/*.cm* extracted/*.o
	rm -f cli/valscope_core.ml cli/valscope_core.mli cli/*.cm* cli/*.o cli/valscope_mutate

.PHONY: all cli test clean check-abstract lint
