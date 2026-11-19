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

(** ---------------- INTERSECT / EXCEPT with and without ALL ----------------

    The analogue of rule 2 (UNION <-> UNION ALL) for the other two set operations:
    INTERSECT keeps each common class once, INTERSECT ALL [min(a, b)] times; EXCEPT keeps
    a class once when it is missing on the right, EXCEPT ALL [a - b] times.  So the
    DISTINCT forms are below the ALL forms (Bag.inter_le_inter_all, exc_le_exc_all). *)

Definition f_intersect_all (q : query) : list query :=
  match q with QIntersect a b => [QIntersectAll a b] | _ => [] end.

Theorem f_intersect_all_sound : forall q q', In q' (f_intersect_all q) -> dle q_le Up q q'.
Proof.
  intros q q' H. destruct q; simpl in H; try contradiction.
  destruct H as [<-|[]]. apply q_le_intersect_all_base.
Qed.

Definition r_intersect_all : qrule :=
  mk_qrule "INTERSECT->INTERSECT-ALL" Up f_intersect_all f_intersect_all_sound.

Definition f_intersect_distinct (q : query) : list query :=
  match q with QIntersectAll a b => [QIntersect a b] | _ => [] end.

Theorem f_intersect_distinct_sound : forall q q', In q' (f_intersect_distinct q) -> dle q_le Down q q'.
Proof.
  intros q q' H. destruct q; simpl in H; try contradiction.
  destruct H as [<-|[]]. apply q_le_intersect_all_base.
Qed.

Definition r_intersect_distinct : qrule :=
  mk_qrule "INTERSECT-ALL->INTERSECT" Down f_intersect_distinct f_intersect_distinct_sound.

Definition f_except_all (q : query) : list query :=
  match q with QExcept a b => [QExceptAll a b] | _ => [] end.

Theorem f_except_all_sound : forall q q', In q' (f_except_all q) -> dle q_le Up q q'.
Proof.
  intros q q' H. destruct q; simpl in H; try contradiction.
  destruct H as [<-|[]]. apply q_le_except_all_base.
Qed.

Definition r_except_all : qrule := mk_qrule "EXCEPT->EXCEPT-ALL" Up f_except_all f_except_all_sound.

Definition f_except_distinct (q : query) : list query :=
  match q with QExceptAll a b => [QExcept a b] | _ => [] end.

Theorem f_except_distinct_sound : forall q q', In q' (f_except_distinct q) -> dle q_le Down q q'.
Proof.
  intros q q' H. destruct q; simpl in H; try contradiction.
  destruct H as [<-|[]]. apply q_le_except_all_base.
Qed.

Definition r_except_distinct : qrule :=
  mk_qrule "EXCEPT-ALL->EXCEPT" Down f_except_distinct f_except_distinct_sound.
