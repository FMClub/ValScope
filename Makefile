# Build the Rocq (Coq) development, extract the verified core to OCaml and build the CLI.
all: Makefile.coq
	mkdir -p extracted
	$(MAKE) -f Makefile.coq

Makefile.coq: _CoqProject
	coq_makefile -f _CoqProject -o Makefile.coq

# The command-line mutator: extracted core + glue (cli/main.ml).
# The rule types are made abstract in the interface main.ml is compiled against: the
# extracted records carry no proof, so OCaml code must not be able to build a rule.
# Only the rules exported by Registry.v (with their theorems) can be used.
cli: all
	cp extracted/valscope_core.ml extracted/valscope_core.mli cli/
	sed -i -E 's/^type (prule|qrule|vrule) = \{.*\}$$/type \1  (* abstract: only the proved rules of Registry.v *)/' cli/valscope_core.mli
	@grep -q '^type prule  (\* abstract' cli/valscope_core.mli || (echo "rule types not abstract"; exit 1)
	cd cli && ocamlfind ocamlopt -w -a valscope_core.mli valscope_core.ml main.ml -o valscope_mutate

# A rule forged in OCaml must not compile against the interface.
check-abstract: cli
	@cd cli && if ocamlfind ocamlopt -w -a -c forge_rule.ml 2>/dev/null; then \
	  echo "FAIL  an OCaml file could build a rule record"; rm -f forge_rule.cm* forge_rule.o; exit 1; \
	else echo "ok    OCaml code cannot build a rule (rule types are abstract)"; fi

# End-to-end test: SQL text -> mutants -> SQL text (needs python3 with sqlglot).
test: cli check-abstract
	python3 bridge/test_bridge.py

clean:
	@if [ -f Makefile.coq ]; then $(MAKE) -f Makefile.coq cleanall; fi
	rm -f Makefile.coq Makefile.coq.conf extracted/*.cm* extracted/*.o
	rm -f cli/valscope_core.ml cli/valscope_core.mli cli/*.cm* cli/*.o cli/valscope_mutate

.PHONY: all cli test clean check-abstract
