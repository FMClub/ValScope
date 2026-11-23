(** Registry.v: the rules that are plugged in.

    To add a rule: prove it (see StdRules.v / ExtraRules.v) and add it to one of
    the two lists below.  Nothing else changes. *)

From Coq Require Import List String.
Import ListNotations.
From Coq Require Import ZArith Lia.
From ValScope Require Import Bag Logic3 Pattern Syntax Semantics Approx Rule Engine StdRules ExtraRules.
From ValScope Require Import Value VEngine VRules VHaving.

Definition pred_rules : list prule :=
  [ r_true; r_false; r_and_drop; r_or_drop; r_cmp_weaken; r_cmp_strengthen;
    r_like_up; r_like_down; r_rx_up; r_rx_down ].

Definition query_rules : list qrule :=
  [ r_distinct_drop; r_distinct_add; r_union_all; r_union_distinct;
    r_except_left; r_intersect_union; r_union_intersect;
    r_inner_left; r_left_inner;
    r_intersect_operand;
    r_intersect_all; r_intersect_distinct; r_except_all; r_except_distinct ].

(** The mutator of the framework: the engine instantiated with the registry. *)
Definition mutate : dir -> query -> list (string * query) :=
  mut_q pred_rules query_rules.

(** Its soundness is an instance of the generic theorem. *)
Theorem mutate_sound : forall d q name q',
  In (name, q') (mutate d q) -> dle q_le d q q'.
Proof. intros d q name q'. apply mut_q_sound. Qed.

Print Assumptions mutate_sound.

(** The same mutator for a class of worlds [W], with further rules that are sound
    in that class only: rules proved against the semantics of one dialect.  The rules
    above are sound in every world, hence in [W].  A development that proves such
    rules instantiates this definition and extracts it in place of [mutate]. *)
Definition mutate_within (W : db_t -> Prop) (prs : list (prule_in W)) (qrs : list (qrule_in W))
  : dir -> query -> list (string * query) :=
  mut_q_in (map (prule_at W) pred_rules ++ prs) (map (qrule_at W) query_rules ++ qrs).

Theorem mutate_within_sound : forall W prs qrs d q name q',
  In (name, q') (mutate_within W prs qrs d q) -> dle (q_le_within W) d q q'.
Proof. intros W prs qrs d q name q'. apply mut_q_in_sound. Qed.

Print Assumptions mutate_within_sound.

(** Without further rules and in the class of all worlds, it is [mutate]. *)
Lemma mutate_within_all : forall d q, mutate_within all_worlds [] [] d q = mutate d q.
Proof.
  intros d q. unfold mutate_within, mutate. rewrite !app_nil_r.
  symmetry. apply (proj2 (mut_eq pred_rules query_rules)).
Qed.

(** ---------------- value-semantic rules ---------------- *)

Lemma le_1_2 : (1 <= 2)%Z. Proof. lia. Qed.
Lemma lt_0_3 : (0 < 3)%Z. Proof. lia. Qed.

Definition value_rules : list vrule :=
  [ r_countd_count; r_count_countd;        (* rule 18 and its reverse *)
    r_avg_max;                             (* rule 19 *)
    r_min_max; r_max_min;                  (* rule 20 and its reverse *)
    r_var_std;                             (* rule 21 *)
    r_std_var;                             (* rule 22 *)
    r_sum_scale 2 le_1_2;                  (* rule 23 *)
    r_shift 3 lt_0_3;                      (* rule 24 *)
    r_scale 2 le_1_2;                      (* rule 25 *)
    r_mono_shift 3 lt_0_3;                 (* rule 26, FUNC(a + k) *)
    r_mono_scale 2 le_1_2 ].               (* rule 26, FUNC(c * k) for c >= 0 *)

(** The value mutator of the framework. *)
Definition vmutate : vquery -> list qmutant := vmut value_rules.

(** Its soundness: rows correspond one to one, agree outside column [j] and are
    related by the rule's relation in column [j]. *)
Theorem vmutate_sound : forall v name r j v',
  In (name, (r, (j, v'))) (vmutate v) ->
  forall env db, Forall2 (row_rel r j) (veval env db v) (veval env db v').
Proof. intros v name r j v'. apply vmut_sound. Qed.

Print Assumptions vmutate_sound.

(** The value mutator for a class of worlds [W], with further value rules that are
    sound in that class only: rules proved against the semantics of one dialect.  The
    rules above are sound in every world, hence in [W]. *)
Definition vmutate_within (W : db_t -> Prop) (vrs : list (vrule_in W)) : vquery -> list qmutant :=
  vmut_in W (map (vrule_at W) value_rules ++ vrs).

Theorem vmutate_within_sound : forall W vrs v name r j v',
  In (name, (r, (j, v'))) (vmutate_within W vrs v) ->
  forall env db, W db -> Forall2 (row_rel r j) (veval env db v) (veval env db v').
Proof. intros W vrs v name r j v'. apply vmut_in_sound. Qed.

Print Assumptions vmutate_within_sound.


(** ---------------- HAVING ---------------- *)

(** Mutation of the HAVING predicate, with the predicate and query rules above. *)
Definition hmutate : dir -> vquery -> list (string * vquery) :=
  hmut pred_rules query_rules.

Theorem hmutate_sound : forall d v name v',
  In (name, v') (hmutate d v) -> dle v_sub d v v'.
Proof. intros d v name v'. apply hmut_sound. Qed.

Print Assumptions hmutate_sound.

(** ---------------- UNION ALL of value queries ---------------- *)

From ValScope Require Import VUnion.

(** Value mutation of one arm of a UNION ALL of value queries. *)
Definition tmutate : vtop -> list tmutant := tmut value_rules.

Theorem tmutate_sound : forall t name r j t',
  In (name, (r, (j, t'))) (tmutate t) ->
  forall env db, Forall2 (row_rel r j) (teval env db t) (teval env db t').
Proof. intros t name r j t'. apply tmut_sound. Qed.

Print Assumptions tmutate_sound.

(** Value mutants keep the grouping keys, HAVING predicates and sources of every arm. *)
Theorem tmutate_frame : forall t name r j t', In (name, (r, (j, t'))) (tmutate t) -> same_frame t t'.
Proof. intros t name r j t'. apply tmut_frame. Qed.

Print Assumptions tmutate_frame.

(** The same for value queries with UNION ALL, which is what the command-line front
    end mutates. *)
Definition tmutate_within (W : db_t -> Prop) (vrs : list (vrule_in W)) : vtop -> list tmutant :=
  tmut_in W (map (vrule_at W) value_rules ++ vrs).

Theorem tmutate_within_sound : forall W vrs t name r j t',
  In (name, (r, (j, t'))) (tmutate_within W vrs t) ->
  forall env db, W db -> Forall2 (row_rel r j) (teval env db t) (teval env db t').
Proof. intros W vrs t name r j t'. apply tmut_in_sound. Qed.

Print Assumptions tmutate_within_sound.

(** HAVING mutation of one arm. *)
Definition thmutate : dir -> vtop -> list (string * vtop) := thmut pred_rules query_rules.

Theorem thmutate_sound : forall d t name t', In (name, t') (thmutate d t) -> dle t_sub d t t'.
Proof. intros d t name t'. apply thmut_sound. Qed.

Print Assumptions thmutate_sound.

(** ---------------- DISTINCT value queries (and UNION of value queries) ---------------- *)

From ValScope Require Import VDistinct.

(** The same mutants under DISTINCT: every row on each side is related to a row on the
    other side ([covers]); the rows no longer correspond one to one. *)
Theorem tmutate_distinct_sound : forall t name r j t',
  In (name, (r, (j, t'))) (tmutate t) ->
  forall env db, covers r j (distinct_rows (teval env db t)) (distinct_rows (teval env db t')).
Proof. intros t name r j t'. apply tmut_distinct_sound. Qed.

Print Assumptions tmutate_distinct_sound.

(** HAVING mutants under DISTINCT: inclusion of the sets of rows. *)
Theorem thmutate_distinct_sound : forall d t name t', In (name, t') (thmutate d t) -> dle d_sub d t t'.
Proof. intros d t name t'. apply thmut_distinct_sound. Qed.

Print Assumptions thmutate_distinct_sound.

(** ---------------- what the command-line front end may see ----------------

    The extracted rule records carry no proof.  The front end only needs the names of
    the registered rules; the rule types are made abstract in the interface it is
    compiled against (see the Makefile), so OCaml code cannot build a rule. *)

(** The names of the rules on queries and on select items of this mutator that are
    sound in a class of worlds only.  The registry has none; a development that adds
    such rules lists them here.  The checker then keeps their mutants to the queries of
    that class (bridge/collation_law.py: compared_selections) and does not judge a rule
    on select items under DISTINCT or UNION, where the theorems are about the rules of
    the registry (VDistinct.v, VSet.v). *)
Definition class_rule_names : list string := [].

Definition pred_rule_names : list (string * dir) := map (fun r => (pr_name r, pr_dir r)) pred_rules.
Definition query_rule_names : list (string * dir) := map (fun r => (qr_name r, qr_dir r)) query_rules.
Definition value_rule_names : list (string * vrel) := map (fun r => (vr_name r, vr_rel r)) value_rules.

(** DISTINCT on some arms of a UNION ALL (SELECT DISTINCT arms, nested UNIONs): the same
    cover, with the DISTINCT parts given by a mask over the UNION ALL. *)
Theorem tmutate_mask_sound : forall t m name r j t',
  In (name, (r, (j, t'))) (tmutate t) ->
  forall env db, covers r j (meval env db m t) (meval env db m t').
Proof. intros t m name r j t'. apply tmut_mask_sound. Qed.

Print Assumptions tmutate_mask_sound.

(** ---------------- INTERSECT / EXCEPT of value queries ---------------- *)

From ValScope Require Import VSet.

(** HAVING mutation inside the operands of INTERSECT and EXCEPT (the direction flipped in
    the right operand of EXCEPT): inclusion of the sets of rows. *)
Definition shmutate : dir -> stop -> list (string * stop) := shmut pred_rules query_rules.

Theorem shmutate_sound : forall d s name s', In (name, s') (shmutate d s) -> dle s_incl d s s'.
Proof. intros d s name s'. apply shmut_sound. Qed.

Print Assumptions shmutate_sound.

(** A mutation outside the DISTINCT parts keeps the one-to-one correspondence of rows. *)
Theorem tmutate_mask_plain_sound : forall t m name r j t',
  In (name, (r, (j, t'))) (tmutate t) -> same_under m t t' ->
  forall env db, Forall2 (row_rel r j) (meval env db m t) (meval env db m t').
Proof. intros t m name r j t'. apply tmut_mask_plain_sound. Qed.

Print Assumptions tmutate_mask_plain_sound.

(** ---------------- a mutated value through a derived table ---------------- *)

From ValScope Require Import VLineage.

(** The inner value query is mutated; the outer query (projection, SUM / MIN / MAX / AVG,
    opaque WHERE, GROUP BY, HAVING and items that do not read the mutated column) passes
    the relation on to the one item that reads the column. *)
Definition wmutate : wtop -> list (string * (vrel * (nat * wtop))) := wmut value_rules.

Theorem wmutate_sound : forall w name r i w',
  In (name, (r, (i, w'))) (wmutate w) ->
  forall oe env db, Forall2 (row_rel r i) (wteval oe env db w) (wteval oe env db w').
Proof. intros w name r i w'. apply wmut_sound. Qed.

Print Assumptions wmutate_sound.

(** The same under SELECT DISTINCT of the outer query: a cover. *)
Theorem wmutate_distinct_sound : forall w name r i w',
  In (name, (r, (i, w'))) (wmutate w) ->
  forall oe env db, covers r i (distinct_rows (wteval oe env db w)) (distinct_rows (wteval oe env db w')).
Proof.
  intros w name r i w' H oe env db. apply covers_distinct, forall2_covers.
  exact (wmutate_sound w name r i w' H oe env db).
Qed.

Print Assumptions wmutate_distinct_sound.
