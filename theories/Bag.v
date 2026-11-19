(** Bag.v: multisets as lists, modulo an equivalence, with the SQL set operations.

    A query result is a bag of rows.  Two rows that are equal under the collation of
    the database (for example 'a' and 'A' under a case-insensitive collation) are
    interchangeable: DISTINCT and the set operations keep one representative, and SQL
    does not say which one.  So results are compared modulo an equivalence [eqb]:
    [bag_le l1 l2] says that every equivalence class occurs in [l1] at most as often as
    in [l2].  With [eqb] = syntactic equality this is ordinary bag inclusion.

    [dedup] keeps the last element of each class; any other choice of representatives
    has the same class counts, so every statement here holds for every choice. *)

From Coq Require Import List Arith Lia Bool.
Import ListNotations.

Section Bag.
Context {A : Type} (eqb : A -> A -> bool).
Hypothesis eqb_refl : forall x, eqb x x = true.
Hypothesis eqb_sym : forall x y, eqb x y = true -> eqb y x = true.
Hypothesis eqb_trans : forall x y z, eqb x y = true -> eqb y z = true -> eqb x z = true.

Definition ind (b : bool) : nat := if b then 1 else 0.

(** Number of elements of [l] equivalent to [x]. *)
Fixpoint count (x : A) (l : list A) : nat :=
  match l with [] => 0 | y :: t => ind (eqb x y) + count x t end.

Definition bag_le (l1 l2 : list A) : Prop := forall x, count x l1 <= count x l2.
Definition bag_eq (l1 l2 : list A) : Prop := bag_le l1 l2 /\ bag_le l2 l1.

Lemma eqb_swap : forall x y z, eqb x y = true -> eqb z x = eqb z y.
Proof.
  intros x y z H. destruct (eqb z x) eqn:E1; destruct (eqb z y) eqn:E2; try reflexivity.
  - rewrite (eqb_trans _ _ _ E1 H) in E2. discriminate.
  - rewrite (eqb_trans _ _ _ E2 (eqb_sym _ _ H)) in E1. discriminate.
Qed.

Lemma count_app : forall x l1 l2, count x (l1 ++ l2) = count x l1 + count x l2.
Proof. intros x l1 l2. induction l1 as [|y t IH]; simpl; [reflexivity|]. rewrite IH. lia. Qed.

Lemma count_compat : forall x y l, eqb x y = true -> count x l = count y l.
Proof.
  intros x y l H. induction l as [|z t IH]; simpl; [reflexivity|].
  rewrite IH. f_equal. unfold ind.
  destruct (eqb x z) eqn:E1; destruct (eqb y z) eqn:E2; try reflexivity.
  - rewrite (eqb_trans _ _ _ (eqb_sym _ _ H) E1) in E2. discriminate.
  - rewrite (eqb_trans _ _ _ H E2) in E1. discriminate.
Qed.

Lemma count_pos : forall x l, count x l > 0 <-> exists y, In y l /\ eqb x y = true.
Proof.
  intros x l. induction l as [|y t IH]; simpl.
  - split; [lia|]. intros [y [[] _]].
  - unfold ind. destruct (eqb x y) eqn:E; split.
    + intros _. exists y. split; [left; reflexivity|exact E].
    + intros _. lia.
    + intros H. destruct (proj1 IH ltac:(lia)) as [z [Hz Ez]]. exists z. split; [right; exact Hz|exact Ez].
    + intros [z [[->|Hz] Ez]]; [congruence|]. simpl. apply IH. exists z. split; assumption.
Qed.

Lemma existsb_count : forall x l, existsb (eqb x) l = true <-> count x l > 0.
Proof.
  intros x l. rewrite existsb_exists, count_pos. reflexivity.
Qed.

Lemma bag_le_refl : forall l, bag_le l l.
Proof. intros l x. lia. Qed.

