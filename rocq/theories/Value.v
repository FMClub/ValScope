(** Value.v: the value-semantic layer.

    A value-semantic mutation changes one select item of a query and leaves the
    set of rows alone.  The result rows of the original and the mutant then
    correspond one to one, and the mutated column is related by a VALUE RELATION.

    Select items are aggregate expressions ([aexpr]) evaluated on a group of rows.
    Inputs are integers (with NULL); results are real numbers (with NULL), because
    AVG needs division and STDDEV a square root.

    Several rules of ValScope only hold under a condition on the data (sign,
    below/above 1).  Instead of a precondition, each rule states an unconditional
    relation that mentions the original value:
      - [VLe]        : the value does not decrease
      - [VGe]        : the value does not increase
      - [VAwayZero]  : a non-negative value does not decrease, a non-positive
                       one does not increase            (v -> v * k, k >= 1)
      - [VTowardOne] : a value <= 1 does not decrease, a value >= 1 does not
                       increase                         (v -> sqrt v)
      - [VAwayOne]   : the converse                     (s -> s * s)
    The checker only has to know these five relations. *)

From Coq Require Import List ZArith Reals Lra Lia.
Import ListNotations.
From ValScope Require Import Logic3 Syntax Semantics.
Local Open Scope R_scope.

(** ---------------- value relations ---------------- *)

Inductive vrel : Type := VLe | VGe | VAwayZero | VTowardOne | VAwayOne.

Definition rel_R (r : vrel) (a b : R) : Prop :=
  match r with
  | VLe => a <= b
  | VGe => b <= a
  | VAwayZero => (0 <= a -> a <= b) /\ (a <= 0 -> b <= a)
  | VTowardOne => (a <= 1 -> a <= b) /\ (1 <= a -> b <= a)
  | VAwayOne => (1 <= a -> a <= b) /\ (a <= 1 -> b <= a)
  end.

(** NULL is related to NULL only: a mutation must not change NULL-ness. *)
Definition rel_holds (r : vrel) (x y : option R) : Prop :=
  match x, y with
  | None, None => True
  | Some a, Some b => rel_R r a b
  | _, _ => False
  end.

(** Relations that survive a monotone context (addition, a non-negative factor,
    a monotone function). *)
Definition is_mono (r : vrel) : bool :=
  match r with VLe | VGe => true | _ => false end.

(** ---------------- aggregates over integer columns ---------------- *)

Fixpoint ints (vs : list value) : list Z :=
  match vs with
  | [] => []
  | VInt z :: t => z :: ints t
  | VNull :: t => ints t
  end.

(** Non-NULL values of [e] over the rows of a group. *)
Definition col (e : expr) (g : list row) : list Z :=
  ints (map (fun r => eval_expr r e) g).

Definition zsum (l : list Z) : Z := fold_right Z.add 0%Z l.

Definition zmax (l : list Z) : option Z :=
  match l with [] => None | x :: t => Some (fold_right Z.max x t) end.

Definition zmin (l : list Z) : option Z :=
  match l with [] => None | x :: t => Some (fold_right Z.min x t) end.

Definition zlen (l : list Z) : Z := Z.of_nat (length l).

Definition mean (l : list Z) : R := IZR (zsum l) / IZR (zlen l).

Fixpoint sumsq (m : R) (l : list Z) : R :=
  match l with
  | [] => 0
  | x :: t => (IZR x - m) * (IZR x - m) + sumsq m t
  end.

(** Sample variance; NULL for fewer than two values, as in MySQL. *)
Definition var_samp (l : list Z) : option R :=
  if (2 <=? length l)%nat
  then Some (sumsq (mean l) l / IZR (zlen l - 1))
  else None.

Definition oIZR (o : option Z) : option R :=
  match o with Some z => Some (IZR z) | None => None end.

Definition olift2 (f : R -> R -> R) (x y : option R) : option R :=
  match x, y with Some a, Some b => Some (f a b) | _, _ => None end.

(** ---------------- select items ---------------- *)

Inductive aexpr : Type :=
  | ACol     : expr -> aexpr          (* a row-level expression (a grouping key) *)
  | AConst   : Z -> aexpr
  | ACount   : expr -> aexpr
  | ACountD  : expr -> aexpr          (* COUNT(DISTINCT e) *)
  | ASum     : expr -> aexpr
  | AMin     : expr -> aexpr
  | AMax     : expr -> aexpr
  | AAvg     : expr -> aexpr
  | AVarSamp : expr -> aexpr
  | AStdSamp : expr -> aexpr
  | AAdd     : aexpr -> aexpr -> aexpr
  | AMul     : aexpr -> aexpr -> aexpr
  | AMono    : nat -> aexpr -> aexpr. (* a monotone (non-decreasing) scalar function *)

