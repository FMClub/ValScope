(** VLineage.v: a mutated value followed through a derived table.

    [SELECT d.k, SUM(d.s) FROM (value query) AS d WHERE ... GROUP BY d.k HAVING ...]: the
    outer query reads the rows of the inner value query.  A value mutation of the inner
    query changes one column [j] of its rows, which stay in one-to-one correspondence
    ([tmut_sound]).  If the outer query uses column [j] in exactly one select item, and
    that item is the column itself or SUM / MIN / MAX / AVG of it (for a relation that
    is an order, [VLe] or [VGe]), and nowhere else (not in WHERE, the grouping keys,
    HAVING or another item), then the outer query forms the same groups and its rows
    correspond one to one, related in the column of that item.

    The outer WHERE and HAVING predicates and the other select items are opaque: arbitrary
    functions ([oenv]) of the columns they read. *)

From Coq Require Import List String Reals Lra Lia Bool Arith.
Import ListNotations.
From ValScope Require Import Bag Logic3 Pattern Syntax Semantics Rule Engine Value VEngine VHaving VUnion VDistinct.
Local Open Scope R_scope.

Definition getc (c : nat) (x : vrow) : option R := nth c x None.
Definition proj (cs : list nat) (x : vrow) : vrow := map (fun c => getc c x) cs.

Fixpoint somes (l : list (option R)) : list R :=
  match l with [] => [] | Some a :: t => a :: somes t | None :: t => somes t end.

(** The non-NULL values of column [c] in a group. *)
Definition colv (c : nat) (g : list vrow) : list R := somes (map (getc c) g).

Inductive oitem : Type :=
  | OCol    : nat -> oitem
  | OSum    : nat -> oitem
  | OMin    : nat -> oitem
  | OMax    : nat -> oitem
  | OAvg    : nat -> oitem
  | OCount  : nat -> oitem
  | OOpaque : nat -> list nat -> oitem.     (* an unanalysed item over the listed columns *)

Record oenv : Type := mk_oenv {
  ofilt : nat -> vrow -> bool;              (* the WHERE predicate, of the columns it reads *)
  ohav  : nat -> list vrow -> bool;         (* the HAVING predicate, of the group *)
  oagg  : nat -> list vrow -> option R      (* the opaque items, of the group *)
}.

(** SUM, MIN, MAX and AVG of the non-NULL values (NULL for none). *)
Definition agg_of (it : oitem) (l : list R) : option R :=
  match it with
  | OSum _ => match l with [] => None | _ => Some (rsum l) end
  | OMin _ => rmin l
  | OMax _ => rmax l
  | OAvg _ => match l with [] => None | _ => Some (mean l) end
  | _ => None
  end.

Definition oeval (oe : oenv) (g : list vrow) (it : oitem) : option R :=
  match it with
  | OCol c => match g with x :: _ => getc c x | [] => None end
  | OSum c | OMin c | OMax c | OAvg c => agg_of it (colv c g)
  | OCount c => Some (INR (List.length (colv c g)))
  | OOpaque n cs => oagg oe n (map (proj cs) g)
  end.

Inductive omode : Type :=
  | OProj                       (* no aggregation: every row is its own group *)
  | OGlobal                     (* aggregates without GROUP BY: one group *)
  | OGroup : list nat -> omode. (* GROUP BY the listed columns *)

Definition same_key (ks : list nat) (k : vrow) (x : vrow) : bool :=
  if vrow_eq_dec (proj ks x) k then true else false.

Definition ogroups (m : omode) (rows : list vrow) : list (list vrow) :=
  match m with
  | OProj => map (fun x => [x]) rows
  | OGlobal => [rows]
  | OGroup ks => map (fun k => filter (same_key ks k) rows) (nodup vrow_eq_dec (map (proj ks) rows))
  end.

Record outer : Type := mk_outer {
  o_mode  : omode;
  o_fid   : nat;  o_fcols : list nat;       (* WHERE: its number and the columns it reads *)
  o_hid   : nat;  o_hcols : list nat;       (* HAVING *)
  o_items : list oitem
}.