Lemma bag_le_trans : forall a b c, bag_le a b -> bag_le b c -> bag_le a c.
Proof. intros a b c H1 H2 x. specialize (H1 x). specialize (H2 x). lia. Qed.

Lemma bag_eq_refl : forall l, bag_eq l l.
Proof. intros l. split; apply bag_le_refl. Qed.

Lemma bag_le_app : forall a a' b b', bag_le a a' -> bag_le b b' -> bag_le (a ++ b) (a' ++ b').
Proof. intros a a' b b' H1 H2 x. rewrite !count_app. specialize (H1 x). specialize (H2 x). lia. Qed.

Lemma bag_le_nil_l : forall l, bag_le [] l.
Proof. intros l x. simpl. lia. Qed.

Lemma bag_le_nil_r : forall l, bag_le l [] -> l = [].
Proof.
  intros [|x l] H; [reflexivity|]. specialize (H x). simpl in H.
  rewrite eqb_refl in H. simpl in H. lia.
Qed.

Lemma bag_le_nonempty : forall l l', bag_le l l' -> l <> [] -> l' <> [].
Proof. intros l l' H Hne Heq. subst. apply Hne. apply bag_le_nil_r. exact H. Qed.

(** An element of the smaller bag has an equivalent element in the larger one. *)
Lemma bag_le_in : forall l l' x, bag_le l l' -> In x l -> exists y, In y l' /\ eqb x y = true.
Proof.
  intros l l' x H Hin. apply count_pos. specialize (H x).
  assert (count x l > 0) by (apply count_pos; exists x; split; [exact Hin|apply eqb_refl]). lia.
Qed.

(** ---------------- sums over a bag ---------------- *)

Fixpoint sumf (g : A -> nat) (l : list A) : nat :=
  match l with [] => 0 | x :: t => g x + sumf g t end.

Definition ncompat (g : A -> nat) : Prop := forall x y, eqb x y = true -> g x = g y.

Lemma sumf_app : forall g l1 l2, sumf g (l1 ++ l2) = sumf g l1 + sumf g l2.
Proof. intros g l1 l2. induction l1 as [|x t IH]; simpl; [reflexivity|]. rewrite IH. lia. Qed.

Lemma count_sumf : forall x l, count x l = sumf (fun y => ind (eqb x y)) l.
Proof. intros x l. induction l as [|y t IH]; simpl; [reflexivity|]. rewrite IH. reflexivity. Qed.

(** Remove one element equivalent to [x]. *)
Lemma extract : forall x l, count x l > 0 ->
  exists y l', eqb x y = true /\ (forall g, sumf g l = g y + sumf g l').
