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

(** ---------------- DISTINCT on some arms of a UNION ALL ---------------- *)

(** Which parts of a UNION ALL of value queries are under DISTINCT: [MOne true] over an arm
    is [SELECT DISTINCT], over a UNION ALL of arms it is their [UNION]; [MOne false] is no
    DISTINCT, and [MUnion] follows the two operands of a UNION ALL.  A mask that does not
    follow the shape of the term means no DISTINCT. *)
Inductive mask : Type :=
  | MOne   : bool -> mask
  | MUnion : mask -> mask -> mask.

Fixpoint meval (env : venv) (db : db_t) (m : mask) (t : vtop) : list vrow :=
  match m, t with
  | MOne true, _ => distinct_rows (teval env db t)
  | MUnion ma mb, VUnionAll a b => meval env db ma a ++ meval env db mb b
  | _, _ => teval env db t
  end.

Lemma meval_in : forall env db m t x, In x (meval env db m t) -> In x (teval env db t).
Proof.
  intros env db m t. revert m. induction t as [v|a IHa b IHb]; intros m x H;
    destruct m as [[|]|ma mb]; simpl in *; try exact H; try (apply nodup_In in H; exact H).
  apply in_app_or in H as [H|H]; apply in_or_app; [left; exact (IHa _ _ H)|right; exact (IHb _ _ H)].
Qed.

Lemma covers_app : forall r j a a' b b', covers r j a a' -> covers r j b b' -> covers r j (a ++ b) (a' ++ b').
Proof.
  intros r j a a' b b' [A1 A2] [B1 B2]. split.
  - intros y Hy. apply in_app_or in Hy as [Hy|Hy].
    + destruct (A1 y Hy) as [x [Hx R]]. exists x. split; [apply in_or_app; left; exact Hx|exact R].
    + destruct (B1 y Hy) as [x [Hx R]]. exists x. split; [apply in_or_app; right; exact Hx|exact R].
  - intros x Hx. apply in_app_or in Hx as [Hx|Hx].
    + destruct (A2 x Hx) as [y [Hy R]]. exists y. split; [apply in_or_app; left; exact Hy|exact R].
    + destruct (B2 x Hx) as [y [Hy R]]. exists y. split; [apply in_or_app; right; exact Hy|exact R].
Qed.

Lemma covers_refl : forall r j l, (forall x, In x l -> j < List.length x) -> covers r j l l.
Proof.
  intros r j l H. split; intros z Hz; exists z; split; try exact Hz; apply row_rel_refl; apply H; exact Hz.
Qed.