Definition weval (oe : oenv) (o : outer) (rows : list vrow) : list vrow :=
  map (fun g => map (oeval oe g) (o_items o))
      (filter (fun g => ohav oe (o_hid o) (map (proj (o_hcols o)) g))
              (ogroups (o_mode o) (filter (fun x => ofilt oe (o_fid o) (proj (o_fcols o) x)) rows))).

(** ---------------- which column is read where ---------------- *)

Definition has (j : nat) (cs : list nat) : bool := existsb (Nat.eqb j) cs.

Definition reads (it : oitem) (j : nat) : bool :=
  match it with
  | OCol c | OSum c | OMin c | OMax c | OAvg c | OCount c => Nat.eqb j c
  | OOpaque _ cs => has j cs
  end.

(** The item passes the relation of its column on. *)
Definition carries (r : vrel) (it : oitem) (j : nat) : bool :=
  match it with
  | OCol c => Nat.eqb j c
  | OSum c | OMin c | OMax c | OAvg c => Nat.eqb j c && is_mono r
  | _ => false
  end.

Definition mode_reads (m : omode) (j : nat) : bool :=
  match m with OGroup ks => has j ks | _ => false end.

(** The position of the only item that reads column [j], if it carries the relation. *)
Fixpoint target (r : vrel) (j : nat) (its : list oitem) : option nat :=
  match its with
  | [] => None
  | it :: t =>
      if reads it j
      then (if carries r it j && negb (existsb (fun x => reads x j) t) then Some 0%nat else None)
      else option_map S (target r j t)
  end.

Definition wcheck (r : vrel) (j : nat) (o : outer) : option nat :=
  if has j (o_fcols o) || has j (o_hcols o) || mode_reads (o_mode o) j then None
  else target r j (o_items o).

(** ---------------- rows related in column j ---------------- *)

