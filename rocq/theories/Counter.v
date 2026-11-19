(** Counter.v: why some positions are never mutated.

    The mutators only enter positions that are monotone or antitone (Approx.v).
    This file proves, with concrete databases, that the remaining positions are
    neither: a mutation there has NO guaranteed effect on the result, so a
    mismatch would be a false alarm, not a DBMS bug.  The Python implementation
    mutated all of them. *)

From Coq Require Import List ZArith Lia QArith Ascii.
Import ListNotations.
From Coq Require Import String.
From ValScope Require Import Bag Logic3 Pattern Syntax Semantics Approx Rule Engine Registry.

(** ---- a concrete world ---- *)

(** The simplest dialect: values are equal only when identical (a binary collation),
    integers are compared numerically, everything else is incomparable (UNKNOWN), and
    arithmetic is defined on integers and rationals only.  It satisfies every law of
    [db_t], so it is a legal world and the counter-examples below are real. *)

Definition veqb (x y : value) : bool := if value_eq_dec x y then true else false.

Lemma veqb_eq : forall x y, veqb x y = true -> x = y.
Proof. intros x y. unfold veqb. destruct (value_eq_dec x y); congruence. Qed.

Lemma list_veqb_eq : forall a b, list_eqb veqb a b = true -> a = b.
Proof.
  induction a as [|x a IH]; intros [|y b] H; simpl in H; try discriminate; [reflexivity|].
  apply andb_prop in H as [H1 H2]. apply veqb_eq in H1. rewrite H1, (IH b H2). reflexivity.
Qed.

Definition vcompare (x y : value) : option comparison :=
  match x, y with VInt a, VInt b => Some (Z.compare a b) | _, _ => None end.

Definition ex_add (x y : value) : value :=
  match x, y with VInt a, VInt b => VInt (a + b) | _, _ => VNull end.

Definition ex_mul (x y : value) : value :=
  match x, y with
  | VInt a, VInt b => VInt (a * b)
  | VNum q, VInt b => VNum (q * inject_Z b)
  | _, _ => VNull
  end.

Definition ex_text (v : value) : option string :=
  match v with VStr s => Some s | _ => None end.

Lemma ex_mul_num : forall v k,
  match numq (ex_mul v (VInt k)), numq v with
  | Some a, Some b => Qeq a (Qmult b (inject_Z k))
  | None, None => True
  | _, _ => False
  end.
Proof.
  intros [| z | q | s] k; simpl; try exact I.
  - rewrite inject_Z_mult. apply Qeq_refl.
  - apply Qeq_refl.
Qed.

Ltac by_eq := repeat match goal with
  | H : veqb _ _ = true |- _ => apply veqb_eq in H; subst
  | H : list_eqb veqb _ _ = true |- _ => apply list_veqb_eq in H; subst
  end.

Definition ex_world (t : nat -> list row) : db_t.
Proof.
  refine (mk_world t (fun _ _ => U3) (fun _ _ => VNull) (fun _ _ => [])
            (fun c x y => cmp_of_compare c (vcompare x y)) ex_add ex_mul veqb ex_text Ascii.eqb
            _ _ _ _ _ _ _ _ _ _ _ _ _ _).
  - intros x. unfold veqb. destruct (value_eq_dec x x); congruence.
  - intros x y H. by_eq. unfold veqb. destruct (value_eq_dec y y); congruence.
  - intros x y z H1 H2. by_eq. unfold veqb. destruct (value_eq_dec z z); congruence.
  - intros c c' x y H. apply cmp_of_compare_weaker. exact H.
  - intros c x x' y y' H1 H2. by_eq. reflexivity.
  - intros x x' y y' H1 H2. by_eq. unfold veqb. destruct (value_eq_dec (ex_add x' y') (ex_add x' y')); congruence.
  - intros x x' y y' H1 H2. by_eq. unfold veqb. destruct (value_eq_dec (ex_mul x' y') (ex_mul x' y')); congruence.
  - intros x y H E. by_eq. reflexivity.
  - intros x y p H. by_eq. reflexivity.
  - intros x y r H. by_eq. reflexivity.
  - intros n c c' H. reflexivity.
  - intros n c c' H. reflexivity.
  - intros n c c' H. intros x. simpl. lia.
  - apply ex_mul_num.
Defined.

Local Open Scope nat_scope.
Definition a_tbl : query := QTable 0 1.
Definition b_tbl : query := QTable 1 1.

Definition db_ex : db_t :=
  ex_world (fun n => match n with 0 => [[VInt 1]] | 1 => [[VInt 2]] | _ => [] end).

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
  bag_le Nat.eqb [1] [2; 1] /\
  ~ bag_le Nat.eqb (firstn 1 [1]) (firstn 1 [2; 1]).
Proof.
  split.
  - intro x. simpl. destruct (Nat.eqb x 1); destruct (Nat.eqb x 2); simpl; lia.
  - intro H. specialize (H 1). vm_compute in H. lia.
Qed.

(** ---- a worked example of the polarity flip ---- *)

(** [SELECT * FROM t0 WHERE NOT EXISTS (SELECT * FROM t1 WHERE c0 < 5)].
    To make the WHOLE query return more rows ([Up]), the mutator has to make the
    subquery return fewer rows: it replaces the inner condition by FALSE. *)
Definition not_exists_q : query :=
  QWhere (PNot (PExists (QWhere (PCmp CLt (ECol 0) (EConst (VInt 5))) b_tbl))) a_tbl.

Definition not_exists_mutant : query :=
  QWhere (PNot (PExists (QWhere PFalse b_tbl))) a_tbl.

Example up_enters_not_exists_with_false :
  In ("cond->FALSE"%string, not_exists_mutant) (mutate Up not_exists_q).
Proof.
  vm_compute. repeat first [ left; reflexivity | right ].
Qed.

(** And the soundness theorem says that this mutant is indeed a super-bag. *)
Example not_exists_mutant_is_sound : q_le not_exists_q not_exists_mutant.
Proof.
  apply (mutate_sound Up not_exists_q _ _ up_enters_not_exists_with_false).
Qed.

(** The ON condition and the right input of a LEFT JOIN are never mutated,
    whatever rules are plugged in: every mutant of a LEFT JOIN is a root rewrite
    or only changes the left input. *)
Lemma left_join_only_left_entered : forall prs qrs d pad p a b name q',
  In (name, q') (mut_q prs qrs d (QLeftJoin pad p a b)) ->
  In (name, q') (fire_q qrs d (QLeftJoin pad p a b)) \/
  exists a', q' = QLeftJoin pad p a' b.
Proof.
  intros prs qrs d pad p a b name q' H. simpl mut_q in H.
  apply in_app_or in H as [H|H]; [left; exact H|right].
  unfold lmap in H. apply in_map_iff in H as [[n a'] [E _]].
  inversion E; subst. exists a'. reflexivity.
Qed.
