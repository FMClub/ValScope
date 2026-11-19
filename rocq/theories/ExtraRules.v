(** ExtraRules.v: a rule that is NOT in the original ValScope rule table.

    It shows what adding a plug-in costs: one rewrite function, one theorem, one
    line in Registry.v.  Engine.v is not touched and its soundness theorem covers
    the new rule automatically. *)

From Coq Require Import List String.
Import ListNotations.
From ValScope Require Import Bag Logic3 Pattern Syntax Semantics Approx Rule.
Local Open Scope string_scope.

(** A INTERSECT B -> A,  A INTERSECT B -> B  (lemmas in Approx.v) *)
Definition f_intersect_operand (q : query) : list query :=
  match q with QIntersect a b => [a; b] | _ => [] end.

Theorem f_intersect_operand_sound :
  forall q q', In q' (f_intersect_operand q) -> dle q_le Up q q'.
Proof.
  intros q q' H. destruct q; simpl in H; try contradiction.
  destruct H as [<-|[<-|[]]]; [apply q_le_intersect_left|apply q_le_intersect_right].
Qed.

Definition r_intersect_operand : qrule :=
  mk_qrule "INTERSECT->operand" Up f_intersect_operand f_intersect_operand_sound.
