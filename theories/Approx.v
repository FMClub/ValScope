(** Approx.v: compatibility with the collation, and monotonicity of every constructor.

    Part 1 proves that evaluation respects the collation equivalence: contexts that are
    equivalent give equal truth values and equivalent bags.  This is what makes the
    representative that DISTINCT keeps irrelevant.

    Part 2 is the mathematical content of the polarity analysis:
    - a position is POSITIVE when growing the sub-term can only grow the whole;
    - a position is NEGATIVE when growing the sub-term can only shrink the whole
      (NOT, the right operand of EXCEPT);
    - the remaining positions (ON condition and right input of a LEFT JOIN, LIMIT,
      the inside of opaque atoms) are NEITHER, and are never mutated.
    All statements hold in every world, i.e. for every dialect and collation. *)

From Coq Require Import List Lia Bool.
Import ListNotations.
From ValScope Require Import Bag Logic3 Pattern Syntax Semantics.

(** ---------------- the row equivalence ---------------- *)

Lemma req_refl : forall db r, req db r r = true.
Proof. intros db r. apply list_eqb_refl. apply veq_refl. Qed.

Lemma req_sym : forall db r s, req db r s = true -> req db s r = true.
Proof. intros db. apply list_eqb_sym. apply veq_sym. Qed.

Lemma req_trans : forall db r s t, req db r s = true -> req db s t = true -> req db r t = true.
Proof. intros db. apply list_eqb_trans. apply veq_trans. Qed.

Lemma req_app : forall db a a' b b', req db a a' = true -> req db b b' = true -> req db (a ++ b) (a' ++ b') = true.
Proof. intros db. apply list_eqb_app. Qed.

Ltac laws db := repeat first [ exact (req_refl db) | exact (req_sym db) | exact (req_trans db) ].

