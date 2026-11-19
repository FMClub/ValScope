(** Registry.v: the rules that are plugged in.

    To add a rule: prove it (see StdRules.v / ExtraRules.v) and add it to one of
    the two lists below.  Nothing else changes. *)

From Coq Require Import List String.
Import ListNotations.
From ValScope Require Import Bag Logic3 Syntax Semantics Approx Rule Engine StdRules ExtraRules.

Definition pred_rules : list prule :=
  [ r_true; r_false; r_and_drop; r_or_drop; r_cmp_weaken; r_cmp_strengthen ].

Definition query_rules : list qrule :=
  [ r_distinct_drop; r_distinct_add; r_union_all; r_union_distinct;
    r_except_left; r_intersect_union; r_union_intersect;
    r_inner_left; r_left_inner;
    r_intersect_operand ].

(** The mutator of the framework: the engine instantiated with the registry. *)
Definition mutate : dir -> query -> list (string * query) :=
  mut_q pred_rules query_rules.

(** Its soundness is an instance of the generic theorem. *)
Theorem mutate_sound : forall d q name q',
  In (name, q') (mutate d q) -> dle q_le d q q'.
Proof. intros d q name q'. apply mut_q_sound. Qed.

Print Assumptions mutate_sound.