Lemma getc_other : forall r j x y c, row_rel r j x y -> c <> j -> getc c x = getc c y.
Proof.
  intros r j x y c [pre [u [u' [post [Ex [Ey [Hl _]]]]]]] Hc. subst x y. unfold getc.
  destruct (lt_dec c (List.length pre)) as [Hlt|Hge].
  - rewrite !app_nth1 by exact Hlt. reflexivity.
  - rewrite !app_nth2 by lia. destruct (c - List.length pre)%nat as [|k] eqn:E; [lia|reflexivity].
Qed.

Lemma getc_at : forall r j x y, row_rel r j x y -> rel_holds r (getc j x) (getc j y).
Proof.
  intros r j x y [pre [u [u' [post [Ex [Ey [Hl Hr]]]]]]]. subst x y j. unfold getc.
  rewrite !app_nth2 by lia. rewrite Nat.sub_diag. exact Hr.
Qed.

Lemma has_false : forall j cs c, has j cs = false -> In c cs -> c <> j.
Proof.
  intros j cs c H Hin E. subst c. unfold has in H.
  assert (existsb (Nat.eqb j) cs = true) as K by (apply existsb_exists; exists j; split; [exact Hin|apply Nat.eqb_refl]).
  congruence.
Qed.

Lemma proj_other : forall r j x y cs, row_rel r j x y -> has j cs = false -> proj cs x = proj cs y.
Proof.
  intros r j x y cs H Hc. unfold proj. apply map_ext_in. intros c Hin.
  exact (getc_other r j x y c H (has_false j cs c Hc Hin)).
Qed.

Lemma projs_other : forall r j g g' cs, Forall2 (row_rel r j) g g' -> has j cs = false ->
  map (proj cs) g = map (proj cs) g'.
Proof.
  intros r j g g' cs H Hc. induction H as [|x y g g' Hxy H IH]; simpl; [reflexivity|].
  rewrite (proj_other r j x y cs Hxy Hc), IH. reflexivity.
Qed.

Lemma forall2_filter : forall {X : Type} (R : X -> X -> Prop) (f f' : X -> bool) l l',
  Forall2 R l l' -> (forall x y, R x y -> f x = f' y) -> Forall2 R (filter f l) (filter f' l').
Proof.
  intros X R f f' l l' H Hf. induction H as [|x y l l' Hxy H IH]; simpl; [constructor|].
  rewrite (Hf x y Hxy). destruct (f' y); [constructor; assumption|exact IH].
Qed.

Lemma forall2_map : forall {X Y : Type} (R : X -> X -> Prop) (S : Y -> Y -> Prop) (f f' : X -> Y) l l',
  Forall2 R l l' -> (forall x y, R x y -> S (f x) (f' y)) -> Forall2 S (map f l) (map f' l').
Proof.
  intros X Y R S f f' l l' H Hf. induction H as [|x y l l' Hxy H IH]; simpl; constructor; auto.
Qed.

Lemma forall2_map_same : forall {X Y : Type} (S : Y -> Y -> Prop) (f f' : X -> Y) l,
  (forall x, S (f x) (f' x)) -> Forall2 S (map f l) (map f' l).
Proof. intros X Y S f f' l H. induction l; simpl; constructor; auto. Qed.

Lemma ogroups_rel : forall r j m L L', Forall2 (row_rel r j) L L' -> mode_reads m j = false ->
  Forall2 (Forall2 (row_rel r j)) (ogroups m L) (ogroups m L').
Proof.
  intros r j m L L' H Hm. destruct m as [| |ks]; simpl.
  - apply (forall2_map (row_rel r j)); [exact H|]. intros x y Hxy. constructor; [exact Hxy|constructor].
  - constructor; [exact H|constructor].
  - simpl in Hm. rewrite (projs_other r j L L' ks H Hm).
    apply forall2_map_same. intros k. apply forall2_filter; [exact H|].
    intros x y Hxy. unfold same_key. rewrite (proj_other r j x y ks Hxy Hm). reflexivity.
Qed.

(** ---------------- the aggregates are monotone ---------------- *)

Lemma somes_rel : forall r l l', Forall2 (rel_holds r) l l' -> Forall2 (rel_R r) (somes l) (somes l').
Proof.
  intros r l l' H. induction H as [|x y l l' Hxy H IH]; simpl; [constructor|].
  destruct x as [a|], y as [b|]; simpl in Hxy; try contradiction; [constructor; assumption|exact IH].
Qed.

Lemma colv_rel : forall r j g g', Forall2 (row_rel r j) g g' -> Forall2 (rel_R r) (colv j g) (colv j g').
Proof.
  intros r j g g' H. unfold colv. apply somes_rel.
  apply (forall2_map (row_rel r j)); [exact H|]. intros x y Hxy. exact (getc_at r j x y Hxy).
Qed.

Lemma colv_other : forall r j g g' c, Forall2 (row_rel r j) g g' -> c <> j -> colv c g = colv c g'.
Proof.
  intros r j g g' c H Hc. unfold colv. f_equal.
  induction H as [|x y g g' Hxy H IH]; simpl; [reflexivity|].
  rewrite (getc_other r j x y c Hxy Hc), IH. reflexivity.
Qed.

Lemma rsum_le2 : forall l l', Forall2 Rle l l' -> rsum l <= rsum l'.
Proof. intros l l' H. induction H; simpl; lra. Qed.

Lemma fold_min_le2 : forall t t' x x', Forall2 Rle t t' -> x <= x' ->
  fold_right Rmin x t <= fold_right Rmin x' t'.
Proof.
  intros t t' x x' H Hx. induction H as [|a b t t' Hab H IH]; simpl; [exact Hx|].
  apply Rmin_glb; [eapply Rle_trans; [apply Rmin_l|exact Hab]|eapply Rle_trans; [apply Rmin_r|exact IH]].
Qed.

Lemma fold_max_le2 : forall t t' x x', Forall2 Rle t t' -> x <= x' ->
  fold_right Rmax x t <= fold_right Rmax x' t'.
Proof.
  intros t t' x x' H Hx. induction H as [|a b t t' Hab H IH]; simpl; [exact Hx|].
  apply Rmax_lub; [eapply Rle_trans; [exact Hab|apply Rmax_l]|eapply Rle_trans; [exact IH|apply Rmax_r]].
Qed.

Lemma mean_le2 : forall l l', Forall2 Rle l l' -> l <> [] -> mean l <= mean l'.
Proof.
  intros l l' H Hn. unfold mean, rlen. rewrite <- (Forall2_length H).
  assert (0 < INR (List.length l)) as Hp.
  { apply lt_0_INR. destruct l; [contradiction|simpl; lia]. }
  unfold Rdiv. apply Rmult_le_compat_r; [left; apply Rinv_0_lt_compat; exact Hp|apply rsum_le2; exact H].
Qed.

Lemma agg_le : forall it l l', Forall2 Rle l l' ->
  match agg_of it l, agg_of it l' with
  | None, None => True
  | Some a, Some b => a <= b
  | _, _ => False
  end.
Proof.
  intros it l l' H. destruct it; simpl; try exact I; inversion H as [|a b t t' Hab Ht]; subst; try exact I.
  - simpl. pose proof (rsum_le2 t t' Ht). lra.
  - simpl. apply fold_min_le2; assumption.
  - simpl. apply fold_max_le2; assumption.
  - apply mean_le2; [exact H|discriminate].
Qed.

Lemma forall2_flip : forall {X : Type} (R : X -> X -> Prop) l l',
  Forall2 (fun a b => R b a) l l' -> Forall2 R l' l.
Proof. intros X R l l' H. induction H; constructor; assumption. Qed.

Lemma agg_rel : forall r it l l', is_mono r = true -> Forall2 (rel_R r) l l' ->
  rel_holds r (agg_of it l) (agg_of it l').
Proof.
  intros r it l l' Hm H. destruct r; simpl in Hm; try discriminate.
  - pose proof (agg_le it l l' H) as K. unfold rel_holds.
    destruct (agg_of it l), (agg_of it l'); simpl; exact K.
  - pose proof (agg_le it l' l (forall2_flip Rle l l' H)) as K. unfold rel_holds.
    destruct (agg_of it l), (agg_of it l'); simpl; try exact K; contradiction.
Qed.

(** ---------------- one output row ---------------- *)

Lemma oeval_other : forall oe r j g g' it, Forall2 (row_rel r j) g g' -> reads it j = false ->
  oeval oe g it = oeval oe g' it.
Proof.
  intros oe r j g g' it H Hr.
  destruct it as [c|c|c|c|c|c|n cs]; simpl in Hr |- *;
    try (apply Nat.eqb_neq in Hr; rewrite (colv_other r j g g' c H (not_eq_sym Hr)); reflexivity).
  - apply Nat.eqb_neq in Hr. inversion H as [|x y t t' Hxy Ht]; subst; [reflexivity|].
    exact (getc_other r j x y c Hxy (not_eq_sym Hr)).
  - rewrite (projs_other r j g g' cs H Hr). reflexivity.
Qed.

Lemma oeval_carries : forall oe r j g g' it, Forall2 (row_rel r j) g g' -> carries r it j = true ->
  rel_holds r (oeval oe g it) (oeval oe g' it).
Proof.
  intros oe r j g g' it H Hc.
  destruct it as [c|c|c|c|c|c|n cs]; simpl in Hc; try discriminate.
  - apply Nat.eqb_eq in Hc. subst c. simpl. inversion H as [|x y t t' Hxy Ht]; subst; [exact I|].
    exact (getc_at r j x y Hxy).
  - apply andb_prop in Hc as [Hc Hm]. apply Nat.eqb_eq in Hc. subst c.
    exact (agg_rel r (OSum j) _ _ Hm (colv_rel r j g g' H)).
  - apply andb_prop in Hc as [Hc Hm]. apply Nat.eqb_eq in Hc. subst c.
    exact (agg_rel r (OMin j) _ _ Hm (colv_rel r j g g' H)).
  - apply andb_prop in Hc as [Hc Hm]. apply Nat.eqb_eq in Hc. subst c.
    exact (agg_rel r (OMax j) _ _ Hm (colv_rel r j g g' H)).
  - apply andb_prop in Hc as [Hc Hm]. apply Nat.eqb_eq in Hc. subst c.
    exact (agg_rel r (OAvg j) _ _ Hm (colv_rel r j g g' H)).
Qed.

Lemma items_other : forall oe r j g g' its, Forall2 (row_rel r j) g g' ->
  existsb (fun x => reads x j) its = false -> map (oeval oe g) its = map (oeval oe g') its.
Proof.
  intros oe r j g g' its H He. induction its as [|it t IH]; simpl; [reflexivity|].
  simpl in He. apply orb_false_elim in He as [H1 H2].
  rewrite (oeval_other oe r j g g' it H H1), (IH H2). reflexivity.
Qed.

Lemma items_rel : forall oe r j g g' its i, Forall2 (row_rel r j) g g' -> target r j its = Some i ->
  row_rel r i (map (oeval oe g) its) (map (oeval oe g') its).
Proof.
  intros oe r j g g' its. induction its as [|it t IH]; intros i H Ht; simpl in Ht; [discriminate|].
  destruct (reads it j) eqn:Er.
  - destruct (carries r it j) eqn:Ec; simpl in Ht; [|discriminate].
    destruct (existsb (fun x => reads x j) t) eqn:Ee; simpl in Ht; [discriminate|]. inversion Ht; subst i.
    exists [], (oeval oe g it), (oeval oe g' it), (map (oeval oe g) t). simpl.
    repeat split; try reflexivity.
    + rewrite (items_other oe r j g g' t H Ee). reflexivity.
    + exact (oeval_carries oe r j g g' it H Ec).
  - destruct (target r j t) as [k|] eqn:Ek; simpl in Ht; [|discriminate]. inversion Ht; subst i.
    destruct (IH k H eq_refl) as [pre [u [u' [post [Ex [Ey [Hl Hr]]]]]]].
    exists (oeval oe g it :: pre), u, u', post. simpl.
    rewrite Ex, Ey, (oeval_other oe r j g g' it H Er). repeat split; try reflexivity; [lia|exact Hr].
Qed.

(** ---------------- the outer query ---------------- *)

Theorem weval_sound : forall oe o r j i L L',
  Forall2 (row_rel r j) L L' -> wcheck r j o = Some i ->
  Forall2 (row_rel r i) (weval oe o L) (weval oe o L').
Proof.
  intros oe o r j i L L' H Hc. unfold wcheck in Hc.
  destruct (has j (o_fcols o)) eqn:Ef; simpl in Hc; [discriminate|].
  destruct (has j (o_hcols o)) eqn:Eh; simpl in Hc; [discriminate|].
  destruct (mode_reads (o_mode o) j) eqn:Em; [discriminate|].
  unfold weval.
  apply (forall2_map (Forall2 (row_rel r j))).
  - apply forall2_filter.
    + apply ogroups_rel; [|exact Em]. apply forall2_filter; [exact H|].
      intros x y Hxy. rewrite (proj_other r j x y _ Hxy Ef). reflexivity.
    + intros g g' Hg. rewrite (projs_other r j g g' _ Hg Eh). reflexivity.
  - intros g g' Hg. exact (items_rel oe r j g g' _ i Hg Hc).
Qed.

(** ---------------- the mutator ---------------- *)

Inductive wtop : Type := W : outer -> vtop -> wtop.

Definition wteval (oe : oenv) (env : venv) (db : db_t) (w : wtop) : list vrow :=
  match w with W o t => weval oe o (teval env db t) end.

Section WEngine.
Variable rs : list vrule.

Definition wmut (w : wtop) : list (string * (vrel * (nat * wtop))) :=
  match w with
  | W o t =>
      flat_map (fun m =>
        match wcheck (fst (snd m)) (fst (snd (snd m))) o with
        | Some i => [(fst m, (fst (snd m), (i, W o (snd (snd (snd m))))))]
        | None => []
        end) (tmut rs t)
  end.

Theorem wmut_sound : forall w name r i w',
  In (name, (r, (i, w'))) (wmut w) ->
  forall oe env db, Forall2 (row_rel r i) (wteval oe env db w) (wteval oe env db w').
Proof.
  intros [o t] name r i w' H oe env db. simpl in H.
  apply in_flat_map in H as [[n0 [r0 [j t']]] [Hin Hm]]. simpl in Hm.
  destruct (wcheck r0 j o) as [k|] eqn:Ec; [|contradiction].
  destruct Hm as [E|[]]. inversion E; subst. simpl.
  exact (weval_sound oe o r j i _ _ (tmut_sound rs t _ _ _ _ Hin env db) Ec).
Qed.

End WEngine.
