# Build the Rocq (Coq) development and extract the verified core to OCaml.
all: Makefile.coq
	$(MAKE) -f Makefile.coq

Makefile.coq: _CoqProject
	coq_makefile -f _CoqProject -o Makefile.coq

# Compile the extracted OCaml and run the smoke test.
test: all
	cd extracted && ocamlfind ocamlopt -package str valscope_core.mli valscope_core.ml smoke_test.ml -o smoke_test && ./smoke_test

clean:
	@if [ -f Makefile.coq ]; then $(MAKE) -f Makefile.coq cleanall; fi
	rm -f Makefile.coq Makefile.coq.conf extracted/*.cm* extracted/*.o extracted/smoke_test

.PHONY: all test clean