Proof.
  intros x l. induction l as [|z t IH]; simpl; intros H; [lia|].
  unfold ind in H. destruct (eqb x z) eqn:E.
  - exists z, t. split; [exact E|]. intros g. reflexivity.
  - destruct (IH ltac:(simpl in H; lia)) as [y [l' [Ey Hs]]].
    exists y, (z :: l'). split; [exact Ey|]. intros g. simpl. rewrite Hs. lia.
Qed.

(** The key lemma: a compatible function summed over a bag is monotone in the bag. *)
Lemma sumf_mono : forall g l1 l2, ncompat g -> bag_le l1 l2 -> sumf g l1 <= sumf g l2.
Proof.
  intros g l1. induction l1 as [|x t IH]; intros l2 Hg H; simpl; [lia|].
  assert (Hx : count x l2 > 0).
  { specialize (H x). simpl in H. rewrite eqb_refl in H. simpl in H. lia. }
  destruct (extract x l2 Hx) as [y [l2' [Exy Hs]]].
  assert (Ht : bag_le t l2').
  { intro z. specialize (H z). simpl in H. rewrite !count_sumf in *.
    rewrite (Hs (fun w => ind (eqb z w))) in H.
    rewrite (eqb_swap _ _ z Exy) in H. lia. }
  specialize (IH l2' Hg Ht). rewrite (Hs g). rewrite (Hg x y Exy). lia.
Qed.

(** ---------------- map, flat_map, filter ---------------- *)

Definition fcompat (f : A -> A) : Prop := forall x y, eqb x y = true -> eqb (f x) (f y) = true.
Definition lcompat (f : A -> list A) : Prop := forall x y, eqb x y = true -> bag_eq (f x) (f y).
Definition pcompat (P : A -> bool) : Prop := forall x y, eqb x y = true -> P x = P y.

Lemma count_map : forall z (f : A -> A) l, count z (map f l) = sumf (fun x => ind (eqb z (f x))) l.
Proof. intros z f l. induction l as [|x t IH]; simpl; [reflexivity|]. rewrite IH. reflexivity. Qed.

Lemma bag_le_map : forall (f : A -> A) l1 l2, fcompat f -> bag_le l1 l2 -> bag_le (map f l1) (map f l2).
Proof.
  intros f l1 l2 Hf H z. rewrite !count_map. apply sumf_mono; [|exact H].
  intros x y E. f_equal. apply eqb_swap. apply Hf. exact E.
Qed.

(** Two pointwise equivalent functions give equivalent bags. *)
Lemma bag_eq_map_ext : forall (f g : A -> A) l, (forall x, eqb (f x) (g x) = true) -> bag_eq (map f l) (map g l).
Proof.
  intros f g l H. split; intro z; rewrite !count_map; apply Nat.eq_le_incl;
    induction l as [|x t IH]; simpl; try reflexivity; rewrite IH; f_equal; f_equal.
  - apply eqb_swap. apply H.
  - symmetry. apply eqb_swap. apply H.
Qed.

Lemma count_flat_map : forall z (f : A -> list A) l, count z (flat_map f l) = sumf (fun x => count z (f x)) l.
Proof.
  intros z f l. induction l as [|x t IH]; simpl; [reflexivity|]. rewrite count_app, IH. reflexivity.
Qed.

Lemma bag_le_flat_map_list : forall (f : A -> list A) l1 l2,
  lcompat f -> bag_le l1 l2 -> bag_le (flat_map f l1) (flat_map f l2).
Proof.
  intros f l1 l2 Hf H z. rewrite !count_flat_map. apply sumf_mono; [|exact H].
  intros x y E. destruct (Hf x y E) as [H1 H2]. specialize (H1 z). specialize (H2 z). lia.
Qed.

Lemma bag_le_flat_map_fun : forall (f g : A -> list A) l,
  (forall x, bag_le (f x) (g x)) -> bag_le (flat_map f l) (flat_map g l).
Proof.
  intros f g l H. induction l as [|x l IH]; simpl; [apply bag_le_refl|]. apply bag_le_app; auto.
Qed.

Lemma count_filter : forall (P : A -> bool) x l, pcompat P ->
  count x (filter P l) = if P x then count x l else 0.
Proof.
  intros P x l HP. induction l as [|y t IH]; simpl; [destruct (P x); reflexivity|].
  destruct (P y) eqn:Py; simpl; rewrite IH; unfold ind; destruct (eqb x y) eqn:E.
  - rewrite (HP x y E), Py. reflexivity.
  - destruct (P x); reflexivity.
  - rewrite (HP x y E), Py. reflexivity.
  - destruct (P x); reflexivity.
Qed.

Lemma bag_le_filter : forall (P Q : A -> bool) l l', pcompat P -> pcompat Q ->
  (forall x, P x = true -> Q x = true) -> bag_le l l' -> bag_le (filter P l) (filter Q l').
Proof.
  intros P Q l l' HP HQ HPQ H x. rewrite (count_filter P), (count_filter Q); try assumption.
  specialize (H x). destruct (P x) eqn:E; [rewrite (HPQ x E); exact H|lia].
Qed.

Lemma filter_ext_eq : forall (P Q : A -> bool) l, (forall x, P x = Q x) -> filter P l = filter Q l.
Proof. intros P Q l H. induction l as [|x t IH]; simpl; [reflexivity|]. rewrite H, IH. reflexivity. Qed.

(** ---------------- SQL set operations (DISTINCT semantics) ---------------- *)

Fixpoint dedup (l : list A) : list A :=
  match l with
  | [] => []
  | x :: t => if existsb (eqb x) t then dedup t else x :: dedup t
  end.

Definition union_all (l1 l2 : list A) : list A := l1 ++ l2.
Definition union (l1 l2 : list A) : list A := dedup (l1 ++ l2).
Definition inter (l1 l2 : list A) : list A := filter (fun x => existsb (eqb x) l2) (dedup l1).
Definition exc (l1 l2 : list A) : list A := filter (fun x => negb (existsb (eqb x) l2)) (dedup l1).

Lemma count_dedup : forall x l, count x (dedup l) = Nat.min 1 (count x l).
Proof.
  intros x l. induction l as [|y t IH]; simpl; [reflexivity|].
  destruct (existsb (eqb y) t) eqn:Ey; simpl; rewrite ?IH; unfold ind.
  - apply existsb_count in Ey. destruct (eqb x y) eqn:E; simpl; [|reflexivity].
    rewrite (count_compat x y t E). destruct (count y t); [lia|reflexivity].
  - destruct (eqb x y) eqn:E; simpl; [|reflexivity].
    assert (C0 : count y t = 0).
    { destruct (count y t) eqn:C; [reflexivity|]. exfalso.
      assert (existsb (eqb y) t = true) by (apply existsb_count; lia). congruence. }
    rewrite (count_compat x y t E), C0. reflexivity.
Qed.

Lemma existsb_compat : forall l, pcompat (fun x => existsb (eqb x) l).
Proof.
  intros l x y E. destruct (existsb (eqb x) l) eqn:H1; destruct (existsb (eqb y) l) eqn:H2;
    try reflexivity; apply existsb_count in H1 || apply existsb_count in H2;
    [ rewrite (count_compat x y l E) in H1 | rewrite <- (count_compat x y l E) in H2 ];
    apply existsb_count in H1 || apply existsb_count in H2; congruence.
Qed.

Lemma negb_existsb_compat : forall l, pcompat (fun x => negb (existsb (eqb x) l)).
Proof. intros l x y E. rewrite (existsb_compat l x y E). reflexivity. Qed.

Lemma existsb_mono : forall l l' x, bag_le l l' -> existsb (eqb x) l = true -> existsb (eqb x) l' = true.
Proof. intros l l' x H E. apply existsb_count. apply existsb_count in E. specialize (H x). lia. Qed.

Lemma dedup_le : forall l, bag_le (dedup l) l.
Proof. intros l x. rewrite count_dedup. lia. Qed.

Lemma bag_le_dedup : forall l l', bag_le l l' -> bag_le (dedup l) (dedup l').
Proof. intros l l' H x. rewrite !count_dedup. specialize (H x). lia. Qed.

Lemma bag_le_union : forall a a' b b', bag_le a a' -> bag_le b b' -> bag_le (union a b) (union a' b').
Proof.
  intros a a' b b' H1 H2 x. unfold union. rewrite !count_dedup, !count_app.
  specialize (H1 x). specialize (H2 x). lia.
Qed.

Lemma union_le_union_all : forall a b, bag_le (union a b) (union_all a b).
Proof. intros a b x. unfold union, union_all. rewrite count_dedup. lia. Qed.

Lemma bag_le_inter : forall a a' b b', bag_le a a' -> bag_le b b' -> bag_le (inter a b) (inter a' b').
Proof.
  intros a a' b b' H1 H2. unfold inter. apply bag_le_filter;
    [apply existsb_compat|apply existsb_compat| |apply bag_le_dedup; exact H1].
  intros x E. eapply existsb_mono; eauto.
Qed.

Lemma inter_le_union : forall a b, bag_le (inter a b) (union a b).
Proof.
  intros a b x. unfold inter, union. rewrite count_filter by apply existsb_compat.
  rewrite !count_dedup, count_app. destruct (existsb (eqb x) b) eqn:E; [|lia].
  apply existsb_count in E. lia.
Qed.

Lemma inter_le_left : forall a b, bag_le (inter a b) a.
Proof.
  intros a b x. unfold inter. rewrite count_filter by apply existsb_compat.
  rewrite count_dedup. destruct (existsb (eqb x) b); lia.
Qed.

Lemma inter_le_right : forall a b, bag_le (inter a b) b.
Proof.
  intros a b x. unfold inter. rewrite count_filter by apply existsb_compat.
  rewrite count_dedup. destruct (existsb (eqb x) b) eqn:E; [|lia].
  apply existsb_count in E. lia.
Qed.

Lemma bag_le_exc_l : forall a a' b, bag_le a a' -> bag_le (exc a b) (exc a' b).
Proof.
  intros a a' b H. unfold exc. apply bag_le_filter;
    [apply negb_existsb_compat|apply negb_existsb_compat|tauto|apply bag_le_dedup; exact H].
Qed.

(** EXCEPT is antitone in its right operand. *)
Lemma bag_le_exc_r : forall a b b', bag_le b b' -> bag_le (exc a b') (exc a b).
Proof.
  intros a b b' H. unfold exc. apply bag_le_filter;
    [apply negb_existsb_compat|apply negb_existsb_compat| |apply bag_le_refl].
  intros x E. apply negb_true_iff in E. apply negb_true_iff.
  destruct (existsb (eqb x) b) eqn:Eb; [|reflexivity].
  rewrite (existsb_mono b b' x H Eb) in E. discriminate.
Qed.

Lemma exc_le_left : forall a b, bag_le (exc a b) a.
Proof.
  intros a b x. unfold exc. rewrite count_filter by apply negb_existsb_compat.
  rewrite count_dedup. destruct (negb (existsb (eqb x) b)); lia.
Qed.

(** ---------------- equivalence of bags (for the compatibility proofs) ---------------- *)

Lemma bag_eq_app : forall a a' b b', bag_eq a a' -> bag_eq b b' -> bag_eq (a ++ b) (a' ++ b').
Proof. intros a a' b b' [H1 H2] [H3 H4]. split; apply bag_le_app; assumption. Qed.

Lemma bag_eq_dedup : forall a a', bag_eq a a' -> bag_eq (dedup a) (dedup a').
Proof. intros a a' [H1 H2]. split; apply bag_le_dedup; assumption. Qed.

Lemma bag_eq_union : forall a a' b b', bag_eq a a' -> bag_eq b b' -> bag_eq (union a b) (union a' b').
Proof. intros a a' b b' [H1 H2] [H3 H4]. split; apply bag_le_union; assumption. Qed.

Lemma bag_eq_inter : forall a a' b b', bag_eq a a' -> bag_eq b b' -> bag_eq (inter a b) (inter a' b').
Proof. intros a a' b b' [H1 H2] [H3 H4]. split; apply bag_le_inter; assumption. Qed.

Lemma bag_eq_exc : forall a a' b b', bag_eq a a' -> bag_eq b b' -> bag_eq (exc a b) (exc a' b').
Proof.
  intros a a' b b' [H1 H2] [H3 H4]. split; (eapply bag_le_trans; [apply bag_le_exc_l; eassumption|]);
    apply bag_le_exc_r; assumption.
Qed.

Lemma bag_eq_map : forall (f : A -> A) l l', fcompat f -> bag_eq l l' -> bag_eq (map f l) (map f l').
Proof. intros f l l' Hf [H1 H2]. split; apply bag_le_map; assumption. Qed.

Lemma bag_eq_filter : forall (P : A -> bool) l l', pcompat P -> bag_eq l l' -> bag_eq (filter P l) (filter P l').
Proof. intros P l l' HP [H1 H2]. split; apply bag_le_filter; auto. Qed.

Lemma bag_eq_flat_map_list : forall (f : A -> list A) l l', lcompat f -> bag_eq l l' -> bag_eq (flat_map f l) (flat_map f l').
Proof. intros f l l' Hf [H1 H2]. split; apply bag_le_flat_map_list; assumption. Qed.

Lemma bag_eq_flat_map_fun : forall (f g : A -> list A) l,
  (forall x, bag_eq (f x) (g x)) -> bag_eq (flat_map f l) (flat_map g l).
Proof.
  intros f g l H. split; apply bag_le_flat_map_fun; intro x; apply H.
Qed.

Lemma bag_eq_trans : forall a b c, bag_eq a b -> bag_eq b c -> bag_eq a c.
Proof. intros a b c [H1 H2] [H3 H4]. split; eapply bag_le_trans; eassumption. Qed.

Lemma bag_eq_sym : forall a b, bag_eq a b -> bag_eq b a.
Proof. intros a b [H1 H2]. split; assumption. Qed.

(** Emptiness only depends on the class of the bag. *)
Lemma bag_eq_nil : forall a b, bag_eq a b -> (a = [] <-> b = []).
Proof.
  intros a b [H1 H2]. split; intro E; subst; apply bag_le_nil_r; assumption.
Qed.

(** ---------------- INTERSECT ALL and EXCEPT ALL (bag semantics) ---------------- *)

(** Remove the first element equivalent to [x]. *)
Fixpoint remove1 (x : A) (l : list A) : list A :=
  match l with [] => [] | y :: t => if eqb x y then t else y :: remove1 x t end.

(** [inter_all a b]: every element of [a] that can be matched with a distinct equivalent
    element of [b]; [exc_all a b]: every element of [a] that cannot. *)
Fixpoint inter_all (l1 l2 : list A) : list A :=
  match l1 with
  | [] => []
  | x :: t => if existsb (eqb x) l2 then x :: inter_all t (remove1 x l2) else inter_all t l2
  end.

Fixpoint exc_all (l1 l2 : list A) : list A :=
  match l1 with
  | [] => []
  | x :: t => if existsb (eqb x) l2 then exc_all t (remove1 x l2) else x :: exc_all t l2
  end.

Lemma count_remove1 : forall z x l,
  count z (remove1 x l) = count z l - ind (eqb z x && existsb (eqb x) l).
Proof.
  intros z x l. induction l as [|y t IH]; simpl; [reflexivity|].
  destruct (eqb x y) eqn:Exy; simpl.
  - (* y is removed: z loses one occurrence exactly when z ~ y, i.e. z ~ x *)
    rewrite (eqb_swap x y z Exy). unfold ind. rewrite ?orb_true_r, ?orb_true_l, ?andb_true_r.
    destruct (eqb z y); simpl; lia.
  - rewrite IH. unfold ind. destruct (eqb z y) eqn:Ezy; simpl.
    + destruct (eqb z x) eqn:Ezx; simpl.
      * exfalso. rewrite (eqb_trans _ _ _ (eqb_sym _ _ Ezx) Ezy) in Exy. discriminate.
      * lia.
    + destruct (eqb z x && existsb (eqb x) t); lia.
Qed.

Lemma count_inter_all : forall z a b, count z (inter_all a b) = Nat.min (count z a) (count z b).
Proof.
  intros z a. induction a as [|x t IH]; intros b; simpl; [reflexivity|].
  destruct (existsb (eqb x) b) eqn:Eb; simpl.
  - rewrite IH, count_remove1, Eb, andb_true_r. unfold ind.
    destruct (eqb z x) eqn:Ezx.
    + apply existsb_count in Eb. rewrite <- (count_compat z x b Ezx) in Eb. lia.
    + lia.
  - rewrite IH. unfold ind. destruct (eqb z x) eqn:Ezx; [|lia].
    assert (C : count x b = 0).
    { destruct (count x b) eqn:C; [reflexivity|].
      assert (existsb (eqb x) b = true) by (apply existsb_count; lia). congruence. }
    rewrite (count_compat z x b Ezx), C. lia.
Qed.

Lemma count_exc_all : forall z a b, count z (exc_all a b) = count z a - count z b.
Proof.
  intros z a. induction a as [|x t IH]; intros b; simpl; [reflexivity|].
  destruct (existsb (eqb x) b) eqn:Eb; simpl.
  - rewrite IH, count_remove1, Eb, andb_true_r. unfold ind.
    destruct (eqb z x) eqn:Ezx.
    + apply existsb_count in Eb. rewrite <- (count_compat z x b Ezx) in Eb. lia.
    + lia.
  - rewrite IH. unfold ind. destruct (eqb z x) eqn:Ezx; [|lia].
    assert (C : count x b = 0).
    { destruct (count x b) eqn:C; [reflexivity|].
      assert (existsb (eqb x) b = true) by (apply existsb_count; lia). congruence. }
    rewrite (count_compat z x b Ezx), C. lia.
Qed.

Lemma bag_le_inter_all : forall a a' b b', bag_le a a' -> bag_le b b' ->
  bag_le (inter_all a b) (inter_all a' b').
Proof. intros a a' b b' H1 H2 z. rewrite !count_inter_all. specialize (H1 z). specialize (H2 z). lia. Qed.

Lemma bag_le_exc_all_l : forall a a' b, bag_le a a' -> bag_le (exc_all a b) (exc_all a' b).
Proof. intros a a' b H z. rewrite !count_exc_all. specialize (H z). lia. Qed.

(** EXCEPT ALL is antitone in its right operand. *)
Lemma bag_le_exc_all_r : forall a b b', bag_le b b' -> bag_le (exc_all a b') (exc_all a b).
Proof. intros a b b' H z. rewrite !count_exc_all. specialize (H z). lia. Qed.

Lemma bag_eq_inter_all : forall a a' b b', bag_eq a a' -> bag_eq b b' ->
  bag_eq (inter_all a b) (inter_all a' b').
Proof. intros a a' b b' [H1 H1'] [H2 H2']. split; apply bag_le_inter_all; assumption. Qed.

Lemma bag_eq_exc_all : forall a a' b b', bag_eq a a' -> bag_eq b b' -> bag_eq (exc_all a b) (exc_all a' b').
Proof.
  intros a a' b b' [H1 H1'] [H2 H2']. split; intro z; rewrite !count_exc_all;
    specialize (H1 z); specialize (H1' z); specialize (H2 z); specialize (H2' z); lia.
Qed.

(** INTERSECT is below INTERSECT ALL, and EXCEPT below EXCEPT ALL. *)
Lemma inter_le_inter_all : forall a b, bag_le (inter a b) (inter_all a b).
Proof.
  intros a b z. unfold inter. rewrite count_filter by apply existsb_compat.
  rewrite count_dedup, count_inter_all. destruct (existsb (eqb z) b) eqn:E; [|lia].
  apply existsb_count in E. lia.
Qed.

Lemma exc_le_exc_all : forall a b, bag_le (exc a b) (exc_all a b).
Proof.
  intros a b z. unfold exc. rewrite count_filter by apply negb_existsb_compat.
  rewrite count_dedup, count_exc_all. destruct (existsb (eqb z) b) eqn:E; cbn [negb]; [lia|].
  assert (C : count z b = 0).
  { destruct (count z b) eqn:C; [reflexivity|]. exfalso.
    assert (Hc : count z b > 0) by lia. apply existsb_count in Hc. congruence. }
  rewrite C. lia.
Qed.

End Bag.
