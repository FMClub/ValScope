(** Counter.v: why some positions are never mutated.

    The mutators only enter positions that are monotone or antitone (Approx.v).
    This file proves, with concrete databases, that the remaining positions are
    neither: a mutation there has NO guaranteed effect on the result, so a
    mismatch would be a false alarm, not a DBMS bug.  The Python implementation
    mutated all of them. *)

From Coq Require Import List ZArith Lia.
Import ListNotations.
From ValScope Require Import Bag Logic3 Syntax Semantics Approx Mutate.

Definition a_tbl : query := QTable 0 1.
Definition b_tbl : query := QTable 1 1.

Definition db_ex : db_t :=
  fun n => match n with 0 => [[VInt 1]] | 1 => [[VInt 2]] | _ => [] end.

(** The ON condition of a LEFT JOIN: [ON FALSE -> ON TRUE] weakens the predicate
    (and is sound for an INNER JOIN, see [q_le_inner_join]) but does NOT give a
    super-bag for a LEFT JOIN: the NULL-padded row of the original disappears. *)
Theorem left_join_on_not_monotone :
  p_le PFalse PTrue /\
  ~ q_le (QLeftJoin 1 PFalse a_tbl b_tbl) (QLeftJoin 1 PTrue a_tbl b_tbl).
Proof.
  split.
  - apply p_le_true.
  - intro H. specialize (H db_ex [] [VInt 1; VNull]).
    vm_compute in H. inversion H.
Qed.

(** The right input of a LEFT JOIN: growing it can remove NULL-padded rows. *)
Theorem left_join_right_not_monotone :
  q_le (QWhere PFalse b_tbl) (QWhere PTrue b_tbl) /\
  ~ q_le (QLeftJoin 1 PTrue a_tbl (QWhere PFalse b_tbl))
         (QLeftJoin 1 PTrue a_tbl (QWhere PTrue b_tbl)).
Proof.
  split.
  - apply q_le_where; [apply p_le_false | apply q_le_refl].
  - intro H. specialize (H db_ex [] [VInt 1; VNull]).
    vm_compute in H. inversion H.
Qed.

(** LIMIT: taking a prefix is not monotone for bag inclusion, because which rows
    are kept depends on the order, which SQL does not define. *)
Theorem limit_not_monotone :
  bag_le Nat.eq_dec [1] [2; 1] /\
  ~ bag_le Nat.eq_dec (firstn 1 [1]) (firstn 1 [2; 1]).
Proof.
  split.
  - intro x. unfold count. cbn [count_occ].
    destruct (Nat.eq_dec 1 x); destruct (Nat.eq_dec 2 x); simpl; lia.
  - intro H. specialize (H 1). vm_compute in H. inversion H.
Qed.

(** ---- a worked example of the polarity flip ---- *)

(** [SELECT * FROM t0 WHERE NOT EXISTS (SELECT * FROM t1 WHERE c0 < 5)].
    To make the WHOLE query return more rows ([Up]), the mutator has to make the
    subquery return fewer rows: it replaces the inner condition by FALSE. *)
Definition not_exists_q : query :=
  QWhere (PNot (PExists (QWhere (PCmp CLt (ECol 0) (EConst (VInt 5))) b_tbl))) a_tbl.

Example up_enters_not_exists_with_false :
  In (QWhere (PNot (PExists (QWhere PFalse b_tbl))) a_tbl) (mut_q Up not_exists_q).
Proof.
  vm_compute. repeat first [ left; reflexivity | right ].
Qed.

(** And the soundness theorem says that this mutant is indeed a super-bag. *)
Example not_exists_mutant_is_sound :
  q_le not_exists_q (QWhere (PNot (PExists (QWhere PFalse b_tbl))) a_tbl).
Proof.
  apply (mut_q_sound Up not_exists_q). exact up_enters_not_exists_with_false.
Qed.

(** The ON condition and the right input of a LEFT JOIN are never mutated: every
    mutant of a LEFT JOIN is a root rewrite or only changes the left input. *)
Lemma left_join_only_left_entered : forall d pad p a b q',
  In q' (mut_q d (QLeftJoin pad p a b)) ->
  q' = QDistinct (QLeftJoin pad p a b) \/ q' = QInnerJoin p a b \/
  exists a', q' = QLeftJoin pad p a' b.
Proof.
  intros d pad p a b q' H. simpl mut_q in H. unfold base_q in H.
  destruct d; simpl in H.
  - apply in_map_iff in H as [a' [<- _]]. right; right. exists a'. reflexivity.
  - destruct H as [E|[E|H]].
    + left. symmetry. exact E.
    + right; left. symmetry. exact E.
    + apply in_map_iff in H as [a' [<- _]]. right; right. exists a'. reflexivity.
Qed.
