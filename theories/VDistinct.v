(** VDistinct.v: value queries under DISTINCT (or a UNION of value queries).

    [SELECT DISTINCT items ...] removes duplicate result rows.  A value mutation keeps
    the rows of the original and of the mutant in one-to-one correspondence ([tmut_sound]),
    but after the duplicates are removed two rows of one side may have become one, so the
    correspondence is no longer one to one.  What still holds is a COVER in both
    directions: every row of the mutant's result is related to some row of the original's
    result, and every row of the original's result to some row of the mutant's.

    For a mutation of the HAVING predicate, the rows of the original are a sub-list of
    those of the mutant (or the converse); after DISTINCT every row of the smaller result
    is a row of the larger one.

    Rows are compared with the equality of value rows (lists of [option R]); NULL equals
    NULL, as in DISTINCT.  [UNION] of value queries is DISTINCT over their UNION ALL. *)

From Coq Require Import List String Reals.
Import ListNotations.
From ValScope Require Import Bag Logic3 Pattern Syntax Semantics Rule Engine Value VEngine VHaving VUnion.

Definition vrow := list (option R).

Definition vrow_eq_dec : forall x y : vrow, {x = y} + {x <> y}.
Proof. decide equality. decide equality. apply Req_EM_T. Defined.

(** The result of DISTINCT. *)
Definition distinct_rows (l : list vrow) : list vrow := nodup vrow_eq_dec l.

(** Every row on each side is related to a row on the other side. *)
Definition covers (r : vrel) (j : nat) (l l' : list vrow) : Prop :=
  (forall y, In y l' -> exists x, In x l /\ row_rel r j x y) /\
  (forall x, In x l -> exists y, In y l' /\ row_rel r j x y).

Lemma forall2_covers : forall r j l l', Forall2 (row_rel r j) l l' -> covers r j l l'.
Proof.
  intros r j l l' H. induction H as [|x y l l' Hxy H IH]; split; intros z Hz;
    try contradiction; destruct IH as [IH1 IH2]; destruct Hz as [<-|Hz].
  - exists x. split; [left; reflexivity|exact Hxy].
  - destruct (IH1 z Hz) as [w [Hw Hr]]. exists w. split; [right; exact Hw|exact Hr].
  - exists y. split; [left; reflexivity|exact Hxy].
  - destruct (IH2 z Hz) as [w [Hw Hr]]. exists w. split; [right; exact Hw|exact Hr].
Qed.

Lemma covers_distinct : forall r j l l', covers r j l l' -> covers r j (distinct_rows l) (distinct_rows l').
Proof.
  intros r j l l' [H1 H2]. unfold distinct_rows. split.
  - intros y Hy. apply nodup_In in Hy. destruct (H1 y Hy) as [x [Hx Hr]].
    exists x. split; [apply nodup_In; exact Hx|exact Hr].
  - intros x Hx. apply nodup_In in Hx. destruct (H2 x Hx) as [y [Hy Hr]].
    exists y. split; [apply nodup_In; exact Hy|exact Hr].
Qed.

(** The value mutator, under DISTINCT. *)
Theorem tmut_distinct_sound : forall rs t name r j t',
  In (name, (r, (j, t'))) (tmut rs t) ->
  forall env db, covers r j (distinct_rows (teval env db t)) (distinct_rows (teval env db t')).
Proof.
  intros rs t name r j t' H env db. apply covers_distinct, forall2_covers.
  exact (tmut_sound rs t name r j t' H env db).
Qed.

(** The HAVING mutator, under DISTINCT: set inclusion (each row of the smaller result,
    which has no duplicates, is a row of the larger one). *)
Definition d_sub (t t' : vtop) : Prop :=
  forall env db, incl (distinct_rows (teval env db t)) (distinct_rows (teval env db t')).

Lemma sub_incl : forall {X : Type} (l l' : list X), Sub l l' -> incl l l'.
Proof.
  intros X l l' H. induction H as [|x l l' H IH|x l l' H IH]; intros z Hz.
  - exact Hz.
  - destruct Hz as [<-|Hz]; [left; reflexivity|right; apply IH; exact Hz].
  - right. apply IH. exact Hz.
Qed.

Theorem thmut_distinct_sound : forall prs qrs d t name t',
  In (name, t') (thmut prs qrs d t) -> dle d_sub d t t'.
Proof.
  intros prs qrs d t name t' H. pose proof (thmut_sound prs qrs d t name t' H) as K.
  destruct d; simpl in *; intros env db z Hz; unfold distinct_rows in *;
    apply nodup_In; apply nodup_In in Hz; apply (sub_incl _ _ (K env db)); exact Hz.
Qed.

Lemma distinct_rows_nodup : forall l, NoDup (distinct_rows l).
Proof. intros l. apply NoDup_nodup. Qed.
