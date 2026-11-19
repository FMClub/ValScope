(** Value.v: the value-semantic layer.

    A value-semantic mutation changes one select item of a query and leaves the set
    of rows alone.  The result rows of the original and the mutant then correspond
    one to one, and the mutated column is related by a VALUE RELATION.

    Select items are aggregate expressions ([aexpr]) evaluated on a group of rows.
    Aggregates follow SQL: COUNT counts the non-NULL values of any type; COUNT
    DISTINCT counts them modulo the collation of the world; SUM, MIN, MAX, AVG,
    VAR_SAMP and STDDEV_SAMP work on the numeric values (integers and rationals, so
    DECIMAL and every finite FLOAT / DOUBLE) and are NULL when there are none.
    Results are real numbers.

    Several rules of ValScope only hold under a condition on the data (sign,
    below/above 1).  Instead of a precondition, each rule states an unconditional
    relation that mentions the original value:
      - [VLe]        : the value does not decrease
      - [VGe]        : the value does not increase
      - [VAwayZero]  : a non-negative value does not decrease, a non-positive one
                       does not increase                    (v -> v * k, k >= 1)
      - [VTowardOne] : a value <= 1 does not decrease, a value >= 1 does not
                       increase                             (v -> sqrt v)
      - [VAwayOne]   : the converse                         (s -> s * s) *)

From Coq Require Import List ZArith QArith Qreals Reals Lra Lia.
Import ListNotations.
From ValScope Require Import Bag Logic3 Pattern Syntax Semantics.
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

(** ---------------- aggregates ---------------- *)

(** The numeric value of a value as a real number. *)
Definition num (v : value) : option R := option_map Q2R (numq v).

Fixpoint nums (vs : list value) : list R :=
  match vs with
  | [] => []
  | v :: t => match num v with Some x => x :: nums t | None => nums t end
  end.

Definition vals (db : db_t) (e : expr) (g : list row) : list value :=
  map (fun r => eval_expr db r e) g.

(** The numeric values of [e] over the rows of a group. *)
Definition col (db : db_t) (e : expr) (g : list row) : list R := nums (vals db e g).

Definition nonnull (vs : list value) : list value :=
  filter (fun v => match v with VNull => false | _ => true end) vs.

Definition rsum (l : list R) : R := fold_right Rplus 0 l.
Definition rmax (l : list R) : option R := match l with [] => None | x :: t => Some (fold_right Rmax x t) end.
Definition rmin (l : list R) : option R := match l with [] => None | x :: t => Some (fold_right Rmin x t) end.
Definition rlen (l : list R) : R := INR (length l).
Definition mean (l : list R) : R := rsum l / rlen l.

Fixpoint sumsq (m : R) (l : list R) : R :=
  match l with [] => 0 | x :: t => (x - m) * (x - m) + sumsq m t end.

(** Sample variance; NULL for fewer than two values, as in MySQL. *)
Definition var_samp (l : list R) : option R :=
  if (2 <=? length l)%nat then Some (sumsq (mean l) l / (rlen l - 1)) else None.

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
  | AMono    : nat -> aexpr -> aexpr  (* a monotone (non-decreasing) scalar function *)
  | AOpaque  : nat -> aexpr.         (* an item that is not analysed (VAR_POP, GROUP_CONCAT, ...) *)

(** Interpretation of the monotone function symbols, and of the operands of a
    HAVING clause ([hrow g] gives their values for the group [g]; it is an arbitrary
    function of the group, so the HAVING theorems hold whatever the aggregates in it
    are). *)
Record venv : Type := mk_venv {
  mfn : nat -> R -> R;
  mfn_mono : forall n x y, x <= y -> mfn n x <= mfn n y;
  hrow : list row -> row;
  magg : nat -> list row -> option R   (* the values of the opaque items, per group *)
}.

Fixpoint aeval (env : venv) (db : db_t) (g : list row) (a : aexpr) : option R :=
  match a with
  | ACol e => match g with r :: _ => num (eval_expr db r e) | [] => None end
  | AConst k => Some (IZR k)
  | ACount e => Some (INR (length (nonnull (vals db e g))))
  | ACountD e => Some (INR (length (dedup (veq db) (nonnull (vals db e g)))))
  | ASum e => match col db e g with [] => None | l => Some (rsum l) end
  | AMin e => rmin (col db e g)
  | AMax e => rmax (col db e g)
  | AAvg e => match col db e g with [] => None | l => Some (mean l) end
  | AVarSamp e => var_samp (col db e g)
  | AStdSamp e => match var_samp (col db e g) with Some v => Some (sqrt v) | None => None end
  | AAdd a b => olift2 Rplus (aeval env db g a) (aeval env db g b)
  | AMul a b => olift2 Rmult (aeval env db g a) (aeval env db g b)
  | AMono f a => match aeval env db g a with Some x => Some (mfn env f x) | None => None end
  | AOpaque n => magg env n g
  end.

(** ---------------- facts about the aggregates ---------------- *)