Lemma bag_eq_single : forall db r r', req db r r' = true -> bag_eq (req db) [r] [r'].
Proof.
  intros db r r' H. split; intro z; simpl; rewrite (eqb_swap (req db) (req_sym db) (req_trans db) r r' z H)
    || rewrite <- (eqb_swap (req db) (req_sym db) (req_trans db) r r' z H); lia.
Qed.

Lemma tv_le_antisym : forall a b, tv_le a b -> tv_le b a -> a = b.
Proof. intros a b. destruct a, b; unfold tv_le; simpl; intros; try reflexivity; lia. Qed.

(** ---------------- Part 1: compatibility ---------------- *)

Lemma expr_compat : forall db e c c', req db c c' = true ->
  veq db (eval_expr db c e) (eval_expr db c' e) = true.
Proof.
  intros db e c c' H. induction e; simpl.
  - apply veq_refl.
  - apply list_eqb_nth; [apply veq_refl|exact H].
  - apply vadd_compat; assumption.
  - apply vmul_compat; assumption.
  - apply eatoms_compat. exact H.
Qed.

Lemma proj_compat : forall db es c c', req db c c' = true ->
  req db (map (eval_expr db c) es) (map (eval_expr db c') es) = true.
Proof.
  intros db es c c' H. unfold req. induction es as [|e es IH]; simpl; [reflexivity|].
  rewrite (expr_compat db e c c' H), IH. reflexivity.
Qed.

Lemma isnull_compat : forall db x y, veq db x y = true ->
  (match x with VNull => T3 | _ => F3 end) = (match y with VNull => T3 | _ => F3 end).
Proof.
  intros db x y H. destruct x eqn:Ex; destruct y eqn:Ey; try reflexivity;
    try (assert (y = VNull) by (subst; apply (null_compat db _ _ H); reflexivity); subst; discriminate);
    try (assert (x = VNull) by (subst; apply (null_compat db _ _ (veq_sym db _ _ H)); reflexivity); subst; discriminate).
Qed.

Lemma in3_ge : forall db v vs x, In x vs -> tv_le (vcmp db CEq v x) (in3 db v vs).
Proof.
  intros db v vs x. induction vs as [|y vs IH]; intro H; simpl in *; [contradiction|].
  destruct H as [->|H]; [apply tv_or_ge_l|].
  eapply tv_le_trans; [apply IH; exact H|apply tv_or_ge_r].
Qed.

Lemma in3_le : forall db v vs t, (forall x, In x vs -> tv_le (vcmp db CEq v x) t) -> tv_le (in3 db v vs) t.
Proof.
  intros db v vs t. induction vs as [|y vs IH]; intro H; simpl; [apply tv_le_F|].
  apply tv_or_lub; [apply H; left; reflexivity|apply IH; intros x Hx; apply H; right; exact Hx].
Qed.

Lemma in3_mono : forall db v v' L L', veq db v v' = true -> bag_le (req db) L L' ->
  tv_le (in3 db v (first_col L)) (in3 db v' (first_col L')).
Proof.
  intros db v v' L L' Hv HL. apply in3_le. intros x Hx.
  unfold first_col in Hx. apply in_map_iff in Hx as [r [<- Hr]].
  destruct (bag_le_in (req db) (req_refl db) L L' r HL Hr) as [r' [Hr' E]].
  rewrite (vcmp_compat db CEq v v' (nth 0 r VNull) (nth 0 r' VNull) Hv).
  - apply in3_ge. unfold first_col. apply in_map_iff. exists r'. split; [reflexivity|exact Hr'].
  - apply list_eqb_nth; [apply veq_refl|exact E].
Qed.

Lemma roweq3_compat : forall db xs xs' ys ys', req db xs xs' = true -> req db ys ys' = true ->
  roweq3 db xs ys = roweq3 db xs' ys'.
Proof.
  intros db xs. induction xs as [|x xs IH]; intros xs' ys ys' Hx Hy;
    destruct xs' as [|x' xs']; simpl in Hx; try discriminate; [reflexivity|].
  apply andb_prop in Hx as [Hx1 Hx2].
  destruct ys as [|y ys]; destruct ys' as [|y' ys']; simpl in Hy; try discriminate; [reflexivity|].
  apply andb_prop in Hy as [Hy1 Hy2]. simpl.
  rewrite (vcmp_compat db CEq x x' y y' Hx1 Hy1), (IH xs' ys ys' Hx2 Hy2). reflexivity.
Qed.

Lemma int3_ge : forall db xs rows r, In r rows -> tv_le (roweq3 db xs r) (int3 db xs rows).
Proof.
  intros db xs rows r. induction rows as [|y rows IH]; intro H; simpl in *; [contradiction|].
  destruct H as [->|H]; [apply tv_or_ge_l|].
  eapply tv_le_trans; [apply IH; exact H|apply tv_or_ge_r].
Qed.

Lemma int3_le : forall db xs rows t, (forall r, In r rows -> tv_le (roweq3 db xs r) t) ->
  tv_le (int3 db xs rows) t.
Proof.
  intros db xs rows t. induction rows as [|y rows IH]; intro H; simpl; [apply tv_le_F|].
  apply tv_or_lub; [apply H; left; reflexivity|apply IH; intros r Hr; apply H; right; exact Hr].
Qed.

(** (x1, ..., xn) IN (subquery) is monotone in the subquery, like IN. *)
Lemma int3_mono : forall db xs xs' L L', req db xs xs' = true -> bag_le (req db) L L' ->
  tv_le (int3 db xs L) (int3 db xs' L').
Proof.
  intros db xs xs' L L' Hx HL. apply int3_le. intros r Hr.
  destruct (bag_le_in (req db) (req_refl db) L L' r HL Hr) as [r' [Hr' E]].
  rewrite (roweq3_compat db xs xs' r r' Hx E). apply int3_ge. exact Hr'.
Qed.

Lemma matches_row : forall db P r1 r1' B, pcompat (req db) P -> req db r1 r1' = true ->
  bag_eq (req db) (matches P r1 B) (matches P r1' B).
Proof.
  intros db P r1 r1' B HP H. unfold matches. eapply bag_eq_filter; laws db; [exact HP|].
  apply bag_eq_map_ext; laws db; []. intro r2. apply req_app; [exact H|apply req_refl].
Qed.

Lemma matches_ctx : forall db P P' r1 B B', pcompat (req db) P' -> (forall r, P r = P' r) ->
  bag_eq (req db) B B' -> bag_eq (req db) (matches P r1 B) (matches P' r1 B').
Proof.
  intros db P P' r1 B B' HP' HPP HB. unfold matches. rewrite (filter_ext_eq P P') by exact HPP.
  eapply bag_eq_filter; laws db; [exact HP'|].
  eapply bag_eq_map; laws db; [ |exact HB].
  intros x y E. apply req_app; [apply req_refl|exact E].
Qed.

Lemma left_compat : forall db P P' pad r1 r1' B B',
  bag_eq (req db) (matches P r1 B) (matches P' r1' B') -> req db r1 r1' = true ->
  bag_eq (req db) (left_matches P pad r1 B) (left_matches P' pad r1' B').
Proof.
  intros db P P' pad r1 r1' B B' HM H. unfold left_matches.
  destruct (bag_eq_nil (req db) (req_refl db) _ _ HM) as [N1 N2].
  destruct (matches P r1 B) as [|x M]; destruct (matches P' r1' B') as [|y M'].
  - apply bag_eq_single. apply req_app; [exact H|apply req_refl].
  - discriminate (N1 eq_refl).
  - discriminate (N2 eq_refl).
  - exact HM.
Qed.

Definition CP (p : pred) : Prop :=
  forall db c c', req db c c' = true -> eval_p db c p = eval_p db c' p.
Definition CQ (q : query) : Prop :=
  forall db c c', req db c c' = true -> bag_eq (req db) (eval_q db c q) (eval_q db c' q).

Lemma pcompat_pred : forall db p c, CP p -> pcompat (req db) (fun r => is_true (eval_p db (r ++ c) p)).
Proof.
  intros db p c Hp r r' E. f_equal. apply Hp. apply req_app; [exact E|apply req_refl].
Qed.

Lemma pred_ctx : forall db p c c' r, CP p -> req db c c' = true ->
  is_true (eval_p db (r ++ c) p) = is_true (eval_p db (r ++ c') p).
Proof. intros db p c c' r Hp H. f_equal. apply Hp. apply req_app; [apply req_refl|exact H]. Qed.

Theorem compat : (forall p, CP p) /\ (forall q, CQ q).
Proof.
  apply (pq_ind CP CQ); unfold CP, CQ; intros; simpl.
  - reflexivity.
  - reflexivity.
  - apply vcmp_compat; apply expr_compat; assumption.
  - apply (isnull_compat db). apply expr_compat. assumption.
  - rewrite (H db c c' H0). reflexivity.
  - rewrite (H db c c' H1), (H0 db c c' H1). reflexivity.
  - rewrite (H db c c' H1), (H0 db c c' H1). reflexivity.
  - (* EXISTS *)
    destruct (bag_eq_nil (req db) (req_refl db) _ _ (H db c c' H0)) as [E1 E2].
    destruct (eval_q db c q), (eval_q db c' q); try reflexivity.
    + discriminate (E1 eq_refl).
    + discriminate (E2 eq_refl).
  - (* IN *)
    destruct (H db c c' H0) as [L1 L2]. apply tv_le_antisym.
    + apply in3_mono; [apply expr_compat; exact H0|exact L1].
    + apply in3_mono; [apply veq_sym; apply expr_compat; exact H0|exact L2].
  - (* (e1, ..., en) IN *)
    destruct (H db c c' H0) as [L1 L2]. apply tv_le_antisym.
    + apply int3_mono; [apply proj_compat; exact H0|exact L1].
    + apply int3_mono; [apply proj_compat; apply req_sym; exact H0|exact L2].
  - apply like_compat. apply expr_compat. assumption.
  - apply rx_compat. apply expr_compat. assumption.
  - apply atoms_compat. exact H.
  - (* QTable *) apply bag_eq_refl.
  - (* QProject *)
    eapply bag_eq_trans; laws db; [ |].
    + eapply bag_eq_map; laws db; [ |apply H; exact H0].
      intros r r' E. apply proj_compat. apply req_app; [exact E|apply req_refl].
    + apply bag_eq_map_ext; laws db; []. intro r. apply proj_compat.
      apply req_app; [apply req_refl|exact H0].
  - (* QWhere *)
    rewrite (filter_ext_eq (fun r => is_true (eval_p db (r ++ c) p))
                           (fun r => is_true (eval_p db (r ++ c') p)))
      by (intro r; apply pred_ctx; assumption).
    eapply bag_eq_filter; laws db; [apply pcompat_pred; exact H|apply H0; exact H1].
  - eapply bag_eq_dedup; laws db; [apply H; exact H0].
  - apply bag_eq_app; [apply H|apply H0]; exact H1.
  - eapply bag_eq_union; laws db; [apply H|apply H0]; exact H1.
  - eapply bag_eq_inter; laws db; [apply H|apply H0]; exact H1.
  - eapply bag_eq_exc; laws db; [apply H|apply H0]; exact H1.
  - eapply bag_eq_inter_all; laws db; [apply H|apply H0]; exact H1.
  - eapply bag_eq_exc_all; laws db; [apply H|apply H0]; exact H1.
  - (* QInnerJoin *)
    eapply bag_eq_trans; laws db; [ |].
    + eapply bag_eq_flat_map_list; laws db; [ |apply H0; exact H2].
      intros r1 r1' E. apply matches_row; [apply pcompat_pred; exact H|exact E].
    + apply bag_eq_flat_map_fun. intro r1.
      apply matches_ctx; [apply pcompat_pred; exact H|intro r; apply pred_ctx; assumption|apply H1; exact H2].
  - (* QLeftJoin *)
    eapply bag_eq_trans; laws db; [ |].
    + eapply bag_eq_flat_map_list; laws db; [ |apply H0; exact H2].
      intros r1 r1' E. apply left_compat; [|exact E].
      apply matches_row; [apply pcompat_pred; exact H|exact E].
    + apply bag_eq_flat_map_fun. intro r1. apply left_compat; [|apply req_refl].
      apply matches_ctx; [apply pcompat_pred; exact H|intro r; apply pred_ctx; assumption|apply H1; exact H2].
  - (* QNamed *) apply H. exact H0.
  - (* QAtom *) split; apply qatoms_compat; [exact H|apply req_sym; exact H].
Qed.

Lemma pcompat_eval : forall db p c, pcompat (req db) (fun r => is_true (eval_p db (r ++ c) p)).
Proof. intros db p c. apply pcompat_pred. apply (proj1 compat). Qed.

(** ---------------- Part 2: monotonicity ---------------- *)

(** Each monotonicity lemma is proved in one world ([_at]); the statement for every
    world follows.  The engine uses the first form, so that it is sound in any class
    of worlds, and the rules proved for every world use the second. *)
Ltac at_world L :=
  intros; let db := fresh "db" in intro db;
  repeat match goal with
         | H : q_le ?a ?b |- _ => assert (q_le_at db a b) by exact (H db); clear H
         | H : p_le ?a ?b |- _ => assert (p_le_at db a b) by exact (H db); clear H
         end;
  match goal with
  | |- forall ctx, bag_le _ (eval_q _ ctx ?a) (eval_q _ ctx ?b) => change (q_le_at db a b)
  | |- forall ctx, tv_le (eval_p _ ctx ?a) (eval_p _ ctx ?b) => change (p_le_at db a b)
  end;
  eapply L; eassumption.

Lemma q_le_refl_at : forall db q, q_le_at db q q.
Proof. intros db q ctx. apply bag_le_refl. Qed.

Lemma q_le_refl : forall q, q_le q q.
Proof. at_world q_le_refl_at. Qed.

Lemma q_le_trans_at : forall db a b c, q_le_at db a b -> q_le_at db b c -> q_le_at db a c.
Proof. intros db a b c H1 H2 ctx. eapply bag_le_trans; [apply H1|apply H2]. Qed.

Lemma q_le_trans : forall a b c, q_le a b -> q_le b c -> q_le a c.
Proof. at_world q_le_trans_at. Qed.

Lemma p_le_refl_at : forall db p, p_le_at db p p.
Proof. intros db p ctx. apply tv_le_refl. Qed.

Lemma p_le_refl : forall p, p_le p p.
Proof. at_world p_le_refl_at. Qed.

Lemma p_le_trans_at : forall db a b c, p_le_at db a b -> p_le_at db b c -> p_le_at db a c.
Proof. intros db a b c H1 H2 ctx. eapply tv_le_trans; [apply H1|apply H2]. Qed.

Lemma p_le_trans : forall a b c, p_le a b -> p_le b c -> p_le a c.
Proof. at_world p_le_trans_at. Qed.

Lemma p_le_and_at : forall db a a' b b', p_le_at db a a' -> p_le_at db b b' -> p_le_at db (PAnd a b) (PAnd a' b').
Proof. intros db a a' b b' H1 H2 ctx. simpl. apply tv_and_mono; auto. Qed.

Lemma p_le_and : forall a a' b b', p_le a a' -> p_le b b' -> p_le (PAnd a b) (PAnd a' b').
Proof. at_world p_le_and_at. Qed.

Lemma p_le_or_at : forall db a a' b b', p_le_at db a a' -> p_le_at db b b' -> p_le_at db (POr a b) (POr a' b').
Proof. intros db a a' b b' H1 H2 ctx. simpl. apply tv_or_mono; auto. Qed.

Lemma p_le_or : forall a a' b b', p_le a a' -> p_le b b' -> p_le (POr a b) (POr a' b').
Proof. at_world p_le_or_at. Qed.

(** NOT is antitone: a mutation under NOT has the opposite effect. *)
Lemma p_le_not_at : forall db a b, p_le_at db a b -> p_le_at db (PNot b) (PNot a).
Proof. intros db a b H ctx. simpl. apply tv_not_anti; auto. Qed.

Lemma p_le_not : forall a b, p_le a b -> p_le (PNot b) (PNot a).
Proof. at_world p_le_not_at. Qed.

Lemma p_le_exists_at : forall db a b, q_le_at db a b -> p_le_at db (PExists a) (PExists b).
Proof.
  intros db a b H ctx. simpl. specialize (H ctx).
  destruct (eval_q db ctx a) eqn:Ea; destruct (eval_q db ctx b) eqn:Eb.
  - apply tv_le_refl.
  - apply tv_le_T.
  - apply (bag_le_nil_r (req db) (req_refl db)) in H. discriminate.
  - apply tv_le_refl.
Qed.

Lemma p_le_exists : forall a b, q_le a b -> p_le (PExists a) (PExists b).
Proof. at_world p_le_exists_at. Qed.

(** IN is monotone in its subquery, so NOT IN is antitone. *)
Lemma p_le_in_at : forall db e a b, q_le_at db a b -> p_le_at db (PIn e a) (PIn e b).
Proof. intros db e a b H ctx. simpl. apply in3_mono; [apply veq_refl|apply H]. Qed.

Lemma p_le_in : forall e a b, q_le a b -> p_le (PIn e a) (PIn e b).
Proof. at_world p_le_in_at. Qed.

Lemma p_le_int_at : forall db es a b, q_le_at db a b -> p_le_at db (PInT es a) (PInT es b).
Proof. intros db es a b H ctx. simpl. apply int3_mono; [apply req_refl|apply H]. Qed.

Lemma p_le_int : forall es a b, q_le a b -> p_le (PInT es a) (PInT es b).
Proof. at_world p_le_int_at. Qed.

Lemma p_le_true : forall p, p_le p PTrue.
Proof. intros p db ctx. simpl. apply tv_le_T. Qed.

Lemma p_le_false : forall p, p_le PFalse p.
Proof. intros p db ctx. simpl. apply tv_le_F. Qed.

Lemma p_le_and_l : forall a b, p_le (PAnd a b) a.
Proof. intros a b db ctx. simpl. apply tv_and_le_l. Qed.

Lemma p_le_and_r : forall a b, p_le (PAnd a b) b.
Proof. intros a b db ctx. simpl. apply tv_and_le_r. Qed.

Lemma p_le_or_l : forall a b, p_le a (POr a b).
Proof. intros a b db ctx. simpl. apply tv_or_ge_l. Qed.

Lemma p_le_or_r : forall a b, p_le b (POr a b).
Proof. intros a b db ctx. simpl. apply tv_or_ge_r. Qed.

Lemma p_le_cmp : forall c c' x y, cmp_weaker c c' -> p_le (PCmp c x y) (PCmp c' x y).
Proof. intros c c' x y H db ctx. simpl. apply vcmp_weaker. exact H. Qed.

(** Rule 7: a more general LIKE pattern matches more. *)
Lemma p_le_like : forall e p p', Forall2 tle p p' -> p_le (PLike e p) (PLike e p').
Proof.
  intros e p p' H db ctx. simpl. unfold like3.
  destruct (to_text db (eval_expr db ctx e)); [|apply tv_le_refl].
  apply tv_le_of_bool. apply lmatch_mono. exact H.
Qed.

(** Rule 14: a more general REGEXP pattern matches more. *)
Lemma p_le_regex : forall e r r', rgen r r' -> p_le (PRegex e r) (PRegex e r').
Proof.
  intros e r r' H db ctx. simpl. unfold rx3.
  destruct (to_text db (eval_expr db ctx e)); [|apply tv_le_refl].
  apply tv_le_of_bool. apply rsearch_mono. exact H.
Qed.

Lemma q_le_project_at : forall db es a b, q_le_at db a b -> q_le_at db (QProject es a) (QProject es b).
Proof.
  intros db es a b H ctx. simpl. eapply bag_le_map; laws db; [ |apply H].
  intros r r' E. apply proj_compat. apply req_app; [exact E|apply req_refl].
Qed.

Lemma q_le_project : forall es a b, q_le a b -> q_le (QProject es a) (QProject es b).
Proof. at_world q_le_project_at. Qed.

Lemma q_le_where_at : forall db p p' a a', p_le_at db p p' -> q_le_at db a a' -> q_le_at db (QWhere p a) (QWhere p' a').
Proof.
  intros db p p' a a' Hp Ha ctx. simpl.
  eapply bag_le_filter; laws db; [apply pcompat_eval|apply pcompat_eval| |apply Ha].
  intros r Hr. exact (is_true_mono _ _ (Hp (r ++ ctx)) Hr).
Qed.

Lemma q_le_where : forall p p' a a', p_le p p' -> q_le a a' -> q_le (QWhere p a) (QWhere p' a').
Proof. at_world q_le_where_at. Qed.

Lemma q_le_distinct_at : forall db a b, q_le_at db a b -> q_le_at db (QDistinct a) (QDistinct b).
Proof. intros db a b H ctx. simpl. eapply bag_le_dedup; laws db. apply H. Qed.

Lemma q_le_distinct : forall a b, q_le a b -> q_le (QDistinct a) (QDistinct b).
Proof. at_world q_le_distinct_at. Qed.

Lemma q_le_named_at : forall db n a b, q_le_at db a b -> q_le_at db (QNamed n a) (QNamed n b).
Proof. intros db n a b H ctx. simpl. apply H. Qed.

Lemma q_le_named : forall n a b, q_le a b -> q_le (QNamed n a) (QNamed n b).
Proof. at_world q_le_named_at. Qed.

Lemma q_le_union_all_at : forall db a a' b b', q_le_at db a a' -> q_le_at db b b' -> q_le_at db (QUnionAll a b) (QUnionAll a' b').
Proof. intros db a a' b b' H1 H2 ctx. simpl. apply bag_le_app; [apply H1|apply H2]. Qed.

Lemma q_le_union_all : forall a a' b b', q_le a a' -> q_le b b' -> q_le (QUnionAll a b) (QUnionAll a' b').
Proof. at_world q_le_union_all_at. Qed.

Lemma q_le_union_at : forall db a a' b b', q_le_at db a a' -> q_le_at db b b' -> q_le_at db (QUnion a b) (QUnion a' b').
Proof. intros db a a' b b' H1 H2 ctx. simpl. eapply bag_le_union; laws db; [apply H1|apply H2]. Qed.

Lemma q_le_union : forall a a' b b', q_le a a' -> q_le b b' -> q_le (QUnion a b) (QUnion a' b').
Proof. at_world q_le_union_at. Qed.

Lemma q_le_intersect_at : forall db a a' b b', q_le_at db a a' -> q_le_at db b b' -> q_le_at db (QIntersect a b) (QIntersect a' b').
Proof. intros db a a' b b' H1 H2 ctx. simpl. eapply bag_le_inter; laws db; [apply H1|apply H2]. Qed.

Lemma q_le_intersect : forall a a' b b', q_le a a' -> q_le b b' -> q_le (QIntersect a b) (QIntersect a' b').
Proof. at_world q_le_intersect_at. Qed.

(** EXCEPT: monotone in the left operand, antitone in the right one. *)
Lemma q_le_except_at : forall db a a' b b', q_le_at db a a' -> q_le_at db b' b -> q_le_at db (QExcept a b) (QExcept a' b').
Proof.
  intros db a a' b b' H1 H2 ctx. simpl. eapply bag_le_trans.
  - eapply bag_le_exc_l; laws db; [apply H1].
  - eapply bag_le_exc_r; laws db; [apply H2].
Qed.

Lemma q_le_except : forall a a' b b', q_le a a' -> q_le b' b -> q_le (QExcept a b) (QExcept a' b').
Proof. at_world q_le_except_at. Qed.

Lemma q_le_inner_join_at : forall db p p' a a' b b', p_le_at db p p' -> q_le_at db a a' -> q_le_at db b b' ->
  q_le_at db (QInnerJoin p a b) (QInnerJoin p' a' b').
Proof.
  intros db p p' a a' b b' Hp Ha Hb ctx. simpl. eapply bag_le_trans.
  - eapply bag_le_flat_map_list; laws db; [ |apply Ha].
    intros r1 r1' E. apply matches_row; [apply pcompat_eval|exact E].
  - apply bag_le_flat_map_fun. intro r1. unfold matches.
    eapply bag_le_filter; laws db; [apply pcompat_eval|apply pcompat_eval| |].
    + intros r Hr. exact (is_true_mono _ _ (Hp (r ++ ctx)) Hr).
    + eapply bag_le_map; laws db; [ |apply Hb]. intros x y E. apply req_app; [apply req_refl|exact E].
Qed.

Lemma q_le_inner_join : forall p p' a a' b b', p_le p p' -> q_le a a' -> q_le b b' ->
  q_le (QInnerJoin p a b) (QInnerJoin p' a' b').
Proof. at_world q_le_inner_join_at. Qed.

(** A LEFT JOIN is monotone in its LEFT input only. *)
Lemma q_le_left_join_left_at : forall db pad p a a' b, q_le_at db a a' -> q_le_at db (QLeftJoin pad p a b) (QLeftJoin pad p a' b).
Proof.
  intros db pad p a a' b H ctx. simpl. eapply bag_le_flat_map_list; laws db; [ |apply H].
  intros r1 r1' E. apply left_compat; [|exact E].
  apply matches_row; [apply pcompat_eval|exact E].
Qed.

Lemma q_le_left_join_left : forall pad p a a' b, q_le a a' -> q_le (QLeftJoin pad p a b) (QLeftJoin pad p a' b).
Proof. at_world q_le_left_join_left_at. Qed.

(** Rule 17: INNER JOIN -> LEFT JOIN (and, read backwards, LEFT JOIN -> INNER JOIN). *)
Lemma matches_le_left : forall db P pad r1 rhs, bag_le (req db) (matches P r1 rhs) (left_matches P pad r1 rhs).
Proof.
  intros db P pad r1 rhs. unfold left_matches. destruct (matches P r1 rhs).
  - apply bag_le_nil_l.
  - apply bag_le_refl.
Qed.

Lemma q_le_inner_left : forall pad p a b, q_le (QInnerJoin p a b) (QLeftJoin pad p a b).
Proof. intros pad p a b db ctx. simpl. apply bag_le_flat_map_fun. intro r1. apply matches_le_left. Qed.

(** Rules 1-4 as relations between queries. *)
Lemma q_le_distinct_base : forall a, q_le (QDistinct a) a.
Proof. intros a db ctx. simpl. eapply dedup_le; laws db. Qed.

Lemma q_le_union_base : forall a b, q_le (QUnion a b) (QUnionAll a b).
Proof. intros a b db ctx. simpl. eapply union_le_union_all; laws db. Qed.

Lemma q_le_intersect_all_at : forall db a a' b b', q_le_at db a a' -> q_le_at db b b' ->
  q_le_at db (QIntersectAll a b) (QIntersectAll a' b').
Proof. intros db a a' b b' H1 H2 ctx. simpl. eapply bag_le_inter_all; laws db; [apply H1|apply H2]. Qed.

Lemma q_le_intersect_all : forall a a' b b', q_le a a' -> q_le b b' ->
  q_le (QIntersectAll a b) (QIntersectAll a' b').
Proof. at_world q_le_intersect_all_at. Qed.

(** EXCEPT ALL is monotone on the left and antitone on the right. *)
Lemma q_le_except_all_at : forall db a a' b b', q_le_at db a a' -> q_le_at db b' b -> q_le_at db (QExceptAll a b) (QExceptAll a' b').
Proof.
  intros db a a' b b' H1 H2 ctx. simpl. eapply bag_le_trans.
  - eapply bag_le_exc_all_l; laws db; [apply H1].
  - eapply bag_le_exc_all_r; laws db; [apply H2].
Qed.

Lemma q_le_except_all : forall a a' b b', q_le a a' -> q_le b' b -> q_le (QExceptAll a b) (QExceptAll a' b').
Proof. at_world q_le_except_all_at. Qed.

(** INTERSECT is below INTERSECT ALL, EXCEPT below EXCEPT ALL. *)
Lemma q_le_intersect_all_base : forall a b, q_le (QIntersect a b) (QIntersectAll a b).
Proof. intros a b db ctx. simpl. eapply inter_le_inter_all; laws db. Qed.

Lemma q_le_except_all_base : forall a b, q_le (QExcept a b) (QExceptAll a b).
Proof. intros a b db ctx. simpl. eapply exc_le_exc_all; laws db. Qed.

Lemma q_le_inter_base : forall a b, q_le (QIntersect a b) (QUnion a b).
Proof. intros a b db ctx. simpl. eapply inter_le_union; laws db. Qed.

Lemma q_le_except_base : forall a b, q_le (QExcept a b) a.
Proof. intros a b db ctx. simpl. eapply exc_le_left; laws db. Qed.

Lemma q_le_intersect_left : forall a b, q_le (QIntersect a b) a.
Proof. intros a b db ctx. simpl. eapply inter_le_left; laws db. Qed.

Lemma q_le_intersect_right : forall a b, q_le (QIntersect a b) b.
Proof. intros a b db ctx. simpl. eapply inter_le_right; laws db. Qed.