(** The value mutator, with DISTINCT on any parts of the UNION ALL. *)
Theorem tmut_mask_sound : forall rs t m name r j t',
  In (name, (r, (j, t'))) (tmut rs t) ->
  forall env db, covers r j (meval env db m t) (meval env db m t').
Proof.
  intros rs t. induction t as [v|a IHa b IHb]; intros m name r j t' H env db.
  - pose proof (tmut_sound rs _ _ _ _ _ H env db) as F. simpl in H.
    apply in_map_iff in H as [[n0 [r0 [j0 v']]] [E Hin]]. simpl in E. inversion E; subst.
    destruct m as [[|]|ma mb]; simpl in *.
    + apply covers_distinct, forall2_covers. exact F.
    + apply forall2_covers. exact F.
    + apply forall2_covers. exact F.
  - pose proof (tmut_sound rs _ _ _ _ _ H env db) as F.
    destruct m as [[|]|ma mb].
    + simpl. apply covers_distinct, forall2_covers. exact F.
    + apply forall2_covers. exact F.
    + simpl in H.
      destruct (tarity a) as [na|] eqn:Ea; destruct (tarity b) as [nb|] eqn:Eb; simpl in H;
        rewrite ?Ea, ?Eb in H; try contradiction.
      destruct (Nat.eqb na nb) eqn:Enb; [|contradiction]. apply Nat.eqb_eq in Enb. subst nb.
      apply in_app_or in H as [H|H]; unfold tmap in H; apply in_map_iff in H as [[n0 [r0 [j0 x]]] [Em Hin]];
        simpl in Em; inversion Em; subst; simpl.
      * apply covers_app; [exact (IHa ma _ _ _ _ Hin env db)|].
        destruct (tmut_shape rs a _ _ _ _ Hin) as [n [Ha [_ Hj]]].
        assert (n = na) by congruence. subst n.
        apply covers_refl. intros row Hr. rewrite (teval_length env db b na row Eb (meval_in _ _ _ _ _ Hr)). exact Hj.
      * apply covers_app; [|exact (IHb mb _ _ _ _ Hin env db)].
        destruct (tmut_shape rs b _ _ _ _ Hin) as [n [Hb [_ Hj]]].
        assert (n = na) by congruence. subst n.
        apply covers_refl. intros row Hr. rewrite (teval_length env db a na row Ea (meval_in _ _ _ _ _ Hr)). exact Hj.
Qed.

(** When the mutation lies outside the DISTINCT parts (the parts under [MOne true] are the
    same term), the rows still correspond one to one: the stronger relation of
    [tmut_sound], which the checker then uses instead of the cover. *)
Fixpoint same_under (m : mask) (t t' : vtop) : Prop :=
  match m, t, t' with
  | MOne true, _, _ => t = t'
  | MUnion ma mb, VUnionAll a b, VUnionAll a' b' => same_under ma a a' /\ same_under mb b b'
  | _, _, _ => True
  end.

Lemma forall2_refl_meval : forall env db m t n r j, tarity t = Some n -> j < n ->
  Forall2 (row_rel r j) (meval env db m t) (meval env db m t).
Proof.
  intros env db m t n r j Ht Hj. apply forall2_refl_rows. intros row Hr.
  rewrite (teval_length env db t n row Ht (meval_in _ _ _ _ _ Hr)). exact Hj.
Qed.

Theorem tmut_mask_plain_sound : forall rs t m name r j t',
  In (name, (r, (j, t'))) (tmut rs t) -> same_under m t t' ->
  forall env db, Forall2 (row_rel r j) (meval env db m t) (meval env db m t').
Proof.
  intros rs t. induction t as [v|a IHa b IHb]; intros m name r j t' H S env db.
  - pose proof (tmut_sound rs _ _ _ _ _ H env db) as F.
    destruct (tmut_shape rs _ _ _ _ _ H) as [n [Ht [_ Hj]]].
    simpl in H. apply in_map_iff in H as [[n0 [r0 [j0 v']]] [E Hin]]. simpl in E. inversion E; subst.
    destruct m as [[|]|ma mb]; try exact F.
    simpl in S. rewrite <- S. exact (forall2_refl_meval env db (MOne true) (VOne v) n r j Ht Hj).
  - pose proof (tmut_sound rs _ _ _ _ _ H env db) as F.
    destruct (tmut_shape rs _ _ _ _ _ H) as [n [Ht [_ Hj]]].
    destruct m as [[|]|ma mb].
    + simpl in S. rewrite <- S. exact (forall2_refl_meval env db (MOne true) _ n r j Ht Hj).
    + exact F.
    + simpl in H.
      destruct (tarity a) as [na|] eqn:Ea; destruct (tarity b) as [nb|] eqn:Eb; simpl in H;
        rewrite ?Ea, ?Eb in H; try contradiction.
      destruct (Nat.eqb na nb) eqn:Enb; [|contradiction]. apply Nat.eqb_eq in Enb. subst nb.
      apply in_app_or in H as [H|H]; unfold tmap in H; apply in_map_iff in H as [[n0 [r0 [j0 x]]] [Em Hin]];
        simpl in Em; inversion Em; subst; simpl in S |- *; destruct S as [Sa Sb]; apply Forall2_app.
      * exact (IHa ma _ _ _ _ Hin Sa env db).
      * destruct (tmut_shape rs a _ _ _ _ Hin) as [k [Ha [_ Hk]]]. assert (k = na) by congruence. subst k.
        exact (forall2_refl_meval env db mb b na r j Eb Hk).
      * destruct (tmut_shape rs b _ _ _ _ Hin) as [k [Hb [_ Hk]]]. assert (k = na) by congruence. subst k.
        exact (forall2_refl_meval env db ma a na r j Ea Hk).
      * exact (IHb mb _ _ _ _ Hin Sb env db).
Qed.
