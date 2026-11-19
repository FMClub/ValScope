(** Logic3.v: SQL values, three-valued logic and comparisons.

    [tv_le] orders the truth values [F3 < U3 < T3].  A WHERE/ON/HAVING clause keeps a
    row exactly when the predicate is [T3], so a predicate that is larger in this
    order keeps more rows.  [NOT] reverses the order, which is why the polarity of a
    position matters. *)

From Coq Require Import ZArith List Arith Lia.
Import ListNotations.

Inductive value : Type :=
  | VNull : value
  | VInt : Z -> value.

Definition row := list value.

Lemma value_eq_dec : forall a b : value, {a = b} + {a <> b}.
Proof. decide equality. apply Z.eq_dec. Defined.

Lemma row_eq_dec : forall a b : row, {a = b} + {a <> b}.
Proof. apply list_eq_dec. apply value_eq_dec. Defined.

Inductive tv : Type := F3 | U3 | T3.

Definition rk (t : tv) : nat := match t with F3 => 0 | U3 => 1 | T3 => 2 end.
Definition tv_le (a b : tv) : Prop := rk a <= rk b.
Definition is_true (t : tv) : bool := match t with T3 => true | _ => false end.
Definition tv_not (t : tv) : tv := match t with F3 => T3 | U3 => U3 | T3 => F3 end.
Definition tv_and (a b : tv) : tv := if Nat.leb (rk a) (rk b) then a else b.
Definition tv_or  (a b : tv) : tv := if Nat.leb (rk a) (rk b) then b else a.
Definition of_bool (b : bool) : tv := if b then T3 else F3.

Lemma tv_le_refl : forall a, tv_le a a.
Proof. intro a. unfold tv_le. lia. Qed.

Lemma tv_le_trans : forall a b c, tv_le a b -> tv_le b c -> tv_le a c.
Proof. unfold tv_le. intros. lia. Qed.

Lemma tv_le_T : forall a, tv_le a T3.
Proof. intro a. destruct a; unfold tv_le; simpl; lia. Qed.

Lemma tv_le_F : forall a, tv_le F3 a.
Proof. intro a. destruct a; unfold tv_le; simpl; lia. Qed.

Lemma tv_not_anti : forall a b, tv_le a b -> tv_le (tv_not b) (tv_not a).
Proof. intros a b. destruct a, b; unfold tv_le; simpl; lia. Qed.

Lemma tv_and_mono : forall a a' b b',
  tv_le a a' -> tv_le b b' -> tv_le (tv_and a b) (tv_and a' b').
Proof. intros a a' b b'. destruct a, a', b, b'; unfold tv_le; simpl; lia. Qed.

Lemma tv_or_mono : forall a a' b b',
  tv_le a a' -> tv_le b b' -> tv_le (tv_or a b) (tv_or a' b').
Proof. intros a a' b b'. destruct a, a', b, b'; unfold tv_le; simpl; lia. Qed.

Lemma tv_and_le_l : forall a b, tv_le (tv_and a b) a.
Proof. intros a b. destruct a, b; unfold tv_le; simpl; lia. Qed.

Lemma tv_and_le_r : forall a b, tv_le (tv_and a b) b.
Proof. intros a b. destruct a, b; unfold tv_le; simpl; lia. Qed.

Lemma tv_or_ge_l : forall a b, tv_le a (tv_or a b).
Proof. intros a b. destruct a, b; unfold tv_le; simpl; lia. Qed.

Lemma tv_or_ge_r : forall a b, tv_le b (tv_or a b).
Proof. intros a b. destruct a, b; unfold tv_le; simpl; lia. Qed.

Lemma is_true_mono : forall a b, tv_le a b -> is_true a = true -> is_true b = true.
Proof. intros a b. destruct a, b; unfold tv_le; simpl; intros; try lia; congruence. Qed.

(** ---- comparisons (NULL on either side gives UNKNOWN) ---- *)

Inductive cmp : Type := CEq | CNe | CLt | CLe | CGt | CGe.

Definition cmp3 (c : cmp) (v1 v2 : value) : tv :=
  match v1, v2 with
  | VInt a, VInt b =>
      of_bool (match c with
               | CEq => Z.eqb a b
               | CNe => negb (Z.eqb a b)
               | CLt => Z.ltb a b
               | CLe => Z.leb a b
               | CGt => Z.gtb a b
               | CGe => Z.geb a b
               end)
  | _, _ => U3
  end.

Lemma tv_le_of_bool : forall b1 b2 : bool,
  (b1 = true -> b2 = true) -> tv_le (of_bool b1) (of_bool b2).
Proof.
  intros b1 b2 H. destruct b1, b2; unfold tv_le, of_bool, rk; simpl;
    first [ lia | exfalso; discriminate (H eq_refl) ].
Qed.

(** Weakening comparisons (rules 8, 9, 10): [a < b] implies [a <= b], [a > b]
    implies [a >= b], and [a = b] implies both [a <= b] and [a >= b].  Read
    backwards, the same facts give the strengthening rules. *)
Inductive cmp_weaker : cmp -> cmp -> Prop :=
  | W_lt_le : cmp_weaker CLt CLe
  | W_gt_ge : cmp_weaker CGt CGe
  | W_eq_le : cmp_weaker CEq CLe
  | W_eq_ge : cmp_weaker CEq CGe
  | W_lt_ne : cmp_weaker CLt CNe
  | W_gt_ne : cmp_weaker CGt CNe.

Lemma cmp3_weaker : forall c c' x y,
  cmp_weaker c c' -> tv_le (cmp3 c x y) (cmp3 c' x y).
Proof.
  intros c c' x y H. destruct x as [|a]; destruct y as [|b]; simpl;
    try apply tv_le_refl.
  apply tv_le_of_bool. intro Hb.
  destruct H.
  - apply Z.ltb_lt in Hb. apply Z.leb_le. lia.
  - apply Z.gtb_gt in Hb. apply Z.geb_le. lia.
  - apply Z.eqb_eq in Hb. apply Z.leb_le. lia.
  - apply Z.eqb_eq in Hb. apply Z.geb_le. lia.
  - apply Z.ltb_lt in Hb. apply Bool.negb_true_iff. apply Z.eqb_neq. lia.
  - apply Z.gtb_gt in Hb. apply Bool.negb_true_iff. apply Z.eqb_neq. lia.
Qed.
