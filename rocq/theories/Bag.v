(** Bag.v: multisets as lists, the SQL set operations on them, and bag inclusion.

    A query result is a bag of rows.  [bag_le l1 l2] says that every row occurs in
    [l1] at most as often as in [l2].  All mutation rules of ValScope are statements
    about this relation (set semantics) or about an order on values (value semantics). *)

From Coq Require Import List Arith Lia Permutation.
Import ListNotations.

Section Bag.
Context {A : Type} (dec : forall x y : A, {x = y} + {x <> y}).

Definition count (x : A) (l : list A) : nat := count_occ dec l x.

(** [bag_le l1 l2]: every element occurs in [l1] at most as often as in [l2]. *)
Definition bag_le (l1 l2 : list A) : Prop := forall x, count x l1 <= count x l2.

Lemma count_app : forall x l1 l2, count x (l1 ++ l2) = count x l1 + count x l2.
Proof. intros. unfold count. apply count_occ_app. Qed.

Lemma count_cons : forall x y l,
  count x (y :: l) = if dec y x then S (count x l) else count x l.
Proof. intros. unfold count. simpl. destruct (dec y x); reflexivity. Qed.

Lemma count_In : forall x l, In x l <-> count x l > 0.
Proof. intros. unfold count. apply count_occ_In. Qed.

Lemma bag_le_refl : forall l, bag_le l l.
Proof. intros l x. lia. Qed.

Lemma bag_le_trans : forall a b c, bag_le a b -> bag_le b c -> bag_le a c.
Proof. intros a b c H1 H2 x. specialize (H1 x). specialize (H2 x). lia. Qed.

Lemma bag_le_app : forall a a' b b', bag_le a a' -> bag_le b b' -> bag_le (a ++ b) (a' ++ b').
Proof.
  intros a a' b b' H1 H2 x. rewrite !count_app.
  specialize (H1 x). specialize (H2 x). lia.
Qed.

Lemma bag_le_nil_r : forall l, bag_le l [] -> l = [].
Proof.
  intros [|x l] H; [reflexivity|].
  specialize (H x). unfold count in H. simpl in H.
  destruct (dec x x) as [_|n]; [lia | exfalso; apply n; reflexivity].
Qed.

Lemma bag_le_in : forall l l' x, bag_le l l' -> In x l -> In x l'.
Proof.
  intros l l' x H Hin. apply count_In. apply count_In in Hin.
  specialize (H x). lia.
Qed.

Lemma bag_le_nonempty : forall l l', bag_le l l' -> l <> [] -> l' <> [].
Proof.
  intros l l' H Hne Heq. subst. apply Hne. apply bag_le_nil_r. exact H.
Qed.

(** A bag [l1] is below [l2] iff [l2] is a permutation of [l1] extended by some bag. *)
Lemma bag_le_perm : forall l1 l2,
  bag_le l1 l2 -> exists l, Permutation (l1 ++ l) l2.
Proof.
  induction l1 as [|x t IH]; intros l2 H.
  - exists l2. reflexivity.
  - assert (Hin : In x l2).
    { apply count_In. specialize (H x). rewrite count_cons in H.
      destruct (dec x x) as [_|n]; [lia | exfalso; apply n; reflexivity]. }
    destruct (in_split x l2 Hin) as [a [b ->]].
    assert (Hle : bag_le t (a ++ b)).
    { intro y. specialize (H y). rewrite count_cons in H.
      rewrite count_app, count_cons in H. rewrite count_app.
      destruct (dec x y); lia. }
    destruct (IH _ Hle) as [l Hl]. exists l. simpl.
    apply Permutation_trans with (x :: (a ++ b)).
    + apply perm_skip. exact Hl.
    + apply Permutation_middle.
Qed.

Lemma bag_le_of_perm : forall l1 l l2, Permutation (l1 ++ l) l2 -> bag_le l1 l2.
Proof.
  intros l1 l l2 P x.
  pose proof (proj1 (Permutation_count_occ dec _ _) P x) as E.
  unfold count. rewrite <- E. rewrite count_occ_app. lia.
Qed.

Lemma count_map_perm : forall (f : A -> A) l1 l2,
  bag_le l1 l2 -> bag_le (map f l1) (map f l2).
Proof.
  intros f l1 l2 H. destruct (bag_le_perm _ _ H) as [l Hl].
  apply bag_le_of_perm with (map f l).
  rewrite <- map_app. apply Permutation_map. exact Hl.
Qed.

Lemma Permutation_flat_map_A : forall (f : A -> list A) l l',
  Permutation l l' -> Permutation (flat_map f l) (flat_map f l').
Proof.
  intros f l l' P. induction P as [|x l l' _ IH|x y l|l l' l'' _ IH1 _ IH2]; simpl.
  - constructor.
  - apply Permutation_app_head. exact IH.
  - rewrite !app_assoc. apply Permutation_app_tail. apply Permutation_app_comm.
  - eapply Permutation_trans; eauto.
Qed.

(** [flat_map] is monotone in the list ... *)
Lemma bag_le_flat_map_list : forall (f : A -> list A) l1 l2,
  bag_le l1 l2 -> bag_le (flat_map f l1) (flat_map f l2).
Proof.
  intros f l1 l2 H. destruct (bag_le_perm _ _ H) as [l Hl].
  apply bag_le_of_perm with (flat_map f l).
  rewrite <- flat_map_app. apply Permutation_flat_map_A. exact Hl.
Qed.

