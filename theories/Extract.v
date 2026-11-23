(** Extract.v: extraction of the verified framework to OCaml.

    [extracted/valscope_core.ml] contains the generic engine ([mut_q], [mut_p]),
    the rule records and the registry ([mutate]).  Proofs are erased: a rule
    becomes a record (name, direction, rewrite function).  Inside Rocq a rule
    cannot be built without its proof; OCaml code that builds rule records by hand
    bypasses that guarantee, so plug-ins should be written and registered in Rocq.

    The class of worlds of a [prule_in W] is erased too: OCaml sees one type for the
    rules of every class.  Only closed mutators are extracted for them (here
    [mutate_add_commutes], the example of Within.v), never [mut_q_in], [mutate_within]
    or a rule on its own: mixing the rules of two classes would be sound in the worlds
    of both only, which no theorem states. *)

From Coq Require Import Extraction ExtrOcamlBasic ExtrOcamlNatInt ExtrOcamlZInt
  ExtrOcamlNativeString.
From ValScope Require Import Logic3 Syntax Rule Engine Value VEngine VHaving VUnion VSet VLineage Registry Within.

Extraction Language OCaml.
Extraction "extracted/valscope_core.ml" mutate mut_q mut_p pred_rules query_rules flip
  vmutate vmut value_rules hmutate hmut tmutate thmutate shmutate wmutate
  pred_rule_names query_rule_names value_rule_names class_rule_names
  mutate_add_commutes.