Lemma max_ge : forall t x y, In y (x :: t) -> y <= fold_right Rmax x t.
Proof.
  induction t as [|z t IH]; intros x y H; simpl in *.
  - destruct H as [->|[]]. lra.
  - destruct H as [->|[->|H]].
    + specialize (IH y y (or_introl eq_refl)). eapply Rle_trans; [exact IH|apply Rmax_r].
    + apply Rmax_l.
    + specialize (IH x y (or_intror H)). eapply Rle_trans; [exact IH|apply Rmax_r].
Qed.

Lemma min_le : forall t x y, In y (x :: t) -> fold_right Rmin x t <= y.
Proof.
  induction t as [|z t IH]; intros x y H; simpl in *.
  - destruct H as [->|[]]. lra.
  - destruct H as [->|[->|H]].
    + specialize (IH y y (or_introl eq_refl)). eapply Rle_trans; [apply Rmin_r|exact IH].
    + apply Rmin_l.
    + specialize (IH x y (or_intror H)). eapply Rle_trans; [apply Rmin_r|exact IH].
Qed.

Lemma rsum_le : forall l m, (forall y, In y l -> y <= m) -> rsum l <= rlen l * m.
Proof.
  induction l as [|x l IH]; intros m H; unfold rlen in *; simpl.
  - lra.
  - assert (x <= m) by (apply H; left; reflexivity).
    assert (rsum l <= INR (length l) * m) by (apply IH; intros; apply H; right; assumption).
    destruct (length l); simpl in *; lra.
Qed.

Lemma dedup_length : forall {A : Type} (eqb : A -> A -> bool) (l : list A),
  (length (dedup eqb l) <= length l)%nat.
Proof.
  intros A eqb l. induction l as [|x l IH]; simpl; [lia|].
  destruct (existsb (eqb x) l); simpl; lia.
Qed.

Lemma sumsq_nonneg : forall m l, 0 <= sumsq m l.
Proof.
  induction l as [|x l IH]; simpl; [lra|].
  assert (0 <= (x - m) * (x - m)) by apply Rle_0_sqr. lra.
Qed.

Lemma var_samp_nonneg : forall l v, var_samp l = Some v -> 0 <= v.
Proof.
  intros l v H. unfold var_samp in H.
  destruct (2 <=? length l)%nat eqn:E; [|discriminate].
  inversion H; subst. apply Nat.leb_le in E.
  unfold Rdiv. apply Rmult_le_pos; [apply sumsq_nonneg|].
  left. apply Rinv_0_lt_compat. unfold rlen.
  assert (1 < INR (length l)) by (apply lt_1_INR; lia). lra.
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

(** Scaling a column scales its numeric values (rule 23). *)
Lemma col_scale : forall db e k g,
  col db (EMul e (EConst (VInt k))) g = map (fun x => x * IZR k) (col db e g).
Proof.
  intros db e k g. unfold col, vals.
  change (fun r => eval_expr db r (EMul e (EConst (VInt k))))
    with (fun r => vmul db (eval_expr db r e) (VInt k)).
  induction g as [|r g IH]; [reflexivity|]. cbn [map nums].
  pose proof (vmul_num db (eval_expr db r e) k) as L. unfold num.
  destruct (numq (vmul db (eval_expr db r e) (VInt k))) as [a|];
    destruct (numq (eval_expr db r e)) as [b|]; try contradiction; cbn [option_map map];
    unfold num in IH; rewrite IH; [|reflexivity].
  apply Qeq_eqR in L. rewrite L, Q2R_mult. unfold Q2R at 2. simpl. f_equal. f_equal. field.
Qed.

Lemma rsum_scale : forall k l, rsum (map (fun x => x * k) l) = rsum l * k.
Proof. intros k l. induction l as [|x l IH]; unfold rsum in *; simpl; [lra|]. rewrite IH. lra. Qed.

(** ---------------- monotone contexts ---------------- *)

Lemma ctx_add_l : forall r u u' w, is_mono r = true ->
  rel_holds r u u' -> rel_holds r (olift2 Rplus u w) (olift2 Rplus u' w).
Proof. intros r u u' w Hm H. destruct r; try discriminate; destruct u, u', w; simpl in *; try tauto; lra. Qed.

Lemma ctx_add_r : forall r u u' w, is_mono r = true ->
  rel_holds r u u' -> rel_holds r (olift2 Rplus w u) (olift2 Rplus w u').
Proof. intros r u u' w Hm H. destruct r; try discriminate; destruct u, u', w; simpl in *; try tauto; lra. Qed.

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
    - [VGroup]  : GROUP BY keys, with a HAVING predicate ([PTrue] when absent);
    - [VGlobal] : aggregates without GROUP BY (one group, even on empty input). *)
Inductive vquery : Type :=
  | VProj   : list aexpr -> query -> vquery
  | VGroup  : list expr -> list aexpr -> pred -> query -> vquery
  | VGlobal : list aexpr -> pred -> query -> vquery.

Definition vitems (v : vquery) : list aexpr :=
  match v with VProj i _ | VGroup _ i _ _ | VGlobal i _ _ => i end.