(** Interpretation of the monotone function symbols. *)
Record venv : Type := mk_venv {
  mfn : nat -> R -> R;
  mfn_mono : forall n x y, x <= y -> mfn n x <= mfn n y
}.

Fixpoint aeval (env : venv) (g : list row) (a : aexpr) : option R :=
  match a with
  | ACol e =>
      match g with
      | r :: _ => match eval_expr r e with VInt z => Some (IZR z) | VNull => None end
      | [] => None
      end
  | AConst k => Some (IZR k)
  | ACount e => Some (IZR (zlen (col e g)))
  | ACountD e => Some (IZR (zlen (nodup Z.eq_dec (col e g))))
  | ASum e => match col e g with [] => None | l => Some (IZR (zsum l)) end
  | AMin e => oIZR (zmin (col e g))
  | AMax e => oIZR (zmax (col e g))
  | AAvg e => match col e g with [] => None | l => Some (mean l) end
  | AVarSamp e => var_samp (col e g)
  | AStdSamp e => match var_samp (col e g) with Some v => Some (sqrt v) | None => None end
  | AAdd a b => olift2 Rplus (aeval env g a) (aeval env g b)
  | AMul a b => olift2 Rmult (aeval env g a) (aeval env g b)
  | AMono f a => match aeval env g a with Some x => Some (mfn env f x) | None => None end
  end.

(** ---------------- facts about the aggregates ---------------- *)

Lemma max_ge : forall t x y, In y (x :: t) -> (y <= fold_right Z.max x t)%Z.
Proof.
  induction t as [|z t IH]; intros x y H; simpl in *.
  - destruct H as [->|[]]. lia.
  - destruct H as [->|[->|H]].
    + specialize (IH y y (or_introl eq_refl)). lia.
    + lia.
    + specialize (IH x y (or_intror H)). lia.
Qed.

Lemma min_le : forall t x y, In y (x :: t) -> (fold_right Z.min x t <= y)%Z.
Proof.
  induction t as [|z t IH]; intros x y H; simpl in *.
  - destruct H as [->|[]]. lia.
  - destruct H as [->|[->|H]].
    + specialize (IH y y (or_introl eq_refl)). lia.
    + lia.
    + specialize (IH x y (or_intror H)). lia.
Qed.

Lemma zsum_le : forall l m, (forall y, In y l -> (y <= m)%Z) -> (zsum l <= zlen l * m)%Z.
Proof.
  induction l as [|x l IH]; intros m H.
  - simpl. lia.
  - unfold zlen in *. simpl length. rewrite Nat2Z.inj_succ. simpl zsum.
    assert (x <= m)%Z by (apply H; left; reflexivity).
    assert (zsum l <= Z.of_nat (length l) * m)%Z by (apply IH; intros; apply H; right; assumption).
    lia.
Qed.

Lemma length_nodup_le : forall l : list Z, (length (nodup Z.eq_dec l) <= length l)%nat.
Proof.
  induction l as [|x l IH]; simpl; [lia|].
  destruct (in_dec Z.eq_dec x l); simpl; lia.
Qed.

Lemma sumsq_nonneg : forall m l, 0 <= sumsq m l.
Proof.
  induction l as [|x l IH]; simpl; [lra|].
  assert (0 <= (IZR x - m) * (IZR x - m)) by apply Rle_0_sqr. lra.
Qed.

Lemma var_samp_nonneg : forall l v, var_samp l = Some v -> 0 <= v.
Proof.
  intros l v H. unfold var_samp in H.
  destruct (2 <=? length l)%nat eqn:E; [|discriminate].
  inversion H; subst. apply Nat.leb_le in E.
  unfold Rdiv. apply Rmult_le_pos; [apply sumsq_nonneg|].
  left. apply Rinv_0_lt_compat. apply IZR_lt. unfold zlen. lia.
Qed.

(** The mathematical core of rules 21 and 22. *)
Lemma sqrt_toward_one : forall v, 0 <= v -> rel_R VTowardOne v (sqrt v).
Proof.
  intros v Hv. pose proof (sqrt_pos v) as Hs. pose proof (sqrt_sqrt v Hv) as Hq.
  set (s := sqrt v) in *. simpl. split; intro H.
  - destruct (Rle_dec s 1) as [L|L]; nra.
  - destruct (Rle_dec 1 s) as [L|L]; nra.
Qed.

