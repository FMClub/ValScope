(** Logic3.v: SQL values, three-valued logic and comparison operators.

    Values are NULL, integers, rational numbers and text.  Rationals cover DECIMAL and
    every finite FLOAT / DOUBLE value exactly (a finite binary floating-point number is
    a rational).  How values are compared, converted and collated is NOT fixed here: it
    depends on the DBMS and is supplied by the world (Semantics.v), together with the
    few laws the theorems need.

    [tv_le] orders the truth values [F3 < U3 < T3].  A WHERE / ON / HAVING clause keeps
    a row exactly when the predicate is [T3], so a predicate that is larger in this
    order keeps more rows.  [NOT] reverses the order, which is why the polarity of a
    position matters. *)

From Coq Require Import ZArith QArith String List Arith Lia.
Import ListNotations.
Local Open Scope nat_scope.

Inductive value : Type :=
  | VNull : value
  | VInt  : Z -> value
  | VNum  : Q -> value
  | VStr  : string -> value.

Definition row := list value.

Lemma Q_struct_dec : forall a b : Q, {a = b} + {a <> b}.
Proof.
  intros [n d] [n' d']. destruct (Z.eq_dec n n') as [->|Hn]; destruct (Pos.eq_dec d d') as [->|Hd];
    [left; reflexivity|right; congruence|right; congruence|right; congruence].
Defined.

Lemma value_eq_dec : forall a b : value, {a = b} + {a <> b}.
Proof. decide equality; [apply Z.eq_dec|apply Q_struct_dec|apply string_dec]. Defined.

Lemma row_eq_dec : forall a b : row, {a = b} + {a <> b}.
Proof. apply list_eq_dec. apply value_eq_dec. Defined.

(** Column-wise lifting of an equivalence on values to rows. *)
Fixpoint list_eqb {X : Type} (f : X -> X -> bool) (a b : list X) : bool :=
  match a, b with
  | [], [] => true
  | x :: a', y :: b' => f x y && list_eqb f a' b'
  | _, _ => false
  end.

Section ListEqb.
Context {X : Type} (f : X -> X -> bool).
Hypothesis f_refl : forall x, f x x = true.
Hypothesis f_sym : forall x y, f x y = true -> f y x = true.
Hypothesis f_trans : forall x y z, f x y = true -> f y z = true -> f x z = true.

Lemma list_eqb_refl : forall a, list_eqb f a a = true.
Proof. induction a as [|x a IH]; simpl; [reflexivity|]. rewrite f_refl, IH. reflexivity. Qed.

Lemma list_eqb_sym : forall a b, list_eqb f a b = true -> list_eqb f b a = true.
Proof.
  induction a as [|x a IH]; intros b H; destruct b as [|y b]; simpl in *; try congruence.
  apply andb_prop in H as [H1 H2]. rewrite (f_sym _ _ H1), (IH _ H2). reflexivity.
Qed.

Lemma list_eqb_trans : forall a b c, list_eqb f a b = true -> list_eqb f b c = true -> list_eqb f a c = true.
Proof.
  induction a as [|x a IH]; intros b c H1 H2; destruct b as [|y b]; destruct c as [|z c];
    simpl in *; try congruence.
  apply andb_prop in H1 as [E1 R1]. apply andb_prop in H2 as [E2 R2].
  rewrite (f_trans _ _ _ E1 E2), (IH _ _ R1 R2). reflexivity.
Qed.

Lemma list_eqb_app : forall a a' b b', list_eqb f a a' = true -> list_eqb f b b' = true ->
  list_eqb f (a ++ b) (a' ++ b') = true.
Proof.
  induction a as [|x a IH]; intros a' b b' H1 H2; destruct a' as [|y a']; simpl in *;
    try congruence.
  apply andb_prop in H1 as [E1 R1]. rewrite E1, (IH _ _ _ R1 H2). reflexivity.
Qed.