(** ... and in the function. *)
Lemma bag_le_flat_map_fun : forall (f g : A -> list A) l,
  (forall x, bag_le (f x) (g x)) -> bag_le (flat_map f l) (flat_map g l).
Proof.
  intros f g l H. induction l as [|x l IH]; simpl.
  - apply bag_le_refl.
  - apply bag_le_app; auto.
Qed.

Lemma count_filter : forall (f : A -> bool) x l,
  count x (filter f l) = if f x then count x l else 0.
Proof.
  intros f x l. induction l as [|y l IH].
  - cbn [filter]. destruct (f x); reflexivity.
  - cbn [filter]. destruct (f y) eqn:Hfy.
    + rewrite !count_cons. destruct (dec y x) as [->|Hne].
      * rewrite IH, Hfy. reflexivity.
      * exact IH.
    + rewrite count_cons. destruct (dec y x) as [->|Hne].
      * rewrite IH, Hfy. reflexivity.
      * exact IH.
Qed.

Lemma bag_le_filter : forall (f g : A -> bool) l l',
  (forall x, f x = true -> g x = true) -> bag_le l l' ->
  bag_le (filter f l) (filter g l').
Proof.
  intros f g l l' Hfg H x. rewrite !count_filter. specialize (H x).
  destruct (f x) eqn:Hf.
  - rewrite (Hfg _ Hf). exact H.
  - lia.
Qed.

(** ---- SQL set operations (DISTINCT semantics) ---- *)

Definition dedup (l : list A) : list A := nodup dec l.
Definition union_all (l1 l2 : list A) : list A := l1 ++ l2.
Definition union (l1 l2 : list A) : list A := nodup dec (l1 ++ l2).
Definition inter (l1 l2 : list A) : list A :=
  filter (fun x => if in_dec dec x l2 then true else false) (nodup dec l1).
Definition exc (l1 l2 : list A) : list A :=
  filter (fun x => if in_dec dec x l2 then false else true) (nodup dec l1).

Lemma count_nodup : forall x l, count x (nodup dec l) = Nat.min 1 (count x l).
Proof.
  intros x l. induction l as [|y l IH]; [reflexivity|].
  simpl nodup. destruct (in_dec dec y l) as [Hin|Hnin].
  - rewrite IH, count_cons. destruct (dec y x) as [->|Hne].
    + apply count_In in Hin. lia.
    + reflexivity.
  - rewrite !count_cons. destruct (dec y x) as [->|Hne].
    + assert (count x l = 0).
      { destruct (count x l) eqn:E; [reflexivity|].
        exfalso. apply Hnin. apply count_In. lia. }
      rewrite IH. lia.
    + exact IH.
Qed.

Lemma dedup_le : forall l, bag_le (dedup l) l.
Proof. intros l x. unfold dedup. rewrite count_nodup. lia. Qed.

Lemma bag_le_dedup : forall l l', bag_le l l' -> bag_le (dedup l) (dedup l').
Proof.
  intros l l' H x. unfold dedup. rewrite !count_nodup. specialize (H x). lia.
Qed.

Lemma bag_le_union : forall a a' b b',
  bag_le a a' -> bag_le b b' -> bag_le (union a b) (union a' b').
Proof.
  intros a a' b b' H1 H2 x. unfold union. rewrite !count_nodup, !count_app.
  specialize (H1 x). specialize (H2 x). lia.
Qed.

Lemma union_le_union_all : forall a b, bag_le (union a b) (union_all a b).
Proof.
  intros a b x. unfold union, union_all. rewrite count_nodup. lia.
Qed.

Lemma bag_le_inter : forall a a' b b',
  bag_le a a' -> bag_le b b' -> bag_le (inter a b) (inter a' b').
Proof.
  intros a a' b b' H1 H2 x. unfold inter. rewrite !count_filter, !count_nodup.
  specialize (H1 x).
  destruct (in_dec dec x b) as [Hb|Hb]; destruct (in_dec dec x b') as [Hb'|Hb'].
  - lia.
  - exfalso. apply Hb'. eapply bag_le_in; eauto.
  - lia.
  - lia.
Qed.

Lemma inter_le_union : forall a b, bag_le (inter a b) (union a b).
Proof.
  intros a b x. unfold inter, union. rewrite count_filter, !count_nodup, count_app.
  destruct (in_dec dec x b) as [Hb|Hb].
  - apply count_In in Hb. lia.
  - lia.
Qed.

Lemma bag_le_exc_l : forall a a' b,
  bag_le a a' -> bag_le (exc a b) (exc a' b).
Proof.
  intros a a' b H x. unfold exc. rewrite !count_filter, !count_nodup.
  specialize (H x). destruct (in_dec dec x b); lia.
Qed.

(** [EXCEPT] is antitone in its right operand. *)
Lemma bag_le_exc_r : forall a b b',
  bag_le b b' -> bag_le (exc a b') (exc a b).
Proof.
  intros a b b' H x. unfold exc. rewrite !count_filter.
  destruct (in_dec dec x b) as [Hb|Hb]; destruct (in_dec dec x b') as [Hb'|Hb'].
  - lia.
  - exfalso. apply Hb'. eapply bag_le_in; eauto.
  - lia.
  - lia.
Qed.

Lemma exc_le_left : forall a b, bag_le (exc a b) a.
Proof.
  intros a b x. unfold exc. rewrite count_filter, count_nodup.
  destruct (in_dec dec x b); lia.
Qed.

End Bag.