Lemma sq_away_one : forall v, 0 <= v -> rel_R VAwayOne (sqrt v) v.
Proof.
  intros v Hv. pose proof (sqrt_pos v) as Hs. pose proof (sqrt_sqrt v Hv) as Hq.
  set (s := sqrt v) in *. simpl. split; intro H; nra.
Qed.

(** Scaling a column scales its sum (rule 23). *)
Lemma eval_mul_const : forall r e k,
  eval_expr r (EMul e (EConst (VInt k))) =
  match eval_expr r e with VInt x => VInt (x * k) | VNull => VNull end.
Proof. intros r e k. reflexivity. Qed.

Lemma col_scale : forall e k g,
  col (EMul e (EConst (VInt k))) g = map (fun z => (z * k)%Z) (col e g).
Proof.
  intros e k g. unfold col. induction g as [|r g IH]; [reflexivity|].
  cbn [map]. rewrite eval_mul_const.
  destruct (eval_expr r e); cbn [ints map]; rewrite IH; reflexivity.
Qed.

Lemma zsum_scale : forall k l, zsum (map (fun z => (z * k)%Z) l) = (zsum l * k)%Z.
Proof.
  intros k l. induction l as [|x l IH]; simpl; [reflexivity|]. rewrite IH. lia.
Qed.

(** ---------------- monotone contexts ---------------- *)

Lemma ctx_add_l : forall r u u' w, is_mono r = true ->
  rel_holds r u u' -> rel_holds r (olift2 Rplus u w) (olift2 Rplus u' w).
Proof.
  intros r u u' w Hm H. destruct r; try discriminate;
    destruct u, u', w; simpl in *; try tauto; lra.
Qed.

Lemma ctx_add_r : forall r u u' w, is_mono r = true ->
  rel_holds r u u' -> rel_holds r (olift2 Rplus w u) (olift2 Rplus w u').
Proof.
  intros r u u' w Hm H. destruct r; try discriminate;
    destruct u, u', w; simpl in *; try tauto; lra.
Qed.

Lemma ctx_mul_const : forall r u u' k, is_mono r = true -> (0 <= k)%Z ->
  rel_holds r u u' ->
  rel_holds r (olift2 Rmult u (Some (IZR k))) (olift2 Rmult u' (Some (IZR k))).
Proof.
  intros r u u' k Hm Hk H. apply IZR_le in Hk.
  destruct r; try discriminate; destruct u, u'; simpl in *; try tauto; nra.
Qed.

(** ---------------- value queries ---------------- *)

(** The three shapes of a SELECT whose items are mutated:
    - [VProj]   : no aggregation, every row is its own group;
    - [VGroup]  : GROUP BY keys;
    - [VGlobal] : aggregates without GROUP BY (one row, even on empty input). *)
Inductive vquery : Type :=
  | VProj   : list aexpr -> query -> vquery
  | VGroup  : list expr -> list aexpr -> query -> vquery
  | VGlobal : list aexpr -> query -> vquery.

Definition vitems (v : vquery) : list aexpr :=
  match v with VProj i _ | VGroup _ i _ | VGlobal i _ => i end.

Definition with_items (v : vquery) (i : list aexpr) : vquery :=
  match v with
  | VProj _ q => VProj i q
  | VGroup k _ q => VGroup k i q
  | VGlobal _ q => VGlobal i q
  end.

Definition key_of (keys : list expr) (r : row) : list value :=
  map (eval_expr r) keys.

Definition key_dec := list_eq_dec value_eq_dec.

(** The groups do not depend on the select items. *)
Definition vgroups (db : db_t) (v : vquery) : list (list row) :=
  match v with
  | VProj _ q => map (fun r => [r]) (eval_q db [] q)
  | VGroup keys _ q =>
      let rows := eval_q db [] q in
      map (fun k => filter (fun r => if key_dec (key_of keys r) k then true else false) rows)
          (nodup key_dec (map (key_of keys) rows))
  | VGlobal _ q => [eval_q db [] q]
  end.

Definition veval (env : venv) (db : db_t) (v : vquery) : list (list (option R)) :=
  map (fun g => map (aeval env g) (vitems v)) (vgroups db v).

Lemma vgroups_with_items : forall db v i, vgroups db (with_items v i) = vgroups db v.
Proof. intros db v i. destruct v; reflexivity. Qed.

Lemma vitems_with_items : forall v i, vitems (with_items v i) = i.
Proof. intros v i. destruct v; reflexivity. Qed.

(** Two result rows agree everywhere except in column [j], where they are related. *)
Definition row_rel (r : vrel) (j : nat) (x y : list (option R)) : Prop :=
  exists pre u u' post,
    x = pre ++ u :: post /\ y = pre ++ u' :: post /\ List.length pre = j /\ rel_holds r u u'.
