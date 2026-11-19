(** Approx.v: monotonicity of every constructor.

    These lemmas are the mathematical content of ValScope's polarity analysis:
    - a position is POSITIVE when growing the sub-term can only grow the whole
      (every [mono] lemma below);
    - a position is NEGATIVE when growing the sub-term can only shrink the whole
      (every [anti] lemma: NOT, the right operand of EXCEPT);
    - the remaining positions (ON condition and right input of a LEFT JOIN, LIMIT,
      scalar subqueries) are NEITHER; Counter.v proves that. *)

From Coq Require Import List Lia.
Import ListNotations.
From ValScope Require Import Bag Logic3 Syntax Semantics.

Lemma q_le_refl : forall q, q_le q q.
Proof. intros q db ctx. apply bag_le_refl. Qed.

Lemma q_le_trans : forall a b c, q_le a b -> q_le b c -> q_le a c.
Proof. intros a b c H1 H2 db ctx. eapply bag_le_trans; [apply H1|apply H2]. Qed.

Lemma p_le_refl : forall p, p_le p p.
Proof. intros p db ctx. apply tv_le_refl. Qed.

Lemma p_le_trans : forall a b c, p_le a b -> p_le b c -> p_le a c.
Proof. intros a b c H1 H2 db ctx. eapply tv_le_trans; [apply H1|apply H2]. Qed.

(** ---------------- predicates ---------------- *)

Lemma p_le_and : forall a a' b b',
  p_le a a' -> p_le b b' -> p_le (PAnd a b) (PAnd a' b').
Proof. intros a a' b b' H1 H2 db ctx. simpl. apply tv_and_mono; auto. Qed.

Lemma p_le_or : forall a a' b b',
  p_le a a' -> p_le b b' -> p_le (POr a b) (POr a' b').
Proof. intros a a' b b' H1 H2 db ctx. simpl. apply tv_or_mono; auto. Qed.

(** NOT is antitone: this is why a mutation under NOT has the opposite effect. *)
Lemma p_le_not : forall a b, p_le a b -> p_le (PNot b) (PNot a).
Proof. intros a b H db ctx. simpl. apply tv_not_anti; auto. Qed.

Lemma p_le_exists : forall a b, q_le a b -> p_le (PExists a) (PExists b).
Proof.
  intros a b H db ctx. simpl. specialize (H db ctx).
  destruct (eval_q db ctx a) eqn:Ea; destruct (eval_q db ctx b) eqn:Eb.
  - apply tv_le_refl.
  - apply tv_le_T.
  - try rewrite Ea in H. try rewrite Eb in H. apply bag_le_nil_r in H. discriminate.
  - apply tv_le_refl.
Qed.

(** IN is monotone in its subquery: more rows can only turn FALSE into UNKNOWN or
    TRUE, and UNKNOWN into TRUE.  Hence NOT IN is antitone. *)
Lemma in3_ge : forall v vs x, In x vs -> tv_le (cmp3 CEq v x) (in3 v vs).
Proof.
  intros v vs x. induction vs as [|y vs IH]; intro H; simpl in *; [contradiction|].
  destruct H as [->|H].
  - apply tv_or_ge_l.
  - eapply tv_le_trans; [apply IH; exact H|apply tv_or_ge_r].
Qed.

Lemma in3_le : forall v vs t,
  (forall x, In x vs -> tv_le (cmp3 CEq v x) t) -> tv_le (in3 v vs) t.
Proof.
  intros v vs t. induction vs as [|y vs IH]; intro H; simpl.
  - apply tv_le_F.
  - apply tv_or_lub.
    + apply H. left. reflexivity.
    + apply IH. intros x Hx. apply H. right. exact Hx.
Qed.

Lemma p_le_in : forall e a b, q_le a b -> p_le (PIn e a) (PIn e b).
Proof.
  intros e a b H db ctx. simpl. apply in3_le. intros x Hx.
  unfold first_col in Hx. apply in_map_iff in Hx as [r [<- Hr]].
  apply in3_ge. unfold first_col. apply in_map_iff. exists r. split; [reflexivity|].
  eapply bag_le_in; [apply H|exact Hr].
Qed.

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

Lemma p_le_cmp : forall c c' x y,
  cmp_weaker c c' -> p_le (PCmp c x y) (PCmp c' x y).
Proof. intros c c' x y H db ctx. simpl. apply cmp3_weaker. exact H. Qed.

(** ---------------- queries ---------------- *)