Definition with_items (v : vquery) (i : list aexpr) : vquery :=
  match v with
  | VProj _ q => VProj i q
  | VGroup k _ h q => VGroup k i h q
  | VGlobal _ h q => VGlobal i h q
  end.

Definition with_having (v : vquery) (h : pred) : vquery :=
  match v with
  | VProj i q => VProj i q
  | VGroup k i _ q => VGroup k i h q
  | VGlobal i _ q => VGlobal i h q
  end.

Definition key_of (db : db_t) (keys : list expr) (r : row) : row :=
  map (eval_expr db r) keys.

(** All groups, before HAVING.  Grouping uses the collation of the world.  The groups
    depend neither on the select items nor on the HAVING predicate. *)
Definition all_groups (db : db_t) (v : vquery) : list (list row) :=
  match v with
  | VProj _ q => map (fun r => [r]) (eval_q db [] q)
  | VGroup keys _ _ q =>
      let rows := eval_q db [] q in
      map (fun k => filter (fun r => req db (key_of db keys r) k) rows)
          (dedup (req db) (map (key_of db keys) rows))
  | VGlobal _ _ q => [eval_q db [] q]
  end.

Definition vhaving (v : vquery) : pred :=
  match v with VProj _ _ => PTrue | VGroup _ _ h _ | VGlobal _ h _ => h end.

(** Does the group pass the HAVING predicate? *)
Definition keep (env : venv) (db : db_t) (h : pred) (g : list row) : bool :=
  is_true (eval_p db (hrow env g) h).

(** The groups that are output. *)
Definition vgroups (env : venv) (db : db_t) (v : vquery) : list (list row) :=
  filter (keep env db (vhaving v)) (all_groups db v).

Definition veval (env : venv) (db : db_t) (v : vquery) : list (list (option R)) :=
  map (fun g => map (aeval env db g) (vitems v)) (vgroups env db v).

Lemma vgroups_with_items : forall env db v i, vgroups env db (with_items v i) = vgroups env db v.
Proof. intros env db v i. destruct v; reflexivity. Qed.

Lemma vitems_with_items : forall v i, vitems (with_items v i) = i.
Proof. intros v i. destruct v; reflexivity. Qed.

(** Two result rows agree everywhere except in column [j], where they are related. *)
Definition row_rel (r : vrel) (j : nat) (x y : list (option R)) : Prop :=
  exists pre u u' post,
    x = pre ++ u :: post /\ y = pre ++ u' :: post /\ List.length pre = j /\ rel_holds r u u'.

(** ---------------- HAVING ---------------- *)

(** [Sub l l']: [l] is obtained from [l'] by deleting elements.  Mutating HAVING
    changes which groups are output; the rows of the groups that stay are the same. *)
Inductive Sub {X : Type} : list X -> list X -> Prop :=
  | Sub_nil : Sub [] []
  | Sub_keep : forall x l l', Sub l l' -> Sub (x :: l) (x :: l')
  | Sub_skip : forall x l l', Sub l l' -> Sub l (x :: l').

Lemma sub_filter : forall {X : Type} (P P' : X -> bool) l,
  (forall x, P x = true -> P' x = true) -> Sub (filter P l) (filter P' l).
Proof.
  intros X P P' l H. induction l as [|x l IH]; simpl; [constructor|].
  destruct (P x) eqn:E.
  - rewrite (H x E). constructor. exact IH.
  - destruct (P' x); [constructor|]; exact IH.
Qed.

Lemma sub_map : forall {X Y : Type} (f : X -> Y) l l', Sub l l' -> Sub (map f l) (map f l').
Proof. intros X Y f l l' H. induction H; simpl; constructor; assumption. Qed.

(** [v_sub v v']: on every world the result of [v] is a sub-list of the result of [v']. *)
Definition v_sub (v v' : vquery) : Prop :=
  forall env db, Sub (veval env db v) (veval env db v').

Lemma all_groups_with_having : forall db v h, all_groups db (with_having v h) = all_groups db v.
Proof. intros db v h. destruct v; reflexivity. Qed.

Lemma vitems_with_having : forall v h, vitems (with_having v h) = vitems v.
Proof. intros v h. destruct v; reflexivity. Qed.

(** A weaker HAVING predicate keeps more groups. *)
Lemma having_mono : forall v h h', vhaving v = h -> vhaving (with_having v h') = h' ->
  p_le h h' -> v_sub v (with_having v h').
Proof.
  intros v h h' E E' H env db. unfold veval, vgroups.
  rewrite all_groups_with_having, vitems_with_having, E, E'.
  apply sub_map. apply sub_filter. intros g Hg. unfold keep in *.
  exact (is_true_mono _ _ (H db (hrow env g)) Hg).
Qed.

Lemma having_anti : forall v h h', vhaving v = h -> vhaving (with_having v h') = h' ->
  p_le h' h -> v_sub (with_having v h') v.
Proof.
  intros v h h' E E' H env db. unfold veval, vgroups.
  rewrite all_groups_with_having, vitems_with_having, E, E'.
  apply sub_map. apply sub_filter. intros g Hg. unfold keep in *.
  exact (is_true_mono _ _ (H db (hrow env g)) Hg).
Qed.