Lemma list_eqb_nth : forall a b i d, f d d = true -> list_eqb f a b = true -> f (nth i a d) (nth i b d) = true.
Proof.
  induction a as [|x a IH]; intros b i d Hd H; destruct b as [|y b]; simpl in H; try discriminate.
  - destruct i; exact Hd.
  - apply andb_prop in H as [E R]. destruct i; simpl; [exact E|apply IH; assumption].
Qed.

Lemma list_eqb_map : forall {Y : Type} (g : Y -> X) (h : Y -> X) (l : list Y),
  (forall y, f (g y) (h y) = true) -> list_eqb f (map g l) (map h l) = true.
Proof.
  intros Y g h l H. induction l as [|y l IH]; simpl; [reflexivity|]. rewrite H, IH. reflexivity.
Qed.

Lemma list_eqb_repeat : forall x n, list_eqb f (repeat x n) (repeat x n) = true.
Proof. intros x n. apply list_eqb_refl. Qed.

End ListEqb.

(** ---------------- three-valued logic ---------------- *)

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

Lemma tv_and_mono : forall a a' b b', tv_le a a' -> tv_le b b' -> tv_le (tv_and a b) (tv_and a' b').
Proof. intros a a' b b'. destruct a, a', b, b'; unfold tv_le; simpl; lia. Qed.

Lemma tv_or_mono : forall a a' b b', tv_le a a' -> tv_le b b' -> tv_le (tv_or a b) (tv_or a' b').
Proof. intros a a' b b'. destruct a, a', b, b'; unfold tv_le; simpl; lia. Qed.

Lemma tv_or_lub : forall a b t, tv_le a t -> tv_le b t -> tv_le (tv_or a b) t.
Proof. intros a b t. destruct a, b, t; unfold tv_le; simpl; lia. Qed.

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

Lemma tv_le_of_bool : forall b1 b2 : bool, (b1 = true -> b2 = true) -> tv_le (of_bool b1) (of_bool b2).
Proof.
  intros b1 b2 H. destruct b1, b2; unfold tv_le, of_bool, rk; simpl;
    first [ lia | exfalso; discriminate (H eq_refl) ].
Qed.

(** ---------------- comparison operators ---------------- *)

Inductive cmp : Type := CEq | CNe | CLt | CLe | CGt | CGe.

(** [cmp_weaker c c']: [x c y] implies [x c' y] for every pair of values that the
    DBMS compares in the usual way.  Rules 8, 9, 10 weaken [c] to [c']; read
    backwards they strengthen. *)
Inductive cmp_weaker : cmp -> cmp -> Prop :=
  | W_lt_le : cmp_weaker CLt CLe
  | W_gt_ge : cmp_weaker CGt CGe
  | W_eq_le : cmp_weaker CEq CLe
  | W_eq_ge : cmp_weaker CEq CGe
  | W_lt_ne : cmp_weaker CLt CNe
  | W_gt_ne : cmp_weaker CGt CNe.

(** A comparison defined from a three-way comparison (None = NULL or incomparable)
    satisfies the weakening laws automatically, whatever the order is: numeric,
    lexicographic, case-insensitive, with type coercions, ... *)
Definition cmp_of_compare (c : cmp) (o : option comparison) : tv :=
  match o with
  | None => U3
  | Some r =>
      of_bool (match c, r with
               | CEq, Eq | CLe, Eq | CGe, Eq => true
               | CLt, Lt | CLe, Lt | CNe, Lt => true
               | CGt, Gt | CGe, Gt | CNe, Gt => true
               | _, _ => false
               end)
  end.

Lemma cmp_of_compare_weaker : forall c c' o,
  cmp_weaker c c' -> tv_le (cmp_of_compare c o) (cmp_of_compare c' o).
Proof.
  intros c c' [r|] H; [|apply tv_le_refl]. simpl. apply tv_le_of_bool.
  destruct H, r; simpl; congruence.
Qed.