Lemma q_le_project : forall es a b, q_le a b -> q_le (QProject es a) (QProject es b).
Proof.
  intros es a b H db ctx. simpl. apply count_map_perm. apply H.
Qed.

Lemma q_le_where : forall p p' a a',
  p_le p p' -> q_le a a' -> q_le (QWhere p a) (QWhere p' a').
Proof.
  intros p p' a a' Hp Ha db ctx. simpl. apply bag_le_filter.
  - intros r Hr. exact (is_true_mono _ _ (Hp db (r ++ ctx)) Hr).
  - apply Ha.
Qed.

Lemma q_le_distinct : forall a b, q_le a b -> q_le (QDistinct a) (QDistinct b).
Proof. intros a b H db ctx. simpl. apply bag_le_dedup. apply H. Qed.

Lemma q_le_union_all : forall a a' b b',
  q_le a a' -> q_le b b' -> q_le (QUnionAll a b) (QUnionAll a' b').
Proof. intros a a' b b' H1 H2 db ctx. simpl. apply bag_le_app; [apply H1|apply H2]. Qed.

Lemma q_le_union : forall a a' b b',
  q_le a a' -> q_le b b' -> q_le (QUnion a b) (QUnion a' b').
Proof. intros a a' b b' H1 H2 db ctx. simpl. apply bag_le_union; [apply H1|apply H2]. Qed.

Lemma q_le_intersect : forall a a' b b',
  q_le a a' -> q_le b b' -> q_le (QIntersect a b) (QIntersect a' b').
Proof. intros a a' b b' H1 H2 db ctx. simpl. apply bag_le_inter; [apply H1|apply H2]. Qed.

(** EXCEPT: monotone in the left operand, antitone in the right one. *)
Lemma q_le_except : forall a a' b b',
  q_le a a' -> q_le b' b -> q_le (QExcept a b) (QExcept a' b').
Proof.
  intros a a' b b' H1 H2 db ctx. simpl.
  eapply bag_le_trans.
  - apply bag_le_exc_l. apply H1.
  - apply bag_le_exc_r. apply H2.
Qed.

Lemma q_le_inner_join : forall p p' a a' b b',
  p_le p p' -> q_le a a' -> q_le b b' ->
  q_le (QInnerJoin p a b) (QInnerJoin p' a' b').
Proof.
  intros p p' a a' b b' Hp Ha Hb db ctx. simpl.
  eapply bag_le_trans.
  - apply bag_le_flat_map_list. apply Ha.
  - apply bag_le_flat_map_fun. intro r1. unfold matches. apply bag_le_filter.
    + intros r Hr. exact (is_true_mono _ _ (Hp db (r ++ ctx)) Hr).
    + apply count_map_perm. apply Hb.
Qed.

(** A LEFT JOIN is monotone in its LEFT input only. *)
Lemma q_le_left_join_left : forall pad p a a' b,
  q_le a a' -> q_le (QLeftJoin pad p a b) (QLeftJoin pad p a' b).
Proof.
  intros pad p a a' b H db ctx. simpl. apply bag_le_flat_map_list. apply H.
Qed.

(** Rule 17: INNER JOIN -> LEFT JOIN (and, read backwards, LEFT JOIN -> INNER JOIN). *)
Lemma matches_le_left : forall P pad r1 rhs,
  rle (matches P r1 rhs) (left_matches P pad r1 rhs).
Proof.
  intros P pad r1 rhs. unfold left_matches.
  destruct (matches P r1 rhs) as [|r l].
  - intro x. unfold count. simpl. lia.
  - apply bag_le_refl.
Qed.

Lemma q_le_inner_left : forall pad p a b,
  q_le (QInnerJoin p a b) (QLeftJoin pad p a b).
Proof.
  intros pad p a b db ctx. simpl. apply bag_le_flat_map_fun.
  intro r1. apply matches_le_left.
Qed.

(** Rules 1-4 as relations between queries. *)
Lemma q_le_distinct_base : forall a, q_le (QDistinct a) a.
Proof. intros a db ctx. simpl. apply dedup_le. Qed.

Lemma q_le_union_base : forall a b, q_le (QUnion a b) (QUnionAll a b).
Proof. intros a b db ctx. simpl. apply union_le_union_all. Qed.

Lemma q_le_inter_base : forall a b, q_le (QIntersect a b) (QUnion a b).
Proof. intros a b db ctx. simpl. apply inter_le_union. Qed.

Lemma q_le_except_base : forall a b, q_le (QExcept a b) a.
Proof. intros a b db ctx. simpl. apply exc_le_left. Qed.
